"""
Pipeline graph nodes. Each node is a thin wrapper around existing
detection / IR / translation code and returns a partial state update.
"""

from __future__ import annotations

from app.detection import detect
from app.graph.state import PipelineState
from app.ir.builder import build_facts_ir as _build_facts_ir, ensure_valid, llm_ir, review_needed
from app.ir.pre_parser import parse
from app.pipeline import (
    ASK_USER_ERROR,
    AUTO_DETECT,
    LOW_CONFIDENCE_WARNING,
    SAME_FRAMEWORK_WARNING,
    PipelineResult,
    llm_detection,
    manual_detection,
    normalize_framework,
    rule_detection,
)
from app.translation import (
    NO_TRANSLATION_WARNING,
    get_translator,
    request_translation,
    translation_messages,
)
from app.translation.response_cleaner import clean
from app.translation.validator import validate_translation


# ── Input ─────────────────────────────────────────────────────────────────────

def check_input(state: PipelineState) -> dict:
    """Normalise framework names. Phase 3 adds size caps and injection checks here."""
    target = normalize_framework(state["target"])
    if target == AUTO_DETECT:
        raise ValueError("target must be a concrete framework, not Auto Detect")
    return {
        "target":         target,
        "source_request": normalize_framework(state["source_request"]),
        "attempts":       0,
        "errors":         [],
    }


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_rules(state: PipelineState) -> dict:
    source = state["source_request"]
    if source != AUTO_DETECT:
        return {"layer1": None, "detection": manual_detection(source)}
    layer1 = detect(state["code"])
    return {"layer1": layer1, "detection": rule_detection(layer1)}


def detect_llm(state: PipelineState) -> dict:
    return {"detection": llm_detection(state["code"], state["layer1"])}


def ask_user(state: PipelineState) -> dict:
    """v1: stop with an error so the client resends with a source. Later: interrupt()."""
    return {"errors": [ASK_USER_ERROR]}


# ── IR ────────────────────────────────────────────────────────────────────────

def pre_parse(state: PipelineState) -> dict:
    return {"summary": parse(state["code"], state["detection"].framework)}


def build_facts_ir(state: PipelineState) -> dict:
    facts_ir = _build_facts_ir(state["summary"])
    return {
        "facts_ir":       facts_ir,
        "review_reasons": review_needed(state["summary"], facts_ir),
    }


def review_ir(state: PipelineState) -> dict:
    return {"ir": llm_ir(state["summary"], state["facts_ir"])}


def validate_ir(state: PipelineState) -> dict:
    facts_ir = state["facts_ir"]
    return {"ir": ensure_valid(state.get("ir", facts_ir), facts_ir)}


# ── Translation ───────────────────────────────────────────────────────────────

def translate(state: PipelineState) -> dict:
    attempts = state["attempts"]
    client   = get_translator(check=attempts == 0)
    errors   = state["validation"].errors if attempts else None
    messages = translation_messages(state["ir"], state["target"], state["code"], errors)
    return {"raw_output": request_translation(client, messages)}


def clean_output(state: PipelineState) -> dict:
    return {"translated_code": clean(state["raw_output"], state["target"])}


def validate_output(state: PipelineState) -> dict:
    validation = validate_translation(state["translated_code"], state["ir"], state["target"])
    return {"validation": validation, "attempts": state["attempts"] + 1}


# ── Result ────────────────────────────────────────────────────────────────────

def finalize(state: PipelineState) -> dict:
    """Same PipelineResult, in the same precedence order, as the legacy pipeline."""
    detection  = state["detection"]
    target     = state["target"]
    stop_after = state["stop_after"]
    base = {"target": target, "detection": detection}

    if stop_after == "detect":
        result = PipelineResult(
            ok=not detection.ask_user, source=detection.framework, stage="detect",
            warnings=[LOW_CONFIDENCE_WARNING] if detection.ask_user else [], **base,
        )
    elif detection.ask_user:
        result = PipelineResult(
            ok=False, source=detection.framework, stage="detect",
            errors=list(state["errors"]), **base,
        )
    elif stop_after == "ir":
        result = PipelineResult(
            ok=True, source=detection.framework, stage="ir", ir=state["ir"], **base,
        )
    elif detection.framework == target:
        result = PipelineResult(
            ok=True, source=detection.framework, stage="translate", ir=state["ir"],
            translated_code=state["code"], warnings=[SAME_FRAMEWORK_WARNING], **base,
        )
    elif "validation" not in state:
        # The IR's framework already equals the target, so nothing was generated.
        ir = state["ir"]
        result = PipelineResult(
            ok=True, source=ir.framework, stage="translate", ir=ir,
            warnings=[NO_TRANSLATION_WARNING], **base,
        )
    else:
        ir, validation = state["ir"], state["validation"]
        result = PipelineResult(
            ok=validation.is_valid, source=ir.framework, stage="translate", ir=ir,
            translated_code=state["translated_code"],
            warnings=validation.warnings,
            errors=validation.errors if not validation.is_valid else [],
            **base,
        )
    return {"result": result}
