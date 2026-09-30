from __future__ import annotations

from typing import TypedDict

from app.detection.rule_detector import DetectionResult
from app.ir.schema import IR
from app.pipeline import PipelineDetection, PipelineResult
from app.translation.validator import TranslationValidationResult


class PipelineState(TypedDict, total=False):
    # Request
    code:              str
    source_request:    str   # "Auto Detect" or a concrete framework
    target:            str
    use_llm_detection: bool
    stop_after:        str   # "detect" | "ir" | "translate"

    # Detection
    layer1:    DetectionResult | None
    detection: PipelineDetection

    # IR
    summary:        dict
    facts_ir:       IR
    review_reasons: list[str]
    ir:             IR

    # Translation
    raw_output:      str
    translated_code: str
    validation:      TranslationValidationResult
    attempts:        int

    # Outcome
    errors: list[str]
    result: PipelineResult

