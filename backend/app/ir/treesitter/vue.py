"""Vue SFC extractor (<script setup> Composition API and Options API)."""

from __future__ import annotations

from app.ir.treesitter.common import (
    Node, body_text, call_args, call_base_name, field, function_value, guess_type,
    html_all_attrs, html_attrs, html_raw_text, html_tag, identifiers, imports, is_call_to,
    lifecycle, method, object_entries, parse, string_value, text, unwrap, walk,
)

_SETUP_LIFECYCLE = {
    "onMounted":       "onMount",
    "onUnmounted":     "onDestroy",
    "onBeforeMount":   "onBeforeMount",
    "onBeforeUnmount": "onBeforeDestroy",
    "onUpdated":       "onUpdate",
    "onBeforeUpdate":  "onBeforeUpdate",
}

_OPTIONS_LIFECYCLE = {
    "created":       "onCreate",
    "beforeMount":   "onBeforeMount",
    "mounted":       "onMount",
    "beforeUpdate":  "onBeforeUpdate",
    "updated":       "onUpdate",
    "beforeUnmount": "onBeforeDestroy",
    "beforeDestroy": "onBeforeDestroy",
    "unmounted":     "onDestroy",
    "destroyed":     "onDestroy",
}

_STATE_CALLS = ("ref", "shallowRef", "reactive", "shallowReactive")


# ── SFC blocks ────────────────────────────────────────────────────────────────

def split_sfc(code: str) -> dict:
    root = parse(code, "html")
    blocks = {"template": "", "script": "", "style": "", "is_setup": False, "lang": "js", "is_sfc": False}

    for node in root.named_children:
        tag = html_tag(node) if node.type in ("element", "script_element", "style_element") else ""
        if tag == "template" and not blocks["is_sfc"]:
            inner = text(node)
            blocks["template"] = inner[inner.find(">") + 1: inner.rfind("</")].strip()
            blocks["is_sfc"] = True
        elif tag == "script":
            attrs = dict(html_attrs(node))
            is_setup = "setup" in attrs
            if is_setup or not blocks["script"]:
                blocks["script"] = html_raw_text(node).strip()
                blocks["is_setup"] = is_setup
                blocks["lang"] = "ts" if attrs.get("lang") in ("ts", "tsx") else "js"
        elif tag == "style":
            blocks["style"] = "\n\n".join(filter(None, [blocks["style"], html_raw_text(node).strip()]))

    if not blocks["is_sfc"] and not blocks["script"]:
        blocks["script"] = code
    return blocks


# ── Props ─────────────────────────────────────────────────────────────────────

def _props_from_definition(arg: Node | None) -> list[dict]:
    arg = unwrap(arg)
    if arg is None:
        return []

    if arg.type == "array":
        return [
            {"name": string_value(item) or text(item), "type": "any", "required": False, "default": None}
            for item in arg.named_children
        ]

    props = []
    for key, value, _ in object_entries(arg):
        value = unwrap(value)
        prop = {"name": key, "type": "any", "required": False, "default": None}
        if value is not None and value.type == "object":
            options = {k: v for k, v, _ in object_entries(value)}
            prop["type"] = text(options.get("type")) or "any"
            prop["required"] = text(options.get("required")) == "true"
            if "default" in options:
                prop["default"] = text(options["default"])
        elif value is not None:
            prop["type"] = text(value)
        props.append(prop)
    return props


def _props_from_type(call: Node) -> list[dict]:
    """defineProps<{ label: string; limit?: number }>()"""
    type_args = field(call, "type_arguments")
    props = []
    for sig in walk(type_args, {"property_signature"}) if type_args is not None else []:
        type_node = field(sig, "type")
        props.append({
            "name":     text(field(sig, "name")),
            "type":     text(type_node)[1:].strip() if type_node is not None else "any",
            "required": "?" not in text(sig).split(":")[0],
            "default":  None,
        })
    return props


def _define_props(value: Node) -> tuple[list[dict], dict]:
    """Handles defineProps(...) and withDefaults(defineProps<...>(), {...})."""
    defaults = {}
    call = value
    if is_call_to(value, "withDefaults"):
        args = call_args(value)
        call = unwrap(args[0]) if args else value
        if len(args) > 1:
            defaults = {k: text(v) for k, v, _ in object_entries(args[1])}

    args = call_args(call)
    props = _props_from_definition(args[0]) if args else _props_from_type(call)
    for prop in props:
        if prop["name"] in defaults:
            prop["default"] = defaults[prop["name"]]
            prop["required"] = False
    return props, defaults


# ── <script setup> ────────────────────────────────────────────────────────────

def _extract_setup(root: Node, facts: dict) -> None:
    reactive: set[str] = set()

    for stmt in root.named_children:
        if stmt.type in ("lexical_declaration", "variable_declaration"):
            for decl in stmt.named_children:
                if decl.type == "variable_declarator":
                    _setup_declarator(decl, facts, reactive)

        elif stmt.type == "function_declaration":
            facts["method_hints"].append(method(text(field(stmt, "name")), stmt))

        elif stmt.type == "expression_statement":
            expr = unwrap(stmt.named_children[0]) if stmt.named_children else None
            if expr is None or expr.type != "call_expression":
                continue
            name = call_base_name(expr)
            args = call_args(expr)
            if name in _SETUP_LIFECYCLE:
                fn = function_value(args[0]) if args else None
                facts["lifecycle_hints"].append(lifecycle(_SETUP_LIFECYCLE[name], body_text(fn)))
            elif name in ("defineProps", "withDefaults"):
                facts["props"], _ = _define_props(expr)
            elif name in ("watch", "watchEffect"):
                facts["watchers"].append(text(expr))
            elif name == "defineOptions" and args:
                options = {k: v for k, v, _ in object_entries(args[0])}
                facts["component"] = string_value(options.get("name")) or facts["component"]


def _setup_declarator(decl: Node, facts: dict, reactive: set[str]) -> None:
    name_node = field(decl, "name")
    value = unwrap(field(decl, "value"))
    if name_node is None:
        return
    name = text(name_node)
    if value is None:
        facts["variables"].append({"name": name, "init": None})
        return
    args = call_args(value) if value.type == "call_expression" else []

    if is_call_to(value, "defineProps", "withDefaults"):
        facts["props"], _ = _define_props(value)
        facts["props_object"] = name
        reactive.update(p["name"] for p in facts["props"])
    elif is_call_to(value, "defineEmits"):
        facts["emits"] = [string_value(a) or text(a) for a in (args[0].named_children if args and args[0].type == "array" else [])]
    elif is_call_to(value, *_STATE_CALLS):
        init = text(args[0]) if args else None
        facts["state_hints"].append({"name": name, "init": init, "type": guess_type(init)})
        reactive.add(name)
    elif is_call_to(value, "computed"):
        arg = unwrap(args[0]) if args else None
        fn = function_value(arg)
        if fn is None and arg is not None and arg.type == "object":
            getter = {k: v for k, v, _ in object_entries(arg)}.get("get")
            fn = function_value(getter) or getter
        expression = body_text(fn)
        facts["computed_hints"].append({
            "name": name, "expression": expression,
            "deps": sorted(identifiers(fn) & reactive),
        })
        reactive.add(name)
    elif function_value(value) is not None:
        facts["method_hints"].append(method(name, function_value(value)))
    else:
        facts["variables"].append({"name": name, "init": text(value)})


# ── Options API ───────────────────────────────────────────────────────────────

def _options_object(root: Node) -> Node | None:
    for stmt in root.named_children:
        if stmt.type != "export_statement":
            continue
        value = unwrap(field(stmt, "value") or field(stmt, "declaration"))
        if value is not None and value.type == "call_expression" and call_base_name(value) == "defineComponent":
            args = call_args(value)
            value = unwrap(args[0]) if args else None
        if value is not None and value.type == "object":
            return value
    return None


def _returned_object(fn: Node | None) -> Node | None:
    if fn is None:
        return None
    for ret in walk(fn, {"return_statement"}):
        value = unwrap(ret.named_children[0]) if ret.named_children else None
        if value is not None and value.type == "object":
            return value
    body = field(fn, "body")
    body = unwrap(body)
    return body if body is not None and body.type == "object" else None


def _as_function(value: Node | None) -> Node | None:
    """Options entries can be `name() {}`, `name: function () {}`, or `name: () => {}`."""
    if value is None:
        return None
    if value.type == "method_definition":
        return value
    return function_value(value)


def _extract_options(root: Node, facts: dict) -> None:
    options = _options_object(root)
    if options is None:
        return

    for key, value, _ in object_entries(options):
        if key == "name":
            facts["component"] = string_value(value) or facts["component"]
        elif key == "props":
            facts["props"] = _props_from_definition(value)
        elif key == "data":
            for name, init, _ in object_entries(_returned_object(_as_function(value))):
                facts["state_hints"].append({"name": name, "init": text(init), "type": guess_type(text(init))})
        elif key == "computed":
            for name, entry, _ in object_entries(value):
                fn = _as_function(entry)
                if fn is None and unwrap(entry) is not None and unwrap(entry).type == "object":
                    fn = _as_function({k: v for k, v, _ in object_entries(entry)}.get("get"))
                facts["computed_hints"].append({"name": name, "expression": body_text(fn), "deps": []})
        elif key == "methods":
            for name, entry, _ in object_entries(value):
                facts["method_hints"].append(method(name, _as_function(entry)))
        elif key in _OPTIONS_LIFECYCLE:
            facts["lifecycle_hints"].append(lifecycle(_OPTIONS_LIFECYCLE[key], body_text(_as_function(value))))
        elif key == "watch":
            facts["watchers"].append(text(value))
        elif key == "emits":
            facts["emits"] = [string_value(a) or text(a) for a in (unwrap(value).named_children if unwrap(value) is not None else [])]


# ── Template ──────────────────────────────────────────────────────────────────

def template_hints(template: str) -> dict:
    attrs = html_all_attrs(parse(template, "html")) if template else []
    hints = {"conditionals": [], "loops": [], "bindings": [], "events": [], "models": [], "slots": [], "refs": []}

    for tag, name, value in attrs:
        value = value or ""
        if name in ("v-if", "v-else-if", "v-show"):
            hints["conditionals"].append(value)
        elif name == "v-for":
            item, _, source = value.partition(" in ")
            if not source:
                item, _, source = value.partition(" of ")
            hints["loops"].append({"item": item.strip("() ").split(",")[0].strip(), "source": source.strip()})
        elif name.startswith("@") or name.startswith("v-on:"):
            hints["events"].append(name.split(":", 1)[-1].lstrip("@").split(".")[0])
        elif name.startswith(":") or name.startswith("v-bind:"):
            hints["bindings"].append(name.split(":", 1)[-1].lstrip(":"))
        elif name.startswith("v-model"):
            hints["models"].append(value)
        elif name == "ref":
            hints["refs"].append(value)
        elif tag == "slot" and name == "name":
            hints["slots"].append(value)

    return {k: (list(dict.fromkeys(v)) if k != "loops" else v) for k, v in hints.items()}


# ── Entry ─────────────────────────────────────────────────────────────────────

def extract(code: str) -> dict:
    blocks = split_sfc(code)
    root = parse(blocks["script"], "typescript" if blocks["lang"] == "ts" else "javascript")

    facts = {
        "framework":       "Vue",
        "component":       "App",
        "imports":         imports(root),
        "props":           [],
        "state_hints":     [],
        "lifecycle_hints": [],
        "computed_hints":  [],
        "method_hints":    [],
        "variables":       [],
        "watchers":        [],
        "emits":           [],
        "is_setup":        blocks["is_setup"],
        "is_sfc":          blocks["is_sfc"],
        "script_block":    blocks["script"],
        "styles":          blocks["style"],
        "parse_errors":    root.has_error,
    }

    if blocks["is_setup"]:
        _extract_setup(root, facts)
    else:
        _extract_options(root, facts)

    facts["template_hints"] = template_hints(blocks["template"])
    facts["event_hints"] = facts["template_hints"]["events"]
    return facts
