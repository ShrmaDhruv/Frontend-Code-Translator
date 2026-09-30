"""
test_detector.py — Test suite for the framework detector.

Run with:
    python test_detector.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.detection.rule_detector import detect

# ─────────────────────────────────────────────
# SAMPLE CODE SNIPPETS
# ─────────────────────────────────────────────

REACT_SAMPLE = """
import React from "react";

class Counter extends React.Component {
  state = {
    count: 0
  };

  methods = {
    increment: () =>
      this.setState((prev) => ({ count: prev.count + 1 })),
    decrement: () =>
      this.setState((prev) => ({ count: prev.count - 1 }))
  };

  render() {
    const { count } = this.state;

    return (
      <section>
        <header>Counter</header>
        <div>{count}</div>
        <button onClick={this.methods.increment}>+</button>
        <button onClick={this.methods.decrement}>-</button>
      </section>
    );
  }
}

export default Counter;
"""

VUE_SAMPLE = """
<template>
  <div class="card">
    <h2>{{ name }}</h2>
    <p>Age: {{ age }}</p>
    <button @click="likes++">Likes: {{ likes }}</button>
    <input v-model="search" placeholder="Search..." />
    <ul>
      <li v-for="item in items" :key="item.id">{{ item.name }}</li>
    </ul>
  </div>
</template>

<script setup>
import { ref, defineProps } from 'vue';

const props = defineProps({ name: String, age: Number });
const likes = ref(0);
const search = ref('');
const items = ref([{ id: 1, name: 'One' }]);
</script>

<style scoped>
.card { padding: 1rem; }
</style>
"""

ANGULAR_SAMPLE = """
import { Component, OnInit, Input, Output, EventEmitter } from '@angular/core';

@Component({
  selector: 'app-user-card',
  template: `
    <div class="card">
      <h2>{{ name }}</h2>
      <button (click)="onLike()">Like</button>
      <ul>
        <li *ngFor="let item of items">{{ item }}</li>
      </ul>
      <div *ngIf="showDetails">Details visible</div>
    </div>
  `
})
export class UserCardComponent implements OnInit {
  @Input() name: string = '';
  @Output() liked = new EventEmitter<void>();
  items = ['One', 'Two', 'Three'];
  showDetails = true;

  ngOnInit() {
    console.log('Component initialized');
  }

  onLike() {
    this.liked.emit();
  }
}
"""

HTML_SAMPLE = """
<!DOCTYPE html>
<html>
<head>
<title>Form Validation + Backend</title>
</head>
<body>

<h2>Register</h2>

<form id="form">
<input type="text" id="name" placeholder="Name"><br><br>
<input type="email" id="email" placeholder="Email"><br><br>
<input type="password" id="password" placeholder="Password"><br><br>

<button type="submit">Submit</button>
</form>

<p id="msg"></p>

<script>

const form = document.getElementById("form");

form.addEventListener("submit", async function(e){

    e.preventDefault();

    const name = document.getElementById("name").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    // basic validation
    if(name === "" || email === "" || password === ""){
        document.getElementById("msg").innerText = "All fields required";
        return;
    }

    try{

        const res = await fetch("http://localhost:3000/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name,
                email,
                password
            })
        });

        const data = await res.json();

        document.getElementById("msg").innerText = data.message;

    }catch(err){
        console.log(err);
    }

});

</script>

</body>
</html>
"""

# Vue 2 Options API with no imports — ambiguous but should still detect Vue
AMBIGUOUS_VUE_SAMPLE = """
export default {
  data() {
    return { count: 0 };
  },
  methods: {
    increment() { this.count++; }
  }
}
"""

# React without JSX (createElement style)
REACT_NO_JSX_SAMPLE = """
import React from 'react';
import { useState } from 'react';

function Counter() {
  const [count, setCount] = useState(0);
  return React.createElement('div', null,
    React.createElement('h2', null, 'Count: ' + count),
    React.createElement('button', { onClick: () => setCount(count + 1) }, 'Increment')
  );
}

export default Counter;
"""


# ─────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────

def run_tests():
    test_cases = [
        ("React — JSX + Hooks",        REACT_SAMPLE,        "React"),
        ("Vue — SFC Composition API",  VUE_SAMPLE,          "Vue"),
        ("Angular — Decorators",       ANGULAR_SAMPLE,      "Angular"),
        ("HTML — Vanilla JS",          HTML_SAMPLE,         "HTML"),
        ("Vue — Options API (no import)", AMBIGUOUS_VUE_SAMPLE, "Vue"),
        ("React — createElement (no JSX)", REACT_NO_JSX_SAMPLE, "React"),
    ]

    print("=" * 65)
    print("  FRONTEND FRAMEWORK DETECTOR — Test Suite")
    print("=" * 65)

    passed = 0
    for label, code, expected in test_cases:
        result = detect(code)
        ok = result.detected == expected
        status = "✅ PASS" if ok else "❌ FAIL"
        if ok:
            passed += 1

        print(f"\n{'─' * 65}")
        print(f"  Test    : {label}")
        print(f"  Expected: {expected}   Got: {result.detected}   {status}")
        print(f"{'─' * 65}")
        print(result.summary())

    print(f"\n{'=' * 65}")
    print(f"  Results: {passed}/{len(test_cases)} passed")
    print(f"{'=' * 65}\n")


if __name__ == "__main__":
    run_tests()
