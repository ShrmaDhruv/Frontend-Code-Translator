import re
from typing import Optional


# ── SFC block splitting ───────────────────────────────────────────────────────

def split_sfc(code: str) -> dict:
    template_m = re.search(r'<template>([\s\S]*?)</template>', code)
    script_setup_m = re.search(
        r'<script\s+setup(?:\s+lang=["\']ts["\'])?\s*>([\s\S]*?)</script>',
        code,
    )
    script_m = re.search(
        r'<script(?:\s+lang=["\']ts["\'])?\s*>([\s\S]*?)</script>',
        code,
    ) if not script_setup_m else None
    style_m  = re.search(r'<style[^>]*>([\s\S]*?)</style>', code)

    return {
        "template":     template_m.group(1).strip()      if template_m     else "",
        "script":       script_setup_m.group(1).strip()  if script_setup_m
                        else (script_m.group(1).strip()  if script_m       else code),
        "style":        style_m.group(1).strip()         if style_m        else "",
        "is_setup":     script_setup_m is not None,
        "is_sfc":       template_m is not None,
    }


# ── Options API extraction (Vue 2 / Vue 3 Options) ────────────────────────────

def extract_options_state(script: str) -> list[dict]:
    state = []
    data_m = re.search(r'data\s*\(\s*\)\s*\{[^}]*return\s*\{([\s\S]*?)\}', script)
    if data_m:
        body = data_m.group(1)
        for m in re.finditer(r'(\w+)\s*:\s*([^,\n]+)', body):
            state.append({ "name": m.group(1), "init": m.group(2).strip() })
    return state


def extract_options_computed(script: str) -> list[dict]:
    computed = []
    block_m = re.search(r'computed\s*:\s*\{([\s\S]*?)\n\s*\}', script)
    if block_m:
        body = block_m.group(1)
        for m in re.finditer(r'(\w+)\s*(?:\([^)]*\)|:\s*(?:function\s*)?\()', body):
            computed.append({ "name": m.group(1), "expression": "" })
    return computed


def extract_options_methods(script: str) -> list[str]:
    methods = []
    block_m = re.search(r'methods\s*:\s*\{([\s\S]*?)\n\s*\}', script)
    if block_m:
        body = block_m.group(1)
        for m in re.finditer(r'(\w+)\s*(?:async\s*)?\(', body):
            name = m.group(1)
            if name not in ("function",):
                methods.append(name)
    return list(dict.fromkeys(methods))


def extract_options_props(script: str) -> list[dict]:
    props = []

    array_m = re.search(r'props\s*:\s*\[([^\]]+)\]', script)
    if array_m:
        for p in array_m.group(1).split(","):
            p = p.strip().strip("'\"")
            if p:
                props.append({ "name": p, "type": "any", "required": False })
        return props

    obj_m = re.search(r'props\s*:\s*\{([\s\S]*?)\n\s*\}', script)
    if obj_m:
        body = obj_m.group(1)
        for m in re.finditer(r'(\w+)\s*:\s*\{([^}]*)\}', body):
            name     = m.group(1)
            detail   = m.group(2)
            type_m   = re.search(r'type\s*:\s*(\w+)', detail)
            req_m    = re.search(r'required\s*:\s*(true|false)', detail)
            props.append({
                "name":     name,
                "type":     type_m.group(1) if type_m else "any",
                "required": req_m.group(1) == "true" if req_m else False,
            })

    return props


def extract_options_lifecycle(script: str) -> list[dict]:
    hooks = {
        "created":        "onCreate",
        "mounted":        "onMount",
        "beforeMount":    "onBeforeMount",
        "updated":        "onUpdate",
        "beforeUpdate":   "onBeforeUpdate",
        "beforeDestroy":  "onDestroy",
        "unmounted":      "onDestroy",
        "beforeUnmount":  "onBeforeDestroy",
    }
    lifecycle = []
    for vue_hook, ir_hook in hooks.items():
        if re.search(rf'\b{vue_hook}\s*\(', script):
            lifecycle.append({ "hook": ir_hook })
    return lifecycle


# ── Composition API extraction (Vue 3 <script setup>) ─────────────────────────

def extract_setup_state(script: str) -> list[dict]:
    state = []

    for m in re.finditer(r'const\s+(\w+)\s*=\s*ref\(([^)]*)\)', script):
        state.append({ "name": m.group(1), "init": m.group(2).strip() })

    for m in re.finditer(r'const\s+(\w+)\s*=\s*reactive\(', script):
        state.append({ "name": m.group(1), "init": "{}" })

    return state


def extract_setup_computed(script: str) -> list[dict]:
    computed = []
    for m in re.finditer(
        r'const\s+(\w+)\s*=\s*computed\s*\(\s*(?:\(\s*\)\s*=>|function\s*\(\s*\))\s*([^)]+)',
        script,
    ):
        computed.append({ "name": m.group(1), "expression": m.group(2).strip() })
    return computed


def extract_setup_props(script: str) -> list[dict]:
    props = []

    array_m = re.search(r'defineProps\s*\(\s*\[([^\]]+)\]', script)
    if array_m:
        for p in array_m.group(1).split(","):
            p = p.strip().strip("'\"")
            if p:
                props.append({ "name": p, "type": "any", "required": False })
        return props

    obj_m = re.search(r'defineProps\s*\(\s*\{([\s\S]*?)\}\s*\)', script)
    if obj_m:
        body = obj_m.group(1)
        for m in re.finditer(r'(\w+)\s*:\s*\{([^}]*)\}', body):
            name   = m.group(1)
            detail = m.group(2)
            type_m = re.search(r'type\s*:\s*(\w+)', detail)
            req_m  = re.search(r'required\s*:\s*(true|false)', detail)
            props.append({
                "name":     name,
                "type":     type_m.group(1) if type_m else "any",
                "required": req_m.group(1) == "true" if req_m else False,
            })

    return props


def extract_setup_lifecycle(script: str) -> list[dict]:
    hooks = {
        "onMounted":       "onMount",
        "onUnmounted":     "onDestroy",
        "onBeforeMount":   "onBeforeMount",
        "onBeforeUnmount": "onBeforeDestroy",
        "onUpdated":       "onUpdate",
        "onBeforeUpdate":  "onBeforeUpdate",
        "onCreated":       "onCreate",
    }
    lifecycle = []
    for vue_hook, ir_hook in hooks.items():
        if re.search(rf'\b{vue_hook}\s*\(', script):
            lifecycle.append({ "hook": ir_hook })
    return lifecycle


def extract_setup_methods(script: str) -> list[str]:
    methods = []
    for m in re.finditer(
        r'(?:const|function)\s+(\w+)\s*=?\s*(?:async\s*)?\([^)]*\)\s*(?:=>|\{)',
        script,
    ):
        name = m.group(1)
        if not name.startswith("on") or name[2:3].islower():
            methods.append(name)
    return list(dict.fromkeys(methods))


# ── Template analysis ─────────────────────────────────────────────────────────

def extract_template_hints(template: str) -> dict:
    conditionals = re.findall(r'v-if\s*=\s*["\']([^"\']+)["\']', template)
    loops        = re.findall(r'v-for\s*=\s*["\'](\w+)\s+in\s+(\w+)["\']', template)
    bindings     = re.findall(r'(?:v-bind:|:)(\w+)\s*=', template)
    events       = re.findall(r'(?:v-on:|@)(\w+)\s*=', template)
    models       = re.findall(r'v-model(?:\.[\w.]+)?\s*=\s*["\'](\w+)["\']', template)
    slots        = re.findall(r'<slot(?:\s+name=["\'](\w+)["\'])?', template)
    refs         = re.findall(r'ref\s*=\s*["\'](\w+)["\']', template)

    return {
        "conditionals": list(dict.fromkeys(conditionals)),
        "loops":        [{"item": l[0], "source": l[1]} for l in loops],
        "bindings":     list(dict.fromkeys(bindings)),
        "events":       list(dict.fromkeys(events)),
        "models":       list(dict.fromkeys(models)),
        "slots":        [s for s in slots if s],
        "refs":         list(dict.fromkeys(refs)),
    }


# ── Main entry ────────────────────────────────────────────────────────────────

def extract(code: str) -> dict:
    blocks   = split_sfc(code)
    script   = blocks["script"]
    template = blocks["template"]

    component_m = re.search(r'name\s*:\s*["\'](\w+)["\']', script)
    component   = component_m.group(1) if component_m else "App"

    if blocks["is_setup"]:
        state_hints     = extract_setup_state(script)
        computed_hints  = extract_setup_computed(script)
        props           = extract_setup_props(script)
        lifecycle_hints = extract_setup_lifecycle(script)
        method_hints    = extract_setup_methods(script)
    else:
        state_hints     = extract_options_state(script)
        computed_hints  = extract_options_computed(script)
        props           = extract_options_props(script)
        lifecycle_hints = extract_options_lifecycle(script)
        method_hints    = extract_options_methods(script)

    return {
        "framework":        "Vue",
        "component":        component,
        "imports":          [],
        "props":            props,
        "state_hints":      state_hints,
        "lifecycle_hints":  lifecycle_hints,
        "computed_hints":   computed_hints,
        "method_hints":     method_hints,
        "event_hints":      extract_template_hints(template).get("events", []),
        "is_setup":         blocks["is_setup"],
        "is_sfc":           blocks["is_sfc"],
        "script_block":     script,
        "template_hints":   extract_template_hints(template),
        "styles":           blocks["style"],
    }