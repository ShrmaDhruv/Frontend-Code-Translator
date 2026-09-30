"""
LangGraph pipeline: routing unit tests + end-to-end graph paths with fake LLM clients.

The graph replaced the hand-rolled pipeline after an offline parity suite
(legacy vs graph, identical results and prompts) and a live eval
(graph-v1-c991b353 == fixes-v2-5a4b1f2f) showed no behaviour change.
These tests pin that behaviour per path, without Ollama.

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
from app.ir import extract_ir
from app.pipeline import ASK_USER_ERROR, LOW_CONFIDENCE_WARNING, SAME_FRAMEWORK_WARNING, run_pipeline
from tests.test_llm_detector import NIGHTMARE_REACT_NO_JSX

DATASET = Path(__file__).resolve().parents[1] / "evals" / "dataset" / "components"
FRAMEWORK_DIRS = {"react": "React", "vue": "Vue", "angular": "Angular", "html": "HTML"}
TARGETS = ("React", "Vue", "Angular", "HTML")

DATASET_CASES = [
    (FRAMEWORK_DIRS[path.parent.name], path.read_text(encoding="utf-8"), path.name)
    for path in sorted(DATASET.glob("*/*"))
]
DATASET_IDS = [case[2] for case in DATASET_CASES]
REACT_COUNTER = next(code for fw, code, name in DATASET_CASES if fw == "React" and "counter" in name)

VALID_VUE = """<template>
  <button @click="increment">{{ count }}</button>
</template>

<script setup>
import { ref } from 'vue'

const count = ref(0)

function increment() {
  count.value++
}
</script>"""

BROKEN_REACT = """
import { useState } from "react";
export default function Broken({ label }) {
  const [count, setCount] = useState(0
  function bump() { setCount(count + 1) }
  return <button onClick={bump}>{label} {count}</button>
}
"""

IR_REPLY = json.dumps({
    "framework": "React", "component": "Broken",
    "props": [{"name": "label", "type": "string"}],
    "state": [{"name": "count", "type": "number", "initial": "0"}],
    "computed": [], "methods": [{"name": "bump", "params": [], "body": "setCount(count + 1)"}],
    "lifecycle": [], "imports": [], "styles": "",
})


class FakeClient:
    """Records every chat call; replies from a function of (messages, call index)."""

    def __init__(self, reply, available=True):
        self.reply = reply
        self.available = available
        self.calls = []

    def chat(self, messages, max_new_tokens=512, temperature=0.1):
        self.calls.append(messages)
        return self.reply(messages, len(self.calls) - 1)

    def is_available(self):
        return self.available


@pytest.fixture
def fakes(monkeypatch):
    monkeypatch.setenv("IR_MODE", "facts")
    state = SimpleNamespace(llm_calls=[])

    def install(translator_reply=lambda m, i: "nope", available=True, llm_confidence="high"):
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
        return state

    state.install = install
    install()
    return state


# ── Dataset: detection + IR through the graph ─────────────────────────────────

@pytest.mark.parametrize("framework,code,name", DATASET_CASES, ids=DATASET_IDS)
def test_dataset_detect_and_ir(fakes, framework, code, name):
    detected = run_pipeline(code, target="Vue", stop_after="detect")
    assert detected.ok and detected.stage == "detect"
    assert detected.detection.framework == framework

    result = run_pipeline(code, target="Vue", stop_after="ir")
    assert result.ok and result.stage == "ir"
    assert result.ir.to_dict() == extract_ir(code, framework).to_dict()
    assert fakes.translator.calls == []


@pytest.mark.parametrize("framework,code,name", DATASET_CASES, ids=DATASET_IDS)
def test_dataset_same_framework_returns_source(fakes, framework, code, name):
    result = run_pipeline(code, target=framework)
    assert result.ok and result.stage == "translate"
    assert result.translated_code == code
    assert result.warnings == [SAME_FRAMEWORK_WARNING]
    assert fakes.translator.calls == []


# ── Translation loop ──────────────────────────────────────────────────────────

def test_valid_first_attempt(fakes):
    fakes.install(translator_reply=lambda m, i: VALID_VUE)
    result = run_pipeline(REACT_COUNTER, target="Vue")
    assert len(fakes.translator.calls) == 1
    assert result.translated_code == VALID_VUE
    assert result.ok is (not result.errors)


def test_retries_exhausted(fakes):
    result = run_pipeline(REACT_COUNTER, target="Vue")
    calls = fakes.translator.calls
    assert len(calls) == translation.MAX_TRANSLATION_ATTEMPTS
    assert result.ok is False and result.errors and result.stage == "translate"
    assert len(calls[0]) == 2
    for retry in calls[1:]:
        assert len(retry) == 4
        assert "Your previous translation had these problems" in retry[-1]["content"]


def test_retry_prompt_carries_last_errors(fakes):
    fakes.install(translator_reply=lambda m, i: "nope" if i == 0 else VALID_VUE)
    run_pipeline(REACT_COUNTER, target="Vue")
    retry = fakes.translator.calls[1][-1]["content"]
    assert "too short" in retry


def test_translator_unreachable(fakes):
    fakes.install(available=False)
    with pytest.raises(RuntimeError, match="not reachable"):
        run_pipeline(REACT_COUNTER, target="Vue")


# ── Detection branches ────────────────────────────────────────────────────────

def test_manual_source_skips_detection(fakes):
    result = run_pipeline(REACT_COUNTER, target="Vue", source="React", stop_after="detect")
    assert result.detection.source == "manual" and result.detection.framework == "React"


@pytest.mark.parametrize("llm_confidence,proceeds", [("high", True), ("low", False), ("down", False)])
def test_ambiguous_detection(fakes, llm_confidence, proceeds):
    fakes.install(llm_confidence=llm_confidence)
    result = run_pipeline(NIGHTMARE_REACT_NO_JSX, target="Vue", stop_after="ir")
    assert fakes.llm_calls == [NIGHTMARE_REACT_NO_JSX]
    if proceeds:
        assert result.ok and result.stage == "ir" and result.detection.source == "layer3"
    else:
        assert not result.ok and result.stage == "detect" and result.errors == [ASK_USER_ERROR]


def test_ambiguous_stop_after_detect_warns(fakes):
    fakes.install(llm_confidence="low")
    result = run_pipeline(NIGHTMARE_REACT_NO_JSX, target="Vue", stop_after="detect")
    assert not result.ok and result.warnings == [LOW_CONFIDENCE_WARNING] and result.errors == []


def test_ambiguous_without_llm_asks_user(fakes):
    result = run_pipeline(NIGHTMARE_REACT_NO_JSX, target="Vue", use_llm_detection=False)
    assert fakes.llm_calls == []
    assert not result.ok and result.stage == "detect" and result.errors == [ASK_USER_ERROR]


# ── IR review ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ir_mode", ["hybrid", "llm"])
def test_ir_review_uses_llm(monkeypatch, fakes, ir_mode):
    monkeypatch.setenv("IR_MODE", ir_mode)
    result = run_pipeline(BROKEN_REACT, target="Vue", source="React", stop_after="ir")
    assert fakes.ir_client.calls, "review LLM should have been called"
    assert {m.name for m in result.ir.methods} >= {"bump"}


def test_facts_mode_never_calls_ir_llm(fakes):
    run_pipeline(BROKEN_REACT, target="Vue", source="React", stop_after="ir")
    assert fakes.ir_client.calls == []


# ── Input errors ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kwargs", [
    {"target": "Auto Detect"},
    {"target": "Svelte"},
    {"target": "Vue", "source": "Svelte"},
])
def test_invalid_frameworks(fakes, kwargs):
    with pytest.raises(ValueError):
        run_pipeline(REACT_COUNTER, **kwargs)


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
