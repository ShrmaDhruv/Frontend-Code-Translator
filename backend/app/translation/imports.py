"""
Framework API import helpers shared by the response cleaner (auto-fix)
and the translation validator (detection).
"""

import re

VUE_APIS = {
    "ref", "reactive", "computed", "watch", "watchEffect", "nextTick",
    "onMounted", "onUnmounted", "onUpdated", "onBeforeMount", "onBeforeUnmount",
}

REACT_HOOKS = {
    "useState", "useEffect", "useMemo", "useCallback", "useRef",
    "useReducer", "useContext", "useLayoutEffect",
}

_MODULES = {"Vue": ("vue", VUE_APIS), "React": ("react", REACT_HOOKS)}


def _named_import_re(module: str) -> str:
    return rf'import\s+(?:(\w+)\s*,\s*)?\{{([^}}]*)\}}\s*from\s*["\']{module}["\']'


def named_imports(code: str, module: str) -> set[str]:
    names = set()
    for match in re.finditer(_named_import_re(module), code):
        names.update(
            item.strip().split(" as ", 1)[-1].strip()
            for item in match.group(2).split(",")
            if item.strip()
        )
    return names


def missing_imports(code: str, apis: set[str], imported: set[str]) -> list[str]:
    """APIs called bare (not as obj.api) that are neither imported nor defined locally."""
    missing = []
    for api in sorted(apis - imported):
        called = re.search(rf'(?<![.\w]){api}\s*\(', code)
        defined = re.search(rf'\b(?:function|const|let|var)\s+{api}\b', code)
        if called and not defined:
            missing.append(api)
    return missing


def _script(code: str, target: str) -> str:
    if target == "Vue":
        return "\n".join(re.findall(r'<script[^>]*>([\s\S]*?)</script>', code))
    return code


def find_missing(code: str, target: str) -> list[str]:
    if target not in _MODULES:
        return []
    module, apis = _MODULES[target]
    return missing_imports(_script(code, target), apis, named_imports(code, module))


def add_missing_imports(code: str, target: str) -> str:
    """Insert missing Vue/React API imports into the existing import (or add one)."""
    missing = find_missing(code, target)
    if not missing:
        return code
    module, _ = _MODULES[target]

    existing = re.search(_named_import_re(module), code)
    if existing:
        default, specifiers = existing.group(1), existing.group(2)
        names = [s.strip() for s in specifiers.split(",") if s.strip()] + missing
        prefix = f"{default}, " if default else ""
        return code[:existing.start()] + f"import {prefix}{{ {', '.join(names)} }} from '{module}'" + code[existing.end():]

    default_only = re.search(rf'import\s+(\w+)\s+from\s*["\']{module}["\']', code)
    if default_only:
        return (code[:default_only.start()]
                + f"import {default_only.group(1)}, {{ {', '.join(missing)} }} from '{module}'"
                + code[default_only.end():])

    statement = f"import {{ {', '.join(missing)} }} from '{module}'\n"
    if target == "Vue":
        tag = re.search(r'<script[^>]*>\s*\n?', code)
        if tag:
            return code[:tag.end()] + statement + code[tag.end():]
    return statement + code
