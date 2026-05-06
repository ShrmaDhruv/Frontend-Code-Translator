"""
translation/prompt_builder.py

Builds Ollama prompt messages for framework translation.

Takes a validated IR instance and a target framework string, and
constructs a messages list for Phi3Client.chat(). The system prompt
contains deep per-framework instructions so the model knows exactly
what syntax to produce for each target.

The IR is serialised as JSON and embedded in the user message.
The model receives structured component intent — never raw source code.

Supported target frameworks:
    React    → functional component, hooks, JSX
    Vue      → Vue 3 SFC with <script setup> and Composition API
    Angular  → TypeScript class component with decorator
    HTML     → vanilla HTML with inline script, no framework

Per-framework instructions cover:
    - File/component structure
    - State management syntax
    - Lifecycle hook mapping
    - Event binding syntax
    - Props/inputs syntax
    - Computed property syntax
    - Import requirements
"""

from ast_layer.ir_schema import IR

SUPPORTED_TARGETS = {"React", "Vue", "Angular", "HTML"}

_BASE_SYSTEM = """You are an expert frontend code translator.
You receive original source code plus a framework-agnostic IR (Intermediate
Representation) as JSON and translate it into the requested target framework.

Priority:
  - Treat the ORIGINAL SOURCE CODE as canonical and highest priority
  - Use the IR as a supporting checklist, not as the only source of truth
  - If the source code and IR conflict, follow the source code
  - Preserve rendered structure, event behavior, state updates, imports,
    props, methods, lifecycle behavior, text content, classes, and styles
  - Ignore any IR entry that is not supported by the original source code

IR field meanings:
  props      — inputs the component receives from its parent
  state      — internal mutable values (init is the initial value)
  computed   — derived values that update when their dependencies change
  lifecycle  — side effects tied to component mount/destroy/update
  methods    — functions defined on the component
  imports    — external modules the component depends on
  template   — structural hints about what the component renders
  styles     — raw CSS belonging to this component

Lifecycle hook mapping:
  onMount        → runs once after the component is inserted into the DOM
  onDestroy      → runs before the component is removed
  onBeforeMount  → runs just before insertion
  onUpdate       → runs after every reactive update
  onBeforeUpdate → runs just before a reactive update
  onCreate       → runs when the component instance is created
  onChanges      → runs when input props change

Rules that always apply:
  - Preserve all state names, method names, and prop names exactly
  - Preserve method body logic as closely as possible
  - Do not add features not present in the source code
  - Do not remove features that are present in the source code
  - Use the IR to recover structure only when the source code is ambiguous
  - Never add empty placeholder lifecycle hooks, empty placeholder methods, or
    placeholder imports
  - When translating React useState setters, convert setName(...) calls into
    the target framework's state update syntax; never copy React setter calls
    into Vue, Angular, or HTML output
  - Do not include comments of any kind in the translated code
  - Do not include line comments, block comments, JSX comments, HTML comments,
    template comments, docstrings, or explanatory annotations
  - Do not output //, /* */, {/* */}, <!-- -->, or any other comment syntax
  - Do not emit random strings, hex fragments, debug artifacts, or any text
    that did not come from the original component
  - Return ONLY the translated code — no explanation, no markdown fences,
    no preamble, no comments about what you changed"""


_REACT_INSTRUCTIONS = """
Target: React (functional component with hooks only)

Structure rules:
  - Use arrow function component:
      const ComponentName = ({ ...props }) => { ... }
  - Export default at bottom:
      export default ComponentName
  - All imports at the top

 Strict Rules (VERY IMPORTANT):

- NEVER use document.getElementById, querySelector, or direct DOM access
- NEVER initialize state using DOM values
- ALWAYS treat React state as the single source of truth
- NEVER use uncontrolled inputs when using state (always bind value + onChange)
- NEVER mutate state directly (no name = "abc")
- ALWAYS use setter (setName)
- NEVER use React class components
- NEVER mix frameworks (Vue syntax, Angular, etc.)
- NEVER forget event.preventDefault() in form submit handlers
- NEVER leave JSX tags unclosed


State:
  - const [name, setName] = useState(initialValue)
  - Initialize with plain values only ("", 0, [], {})
  - NEVER use DOM reads during initialization


Computed:
  - const value = useMemo(() => expression, [deps])
  - Include correct dependencies array


Lifecycle:
  - onMount       → useEffect(() => { ... }, [])
  - onDestroy     → useEffect(() => { return () => { ... } }, [])
  - onUpdate      → useEffect(() => { ... })
  - onChanges     → useEffect(() => { ... }, [deps])


Props:
  - Destructure in function signature:
      const App = ({ prop1, prop2 = defaultValue }) => {}


Methods:
  - const methodName = (params) => { ... }
  - async allowed


Events (JSX only):
  - onClick={handler}
  - onChange={handler}
  - onInput={handler}
  - onSubmit={handler}

  Rules:
  - Handler MUST exist
  - For forms: ALWAYS call event.preventDefault()
  - NEVER use inline DOM access


Form Handling Rules:
  - ALWAYS use controlled components:
      value={state} + onChange={(e) => setState(e.target.value)}
  - NEVER read values from DOM
  - Use .trim() ONLY during validation, not initialization


Template (JSX):
  - Return JSX
  - Use className (NOT class)
  - Self-close tags: <input />, <br />
  - Conditionals: {cond && <A />} or ternary
  - Lists: items.map((item, i) => <El key={i} />)


Error Handling:
  - Store errors in state:
      const [error, setError] = useState("")
  - Update via setError(...)
  - Display using JSX


Imports:
  - import React from 'react'
  - import { useState, useEffect, useMemo } from 'react' (as needed)"""


_VUE_INSTRUCTIONS = """
Target: Vue 3 SFC using <script setup> and Composition API only

Structure:
  <template>
    ...
  </template>

  <script setup>
  import { ref, computed, onMounted, onUnmounted, onUpdated, onBeforeMount, onBeforeUnmount } from 'vue'
  ...
  </script>

  <style scoped>
  ...
  </style>


Strict Rules (VERY IMPORTANT):

- NEVER use document.getElementById, querySelector, or direct DOM access
- NEVER initialize refs using DOM values
- ALWAYS use v-model for form inputs instead of manual DOM reads
- NEVER mix Options API (data, methods, mounted, etc.)
- NEVER use React patterns (setState, useState, etc.)
- NEVER import or use event names (click, input, change) from Vue
- NEVER use watchEffect for handling DOM events
- Every template event must reference a defined function


State:
  - Each state → const name = ref(initialValue)
  - ALWAYS initialize with plain values ("" | 0 | [] | {})
  - NEVER use DOM to initialize state
  - Use name.value in script, name in template


Computed:
  - const name = computed(() => expression)


Lifecycle:
  - onMounted(() => { ... })
  - onUnmounted(() => { ... })
  - onUpdated(() => { ... })
  - onBeforeMount(() => { ... })
  - onBeforeUnmount(() => { ... })


Props:
  - const props = defineProps({
      propName: { type: Type, required: boolean, default: value }
    })


Methods:
  - const methodName = (params) => { ... }
  - async allowed


Events (Template only):
  - @click="handler"
  - @input="handler"
  - @change="handler"
  - @submit.prevent="handler"

  Rules:
  - Handler MUST exist in <script setup>
  - No inline DOM access
  - No watch/watchEffect for events


Template:
  - v-if="condition"
  - v-for="item in items" :key="item.id"
  - v-model="state"
  - :prop="value"
  - class (NOT className)


Form Handling Rules:
  - ALWAYS use v-model for inputs
  - ALWAYS validate using reactive state (ref values)
  - NEVER read values using document.getElementById
  - Use .trim() during validation, NOT during initialization


Error Handling:
  - Store errors in ref (e.g., const errorMsg = ref(""))
  - Update errorMsg.value inside methods
  - Display errors using {{ errorMsg }}


Imports (only when needed):
  ref, reactive, computed, watch,
  onMounted, onUnmounted, onUpdated,
  onBeforeMount, onBeforeUnmount"""


_ANGULAR_INSTRUCTIONS = """
Target: Angular TypeScript class component

Structure:
  import { Component } from '@angular/core'
  - Add Input, Output, EventEmitter, and lifecycle interfaces to the
    @angular/core import only when they are actually used

  @Component({
    selector: 'app-component-name',
    template: `...`
  })
  export class ComponentNameComponent {
    ...
  }

State:
  - Each IRState entry → public name: type = init  (class field)
  - Preserve every initial state value exactly
  - State from React useState is local component state, not @Input()
  - Use appropriate TypeScript types: string, number, boolean, any, T[]

Computed:
  - Each IRComputed entry → get name(): type { return expression }
  - Getter syntax, no decorator needed
  - Do not add getters or setters unless the source has a real derived value
  - Remove unused or redundant getters/setters

Lifecycle:
  - onMount   → ngOnInit(): void { body }    implement OnInit
  - onDestroy → ngOnDestroy(): void { body } implement OnDestroy
  - onUpdate  → ngDoCheck(): void { body }   implement DoCheck
  - onChanges → ngOnChanges(changes): void   implement OnChanges
  - Add lifecycle hooks only when the original source has equivalent side
    effects; never add ngOnInit, ngDoCheck, or other hooks for placeholder
    initialization or empty bodies

Props:
  - Each IRProp → @Input() propName: type
  - Required props have no default, optional use = defaultValue
  - Import Input from '@angular/core'
  - Never mutate an @Input() property directly
  - If a received input needs local edits, copy it into local state and update
    that local state
  - If a state change must notify the parent, use @Output() with EventEmitter

Outputs:
  - EventEmitter fields → @Output() eventName = new EventEmitter<type>()
  - Import Output, EventEmitter from '@angular/core'
  - Add an @Output() EventEmitter when the source behavior calls a parent
    callback or when changed input-like data needs to propagate upward

Methods:
  - Each IRMethod → methodName(params: types): returnType { body }
  - Async methods → async methodName(...): Promise<type> { body }
  - Avoid dead code and redundant wrapper methods

Events (in template):
  - events.click  → (click)="handler()"
  - events.change → (change)="handler($event)"
  - events.input  → (input)="handler($event)"
  - events.submit → (ngSubmit)="handler()"
  - React onClick must become Angular (click) with the same handler logic
  - Inline React state updates must become equivalent Angular expressions,
    for example onClick={() => setSaved(!saved)} → (click)="saved = !saved"

Template:
  - Use *ngIf="condition" for conditionals
  - Use *ngFor="let item of items; trackBy: trackFn" for loops
  - Use [propName]="value" for property bindings
  - Use [(ngModel)]="stateName" for two-way binding
  - Use class instead of className
  - Preserve ternary order exactly: condition ? A : B must stay condition ? A : B
  - Use Angular interpolation exactly: {{ condition ? 'A' : 'B' }}
  - Do not flip conditional rendering logic or swap ternary branches
  - Do not add [class], [ngClass], or extra class bindings unless the React
    source had equivalent dynamic class behavior
  - Do not include hex fragments, random strings, markdown artifacts, or any
    unexpected text inside the template

Implements clause:
  - Add OnInit if onMount lifecycle present
  - Add OnDestroy if onDestroy lifecycle present
  - Import all implemented interfaces from '@angular/core'
  - Keep the component clean and minimal; no unused imports, empty hooks,
    dead methods, extra bindings, or boilerplate"""


_HTML_INSTRUCTIONS = """
Target: Vanilla HTML + CSS + JavaScript (NO framework)

Structure:
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ComponentName</title>

    <style>
      /* CSS here */
    </style>
  </head>

  <body>
    <!-- HTML markup here -->

    <script>
      // JavaScript here
    </script>
  </body>
  </html>


Strict Rules (VERY IMPORTANT)

- NEVER use React, Vue, Angular, JSX, hooks, or framework syntax
- NEVER use inline event attributes:
    onclick=""
    onchange=""
    oninput=""
    onsubmit=""
- NEVER use React-style CSS:
    borderRadius
    boxShadow
    alignItems
  Use standard CSS:
    border-radius
    box-shadow
    align-items

- NEVER use duplicate id attributes
- Use class for repeated elements
- NEVER access DOM elements before they exist
- NEVER call addEventListener on null elements
- NEVER leave empty DOMContentLoaded blocks
- NEVER scatter event listeners across multiple unrelated locations
- NEVER mix HTML attributes with JavaScript event systems


Initialization Rules:
  - Put ALL DOM querying and listener setup inside:

    document.addEventListener('DOMContentLoaded', () => {
      init();
    });

  - Create a single init() function for setup
  - init() must:
      - query elements
      - attach listeners
      - render initial UI if needed

  - Store queried elements in constants:

    const form = document.getElementById('form');

  - Guard element usage:

    if (form) {
      form.addEventListener(...)
    }


State:
  - Mutable state:
      let count = 0;

  - Constants:
      const API_URL = "...";


Computed:
  - Use functions:

    function getTotal() {
      return price * qty;
    }


Methods:
  - Standard functions:

    function increment() {
      count++;
      render();
    }

  - Async allowed:

    async function fetchData() {}


Lifecycle:
  - onMount:
      document.addEventListener('DOMContentLoaded', () => { ... })

  - onDestroy:
      window.addEventListener('beforeunload', () => { ... })

  - onUpdate:
      call render() manually after state changes


Events:
  - Use addEventListener ONLY

    button.addEventListener('click', handler)

  - Form submit:

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      handler();
    })

  - Input:

    input.addEventListener('input', handler)

  - Change:

    select.addEventListener('change', handler)


DOM Updates:
  - Update UI manually after state changes
  - Use:
      element.textContent
      element.innerHTML (sparingly)

  - Prefer render() for centralized updates

  Example:

    function render() {
      counter.textContent = count;
    }

  - Every state-changing method MUST:
      - update DOM directly
      OR
      - call render()


Template Rules:
  - Use standard HTML elements
  - Use class (NOT className)
  - Use unique ids only when needed
  - Use classes for reusable styling
  - Self-close void elements properly:
      <input>
      <img>
      <br>

  - Ensure all referenced ids/classes exist in markup


CSS Rules:
  - Use valid CSS syntax only
  - Use kebab-case property names:
      background-color
      border-radius
      justify-content

  - NEVER use JS object-style CSS


Forms:
  - Use addEventListener('input') or submit handling
  - NEVER read values before DOMContentLoaded
  - Validate values inside handlers
  - Prevent default form reload on submit


Rendering:
  - Initial UI must render immediately
  - If dynamic UI exists, call render() inside init()
  - Avoid empty containers without content"""


_TARGET_INSTRUCTIONS = {
    "React":   _REACT_INSTRUCTIONS,
    "Vue":     _VUE_INSTRUCTIONS,
    "Angular": _ANGULAR_INSTRUCTIONS,
    "HTML":    _HTML_INSTRUCTIONS,
}


def build_messages(
    ir: IR,
    target_framework: str,
    source_code: str | None = None,
) -> list[dict]:
    """
    Build Ollama messages list for translation.

    Args:
        ir               : Validated IR instance from ir_builder
        target_framework : One of React | Vue | Angular | HTML
        source_code      : Original source code. When provided, this is
                           the highest-priority translation input.

    Returns:
        messages list for Phi3Client.chat()

    Raises:
        ValueError if target_framework is not supported
    """
    if target_framework not in SUPPORTED_TARGETS:
        raise ValueError(
            f"Unsupported target: '{target_framework}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_TARGETS))}"
        )

    system  = _BASE_SYSTEM + "\n" + _TARGET_INSTRUCTIONS[target_framework]
    ir_json = ir.to_json()
    source_section = ""
    if source_code and source_code.strip():
        source_section = (
            "Original source code - highest priority:\n"
            "```\n"
            f"{source_code.strip()}\n"
            "```\n\n"
        )

    user = (
        f"Translate this component from {ir.framework} to {target_framework}.\n\n"
        "Use the original source code as the source of truth. "
        "Use the IR only as a supporting extraction checklist. "
        "If they disagree, the original source code wins.\n\n"
        f"{source_section}"
        f"Component IR - supporting checklist:\n{ir_json}\n\n"
        f"Return only the {target_framework} code with zero comments."
    )

    return [
        { "role": "system", "content": system },
        { "role": "user",   "content": user   },
    ]
