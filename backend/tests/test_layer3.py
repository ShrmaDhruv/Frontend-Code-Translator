"""
Layer 3 test suite — nightmare cases only.
Flow: ambiguous code -> Layer 1 scores low -> Layer 3 Qwen model called
-> response_parser extracts JSON -> score_merger returns final framework
-> cache returns instant result on repeat calls.
Run: python test_layer3.py
Run with model: python test_layer3.py --live
"""

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

warnings.filterwarnings('ignore')

from app.layer3.response_parser import parse_response, ParsedResponse
from app.layer3.score_merger    import merge_results
from app.layer3.cache           import DetectionCache

NIGHTMARE_VUE_WITH_DOM = """
export default {
  data() { return { count: 0 } },
  methods: {
    increment() {
      this.count++
      document.getElementById('counter').innerHTML = this.count
      document.querySelector('.display').innerText = this.count
      document.querySelector('.box').addEventListener('click', () => {})
      document.querySelector('.box').innerHTML = this.count
      document.querySelector('.box').innerText = this.count
    }
  }
}
"""

NIGHTMARE_REACT_NO_JSX = """
const App = ({ title }) => {
  const [open, setOpen] = React.useState(false)
  const [data, setData] = React.useState(null)
  React.useEffect(() => {
    document.title = title
    document.getElementById('root').innerHTML = title
    document.querySelector('body').addEventListener('click', () => setOpen(true))
  }, [])
  return React.createElement('div', { id: 'root' },
    React.createElement('h1', null, title),
    React.createElement('p', null, open ? 'open' : 'closed')
  )
}
"""

NIGHTMARE_ANGULAR_NO_DECORATOR = """
export class DashboardComponent {
  users = []
  loading = false

  constructor(private http, private router) {}

  ngOnInit() {
    this.loading = true
    this.http.get('/api/users').subscribe(data => {
      this.users = data
      this.loading = false
      document.getElementById('loader').style.display = 'none'
      document.querySelector('.table').innerHTML = data.length + ' users'
    })
  }

  navigate(id) {
    this.router.navigate(['/user', id])
  }
}
"""

NIGHTMARE_HTML_LOOKS_LIKE_REACT = """
<!DOCTYPE html>
<html>
<head><title>App</title></head>
<body>
  <div id="root" className="container">
    <h1 onClick="handleClick()">Hello</h1>
    <p>Count: <span id="count">0</span></p>
    <button onClick="increment()">Add</button>
  </div>
  <script>
    let count = 0
    function increment() {
      count++
      document.getElementById('count').innerText = count
    }
    function handleClick() {
      document.querySelector('#root').style.color = 'red'
    }
  </script>
</body>
</html>
"""


def run(label, cases, test_fn):
    print(f"\n{label}")
    print("-" * 50)
    passed = 0
    for case in cases:
        ok, msg = test_fn(case)
        print(f"  {'PASS' if ok else 'FAIL'} - {msg}")
        if ok:
            passed += 1
    print(f"  {passed}/{len(cases)} passed")
    return passed == len(cases)


def test_parser():
    cases = [
        (
            "Vue inside broken JSON - keyword fallback",
            "The code uses data() and methods: so it is definitely Vue",
            "Vue", "low", "fallback"
        ),
        (
            "React lowercase with markdown fences",
            '```json\n{"reasoning": "createElement", "detected": "react", "confidence": "high"}\n```',
            "React", "high", "json"
        ),
        (
            "Angular with preamble text",
            'Looking at the code:\n{"reasoning": "ngOnInit present", "detected": "Angular", "confidence": "high"}\nDone.',
            "Angular", "high", "json"
        ),
        (
            "HTML but model says Vanilla",
            '{"reasoning": "no framework", "detected": "Vanilla", "confidence": "high"}',
            "HTML", "high", "json"
        ),
        (
            "Missing confidence field",
            '{"reasoning": "has v-if", "detected": "Vue"}',
            "Vue", "medium", "json"
        ),
    ]

    def test_fn(case):
        label, raw, exp_fw, exp_conf, exp_method = case
        r  = parse_response(raw)
        ok = r.detected == exp_fw and r.confidence == exp_conf and r.parse_method == exp_method
        msg = label if ok else f"{label} | got {r.detected}/{r.confidence}/{r.parse_method}"
        return ok, msg

    return run("PARSER - nightmare inputs", cases, test_fn)


def test_merger():
    def p(detected, confidence):
        return ParsedResponse(detected=detected, confidence=confidence,
                              reasoning="", raw="{}", parse_method="json")

    cases = [
        (
            "Vue code with heavy DOM - HTML scored 48, Vue scored 15, Layer 3 says Vue",
            {"React": 0, "Vue": 15, "Angular": 0, "HTML": 48},
            p("Vue", "high"), "Vue", "high", False
        ),
        (
            "React no JSX - HTML scored high from DOM calls, Layer 3 says React",
            {"React": 10, "Vue": 0, "Angular": 0, "HTML": 35},
            p("React", "high"), "React", "high", False
        ),
        (
            "Angular no decorator - all scores near zero, Layer 3 says Angular",
            {"React": 0, "Vue": 0, "Angular": 3, "HTML": 8},
            p("Angular", "high"), "Angular", "high", False
        ),
        (
            "HTML looks like React - className and onClick fired React rules",
            {"React": 20, "Vue": 0, "Angular": 0, "HTML": 25},
            p("HTML", "high"), "HTML", "high", False
        ),
        (
            "Completely ambiguous - all scores equal, Layer 3 says low confidence",
            {"React": 15, "Vue": 15, "Angular": 15, "HTML": 15},
            p("Vue", "low"), "Vue", "low", True
        ),
    ]

    def test_fn(case):
        label, l1, l3, exp_fw, exp_conf, exp_ask = case
        r  = merge_results(l1, l3)
        ok = r.detected == exp_fw and r.confidence == exp_conf and r.ask_user == exp_ask
        msg = label if ok else f"{label} | got {r.detected}/{r.confidence}/ask={r.ask_user}"
        return ok, msg

    return run("MERGER - nightmare scores", cases, test_fn)


def test_cache():
    cache = DetectionCache()
    react = ParsedResponse("React", "high", "", "{}", "json")
    vue   = ParsedResponse("Vue",   "high", "", "{}", "json")

    code  = NIGHTMARE_VUE_WITH_DOM.strip()

    cases = [
        ("Miss on empty cache",          lambda: cache.get(code) is None),
        ("Hit after set",                lambda: (cache.set(code, react), cache.get(code)) and cache.get(code).detected == "React"),
        ("Whitespace ignored in key",    lambda: cache.get("   " + code + "\n") is not None),
        ("Different code is a miss",     lambda: cache.get(NIGHTMARE_REACT_NO_JSX.strip()) is None),
        ("Size correct after two sets",  lambda: (cache.set(NIGHTMARE_REACT_NO_JSX.strip(), vue), cache.size) and cache.size == 2),
        ("Clear empties cache",          lambda: (cache.clear(), cache.size) and cache.size == 0),
        ("Miss after clear",             lambda: cache.get(code) is None),
    ]

    def test_fn(case):
        label, fn = case
        ok = bool(fn())
        return ok, label

    return run("CACHE - behavior checks", cases, test_fn)


def test_live():
    from app.ollama_client import OLClient
    from app.layer3       import detect_with_llm
    import time

    if not OLClient().is_available():
        print("\n  Skipped - Ollama unreachable. Run: ollama serve")
        return

    cases = [
        (
            "Vue with heavy DOM calls - Layer 1 says HTML, Layer 3 must correct to Vue",
            NIGHTMARE_VUE_WITH_DOM,
            {"React": 0, "Vue": 15, "Angular": 0, "HTML": 48},
            "Vue"
        ),
        (
            "React createElement no JSX - DOM calls pollute scores, Layer 3 must say React",
            NIGHTMARE_REACT_NO_JSX,
            {"React": 10, "Vue": 0, "Angular": 0, "HTML": 35},
            "React"
        ),
        (
            "Angular no decorator - near zero scores, Layer 3 must recognise Angular",
            NIGHTMARE_ANGULAR_NO_DECORATOR,
            {"React": 0, "Vue": 0, "Angular": 3, "HTML": 8},
            "Angular"
        ),
        (
            "HTML with className and onClick - looks like React, Layer 3 must say HTML",
            NIGHTMARE_HTML_LOOKS_LIKE_REACT,
            {"React": 20, "Vue": 0, "Angular": 0, "HTML": 25},
            "HTML"
        ),
    ]

    print("\nLIVE - nightmare cases against Qwen model")
    print("-" * 50)
    passed = 0
    for label, code, l1_scores, expected in cases:
        try:
            result = detect_with_llm(code, l1_scores)
            ok     = result.detected == expected
            if ok:
                passed += 1
            print(f"  {'PASS' if ok else 'FAIL'} - {label}")
            if not ok:
                print(f"    expected {expected}, got {result.detected} ({result.confidence})")
        except Exception as e:
            print(f"  ERROR - {label} | {e}")

    detect_with_llm(NIGHTMARE_VUE_WITH_DOM, {"React": 0, "Vue": 15, "Angular": 0, "HTML": 48})
    start   = time.time()
    detect_with_llm(NIGHTMARE_VUE_WITH_DOM, {"React": 0, "Vue": 15, "Angular": 0, "HTML": 48})
    elapsed = time.time() - start
    print(f"  Cache hit - {elapsed * 1000:.1f}ms {'PASS' if elapsed < 0.1 else 'FAIL'}")
    print(f"  {passed}/{len(cases)} passed")


if __name__ == "__main__":
    live = "--live" in sys.argv

    print("\n" + "=" * 50)
    print("  LAYER 3 - NIGHTMARE TEST SUITE")
    print("=" * 50)

    p1 = test_parser()
    p2 = test_merger()
    p3 = test_cache()

    if live:
        test_live()
    else:
        print("\n  Live skipped. Run: python test_layer3.py --live")

    print("\n" + "=" * 50)
    print(f"  Unit : {'ALL PASSED' if p1 and p2 and p3 else 'SOME FAILED'}")
    print("=" * 50 + "\n")
