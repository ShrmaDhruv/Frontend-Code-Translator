"""
Shared tree-sitter helpers for the framework extractors.

Grammars:
    javascript  plain JS + JSX        (HTML scripts, Vue <script>)
    tsx         TypeScript + JSX      (React)
    typescript  TypeScript            (Angular, Vue <script lang="ts">)
    html        HTML                  (HTML documents, Vue SFC blocks, Angular templates)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterator

import tree_sitter as ts

Node = ts.Node

FUNCTION_TYPES = {"arrow_function", "function_expression", "function", "function_declaration"}
JSX_TYPES      = {"jsx_element", "jsx_self_closing_element", "jsx_fragment"}
CLEANUP_CALLS  = {"clearInterval", "clearTimeout", "removeEventListener", "unsubscribe", "disconnect"}


@lru_cache(maxsize=None)
def _language(name: str) -> ts.Language:
    if name == "javascript":
        import tree_sitter_javascript as grammar
        return ts.Language(grammar.language())
    if name == "tsx":
        import tree_sitter_typescript as grammar
        return ts.Language(grammar.language_tsx())
    if name == "typescript":
        import tree_sitter_typescript as grammar
        return ts.Language(grammar.language_typescript())
    if name == "html":
        import tree_sitter_html as grammar
        return ts.Language(grammar.language())
    raise ValueError(f"unknown grammar '{name}'")


def parse(code: str, grammar: str) -> Node:
    return ts.Parser(_language(grammar)).parse(code.encode("utf-8")).root_node


def text(node: Node | None) -> str:
    return node.text.decode("utf-8") if node is not None else ""


def walk(node: Node, types: set[str] | None = None) -> Iterator[Node]:
    """Depth-first walk over named nodes, optionally filtered by type."""
    stack = [node]
    while stack:
        current = stack.pop()
        if types is None or current.type in types:
            yield current
        stack.extend(reversed(current.named_children))


def has_error(node: Node) -> bool:
    return node.has_error


def field(node: Node | None, name: str) -> Node | None:
    return node.child_by_field_name(name) if node is not None else None


def unwrap(node: Node | None) -> Node | None:
    """Strip parentheses / TS `as` / non-null wrappers around an expression."""
    while node is not None and node.type in (
        "parenthesized_expression", "as_expression", "non_null_expression", "satisfies_expression",
    ):
        node = node.named_children[0] if node.named_children else None
    return node


# ── Calls ─────────────────────────────────────────────────────────────────────

def call_name(call: Node) -> str:
    """`useState` for useState(...), `React.useState` for React.useState(...)."""
    fn = field(call, "function")
    return text(fn) if fn is not None else ""


def call_base_name(call: Node) -> str:
    """Last segment of the callee: `useState` for both useState() and React.useState()."""
    return call_name(call).split(".")[-1]


def call_args(call: Node) -> list[Node]:
    args = field(call, "arguments")
    if args is None:
        return []
    return [a for a in args.named_children if a.type != "comment"]


def is_call_to(node: Node | None, *names: str) -> bool:
    node = unwrap(node)
    return node is not None and node.type == "call_expression" and call_base_name(node) in names


# ── Functions ─────────────────────────────────────────────────────────────────

def params(fn: Node | None) -> list[str]:
    """Parameter names, dropping types and defaults."""
    if fn is None:
        return []
    single = field(fn, "parameter")
    if single is not None:
        return [text(single)]
    plist = field(fn, "parameters")
    if plist is None:
        return []
    return [
        text(field(p, "pattern") or field(p, "left") or p)
        for p in plist.named_children
        if p.type != "comment"
    ]


def body_node(fn: Node | None) -> Node | None:
    return field(fn, "body") if fn is not None else None


def body_text(fn: Node | None) -> str:
    """Function body without the surrounding braces, or the expression of a concise arrow."""
    body = body_node(fn)
    if body is None:
        return ""
    if body.type == "statement_block":
        return text(body)[1:-1].strip()
    return text(body).strip()


def returned_function(fn: Node | None) -> Node | None:
    """For `() => { ...; return () => cleanup }`, the returned cleanup function (top level only)."""
    body = body_node(fn)
    if body is None or body.type != "statement_block":
        return None
    for stmt in body.named_children:
        if stmt.type == "return_statement" and stmt.named_children:
            value = unwrap(stmt.named_children[0])
            if value is not None and value.type in FUNCTION_TYPES:
                return value
    return None


def body_without_return(fn: Node | None) -> str:
    body = body_node(fn)
    if body is None:
        return ""
    if body.type != "statement_block":
        return text(body).strip()
    return "\n".join(
        text(stmt) for stmt in body.named_children
        if stmt.type not in ("return_statement", "comment")
    ).strip()


def function_value(node: Node | None) -> Node | None:
    """The function node if `node` is a function or useCallback-style wrapper around one."""
    node = unwrap(node)
    if node is None:
        return None
    if node.type in FUNCTION_TYPES:
        return node
    return None


# ── Identifiers / JSX ─────────────────────────────────────────────────────────

def identifiers(node: Node | None) -> set[str]:
    """Every identifier referenced inside `node` (including `x` in `this.x` / `props.x`)."""
    if node is None:
        return set()
    names = set()
    for n in walk(node, {"identifier", "shorthand_property_identifier", "property_identifier"}):
        names.add(text(n))
    return names


def contains_jsx(node: Node | None) -> bool:
    return node is not None and any(True for _ in walk(node, JSX_TYPES))


def imports(root: Node) -> list[dict]:
    result = []
    for stmt in root.named_children:
        if stmt.type != "import_statement":
            continue
        source = field(stmt, "source")
        entry = {"source": text(source).strip("'\"`"), "specifiers": [], "default": None}
        for clause in walk(stmt, {"import_clause"}):
            for part in clause.named_children:
                if part.type == "identifier":
                    entry["default"] = text(part)
                elif part.type == "named_imports":
                    for spec in part.named_children:
                        name = field(spec, "alias") or field(spec, "name")
                        if name is not None:
                            entry["specifiers"].append(text(name))
                elif part.type == "namespace_import":
                    entry["default"] = text(part)
        result.append(entry)
    return result


def string_value(node: Node | None) -> str | None:
    node = unwrap(node)
    if node is None:
        return None
    if node.type == "string":
        return text(node)[1:-1]
    if node.type == "template_string" and not any(True for _ in walk(node, {"template_substitution"})):
        return text(node)[1:-1]
    return None


def object_entries(obj: Node | None) -> list[tuple[str, Node, Node]]:
    """(key, value_or_method_node, entry_node) for each property of an object literal."""
    obj = unwrap(obj)
    if obj is None or obj.type != "object":
        return []
    entries = []
    for entry in obj.named_children:
        if entry.type == "pair":
            key = field(entry, "key")
            entries.append((text(key).strip("'\"`"), field(entry, "value"), entry))
        elif entry.type == "method_definition":
            entries.append((text(field(entry, "name")), entry, entry))
        elif entry.type == "shorthand_property_identifier":
            entries.append((text(entry), entry, entry))
    return entries


def guess_type(init: str | None) -> str:
    if init is None:
        return "any"
    value = init.strip()
    if value in ("true", "false"):
        return "boolean"
    if value.lstrip("-").replace(".", "", 1).isdigit():
        return "number"
    if value[:1] in ("'", '"', "`"):
        return "string"
    if value.startswith("["):
        return "array"
    if value.startswith("{"):
        return "object"
    return "any"


def lifecycle(hook: str, body: str = "", **extra) -> dict:
    return {"hook": hook, "body": body, **extra}


def method(name: str, fn: Node | None) -> dict:
    return {"name": name, "params": params(fn), "body": body_text(fn)}


# ── HTML-grammar helpers (HTML docs, Vue SFC, Angular templates) ──────────────

def html_tag(element: Node) -> str:
    start = next((c for c in element.named_children if c.type in ("start_tag", "self_closing_tag")), None)
    name = next((c for c in start.named_children if c.type == "tag_name"), None) if start else None
    return text(name).lower()


def html_attrs(element: Node) -> list[tuple[str, str | None]]:
    start = next((c for c in element.named_children if c.type in ("start_tag", "self_closing_tag")), None)
    if start is None:
        return []
    attrs = []
    for attr in start.named_children:
        if attr.type != "attribute":
            continue
        name = next((c for c in attr.named_children if c.type == "attribute_name"), None)
        value = next((c for c in attr.named_children if c.type in ("attribute_value", "quoted_attribute_value")), None)
        raw = text(value)
        if value is not None and value.type == "quoted_attribute_value":
            raw = raw[1:-1]
        attrs.append((text(name), raw if value is not None else None))
    return attrs


def html_raw_text(element: Node) -> str:
    raw = next((c for c in element.named_children if c.type == "raw_text"), None)
    return text(raw)


def html_all_attrs(root: Node) -> list[tuple[str, str, str | None]]:
    """(tag, attr_name, attr_value) for every element in the tree."""
    result = []
    for element in walk(root, {"element", "script_element", "style_element"}):
        tag = html_tag(element)
        for name, value in html_attrs(element):
            result.append((tag, name, value))
    return result


def html_elements(root: Node, tag: str) -> list[Node]:
    return [e for e in walk(root, {"element", "script_element", "style_element"}) if html_tag(e) == tag]


def html_inner_text(element: Node) -> str:
    return " ".join(text(t).strip() for t in walk(element, {"text"}) if text(t).strip())
