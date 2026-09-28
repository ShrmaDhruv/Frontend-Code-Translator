"""
html_rules.py — Rule-based fingerprints for detecting Vanilla HTML/JS code.

Unlike framework rules, HTML detection is partly about the ABSENCE of framework
patterns and partly about the PRESENCE of raw DOM API usage.

Weight scale:
  10 = Definitive. Frameworks never do this.
   7 = Very strong. Almost exclusively vanilla JS.
   5 = Strong. Common in vanilla, rare in frameworks.
   3 = Moderate. Slightly increases HTML probability.

Usage:
    from app.rules.html_rules import HTML_RULES
"""

import re
from app.rules.base import Rule


HTML_RULES: list[Rule] = [

    # ── WEIGHT 10 — DEFINITIVE ──────────────────────────────────────────

    Rule(
        id="html_inline_event_string",
        pattern=re.compile(r'\bon\w+\s*=\s*["\'][^"\']+["\']', re.MULTILINE),
        weight=10,
        reason="String-based inline event handlers onclick='fn()'. Frameworks never do this."
    ),
    Rule(
        id="html_document_getelementbyid",
        pattern=re.compile(r'document\.getElementById\s*\(', re.MULTILINE),
        weight=10,
        reason="Raw DOM API getElementById. Frameworks abstract this entirely."
    ),

    # ── WEIGHT 7 — VERY STRONG ──────────────────────────────────────────

    Rule(
        id="html_query_selector",
        pattern=re.compile(r'document\.querySelector\s*\(', re.MULTILINE),
        weight=7,
        reason="Raw DOM querying — vanilla JS pattern."
    ),
    Rule(
        id="html_query_selector_all",
        pattern=re.compile(r'document\.querySelectorAll\s*\(', re.MULTILINE),
        weight=7,
        reason="Raw DOM bulk querying — vanilla JS pattern."
    ),
    Rule(
        id="html_innerhtml",
        pattern=re.compile(r'\.innerHTML\s*=', re.MULTILINE),
        weight=7,
        reason="Direct innerHTML mutation. Frameworks manage the DOM, not you."
    ),
    Rule(
        id="html_addeventlistener",
        pattern=re.compile(r'\.addEventListener\s*\(', re.MULTILINE),
        weight=7,
        reason="Manual event listener attachment — vanilla JS pattern."
    ),

    # ── WEIGHT 5 — STRONG ───────────────────────────────────────────────

    Rule(
        id="html_doctype",
        pattern=re.compile(r'<!DOCTYPE\s+html>', re.MULTILINE | re.IGNORECASE),
        weight=5,
        reason="Full HTML document with DOCTYPE declaration."
    ),
    Rule(
        id="html_script_src",
        pattern=re.compile(r'<script\s+src\s*=', re.MULTILINE),
        weight=5,
        reason="CDN script loading without a module bundler."
    ),
    Rule(
        id="html_innertext",
        pattern=re.compile(r'\.innerText\s*=', re.MULTILINE),
        weight=5,
        reason="Direct DOM text mutation via innerText — vanilla JS."
    ),
    Rule(
        id="html_createelement_dom",
        pattern=re.compile(r'document\.createElement\s*\(', re.MULTILINE),
        weight=5,
        reason="Programmatic DOM node creation — vanilla JS."
    ),
    Rule(
        id="html_appendchild",
        pattern=re.compile(r'\.appendChild\s*\(', re.MULTILINE),
        weight=5,
        reason="Manual DOM tree manipulation — vanilla JS."
    ),

    # ── WEIGHT 3 — MODERATE ─────────────────────────────────────────────

    Rule(
        id="html_var_keyword",
        pattern=re.compile(r'\bvar\b', re.MULTILINE),
        weight=3,
        reason="var keyword — older JS style, rare in modern framework code."
    ),
    Rule(
        id="html_style_tag",
        pattern=re.compile(r'<style\s*>', re.MULTILINE),
        weight=3,
        reason="Inline <style> block — common in vanilla HTML pages."
    ),
    Rule(
        id="html_window_onload",
        pattern=re.compile(r'window\.onload\s*=', re.MULTILINE),
        weight=3,
        reason="window.onload assignment — vanilla JS initialization pattern."
    ),
    Rule(
        id="html_settimeout_raw",
        pattern=re.compile(r'\bsetTimeout\s*\(', re.MULTILINE),
        weight=3,
        reason="Raw setTimeout — more common in vanilla JS than framework code."
    ),
]
