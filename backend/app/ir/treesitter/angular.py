"""Angular component extractor (decorated class + inline template)."""

from __future__ import annotations

import re

from app.ir.treesitter.common import (
    Node, body_text, call_args, call_base_name, field, guess_type, html_all_attrs,
    imports, method, object_entries, parse, string_value, text, unwrap, walk, lifecycle,
)

_LIFECYCLE = {
    "ngOnInit":           "onMount",
    "ngOnDestroy":        "onDestroy",
    "ngAfterViewInit":    "onAfterViewInit",
    "ngAfterContentInit": "onAfterViewInit",
    "ngOnChanges":        "onChanges",
    "ngDoCheck":          "onUpdate",
}


# ── Class discovery ───────────────────────────────────────────────────────────

def _decorator_call(node: Node, name: str) -> Node | None:
    for dec in node.named_children:
        if dec.type != "decorator":
            continue
        call = unwrap(dec.named_children[0]) if dec.named_children else None
        if call is not None and call.type == "call_expression" and call_base_name(call) == name:
            return call
        if call is not None and text(call) == name:
            return call
    return None


def _find_component(root: Node) -> tuple[Node | None, Node | None]:
    """(class_declaration, @Component(...) call). Decorators sit on the export statement or the class."""
    fallback = None
    for stmt in root.named_children:
        cls = field(stmt, "declaration") if stmt.type == "export_statement" else stmt
        if cls is None or cls.type not in ("class_declaration", "abstract_class_declaration"):
            continue
        decorator = _decorator_call(stmt, "Component") or _decorator_call(cls, "Component")
        if decorator is not None:
            return cls, decorator
        fallback = fallback or cls
    return fallback, None


def _component_name(class_name: str) -> str:
    if class_name.endswith("Component") and class_name != "Component":
        return class_name[: -len("Component")]
    return class_name or "App"


# ── Decorator metadata ────────────────────────────────────────────────────────

def _metadata(decorator: Node | None) -> dict:
    args = call_args(decorator) if decorator is not None else []
    options = {key: value for key, value, _ in object_entries(args[0])} if args else {}

    styles = []
    style_node = unwrap(options.get("styles"))
    if style_node is not None:
        items = style_node.named_children if style_node.type == "array" else [style_node]
        styles = [string_value(s) or text(s)[1:-1] for s in items]

    template = options.get("template")
    return {
        "selector":     string_value(options.get("selector")),
        "template":     (string_value(template) or text(template)[1:-1]) if template is not None else "",
        "template_url": string_value(options.get("templateUrl")),
        "styles":       "\n\n".join(s.strip() for s in styles if s and s.strip()),
    }


# ── Class members ─────────────────────────────────────────────────────────────

def _is_getter(member: Node) -> bool:
    return any(c.type == "get" for c in member.children)


def _accessibility(member: Node) -> str:
    mod = next((c for c in member.named_children if c.type == "accessibility_modifier"), None)
    return text(mod) or "public"


def _type_of(member: Node) -> str:
    annotation = next((c for c in member.named_children if c.type == "type_annotation"), None)
    return text(annotation).lstrip(":").strip() if annotation is not None else ""


def _extract_members(cls: Node, template: str, facts: dict) -> None:
    body = field(cls, "body")
    template_words = set(re.findall(r"[A-Za-z_$][\w$]*", template))

    for member in body.named_children if body is not None else []:
        if member.type == "public_field_definition":
            _field(member, template_words, facts)
        elif member.type == "method_definition":
            _method(member, facts)


def _field(member: Node, template_words: set[str], facts: dict) -> None:
    name = text(field(member, "name") or field(member, "property"))
    value = unwrap(field(member, "value"))
    init = text(value) if value is not None else None
    type_ = _type_of(member) or guess_type(init)

    input_call = _decorator_call(member, "Input")
    if input_call is not None:
        args = call_args(input_call)
        required = "!" in text(member).split(":")[0] or (
            bool(args) and "required: true" in text(args[0])
        )
        facts["props"].append({"name": name, "type": type_, "required": required, "default": init})
        return
    if _decorator_call(member, "Output") is not None:
        facts["outputs"].append(name)
        return
    if _decorator_call(member, "ViewChild") is not None or _decorator_call(member, "ViewChildren") is not None:
        facts["view_children"].append(name)
        return

    entry = {"name": name, "init": init, "type": type_}
    if _accessibility(member) == "private" and name not in template_words:
        facts["variables"].append(entry)
    else:
        facts["state_hints"].append(entry)


def _method(member: Node, facts: dict) -> None:
    name = text(field(member, "name"))
    if name == "constructor":
        for param in walk(field(member, "parameters"), {"required_parameter", "optional_parameter"}):
            if any(c.type == "accessibility_modifier" for c in param.named_children):
                annotation = next((c for c in param.named_children if c.type == "type_annotation"), None)
                facts["injected_services"].append({
                    "name": text(field(param, "pattern")),
                    "type": text(annotation).lstrip(":").strip(),
                })
        return
    if _is_getter(member):
        facts["computed_hints"].append({"name": name, "expression": body_text(member), "deps": []})
    elif name in _LIFECYCLE:
        facts["lifecycle_hints"].append(lifecycle(_LIFECYCLE[name], body_text(member)))
    else:
        facts["method_hints"].append(method(name, member))


# ── Template ──────────────────────────────────────────────────────────────────

def template_hints(template: str) -> dict:
    attrs = html_all_attrs(parse(template, "html")) if template else []
    hints = {"conditionals": [], "loops": [], "bindings": [], "events": [], "models": []}

    for _, name, value in attrs:
        value = value or ""
        if name == "*ngIf":
            hints["conditionals"].append(value.split(";")[0].strip())
        elif name == "*ngFor":
            match = re.match(r"\s*let\s+(\w+)\s+of\s+([^;]+)", value)
            if match:
                hints["loops"].append({"item": match.group(1), "source": match.group(2).strip()})
        elif name == "[(ngModel)]":
            hints["models"].append(value)
        elif name.startswith("(") and name.endswith(")"):
            hints["events"].append(name[1:-1])
        elif name.startswith("[") and name.endswith("]"):
            hints["bindings"].append(name[1:-1])

    for match in re.finditer(r"@(if|for)\s*\(([^)]*)\)", template):
        key = "conditionals" if match.group(1) == "if" else "loops"
        hints[key].append(match.group(2).strip() if key == "conditionals" else {"item": "", "source": match.group(2).strip()})

    return {k: (list(dict.fromkeys(v)) if k != "loops" else v) for k, v in hints.items()}


# ── Entry ─────────────────────────────────────────────────────────────────────

def extract(code: str) -> dict:
    root = parse(code, "typescript")
    cls, decorator = _find_component(root)
    meta = _metadata(decorator)

    facts = {
        "framework":         "Angular",
        "component":         _component_name(text(field(cls, "name"))) if cls is not None else "App",
        "selector":          meta["selector"],
        "template_url":      meta["template_url"],
        "imports":           imports(root),
        "props":             [],
        "outputs":           [],
        "view_children":     [],
        "injected_services": [],
        "state_hints":       [],
        "variables":         [],
        "lifecycle_hints":   [],
        "computed_hints":    [],
        "method_hints":      [],
        "subscription_hints": [
            text(call) for call in walk(root, {"call_expression"}) if call_base_name(call) == "subscribe"
        ],
        "script_block":      "\n\n".join(text(s) for s in root.named_children if s.type != "import_statement"),
        "styles":            meta["styles"],
        "parse_errors":      root.has_error,
    }

    if cls is not None:
        _extract_members(cls, meta["template"], facts)

    facts["template_hints"] = template_hints(meta["template"])
    facts["event_hints"] = facts["template_hints"]["events"]
    return facts
