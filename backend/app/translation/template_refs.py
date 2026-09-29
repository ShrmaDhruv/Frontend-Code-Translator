"""
Find identifiers used in a Vue / Angular template that the component never defines
(e.g. `{{ parity }}` with no `parity` in <script setup>). Those render as empty /
fail to compile, which neither the regex checks nor the LLM judge reliably catch.

Conservative by design: expressions that fail to parse are skipped, and only
root identifiers are checked (`todo` in `todo.done`, never `done`).
"""

from __future__ import annotations

import re

from app.ast_layer.treesitter.common import (
    field, html_all_attrs, identifiers, imports, parse, text, walk,
)

_JS_GLOBALS = {
    "true", "false", "null", "undefined", "NaN", "Infinity", "this", "arguments",
    "Math", "Number", "String", "Boolean", "Array", "Object", "Date", "JSON",
    "parseInt", "parseFloat", "isNaN", "encodeURIComponent", "decodeURIComponent",
    "console", "window", "document", "alert", "confirm", "Intl", "Promise", "Set", "Map",
}
_VUE_GLOBALS = {"$event", "$emit", "$refs", "$slots", "$attrs", "$props", "$el", "$route", "$router", "$t"}
_ANGULAR_GLOBALS = {"$event", "$any", "undefined"}

_INTERPOLATION = re.compile(r"\{\{([\s\S]*?)\}\}")


def _root_identifiers(expression: str) -> set[str] | None:
    """Free identifiers of a JS expression, or None if it doesn't parse."""
    root = parse(expression, "javascript")
    if root.has_error:
        return None
    local = set()
    for fn in walk(root, {"arrow_function", "function_expression"}):
        params = field(fn, "parameters") or field(fn, "parameter")
        local |= identifiers(params)
    return {text(n) for n in walk(root, {"identifier"})} - local


def _check(expressions: list[str], defined: set[str]) -> list[str]:
    missing = []
    for expression in expressions:
        names = _root_identifiers(expression.strip()) if expression and expression.strip() else set()
        for name in sorted(names or ()):
            if name not in defined and name not in missing:
                missing.append(name)
    return missing


def _script_names(script: str, grammar: str) -> set[str]:
    """Every top-level name the script declares or imports."""
    root = parse(script, grammar)
    names = set()
    for entry in imports(root):
        names |= set(entry["specifiers"])
        if entry["default"]:
            names.add(entry["default"].split(" as ")[-1].strip())
    for stmt in root.named_children:
        if stmt.type in ("lexical_declaration", "variable_declaration"):
            for decl in stmt.named_children:
                if decl.type == "variable_declarator":
                    name = field(decl, "name")
                    names |= identifiers(name) if name is not None and name.type != "identifier" else {text(name)}
        elif stmt.type in ("function_declaration", "class_declaration"):
            names.add(text(field(stmt, "name")))
    return names


# ── Vue ───────────────────────────────────────────────────────────────────────

def _vue(code: str) -> list[str]:
    from app.ast_layer.treesitter.vue import split_sfc
    from app.ast_layer.treesitter.vue import extract as extract_vue

    blocks = split_sfc(code)
    if not blocks["is_setup"] or not blocks["template"]:
        return []

    grammar = "typescript" if blocks["lang"] == "ts" else "javascript"
    defined = _script_names(blocks["script"], grammar) | _VUE_GLOBALS | _JS_GLOBALS
    defined |= {p["name"] for p in extract_vue(code)["props"]}

    expressions = [m.group(1) for m in _INTERPOLATION.finditer(blocks["template"])]
    for _, name, value in html_all_attrs(parse(blocks["template"], "html")):
        if value is None:
            continue
        if name == "v-for":
            if match := re.match(r"\s*(.+?)\s+(?:in|of)\s+(.+)", value, re.S):
                alias, source = match.groups()
                defined |= set(re.findall(r"[A-Za-z_$][\w$]*", alias))
                expressions.append(source)
        elif name.startswith("#") or name.startswith("v-slot"):
            defined |= set(re.findall(r"[A-Za-z_$][\w$]*", value))
        elif name.startswith(("@", "v-on:", ":", "v-bind:", "v-if", "v-else-if", "v-show", "v-model", "v-html", "v-text")):
            expressions.append(value)
    return _check(expressions, defined)


# ── Angular ───────────────────────────────────────────────────────────────────

def _strip_pipes(expression: str) -> str:
    return re.split(r"(?<!\|)\|(?!\|)", expression, maxsplit=1)[0]


def _angular(code: str) -> list[str]:
    from app.ast_layer.treesitter import angular

    root = parse(code, "typescript")
    _, decorator = angular._find_component(root)
    template = angular._metadata(decorator)["template"]
    if not template:
        return []

    facts = angular.extract(code)
    defined = {
        item["name"] if isinstance(item, dict) else item
        for key in ("props", "state_hints", "variables", "computed_hints", "method_hints",
                    "outputs", "view_children", "injected_services")
        for item in facts.get(key, [])
    } | _ANGULAR_GLOBALS | _JS_GLOBALS

    expressions = [_strip_pipes(m.group(1)) for m in _INTERPOLATION.finditer(template)]
    for _, name, value in html_all_attrs(parse(template, "html")):
        if name.startswith("#"):
            defined.add(name[1:])
            continue
        if value is None:
            continue
        if name == "*ngFor":
            for part in value.split(";"):
                part = part.strip()
                if match := re.match(r"let\s+(\w+)\s+of\s+(.+)", part):
                    defined.add(match.group(1))
                    expressions.append(_strip_pipes(match.group(2)))
                elif match := re.match(r"let\s+(\w+)\s*=", part):
                    defined.add(match.group(1))
                elif match := re.match(r"trackBy\s*:\s*(\w+)", part):
                    expressions.append(match.group(1))
        elif name == "*ngIf":
            condition, *rest = value.split(";")
            if match := re.search(r"\bas\s+(\w+)", condition):
                defined.add(match.group(1))
                condition = condition[: match.start()]
            expressions.append(_strip_pipes(condition))
        elif name.startswith(("(", "[")):
            expressions.append(_strip_pipes(value))
    return _check(expressions, defined)


def undefined_template_refs(code: str, target: str) -> list[str]:
    try:
        if target == "Vue":
            return _vue(code)
        if target == "Angular":
            return _angular(code)
    except Exception:
        return []
    return []
