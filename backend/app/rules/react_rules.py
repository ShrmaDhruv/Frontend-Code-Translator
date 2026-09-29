"""
react_rules.py — Rule-based fingerprints for detecting React code.

Weight scale:
  10 = Definitive. This pattern exists in React ONLY.
   7 = Very strong. Extremely rare outside React.
   5 = Strong. Common in React, unlikely elsewhere.
   3 = Moderate. Slightly increases React probability.
  -5 to -10 = Negative. This pattern suggests it is NOT React.

Usage:
    from app.rules.react_rules import REACT_RULES
"""

import re
from app.rules.base import Rule


REACT_RULES: list[Rule] = [

    # ── WEIGHT 10 — DEFINITIVE ──────────────────────────────────────────

    Rule(
        id="react_classname",
        pattern=re.compile(r'className\s*=', re.MULTILINE),
        weight=10,
        reason="className is React-exclusive. No other framework uses this."
    ),
    Rule(
        id="react_usestate",
        pattern=re.compile(r'\buseState\s*\(', re.MULTILINE),
        weight=10,
        reason="React hook. Exists nowhere else."
    ),
    Rule(
        id="react_useeffect",
        pattern=re.compile(r'\buseEffect\s*\(', re.MULTILINE),
        weight=10,
        reason="React hook. Exists nowhere else."
    ),
    Rule(
        id="react_import_from_react",
        pattern=re.compile(r"import\s+.+\s+from\s+['\"]react['\"]", re.MULTILINE),
        weight=10,
        reason="Explicit React package import."
    ),
    Rule(
        id="react_createelement",
        pattern=re.compile(r'React\.createElement\s*\(', re.MULTILINE),
        weight=10,
        reason="React.createElement API. Covers non-JSX React code."
    ),

    # ── WEIGHT 7 — VERY STRONG ──────────────────────────────────────────

    Rule(
        id="react_jsx_return",
        pattern=re.compile(r'return\s*\(\s*\n?\s*<', re.MULTILINE),
        weight=7,
        reason="Returning JSX from a function — core React pattern."
    ),
    Rule(
        id="react_hooks_other",
        pattern=re.compile(
            r'\b(useRef|useCallback|useMemo|useContext|useReducer|useLayoutEffect)\s*\(',
            re.MULTILINE
        ),
        weight=7,
        reason="Other React hooks — all exclusive to React."
    ),
    Rule(
        id="react_jsx_self_closing_component",
        pattern=re.compile(r'<[A-Z][a-zA-Z]*\s*/>', re.MULTILINE),
        weight=7,
        reason="Self-closing capitalized component tag — JSX pattern."
    ),
    Rule(
        id="react_jsx_expression_in_attr",
        pattern=re.compile(r'\w+\s*=\s*\{[^}]+\}', re.MULTILINE),
        weight=7,
        reason="Curly brace expressions in JSX attributes — JSX specific."
    ),
    Rule(
        id="react_onclick_camel",
        pattern=re.compile(r'\bonClick\s*=\s*\{', re.MULTILINE),
        weight=7,
        reason="camelCase onClick with JSX expression. Vue/Angular use different syntax."
    ),

    # ── WEIGHT 5 — STRONG ───────────────────────────────────────────────

    Rule(
        id="react_export_default_function_cap",
        pattern=re.compile(r'export\s+default\s+function\s+[A-Z]', re.MULTILINE),
        weight=5,
        reason="Capitalized exported function — React component convention."
    ),
    Rule(
        id="react_props_destructure",
        pattern=re.compile(r'function\s+[A-Z]\w*\s*\(\s*\{[^}]*\}\s*\)', re.MULTILINE),
        weight=5,
        reason="Destructured props in component function signature."
    ),
    Rule(
        id="react_jsx_inline_expression",
        pattern=re.compile(r'>\s*\{[^}]+\}\s*<', re.MULTILINE),
        weight=5,
        reason="Inline JS expressions between JSX tags: {variable}"
    ),
    Rule(
        id="react_onchange",
        pattern=re.compile(r'\bonChange\s*=\s*\{', re.MULTILINE),
        weight=5,
        reason="camelCase onChange — React form handling pattern."
    ),
    Rule(
        id="react_router_import",
        pattern=re.compile(r"from\s+['\"]react-router", re.MULTILINE),
        weight=5,
        reason="React Router — React ecosystem package."
    ),

    # ── WEIGHT 3 — MODERATE ─────────────────────────────────────────────

    Rule(
        id="react_fragment_short",
        pattern=re.compile(r'<>\s*[\s\S]*?\s*</>', re.MULTILINE),
        weight=3,
        reason="Fragment shorthand <> </> — React specific."
    ),
    Rule(
        id="react_usestate_setter",
        pattern=re.compile(r'(?<![.\w])set(?!(?:Interval|Timeout|Immediate)\b)[A-Z]\w+\s*\(', re.MULTILINE),
        weight=3,
        reason="setX() naming convention for useState setters."
    ),
    Rule(
        id="react_prop_types",
        pattern=re.compile(r'\bpropTypes\s*=', re.MULTILINE),
        weight=3,
        reason="PropTypes validation — React ecosystem."
    ),

    # ── NEGATIVE SIGNALS ────────────────────────────────────────────────

    Rule(
        id="react_neg_template_tag",
        pattern=re.compile(r'<template>', re.MULTILINE),
        weight=-7,
        reason="Vue-exclusive SFC tag. Subtracts from React score."
    ),
    Rule(
        id="react_neg_angular_decorator",
        pattern=re.compile(r'@Component\s*\(', re.MULTILINE),
        weight=-10,
        reason="Angular decorator. Definitely not React."
    ),
]
