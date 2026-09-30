"""
Run evaluations against the golden dataset in LangSmith.

Pass 1 runs the real pipeline (Ollama on EC2) plus the cheap checks:
    python -m evals.run_eval pipeline --split easy          # 12-example smoke run
    python -m evals.run_eval pipeline                       # all 36 examples

Pass 2 adds LLM-judge scores to an experiment from pass 1:
    python -m evals.run_eval judge <experiment-name>

Examples run one at a time: a single Ollama GPU is the bottleneck, and
parallel requests would only queue there and risk timeouts.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

from evals.build_dataset import DEFAULT_DATASET_NAME  # noqa: E402
from evals.evaluators import (  # noqa: E402
    behavior_judge,
    detection_correct,
    ir_recall,
    judge_model,
    translation_valid,
)


def pipeline_target(inputs: dict) -> dict:
    from app.pipeline import run_pipeline

    result = run_pipeline(code=inputs["code"], target=inputs["target"])
    return {
        "detected_source": result.detection.framework,
        "detection_confidence": result.detection.confidence,
        "detection_layer": result.detection.source,
        "ok": result.ok,
        "stage": result.stage,
        "ir": result.ir.to_dict() if result.ir else None,
        "translated_code": result.translated_code,
        "warnings": result.warnings,
        "errors": result.errors,
    }


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _print_summary(results) -> None:
    overall: dict[str, list[float]] = defaultdict(list)
    by_pair: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for row in results:
        pair = row["example"].metadata.get("pair", "?")
        for res in row["evaluation_results"]["results"]:
            if res.score is None:
                continue
            overall[res.key].append(float(res.score))
            by_pair[pair][res.key].append(float(res.score))

    print("\nOverall (mean):")
    for key in sorted(overall):
        scores = overall[key]
        print(f"  {key:<24} {sum(scores) / len(scores):.2f}  (n={len(scores)})")

    headline = [k for k in ("translation_valid", "ir_recall", "behavior_pass_rate") if k in overall]
    if headline:
        print("\nBy pair:")
        print("  " + f"{'pair':<18}" + "".join(f"{k:>22}" for k in headline))
        for pair in sorted(by_pair):
            cells = []
            for key in headline:
                scores = by_pair[pair].get(key, [])
                cells.append(f"{sum(scores) / len(scores):>22.2f}" if scores else f"{'-':>22}")
            print(f"  {pair:<18}" + "".join(cells))


def run_pipeline_pass(args) -> None:
    from langsmith import Client

    # Read at call time by pre_parser / ir.builder, so setting them here is enough.
    os.environ["AST_PARSER"] = args.parser
    os.environ["IR_MODE"] = args.ir_mode

    client = Client()
    examples = list(client.list_examples(
        dataset_name=args.dataset,
        splits=[args.split] if args.split else None,
    ))
    examples.sort(key=lambda ex: (ex.metadata.get("case_id", ""), ex.metadata.get("target", "")))
    if args.limit:
        examples = examples[: args.limit]

    print(f"Running pipeline on {len(examples)} example(s) from '{args.dataset}'"
          + (f" (split={args.split})" if args.split else "")
          + f" [parser={args.parser}, ir_mode={args.ir_mode}]")

    results = client.evaluate(
        pipeline_target,
        data=examples,
        evaluators=[detection_correct, ir_recall, translation_valid],
        experiment_prefix=args.prefix,
        description=args.description,
        max_concurrency=1,
        metadata={
            "git_commit": _git_commit(),
            "translator_model": os.getenv("MODEL_NAME"),
            "ir_model": os.getenv("HF_MODEL_NAME"),
            "ast_parser": args.parser,
            "ir_mode": args.ir_mode,
            "split": args.split or "all",
        },
    )

    _print_summary(results)
    print(f"\nExperiment: {results.experiment_name}")
    print(f"Next: python -m evals.run_eval judge {results.experiment_name}")


def run_judge_pass(args) -> None:
    from langsmith.evaluation import evaluate_existing

    print(f"Judging '{args.experiment}' with {judge_model()}")
    results = evaluate_existing(
        args.experiment,
        evaluators=[behavior_judge],
        max_concurrency=1,
        metadata={"judge_model": judge_model()},
    )
    _print_summary(results)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pipeline", help="Pass 1: run the pipeline and cheap evaluators")
    p.add_argument("--dataset", default=DEFAULT_DATASET_NAME)
    p.add_argument("--split", choices=["easy", "medium", "hard"], help="Only run one difficulty split")
    p.add_argument("--limit", type=int, help="Cap the number of examples (for quick checks)")
    p.add_argument("--parser", choices=["tree-sitter", "regex"], default="tree-sitter",
                   help="Pre-parser used for AST extraction")
    p.add_argument("--ir-mode", choices=["facts", "hybrid", "llm"], default="hybrid",
                   help="facts: no LLM; hybrid: LLM only fills gaps; llm: legacy full LLM IR")
    p.add_argument("--prefix", default="baseline", help="Experiment name prefix")
    p.add_argument("--description", default=None)
    p.set_defaults(func=run_pipeline_pass)

    j = sub.add_parser("judge", help="Pass 2: add LLM-judge scores to an existing experiment")
    j.add_argument("experiment", help="Experiment name or ID printed by pass 1")
    j.set_defaults(func=run_judge_pass)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
