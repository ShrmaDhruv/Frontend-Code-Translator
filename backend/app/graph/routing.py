"""
Routing functions for the pipeline graph. Pure: they only read state.
"""

from __future__ import annotations

from app.graph.state import PipelineState
from app.translation import MAX_TRANSLATION_ATTEMPTS


def after_rules(state: PipelineState) -> str:
    layer1 = state.get("layer1")
    if layer1 is not None and layer1.is_ambiguous and state["use_llm_detection"]:
        return "detect_llm"
    return after_detection(state)


def after_detection(state: PipelineState) -> str:
    if state["stop_after"] == "detect":
        return "finalize"
    if state["detection"].ask_user:
        return "ask_user"
    return "pre_parse"


def after_facts(state: PipelineState) -> str:
    return "review_ir" if state["review_reasons"] else "validate_ir"


def after_ir(state: PipelineState) -> str:
    if state["stop_after"] == "ir":
        return "finalize"
    target = state["target"]
    if state["detection"].framework == target or state["ir"].framework == target:
        return "finalize"
    return "translate"


def after_validation(state: PipelineState) -> str:
    if state["validation"].is_valid or state["attempts"] >= MAX_TRANSLATION_ATTEMPTS:
        return "finalize"
    return "translate"
