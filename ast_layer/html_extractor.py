import re



def split_document(code: str) -> dict:
    script_blocks = re.findall(
        r'<script(?:\s[^>]*)?>(\s*)([\s\S]*?)</script>',
        code,
        re.IGNORECASE,
    )
    scripts = [b[1].strip() for b in script_blocks if b[1].strip()]

    style_blocks = re.findall(
        r'<style(?:\s[^>]*)?>(\s*)([\s\S]*?)</style>',
        code,
        re.IGNORECASE,
    )
    styles = [b[1].strip() for b in style_blocks if b[1].strip()]

    markup = re.sub(r'<script[\s\S]*?</script>', '', code, flags=re.IGNORECASE)
    markup = re.sub(r'<style[\s\S]*?</style>',  '', markup, flags=re.IGNORECASE)
    markup = markup.strip()

    external_scripts = re.findall(
        r'<script[^>]+src\s*=\s*["\']([^"\']+)["\']',
        code,
        re.IGNORECASE,
    )

    return {
        "scripts":          scripts,
        "merged_script":    "\n\n".join(scripts),
        "styles":           "\n\n".join(styles),
        "markup":           markup,
        "external_scripts": external_scripts,
    }


# ── Markup analysis ───────────────────────────────────────────────────────────

def extract_element_ids(markup: str) -> list[str]:
    return re.findall(r'id\s*=\s*["\']([^"\']+)["\']', markup, re.IGNORECASE)


def extract_element_classes(markup: str) -> list[str]:
    raw = re.findall(r'class\s*=\s*["\']([^"\']+)["\']', markup, re.IGNORECASE)
    classes = []
    for r in raw:
        classes.extend(r.split())
    return list(dict.fromkeys(classes))


def extract_inline_events(markup: str) -> list[dict]:
    events = []
    pattern = re.compile(
        r'on(\w+)\s*=\s*["\']([^"\']*)["\']',
        re.IGNORECASE,
    )
    for m in pattern.finditer(markup):
        events.append({
            "event":   m.group(1).lower(),
            "handler": m.group(2).strip(),
        })
    return events


def extract_form_elements(markup: str) -> list[dict]:
    forms = []
    for m in re.finditer(
        r'<input[^>]+name\s*=\s*["\']([^"\']+)["\'][^>]*>',
        markup,
        re.IGNORECASE,
    ):
        type_m = re.search(r'type\s*=\s*["\']([^"\']+)["\']', m.group(0), re.IGNORECASE)
        forms.append({
            "name": m.group(1),
            "type": type_m.group(1) if type_m else "text",
        })
    return forms


def extract_page_title(markup: str) -> str:
    m = re.search(r'<title[^>]*>([\s\S]*?)</title>', markup, re.IGNORECASE)
    return m.group(1).strip() if m else ""


# ── Script analysis ───────────────────────────────────────────────────────────

def extract_variables(script: str) -> list[dict]:
    variables = []

    for m in re.finditer(
        r'(?:var|let|const)\s+(\w+)\s*=\s*([^;\n]+)',
        script,
    ):
        name = m.group(1)
        init = m.group(2).strip()
        variables.append({ "name": name, "init": init })

    return variables


def extract_functions(script: str) -> list[str]:
    functions = []

    declared = re.findall(
        r'(?:async\s+)?function\s+(\w+)\s*\(',
        script,
    )
    functions.extend(declared)

    arrow = re.findall(
        r'(?:var|let|const)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>',
        script,
    )
    functions.extend(arrow)

    short_arrow = re.findall(
        r'(?:var|let|const)\s+(\w+)\s*=\s*(?:async\s*)?\w+\s*=>',
        script,
    )
    functions.extend(short_arrow)

    return list(dict.fromkeys(functions))


def extract_dom_queries(script: str) -> list[dict]:
    queries = []

    methods = [
        "getElementById",
        "querySelector",
        "querySelectorAll",
        "getElementsByClassName",
        "getElementsByTagName",
        "getElementsByName",
    ]

    for method in methods:
        for m in re.finditer(
            rf'document\.{method}\s*\(\s*["\']([^"\']+)["\']\s*\)',
            script,
        ):
            queries.append({ "method": method, "selector": m.group(1) })

    return queries


def extract_dom_mutations(script: str) -> list[str]:
    mutations = []

    patterns = [
        r'\.innerHTML\s*=',
        r'\.innerText\s*=',
        r'\.textContent\s*=',
        r'\.style\.\w+\s*=',
        r'\.classList\.(add|remove|toggle)',
        r'\.setAttribute\s*\(',
        r'\.appendChild\s*\(',
        r'\.removeChild\s*\(',
        r'\.createElement\s*\(',
    ]

    for p in patterns:
        if re.search(p, script):
            label = p.replace(r'\.', '.').replace(r'\s*=', '=').replace(r'\s*\(', '(').replace('\\', '')
            mutations.append(label.strip())

    return mutations


def extract_event_listeners(script: str) -> list[dict]:
    listeners = []
    for m in re.finditer(
        r'(?:(\w+)\.)?addEventListener\s*\(\s*["\'](\w+)["\']\s*,',
        script,
    ):
        listeners.append({
            "target":  m.group(1) if m.group(1) else "document",
            "event":   m.group(2),
        })
    return listeners


def extract_fetch_hints(script: str) -> list[dict]:
    hints = []

    for m in re.finditer(
        r'fetch\s*\(\s*["\']([^"\']+)["\']',
        script,
    ):
        hints.append({ "type": "fetch", "url": m.group(1) })

    if re.search(r'new\s+XMLHttpRequest', script):
        hints.append({ "type": "xhr" })

    return hints


def extract_storage_hints(script: str) -> list[str]:
    storage = []
    if re.search(r'localStorage\.',  script):
        storage.append("localStorage")
    if re.search(r'sessionStorage\.', script):
        storage.append("sessionStorage")
    return storage


def extract_state_hints(script: str) -> list[dict]:
    state = []
    for m in re.finditer(
        r'(?:var|let)\s+(\w+)\s*=\s*([^;\n]+)',
        script,
    ):
        init = m.group(2).strip()
        state.append({ "name": m.group(1), "init": init })
    return state


# ── Main entry ────────────────────────────────────────────────────────────────

def extract(code: str) -> dict:
    blocks = split_document(code)
    markup = blocks["markup"]
    script = blocks["merged_script"]

    title     = extract_page_title(markup)
    component = re.sub(r'\s+', '', title) if title else "App"

    inline_events    = extract_inline_events(markup)
    listener_events  = extract_event_listeners(script)
    all_event_hints  = list(dict.fromkeys(
        [e["event"] for e in inline_events] +
        [e["event"] for e in listener_events]
    ))

    return {
        "framework":          "HTML",
        "component":          component,
        "title":              title,
        "imports":            [],
        "props":              [],
        "state_hints":        extract_state_hints(script),
        "variables":          extract_variables(script),
        "lifecycle_hints":    [{ "hook": "onMount" }] if script.strip() else [],
        "computed_hints":     [],
        "method_hints":       extract_functions(script),
        "event_hints":        all_event_hints,
        "inline_events":      inline_events,
        "event_listeners":    listener_events,
        "dom_queries":        extract_dom_queries(script),
        "dom_mutations":      extract_dom_mutations(script),
        "fetch_hints":        extract_fetch_hints(script),
        "storage_hints":      extract_storage_hints(script),
        "form_elements":      extract_form_elements(markup),
        "element_ids":        extract_element_ids(markup),
        "element_classes":    extract_element_classes(markup),
        "external_scripts":   blocks["external_scripts"],
        "script_block":       script,
        "template_hints": {
            "conditionals": [],
            "loops":        [],
            "bindings":     [],
            "events":       all_event_hints,
            "models":       [f["name"] for f in extract_form_elements(markup)],
        },
        "styles":             blocks["styles"],
    }
