"""
Builds the translation pipeline as a LangGraph StateGraph.

    check_input → detect_rules → [detect_llm] → [ask_user] → pre_parse
    → build_facts_ir → [review_ir] → validate_ir
    → translate → clean_output → validate_output (↺ translate, up to 3 attempts)
    → finalize

See claude-logs/langgraph-plan.md for the design.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph import nodes, routing
from app.graph.state import PipelineState
from app.pipeline import PipelineResult

# Longest path is 17 steps (LLM detection + IR review + 3 translation attempts).
RECURSION_LIMIT = 40


@lru_cache(maxsize=1)
def get_graph():
    graph = StateGraph(PipelineState)

    for name in (
        "check_input", "detect_rules", "detect_llm", "ask_user",
        "pre_parse", "build_facts_ir", "review_ir", "validate_ir",
        "translate", "clean_output", "validate_output", "finalize",
    ):
        graph.add_node(name, getattr(nodes, name))

    detection_targets = ["finalize", "ask_user", "pre_parse"]

    graph.add_edge(START, "check_input")
    graph.add_edge("check_input", "detect_rules")
    graph.add_conditional_edges("detect_rules", routing.after_rules, ["detect_llm", *detection_targets])
    graph.add_conditional_edges("detect_llm", routing.after_detection, detection_targets)
    graph.add_edge("ask_user", "finalize")

    graph.add_edge("pre_parse", "build_facts_ir")
    graph.add_conditional_edges("build_facts_ir", routing.after_facts, ["review_ir", "validate_ir"])
    graph.add_edge("review_ir", "validate_ir")
    graph.add_conditional_edges("validate_ir", routing.after_ir, ["translate", "finalize"])

    graph.add_edge("translate", "clean_output")
    graph.add_edge("clean_output", "validate_output")
    graph.add_conditional_edges("validate_output", routing.after_validation, ["translate", "finalize"])
    graph.add_edge("finalize", END)

    return graph.compile()


def run_graph(
    code: str,
    target: str,
    source: str,
    use_llm_detection: bool,
    stop_after: str,
) -> PipelineResult:
    state = get_graph().invoke(
        {
            "code":              code,
            "target":            target,
            "source_request":    source,
            "use_llm_detection": use_llm_detection,
            "stop_after":        stop_after,
        },
        config={"recursion_limit": RECURSION_LIMIT, "run_name": "translation_pipeline"},
    )
    return state["result"]
