"""
detection

Source-framework detection.

    rule_detector  Layer 1: weighted regex rules (rules/) → scores + ambiguity flag
    llm_detector   Layer 3: small-model fallback used only when Layer 1 is ambiguous
"""

from app.detection.rule_detector import DetectionResult, detect

__all__ = ["DetectionResult", "detect"]
