"""
Output guard (Layer 4): a capability diff between the source and the translation.

A translation may only do what the source already does. If the output can make
network requests, run dynamic code, read cookies/storage, navigate away, inject
raw HTML, embed external content, contact a new host, or import a new package
and the source cannot, the model either followed an injected instruction or
invented a feature. Both are reported as violations: the graph feeds them back
for a retry and withholds the code if they survive the last attempt.

Both sides are compared on two views built with tree-sitter:

    no_comments   comments removed. Used for markup-level checks, URLs, imports.
    logic         comments removed and string / text contents blanked. Used for
                  JavaScript API checks, so a payload that only *mentions*
                  fetch(...) in a comment or string grants no capability on the
                  source side and raises no alarm on the output side.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field

from app.ir.treesitter.common import parse, walk

log = logging.getLogger(__name__)


@dataclass
class OutputReport:
    violations: list[str] = field(default_factory=list)   # fail validation, withheld if they persist
    warnings: list[str] = field(default_factory=list)


# ── Views ─────────────────────────────────────────────────────────────────────

Range = tuple[int, int]


def _js_ranges(code: bytes, grammar: str, offset: int = 0) -> tuple[list[Range], list[Range]]:
    """(comment ranges, string/text ranges) of a script, shifted by offset."""
    comments, texts = [], []
    root = parse(code.decode("utf-8", errors="replace"), grammar)
    for node in walk(root, {"comment", "string_fragment", "jsx_text"}):
        span = (node.start_byte + offset, node.end_byte + offset)
        (comments if node.type == "comment" else texts).append(span)
    return comments, texts


def _html_ranges(code: bytes) -> tuple[list[Range], list[Range]]:
    """HTML document or Vue SFC: markup comments and text, plus each <script> parsed as JS/TS."""
    comments, texts = [], []
    root = parse(code.decode("utf-8", errors="replace"), "html")
    for node in walk(root, {"comment", "text", "script_element"}):
        if node.type == "comment":
            comments.append((node.start_byte, node.end_byte))
        elif node.type == "text":
            texts.append((node.start_byte, node.end_byte))
        else:
            raw = next((child for child in node.named_children if child.type == "raw_text"), None)
            if raw is None:
                continue
            start_tag = code[node.start_byte:raw.start_byte]
            grammar = "typescript" if re.search(rb"lang\s*=\s*[\"']ts", start_tag) else "javascript"
            script_comments, script_texts = _js_ranges(code[raw.start_byte:raw.end_byte], grammar, raw.start_byte)
            comments += script_comments
            texts += script_texts
    return comments, texts


def _blank(code: bytes, ranges: list[Range]) -> str:
    data = bytearray(code)
    for start, end in ranges:
        for index in range(start, min(end, len(data))):
            if data[index] not in (0x0A, 0x0D):
                data[index] = 0x20
    return data.decode("utf-8", errors="replace")


def views(code: str, framework: str) -> tuple[str, str]:
    """(no_comments, logic) views of the code. Falls back to the raw text if parsing fails."""
    raw = code.encode("utf-8")
    try:
        if framework == "React":
            comments, texts = _js_ranges(raw, "tsx")
        elif framework == "Angular":
            comments, texts = _js_ranges(raw, "typescript")
        else:
            comments, texts = _html_ranges(raw)
    except Exception as exc:
        log.warning("output guard could not parse %s code: %s", framework, exc)
        return code, code
    return _blank(raw, comments), _blank(raw, comments + texts)


# ── Capabilities ──────────────────────────────────────────────────────────────

# JavaScript APIs, matched on the logic view.
_LOGIC_CAPABILITIES: dict[str, re.Pattern] = {
    "a network request": re.compile(
        r"\bfetch\s*\(|\bXMLHttpRequest\b|\bnew\s+WebSocket\b|\bnew\s+EventSource\b|\bsendBeacon\s*\("
        r"|\baxios\b|\$\.(?:ajax|get|post|getJSON)\s*\(|\bHttpClient\b"
        r"|\.http\.(?:get|post|put|delete|patch)\s*\(|\bnew\s+Image\s*\("),
    "dynamic code execution": re.compile(
        r"\beval\s*\(|\bnew\s+Function\s*\(|\bFunction\s*\(\s*[\"'`]"
        r"|\bset(?:Timeout|Interval)\s*\(\s*[\"'`]|\bdocument\.write(?:ln)?\s*\(|\bimportScripts\s*\("),
    "cookie or browser storage access": re.compile(
        r"\bdocument\.cookie\b|\b(?:localStorage|sessionStorage|indexedDB)\b"),
    "page navigation": re.compile(
        r"\b(?:window|document|self|top|parent)\.location(?:\.href)?\s*=(?!=)|\blocation\.href\s*=(?!=)"
        r"|\blocation\.(?:assign|replace)\s*\(|\bwindow\.open\s*\("),
    "a sensitive browser API": re.compile(
        r"\bnavigator\.(?:clipboard|geolocation|mediaDevices|credentials|serviceWorker)\b"
        r"|\bgetUserMedia\b|\bpostMessage\s*\(|\bNotification\.requestPermission\b"),
    "encoded or obfuscated code": re.compile(
        r"\batob\s*\(|\bunescape\s*\(|\bString\.fromCharCode\s*\("),
}

# Markup-level features, matched on the no_comments view (Angular templates live in strings).
RAW_HTML = "raw HTML injection"
_MARKUP_CAPABILITIES: dict[str, re.Pattern] = {
    RAW_HTML: re.compile(
        r"\bdangerouslySetInnerHTML\b|\bv-html\b|\[innerHTML\]|\.(?:innerHTML|outerHTML)\s*\+?=(?!=)"
        r"|\binsertAdjacentHTML\s*\(|\bbypassSecurityTrust\w+"),
    "embedded external content": re.compile(
        r"<\s*(?:iframe|object|embed|frame)\b|<\s*script\b[^>]*\bsrc\s*="
        r"|createElement\(\s*[\"'`](?:script|iframe)[\"'`]"
        r"|<\s*meta\b[^>]*http-equiv\s*=\s*[\"']?refresh|<\s*base\b[^>]*\bhref",
        re.IGNORECASE),
    "a javascript: URL": re.compile(r"[\"'`=]\s*javascript\s*:", re.IGNORECASE),
}

_HOST = re.compile(
    r"(?:(?:https?|wss?|ftp):|(?<=[\"'`(=\s]))//"
    r"((?:[a-z0-9-]+\.)+[a-z]{2,}|localhost|\d{1,3}(?:\.\d{1,3}){3})",
    re.IGNORECASE,
)
_IGNORED_HOSTS = {"www.w3.org"}  # XML namespaces (SVG, MathML)

_IMPORT = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)["'`]([^"'`\s]+)["'`]"""
)

_FRAMEWORK_PACKAGES = {
    "React":   {"react", "react-dom", "prop-types"},
    "Vue":     {"vue"},
    "Angular": {"rxjs"},     # plus every @angular/* package
    "HTML":    set(),
}


def _package(specifier: str) -> str | None:
    """npm package of an import specifier; None for relative paths and URLs."""
    if specifier.startswith((".", "/", "~", "#")) or "://" in specifier:
        return None
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") and len(parts) > 1 else parts[0]


def _packages(no_comments: str) -> set[str]:
    return {pkg for spec in _IMPORT.findall(no_comments) if (pkg := _package(spec))}


def _hosts(no_comments: str) -> Counter:
    return Counter(host.lower() for host in _HOST.findall(no_comments) if host.lower() not in _IGNORED_HOSTS)


def _first(pattern: re.Pattern, text: str) -> str:
    match = pattern.search(text)
    return re.sub(r"\s+", " ", match.group(0)).strip() if match else ""


# ── Check ─────────────────────────────────────────────────────────────────────

def check_output(
    source_code: str,
    source_framework: str,
    output_code: str,
    target_framework: str,
) -> OutputReport:
    report = OutputReport()
    if not output_code or not output_code.strip():
        return report

    source_plain, source_logic = views(source_code, source_framework)
    output_plain, output_logic = views(output_code, target_framework)

    def compare(capabilities: dict[str, re.Pattern], source_view: str, output_view: str) -> None:
        for name, pattern in capabilities.items():
            found = _first(pattern, output_view)
            if not found or pattern.search(source_view):
                continue
            message = f"output adds {name} ('{found}') that the source code does not contain"
            if name == RAW_HTML and target_framework == "HTML":
                report.warnings.append(f"{message}; make sure inserted values are escaped")
            else:
                report.violations.append(f"security: {message}; remove it")

    compare(_LOGIC_CAPABILITIES, source_logic, output_logic)
    compare(_MARKUP_CAPABILITIES, source_plain, output_plain)

    source_hosts, output_hosts = _hosts(source_plain), _hosts(output_plain)
    for host, count in output_hosts.items():
        if count > source_hosts.get(host, 0):
            where = "that the source code does not contain" if host not in source_hosts else "more often than the source code does"
            report.violations.append(f"security: output uses a URL on '{host}' {where}; remove it")

    allowed = _packages(source_plain) | _FRAMEWORK_PACKAGES.get(target_framework, set())
    for package in sorted(_packages(output_plain) - allowed):
        if target_framework == "Angular" and package.startswith("@angular/"):
            continue
        report.violations.append(
            f"security: output imports the package '{package}', which the source code does not use; "
            "remove the import and everything that depends on it"
        )

    return report
