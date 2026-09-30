"""
translation/__init__.py

Public interface for the translation pipeline.

Translates frontend code from one framework to another using a
three-stage pipeline:

  Stage 1 — AST extraction
      raw code → pre_parser → ir.builder → validated IR

  Stage 2 — Translation
      IR + target framework → prompt_builder → translation model (Ollama) → raw response

  Stage 3 — Cleaning and validation
      raw response → response_cleaner → validator
      if critical errors → one retry with error context

The source framework is provided by the caller (already determined
by the detection pipeline). Translation never re-detects.

Usage:
    from app.translation import translate

    result = translate(code, source="React", target="Vue")
    print(result.code)
    print(result.warnings)
    print(result.ok)
"""

from dataclasses import dataclass, field

from app.ir              import extract_ir
from app.ir.schema    import IR
from app.translation.prompt_builder      import build_messages
from app.translation.response_cleaner    import clean
from app.translation.validator import validate_translation

MAX_NEW_TOKENS = 2048
TEMPERATURE    = 0.1
MAX_TRANSLATION_ATTEMPTS = 3

SUPPORTED = {"React", "Vue", "Angular", "HTML"}


@dataclass
class TranslationResult:
    ok:        bool
    code:      str
    source:    str
    target:    str
    warnings:  list[str] = field(default_factory=list)
    errors:    list[str] = field(default_factory=list)
    ir:        IR | None = None


def _get_client():
    from app.ollama_client import translation_client
    return translation_client()


def _run_translation(
    ir: IR,
    target: str,
    client,
    source_code: str | None = None,
) -> str:
    messages = build_messages(ir, target, source_code=source_code)
    raw      = client.chat(messages, max_new_tokens=MAX_NEW_TOKENS, temperature=TEMPERATURE)
    return clean(raw, target)


def _retry_prompt(
    ir: IR,
    target: str,
    errors: list[str],
    client,
    source_code: str | None = None,
) -> str:
    from app.translation.prompt_builder import build_messages as bm
    messages = bm(ir, target, source_code=source_code)
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
    raw = client.chat(messages, max_new_tokens=MAX_NEW_TOKENS, temperature=TEMPERATURE)
    return clean(raw, target)


def translate_ir(
    ir: IR,
    target: str,
    source_code: str | None = None,
) -> TranslationResult:
    """
    Translate an already-built IR into the target framework using the translation model.

    Use this when AST/IR extraction has already happened and you want
    the full generated code output from the translation model directly.
    """
    if target not in SUPPORTED:
        raise ValueError(
            f"Unsupported target framework: '{target}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED))}"
        )

    if ir.framework == target:
        return TranslationResult(
            ok=True,
            code="",
            source=ir.framework,
            target=target,
            warnings=["source and target are the same framework - no translation generated"],
            ir=ir,
        )

    client = _get_client()
    if not client.is_available():
        raise RuntimeError(
            "Ollama translation model is not reachable.\n"
            "Check OLLAMA_BASE_URL or run: ollama serve"
        )

    translated = _run_translation(ir, target, client, source_code=source_code)
    validation = validate_translation(translated, ir, target)
    attempts = 1

    while not validation.is_valid and attempts < MAX_TRANSLATION_ATTEMPTS:
        translated = _retry_prompt(ir, target, validation.errors, client, source_code=source_code)
        validation = validate_translation(translated, ir, target)
        attempts += 1

    return TranslationResult(
        ok       = validation.is_valid,
        code     = translated,
        source   = ir.framework,
        target   = target,
        warnings = validation.warnings,
        errors   = validation.errors if not validation.is_valid else [],
        ir       = ir,
    )


def translate(
    code:   str,
    source: str,
    target: str,
) -> TranslationResult:
    """
    Translate frontend code from source framework to target framework.

    Args:
        code   : Raw source code string
        source : Source framework — one of React | Vue | Angular | HTML
        target : Target framework — one of React | Vue | Angular | HTML

    Returns:
        TranslationResult with translated code, warnings, and ok flag

    Raises:
        ValueError   if source or target framework is not supported
        RuntimeError if Ollama is unreachable
    """
    if source not in SUPPORTED:
        raise ValueError(
            f"Unsupported source framework: '{source}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED))}"
        )
    if target not in SUPPORTED:
        raise ValueError(
            f"Unsupported target framework: '{target}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED))}"
        )
    if source == target:
        return TranslationResult(
            ok=True, code=code, source=source, target=target,
            warnings=["source and target are the same framework — code returned unchanged"],
        )

    ir = extract_ir(code, source)
    return translate_ir(ir, target, source_code=code)


__all__ = [
    "translate",
    "translate_ir",
    "TranslationResult",
]
