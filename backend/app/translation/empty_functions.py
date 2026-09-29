"""
Named functions/methods with an empty body, e.g. a `function render() {}` left
behind after the model's "// Vue handles this" comment was stripped.

The cleaner removes them together with their bare call statements when nothing
else references them; the validator reports any that remain.
"""

import re

_PATTERNS = [
    # function name(...) {}
    r'(?m)^[ \t]*(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\([^)]*\)\s*\{\s*\}[ \t]*;?[ \t]*\n?',
    # const name = (...) => {}
    r'(?m)^[ \t]*(?:const|let|var)\s+(?P<name>\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>\s*\{\s*\}[ \t]*;?[ \t]*\n?',
    # class / object method: name(...): type {}
    r'(?m)^[ \t]*(?:(?:public|private|protected|static|async)\s+)*'
    r'(?!(?:constructor|if|for|while|switch|catch|function|return)\b)(?P<name>\w+)\s*\([^)]*\)'
    r'\s*(?::\s*[\w<>\[\]|, ]+)?\s*\{\s*\}[ \t]*\n?',
]


def find(code: str) -> list[re.Match]:
    matches = [m for pattern in _PATTERNS for m in re.finditer(pattern, code)]
    return sorted(matches, key=lambda m: m.start())


def names(code: str) -> list[str]:
    return list(dict.fromkeys(m.group("name") for m in find(code)))


def remove(code: str) -> str:
    """Drop empty functions and their bare `name()` / `this.name()` call lines, if otherwise unused."""
    for name in names(code):
        candidate = code
        for match in reversed([m for m in find(candidate) if m.group("name") == name]):
            candidate = candidate[:match.start()] + candidate[match.end():]
        candidate = re.sub(
            rf'(?m)^[ \t]*(?:this\.)?{re.escape(name)}\s*\(\s*\)\s*;?[ \t]*\n?', '', candidate,
        )
        if not re.search(rf'\b{re.escape(name)}\b', candidate):
            code = candidate
    return code
