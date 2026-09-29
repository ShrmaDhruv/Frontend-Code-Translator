"""Plain HTML + inline <script> extractor."""

from __future__ import annotations

import re

from app.ast_layer.treesitter.common import (
    Node, body_text, call_args, call_base_name, call_name, field, function_value, guess_type,
    html_all_attrs, html_attrs, html_elements, html_tag, html_inner_text, html_raw_text, method, parse,
    string_value, text, unwrap, walk, lifecycle,
)

_MOUNT_EVENTS   = {"DOMContentLoaded", "load"}
_DESTROY_EVENTS = {"beforeunload", "unload", "pagehide"}
_TIMER_CALLS    = {"setInterval", "setTimeout", "requestAnimationFrame"}
_DOM_QUERIES    = {
    "getElementById", "querySelector", "querySelectorAll",
    "getElementsByClassName", "getElementsByTagName", "getElementsByName",
}
_DOM_WRITES     = {"innerHTML", "innerText", "textContent", "hidden", "value", "checked", "className"}
_DOM_CALLS      = {"appendChild", "removeChild", "replaceChildren", "append", "prepend", "remove",
                   "setAttribute", "createElement", "add", "toggle"}


# ── Document ──────────────────────────────────────────────────────────────────

def split_document(code: str) -> dict:
    root = parse(code, "html")
    scripts, external = [], []
    for element in html_elements(root, "script"):
        attrs = dict(html_attrs(element))
        if attrs.get("src"):
            external.append(attrs["src"])
        elif attrs.get("type", "text/javascript") in ("text/javascript", "module", "application/javascript"):
            body = html_raw_text(element).strip()
            if body:
                scripts.append(body)

    styles = [html_raw_text(e).strip() for e in html_elements(root, "style")]
    titles = html_elements(root, "title")
    markup = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", "", code, flags=re.IGNORECASE).strip()

    return {
        "root":             root,
        "scripts":          scripts,
        "merged_script":    "\n\n".join(scripts),
        "styles":           "\n\n".join(s for s in styles if s),
        "markup":           markup,
        "title":            html_inner_text(titles[0]) if titles else "",
        "external_scripts": external,
    }


def _markup_facts(root: Node) -> dict:
    ids, classes, inline_events, form_elements = [], [], [], []
    for tag, name, value in html_all_attrs(root):
        name_l = name.lower()
        if name_l == "id" and value:
            ids.append(value)
        elif name_l == "class" and value:
            classes.extend(value.split())
        elif name_l.startswith("on") and value is not None:
            inline_events.append({"event": name_l[2:], "handler": value.strip()})

    for element in walk(root, {"element"}):
        if (tag := html_tag(element)) in ("input", "select", "textarea"):
            attrs = dict(html_attrs(element))
            if attrs.get("name") or attrs.get("id"):
                form_elements.append({
                    "name": attrs.get("name") or attrs.get("id"),
                    "type": attrs.get("type", "text") if tag == "input" else tag,
                })

    return {
        "element_ids":     list(dict.fromkeys(ids)),
        "element_classes": list(dict.fromkeys(classes)),
        "inline_events":   inline_events,
        "form_elements":   form_elements,
    }


# ── Script ────────────────────────────────────────────────────────────────────

def _listener(call: Node) -> tuple[str, str, Node | None]:
    """(target, event, handler) for `target.addEventListener('event', handler)`."""
    target = text(field(field(call, "function"), "object")) or "document"
    args = call_args(call)
    event = string_value(args[0]) if args else ""
    return target, event or "", (args[1] if len(args) > 1 else None)


def _handler_body(handler: Node | None) -> str:
    fn = function_value(handler)
    if fn is not None:
        return body_text(fn)
    return f"{text(handler)}()" if handler is not None else ""


def _timer_handles(root: Node) -> set[str]:
    handles = set()
    for node in walk(root, {"assignment_expression", "variable_declarator"}):
        target = field(node, "left") or field(node, "name")
        value = unwrap(field(node, "right") or field(node, "value"))
        if value is not None and value.type == "call_expression" and call_base_name(value) in _TIMER_CALLS:
            handles.add(text(target))
    return handles


def _script_facts(script: str) -> dict:
    root = parse(script, "javascript")
    timer_handles = _timer_handles(root)
    facts = {
        "state_hints": [], "variables": [], "constants": [], "method_hints": [],
        "lifecycle_hints": [], "event_listeners": [], "dom_queries": [], "dom_mutations": [],
        "fetch_hints": [], "storage_hints": [], "parse_errors": root.has_error,
    }
    mount_bodies = []

    for stmt in root.named_children:
        if stmt.type in ("lexical_declaration", "variable_declaration"):
            is_const = text(stmt).startswith("const")
            for decl in stmt.named_children:
                if decl.type != "variable_declarator":
                    continue
                name = text(field(decl, "name"))
                value = unwrap(field(decl, "value"))
                init = text(value) if value is not None else None
                fn = function_value(value)
                if fn is not None:
                    facts["method_hints"].append(method(name, fn))
                elif name in timer_handles:
                    facts["variables"].append({"name": name, "init": init})
                elif not is_const or (value is not None and value.type in ("array", "object")):
                    facts["state_hints"].append({"name": name, "init": init, "type": guess_type(init)})
                else:
                    facts["constants"].append({"name": name, "init": init})

        elif stmt.type == "function_declaration":
            facts["method_hints"].append(method(text(field(stmt, "name")), stmt))

        elif stmt.type == "expression_statement":
            expr = unwrap(stmt.named_children[0]) if stmt.named_children else None
            if expr is None:
                continue
            if expr.type == "call_expression" and call_base_name(expr) == "addEventListener":
                target, event, handler = _listener(expr)
                if target in ("document", "window") and event in _MOUNT_EVENTS:
                    mount_bodies.append(_handler_body(handler))
                    continue
                if target == "window" and event in _DESTROY_EVENTS:
                    facts["lifecycle_hints"].append(lifecycle("onDestroy", _handler_body(handler)))
                    continue
            if expr.type == "assignment_expression" and text(field(expr, "left")) in ("window.onload", "document.onload"):
                mount_bodies.append(_handler_body(field(expr, "right")))
                continue
            # Any other top-level statement runs when the script loads.
            mount_bodies.append(text(stmt))

    if mount_bodies:
        facts["lifecycle_hints"].insert(0, lifecycle("onMount", "\n".join(b for b in mount_bodies if b)))

    for call in walk(root, {"call_expression"}):
        name = call_base_name(call)
        args = call_args(call)
        if name == "addEventListener":
            target, event, _ = _listener(call)
            facts["event_listeners"].append({"target": target, "event": event})
        elif name in _DOM_QUERIES and args:
            facts["dom_queries"].append({"method": name, "selector": string_value(args[0]) or text(args[0])})
        elif name in _DOM_CALLS and "." in call_name(call):
            facts["dom_mutations"].append(f".{name}()")
        elif name == "fetch":
            facts["fetch_hints"].append({"type": "fetch", "url": string_value(args[0]) if args else None})
        if call_name(call).startswith(("localStorage.", "sessionStorage.")):
            facts["storage_hints"].append(call_name(call).split(".")[0])

    for assign in walk(root, {"assignment_expression"}):
        left = field(assign, "left")
        if left is not None and left.type == "member_expression" and text(field(left, "property")) in _DOM_WRITES:
            facts["dom_mutations"].append(f".{text(field(left, 'property'))}=")

    if any(text(field(n, "constructor")) == "XMLHttpRequest" for n in walk(root, {"new_expression"})):
        facts["fetch_hints"].append({"type": "xhr"})

    facts["dom_mutations"] = list(dict.fromkeys(facts["dom_mutations"]))
    facts["storage_hints"] = list(dict.fromkeys(facts["storage_hints"]))
    return facts


# ── Entry ─────────────────────────────────────────────────────────────────────

def extract(code: str) -> dict:
    doc = split_document(code)
    markup = _markup_facts(doc["root"])
    script = _script_facts(doc["merged_script"]) if doc["merged_script"] else _script_facts("")

    event_hints = list(dict.fromkeys(
        [e["event"] for e in markup["inline_events"]]
        + [e["event"] for e in script["event_listeners"] if e["event"] not in _MOUNT_EVENTS | _DESTROY_EVENTS]
    ))

    return {
        "framework":        "HTML",
        "component":        re.sub(r"\s+", "", doc["title"]) or "App",
        "title":            doc["title"],
        "imports":          [],
        "props":            [],
        "state_hints":      script["state_hints"],
        "variables":        script["variables"],
        "constants":        script["constants"],
        "lifecycle_hints":  script["lifecycle_hints"],
        "computed_hints":   [],
        "method_hints":     script["method_hints"],
        "event_hints":      event_hints,
        "inline_events":    markup["inline_events"],
        "event_listeners":  script["event_listeners"],
        "dom_queries":      script["dom_queries"],
        "dom_mutations":    script["dom_mutations"],
        "fetch_hints":      script["fetch_hints"],
        "storage_hints":    script["storage_hints"],
        "form_elements":    markup["form_elements"],
        "element_ids":      markup["element_ids"],
        "element_classes":  markup["element_classes"],
        "external_scripts": doc["external_scripts"],
        "script_block":     doc["merged_script"],
        "styles":           doc["styles"],
        "parse_errors":     script["parse_errors"],
        "template_hints": {
            "conditionals": [],
            "loops":        [],
            "bindings":     [],
            "events":       event_hints,
            "models":       [f["name"] for f in markup["form_elements"]],
        },
    }
