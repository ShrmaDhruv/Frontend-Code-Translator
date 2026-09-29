"""
Offline tests for LLM-judge response handling (no Ollama calls).

Run: python -m pytest tests/test_judge_parsing.py -q
"""

import json

import pytest

from evals import evaluators

REFERENCE = {
    "expected_source": "React",
    "behaviors": ["shows a heading", "adds a todo", "deletes a todo"],
    "judge_notes": "",
}
INPUTS = {"code": "source", "target": "Vue"}
OUTPUTS = {"translated_code": "<template><h2>x</h2></template>"}


def judge_returns(monkeypatch, raw):
    monkeypatch.setattr(evaluators, "_judge_chat", lambda messages: raw)


def verdicts(*passes):
    return json.dumps({"verdicts": [
        {"behavior": i, "reasoning": "r", "pass": p} for i, p in enumerate(passes, start=1)
    ]})


def test_all_verdicts_scored(monkeypatch):
    judge_returns(monkeypatch, verdicts(True, False, True))
    result = evaluators.behavior_judge(INPUTS, OUTPUTS, REFERENCE)
    assert result["score"] == pytest.approx(2 / 3)
    assert "[2] adds a todo" in result["comment"]


def test_incomplete_verdicts_are_unusable_not_failures(monkeypatch):
    judge_returns(monkeypatch, verdicts(True, True))
    result = evaluators.behavior_judge(INPUTS, OUTPUTS, REFERENCE)
    assert result["score"] is None
    assert result["comment"].startswith("unusable judge output")


def test_truncated_json_is_unusable(monkeypatch):
    judge_returns(monkeypatch, '{"verdicts": [{"behavior": 1, "reasoning": "uses v-model=')
    assert evaluators.behavior_judge(INPUTS, OUTPUTS, REFERENCE)["score"] is None


def test_non_boolean_pass_is_unusable(monkeypatch):
    judge_returns(monkeypatch, json.dumps({"verdicts": [
        {"behavior": 1, "pass": "yes"}, {"behavior": 2, "pass": True}, {"behavior": 3, "pass": True},
    ]}))
    assert evaluators.behavior_judge(INPUTS, OUTPUTS, REFERENCE)["score"] is None


def test_legacy_reason_key_accepted(monkeypatch):
    judge_returns(monkeypatch, json.dumps({"verdicts": [
        {"behavior": 1, "pass": True, "reason": "ok"},
        {"behavior": 2, "pass": False, "reason": "missing add"},
        {"behavior": 3, "pass": True, "reason": "ok"},
    ]}))
    assert "missing add" in evaluators.behavior_judge(INPUTS, OUTPUTS, REFERENCE)["comment"]


def test_empty_translation_scores_zero_without_calling_judge(monkeypatch):
    def fail(_):
        raise AssertionError("judge should not be called")
    monkeypatch.setattr(evaluators, "_judge_chat", fail)
    assert evaluators.behavior_judge(INPUTS, {"translated_code": "  "}, REFERENCE)["score"] == 0.0


def test_calibration_labels_match_behavior_counts():
    from evals.calibrate_judge import load_cases
    cases, dataset = load_cases()
    for case in cases:
        assert len(case["expected"]) == len(dataset["concepts"][case["concept"]]["behaviors"]), case["id"]
