"""
detector.py — Framework detection engine.

Imports rule sets from individual framework files and runs
them against input code to produce a DetectionResult.

Usage:
    from detector import detect

    result = detect(code)
    print(result.detected)       # "React"
    print(result.confidence)     # {"React": 94, "Vue": 4, ...}
    print(result.is_ambiguous)   # False
    print(result.summary())      # Full audit trail
"""

from dataclasses import dataclass
from app.rules import REACT_RULES, VUE_RULES, ANGULAR_RULES, HTML_RULES
from app.rules.base import Rule, FiredRule


# ─────────────────────────────────────────────
# RESULT DATA STRUCTURE
# ─────────────────────────────────────────────

@dataclass
class DetectionResult:
    detected: str                    # winning framework name
    confidence: dict[str, int]       # { "React": 94, "Vue": 4, ... }
    scores: dict[str, int]           # raw accumulated scores
    fired_rules: list[FiredRule]     # full audit trail of matched rules
    is_ambiguous: bool               # True when top confidence < 75%

    def summary(self) -> str:
        """Pretty-print the detection result and every rule that fired."""
        lines = [
            f"Detected  : {self.detected}",
            f"Ambiguous : {self.is_ambiguous}",
            f"Confidence: " + " | ".join(
                f"{fw}: {pct}%"
                for fw, pct in sorted(self.confidence.items(), key=lambda x: -x[1])
            ),
            "",
            "Fired Rules (sorted by contribution):",
        ]
        for r in sorted(self.fired_rules, key=lambda x: -abs(x.contribution)):
            sign = "+" if r.contribution >= 0 else ""
            lines.append(
                f"  [{r.framework:8s}] {sign}{r.contribution:4d}  "
                f"{r.id}  ({r.match_count} match{'es' if r.match_count > 1 else ''})"
            )
        return "\n".join(lines)


# ─────────────────────────────────────────────
# FRAMEWORK → RULES REGISTRY
# (add new frameworks here — no other changes needed)
# ─────────────────────────────────────────────

FRAMEWORK_RULES: dict[str, list[Rule]] = {
    "React":   REACT_RULES,
    "Vue":     VUE_RULES,
    "Angular": ANGULAR_RULES,
    "HTML":    HTML_RULES,
}

FRAMEWORKS = list(FRAMEWORK_RULES.keys())


# ─────────────────────────────────────────────
# DETECTION ENGINE
# ─────────────────────────────────────────────

def detect(code: str, ambiguity_threshold: int = 75) -> DetectionResult:
    """
    Run all framework rules against the input code string.

    Args:
        code                : Raw source code to analyse.
        ambiguity_threshold : Confidence % below which result is flagged
                              as ambiguous (default 75).

    Returns:
        DetectionResult with detected framework, confidence scores,
        raw scores, fired rules, and ambiguity flag.
    """
    scores: dict[str, int] = {fw: 0 for fw in FRAMEWORKS}
    fired_rules: list[FiredRule] = []

    for framework, rules in FRAMEWORK_RULES.items():
        for rule in rules:
            matches = rule.pattern.findall(code)
            if matches:
                match_count = len(matches)
                contribution = rule.weight * match_count
                scores[framework] += contribution
                fired_rules.append(FiredRule(
                    id=rule.id,
                    framework=framework,
                    weight=rule.weight,
                    match_count=match_count,
                    contribution=contribution,
                    reason=rule.reason,
                ))

    # Normalize positive scores to confidence percentages
    total = sum(max(s, 0) for s in scores.values())
    confidence: dict[str, int] = {
        fw: round((max(score, 0) / total) * 100) if total > 0 else 0
        for fw, score in scores.items()
    }

    winner = max(scores, key=lambda fw: scores[fw])

    return DetectionResult(
        detected=winner,
        confidence=confidence,
        scores=scores,
        fired_rules=fired_rules,
        is_ambiguous=confidence[winner] < ambiguity_threshold,
    )
