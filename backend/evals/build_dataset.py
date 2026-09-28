"""
Build the golden translation dataset and upsert it into LangSmith.

Each case in dataset/cases.json is one source component; it is expanded into
one example per target framework (skipping same-to-same), so 12 components
become 36 examples covering all 12 framework pairs.

Usage (from backend/):
    python -m evals.build_dataset --dry-run
    python -m evals.build_dataset
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from dotenv import load_dotenv

DATASET_DIR = Path(__file__).resolve().parent / "dataset"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_NAME = "frontend-translator-golden"

# Fixed namespace so example IDs are stable across runs, which makes uploads idempotent.
_ID_NAMESPACE = uuid.UUID("6f1c2a7e-3b0d-4c8e-9a51-2d7f0e4b8c13")


def build_examples() -> list[dict]:
    spec = json.loads((DATASET_DIR / "cases.json").read_text(encoding="utf-8"))
    concepts = spec["concepts"]
    examples = []

    for case in spec["cases"]:
        concept = concepts[case["concept"]]
        code = (DATASET_DIR / case["file"]).read_text(encoding="utf-8")

        for target in spec["targets"]:
            if target == case["source"]:
                continue

            key = f"{case['id']}->{target}"
            examples.append({
                "id": str(uuid.uuid5(_ID_NAMESPACE, key)),
                "inputs": {"code": code, "target": target},
                "outputs": {
                    "expected_source": case["source"],
                    "expected_ir": case["expected_ir"],
                    "behaviors": concept["behaviors"],
                    "judge_notes": spec["judge_notes"],
                },
                "metadata": {
                    "case_id": case["id"],
                    "source": case["source"],
                    "target": target,
                    "pair": f"{case['source']}->{target}",
                    "concept": case["concept"],
                    "difficulty": concept["difficulty"],
                    "source_file": case["file"],
                    "dataset_version": spec["version"],
                },
                "split": concept["difficulty"],
            })

    return examples


def upload(examples: list[dict], dataset_name: str) -> None:
    from langsmith import Client

    client = Client()

    if client.has_dataset(dataset_name=dataset_name):
        dataset = client.read_dataset(dataset_name=dataset_name)
    else:
        dataset = client.create_dataset(
            dataset_name,
            description=(
                "Golden set for the frontend code translator: 12 source components "
                "(React/Vue/Angular/HTML x counter/todo_list/session_timer) expanded "
                "across every non-identical target framework."
            ),
        )

    existing_ids = {str(ex.id) for ex in client.list_examples(dataset_id=dataset.id)}
    to_create = [ex for ex in examples if ex["id"] not in existing_ids]
    to_update = [ex for ex in examples if ex["id"] in existing_ids]

    if to_create:
        client.create_examples(dataset_id=dataset.id, examples=to_create)
    if to_update:
        client.update_examples(dataset_id=dataset.id, updates=to_update)

    stale = existing_ids - {ex["id"] for ex in examples}
    print(f"Dataset '{dataset_name}' ({dataset.id})")
    print(f"  created: {len(to_create)}  updated: {len(to_update)}")
    if stale:
        print(f"  note: {len(stale)} example(s) in LangSmith are no longer in cases.json (left untouched)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", default=DEFAULT_DATASET_NAME, help="LangSmith dataset name")
    parser.add_argument("--dry-run", action="store_true", help="Build and summarize without uploading")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    examples = build_examples()

    pairs: dict[str, int] = {}
    for ex in examples:
        pairs[ex["metadata"]["pair"]] = pairs.get(ex["metadata"]["pair"], 0) + 1

    print(f"Built {len(examples)} examples across {len(pairs)} framework pairs:")
    for pair, count in sorted(pairs.items()):
        print(f"  {pair:<18} {count}")

    if args.dry_run:
        return 0

    upload(examples, args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
