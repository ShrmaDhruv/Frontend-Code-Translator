import re
from typing import Optional


# ── Imports ───────────────────────────────────────────────────────────────────

def extract_imports(code: str) -> list[dict]:
    imports = []
    for m in re.finditer(
        r'import\s+\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']',
        code,
    ):
        specifiers = [s.strip() for s in m.group(1).split(",") if s.strip()]
        imports.append({ "source": m.group(2), "specifiers": specifiers })
    return imports


# ── Component name ────────────────────────────────────────────────────────────

def extract_component_name(code: str) -> str:
    m = re.search(r'export\s+class\s+(\w+)(?:Component)?', code)
    if m:
        return m.group(1)
    m = re.search(r'class\s+(\w+)', code)
    return m.group(1) if m else "App"


# ── Selector ──────────────────────────────────────────────────────────────────

def extract_selector(code: str) -> Optional[str]:
    m = re.search(r'selector\s*:\s*["\']([^"\']+)["\']', code)
    return m.group(1) if m else None


# ── Props (@Input) ────────────────────────────────────────────────────────────

def extract_props(code: str) -> list[dict]:
    props = []
    for m in re.finditer(
        r'@Input\s*\(\s*\)\s+(?:(?:public|private|protected|readonly)\s+)?(\w+)(?:\s*:\s*(\w+))?',
        code,
    ):
        props.append({
            "name":     m.group(1),
            "type":     m.group(2) if m.group(2) else "any",
            "required": False,
        })
    return props


# ── Outputs (@Output / EventEmitter) ─────────────────────────────────────────

def extract_outputs(code: str) -> list[str]:
    outputs = []
    for m in re.finditer(
        r'@Output\s*\(\s*\)\s+(?:(?:public|private|protected|readonly)\s+)?(\w+)',
        code,
    ):
        outputs.append(m.group(1))
    return outputs


# ── Constructor injection ─────────────────────────────────────────────────────

def extract_injected_services(code: str) -> list[dict]:
    services  = []
    ctor_m    = re.search(r'constructor\s*\(([\s\S]*?)\)\s*\{', code)
    if not ctor_m:
        return services

    params = ctor_m.group(1)
    for m in re.finditer(
        r'(?:private|public|protected|readonly)\s+(\w+)\s*:\s*(\w+)',
        params,
    ):
        services.append({ "name": m.group(1), "type": m.group(2) })
    return services


# ── Class fields (state) ──────────────────────────────────────────────────────

def extract_state_hints(code: str) -> list[dict]:
    state     = []
    ctor_m    = re.search(r'constructor\s*\([\s\S]*?\)\s*\{', code)
    ctor_start = ctor_m.end() if ctor_m else len(code)

    class_body_m = re.search(r'class\s+\w+[^{]*\{', code)
    class_start  = class_body_m.end() if class_body_m else 0

    class_header = code[class_start:ctor_start] if class_body_m else ""

    for m in re.finditer(
        r'(?:^|\n)\s+(?:(?:public|private|protected|readonly)\s+)?(\w+)(?:\s*:\s*(\w+(?:\[\])?))?'
        r'\s*=\s*([^;\n]+)',
        class_header,
    ):
        name = m.group(1)
        if name in ("constructor",) or name.startswith("@"):
            continue
        state.append({
            "name": name,
            "type": m.group(2) if m.group(2) else "any",
            "init": m.group(3).strip(),
        })

    uninitialized = re.finditer(
        r'(?:^|\n)\s+(?:(?:public|private|protected|readonly)\s+)?(\w+)\s*:\s*(\w+(?:\[\])?)\s*;',
        class_header,
    )
    for m in uninitialized:
        name = m.group(1)
        if not any(s["name"] == name for s in state):
            state.append({ "name": name, "type": m.group(2), "init": None })

    return state


# ── Lifecycle hooks ───────────────────────────────────────────────────────────

def extract_lifecycle_hints(code: str) -> list[dict]:
    hooks = {
        "ngOnInit":           "onMount",
        "ngOnDestroy":        "onDestroy",
        "ngAfterViewInit":    "onAfterViewInit",
        "ngOnChanges":        "onChanges",
        "ngAfterContentInit": "onAfterContentInit",
    }
    lifecycle = []
    for ng_hook, ir_hook in hooks.items():
        if re.search(rf'\b{ng_hook}\s*\(', code):
            lifecycle.append({ "hook": ir_hook })
    return lifecycle


# ── Methods ───────────────────────────────────────────────────────────────────

def extract_method_hints(code: str) -> list[str]:
    methods = []
    for m in re.finditer(
        r'(?:^|\n)\s+(?:(?:public|private|protected|async)\s+)*(\w+)\s*\([^)]*\)\s*(?::\s*\w+\s*)?\{',
        code,
    ):
        name = m.group(1)
        skip = {
            "constructor", "ngOnInit", "ngOnDestroy", "ngAfterViewInit",
            "ngOnChanges", "ngAfterContentInit", "if", "for", "while",
        }
        if name not in skip:
            methods.append(name)
    return list(dict.fromkeys(methods))


# ── Observable / subscription hints ──────────────────────────────────────────

def extract_subscription_hints(code: str) -> list[dict]:
    subs = []
    for m in re.finditer(
        r'(\w+)\.(\w+)\s*\([^)]*\)\s*\.subscribe\s*\(',
        code,
    ):
        subs.append({ "service": m.group(1), "method": m.group(2) })
    return subs


# ── Template analysis (inline template string) ────────────────────────────────

def extract_template_hints(code: str) -> dict:
    template_m = re.search(
        r'template\s*:\s*`([\s\S]*?)`|template\s*:\s*["\']([^"\']*)["\']',
        code,
    )
    template = ""
    if template_m:
        template = template_m.group(1) or template_m.group(2) or ""

    return {
        "conditionals": re.findall(r'\*ngIf\s*=\s*["\']([^"\']+)["\']',   template),
        "loops":        re.findall(r'\*ngFor\s*=\s*["\'][^"\']*of\s+(\w+)', template),
        "bindings":     re.findall(r'\[(\w+)\]\s*=',                        template),
        "events":       re.findall(r'\((\w+)\)\s*=',                        template),
        "models":       re.findall(r'\[\(ngModel\)\]\s*=\s*["\'](\w+)["\']', template),
        "inline":       bool(template),
    }


# ── Main entry ────────────────────────────────────────────────────────────────

def extract(code: str) -> dict:
    component = extract_component_name(code)
    imports   = extract_imports(code)

    lines        = code.splitlines()
    import_end   = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("import "):
            import_end = i + 1
    script_block = "\n".join(lines[import_end:]).strip()

    return {
        "framework":            "Angular",
        "component":            component,
        "selector":             extract_selector(code),
        "imports":              imports,
        "props":                extract_props(code),
        "outputs":              extract_outputs(code),
        "injected_services":    extract_injected_services(code),
        "state_hints":          extract_state_hints(code),
        "lifecycle_hints":      extract_lifecycle_hints(code),
        "method_hints":         extract_method_hints(code),
        "subscription_hints":   extract_subscription_hints(code),
        "event_hints":          extract_template_hints(code).get("events", []),
        "script_block":         script_block,
        "template_hints":       extract_template_hints(code),
    }

