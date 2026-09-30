"""
Deterministic output fixes (response_cleaner) and checks (translation_validator):
missing imports, empty functions, undefined template references, DOM APIs in components.

Run: python -m pytest tests/test_translation_fixes.py -q
"""

from app.ir.schema import IR
from app.translation import empty_functions
from app.translation.imports import add_missing_imports, find_missing
from app.translation.response_cleaner import _sanitize_output
from app.translation.template_refs import undefined_template_refs
from app.translation.validator import validate_translation


def errors_for(code: str, target: str) -> list[str]:
    return validate_translation(code, IR(framework="HTML", component="App"), target).errors


# ── Missing imports ───────────────────────────────────────────────────────────

VUE_MISSING = """<template><p>{{ doubled }}</p></template>

<script setup>
import { ref } from 'vue'
const n = ref(1)
const doubled = computed(() => n.value * 2)
onMounted(() => { n.value = 2 })
</script>"""


def test_vue_missing_imports_are_added_to_existing_import():
    fixed = add_missing_imports(VUE_MISSING, "Vue")
    assert "import { ref, computed, onMounted } from 'vue'" in fixed
    assert find_missing(fixed, "Vue") == []


def test_vue_import_statement_created_when_absent():
    code = "<template><p>{{ n }}</p></template>\n<script setup>\nconst n = ref(0)\n</script>"
    fixed = add_missing_imports(code, "Vue")
    assert "<script setup>\nimport { ref } from 'vue'\nconst n = ref(0)" in fixed


def test_react_missing_hooks_added():
    assert "import React, { useState, useMemo } from 'react'" in add_missing_imports(
        "import React, { useState } from 'react'\nconst a = useMemo(() => 1, [])", "React")
    assert "import React, { useEffect } from 'react'" in add_missing_imports(
        "import React from 'react'\nuseEffect(() => { go() }, [])", "React")
    assert add_missing_imports("const [a] = useState(0)", "React").startswith(
        "import { useState } from 'react'\n")


def test_react_member_calls_and_local_definitions_are_not_missing():
    assert find_missing("import React from 'react'\nReact.useState(0)", "React") == []
    assert find_missing("function useState() {}\nuseState()", "React") == []


# ── Empty functions ───────────────────────────────────────────────────────────

def test_empty_function_names():
    code = """
function render() {
}
const noop = () => {}
async function load() { await x() }
constructor(private http: HttpClient) {}
if (x) {}
  refresh(): void {}
"""
    assert empty_functions.names(code) == ["render", "noop", "refresh"]


def test_empty_function_and_its_calls_are_removed_then_empty_hook_cleaned():
    code = """<script setup>
import { ref, onMounted } from 'vue'
const count = ref(0)
function render() {
}
function inc() {
  count.value++
  render()
}
onMounted(() => {
  render()
})
</script>"""
    cleaned = _sanitize_output(code, "Vue")
    assert "render" not in cleaned
    assert "onMounted" not in cleaned
    assert "count.value++" in cleaned


def test_empty_function_kept_when_still_referenced():
    code = "function noop() {}\nbutton.addEventListener('click', noop)"
    assert empty_functions.remove(code) == code
    assert any("'noop' has an empty body" in e for e in errors_for(
        "<!DOCTYPE html><html><body><script>\n" + code + "\n</script></body></html>", "HTML"))


def test_angular_implements_pruned_after_empty_hook_removed():
    code = """import { Component, OnInit, OnDestroy } from '@angular/core';
@Component({ selector: 'a', template: `<p>{{ n }}</p>` })
export class AComponent implements OnInit, OnDestroy {
  n = 0;
  ngOnInit() {
  }
  ngOnDestroy() { clearInterval(this.id) }
}"""
    cleaned = _sanitize_output(code, "Angular")
    assert "implements OnDestroy {" in cleaned
    assert "OnInit" not in cleaned


# ── Undefined template references ─────────────────────────────────────────────

def test_vue_template_undefined_identifier():
    code = """<template>
  <li v-for="(todo, i) in todos" :key="todo.id" @click="toggle(todo.id, $event)">{{ i }} {{ todo.text }}</li>
  <p v-if="count > LIMIT">{{ parity }}</p>
  <Child #default="{ item }">{{ item.name }}</Child>
</template>
<script setup>
import { ref } from 'vue'
const props = defineProps({ todos: Array })
const LIMIT = 3
const count = ref(0)
function toggle(id) {}
</script>"""
    assert undefined_template_refs(code, "Vue") == ["parity"]


def test_angular_template_undefined_identifier():
    code = """import { Component, Input } from '@angular/core';
@Component({
  selector: 'a',
  template: `
    <input #box (keyup.enter)="add(box.value)" [(ngModel)]="draft" />
    <li *ngFor="let t of todos; let i = index; trackBy: byId">{{ i }} {{ t.text | uppercase }}</li>
    <p *ngIf="user$ | async as user; else empty">{{ user.name }}</p>
    <ng-template #empty>{{ remaining }}</ng-template>
  `,
})
export class AComponent {
  @Input() todos = [];
  draft = '';
  user$ = null;
  add(v) { this.todos.push(v) }
  byId(i, t) { return t.id }
}"""
    assert undefined_template_refs(code, "Angular") == ["remaining"]


def test_template_refs_ignores_unparseable_and_other_targets():
    assert undefined_template_refs("<template><p>{{ a b c }}</p></template><script setup></script>", "Vue") == []
    assert undefined_template_refs("const x = <p>{y}</p>", "React") == []


# ── DOM APIs in component output ──────────────────────────────────────────────

def test_dom_api_in_component_output_is_an_error():
    react = "import React from 'react'\nexport default function A() { document.getElementById('x'); return <p/> }"
    assert any("document.getElementById" in e for e in errors_for(react, "React"))
    html = "<!DOCTYPE html><html><body><p id='x'></p><script>document.getElementById('x')</script></body></html>"
    assert not any("DOM APIs" in e for e in errors_for(html, "HTML"))
