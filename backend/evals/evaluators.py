"""
Evaluators for the golden translation dataset.

Cheap, deterministic checks (run in the same pass as the pipeline):
    detection_correct   source framework detected correctly
    ir_*_recall         share of expected IR names the extractor found
    translation_valid   pipeline's final output passed translation_validator

LLM judge (run as a separate pass so the judge model doesn't evict the
translator model from GPU memory between every example):
    behavior_pass_rate  share of behavior specs the judge says the translation keeps
"""

from __future__ import annotations

import json
import os

IR_FIELDS = ("props", "state", "computed", "methods", "lifecycle")

# Treat near-equivalent teardown hooks as the same when scoring.
_HOOK_ALIASES = {"onBeforeDestroy": "onDestroy"}


def detection_correct(outputs: dict, reference_outputs: dict) -> dict:
    expected = reference_outputs["expected_source"]
    got = (outputs or {}).get("detected_source")
    return {
        "key": "detection_correct",
        "score": int(got == expected),
        "comment": f"expected {expected}, got {got}",
    }


def _actual_names(ir: dict, field: str) -> set[str]:
    items = ir.get(field) or []
    if field == "lifecycle":
        return {_HOOK_ALIASES.get(i.get("hook", ""), i.get("hook", "")) for i in items}
    return {i.get("name", "") for i in items}


def _normalize_component(name: str | None) -> str:
    name = (name or "").strip().lower()
    return name[: -len("component")] if name.endswith("component") and name != "component" else name


def ir_recall(outputs: dict, reference_outputs: dict) -> dict:
    expected_ir = reference_outputs["expected_ir"]
    ir = (outputs or {}).get("ir") or {}
    results = []
    total_expected = total_found = 0

    for field in IR_FIELDS:
        expected = set(expected_ir.get(field, []))
        if not expected:
            continue
        found = expected & _actual_names(ir, field)
        total_expected += len(expected)
        total_found += len(found)
        missing = sorted(expected - found)
        results.append({
            "key": f"ir_{field}_recall",
            "score": len(found) / len(expected),
            "comment": f"missing: {missing}" if missing else "all found",
        })

    results.append({
        "key": "ir_recall",
        "score": total_found / total_expected if total_expected else 1.0,
        "comment": f"{total_found}/{total_expected} expected names found",
    })

    expected_component = expected_ir.get("component")
    if expected_component:
        got = ir.get("component")
        results.append({
            "key": "ir_component_correct",
            "score": int(_normalize_component(got) == _normalize_component(expected_component)),
            "comment": f"expected {expected_component}, got {got}",
        })

    return {"results": results}


def translation_valid(outputs: dict) -> dict:
    outputs = outputs or {}
    ok = bool(outputs.get("ok")) and bool(outputs.get("translated_code"))
    errors = outputs.get("errors") or []
    return {
        "key": "translation_valid",
        "score": int(ok),
        "comment": "; ".join(errors)[:500] if errors else f"stage={outputs.get('stage')}",
    }


# ── LLM judge ────────────────────────────────────────────────────────────────

DEFAULT_JUDGE_MODEL = "gemma3:12b"


def judge_model() -> str:
    return os.getenv("JUDGE_MODEL", DEFAULT_JUDGE_MODEL)


_JUDGE_SYSTEM = """You are a strict reviewer of frontend code translations.
You receive a source component, its translation into another framework, and a
list of required behaviors. For each behavior, decide whether the TRANSLATED
code implements it exactly as described. Judge only the translated code's
actual logic; do not assume behavior that is not in the code. Idiomatic
differences between frameworks are fine as long as the behavior matches.

Respond with JSON only, in this shape:
{"verdicts": [{"behavior": 1, "pass": true, "reason": "short reason"}, ...]}
Include exactly one verdict per behavior, numbered as given."""


def _judge_chat(messages: list[dict]) -> str:
    import requests

    base = os.environ["OLLAMA_BASE_URL"].rstrip("/")
    response = requests.post(
        f"{base}/api/chat",
        json={
            "model": judge_model(),
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_ctx": 8192},
        },
        timeout=int(os.getenv("JUDGE_TIMEOUT_SECS", "300")),
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def behavior_judge(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    translated = (outputs or {}).get("translated_code") or ""
    behaviors = reference_outputs["behaviors"]

    if not translated.strip():
        return {"key": "behavior_pass_rate", "score": 0.0, "comment": "no translated code produced"}

    numbered = "\n".join(f"{i}. {b}" for i, b in enumerate(behaviors, start=1))
    user = (
        f"Source framework: {reference_outputs['expected_source']}\n"
        f"Target framework: {inputs['target']}\n\n"
        f"Note: {reference_outputs.get('judge_notes', '')}\n\n"
        f"SOURCE CODE:\n```\n{inputs['code']}\n```\n\n"
        f"TRANSLATED CODE:\n```\n{translated}\n```\n\n"
        f"REQUIRED BEHAVIORS:\n{numbered}"
    )

    raw = _judge_chat([
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user", "content": user},
    ])

    try:
        verdicts = json.loads(raw)["verdicts"]
        by_number = {int(v["behavior"]): v for v in verdicts}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return {"key": "behavior_pass_rate", "score": None, "comment": f"unparseable judge output: {raw[:300]}"}

    passed, failures = 0, []
    for i, behavior in enumerate(behaviors, start=1):
        verdict = by_number.get(i)
        if verdict and verdict.get("pass") is True:
            passed += 1
        else:
            reason = verdict.get("reason", "") if verdict else "no verdict returned"
            failures.append(f"[{i}] {behavior} -> {reason}")

    return {
        "key": "behavior_pass_rate",
        "score": passed / len(behaviors),
        "comment": "all behaviors pass" if not failures else "\n".join(failures)[:2000],
    }
