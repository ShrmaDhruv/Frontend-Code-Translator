import re


_FENCE_LANGUAGES = {
    "react", "vue", "angular", "html", "javascript", "typescript",
    "js", "ts", "jsx", "tsx", "svelte", "css", "scss",
}


def _strip_think_blocks(raw: str) -> str:
    return re.sub(r'<think>[\s\S]*?</think>', '', raw).strip()


def _extract_fenced_block(raw: str) -> str | None:
    pattern = re.compile(
        r'```(?:' + '|'.join(_FENCE_LANGUAGES) + r')?\s*\n([\s\S]*?)```',
        re.IGNORECASE,
    )
    matches = pattern.findall(raw)
    if matches:
        return max(matches, key=len).strip()
    return None


def _extract_by_marker(raw: str, target_framework: str) -> str | None:
    if target_framework == "HTML":
        m = re.search(r'(<!DOCTYPE[\s\S]+)', raw, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    if target_framework == "Vue":
        m = re.search(r'(<template>[\s\S]+)', raw)
        if m:
            return m.group(1).strip()

    if target_framework in ("React", "Angular"):
        m = re.search(r'(import\s+[\s\S]+)', raw)
        if m:
            return m.group(1).strip()

    return None


def _strip_fallback(raw: str) -> str:
    lines    = raw.splitlines()
    cleaned  = []
    skip_prefixes = (
        "here is", "here's", "the translated", "translating",
        "below is", "output:", "result:", "translation:",
        "i've translated", "i have translated",
    )

    for line in lines:
        stripped = line.strip().lower()
        if any(stripped.startswith(p) for p in skip_prefixes):
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def _remove_comments(code: str) -> str:
    code = re.sub(r'<!--[\s\S]*?-->', '', code)
    code = re.sub(r'/\*[\s\S]*?\*/', '', code)
    code = re.sub(
        r'(?m)(^|[;{}\s])//[^\n\r]*',
        lambda match: match.group(1).rstrip(),
        code,
    )
    return code


def _remove_empty_placeholders(code: str) -> str:
    code = re.sub(
        r'\n?\s*on(?:Mounted|Unmounted|Updated|BeforeMount|BeforeUnmount)\s*'
        r'\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)\s*;?',
        '',
        code,
    )
    code = re.sub(
        r'\n?\s*watch(?:Effect)?\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)\s*;?',
        '',
        code,
    )
    code = re.sub(
        r'\n?\s*useEffect\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*'
        r'(?:,\s*\[[^\]]*\])?\s*\)\s*;?',
        '',
        code,
    )
    code = re.sub(
        r'\n?\s*ng(?:OnInit|OnDestroy|DoCheck|OnChanges)\s*'
        r'\([^)]*\)\s*(?::\s*\w+)?\s*\{\s*\}',
        '',
        code,
    )
    return code


def _remove_artifact_lines(code: str) -> str:
    cleaned = []
    for line in code.splitlines():
        stripped = line.strip()
        if re.fullmatch(r'(?:0x)?[0-9a-fA-F]{8,}', stripped):
            continue
        if re.fullmatch(r'[A-Za-z0-9+/=]{24,}', stripped):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _prune_unused_vue_imports(code: str) -> str:
    def replace_import(match: re.Match) -> str:
        specifiers = [item.strip() for item in match.group(1).split(",") if item.strip()]
        rest = code[:match.start()] + code[match.end():]
        kept = []

        for specifier in specifiers:
            local_name = specifier.split(" as ", 1)[-1].strip()
            if re.search(rf'\b{re.escape(local_name)}\b', rest):
                kept.append(specifier)

        if not kept:
            return ""
        return f"import {{ {', '.join(kept)} }} from 'vue'"

    return re.sub(
        r'import\s*\{([^}]+)\}\s*from\s*["\']vue["\']',
        replace_import,
        code,
    )


def _prune_unused_angular_imports(code: str) -> str:
    def replace_import(match: re.Match) -> str:
        specifiers = [item.strip() for item in match.group(1).split(",") if item.strip()]
        rest = code[:match.start()] + code[match.end():]
        kept = []

        for specifier in specifiers:
            local_name = specifier.split(" as ", 1)[-1].strip()
            if re.search(rf'\b{re.escape(local_name)}\b', rest):
                kept.append(specifier)

        if not kept:
            return ""
        return f"import {{ {', '.join(kept)} }} from '@angular/core'"

    return re.sub(
        r'import\s*\{([^}]+)\}\s*from\s*["\']@angular/core["\']',
        replace_import,
        code,
    )


def _sanitize_output(code: str, target_framework: str) -> str:
    code = _remove_comments(code)
    code = _remove_empty_placeholders(code)
    code = _remove_artifact_lines(code)
    if target_framework == "Vue":
        code = _prune_unused_vue_imports(code)
    if target_framework == "Angular":
        code = _prune_unused_angular_imports(code)
    return code.strip()


def clean(raw: str, target_framework: str) -> str:
    """
    Extract clean translated code from a raw Ollama response.

    Attempts three strategies in order, returning the first success.
    Falls back to the stripped raw response if all strategies fail.

    Args:
        raw              : Raw string from Phi3Client.chat()
        target_framework : One of React | Vue | Angular | HTML
                           Used to guide marker-based extraction

    Returns:
        Clean code string with no markdown, fences, or preamble
    """
    if not raw or not raw.strip():
        raise ValueError("Empty response from model — nothing to clean")

    text = _strip_think_blocks(raw)

    fenced = _extract_fenced_block(text)
    if fenced:
        return _sanitize_output(fenced, target_framework)

    by_marker = _extract_by_marker(text, target_framework)
    if by_marker:
        return _sanitize_output(by_marker, target_framework)

    return _sanitize_output(_strip_fallback(text), target_framework)
