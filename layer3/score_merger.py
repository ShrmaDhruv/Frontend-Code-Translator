from dataclasses import dataclass
from layer3.response_parser import ParsedResponse


# ─────────────────────────────────────────────
# RESULT STRUCTURE
# ─────────────────────────────────────────────

@dataclass
class MergedResult:
    detected:      str    # final framework decision — always Layer 3's answer
    confidence:    str    # "high" | "medium" | "low" — from Layer 3
    ask_user:      bool   # True only when Layer 3 itself is uncertain
    reasoning:     str    # Layer 3's explanation
    layer1_top:    str    # Layer 1's top scorer (for debugging/display only)
    layer3_result: str    # Layer 3's detected framework (same as detected)
    source:        str    # always "layer3"

    def summary(self) -> str:
        lines = [
            f"Final Decision : {self.detected}",
            f"Confidence     : {self.confidence}",
            f"Ask User       : {'Yes — Layer 3 was uncertain' if self.ask_user else 'No'}",
            f"Layer 1 Top    : {self.layer1_top} (for reference only)",
            f"Layer 3 Result : {self.layer3_result}",
            f"Source         : {self.source}",
            f"Reasoning      : {self.reasoning}",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────
# MERGER — Layer 3 always wins
# ─────────────────────────────────────────────

def merge_results(
    layer1_scores: dict[str, int],
    layer3_result: ParsedResponse,
) -> MergedResult:
    """
    Layer 3 always prevails.

    Layer 1 scores are passed in only for debugging visibility —
    they do NOT influence the final decision.

    The only case we ask the user is when Layer 3 itself
    returns confidence "low" — meaning even the LLM can't tell.

    Args:
        layer1_scores : Raw score dict from detector.py (for display only)
        layer3_result : ParsedResponse from response_parser.py

    Returns:
        MergedResult where detected is always Layer 3's answer.
    """

    layer1_top = max(layer1_scores, key=lambda fw: layer1_scores[fw])

    # Only ask user when Layer 3 itself is genuinely uncertain
    ask_user = layer3_result.confidence == "low"

    return MergedResult(
        detected      = layer3_result.detected,
        confidence    = layer3_result.confidence,
        ask_user      = ask_user,
        reasoning     = layer3_result.reasoning,
        layer1_top    = layer1_top,
        layer3_result = layer3_result.detected,
        source        = "layer3",
    )