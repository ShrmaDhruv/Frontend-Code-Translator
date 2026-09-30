"""
LangGraph pipeline: routing unit tests + legacy/graph parity with fake LLM clients.

Parity = identical PipelineResult.to_dict() and identical LLM calls (same
prompts, same order) for both PIPELINE_ENGINE values, so the graph can be
proven behaviour-preserving without Ollama.

Run: python -m pytest tests/test_graph.py -q
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.detection.llm_detector as llm_detector
import app.ir.builder as ir_builder
import app.translation as translation
from app.detection.llm_detector.score_merger import MergedResult
from app.graph import routing
from app.pipeline import run_pipeline
from tests.test_llm_detector import NIGHTMARE_REACT_NO_JSX

DATASET = Path(__file__).resolve().parents[1] / "evals" / "dataset" / "components"
FRAMEWORK_DIRS = {"react": "React", "vue": "Vue", "angular": "Angular", "html": "HTML"}
TARGETS = ("React", "Vue", "Angular", "HTML")

DATASET_CASES = [
    (FRAMEWORK_DIRS[path.parent.name], path.read_text(encoding="utf-8"), path.name)
    for path in sorted(DATASET.glob("*/*"))
]

BROKEN_REACT = """
import { useState } from "react";
export default function Broken({ label }) {
  const [count, setCount] = useState(0
  function bump() { setCount(count + 1) }
  return <button onClick={bump}>{label} {count}</button>
}
"""


class FakeClient:
    """Records every chat call; replies from a function of (messages, call index)."""

    def __init__(self, reply, available=True):
        self.reply = reply
        self.available = available
        self.calls = []

    def chat(self, messages, max_new_tokens=512, temperature=0.1):
        self.calls.append((json.dumps(messages), max_new_tokens, temperature))
        return self.reply(messages, len(self.calls) - 1)

    def is_available(self):
        return self.available


def bad_then_source(messages, index):
    """First attempt fails validation, retries echo the source (usually still invalid)."""
    return "nope" if index == 0 else messages[-1]["content"]


IR_REPLY = json.dumps({
    "framework": "React", "component": "Broken",
    "props": [{"name": "label", "type": "string"}],
    "state": [{"name": "count", "type": "number", "initial": "0"}],
    "computed": [], "methods": [{"name": "bump", "params": [], "body": "setCount(count + 1)"}],
    "lifecycle": [], "imports": [], "styles": "",
})


@pytest.fixture
def fakes(monkeypatch):
    state = SimpleNamespace(translator=None, ir_client=None, llm_calls=[])

    def install(translator_reply=bad_then_source, available=True, llm_confidence="high"):
        state.translator = FakeClient(translator_reply, available)
        state.ir_client = FakeClient(lambda m, i: IR_REPLY)
        state.llm_calls = []

        def fake_detect_with_llm(code, scores):
            state.llm_calls.append(code)
            if llm_confidence == "down":
                raise RuntimeError("Ollama is not reachable")
            return MergedResult(
                detected="React", confidence=llm_confidence, ask_user=llm_confidence == "low",
                reasoning="fake", layer1_top="HTML", layer3_result="React", source="layer3",
            )

        monkeypatch.setattr(translation, "_get_client", lambda: state.translator)
        monkeypatch.setattr(ir_builder, "_get_client", lambda: state.ir_client)
        monkeypatch.setattr(llm_detector, "detect_with_llm", fake_detect_with_llm)

    state.install = install
    return state


def run_engine(monkeypatch, fakes, engine, install_kwargs, **kwargs):
    monkeypatch.setenv("PIPELINE_ENGINE", engine)
    fakes.install(**install_kwargs)
    try:
        outcome = run_pipeline(**kwargs).to_dict()
    except (ValueError, RuntimeError) as exc:
        outcome = f"{type(exc).__name__}: {exc}"
    return outcome, fakes.translator.calls, fakes.ir_client.calls, fakes.llm_calls


def assert_parity(monkeypatch, fakes, install_kwargs=None, **kwargs):
    install_kwargs = install_kwargs or {}
    legacy = run_engine(monkeypatch, fakes, "legacy", install_kwargs, **kwargs)
    graph = run_engine(monkeypatch, fakes, "graph", install_kwargs, **kwargs)
    assert graph[0] == legacy[0], "PipelineResult differs"
    assert graph[1] == legacy[1], "translation LLM calls differ"
    assert graph[2] == legacy[2], "IR review LLM calls differ"
    assert graph[3] == legacy[3], "LLM detection calls differ"
    return legacy


# ── Parity over the golden dataset ────────────────────────────────────────────

@pytest.mark.parametrize("ir_mode", ["facts", "hybrid"])
@pytest.mark.parametrize("stop_after", ["detect", "ir", "translate"])
@pytest.mark.parametrize("framework,code,name", DATASET_CASES, ids=[c[2] for c in DATASET_CASES])
def test_dataset_parity(monkeypatch, fakes, framework, code, name, stop_after, ir_mode):
    monkeypatch.setenv("IR_MODE", ir_mode)
    for target in TARGETS:
        assert_parity(monkeypatch, fakes, code=code, target=target, stop_after=stop_after)


def test_manual_source_parity(monkeypatch, fakes):
    _, code, _ = DATASET_CASES[0]
    assert_parity(monkeypatch, fakes, code=code, target="Vue", source="Angular")


def test_retries_exhausted_parity(monkeypatch, fakes):
    monkeypatch.setenv("IR_MODE", "facts")
    _, code, _ = DATASET_CASES[0]
    result, translator_calls, _, _ = assert_parity(
        monkeypatch, fakes, install_kwargs={"translator_reply": lambda m, i: "nope"},
        code=code, target="Vue",
    )
    assert len(translator_calls) == translation.MAX_TRANSLATION_ATTEMPTS
    assert result["ok"] is False and result["errors"]


# ── Detection branches ────────────────────────────────────────────────────────

@pytest.mark.parametrize("llm_confidence", ["high", "low", "down"])
@pytest.mark.parametrize("stop_after", ["detect", "translate"])
def test_ambiguous_detection_parity(monkeypatch, fakes, llm_confidence, stop_after):
    monkeypatch.setenv("IR_MODE", "facts")
    result, *_ , llm_calls = assert_parity(
        monkeypatch, fakes, install_kwargs={"llm_confidence": llm_confidence},
        code=NIGHTMARE_REACT_NO_JSX, target="Vue", stop_after=stop_after,
    )
    assert llm_calls == [NIGHTMARE_REACT_NO_JSX]


def test_ambiguous_without_llm_parity(monkeypatch, fakes):
    result, *_ = assert_parity(
        monkeypatch, fakes, code=NIGHTMARE_REACT_NO_JSX, target="Vue", use_llm_detection=False,
    )
    assert result["ok"] is False and result["stage"] == "detect"


# ── IR review branches ────────────────────────────────────────────────────────

@pytest.mark.parametrize("ir_mode", ["hybrid", "llm"])
def test_ir_review_parity(monkeypatch, fakes, ir_mode):
    monkeypatch.setenv("IR_MODE", ir_mode)
    result, _, ir_calls, _ = assert_parity(
        monkeypatch, fakes, code=BROKEN_REACT, target="Vue", source="React", stop_after="ir",
    )
    assert ir_calls, "review LLM should have been called"


# ── Errors ────────────────────────────────────────────────────────────────────

def test_error_parity(monkeypatch, fakes):
    _, code, _ = DATASET_CASES[0]
    assert "ValueError" in assert_parity(monkeypatch, fakes, code=code, target="Auto Detect")[0]
    assert "ValueError" in assert_parity(monkeypatch, fakes, code=code, target="Svelte")[0]
    assert "ValueError" in assert_parity(monkeypatch, fakes, code=code, target="Vue", source="Svelte")[0]
    outcome = assert_parity(
        monkeypatch, fakes, install_kwargs={"available": False},
        code=code, target="Vue", source="React",
    )[0]
    assert "RuntimeError" in outcome


# ── Routing ───────────────────────────────────────────────────────────────────

def _state(**overrides):
    base = {
        "stop_after": "translate", "target": "Vue", "use_llm_detection": True,
        "layer1": SimpleNamespace(is_ambiguous=False),
        "detection": SimpleNamespace(ask_user=False, framework="React"),
        "ir": SimpleNamespace(framework="React"),
        "review_reasons": [], "attempts": 1,
        "validation": SimpleNamespace(is_valid=False),
    }
    base.update(overrides)
    return base


def test_routing():
    assert routing.after_rules(_state(layer1=SimpleNamespace(is_ambiguous=True))) == "detect_llm"
    assert routing.after_rules(_state(layer1=SimpleNamespace(is_ambiguous=True), use_llm_detection=False)) == "pre_parse"
    assert routing.after_rules(_state(layer1=None)) == "pre_parse"
    assert routing.after_detection(_state(stop_after="detect")) == "finalize"
    assert routing.after_detection(_state(detection=SimpleNamespace(ask_user=True, framework="React"))) == "ask_user"
    assert routing.after_facts(_state(review_reasons=["x"])) == "review_ir"
    assert routing.after_facts(_state()) == "validate_ir"
    assert routing.after_ir(_state(stop_after="ir")) == "finalize"
    assert routing.after_ir(_state(target="React")) == "finalize"
    assert routing.after_ir(_state()) == "translate"
    assert routing.after_validation(_state()) == "translate"
    assert routing.after_validation(_state(attempts=3)) == "finalize"
    assert routing.after_validation(_state(validation=SimpleNamespace(is_valid=True))) == "finalize"
