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


# Short on purpose: a longer "trace step by step" prompt measured worse on the
# calibration set (gemma3:12b rationalised buggy code into passes; bug recall 0/7
# vs 3/7). Re-run `python -m evals.calibrate_judge` before changing it.
_JUDGE_SYSTEM = """You are a strict reviewer of frontend code translations.
You receive a source component, its translation into another framework, and a
list of required behaviors. For each behavior, decide whether the TRANSLATED
code implements it exactly as described. Judge only the translated code's
actual logic; do not assume behavior that is not in the code. Idiomatic
differences between frameworks are fine as long as the behavior matches.

Respond with JSON only, in this shape:
{"verdicts": [{"behavior": 1, "reasoning": "short reason", "pass": true}, ...]}
Include exactly one verdict per behavior, numbered as given. Inside "reasoning",
quote code with backticks or single quotes, never with double quotes."""


_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "behavior":  {"type": "integer"},
                    "reasoning": {"type": "string"},
                    "pass":      {"type": "boolean"},
                },
                "required": ["behavior", "reasoning", "pass"],
            },
        },
    },
    "required": ["verdicts"],
}


def _judge_chat(messages: list[dict]) -> str:
    import requests

    from app.ollama_client.retry import post_with_retry

    base = os.environ["OLLAMA_BASE_URL"].rstrip("/")
    response = post_with_retry(
        requests,
        f"{base}/api/chat",
        {
            "model": judge_model(),
            "messages": messages,
            "stream": False,
            "format": _JUDGE_SCHEMA,
            "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 3000},
        },
        int(os.getenv("JUDGE_TIMEOUT_SECS", "300")),
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


def judge_verdicts(
    source_code: str,
    target: str,
    translated: str,
    reference_outputs: dict,
    system_prompt: str | None = None,
) -> tuple[list[dict] | None, str]:
    """
    Ask the judge for one verdict per behavior.

    Returns (verdicts, raw). `verdicts` is None when the judge output is unusable
    (not JSON, or missing any behavior); a judge failure is not a translation failure.
    """
    behaviors = reference_outputs["behaviors"]
    numbered = "\n".join(f"{i}. {b}" for i, b in enumerate(behaviors, start=1))
    user = (
        f"Source framework: {reference_outputs['expected_source']}\n"
        f"Target framework: {target}\n\n"
        f"Note: {reference_outputs.get('judge_notes', '')}\n\n"
        f"SOURCE CODE:\n```\n{source_code}\n```\n\n"
        f"TRANSLATED CODE:\n```\n{translated}\n```\n\n"
        f"REQUIRED BEHAVIORS:\n{numbered}"
    )
    raw = _judge_chat([
        {"role": "system", "content": system_prompt or _JUDGE_SYSTEM},
        {"role": "user", "content": user},
    ])

    try:
        by_number = {int(v["behavior"]): v for v in json.loads(raw)["verdicts"]}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None, raw

    verdicts = []
    for i, behavior in enumerate(behaviors, start=1):
        verdict = by_number.get(i)
        if verdict is None or not isinstance(verdict.get("pass"), bool):
            return None, raw
        verdicts.append({
            "behavior": behavior,
            "pass": verdict["pass"],
            "reason": verdict.get("reasoning") or verdict.get("reason") or "",
        })
    return verdicts, raw


def behavior_judge(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    translated = (outputs or {}).get("translated_code") or ""
    if not translated.strip():
        return {"key": "behavior_pass_rate", "score": 0.0, "comment": "no translated code produced"}

    verdicts, raw = judge_verdicts(inputs["code"], inputs["target"], translated, reference_outputs)
    if verdicts is None:
        return {"key": "behavior_pass_rate", "score": None, "comment": f"unusable judge output: {raw[:300]}"}

    failures = [
        f"[{i}] {v['behavior']} -> {v['reason']}"
        for i, v in enumerate(verdicts, start=1) if not v["pass"]
    ]
    return {
        "key": "behavior_pass_rate",
        "score": sum(v["pass"] for v in verdicts) / len(verdicts),
        "comment": "all behaviors pass" if not failures else "\n".join(failures)[:2000],
    }
