from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from app.ir.schema import IR
from app.detection.rule_detector import DetectionResult, detect


SUPPORTED_FRAMEWORKS = {"React", "Vue", "Angular", "HTML"}
AUTO_DETECT = "Auto Detect"

StopAfter = Literal["detect", "ir", "translate"]

LOW_CONFIDENCE_WARNING = "detection confidence is low"
ASK_USER_ERROR = (
    "Detection confidence is low. Confirm or override the source framework before extraction."
)
SAME_FRAMEWORK_WARNING = "source and target are the same framework - code returned unchanged"


@dataclass
class PipelineDetection:
    framework: str
    confidence: str
    source: str
    ask_user: bool = False
    confidence_scores: dict[str, int] = field(default_factory=dict)
    raw_scores: dict[str, int] = field(default_factory=dict)
    reasoning: str = ""


@dataclass
class PipelineResult:
    ok: bool
    source: str
    target: str
    stage: str
    detection: PipelineDetection
    translated_code: str = ""
    ir: IR | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ir"] = self.ir.to_dict() if self.ir else None
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def normalize_framework(value: str) -> str:
    normalized = value.strip().lower().replace("-", "").replace("_", "").replace(" ", "")
    aliases = {
        "autodetect": AUTO_DETECT,
        "auto": AUTO_DETECT,
        "react": "React",
        "vue": "Vue",
        "vue3": "Vue",
        "angular": "Angular",
        "html": "HTML",
        "vanilla": "HTML",
        "vanillajs": "HTML",
    }

    if normalized not in aliases:
        expected = ", ".join([AUTO_DETECT, *sorted(SUPPORTED_FRAMEWORKS)])
        raise ValueError(f"Unsupported framework '{value}'. Expected one of: {expected}")

    return aliases[normalized]


def confidence_label(percent: int) -> str:
    if percent >= 85:
        return "high"
    if percent >= 65:
        return "medium"
    return "low"


def manual_detection(source: str) -> PipelineDetection:
    return PipelineDetection(
        framework=source,
        confidence="high",
        source="manual",
        ask_user=False,
    )


def rule_detection(layer1: DetectionResult) -> PipelineDetection:
    """Layer 1 result as the final answer (asks the user when it is ambiguous)."""
    return PipelineDetection(
        framework=layer1.detected,
        confidence=confidence_label(layer1.confidence.get(layer1.detected, 0)),
        source="layer1",
        ask_user=layer1.is_ambiguous,
        confidence_scores=layer1.confidence,
        raw_scores=layer1.scores,
        reasoning="Rule-based detector selected the highest scoring framework.",
    )


def llm_detection(code: str, layer1: DetectionResult) -> PipelineDetection:
    """Layer 3 answer for ambiguous Layer 1 results; asks the user if the LLM is unavailable."""
    from app.detection.llm_detector import detect_with_llm

    try:
        layer3 = detect_with_llm(code, layer1.scores)
    except RuntimeError as exc:
        return PipelineDetection(
            framework=layer1.detected,
            confidence=confidence_label(layer1.confidence.get(layer1.detected, 0)),
            source="layer1",
            ask_user=True,
            confidence_scores=layer1.confidence,
            raw_scores=layer1.scores,
            reasoning=(
                "Rule-based detector was ambiguous and LLM detection was unavailable: "
                f"{exc}"
            ),
        )
    return PipelineDetection(
        framework=layer3.detected,
        confidence=layer3.confidence,
        source=layer3.source,
        ask_user=layer3.ask_user,
        confidence_scores=layer1.confidence,
        raw_scores=layer1.scores,
        reasoning=layer3.reasoning,
    )


def detect_source(
    code: str,
    source: str = AUTO_DETECT,
    use_llm_detection: bool = True,
) -> PipelineDetection:
    """
    Detect the source framework.

    Manual source selection skips detection and returns high confidence.
    Auto-detect first uses Layer 1 rules. If Layer 1 is ambiguous and
    use_llm_detection=True, Layer 3 Qwen detection is called and its answer wins.
    """
    source = normalize_framework(source)

    if source != AUTO_DETECT:
        return manual_detection(source)

    layer1: DetectionResult = detect(code)
    if layer1.is_ambiguous and use_llm_detection:
        return llm_detection(code, layer1)
    return rule_detection(layer1)


def run_pipeline(
    code: str,
    target: str,
    source: str = AUTO_DETECT,
    use_llm_detection: bool = True,
    stop_after: StopAfter = "translate",
) -> PipelineResult:
    """
    Run the whole project pipeline (LangGraph, see app/graph/).

    Args:
        code: Raw frontend source code.
        target: Target framework: React, Vue, Angular, or HTML.
        source: Source framework or "Auto Detect".
        use_llm_detection: If True, ambiguous Layer 1 detection calls Layer 3.
        stop_after: Useful for debugging: "detect", "ir", or "translate".

    Returns:
        PipelineResult containing detection metadata, IR, translated code,
        warnings, and errors.
    """
    from app.graph import run_graph  # the graph imports this module

    return run_graph(code, target, source, use_llm_detection, stop_after)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run frontend code translation: detection -> AST/IR -> translation."
    )
    parser.add_argument("input", type=Path, help="Path to the source code file")
    parser.add_argument("--target", required=True, help="Target framework")
    parser.add_argument("--source", default=AUTO_DETECT, help="Source framework or Auto Detect")
    parser.add_argument(
        "--no-llm-detection",
        action="store_true",
        help="Skip Layer 3 LLM detection even when Layer 1 is ambiguous",
    )
    parser.add_argument(
        "--stop-after",
        choices=["detect", "ir", "translate"],
        default="translate",
        help="Stop after a specific pipeline stage",
    )
    parser.add_argument("--show-ir", action="store_true", help="Print extracted IR JSON")
    parser.add_argument("--json", action="store_true", help="Print the full PipelineResult as JSON")
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    code = args.input.read_text(encoding="utf-8")

    try:
        result = run_pipeline(
            code=code,
            source=args.source,
            target=args.target,
            use_llm_detection=not args.no_llm_detection,
            stop_after=args.stop_after,
        )
    except Exception as exc:
        print(f"Pipeline failed: {type(exc).__name__}: {exc}")
        return 1

    if args.json:
        print(result.to_json())
        return 0 if result.ok else 2

    print(f"stage: {result.stage}")
    print(f"ok: {result.ok}")
    print(f"source: {result.source}")
    print(f"target: {result.target}")
    print(f"detection: {result.detection.framework} ({result.detection.confidence})")

    if result.warnings:
        print("warnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    if result.errors:
        print("errors:")
        for error in result.errors:
            print(f"  - {error}")

    if args.show_ir and result.ir:
        print("\nIR")
        print(result.ir.to_json(indent=2))

    if result.translated_code:
        print("\nTRANSLATED CODE")
        print(result.translated_code)

    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
