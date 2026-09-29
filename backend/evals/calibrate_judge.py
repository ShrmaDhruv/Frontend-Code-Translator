"""
Measure the LLM judge against hand-labelled translations (judge_calibration/).

Treats the judge as a classifier over individual behavior verdicts:
    agreement      share of verdicts matching the label
    bug recall     share of real bugs (label = fail) the judge caught
    false fails    correct behavior the judge rejected (too strict)
    false passes   buggy behavior the judge accepted (too lenient)

Usage (from backend/):
    python -m evals.calibrate_judge                  # current judge prompt
    python -m evals.calibrate_judge --prompt v1      # original prompt, for comparison
    python -m evals.calibrate_judge --runs 3         # repeat to see judge variance
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

EVALS_DIR = Path(__file__).resolve().parent
load_dotenv(EVALS_DIR.parents[1] / ".env")

from evals.evaluators import judge_model, judge_verdicts  # noqa: E402

# The prompt used for baseline-16d2e979 and treesitter-hybrid-e2d42011.
JUDGE_PROMPT_V1 = """You are a strict reviewer of frontend code translations.
You receive a source component, its translation into another framework, and a
list of required behaviors. For each behavior, decide whether the TRANSLATED
code implements it exactly as described. Judge only the translated code's
actual logic; do not assume behavior that is not in the code. Idiomatic
differences between frameworks are fine as long as the behavior matches.

Respond with JSON only, in this shape:
{"verdicts": [{"behavior": 1, "pass": true, "reason": "short reason"}, ...]}
Include exactly one verdict per behavior, numbered as given."""


def load_cases() -> tuple[list[dict], dict]:
    calibration = json.loads((EVALS_DIR / "judge_calibration" / "cases.json").read_text(encoding="utf-8"))
    dataset = json.loads((EVALS_DIR / "dataset" / "cases.json").read_text(encoding="utf-8"))
    return calibration["cases"], dataset


def run(prompt: str | None, runs: int) -> dict:
    cases, dataset = load_cases()
    totals = {"verdicts": 0, "agree": 0, "bugs": 0, "caught": 0, "false_fail": 0, "false_pass": 0, "unusable": 0}

    for case in cases:
        behaviors = dataset["concepts"][case["concept"]]["behaviors"]
        assert len(behaviors) == len(case["expected"]), f"{case['id']}: label count mismatch"
        source = (EVALS_DIR / "dataset" / case["source_file"]).read_text(encoding="utf-8")
        translated = (EVALS_DIR / "judge_calibration" / case["translation"]).read_text(encoding="utf-8")
        reference = {
            "expected_source": case["source"],
            "behaviors": behaviors,
            "judge_notes": dataset["judge_notes"],
        }

        for attempt in range(runs):
            verdicts, raw = judge_verdicts(source, case["target"], translated, reference, system_prompt=prompt)
            tag = f"{case['id']}" + (f" (run {attempt + 1})" if runs > 1 else "")
            if verdicts is None:
                totals["unusable"] += 1
                print(f"  ?  {tag}: unusable judge output: {raw[:120]!r}")
                continue

            mistakes = []
            for i, (verdict, expected) in enumerate(zip(verdicts, case["expected"]), start=1):
                totals["verdicts"] += 1
                totals["agree"] += verdict["pass"] == expected
                if not expected:
                    totals["bugs"] += 1
                    totals["caught"] += not verdict["pass"]
                if expected and not verdict["pass"]:
                    totals["false_fail"] += 1
                    mistakes.append(f"      [{i}] FALSE FAIL: {verdict['reason'][:220]}")
                if not expected and verdict["pass"]:
                    totals["false_pass"] += 1
                    mistakes.append(f"      [{i}] FALSE PASS (missed: {case['note']}): {verdict['reason'][:220]}")

            print(f"  {'ok' if not mistakes else 'XX'} {tag}")
            for line in mistakes:
                print(line)

    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt", choices=["current", "v1"], default="current")
    parser.add_argument("--runs", type=int, default=1, help="Judge each case this many times")
    args = parser.parse_args()

    prompt = JUDGE_PROMPT_V1 if args.prompt == "v1" else None
    print(f"Calibrating judge {judge_model()} with prompt '{args.prompt}' ({args.runs} run(s) per case)\n")
    t = run(prompt, args.runs)

    n = t["verdicts"] or 1
    print(f"\nverdicts        {t['verdicts']}  (unusable responses: {t['unusable']})")
    print(f"agreement       {t['agree'] / n:.2%}")
    print(f"bug recall      {t['caught']}/{t['bugs']}" + (f"  ({t['caught'] / t['bugs']:.0%})" if t["bugs"] else ""))
    print(f"false fails     {t['false_fail']}   (correct behavior rejected: judge too strict)")
    print(f"false passes    {t['false_pass']}   (bug accepted: judge too lenient)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
