"""
test_ast_ir_layer.py

Focused test suite for the AST pre-parser and IR builder layer.

Run offline checks:
    python test_ast_ir_layer.py

Run with local Ollama/Qwen IR extraction:
    python test_ast_ir_layer.py --live
"""

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

from app.ast_layer.ir_schema import IR, IRState, IRProp, IRMethod, IRLifecycle
from app.ast_layer.ir_validator import validate
from app.ast_layer.pre_parser import parse


REACT_SAMPLE = """
import React, { useState, useEffect, useMemo } from 'react'

const Dashboard = ({ userId, title = 'Home' }) => {
  const [count, setCount] = useState(0)
  const total = useMemo(() => count + 1, [count])

  useEffect(() => {
    document.title = title
  }, [])

  const handleClick = () => {
    setCount(c => c + 1)
  }

  return <button onClick={handleClick}>{total}</button>
}

export default Dashboard
"""


VUE_SAMPLE = """
<template>
  <section>
    <p v-if="visible">{{ count }}</p>
    <button @click="increment">Add</button>
    <input v-model="name" />
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const count = ref(0)
const name = ref('')
const label = computed(() => name.value || 'Anonymous')

const increment = () => {
  count.value++
}

onMounted(() => {
  document.title = label.value
})
</script>

<style>
section { padding: 1rem; }
</style>
"""


ANGULAR_SAMPLE = """
import { Component, Input, OnInit } from '@angular/core'

@Component({
  selector: 'app-user-card',
  template: `
    <button (click)="load()">Load</button>
    <p *ngIf="loading">Loading...</p>
  `
})
export class UserCardComponent implements OnInit {
  @Input() userId: number = 0
  loading: boolean = false

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.load()
  }

  load(): void {
    this.loading = true
  }
}
"""


HTML_SAMPLE = """
<!DOCTYPE html>
<html>
<head>
  <title>Todo App</title>
  <style>.done { text-decoration: line-through; }</style>
</head>
<body>
  <input id="todo-input" name="todo" />
  <button onclick="addTodo()">Add</button>
  <ul id="todo-list"></ul>
  <script>
    let todos = []
    function addTodo() {
      const input = document.getElementById('todo-input')
      todos.push(input.value)
    }
    document.addEventListener('DOMContentLoaded', addTodo)
  </script>
</body>
</html>
"""


def run(label, cases, test_fn):
    print(f"\n{label}")
    print("-" * 60)
    passed = 0
    for case in cases:
        ok, msg = test_fn(case)
        print(f"  {'PASS' if ok else 'FAIL'} - {msg}")
        if ok:
            passed += 1
    print(f"  {passed}/{len(cases)} passed")
    return passed == len(cases)


def contains_name(items, name):
    for item in items:
        if isinstance(item, dict) and item.get("name") == name:
            return True
        if item == name:
            return True
    return False


def test_pre_parser():
    cases = [
        (
            "React extracts component, props, state, lifecycle, method, event",
            "React",
            REACT_SAMPLE,
            lambda s: (
                s["component"] == "Dashboard"
                and "userId" in s["props"]
                and contains_name(s["state_hints"], "count")
                and contains_name(s["computed_hints"], "total")
                and any(h.get("hook") == "onMount" for h in s["lifecycle_hints"])
                and "handleClick" in s["method_hints"]
                and "click" in s["event_hints"]
            ),
        ),
        (
            "Vue extracts setup refs, computed, mounted hook, template hints",
            "Vue",
            VUE_SAMPLE,
            lambda s: (
                s["is_setup"]
                and s["is_sfc"]
                and contains_name(s["state_hints"], "count")
                and contains_name(s["state_hints"], "name")
                and contains_name(s["computed_hints"], "label")
                and any(h.get("hook") == "onMount" for h in s["lifecycle_hints"])
                and "increment" in s["method_hints"]
                and "click" in s["event_hints"]
                and "name" in s["template_hints"]["models"]
                and "section { padding: 1rem; }" in s["styles"]
            ),
        ),
        (
            "Angular extracts selector, input, state, service, lifecycle, method",
            "Angular",
            ANGULAR_SAMPLE,
            lambda s: (
                s["selector"] == "app-user-card"
                and contains_name(s["props"], "userId")
                and contains_name(s["state_hints"], "loading")
                and contains_name(s["injected_services"], "http")
                and any(h.get("hook") == "onMount" for h in s["lifecycle_hints"])
                and "load" in s["method_hints"]
                and "click" in s["event_hints"]
            ),
        ),
        (
            "HTML extracts title, state, function, events, DOM query, form field",
            "HTML",
            HTML_SAMPLE,
            lambda s: (
                s["component"] == "TodoApp"
                and contains_name(s["state_hints"], "todos")
                and "addTodo" in s["method_hints"]
                and "click" in s["event_hints"]
                and "DOMContentLoaded" in s["event_hints"]
                and any(q["selector"] == "todo-input" for q in s["dom_queries"])
                and contains_name(s["form_elements"], "todo")
                and ".done" in s["styles"]
            ),
        ),
    ]

    def test_fn(case):
        label, framework, code, predicate = case
        try:
            summary = parse(code, framework)
            ok = predicate(summary)
            return ok, label if ok else f"{label} | summary keys={sorted(summary.keys())}"
        except Exception as e:
            return False, f"{label} | {type(e).__name__}: {e}"

    return run("AST PRE-PARSER - framework summaries", cases, test_fn)


def test_ir_schema_and_validator():
    valid_ir = IR(
        framework="React",
        component="Counter",
        props=[IRProp(name="label")],
        state=[IRState(name="count", init="0")],
        methods=[IRMethod(name="increment", body="setCount(c => c + 1)")],
        lifecycle=[IRLifecycle(hook="onMount", body="document.title = label")],
    )

    invalid_ir = IR(
        framework="Svelte",
        component="",
        state=[IRState(name="")],
        lifecycle=[IRLifecycle(hook="afterLunch")],
    )

    cases = [
        (
            "Valid IR passes critical validation",
            lambda: validate(valid_ir).is_valid,
        ),
        (
            "IR JSON round-trip preserves component and state",
            lambda: (
                IR.from_dict(valid_ir.to_dict()).component == "Counter"
                and IR.from_dict(valid_ir.to_dict()).state[0].name == "count"
            ),
        ),
        (
            "Invalid IR reports critical errors",
            lambda: (
                not validate(invalid_ir).is_valid
                and len(validate(invalid_ir).errors) >= 3
            ),
        ),
    ]

    def test_fn(case):
        label, predicate = case
        try:
            ok = predicate()
            return bool(ok), label
        except Exception as e:
            return False, f"{label} | {type(e).__name__}: {e}"

    return run("IR SCHEMA + VALIDATOR - offline checks", cases, test_fn)


def test_live_ir_builder():
    from app.ast_layer.ir_builder import build_ir
    from app.ollama_client import OLClient

    if not OLClient().is_available():
        print("\n  Skipped - Ollama unreachable. Run: ollama serve")
        return False

    summary = parse(REACT_SAMPLE, "React")

    try:
        ir = build_ir(summary)
    except Exception as e:
        print(f"\n  ERROR - IR builder failed | {e}")
        return False

    checks = [
        ("framework is React", ir.framework == "React"),
        ("component is Dashboard", ir.component == "Dashboard"),
        ("count state exists", any(s.name == "count" for s in ir.state)),
        ("onMount lifecycle exists", any(l.hook == "onMount" for l in ir.lifecycle)),
    ]

    print("\nLIVE IR BUILDER - Qwen/Ollama extraction")
    print("-" * 60)
    passed = 0
    for label, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'} - {label}")
        if ok:
            passed += 1

    print("\n  IR preview:")
    print("  " + ir.to_json(indent=2)[:800].replace("\n", "\n  "))
    print(f"  {passed}/{len(checks)} passed")
    return passed == len(checks)


if __name__ == "__main__":
    live = "--live" in sys.argv

    print("\n" + "=" * 60)
    print("  AST + IR LAYER - TEST SUITE")
    print("=" * 60)

    p1 = test_pre_parser()
    p2 = test_ir_schema_and_validator()

    p3 = True
    if live:
        p3 = test_live_ir_builder()
    else:
        print("\n  Live skipped. Run: python test_ast_ir_layer.py --live")

    print("\n" + "=" * 60)
    print(f"  Unit : {'ALL PASSED' if p1 and p2 else 'SOME FAILED'}")
    if live:
        print(f"  Live : {'PASSED' if p3 else 'FAILED'}")
    print("=" * 60 + "\n")
