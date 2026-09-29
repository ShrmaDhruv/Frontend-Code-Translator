"""
Tree-sitter based extractors.

Each extractor returns the same summary-dict shape as the legacy regex
extractors (props / state_hints / computed_hints / lifecycle_hints /
method_hints / template_hints / script_block / styles ...), but with full
facts: method params and bodies, lifecycle bodies, computed expressions and
dependencies. That lets ir_builder build the IR deterministically.
"""

import re

from app.ast_layer.treesitter import angular, html, react, vue

EXTRACTORS = {
    "React":   react.extract,
    "Vue":     vue.extract,
    "Angular": angular.extract,
    "HTML":    html.extract,
}


def _fill_this_deps(facts: dict) -> None:
    """Class/Options-API computed values reference data through `this.x`."""
    known = {
        item["name"] if isinstance(item, dict) else item
        for key in ("props", "state_hints", "computed_hints")
        for item in facts.get(key, [])
    }
    for computed in facts.get("computed_hints", []):
        if not computed.get("deps"):
            refs = set(re.findall(r"\bthis\.(\w+)", computed.get("expression", "")))
            computed["deps"] = sorted((refs & known) - {computed["name"]})


def extract(code: str, framework: str) -> dict:
    facts = EXTRACTORS[framework](code)
    _fill_this_deps(facts)
    facts["extractor"] = "tree-sitter"
    return facts


__all__ = ["extract", "EXTRACTORS"]
