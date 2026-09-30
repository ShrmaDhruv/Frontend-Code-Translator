import re
import json
from dataclasses import dataclass


VALID_FRAMEWORKS  = {"React", "Vue", "Angular", "HTML"}
VALID_CONFIDENCES = {"high", "medium", "low"}


# ─────────────────────────────────────────────
# RESULT STRUCTURE
# ─────────────────────────────────────────────

@dataclass
class ParsedResponse:
    detected:   str    # "React" | "Vue" | "Angular" | "HTML"
    confidence: str    # "high" | "medium" | "low"
    reasoning:  str    # model's explanation
    raw:        str    # original raw string (for debugging)
    parse_method: str  # how it was parsed: "json" | "regex" | "fallback"


# ─────────────────────────────────────────────
# PARSER
# ─────────────────────────────────────────────

def parse_response(raw: str) -> ParsedResponse:
    """
    Parse Ollama's raw response string into a ParsedResponse.

    Tries three methods in order:
      1. Clean JSON parse       — ideal path
      2. Regex extraction       — when model adds extra text
      3. Keyword scan fallback  — last resort

    Args:
        raw : Raw string response from Ollama

    Returns:
        ParsedResponse with detected framework and confidence.
    """

    # ── Method 1: Clean JSON parse ───────────────────────────────────────
    # Since we use Ollama's "format": "json", this should succeed 95%+ of the time
    try:
        cleaned = _clean_json_string(raw)
        data    = json.loads(cleaned)

        detected   = _extract_framework(data.get("detected", ""))
        confidence = _extract_confidence(data.get("confidence", "medium"))
        reasoning  = str(data.get("reasoning", "")).strip()

        if detected:
            return ParsedResponse(
                detected=detected,
                confidence=confidence,
                reasoning=reasoning,
                raw=raw,
                parse_method="json"
            )

    except (json.JSONDecodeError, KeyError, TypeError):
        pass


    # ── Method 2: Regex extraction ───────────────────────────────────────
    # Model added preamble or postamble around the JSON

    try:
        # Find anything that looks like {"detected": "..."}
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            data       = json.loads(json_match.group())
            detected   = _extract_framework(data.get("detected", ""))
            confidence = _extract_confidence(data.get("confidence", "medium"))
            reasoning  = str(data.get("reasoning", "")).strip()

            if detected:
                return ParsedResponse(
                    detected=detected,
                    confidence=confidence,
                    reasoning=reasoning,
                    raw=raw,
                    parse_method="regex"
                )

    except (json.JSONDecodeError, AttributeError):
        pass


    # ── Method 3: Keyword scan fallback ─────────────────────────────────
    # JSON is completely broken — scan raw text for framework names

    detected = _scan_for_framework(raw)
    return ParsedResponse(
        detected=detected or "HTML",   # default to HTML if nothing found
        confidence="low",               # low confidence since parsing failed
        reasoning="Could not parse structured response from model.",
        raw=raw,
        parse_method="fallback"
    )


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _clean_json_string(raw: str) -> str:
    """
    Strip common model artifacts from around JSON:
    - Markdown code fences: ```json ... ```
    - Leading/trailing whitespace
    - BOM characters
    """
    cleaned = raw.strip()
    # Remove ```json ... ``` or ``` ... ```
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$',          '', cleaned)
    # Trim to first { and last }
    start = cleaned.find('{')
    end   = cleaned.rfind('}')
    if start != -1 and end != -1:
        cleaned = cleaned[start:end + 1]
    return cleaned.strip()


def _extract_framework(value: str) -> str | None:
    """
    Validate and normalize the detected framework value.
    Case-insensitive match against valid frameworks.
    """
    if not value:
        return None
    # Direct match
    if value in VALID_FRAMEWORKS:
        return value
    # Case-insensitive match against all valid frameworks
    value_lower = value.strip().lower()
    for fw in VALID_FRAMEWORKS:
        if fw.lower() == value_lower:
            return fw
    # Handle "Vanilla" or "Vanilla JS" → HTML
    if "vanilla" in value_lower or "plain" in value_lower:
        return "HTML"
    return None


def _extract_confidence(value: str) -> str:
    """
    Validate confidence level. Default to 'medium' if invalid.
    """
    if value and value.lower() in VALID_CONFIDENCES:
        return value.lower()
    return "medium"


def _scan_for_framework(text: str) -> str | None:
    """
    Last resort: scan raw text for framework name mentions.
    Returns the first valid framework name found.
    """
    text_lower = text.lower()
    # Order matters — check most distinctive first
    if "angular"  in text_lower: return "Angular"
    if "react"    in text_lower: return "React"
    if "vue"      in text_lower: return "Vue"
    if "vanilla"  in text_lower: return "HTML"
    if "html"     in text_lower: return "HTML"
    return None