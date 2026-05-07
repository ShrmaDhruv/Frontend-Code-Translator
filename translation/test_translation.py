import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore")

from translation.response_cleaner       import clean
from translation.translation_validator  import validate_translation
from translation.prompt_builder         import build_messages
from ast_layer.ir_schema import (
    IR, IRState, IRProp, IRMethod, IRLifecycle, IRComputed, IRImport
)


# ── Nightmare source snippets ─────────────────────────────────────────────────

NIGHTMARE_VUE_OPTIONS_TO_REACT = """
<template>
  <div>
    <p>{{ fullName }}</p>
    <p>Count: {{ count }}</p>
    <button @click="increment">Add</button>
    <input v-model="firstName" placeholder="First name" />
  </div>
</template>

<script>
export default {
  name: 'UserCard',
  props: {
    userId: { type: Number, required: true }
  },
  data() {
    return {
      count:     0,
      firstName: '',
      lastName:  '',
    }
  },
  computed: {
    fullName() {
      return this.firstName + ' ' + this.lastName
    }
  },
  methods: {
    increment() {
      this.count++
    }
  },
  mounted() {
    document.title = 'UserCard'
  }
}
</script>
"""

NIGHTMARE_REACT_HOOKS_TO_VUE = """
import React, { useState, useEffect, useMemo } from 'react'

const Dashboard = ({ userId, onLogout }) => {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const itemCount = useMemo(() => data ? data.length : 0, [data])

  useEffect(() => {
    setLoading(true)
    fetch('/api/user/' + userId)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [userId])

  useEffect(() => {
    return () => { document.title = 'App' }
  }, [])

  const handleRefresh = () => {
    setData(null)
    setLoading(true)
  }

  return (
    <div>
      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
      {data && <p>{itemCount} items</p>}
      <button onClick={handleRefresh}>Refresh</button>
      <button onClick={onLogout}>Logout</button>
    </div>
  )
}

export default Dashboard
"""

NIGHTMARE_ANGULAR_TO_REACT = """
import { Component, OnInit, OnDestroy, Input } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { Router }     from '@angular/router'

@Component({
  selector: 'app-user-list',
  template: `
    <div>
      <p *ngIf="loading">Loading...</p>
      <ul>
        <li *ngFor="let user of users" (click)="navigate(user.id)">
          {{ user.name }}
        </li>
      </ul>
    </div>
  `
})
export class UserListComponent implements OnInit, OnDestroy {
  @Input() pageSize: number = 10

  users:   any[]    = []
  loading: boolean  = false

  constructor(
    private http:   HttpClient,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.loading = true
    this.http.get('/api/users').subscribe(data => {
      this.users   = data as any[]
      this.loading = false
    })
  }

  ngOnDestroy(): void {
    document.title = 'App'
  }

  navigate(id: number): void {
    this.router.navigate(['/user', id])
  }
}
"""

NIGHTMARE_REACT_TO_HTML = """
import React, { useState } from 'react'

const Counter = ({ initialCount = 0, label }) => {
  const [count,    setCount]    = useState(initialCount)
  const [history,  setHistory]  = useState([])

  const increment = () => {
    setCount(c => c + 1)
    setHistory(h => [...h, count + 1])
  }

  const decrement = () => {
    setCount(c => c - 1)
    setHistory(h => [...h, count - 1])
  }

  const reset = () => {
    setCount(initialCount)
    setHistory([])
  }

  return (
    <div className="counter">
      <h2>{label}</h2>
      <p id="count">{count}</p>
      <button onClick={increment}>+</button>
      <button onClick={decrement}>-</button>
      <button onClick={reset}>Reset</button>
      <ul>
        {history.map((h, i) => <li key={i}>{h}</li>)}
      </ul>
    </div>
  )
}

export default Counter
"""

NIGHTMARE_VUE3_TO_ANGULAR = """
<template>
  <div>
    <p>{{ greeting }}</p>
    <input v-model="name" placeholder="Enter name" />
    <button @click="submitName">Submit</button>
    <p v-if="submitted">Hello, {{ name }}!</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const name      = ref('')
const submitted = ref(false)

const greeting  = computed(() => name.value ? `Welcome, ${name.value}` : 'Welcome')

const submitName = () => {
  submitted.value = true
}

onMounted(() => {
  document.title = 'Greeting App'
})
</script>
"""

NIGHTMARE_HTML_TO_VUE = """
<!DOCTYPE html>
<html>
<head><title>Todo App</title></head>
<body>
  <div id="app">
    <input id="todo-input" type="text" placeholder="New todo" />
    <button onclick="addTodo()">Add</button>
    <ul id="todo-list"></ul>
    <p id="count">0 items</p>
  </div>
  <script>
    let todos = []

    function addTodo() {
      const input = document.getElementById('todo-input')
      const text  = input.value.trim()
      if (!text) return
      todos.push({ id: Date.now(), text, done: false })
      input.value = ''
      render()
    }

    function toggleTodo(id) {
      todos = todos.map(t => t.id === id ? { ...t, done: !t.done } : t)
      render()
    }

    function render() {
      const list  = document.getElementById('todo-list')
      const count = document.getElementById('count')
      list.innerHTML = todos.map(t =>
        `<li onclick="toggleTodo(${t.id})" style="text-decoration:${t.done ? 'line-through' : 'none'}">${t.text}</li>`
      ).join('')
      count.textContent = todos.length + ' items'
    }

    document.addEventListener('DOMContentLoaded', render)
  </script>
</body>
</html>
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

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


# ── Unit: response cleaner ────────────────────────────────────────────────────

def test_cleaner():
    cases = [
        (
            "Fenced React block with preamble",
            "Here is the React component:\n```jsx\nconst App = () => <div />\n```\nDone.",
            "React",
            "const App = () => <div />",
        ),
        (
            "Fenced Vue block with language label",
            "```vue\n<template><div /></template>\n<script setup>\n</script>\n```",
            "Vue",
            "<template><div /></template>",
        ),
        (
            "HTML with DOCTYPE marker fallback",
            "Here you go:\n<!DOCTYPE html>\n<html><body></body></html>",
            "HTML",
            "<!DOCTYPE html>",
        ),
        (
            "Think block stripped before fence extraction",
            "<think>reasoning here</think>\n```js\nconst x = 1\n```",
            "React",
            "const x = 1",
        ),
        (
            "React import marker fallback when no fence",
            "The translation:\nimport React from 'react'\nconst App = () => null",
            "React",
            "import React from 'react'",
        ),
    ]

    def test_fn(case):
        label, raw, target, expected_start = case
        result = clean(raw, target)
        ok     = result.startswith(expected_start)
        msg    = label if ok else f"{label} | got: {result[:60]!r}"
        return ok, msg

    return run("CLEANER - extraction strategies", cases, test_fn)


# ── Unit: translation validator ───────────────────────────────────────────────

def test_validator():
    def make_ir(framework, states=None, methods=None, props=None):
        return IR(
            framework = framework,
            component = "TestComp",
            state     = [IRState(name=s) for s in (states or [])],
            methods   = [IRMethod(name=m) for m in (methods or [])],
            props     = [IRProp(name=p)   for p in (props   or [])],
        )

    cases = [
        (
            "Valid React output passes",
            "import React, { useState } from 'react'\nconst TestComp = () => { const [count, setCount] = useState(0)\nreturn <div>{count}</div> }\nexport default TestComp",
            make_ir("React", states=["count"]),
            "React",
            True,
        ),
        (
            "Empty output is critical failure",
            "",
            make_ir("React"),
            "React",
            False,
        ),
        (
            "Vue markers in React output is critical failure",
            "<template><div /></template>\n<script setup>\nconst x = ref(0)\n</script>",
            make_ir("React"),
            "React",
            False,
        ),
        (
            "Valid Vue output passes",
            "<template><div>{{ count }}</div></template>\n<script setup>\nimport { ref } from 'vue'\nconst count = ref(0)\ndefineProps({ userId: Number })\n</script>",
            make_ir("Vue", states=["count"], props=["userId"]),
            "Vue",
            True,
        ),
        (
            "Valid Angular output passes",
            "import { Component } from '@angular/core'\n@Component({ selector: 'app-test', template: `<button (click)=\"saved = !saved\">{{ saved ? 'Saved' : 'Save item' }}</button>` })\nexport class TestCompComponent {\n  saved: boolean = false\n}",
            make_ir("Angular"),
            "Angular",
            True,
        ),
        (
            "Angular mutating @Input fails",
            "import { Component, Input } from '@angular/core'\n@Component({ selector: 'app-test', template: `<button (click)=\"count = count + 1\">Add</button>` })\nexport class TestCompComponent {\n  @Input() count: number = 0\n}",
            make_ir("Angular", props=["count"]),
            "Angular",
            False,
        ),
        (
            "Angular unnecessary lifecycle fails",
            "import { Component, OnInit } from '@angular/core'\n@Component({ selector: 'app-test', template: `<p>Hi</p>` })\nexport class TestCompComponent implements OnInit {\n  ngOnInit(): void { this.ready = true }\n  ready: boolean = false\n}",
            make_ir("Angular", states=["ready"]),
            "Angular",
            False,
        ),
        (
            "Angular template artifact fails",
            "import { Component } from '@angular/core'\n@Component({ selector: 'app-test', template: `<p>Hi</p>\n9f8a7b6c5d4e3f2a` })\nexport class TestCompComponent {}",
            make_ir("Angular"),
            "Angular",
            False,
        ),
        (
            "Valid HTML output passes",
            "<!DOCTYPE html>\n<html>\n<head>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n</head>\n<body>\n<p id=\"count\">0</p>\n<script>\nlet count = 0\n</script>\n</body>\n</html>",
            make_ir("HTML", states=["count"]),
            "HTML",
            True,
        ),
        (
            "HTML missing referenced DOM id fails",
            "<!DOCTYPE html>\n<html>\n<head>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n</head>\n<body>\n<script>\ndocument.getElementById('missing').addEventListener('click', submit)\n</script>\n</body>\n</html>",
            make_ir("HTML"),
            "HTML",
            False,
        ),
        (
            "HTML unsafe unguarded listener target fails",
            "<!DOCTYPE html>\n<html>\n<head>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n</head>\n<body>\n<button id=\"submit\">Go</button>\n<script>\nconst submitButton = document.getElementById('submit')\nsubmitButton.addEventListener('click', submit)\n</script>\n</body>\n</html>",
            make_ir("HTML"),
            "HTML",
            False,
        ),
        (
            "HTML invalid viewport fails",
            "<!DOCTYPE html>\n<html>\n<head>\n<meta name=\"viewport\" content=\"initial-scale=3.0\">\n</head>\n<body>\n<p>Hi</p>\n<script>\nlet count = 0\n</script>\n</body>\n</html>",
            make_ir("HTML"),
            "HTML",
            False,
        ),
        (
            "HTML inline event handler fails",
            "<!DOCTYPE html>\n<html>\n<head>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n</head>\n<body>\n<button onclick=\"increment()\">Add</button>\n<script>\nfunction increment() {}\n</script>\n</body>\n</html>",
            make_ir("HTML"),
            "HTML",
            False,
        ),
        (
            "HTML state mutation without DOM render fails",
            "<!DOCTYPE html>\n<html>\n<head>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n</head>\n<body>\n<p id=\"count\">0</p>\n<script>\nlet count = 0\nfunction increment() { count += 1 }\n</script>\n</body>\n</html>",
            make_ir("HTML", states=["count"]),
            "HTML",
            False,
        ),
        (
            "HTML event property assignment fails",
            "<!DOCTYPE html>\n<html>\n<head>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n</head>\n<body>\n<button id=\"add\">Add</button>\n<script>\nconst add = document.getElementById('add')\nif (add) { add.onclick = increment }\nfunction increment() {}\n</script>\n</body>\n</html>",
            make_ir("HTML"),
            "HTML",
            False,
        ),
    ]

    def test_fn(case):
        label, code, ir, target, expected_valid = case
        result = validate_translation(code, ir, target)
        ok     = result.is_valid == expected_valid
        msg    = label if ok else (
            f"{label} | expected valid={expected_valid}, "
            f"got valid={result.is_valid}, errors={result.errors}"
        )
        return ok, msg

    return run("VALIDATOR - translation checks", cases, test_fn)


# ── Unit: prompt builder ──────────────────────────────────────────────────────

def test_prompt_builder():
    ir = IR(
        framework = "React",
        component = "Counter",
        state     = [IRState(name="count", init="0")],
        props     = [IRProp(name="label")],
        methods   = [IRMethod(name="increment", body="setCount(c => c + 1)")],
        lifecycle = [IRLifecycle(hook="onMount", body="document.title = label")],
    )

    cases = [
        ("React → Vue messages has system + user", ir, "Vue",     2),
        ("React → Angular has system + user",      ir, "Angular", 2),
        ("React → HTML has system + user",         ir, "HTML",    2),
    ]

    def test_fn(case):
        label, source_ir, target, expected_len = case
        msgs = build_messages(source_ir, target)
        ok   = (
            len(msgs) == expected_len
            and msgs[0]["role"] == "system"
            and msgs[1]["role"] == "user"
            and source_ir.component in msgs[1]["content"]
            and target in msgs[1]["content"]
        )
        msg = label if ok else f"{label} | msgs={len(msgs)}, content check failed"
        return ok, msg

    return run("PROMPT BUILDER - message structure", cases, test_fn)


# ── Live: full pipeline ───────────────────────────────────────────────────────

def test_live():
    from translation import translate

    cases = [
        (
            "Vue Options API → React — computed and lifecycle",
            NIGHTMARE_VUE_OPTIONS_TO_REACT,
            "Vue", "React",
            ["useState", "useEffect", "export default"],
        ),
        (
            "React hooks → Vue 3 — useMemo, multiple useEffect",
            NIGHTMARE_REACT_HOOKS_TO_VUE,
            "React", "Vue",
            ["<template>", "<script setup>", "ref("],
        ),
        (
            "Angular service injection → React — HTTP, Router",
            NIGHTMARE_ANGULAR_TO_REACT,
            "Angular", "React",
            ["useState", "useEffect", "fetch"],
        ),
        (
            "React → HTML — state becomes variables, JSX becomes DOM",
            NIGHTMARE_REACT_TO_HTML,
            "React", "HTML",
            ["<!DOCTYPE", "let count", "addEventListener"],
        ),
        (
            "Vue 3 script setup → Angular — ref, computed, onMounted",
            NIGHTMARE_VUE3_TO_ANGULAR,
            "Vue", "Angular",
            ["@Component", "ngOnInit", "export class"],
        ),
        (
            "HTML todo app → Vue — DOM mutations become reactive state",
            NIGHTMARE_HTML_TO_VUE,
            "HTML", "Vue",
            ["<template>", "ref(", "defineProps"],
        ),
    ]

    print("\nLIVE - nightmare translation cases")
    print("-" * 60)
    passed = 0
    for label, code, source, target, expected_markers in cases:
        try:
            result = translate(code, source=source, target=target)
            markers_found = all(m in result.code for m in expected_markers)
            ok = result.ok and markers_found

            if ok:
                passed += 1
            print(f"  {'PASS' if ok else 'FAIL'} - {label}")

            if not result.ok:
                print(f"    errors:   {result.errors}")
            if not markers_found:
                missing = [m for m in expected_markers if m not in result.code]
                print(f"    missing markers: {missing}")
            if result.warnings:
                print(f"    warnings: {result.warnings}")

        except Exception as e:
            print(f"  ERROR - {label} | {e}")

    print(f"  {passed}/{len(cases)} passed")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    live = "--live" in sys.argv

    print("\n" + "=" * 60)
    print("  TRANSLATION - NIGHTMARE TEST SUITE")
    print("=" * 60)

    p1 = test_cleaner()
    p2 = test_validator()
    p3 = test_prompt_builder()

    if live:
        test_live()
    else:
        print("\n  Live skipped. Run: python test_translation.py --live")

    print("\n" + "=" * 60)
    print(f"  Unit : {'ALL PASSED' if p1 and p2 and p3 else 'SOME FAILED'}")
    print("=" * 60 + "\n")
