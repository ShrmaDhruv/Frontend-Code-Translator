"""
translation/__init__.py

Building blocks for the translation stage. The graph (app/graph/nodes.py)
runs them as translate → clean_output → validate_output, retrying up to
MAX_TRANSLATION_ATTEMPTS times with the validator errors fed back.

    IR + target → translation_messages → request_translation (Ollama)
        → response_cleaner.clean → validator.validate_translation

Usage:
    from app.translation import get_translator, request_translation, translation_messages

    raw = request_translation(get_translator(), translation_messages(ir, "Vue", source_code))
"""

from app.ir.schema import IR
from app.translation.prompt_builder import build_messages

MAX_NEW_TOKENS = 2048
TEMPERATURE    = 0.1
MAX_TRANSLATION_ATTEMPTS = 3

NO_TRANSLATION_WARNING = "source and target are the same framework - no translation generated"


def _get_client():
    from app.ollama_client import translation_client
    return translation_client()


def get_translator(check: bool = True):
    """Translation model client; with check, raises RuntimeError if Ollama is unreachable."""
    client = _get_client()
    if check and not client.is_available():
        raise RuntimeError(
            "Ollama translation model is not reachable.\n"
            "Check OLLAMA_BASE_URL or run: ollama serve"
        )
    return client


def translation_messages(
    ir: IR,
    target: str,
    source_code: str | None = None,
    errors: list[str] | None = None,
) -> list[dict]:
    """First-attempt prompt, or the retry prompt when the last attempt's errors are given."""
    messages = build_messages(ir, target, source_code=source_code)
    if errors:
        error_str = "\n".join(f"  - {e}" for e in errors)
        messages.append({
            "role": "assistant",
            "content": "[previous translation had issues]",
        })
        messages.append({
            "role": "user",
            "content": (
                f"Your previous translation had these problems:\n{error_str}\n\n"
                "Use the original source code as the source of truth and the IR only as a checklist. "
                f"Please fix them and return only the corrected {target} code with zero comments."
            ),
        })
    return messages


def request_translation(client, messages: list[dict]) -> str:
    return client.chat(messages, max_new_tokens=MAX_NEW_TOKENS, temperature=TEMPERATURE)


__all__ = [
    "get_translator",
    "translation_messages",
    "request_translation",
    "MAX_TRANSLATION_ATTEMPTS",
    "NO_TRANSLATION_WARNING",
]
