"""
Input guardrails (Layer 2): run on user code before it reaches any prompt.

    sanitize_input(code)  → (clean code, warnings)   pure transformation, runs before the graph
                                                     so traces never see the raw input
    inspect_input(code)   → InputVerdict             policy checks, runs in the check_input node

sanitize_input:
  - removes invisible / control characters (Trojan Source bidi overrides,
    zero-width characters, Unicode "tag" characters used for ASCII smuggling)
  - removes chat-template special tokens (<|im_start|>, [INST], ...) that could
    fake a new system/user turn inside the prompt
  - masks credentials (cloud keys, API tokens, JWTs, private keys) so they are
    not sent to the model server or tracing

inspect_input:
  - size limits (characters, lines)
  - "does this look like code?" gate, so the app can't be used as a free chatbot
  - prompt-injection heuristics: strong patterns block, weak ones only warn
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

MAX_CODE_CHARS = int(os.getenv("MAX_CODE_CHARS", "20000"))
MAX_CODE_LINES = int(os.getenv("MAX_CODE_LINES", "1000"))

# "block" (default): high-risk injection text rejects the request. "warn": only warn.
INJECTION_POLICY = os.getenv("INJECTION_POLICY", "block")
INJECTION_BLOCK_SCORE = 3

MIN_CODE_LINE_RATIO = 0.4


# ── Sanitising ────────────────────────────────────────────────────────────────

_INVISIBLE = re.compile(
    "["
    "\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f"   # C0 controls except \t \n \r
    "​"                                          # zero-width space
    "‪-‮⁦-⁩"                      # bidi embeddings / overrides / isolates
    "⁠-⁤"                                   # word joiner, invisible operators
    "﻿"                                          # BOM inside text
    "\U000e0000-\U000e007f"                           # Unicode tag characters
    "]"
)

_SPECIAL_TOKENS = re.compile(
    r"<\|[\w\-]{1,40}\|>"                             # Qwen / ChatML / Llama 3: <|im_start|>, <|eot_id|>
    r"|</?(?:start_of_turn|end_of_turn)>"             # Gemma
    r"|\[/?INST\]|<</?SYS>>",                         # Llama 2 / Mistral
    re.IGNORECASE,
)

_SECRET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("private key", re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("Stripe secret key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
]

# apiKey: "…", const password = '…', accessToken="…"  → mask only the quoted value.
_SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    (\b\w*(?:api[_-]?key|secret|token|passw(?:or)?d)\w*["']?\s*[:=]\s*)
    (["'`])([^"'`\s]{12,})\2
    """
)

REDACTED = "REDACTED_SECRET"


def _mask_secrets(code: str) -> tuple[str, list[str]]:
    found: list[str] = []
    for kind, pattern in _SECRET_PATTERNS:
        code, count = pattern.subn(REDACTED, code)
        if count:
            found.append(kind)

    def mask_value(match: re.Match) -> str:
        if match.group(3) == REDACTED:
            return match.group(0)
        found.append("credential-like value")
        quote = match.group(2)
        return f"{match.group(1)}{quote}{REDACTED}{quote}"

    code = _SECRET_ASSIGNMENT.sub(mask_value, code)
    return code, list(dict.fromkeys(found))


def sanitize_input(code: str) -> tuple[str, list[str]]:
    """Remove hidden characters and chat tokens, mask secrets. Returns (code, warnings)."""
    warnings: list[str] = []

    code, removed = _INVISIBLE.subn("", code)
    if removed:
        warnings.append(
            f"removed {removed} invisible or control character(s) "
            "(bidi overrides, zero-width or tag characters) from the input"
        )

    code, removed = _SPECIAL_TOKENS.subn("", code)
    if removed:
        warnings.append(f"removed {removed} chat-template token(s) from the input")

    code, kinds = _mask_secrets(code)
    if kinds:
        warnings.append(
            f"masked secret(s) in the input ({', '.join(kinds)}) as {REDACTED}; "
            "put your real values back into the translated code"
        )

    return code, warnings


# ── Inspection ────────────────────────────────────────────────────────────────

_W = r"[\s\W_]{1,6}"  # separator between words: spaces, punctuation, comment markers

# (weight, description, pattern). Weight >= INJECTION_BLOCK_SCORE on its own blocks.
_INJECTION_PATTERNS: list[tuple[int, str, re.Pattern]] = [
    (3, "instruction override", re.compile(
        rf"\b(?:ignore|disregard|forget|override|bypass|skip)(?:{_W}\w+){{0,3}}?{_W}"
        rf"(?:previous|prior|above|earlier|preceding|system|all|your|these|the){_W}"
        rf"(?:\w+{_W})?(?:instructions?|rules|prompts?|directions|guidelines|constraints)\b",
        re.IGNORECASE)),
    (3, "prompt extraction", re.compile(
        rf"\b(?:reveal|print|output|show|repeat|leak|dump|display){_W}(?:me{_W})?(?:your|the){_W}"
        rf"(?:system{_W}|initial{_W}|hidden{_W})?(?:prompt|instructions)\b",
        re.IGNORECASE)),
    (3, "fake instruction block", re.compile(
        rf"\b(?:new|updated|real|actual|additional){_W}(?:system{_W})?instructions?\s*:",
        re.IGNORECASE)),
    (2, "instruction addressed to the model", re.compile(
        rf"\b(?:AI|LLM|assistant|model|translator|chatbot)\s*[:,]{_W}?(?:please{_W})?"
        rf"(?:add|insert|include|inject|append|embed|send|also)\b",
        re.IGNORECASE)),
    (2, "data exfiltration request", re.compile(
        r"\b(?:send|post|upload|exfiltrate|forward|leak)\b[^\n]{0,60}"
        r"\b(?:cookies?|localStorage|sessionStorage|tokens?|credentials?|passwords?)\b[^\n]{0,60}"
        r"(?:\bto\b|https?://)",
        re.IGNORECASE)),
    (1, "cookie next to a URL", re.compile(
        r"https?://[^\n]{0,80}document\.cookie|document\.cookie[^\n]{0,80}https?://",
        re.IGNORECASE)),
    (1, "role reassignment", re.compile(
        rf"\b(?:you{_W}are{_W}now|from{_W}now{_W}on{_W}you|act{_W}as{_W}(?:a|an){_W}|"
        rf"pretend{_W}(?:to{_W}be|you{_W}are))",
        re.IGNORECASE)),
    (1, "role tag", re.compile(r"</?(?:system|assistant|instructions?)>", re.IGNORECASE)),
]

_CODE_LINE = re.compile(
    r"[{};=<>]|=>|\w\(|\)\s*[{;]"
    r"|^\s*(?:import|export|const|let|var|function|return|class|if|for|while|@\w+)\b",
)


@dataclass
class InputVerdict:
    blocked: str | None = None             # reason shown to the user when the input is rejected
    warnings: list[str] = field(default_factory=list)
    injection_score: int = 0
    injection_signals: list[str] = field(default_factory=list)


def injection_signals(code: str) -> tuple[int, list[str]]:
    score, signals = 0, []
    for weight, name, pattern in _INJECTION_PATTERNS:
        if pattern.search(code):
            score += weight
            signals.append(name)
    return score, signals


def code_line_ratio(code: str) -> float:
    lines = [line for line in code.splitlines() if line.strip()]
    if not lines:
        return 0.0
    return sum(1 for line in lines if _CODE_LINE.search(line)) / len(lines)


def inspect_input(code: str) -> InputVerdict:
    verdict = InputVerdict()

    if not code.strip():
        verdict.blocked = "input is empty"
        return verdict
    if len(code) > MAX_CODE_CHARS:
        verdict.blocked = f"input is too long ({len(code)} characters, limit {MAX_CODE_CHARS})"
        return verdict
    line_count = code.count("\n") + 1
    if line_count > MAX_CODE_LINES:
        verdict.blocked = f"input is too long ({line_count} lines, limit {MAX_CODE_LINES})"
        return verdict

    if code_line_ratio(code) < MIN_CODE_LINE_RATIO:
        verdict.blocked = (
            "input does not look like frontend source code; "
            "paste a React, Vue, Angular, or HTML component"
        )
        return verdict

    score, signals = injection_signals(code)
    verdict.injection_score, verdict.injection_signals = score, signals
    if signals:
        detail = ", ".join(signals)
        if score >= INJECTION_BLOCK_SCORE and INJECTION_POLICY == "block":
            verdict.blocked = (
                f"input contains text that looks like instructions to the AI ({detail}); "
                "remove it and try again"
            )
        else:
            verdict.warnings.append(
                f"input contains text that looks like instructions to the AI ({detail}); "
                "it was treated as code, not as instructions"
            )
    return verdict
