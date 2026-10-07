"""
Style fidelity: the translation may only carry over CSS the source already has.

Compares stylesheet declarations (<style> blocks, Angular `styles`) in the output
with every declaration the source contains (stylesheets and inline styles).
Inline styles in the output are not checked: turning a conditional render into
style="display: none" is a normal translation, inventing a stylesheet is not.
"""

from __future__ import annotations

import re

Declaration = tuple[str, str]

_STYLE_BLOCK = re.compile(r"<style\b[^>]*>([\s\S]*?)</style>", re.IGNORECASE)
_ANGULAR_STYLES = re.compile(r"\bstyles\s*:\s*(\[[\s\S]*?\]|`[\s\S]*?`|'[^']*'|\"[^\"]*\")")
_DECLARATION = re.compile(r"(?<![\w-])(-{0,2}[a-zA-Z][\w-]*)\s*:\s*([^;{}]+?)\s*(?:;|(?=\}))")
_INLINE_ATTR = re.compile(r"""(?<![\w:\[-])style\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_INLINE_OBJECT = re.compile(r"""(?:\bstyle\s*=\s*\{\s*|:style\s*=\s*["']\s*|\[ngStyle\]\s*=\s*["']\s*)\{([^{}]*)\}""")
_OBJECT_ENTRY = re.compile(r"""["']?([A-Za-z][\w-]*)["']?\s*:\s*(?:"([^"]*)"|'([^']*)'|`([^`]*)`|([^,}]+))""")
_CSS_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
_EMPTY_RULE = re.compile(r"[^{}]*\{\s*\}")

# Generated when a conditional render becomes a hidden element; not an invented design.
_ALWAYS_ALLOWED = {("display", "none")}


def _normalize(prop: str, value: str) -> Declaration:
    prop = re.sub(r"(?<=[a-z])([A-Z])", r"-\1", prop).lower()
    value = re.sub(r"\s+", " ", value.strip().strip("\"'`")).lower()
    value = re.sub(r"\s*!important$", "", value).rstrip(";").strip()
    return prop, value


def stylesheets(code: str) -> list[str]:
    """Raw CSS text of every stylesheet in the code."""
    sheets = [match.group(1) for match in _STYLE_BLOCK.finditer(code)]
    sheets += [match.group(1) for match in _ANGULAR_STYLES.finditer(code)]
    return [_CSS_COMMENT.sub("", sheet) for sheet in sheets]


def stylesheet_declarations(code: str) -> set[Declaration]:
    return {
        _normalize(prop, value)
        for sheet in stylesheets(code)
        for prop, value in _DECLARATION.findall(sheet)
    }


def inline_declarations(code: str) -> set[Declaration]:
    found = set()
    for match in _INLINE_ATTR.finditer(code):
        text = (match.group(1) or match.group(2) or "") + ";"
        found.update(_normalize(prop, value) for prop, value in _DECLARATION.findall(text))
    for match in _INLINE_OBJECT.finditer(code):
        for entry in _OBJECT_ENTRY.finditer(match.group(1)):
            value = next((group for group in entry.groups()[1:] if group is not None), "")
            found.add(_normalize(entry.group(1), value))
    return found


def invented_declarations(source: str, output: str) -> list[str]:
    """Stylesheet declarations in the output that the source has nowhere, as 'property: value'."""
    allowed = stylesheet_declarations(source) | inline_declarations(source) | _ALWAYS_ALLOWED
    invented = stylesheet_declarations(output) - allowed
    return sorted(f"{prop}: {value}" for prop, value in invented)


def remove_empty_styles(code: str) -> str:
    """Drop CSS rules with no declarations, then stylesheets with no rules."""
    def strip_rules(css: str) -> str:
        previous = None
        while previous != css:
            previous = css
            css = _EMPTY_RULE.sub("", css)
        return css

    def clean_block(match: re.Match) -> str:
        body = match.group(2)
        wrapped = re.fullmatch(r"\s*\{`([\s\S]*)`\}\s*", body)      # JSX: <style>{`...`}</style>
        css = strip_rules(wrapped.group(1) if wrapped else body)
        if not css.strip():
            return ""
        return f"{match.group(1)}{{`{css}`}}{match.group(3)}" if wrapped else f"{match.group(1)}{css}{match.group(3)}"

    code = re.sub(r"(<style\b[^>]*>)([\s\S]*?)(</style>)", clean_block, code, flags=re.IGNORECASE)

    def clean_angular(match: re.Match) -> str:
        css = strip_rules(re.sub(r"[\[\]`'\"]", "", match.group(3)))
        if css.strip().strip(","):
            return match.group(0)
        return "," if match.group(1) and "," in match.group(4) else ""

    code = re.sub(r"(,?)(\s*\bstyles\s*:\s*)(\[[^\]]*\]|`[^`]*`)(\s*,?)", clean_angular, code)
    return re.sub(r"\n{3,}", "\n\n", code)
