"""React extractor (function components with hooks, plus basic class components)."""

from __future__ import annotations

from app.ast_layer.treesitter.common import (
    Node, body_node, body_text, body_without_return, call_args, call_base_name, call_name,
    contains_jsx, field, function_value, guess_type, identifiers, imports, is_call_to,
    lifecycle, method, object_entries, params, parse, returned_function, text, unwrap, walk,
)

_CLASS_LIFECYCLE = {
    "componentDidMount":    "onMount",
    "componentWillUnmount": "onDestroy",
    "componentDidUpdate":   "onUpdate",
}


# ── Component discovery ───────────────────────────────────────────────────────

def _declared_functions(root: Node) -> list[tuple[str, Node, bool]]:
    """(name, function-or-class node, is_default_export) for top-level declarations."""
    found = []
    default_name = None

    for stmt in root.named_children:
        is_default = False
        decl = stmt
        if stmt.type == "export_statement":
            is_default = any(c.type == "default" for c in stmt.children)
            decl = field(stmt, "declaration") or field(stmt, "value")
            if decl is not None and decl.type == "identifier":
                default_name = text(decl)
                continue
        if decl is None:
            continue

        if decl.type in ("function_declaration", "class_declaration"):
            found.append((text(field(decl, "name")), decl, is_default))
        elif decl.type in ("lexical_declaration", "variable_declaration"):
            for declarator in decl.named_children:
                if declarator.type != "variable_declarator":
                    continue
                value = unwrap(field(declarator, "value"))
                if value is not None and value.type == "call_expression" and call_base_name(value) in ("memo", "forwardRef"):
                    args = call_args(value)
                    value = unwrap(args[0]) if args else None
                fn = function_value(value)
                if fn is not None:
                    found.append((text(field(declarator, "name")), fn, is_default))
        elif decl.type in ("arrow_function", "function_expression", "function"):
            found.append((text(field(decl, "name")) or "App", decl, True))

    if default_name:
        found = [(n, node, d or n == default_name) for n, node, d in found]
    return found


def _find_component(root: Node) -> tuple[str, Node | None]:
    candidates = [
        (name, node, is_default) for name, node, is_default in _declared_functions(root)
        if name[:1].isupper() and (contains_jsx(node) or _is_class_component(node))
    ]
    if not candidates:
        return "App", None
    candidates.sort(key=lambda c: not c[2])
    return candidates[0][0], candidates[0][1]


def _is_class_component(node: Node) -> bool:
    if node.type != "class_declaration":
        return False
    heritage = next((c for c in node.named_children if c.type == "class_heritage"), None)
    return heritage is not None and "Component" in text(heritage)


# ── Props ─────────────────────────────────────────────────────────────────────

def _props_from_pattern(pattern: Node) -> list[dict]:
    props = []
    for part in pattern.named_children:
        if part.type == "shorthand_property_identifier_pattern":
            props.append({"name": text(part), "type": "any", "required": True, "default": None})
        elif part.type == "object_assignment_pattern":
            default = text(field(part, "right"))
            props.append({
                "name": text(field(part, "left")), "type": guess_type(default),
                "required": False, "default": default,
            })
        elif part.type == "pair_pattern":
            value = field(part, "value")
            default = text(field(value, "right")) if value is not None and value.type == "assignment_pattern" else None
            props.append({
                "name": text(field(part, "key")), "type": guess_type(default),
                "required": default is None, "default": default,
            })
    return props


def _member_props(scope: Node, object_text: str) -> list[dict]:
    names = []
    for member in walk(scope, {"member_expression"}):
        if text(field(member, "object")) == object_text:
            names.append(text(field(member, "property")))
    return [{"name": n, "type": "any", "required": True, "default": None} for n in dict.fromkeys(names)]


def _function_props(fn: Node) -> list[dict]:
    plist = field(fn, "parameters")
    first = plist.named_children[0] if plist is not None and plist.named_children else field(fn, "parameter")
    if first is None:
        return []
    pattern = field(first, "pattern") or first
    if pattern.type == "assignment_pattern":
        pattern = field(pattern, "left")
    if pattern is None:
        return []
    if pattern.type == "object_pattern":
        return _props_from_pattern(pattern)
    if pattern.type == "identifier":
        return _member_props(fn, text(pattern))
    return []


# ── Function component body ───────────────────────────────────────────────────

def _effect(call: Node) -> list[dict]:
    args = call_args(call)
    fn = function_value(args[0]) if args else None
    if fn is None:
        return []

    deps_node = unwrap(args[1]) if len(args) > 1 else None
    main = body_without_return(fn)
    hooks = []

    if deps_node is None:
        hooks.append(lifecycle("onEveryRender", main))
    elif deps_node.type == "array" and not deps_node.named_children:
        hooks.append(lifecycle("onMount", main, deps=[]))
    else:
        deps = [text(d) for d in deps_node.named_children] if deps_node.type == "array" else [text(deps_node)]
        hooks.append(lifecycle("onUpdate", main, deps=deps))

    cleanup = returned_function(fn)
    if cleanup is not None:
        hooks.append(lifecycle("onDestroy", body_text(cleanup)))
    return hooks


def _extract_function_component(fn: Node, facts: dict) -> None:
    facts["props"] = _function_props(fn)
    reactive = {p["name"] for p in facts["props"]}

    body = body_node(fn)
    if body is None or body.type != "statement_block":
        return

    for stmt in body.named_children:
        if stmt.type in ("lexical_declaration", "variable_declaration"):
            for decl in stmt.named_children:
                if decl.type == "variable_declarator":
                    _declarator(decl, facts, reactive)

        elif stmt.type == "function_declaration":
            facts["method_hints"].append(method(text(field(stmt, "name")), stmt))

        elif stmt.type == "expression_statement":
            expr = unwrap(stmt.named_children[0]) if stmt.named_children else None
            if is_call_to(expr, "useEffect", "useLayoutEffect"):
                facts["lifecycle_hints"].extend(_effect(expr))


def _declarator(decl: Node, facts: dict, reactive: set[str]) -> None:
    name_node = field(decl, "name")
    value = unwrap(field(decl, "value"))
    if name_node is None or value is None:
        return
    name = text(name_node)
    args = call_args(value) if value.type == "call_expression" else []

    if is_call_to(value, "useState", "useReducer"):
        elements = name_node.named_children if name_node.type == "array_pattern" else [name_node]
        init_arg = args[0] if is_call_to(value, "useState") else (args[1] if len(args) > 1 else None)
        init = text(init_arg) if init_arg is not None else None
        state_name = text(elements[0]) if elements else name
        facts["state_hints"].append({"name": state_name, "init": init, "type": guess_type(init)})
        if len(elements) > 1:
            facts["setters"][text(elements[1])] = state_name
        reactive.add(state_name)

    elif is_call_to(value, "useRef"):
        init = text(args[0]) if args else None
        facts["refs"].append({"name": name, "init": init})

    elif is_call_to(value, "useMemo"):
        fn = function_value(args[0]) if args else None
        deps = [text(d) for d in args[1].named_children] if len(args) > 1 and args[1].type == "array" else []
        facts["computed_hints"].append({"name": name, "expression": body_text(fn), "deps": deps})
        reactive.add(name)

    elif is_call_to(value, "useCallback"):
        fn = function_value(args[0]) if args else None
        facts["method_hints"].append(method(name, fn))

    elif function_value(value) is not None:
        facts["method_hints"].append(method(name, function_value(value)))

    elif value.type == "call_expression" and call_base_name(value).startswith("use"):
        facts["hook_calls"].append({"name": name, "call": text(value)})
        for n in (identifiers(name_node) if name_node.type != "identifier" else {name}):
            reactive.add(n)

    elif name_node.type == "identifier":
        deps = sorted(identifiers(value) & reactive)
        if deps:
            facts["computed_hints"].append({"name": name, "expression": text(value), "deps": deps})
            reactive.add(name)
        else:
            facts["constants"].append({"name": name, "init": text(value)})


# ── Class components ──────────────────────────────────────────────────────────

def _extract_class_component(cls: Node, facts: dict) -> None:
    body = field(cls, "body")
    facts["props"] = _member_props(cls, "this.props")

    for member in body.named_children if body is not None else []:
        if member.type == "method_definition":
            name = text(field(member, "name"))
            if name == "render":
                continue
            if name == "constructor":
                for assign in walk(member, {"assignment_expression"}):
                    if text(field(assign, "left")) == "this.state":
                        _class_state(field(assign, "right"), facts)
                continue
            if name in _CLASS_LIFECYCLE:
                facts["lifecycle_hints"].append(lifecycle(_CLASS_LIFECYCLE[name], body_text(member)))
            else:
                facts["method_hints"].append(method(name, member))

        elif member.type in ("field_definition", "public_field_definition"):
            name = text(field(member, "property") or field(member, "name"))
            value = unwrap(field(member, "value"))
            if name == "state":
                _class_state(value, facts)
            elif function_value(value) is not None:
                facts["method_hints"].append(method(name, function_value(value)))


def _class_state(obj: Node | None, facts: dict) -> None:
    for key, value, _ in object_entries(obj):
        init = text(value)
        facts["state_hints"].append({"name": key, "init": init, "type": guess_type(init)})


# ── Template (JSX) hints ──────────────────────────────────────────────────────

def _template_hints(scope: Node) -> dict:
    conditionals, loops, events = [], [], []

    for expr in walk(scope, {"jsx_expression"}):
        inner = unwrap(expr.named_children[0]) if expr.named_children else None
        if inner is None:
            continue
        if inner.type == "binary_expression" and text(field(inner, "operator")) == "&&" and contains_jsx(field(inner, "right")):
            conditionals.append(text(field(inner, "left")))
        elif inner.type == "ternary_expression" and (
            contains_jsx(field(inner, "consequence")) or contains_jsx(field(inner, "alternative"))
        ):
            conditionals.append(text(field(inner, "condition")))
        elif inner.type == "call_expression" and call_name(inner).endswith(".map"):
            args = call_args(inner)
            item = params(function_value(args[0]) if args else None)
            loops.append({
                "item":   item[0] if item else "",
                "source": text(field(field(inner, "function"), "object")),
            })

    for attr in walk(scope, {"jsx_attribute"}):
        name = text(attr.named_children[0]) if attr.named_children else ""
        if name.startswith("on") and name[2:3].isupper():
            events.append(name[2].lower() + name[3:])

    return {
        "conditionals": list(dict.fromkeys(conditionals)),
        "loops":        loops,
        "bindings":     [],
        "events":       list(dict.fromkeys(events)),
        "models":       [],
    }


# ── Entry ─────────────────────────────────────────────────────────────────────

def extract(code: str) -> dict:
    root = parse(code, "tsx")
    component, node = _find_component(root)

    facts = {
        "framework":       "React",
        "component":       component,
        "imports":         imports(root),
        "props":           [],
        "state_hints":     [],
        "lifecycle_hints": [],
        "computed_hints":  [],
        "method_hints":    [],
        "refs":            [],
        "constants":       [],
        "hook_calls":      [],
        "setters":         {},
        "is_createElement": any(call_name(c) == "React.createElement" for c in walk(root, {"call_expression"})),
        "script_block":    "\n\n".join(text(s) for s in root.named_children if s.type != "import_statement"),
        "parse_errors":    root.has_error,
    }

    if node is not None and node.type == "class_declaration":
        _extract_class_component(node, facts)
    elif node is not None:
        _extract_function_component(node, facts)

    # useRef values behave like non-rendering state; keep them visible to the IR.
    facts["state_hints"].extend(
        {"name": r["name"], "init": r["init"], "type": "ref"} for r in facts["refs"]
    )

    facts["template_hints"] = _template_hints(node if node is not None else root)
    facts["event_hints"] = facts["template_hints"]["events"]
    return facts
