"""
Tree-sitter extractor tests on components that are NOT in the eval dataset
(the dataset scores are optimistic because the extractors were built against it).

Run: python -m pytest tests/test_treesitter_extractors.py -q
"""

import json
from pathlib import Path

import pytest

from app.ir.builder import build_facts_ir, merge_ir, review_reasons
from app.ir.schema import IR, IRLifecycle, IRMethod, IRState
from app.ir.pre_parser import parse


def names(items):
    return [i["name"] if isinstance(i, dict) else i for i in items]


def hooks(summary):
    return [h["hook"] for h in summary["lifecycle_hints"]]


# ── React ─────────────────────────────────────────────────────────────────────

REACT_TS = """
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'

type Props = { items: string[]; pageSize?: number }

function helper(x: number) { return x * 2 }

export const Paginated: React.FC<Props> = ({ items, pageSize = 10 }) => {
  const [page, setPage] = useState<number>(0)
  const [query, setQuery] = useState(() => '')
  const inputRef = useRef<HTMLInputElement>(null)
  const MAX = 100
  const filtered = useMemo(() => items.filter(i => i.includes(query)), [items, query])
  const pageCount = Math.ceil(filtered.length / pageSize)
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'ArrowRight') setPage(p => p + 1) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => { document.title = `Page ${page}` }, [page])

  const next = useCallback(() => setPage(p => Math.min(p + 1, pageCount - 1)), [pageCount])
  function prev() { setPage(p => Math.max(p - 1, 0)) }

  return (
    <div>
      <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)} />
      {visible.length === 0 ? <p>Empty</p> : <ul>{visible.map(v => <li key={v}>{v}</li>)}</ul>}
      <button onClick={prev}>Prev</button>
      <button onClick={next}>Next</button>
    </div>
  )
}
"""

REACT_CLASS = """
import React, { Component } from 'react'

export default class Clock extends Component {
  state = { now: new Date(), ticks: 0 }

  componentDidMount() {
    this.timer = setInterval(this.tick, 1000)
  }

  componentWillUnmount() {
    clearInterval(this.timer)
  }

  tick = () => {
    this.setState({ now: new Date(), ticks: this.state.ticks + 1 })
  }

  render() {
    return <p>{this.props.label}: {this.state.now.toLocaleTimeString()}</p>
  }
}
"""


def test_react_typescript_function_component():
    s = parse(REACT_TS, "React")
    assert s["extractor"] == "tree-sitter" and not s["parse_errors"]
    assert s["component"] == "Paginated"
    assert names(s["props"]) == ["items", "pageSize"]
    assert {p["name"]: p["default"] for p in s["props"]} == {"items": None, "pageSize": "10"}
    assert names(s["state_hints"]) == ["page", "query", "inputRef"]
    assert {c["name"] for c in s["computed_hints"]} == {"filtered", "pageCount", "visible"}
    assert names(s["constants"]) == ["MAX"]
    assert names(s["method_hints"]) == ["next", "prev"]
    assert "helper" not in names(s["method_hints"])
    assert hooks(s) == ["onMount", "onDestroy", "onUpdate"]
    destroy = next(h for h in s["lifecycle_hints"] if h["hook"] == "onDestroy")
    assert "removeEventListener" in destroy["body"]
    update = next(h for h in s["lifecycle_hints"] if h["hook"] == "onUpdate")
    assert update["deps"] == ["page"]
    assert s["template_hints"]["loops"] == [{"item": "v", "source": "visible"}]
    assert set(s["event_hints"]) == {"change", "click"}


def test_react_class_component():
    s = parse(REACT_CLASS, "React")
    assert s["component"] == "Clock"
    assert names(s["props"]) == ["label"]
    assert names(s["state_hints"]) == ["now", "ticks"]
    assert hooks(s) == ["onMount", "onDestroy"]
    assert names(s["method_hints"]) == ["tick"]


# ── Vue ───────────────────────────────────────────────────────────────────────

VUE_TS_SETUP = """
<template>
  <form @submit.prevent="save">
    <input v-model="draft.title" />
    <li v-for="(tag, i) in tags" :key="i">{{ tag }}</li>
    <p v-if="dirty">Unsaved</p>
    <slot name="footer" />
  </form>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<{ id: number; tags?: string[] }>(), { tags: () => [] })
const emit = defineEmits(['saved'])

const draft = reactive({ title: '' })
const saving = ref(false)
let timer: number | undefined

const dirty = computed({
  get: () => draft.title.length > 0,
  set: (v: boolean) => { if (!v) draft.title = '' },
})

async function save() {
  saving.value = true
  emit('saved', props.id)
}

watch(() => props.id, () => { draft.title = '' })
onMounted(() => { timer = window.setInterval(save, 30000) })
onBeforeUnmount(() => clearInterval(timer))
</script>
"""

VUE_OPTIONS = """
<script>
export default defineComponent({
  name: 'Cart',
  props: ['items', 'currency'],
  data: () => ({ open: false, coupon: '' }),
  computed: {
    total() { return this.items.reduce((s, i) => s + i.price, 0) },
    label: { get() { return this.currency + this.total }, set(v) {} },
  },
  methods: {
    toggle() { this.open = !this.open },
    apply: function (code) { this.coupon = code },
  },
  mounted() { this.toggle() },
  unmounted() {},
})
</script>
"""


def test_vue_typescript_setup():
    s = parse(VUE_TS_SETUP, "Vue")
    assert s["extractor"] == "tree-sitter" and not s["parse_errors"]
    assert s["is_setup"]
    assert names(s["props"]) == ["id", "tags"]
    tags = next(p for p in s["props"] if p["name"] == "tags")
    assert tags["required"] is False and tags["default"] == "() => []"
    assert names(s["state_hints"]) == ["draft", "saving"]
    assert names(s["variables"]) == ["timer"]
    assert [c["name"] for c in s["computed_hints"]] == ["dirty"]
    assert "draft.title.length > 0" in s["computed_hints"][0]["expression"]
    assert names(s["method_hints"]) == ["save"]
    assert hooks(s) == ["onMount", "onBeforeDestroy"]
    assert s["emits"] == ["saved"]
    t = s["template_hints"]
    assert t["loops"] == [{"item": "tag", "source": "tags"}]
    assert t["conditionals"] == ["dirty"]
    assert "submit" in t["events"] and t["models"] == ["draft.title"] and t["slots"] == ["footer"]


def test_vue_options_define_component():
    s = parse(VUE_OPTIONS, "Vue")
    assert s["component"] == "Cart"
    assert names(s["props"]) == ["items", "currency"]
    assert names(s["state_hints"]) == ["open", "coupon"]
    assert [c["name"] for c in s["computed_hints"]] == ["total", "label"]
    assert s["computed_hints"][1]["deps"] == ["currency", "total"]
    assert names(s["method_hints"]) == ["toggle", "apply"]
    assert s["method_hints"][1]["params"] == ["code"]
    assert hooks(s) == ["onMount", "onDestroy"]


# ── Angular ───────────────────────────────────────────────────────────────────

ANGULAR = """
import { Component, Input, Output, EventEmitter, OnInit, OnDestroy } from '@angular/core'
import { HttpClient } from '@angular/common/http'
import { Subscription } from 'rxjs'

@Component({
  selector: 'app-user-list',
  templateUrl: './user-list.component.html',
  styles: ['.active { color: green; }', '.muted { color: gray; }'],
})
export class UserListComponent implements OnInit, OnDestroy {
  @Input({ required: true }) groupId!: number
  @Input() filter = ''
  @Output() selected = new EventEmitter<number>()
  users: User[] = []
  loading = false
  private sub?: Subscription

  constructor(private http: HttpClient, public zone: NgZone) {}

  get visible(): User[] {
    return this.users.filter(u => u.name.includes(this.filter))
  }

  ngOnInit(): void {
    this.loading = true
    this.sub = this.http.get<User[]>(`/api/groups/${this.groupId}`).subscribe(u => {
      this.users = u
      this.loading = false
    })
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe()
  }

  select(user: User, index: number): void {
    this.selected.emit(user.id)
  }
}
"""


def test_angular_component():
    s = parse(ANGULAR, "Angular")
    assert s["extractor"] == "tree-sitter" and not s["parse_errors"]
    assert s["component"] == "UserList"
    assert s["template_url"] == "./user-list.component.html"
    assert names(s["props"]) == ["groupId", "filter"]
    group = next(p for p in s["props"] if p["name"] == "groupId")
    assert group["required"] is True and group["type"] == "number"
    assert s["outputs"] == ["selected"]
    assert names(s["state_hints"]) == ["users", "loading"]
    assert names(s["variables"]) == ["sub"]
    assert s["injected_services"] == [
        {"name": "http", "type": "HttpClient"}, {"name": "zone", "type": "NgZone"},
    ]
    assert [c["name"] for c in s["computed_hints"]] == ["visible"]
    assert s["computed_hints"][0]["deps"] == ["filter", "users"]
    assert hooks(s) == ["onMount", "onDestroy"]
    assert names(s["method_hints"]) == ["select"]
    assert s["method_hints"][0]["params"] == ["user", "index"]
    assert ".active" in s["styles"] and ".muted" in s["styles"]


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Stop Watch</title>
  <style>.running { color: green; }</style>
  <script src="https://cdn.example.com/lib.js"></script>
</head>
<body>
  <p id="display" class="big mono">0.0</p>
  <input id="lap-name" name="lapName" type="text" />
  <button onclick="toggle()">Start</button>
  <script>
    const TICK_MS = 100
    const laps = []
    let elapsed = 0
    let handle = null

    const format = (ms) => (ms / 1000).toFixed(1)

    function toggle() {
      if (handle) { clearInterval(handle); handle = null; return }
      handle = setInterval(() => { elapsed += TICK_MS; render() }, TICK_MS)
    }

    function render() {
      document.getElementById('display').textContent = format(elapsed)
      localStorage.setItem('elapsed', elapsed)
    }

    window.onload = () => { elapsed = Number(localStorage.getItem('elapsed') || 0); render() }
    window.addEventListener('beforeunload', () => clearInterval(handle))
  </script>
</body>
</html>
"""


def test_html_document():
    s = parse(HTML, "HTML")
    assert s["extractor"] == "tree-sitter" and not s["parse_errors"]
    assert s["component"] == "StopWatch"
    assert names(s["state_hints"]) == ["laps", "elapsed"]
    assert names(s["variables"]) == ["handle"]
    assert names(s["constants"]) == ["TICK_MS"]
    assert names(s["method_hints"]) == ["format", "toggle", "render"]
    assert hooks(s) == ["onMount", "onDestroy"]
    assert "render()" in s["lifecycle_hints"][0]["body"]
    assert s["external_scripts"] == ["https://cdn.example.com/lib.js"]
    assert s["element_ids"] == ["display", "lap-name"]
    assert s["element_classes"] == ["big", "mono"]
    assert s["inline_events"] == [{"event": "click", "handler": "toggle()"}]
    assert s["storage_hints"] == ["localStorage"]
    assert ".textContent=" in s["dom_mutations"]
    assert ".running" in s["styles"]


# ── Fallback / IR building ────────────────────────────────────────────────────

def test_regex_fallback_when_forced(monkeypatch):
    monkeypatch.setenv("AST_PARSER", "regex")
    assert parse(REACT_TS, "React")["extractor"] == "regex"


def test_facts_ir_is_valid_and_needs_no_review():
    for code, framework in [(REACT_TS, "React"), (VUE_TS_SETUP, "Vue"), (ANGULAR, "Angular"), (HTML, "HTML")]:
        summary = parse(code, framework)
        ir = build_facts_ir(summary)
        assert review_reasons(summary, ir) == [], framework
        assert all(m.body for m in ir.methods), framework


def test_review_triggered_by_broken_source():
    summary = parse("export default function Broken( { return <div> }", "React")
    assert "source has syntax errors" in review_reasons(summary, build_facts_ir(summary))


def test_merge_keeps_facts_and_adds_only_new_names():
    facts = IR(framework="React", component="A",
               state=[IRState(name="count", init="0")],
               methods=[IRMethod(name="inc", body="setCount(c => c + 1)")],
               lifecycle=[IRLifecycle(hook="onMount", body="start()")])
    llm = IR(framework="React", component="Other",
             state=[IRState(name="count", init="999"), IRState(name="extra")],
             methods=[IRMethod(name="inc", body="WRONG")],
             lifecycle=[IRLifecycle(hook="onMount", body="WRONG"), IRLifecycle(hook="onDestroy", body="stop()")])
    merged = merge_ir(facts, llm)
    assert merged.component == "A"
    assert [(s.name, s.init) for s in merged.state] == [("count", "0"), ("extra", None)]
    assert [m.body for m in merged.methods] == ["setCount(c => c + 1)"]
    assert [(h.hook, h.body) for h in merged.lifecycle] == [("onMount", "start()"), ("onDestroy", "stop()")]


@pytest.mark.parametrize("case", json.loads(
    (Path(__file__).resolve().parents[1] / "evals/dataset/cases.json").read_text(encoding="utf-8")
)["cases"], ids=lambda c: c["id"])
def test_dataset_components_parse_cleanly(case):
    code = (Path(__file__).resolve().parents[1] / "evals/dataset" / case["file"]).read_text(encoding="utf-8")
    summary = parse(code, case["source"])
    assert summary["extractor"] == "tree-sitter"
    assert not summary["parse_errors"]
