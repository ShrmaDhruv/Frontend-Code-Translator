import re
from dataclasses import dataclass, field
from ast_layer.ir_schema import IR


_FRAMEWORK_MARKERS = {
    "React": [
        r'\buseState\b',
        r'\buseEffect\b',
        r'export\s+default',
        r'=>\s*\(',
    ],
    "Vue": [
        r'<template>',
        r'<script\s+setup',
        r'\bref\s*\(',
        r'defineProps',
    ],
    "Angular": [
        r'@Component',
        r'export\s+class',
        r'@angular/core',
    ],
    "HTML": [
        r'<!DOCTYPE',
        r'<html',
        r'<script',
        r'<body',
    ],
}

_ANTI_MARKERS = {
    "React":   [r'<template>', r'ngOnInit', r'<!DOCTYPE'],
    "Vue":     [r'useState\b', r'\bset[A-Z]\w+\s*\(', r'ngOnInit', r'<!DOCTYPE'],
    "Angular": [r'<template>', r'useState\b', r'\bset[A-Z]\w+\s*\(', r'<!DOCTYPE'],
    "HTML":    [r'useState\b', r'\bset[A-Z]\w+\s*\(', r'<template>', r'ngOnInit'],
}

_REQUIRED_MARKERS = {
    "Vue": [r'<template>', r'<script\s+setup'],
    "Angular": [r'@Component', r'export\s+class'],
    "HTML": [r'<!DOCTYPE', r'<html', r'<body'],
}

_COMMENT_PATTERNS = [
    ("line comment", r'(?m)(^|[;{}\s])//[^\n\r]*'),
    ("block comment", r'/\*[\s\S]*?\*/'),
    ("HTML comment", r'<!--[\s\S]*?-->'),
]

_EMPTY_PLACEHOLDER_PATTERNS = [
    (
        "empty Vue lifecycle hook",
        r'\bon(?:Mounted|Unmounted|Updated|BeforeMount|BeforeUnmount)\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)',
    ),
    (
        "empty Vue watcher",
        r'\bwatch(?:Effect)?\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)',
    ),
    (
        "empty React effect",
        r'\buseEffect\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*(?:,\s*\[[^\]]*\])?\s*\)',
    ),
    (
        "empty Angular lifecycle hook",
        r'\bng(?:OnInit|OnDestroy|DoCheck|OnChanges)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{\s*\}',
    ),
]

_VUE_ALLOWED_IMPORTS = {
    "ref",
    "reactive",
    "computed",
    "watch",
    "watchEffect",
    "onMounted",
    "onUnmounted",
    "onUpdated",
    "onBeforeMount",
    "onBeforeUnmount",
    "nextTick",
}


def _validate_vue_imports(code: str, errors: list[str]) -> None:
    for match in re.finditer(r'import\s*\{([^}]+)\}\s*from\s*["\']vue["\']', code):
        raw_specifiers = match.group(1).split(",")
        specifiers = [
            item.strip().split(" as ", 1)[0].strip()
            for item in raw_specifiers
            if item.strip()
        ]
        invalid = [item for item in specifiers if item not in _VUE_ALLOWED_IMPORTS]
        if invalid:
            errors.append(
                "output imports invalid Vue symbol(s): "
                f"{', '.join(invalid)}"
            )


def _validate_vue_event_handlers(code: str, errors: list[str]) -> None:
    script_match = re.search(r'<script\s+setup[^>]*>([\s\S]*?)</script>', code)
    script = script_match.group(1) if script_match else ""
    handlers = set(re.findall(r'\bfunction\s+(\w+)\s*\(', script))
    handlers.update(
        re.findall(
            r'\bconst\s+(\w+)\s*=\s*(?:async\s*)?(?:function\s*)?(?:\([^)]*\)|\w+)\s*=>',
            script,
        )
    )

    templates = re.findall(r'<template[^>]*>([\s\S]*?)</template>', code)
    for template in templates:
        for expression in re.findall(r'@[\w:.]+\s*=\s*["\']([^"\']+)["\']', template):
            stripped = expression.strip()
            simple_handler = re.fullmatch(r'([A-Za-z_]\w*)\s*(?:\([^)]*\))?', stripped)
            if simple_handler:
                name = simple_handler.group(1)
                if not name.startswith("$") and name not in handlers:
                    errors.append(
                        f"Vue template event references undefined handler '{name}'"
                    )


def _angular_template(code: str) -> str:
    match = re.search(r'template\s*:\s*`([\s\S]*?)`', code)
    if match:
        return match.group(1)

    match = re.search(r'template\s*:\s*["\']([^"\']*)["\']', code)
    if match:
        return match.group(1)

    return ""


def _angular_input_names(code: str, ir: IR) -> set[str]:
    names = {prop.name for prop in ir.props if prop.name}
    names.update(
        re.findall(
            r'@Input\s*\(\s*\)\s+'
            r'(?:(?:public|private|protected|readonly)\s+)?'
            r'([A-Za-z_]\w*)',
            code,
        )
    )
    return names


def _validate_angular_template(code: str, errors: list[str]) -> None:
    template = _angular_template(code)
    if not template:
        return

    if re.search(r'\bon[A-Z]\w*\s*=', template):
        errors.append("Angular template contains React-style event binding")

    if "className=" in template:
        errors.append("Angular template uses className instead of class")

    if re.search(r'(?<!\{)\{[^{}\n]*\?[^{}\n]*:[^{}\n]*\}(?!\})', template):
        errors.append("Angular template contains JSX-style ternary interpolation")

    for line in template.splitlines():
        stripped = line.strip()
        if re.fullmatch(r'(?:0x)?[0-9a-fA-F]{8,}', stripped):
            errors.append("Angular template contains a standalone hex artifact")
            return
        if re.fullmatch(r'[A-Za-z0-9+/=]{24,}', stripped):
            errors.append("Angular template contains a standalone random artifact")
            return


def _validate_angular_input_mutation(code: str, ir: IR, errors: list[str]) -> None:
    input_names = _angular_input_names(code, ir)
    if not input_names:
        return

    template = _angular_template(code)
    class_code = re.sub(r'template\s*:\s*`[\s\S]*?`', '', code)
    class_code = re.sub(r'template\s*:\s*["\'][^"\']*["\']', '', class_code)

    for name in sorted(input_names):
        escaped = re.escape(name)
        if re.search(rf'\bthis\.{escaped}\s*(?:\+\+|--|[+\-*/]?=)', class_code):
            errors.append(
                f"Angular output mutates @Input() '{name}' directly; use local state or @Output()"
            )

        if re.search(
            rf'\([^)]+\)\s*=\s*["\'][^"\']*\b{escaped}\s*(?:\+\+|--|[+\-*/]?=)',
            template,
        ):
            errors.append(
                f"Angular template mutates @Input() '{name}' directly; use local state or @Output()"
            )


_ANGULAR_LIFECYCLE_TO_IR = {
    "ngOnInit": "onMount",
    "ngOnDestroy": "onDestroy",
    "ngDoCheck": "onUpdate",
    "ngOnChanges": "onChanges",
}


def _validate_angular_lifecycle(code: str, ir: IR, errors: list[str]) -> None:
    allowed_hooks = {item.hook for item in ir.lifecycle if item.hook}
    for hook, ir_hook in _ANGULAR_LIFECYCLE_TO_IR.items():
        if re.search(rf'\b{hook}\s*\(', code) and ir_hook not in allowed_hooks:
            errors.append(
                f"Angular output adds {hook} without matching source lifecycle behavior"
            )


def _validate_angular_imports(code: str, errors: list[str]) -> None:
    for match in re.finditer(r'import\s*\{([^}]+)\}\s*from\s*["\']@angular/core["\']', code):
        raw_specifiers = match.group(1).split(",")
        specifiers = [
            item.strip().split(" as ", 1)[-1].strip()
            for item in raw_specifiers
            if item.strip()
        ]
        rest = code[:match.start()] + code[match.end():]
        unused = [
            item for item in specifiers
            if not re.search(rf'\b{re.escape(item)}\b', rest)
        ]
        if unused:
            errors.append(
                "Angular output imports unused core symbol(s): "
                f"{', '.join(unused)}"
            )


def _validate_angular_output(code: str, ir: IR, errors: list[str]) -> None:
    _validate_angular_template(code, errors)
    _validate_angular_input_mutation(code, ir, errors)
    _validate_angular_lifecycle(code, ir, errors)
    _validate_angular_imports(code, errors)


def _html_markup(code: str) -> str:
    markup = re.sub(r'<script[\s\S]*?</script>', '', code, flags=re.IGNORECASE)
    markup = re.sub(r'<style[\s\S]*?</style>', '', markup, flags=re.IGNORECASE)
    return markup


def _html_scripts(code: str) -> list[tuple[int, str]]:
    scripts = []
    for match in re.finditer(
        r'<script(?:\s[^>]*)?>([\s\S]*?)</script>',
        code,
        flags=re.IGNORECASE,
    ):
        scripts.append((match.start(), match.group(1)))
    return scripts


def _html_ids(markup: str) -> set[str]:
    return set(re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']', markup, flags=re.IGNORECASE))


def _html_classes(markup: str) -> set[str]:
    classes: set[str] = set()
    for raw in re.findall(r'\bclass\s*=\s*["\']([^"\']+)["\']', markup, flags=re.IGNORECASE):
        classes.update(item for item in raw.split() if item)
    return classes


def _html_dom_refs(script: str) -> tuple[set[str], set[str]]:
    ids = set(re.findall(r'document\.getElementById\s*\(\s*["\']([^"\']+)["\']', script))
    classes = set(
        re.findall(r'document\.getElementsByClassName\s*\(\s*["\']([^"\']+)["\']', script)
    )

    for selector in re.findall(
        r'document\.querySelector(?:All)?\s*\(\s*["\']([^"\']+)["\']',
        script,
    ):
        id_match = re.fullmatch(r'#([A-Za-z_][\w\-]*)', selector.strip())
        class_match = re.fullmatch(r'\.([A-Za-z_][\w\-]*)', selector.strip())
        if id_match:
            ids.add(id_match.group(1))
        if class_match:
            classes.add(class_match.group(1))

    return ids, classes


def _validate_html_viewport(code: str, errors: list[str]) -> None:
    viewport = re.search(
        r'<meta[^>]+name\s*=\s*["\']viewport["\'][^>]*>',
        code,
        flags=re.IGNORECASE,
    )
    if not viewport:
        errors.append("HTML output is missing a viewport meta tag")
        return

    content_match = re.search(
        r'content\s*=\s*["\']([^"\']+)["\']',
        viewport.group(0),
        flags=re.IGNORECASE,
    )
    content = content_match.group(1).replace(" ", "").lower() if content_match else ""
    if "width=device-width" not in content or not re.search(r'initial-scale=1(?:\.0)?', content):
        errors.append(
            "HTML viewport must use content=\"width=device-width, initial-scale=1.0\""
        )


def _validate_html_dom_consistency(code: str, errors: list[str]) -> None:
    markup = _html_markup(code)
    ids = _html_ids(markup)
    classes = _html_classes(markup)
    script = "\n".join(block for _, block in _html_scripts(code))
    referenced_ids, referenced_classes = _html_dom_refs(script)

    for element_id in sorted(referenced_ids - ids):
        errors.append(f"JavaScript references missing HTML id '{element_id}'")

    for class_name in sorted(referenced_classes - classes):
        errors.append(f"JavaScript references missing HTML class '{class_name}'")


def _script_has_dom_ready(script: str) -> bool:
    return bool(re.search(r'document\.addEventListener\s*\(\s*["\']DOMContentLoaded["\']', script))


def _validate_html_timing(code: str, errors: list[str]) -> None:
    scripts = _html_scripts(code)
    if not scripts:
        return

    script = "\n".join(block for _, block in scripts)
    uses_dom = bool(
        re.search(
            r'document\.(getElementById|querySelector|querySelectorAll|getElementsByClassName)|\.addEventListener\s*\(',
            script,
        )
    )
    if not uses_dom or _script_has_dom_ready(script):
        return

    first_script_index = scripts[0][0]
    referenced_ids, referenced_classes = _html_dom_refs(script)

    for element_id in referenced_ids:
        attr_index = code.find(f'id="{element_id}"')
        if attr_index == -1:
            attr_index = code.find(f"id='{element_id}'")
        if attr_index > first_script_index:
            errors.append(
                f"JavaScript queries id '{element_id}' before its element is parsed"
            )

    for class_name in referenced_classes:
        attr_match = re.search(
            rf'class\s*=\s*["\'][^"\']*\b{re.escape(class_name)}\b',
            code,
            flags=re.IGNORECASE,
        )
        if attr_match and attr_match.start() > first_script_index:
            errors.append(
                f"JavaScript queries class '{class_name}' before its element is parsed"
            )


def _validate_html_initialization(code: str, errors: list[str]) -> None:
    script = "\n".join(block for _, block in _html_scripts(code))

    empty_dom_ready = re.search(
        r'document\.addEventListener\s*\(\s*["\']DOMContentLoaded["\']\s*,\s*'
        r'(?:\(\s*\)\s*=>|function\s*\([^)]*\))\s*\{\s*\}\s*\)',
        script,
    )
    if empty_dom_ready:
        errors.append("DOMContentLoaded callback is empty; initialization is incomplete")

    markup = _html_markup(code)
    empty_containers = re.findall(
        r'<(div|main|section|ul|ol|tbody)\b([^>]*)>\s*</\1>',
        markup,
        flags=re.IGNORECASE,
    )
    if empty_containers:
        has_rendering = bool(
            re.search(r'\.(innerHTML|textContent)\s*=|\.appendChild\s*\(|\.replaceChildren\s*\(|render\s*\(', script)
        )
        if not has_rendering:
            errors.append("HTML output defines empty containers without rendering UI content")


def _validate_html_event_binding(code: str, errors: list[str]) -> None:
    markup = _html_markup(code)
    if re.search(r'\son\w+\s*=', markup, flags=re.IGNORECASE):
        errors.append(
            "HTML output uses inline event attributes; attach listeners during initialization"
        )

    script = "\n".join(block for _, block in _html_scripts(code))
    if re.search(r'\.\s*on(?:click|change|input|submit|keydown|keyup|load)\s*=', script):
        errors.append(
            "HTML output assigns event handler properties; use guarded addEventListener setup"
        )


def _validate_html_state_rendering(code: str, ir: IR, errors: list[str]) -> None:
    if not ir.state:
        return

    script = "\n".join(block for _, block in _html_scripts(code))
    mutates_state = False
    for state in ir.state:
        if not state.name:
            continue
        name = re.escape(state.name)
        if re.search(
            rf'\b{name}\s*(?:\+\+|--|[+\-*/]=)|\b{name}\s*=\s*\b{name}\b\s*[+\-*/]|'
            rf'\b{name}\.(?:push|pop|splice|shift|unshift)\s*\(',
            script,
        ):
            mutates_state = True
            break

    if not mutates_state:
        return

    renders_state = bool(
        re.search(
            r'\.(?:textContent|innerHTML|value)\s*=|\.appendChild\s*\(|\.replaceChildren\s*\(|\brender\s*\(|\bupdate\w*\s*\(',
            script,
        )
    )
    if not renders_state:
        errors.append(
            "HTML state changes are not rendered back into the DOM"
        )


def _has_null_guard(script: str, name: str) -> bool:
    escaped = re.escape(name)
    return bool(
        re.search(rf'\bif\s*\(\s*{escaped}\s*\)', script)
        or re.search(rf'\bif\s*\(\s*!\s*{escaped}\s*\)\s*return\b', script)
        or re.search(rf'\b{escaped}\?\.', script)
    )


def _validate_html_safe_dom_access(code: str, errors: list[str]) -> None:
    script = "\n".join(block for _, block in _html_scripts(code))
    direct_unsafe = re.search(
        r'document\.(?:getElementById|querySelector|querySelectorAll|getElementsByClassName)'
        r'\s*\([^)]*\)\s*\.(?:addEventListener|textContent|innerHTML|value|style|classList)\b',
        script,
    )
    if direct_unsafe:
        errors.append("JavaScript uses direct DOM access without a null guard")

    assignments = re.findall(
        r'\b(?:const|let|var)\s+(\w+)\s*=\s*document\.'
        r'(?:getElementById|querySelector|querySelectorAll|getElementsByClassName)\s*\([^)]*\)',
        script,
    )
    for name in assignments:
        unsafe_use = re.search(
            rf'\b{re.escape(name)}\.(?:addEventListener|textContent|innerHTML|value|style|classList)\b',
            script,
        )
        if unsafe_use and not _has_null_guard(script, name):
            errors.append(f"DOM element '{name}' is used without a null guard")


def _validate_html_output(code: str, ir: IR, errors: list[str]) -> None:
    _validate_html_viewport(code, errors)
    _validate_html_dom_consistency(code, errors)
    _validate_html_timing(code, errors)
    _validate_html_initialization(code, errors)
    _validate_html_event_binding(code, errors)
    _validate_html_state_rendering(code, ir, errors)
    _validate_html_safe_dom_access(code, errors)


@dataclass
class TranslationValidationResult:
    is_valid: bool
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_translation(
    code:             str,
    ir:               IR,
    target_framework: str,
) -> TranslationValidationResult:
    """
    Validate translated code against the source IR.

    Args:
        code             : Cleaned translated code string
        ir               : Source IR the translation was generated from
        target_framework : The framework the code was translated into

    Returns:
        TranslationValidationResult with errors and warnings
    """
    errors   = []
    warnings = []

    if not code or not code.strip():
        errors.append("translated output is empty")
        return TranslationValidationResult(is_valid=False, errors=errors)

    if len(code.strip()) < 20:
        errors.append("translated output is too short to be valid code")
        return TranslationValidationResult(is_valid=False, errors=errors)

    for label, pattern in _COMMENT_PATTERNS:
        if re.search(pattern, code):
            errors.append(f"output contains a {label}; translated code must have zero comments")

    for label, pattern in _EMPTY_PLACEHOLDER_PATTERNS:
        if re.search(pattern, code):
            errors.append(f"output contains an {label}; do not add placeholder code")

    for anti in _ANTI_MARKERS.get(target_framework, []):
        if re.search(anti, code):
            errors.append(
                f"output contains source-framework marker '{anti}' — "
                f"translation may have failed"
            )

    markers      = _FRAMEWORK_MARKERS.get(target_framework, [])
    markers_hit  = sum(1 for m in markers if re.search(m, code))
    if markers_hit == 0:
        errors.append(
            f"output contains no {target_framework} framework markers — "
            f"translation may be wrong framework"
        )

    for marker in _REQUIRED_MARKERS.get(target_framework, []):
        if not re.search(marker, code, flags=re.IGNORECASE):
            errors.append(
                f"output is missing required {target_framework} structure marker '{marker}'"
            )

    if target_framework == "Vue":
        _validate_vue_imports(code, errors)
        _validate_vue_event_handlers(code, errors)

    if target_framework == "Angular":
        _validate_angular_output(code, ir, errors)

    if target_framework == "HTML":
        _validate_html_output(code, ir, errors)

    if target_framework in ("React", "Angular") and ir.component and ir.component != "App":
        if ir.component not in code:
            errors.append(
                f"component name '{ir.component}' not found in output"
            )

    for state in ir.state:
        if state.name and state.name not in code:
            warnings.append(f"state '{state.name}' not found in output")

    for method in ir.methods:
        if method.name and method.name not in code:
            warnings.append(f"method '{method.name}' not found in output")

    for prop in ir.props:
        if prop.name and prop.name not in code:
            warnings.append(f"prop '{prop.name}' not found in output")

    return TranslationValidationResult(
        is_valid = len(errors) == 0,
        errors   = errors,
        warnings = warnings,
    )
