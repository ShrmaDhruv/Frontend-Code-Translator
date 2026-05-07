import re
from typing import Optional


# ── Imports ───────────────────────────────────────────────────────────────────

def extract_imports(code: str) -> list[dict]:
    imports = []

    named = re.finditer(
        r'import\s+\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']',
        code,
    )
    for m in named:
        specifiers = [s.strip() for s in m.group(1).split(",") if s.strip()]
        imports.append({ "source": m.group(2), "specifiers": specifiers, "default": None })

    default_named = re.finditer(
        r'import\s+(\w+)\s*,\s*\{([^}]+)\}\s+from\s+["\']([^"\']+)["\']',
        code,
    )
    for m in default_named:
        specifiers = [s.strip() for s in m.group(2).split(",") if s.strip()]
        imports.append({ "source": m.group(3), "specifiers": specifiers, "default": m.group(1) })

    default_only = re.finditer(
        r'import\s+(\w+)\s+from\s+["\']([^"\']+)["\']',
        code,
    )
    for m in default_only:
        if not any(i["source"] == m.group(2) for i in imports):
            imports.append({ "source": m.group(2), "specifiers": [], "default": m.group(1) })

    return imports


# ── Component name ────────────────────────────────────────────────────────────

def extract_component_name(code: str) -> str:
    patterns = [
        r'export\s+default\s+function\s+(\w+)',
        r'export\s+function\s+(\w+)',
        r'function\s+(\w+)\s*\(',
        r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>',
        r'const\s+(\w+)\s*=\s*\w+\s*=>',
        r'class\s+(\w+)\s+extends\s+(?:React\.)?(?:Component|PureComponent)',
    ]
    for p in patterns:
        m = re.search(p, code)
        if m:
            name = m.group(1)
            if name not in ("default", "function", "class"):
                return name
    return "App"


# ── Props ─────────────────────────────────────────────────────────────────────

def extract_props(code: str, component_name: str) -> list[str]:
    props = []

    patterns = [
        rf'(?:function\s+{component_name}|const\s+{component_name}\s*=\s*(?:function\s*)?\()\s*\(?\s*\{{([^}}]+)\}}',
        r'(?:function\s+\w+|const\s+\w+\s*=\s*(?:function\s*)?\()\s*\(?\s*\{([^}]+)\}',
        r'=>\s*\{[^}]*\}\s*\(\s*\{([^}]+)\}',
    ]

    for p in patterns:
        m = re.search(p, code)
        if m:
            raw = m.group(1)
            for prop in raw.split(","):
                prop = prop.strip()
                if "=" in prop:
                    prop = prop.split("=")[0].strip()
                if ":" in prop:
                    prop = prop.split(":")[0].strip()
                if prop and re.match(r'^[a-zA-Z_]\w*$', prop):
                    props.append(prop)
            if props:
                return props

    multiline = re.search(
        r'(?:function\s+\w+|const\s+\w+\s*=.*?=>)\s*\(\s*\{([\s\S]*?)\}[\s,]*\)',
        code,
    )
    if multiline:
        raw = multiline.group(1)
        for prop in raw.split(","):
            prop = prop.strip().split("\n")[0].strip()
            prop = prop.split("=")[0].split(":")[0].strip()
            if prop and re.match(r'^[a-zA-Z_]\w*$', prop):
                props.append(prop)

    return list(dict.fromkeys(props))


# ── State ─────────────────────────────────────────────────────────────────────

def extract_state_hints(code: str) -> list[dict]:
    state = []

    use_state = re.finditer(
        r'const\s+\[(\w+),\s*\w+\]\s*=\s*useState\(([^)]*)\)',
        code,
    )
    for m in use_state:
        state.append({ "name": m.group(1), "init": m.group(2).strip() })

    use_reducer = re.finditer(
        r'const\s+\[(\w+),\s*\w+\]\s*=\s*useReducer\(',
        code,
    )
    for m in use_reducer:
        state.append({ "name": m.group(1), "init": None })

    use_ref = re.finditer(
        r'const\s+(\w+)\s*=\s*useRef\(([^)]*)\)',
        code,
    )
    for m in use_ref:
        state.append({ "name": m.group(1), "init": m.group(2).strip() })

    return state


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def extract_lifecycle_hints(code: str) -> list[dict]:
    lifecycle = []

    effects = re.finditer(
        r'useEffect\s*\(\s*(?:\(\s*\)|[^,]+),\s*(\[[^\]]*\])',
        code,
    )
    for m in effects:
        deps_raw = m.group(1).strip()
        deps     = [d.strip() for d in deps_raw.strip("[]").split(",") if d.strip()]
        if not deps:
            lifecycle.append({ "hook": "onMount", "deps": [] })
        else:
            lifecycle.append({ "hook": "onEffect", "deps": deps })

    no_deps = re.findall(r'useEffect\s*\(\s*[^,)]+\s*\)', code)
    for _ in no_deps:
        lifecycle.append({ "hook": "onEveryRender", "deps": None })

    if re.search(r'componentDidMount\s*\(', code):
        lifecycle.append({ "hook": "onMount", "deps": [] })
    if re.search(r'componentWillUnmount\s*\(', code):
        lifecycle.append({ "hook": "onDestroy", "deps": [] })

    return lifecycle


# ── Computed ──────────────────────────────────────────────────────────────────

def extract_computed_hints(code: str) -> list[dict]:
    computed = []

    memo = re.finditer(
        r'const\s+(\w+)\s*=\s*useMemo\s*\(\s*\(\s*\)\s*=>\s*([^,]+),',
        code,
    )
    for m in memo:
        computed.append({ "name": m.group(1), "expression": m.group(2).strip() })

    callback = re.finditer(
        r'const\s+(\w+)\s*=\s*useCallback\s*\(',
        code,
    )
    for m in callback:
        computed.append({ "name": m.group(1), "expression": "" })

    return computed


# ── Methods ───────────────────────────────────────────────────────────────────

def extract_method_hints(code: str) -> list[str]:
    methods = []

    handlers = re.findall(r'const\s+(handle\w+|on\w+)\s*=\s*(?:async\s*)?\(', code)
    methods.extend(handlers)

    arrow_fns = re.findall(r'const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', code)
    for name in arrow_fns:
        if name not in methods and not any(
            s["name"] == name for s in extract_state_hints(code)
        ):
            methods.append(name)

    return list(dict.fromkeys(methods))


# ── Event hints ───────────────────────────────────────────────────────────────

def extract_event_hints(code: str) -> list[str]:
    events  = set()
    jsx     = re.findall(r'on([A-Z]\w+)\s*=\s*\{', code)
    for e in jsx:
        events.add(e[0].lower() + e[1:])
    create  = re.findall(r'addEventListener\s*\(\s*["\'](\w+)["\']', code)
    events.update(create)
    return list(events)


# ── Is createElement style ────────────────────────────────────────────────────

def is_create_element_style(code: str) -> bool:
    return bool(re.search(r'React\.createElement\s*\(', code))


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
        "framework":          "React",
        "component":          component,
        "imports":            imports,
        "props":              extract_props(code, component),
        "state_hints":        extract_state_hints(code),
        "lifecycle_hints":    extract_lifecycle_hints(code),
        "computed_hints":     extract_computed_hints(code),
        "method_hints":       extract_method_hints(code),
        "event_hints":        extract_event_hints(code),
        "is_createElement":   is_create_element_style(code),
        "script_block":       script_block,
        "template_hints":     {},
    }