"""
test_ir_translation_live.py

End-to-end test for:
    source code -> AST pre-parser -> IR builder -> translation model

This script prints the full IR and the full translated code output.

Run:
    python tests/test_ir_translation_live.py
"""

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

from app.pipeline import run_pipeline


SOURCE_FRAMEWORK = "React"
TARGET_FRAMEWORK = "Vue"


SOURCE_CODE = """
import React, { useState, useEffect, useMemo } from 'react'

const Dashboard = ({ userId, onLogout }) => {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const itemCount = useMemo(() => data ? data.length : 0, [data])

  useEffect(() => {
    setLoading(true)
    fetch('/api/user/' + userId)
      .then(r => r.json())
      .then(d => {
        setData(d)
        setLoading(false)
      })
      .catch(e => {
        setError(e.message)
        setLoading(false)
      })
  }, [userId])

  const handleRefresh = () => {
    setData(null)
    setLoading(true)
  }

  return (
    <div className="dashboard">
      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
      {data && <p>{itemCount} items</p>}
      <button onClick={handleRefresh}>Refresh</button>
      <button onClick={onLogout}>Logout</button>
    </div>
  )
}

export default Dashboard
"""


def main():
    print("\n" + "=" * 70)
    print("  IR + TRANSLATION FULL PIPELINE")
    print("=" * 70)
    print(f"  Source: {SOURCE_FRAMEWORK}")
    print(f"  Target: {TARGET_FRAMEWORK}")

    result = run_pipeline(SOURCE_CODE, target=TARGET_FRAMEWORK, source=SOURCE_FRAMEWORK)

    print("\nIR")
    print("-" * 70)
    print(result.ir.to_json(indent=2) if result.ir else None)

    print(f"ok: {result.ok}")
    if result.warnings:
        print(f"warnings: {result.warnings}")
    if result.errors:
        print(f"errors: {result.errors}")

    print("\nFULL TRANSLATED CODE")
    print("=" * 70)
    print(result.translated_code)
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
