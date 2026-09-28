"""
test_phi_layer.py

Focused test suite for the Phi3 Ollama translation client layer.

Run offline checks:
    python test_phi_layer.py

Run with local Ollama/Phi3:
    python test_phi_layer.py --live
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


def run(label, cases, test_fn):
    print(f"\n{label}")
    print("-" * 50)
    passed = 0
    for case in cases:
        ok, msg = test_fn(case)
        print(f"  {'PASS' if ok else 'FAIL'} - {msg}")
        if ok:
            passed += 1
    print(f"  {passed}/{len(cases)} passed")
    return passed == len(cases)


def test_package_exports():
    from app.phi_client import MODEL_NAME, OLLAMA_URL, TIMEOUT_SECS, Phi3Client

    cases = [
        ("Phi3Client is exported", Phi3Client.__name__ == "Phi3Client"),
        ("MODEL_NAME is phi3:3.8b", MODEL_NAME == "phi3:3.8b"),
        ("OLLAMA_URL points to chat endpoint", OLLAMA_URL.endswith("/api/chat")),
        ("TIMEOUT_SECS allows longer generation", TIMEOUT_SECS >= 120),
    ]

    def test_fn(case):
        label, ok = case
        return bool(ok), label

    return run("PHI PACKAGE - exports", cases, test_fn)


def test_singleton_behavior():
    from app.phi_client import Phi3Client

    first = Phi3Client()
    second = Phi3Client()

    cases = [
        ("Phi3Client reuses the same instance", first is second),
        ("Client starts unloaded", hasattr(first, "_loaded")),
    ]

    def test_fn(case):
        label, ok = case
        return bool(ok), label

    return run("PHI CLIENT - singleton", cases, test_fn)


def test_live():
    from app.phi_client import Phi3Client

    client = Phi3Client()

    if not client.is_available():
        print("\n  Skipped - Ollama unreachable. Run: ollama serve")
        return False

    messages = [
        {
            "role": "system",
            "content": (
                "You are a code translation test model. "
                "Return only code, no markdown fences."
            ),
        },
        {
            "role": "user",
            "content": (
                "Translate this React component to Vue 3 script setup:\n\n"
                "const Counter = () => {\n"
                "  const [count, setCount] = React.useState(0)\n"
                "  return <button onClick={() => setCount(count + 1)}>{count}</button>\n"
                "}\n"
            ),
        },
    ]

    try:
        response = client.chat(messages, max_new_tokens=512, temperature=0.1)
    except Exception as e:
        print(f"\n  ERROR - Phi3 request failed | {e}")
        return False

    expected_markers = ["<template", "script", "ref"]
    missing = [m for m in expected_markers if m.lower() not in response.lower()]
    ok = not missing

    print("\nPHI LIVE - translation smoke test")
    print("-" * 50)
    print(f"  {'PASS' if ok else 'FAIL'} - React counter to Vue smoke test")
    if missing:
        print(f"    missing markers: {missing}")
    print("\n  Response preview:")
    print("  " + response[:500].replace("\n", "\n  "))

    return ok


if __name__ == "__main__":
    live = "--live" in sys.argv

    print("\n" + "=" * 50)
    print("  PHI LAYER - TEST SUITE")
    print("=" * 50)

    p1 = test_package_exports()
    p2 = test_singleton_behavior()

    p3 = True
    if live:
        p3 = test_live()
    else:
        print("\n  Live skipped. Run: python test_phi_layer.py --live")

    print("\n" + "=" * 50)
    print(f"  Unit : {'ALL PASSED' if p1 and p2 else 'SOME FAILED'}")
    if live:
        print(f"  Live : {'PASSED' if p3 else 'FAILED'}")
    print("=" * 50 + "\n")
