"""
angular_rules.py — Rule-based fingerprints for detecting Angular code.

Weight scale:
  10 = Definitive. This pattern exists in Angular ONLY.
   7 = Very strong. Extremely rare outside Angular.
   5 = Strong. Common in Angular, unlikely elsewhere.
   3 = Moderate. Slightly increases Angular probability.
  -5 to -10 = Negative. This pattern suggests it is NOT Angular.

Usage:
    from app.detection.rules.angular_rules import ANGULAR_RULES
"""

import re
from app.detection.rules.base import Rule


ANGULAR_RULES: list[Rule] = [

    # ── WEIGHT 10 — DEFINITIVE ──────────────────────────────────────────

    Rule(
        id="angular_component_decorator",
        pattern=re.compile(r'@Component\s*\(\s*\{', re.MULTILINE),
        weight=10,
        reason="Angular's core class decorator. Exists nowhere else."
    ),
    Rule(
        id="angular_ngmodule",
        pattern=re.compile(r'@NgModule\s*\(\s*\{', re.MULTILINE),
        weight=10,
        reason="Angular module decorator."
    ),
    Rule(
        id="angular_import_core",
        pattern=re.compile(r"from\s+['\"]@angular/core['\"]", re.MULTILINE),
        weight=10,
        reason="Angular core package import. Definitive proof."
    ),
    Rule(
        id="angular_injectable",
        pattern=re.compile(r'@Injectable\s*\(\s*\{', re.MULTILINE),
        weight=10,
        reason="Angular dependency injection decorator."
    ),

    # ── WEIGHT 7 — VERY STRONG ──────────────────────────────────────────

    Rule(
        id="angular_event_binding",
        pattern=re.compile(r'\([a-z]+\)\s*=\s*"', re.MULTILINE),
        weight=7,
        reason="Angular event binding syntax: (click)='method()'"
    ),
    Rule(
        id="angular_property_binding",
        pattern=re.compile(r'\[[a-z]+\]\s*=\s*"', re.MULTILINE),
        weight=7,
        reason="Angular property binding: [property]='value'"
    ),
    Rule(
        id="angular_ngif",
        pattern=re.compile(r'\*ngIf\s*=', re.MULTILINE),
        weight=7,
        reason="Angular structural directive for conditional rendering."
    ),
    Rule(
        id="angular_ngfor",
        pattern=re.compile(r'\*ngFor\s*=\s*"let\s+\w+\s+of', re.MULTILINE),
        weight=7,
        reason="Angular list rendering structural directive."
    ),
    Rule(
        id="angular_two_way_binding",
        pattern=re.compile(r'\[\(ngModel\)\]', re.MULTILINE),
        weight=7,
        reason="Angular banana-in-a-box [(ngModel)] two-way binding. Unique syntax."
    ),
    Rule(
        id="angular_input_decorator",
        pattern=re.compile(r'@Input\s*\(\s*\)', re.MULTILINE),
        weight=7,
        reason="Angular @Input() property decorator for receiving parent data."
    ),
    Rule(
        id="angular_output_decorator",
        pattern=re.compile(r'@Output\s*\(\s*\)', re.MULTILINE),
        weight=7,
        reason="Angular @Output() property decorator for emitting events."
    ),

    # ── WEIGHT 5 — STRONG ───────────────────────────────────────────────

    Rule(
        id="angular_implements_oninit",
        pattern=re.compile(r'implements\s+OnInit', re.MULTILINE),
        weight=5,
        reason="Angular lifecycle interface implementation."
    ),
    Rule(
        id="angular_ngoninit",
        pattern=re.compile(r'\bngOnInit\s*\(\s*\)', re.MULTILINE),
        weight=5,
        reason="Angular lifecycle hook method called after component init."
    ),
    Rule(
        id="angular_selector",
        pattern=re.compile(r"selector\s*:\s*['\"]app-", re.MULTILINE),
        weight=5,
        reason="Angular component selector with app- prefix convention."
    ),
    Rule(
        id="angular_template_url",
        pattern=re.compile(r"templateUrl\s*:\s*['\"]", re.MULTILINE),
        weight=5,
        reason="Angular external template file reference."
    ),
    Rule(
        id="angular_router_import",
        pattern=re.compile(r"from\s+['\"]@angular/router['\"]", re.MULTILINE),
        weight=5,
        reason="Angular Router package — Angular ecosystem."
    ),
    Rule(
        id="angular_eventemitter",
        pattern=re.compile(r'\bEventEmitter\s*[<(]', re.MULTILINE),
        weight=5,
        reason="Angular EventEmitter class for @Output() properties."
    ),

    # ── WEIGHT 3 — MODERATE ─────────────────────────────────────────────

    Rule(
        id="angular_class_component",
        pattern=re.compile(r'export\s+class\s+[A-Z]\w+Component', re.MULTILINE),
        weight=3,
        reason="Angular class naming convention — XxxComponent."
    ),
    Rule(
        id="angular_pipe_decorator",
        pattern=re.compile(r'@Pipe\s*\(\s*\{', re.MULTILINE),
        weight=3,
        reason="Angular Pipe decorator for data transformation."
    ),
    Rule(
        id="angular_directive_decorator",
        pattern=re.compile(r'@Directive\s*\(\s*\{', re.MULTILINE),
        weight=3,
        reason="Angular Directive decorator for DOM manipulation."
    ),
    Rule(
        id="angular_ngoondestroy",
        pattern=re.compile(r'\bngOnDestroy\s*\(\s*\)', re.MULTILINE),
        weight=3,
        reason="Angular cleanup lifecycle hook."
    ),

    # ── NEGATIVE SIGNALS ────────────────────────────────────────────────

    Rule(
        id="angular_neg_classname",
        pattern=re.compile(r'className\s*=', re.MULTILINE),
        weight=-10,
        reason="React-exclusive attribute. Subtracts from Angular score."
    ),
    Rule(
        id="angular_neg_template_tag",
        pattern=re.compile(r'^<template>', re.MULTILINE),
        weight=-10,
        reason="Vue SFC top-level tag. Subtracts from Angular score."
    ),
]
