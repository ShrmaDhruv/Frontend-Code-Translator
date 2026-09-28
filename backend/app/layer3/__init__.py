"""
layer3/__init__.py

Layer 3 LLM detection using Qwen2.5-Coder-3B-Instruct via Ollama.

Flow:
  - Layer 1 is ambiguous  →  call Qwen2.5-Coder-3B-Instruct
  - Layer 3 answer always prevails
  - Only ask user when Layer 3 itself says confidence "low"

Usage:
    from app.layer3 import detect_with_llm

    merged = detect_with_llm(code, layer1_scores)
    print(merged.detected)     # "Vue"
    print(merged.confidence)   # "high"
    print(merged.ask_user)     # False
    print(merged.summary())
"""

from app.layer3.prompt_builder  import build_messages
from app.layer3.response_parser import parse_response
from app.layer3.cache           import DetectionCache
from app.layer3.score_merger    import merge_results, MergedResult

_cache  = DetectionCache()
_client = None


def _get_client():
    """Lazy-load OLClient so requests import only happens when actually needed."""
    global _client
    if _client is None:
        from app.ollama_client import OLClient
        _client = OLClient()
    return _client


def detect_with_llm(
    code: str,
    layer1_scores: dict[str, int],
) -> MergedResult:
    """
    Full Layer 3 detection pipeline using Qwen2.5-Coder-3B-Instruct via Ollama.

    1. Check cache        → return instantly if seen before
    2. Build prompt
    3. Call Qwen model    → hits localhost:11434 via Ollama
    4. Parse JSON response
    5. Cache result
    6. Return MergedResult — Layer 3 answer is final

    Args:
        code          : Ambiguous source code string
        layer1_scores : Raw scores from Layer 1 (for display only)

    Returns:
        MergedResult where detected is always Layer 3's answer.
        ask_user is True only when Layer 3 confidence is "low".
    """

    cached = _cache.get(code)
    if cached:
        return merge_results(layer1_scores, cached)

    client = _get_client()
    if not client.is_available():
        raise RuntimeError(
            "Ollama is not reachable at localhost:11434.\n"
            "Run: ollama serve"
        )

    messages = build_messages(code)

    raw_response = client.chat(
        messages,
        max_new_tokens = 150,
        temperature    = 0.1,
    )

    parsed = parse_response(raw_response)

    _cache.set(code, parsed)

    return merge_results(layer1_scores, parsed)


__all__ = [
    "detect_with_llm",
    "MergedResult",
]
