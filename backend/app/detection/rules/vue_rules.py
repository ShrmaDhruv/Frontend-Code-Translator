"""
vue_rules.py — Rule-based fingerprints for detecting Vue code.

Weight scale:
  10 = Definitive. This pattern exists in Vue ONLY.
   7 = Very strong. Extremely rare outside Vue.
   5 = Strong. Common in Vue, unlikely elsewhere.
   3 = Moderate. Slightly increases Vue probability.
  -5 to -10 = Negative. This pattern suggests it is NOT Vue.

Usage:
    from app.detection.rules.vue_rules import VUE_RULES
"""

import re
from app.detection.rules.base import Rule


VUE_RULES: list[Rule] = [

    # ── WEIGHT 10 — DEFINITIVE ──────────────────────────────────────────

    Rule(
        id="vue_template_tag",
        pattern=re.compile(r'^<template>', re.MULTILINE),
        weight=10,
        reason="Top-level <template> is exclusively Vue's SFC format."
    ),
    Rule(
        id="vue_script_setup",
        pattern=re.compile(r'<script\s+setup>', re.MULTILINE),
        weight=10,
        reason="Vue 3 Composition API script setup block. Exists nowhere else."
    ),
    Rule(
        id="vue_v_model",
        pattern=re.compile(r'\bv-model\s*=', re.MULTILINE),
        weight=10,
        reason="Vue directive. No other framework uses the v- prefix."
    ),
    Rule(
        id="vue_v_for",
        pattern=re.compile(r'\bv-for\s*=\s*[\'"]', re.MULTILINE),
        weight=10,
        reason="Vue list rendering directive."
    ),
    Rule(
        id="vue_v_if",
        pattern=re.compile(r'\bv-if\s*=\s*[\'"]', re.MULTILINE),
        weight=10,
        reason="Vue conditional rendering directive."
    ),
    Rule(
        id="vue_import_from_vue",
        pattern=re.compile(r"from\s+['\"]vue['\"]", re.MULTILINE),
        weight=10,
        reason="Explicit Vue package import."
    ),

    # ── WEIGHT 7 — VERY STRONG ──────────────────────────────────────────

    Rule(
        id="vue_at_click",
        pattern=re.compile(r'@click\s*=', re.MULTILINE),
        weight=7,
        reason="Shorthand for v-on:click. Vue-exclusive syntax."
    ),
    Rule(
        id="vue_colon_bind",
        pattern=re.compile(r':[a-z]+\w*\s*=', re.MULTILINE),
        weight=7,
        reason="Shorthand for v-bind — :href, :class, :style"
    ),
    Rule(
        id="vue_define_props",
        pattern=re.compile(r'\bdefineProps\s*[(<]', re.MULTILINE),
        weight=7,
        reason="Vue 3 Composition API macro for declaring props."
    ),
    Rule(
        id="vue_define_emits",
        pattern=re.compile(r'\bdefineEmits\s*\(', re.MULTILINE),
        weight=7,
        reason="Vue 3 Composition API macro for declaring emits."
    ),
    Rule(
        id="vue_v_bind_explicit",
        pattern=re.compile(r'\bv-bind\s*:', re.MULTILINE),
        weight=7,
        reason="Explicit v-bind directive."
    ),
    Rule(
        id="vue_v_on_explicit",
        pattern=re.compile(r'\bv-on\s*:', re.MULTILINE),
        weight=7,
        reason="Explicit v-on directive."
    ),

    # ── WEIGHT 5 — STRONG ───────────────────────────────────────────────

    Rule(
        id="vue_ref_call",
        pattern=re.compile(r'\bref\s*\(\s*[^)]+\)', re.MULTILINE),
        weight=5,
        reason="ref() as standalone function — Vue 3 reactive primitive. Different from React's useRef()."
    ),
    Rule(
        id="vue_reactive",
        pattern=re.compile(r'\breactive\s*\(\s*\{', re.MULTILINE),
        weight=5,
        reason="reactive() object wrapper — Vue 3 exclusive."
    ),
    Rule(
        id="vue_computed_fn",
        pattern=re.compile(r'\bcomputed\s*\(\s*\(\s*\)', re.MULTILINE),
        weight=5,
        reason="Vue computed property as a function call."
    ),
    Rule(
        id="vue_options_data",
        pattern=re.compile(r'\bdata\s*\(\s*\)\s*\{[\s\S]*?return\s*\{', re.MULTILINE),
        weight=5,
        reason="Vue 2 Options API data() function — returns reactive state object."
    ),
    Rule(
        id="vue_options_methods",
        pattern=re.compile(r'\bmethods\s*:\s*\{', re.MULTILINE),
        weight=5,
        reason="Vue Options API methods object."
    ),
    Rule(
        id="vue_options_computed",
        pattern=re.compile(r'\bcomputed\s*:\s*\{', re.MULTILINE),
        weight=5,
        reason="Vue Options API computed properties object."
    ),
    Rule(
        id="vue_watch",
        pattern=re.compile(r'\bwatch\s*:\s*\{', re.MULTILINE),
        weight=5,
        reason="Vue Options API watch object."
    ),
    Rule(
        id="vue_router_import",
        pattern=re.compile(r"from\s+['\"]vue-router['\"]", re.MULTILINE),
        weight=5,
        reason="Vue Router — Vue ecosystem package."
    ),

    # ── WEIGHT 3 — MODERATE ─────────────────────────────────────────────

    Rule(
        id="vue_three_block_structure",
        pattern=re.compile(r'<template>[\s\S]*<script[\s\S]*<style', re.MULTILINE),
        weight=3,
        reason="All three SFC blocks present (template + script + style) — strongly Vue."
    ),
    Rule(
        id="vue_mustache",
        pattern=re.compile(r'\{\{\s*\w[\w.]*\s*\}\}', re.MULTILINE),
        weight=3,
        reason="Mustache interpolation {{ value }} — very common in Vue templates."
    ),
    Rule(
        id="vue_v_show",
        pattern=re.compile(r'\bv-show\s*=', re.MULTILINE),
        weight=3,
        reason="Vue visibility directive (renders but hides via CSS)."
    ),
    Rule(
        id="vue_emit",
        pattern=re.compile(r'\$emit\s*\(', re.MULTILINE),
        weight=3,
        reason="Vue instance $emit method for child-to-parent events."
    ),

    # ── NEGATIVE SIGNALS ────────────────────────────────────────────────

    Rule(
        id="vue_neg_classname",
        pattern=re.compile(r'className\s*=', re.MULTILINE),
        weight=-10,
        reason="React-exclusive attribute. Subtracts from Vue score."
    ),
    Rule(
        id="vue_neg_angular_decorator",
        pattern=re.compile(r'@Component\s*\(', re.MULTILINE),
        weight=-10,
        reason="Angular class decorator. Definitely not Vue."
    ),
]
