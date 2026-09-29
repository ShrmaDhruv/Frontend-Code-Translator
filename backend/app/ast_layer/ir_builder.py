
import json
import logging
import os
import re
from app.ast_layer.ir_schema import (
    IR,
    IRComputed,
    IRImport,
    IRLifecycle,
    IRMethod,
    IRProp,
    IRState,
)
from app.ast_layer.ir_validator import validate

log = logging.getLogger(__name__)

MAX_TOKENS = 3000
TEMPERATURE = 0.1

# facts  : IR built only from tree-sitter facts (no LLM call)
# hybrid : facts first; LLM only fills gaps when the facts look unreliable (default)
# llm    : legacy - LLM rewrites the whole IR from the summary, facts as fallback
IR_MODES = ("facts", "hybrid", "llm")
DEFAULT_IR_MODE = "hybrid"

_IR_SCHEMA = """IR schema:
{
  "framework":  string,               // source framework as detected
  "component":  string,               // component name
  "props":      [{ "name": string, "type": string, "required": bool, "default": string|null }],
  "state":      [{ "name": string, "init": string|null, "type": string }],
  "computed":   [{ "name": string, "expression": string, "deps": [string] }],
  "lifecycle":  [{ "hook": string, "body": string }],
  "methods":    [{ "name": string, "params": [string], "body": string }],
  "imports":    [{ "source": string, "specifiers": [string], "default": string|null }],
  "styles":     string
}"""

_SYSTEM_PROMPT = """You are a frontend code analyser.
You will receive a pre-parsed structural summary of a frontend component
alongside its raw script block.

Your job is to fill in the following IR schema as a JSON object.
Use the summary hints as a starting point and correct or extend them
using the raw script block.

""" + _IR_SCHEMA + """

Lifecycle hook names to use:
  onMount | onDestroy | onBeforeMount | onBeforeDestroy | onUpdate |
  onBeforeUpdate | onCreate | onAfterViewInit | onChanges | onEveryRender

Rules:
  - className   → use "class" in attrs
  - onClick     → use "events.click"
  - useState    → state entry
  - useEffect with [] deps → lifecycle hook "onMount"
  - ref()       → state entry  (Vue 3)
  - computed()  → computed entry  (Vue 3)
  - ngOnInit    → lifecycle hook "onMount"
  - ngOnDestroy → lifecycle hook "onDestroy"

Return ONLY one complete valid JSON object.
No markdown fences. No explanation. No preamble. No trailing commas."""


def _build_prompt(summary: dict) -> list[dict]:
    summary_text = json.dumps({
        k: v for k, v in summary.items()
        if k not in ("script_block", "styles", "markup")
    }, indent=2)

    user_content = (
        f"Framework: {summary['framework']}\n\n"
        f"Pre-parsed summary:\n{summary_text}\n\n"
        f"Raw script block:\n```\n{summary.get('script_block', '')}\n```\n\n"
        "Fill the IR schema from the above. Return only JSON."
    )

    return [
        { "role": "system",  "content": _SYSTEM_PROMPT },
        { "role": "user",    "content": user_content },
    ]


def _build_retry_prompt(summary: dict, errors: list[str]) -> list[dict]:
    base     = _build_prompt(summary)
    error_str = "\n".join(f"  - {e}" for e in errors)

    base.append({
        "role": "assistant",
        "content": "[previous attempt had errors]",
    })
    base.append({
        "role": "user",
        "content": (
            f"Your previous response had these critical errors:\n{error_str}\n\n"
            "Please fix them and return corrected JSON only."
        ),
    })
    return base


def _build_json_retry_prompt(summary: dict, raw: str, error: str) -> list[dict]:
    base = _build_prompt(summary)
    base.append({
        "role": "assistant",
        "content": raw[:1200],
    })
    base.append({
        "role": "user",
        "content": (
            "Your previous response could not be parsed as JSON.\n"
            f"Parser error: {error}\n\n"
            "Return the same IR again as ONE complete valid JSON object only. "
            "Do not use markdown fences, comments, preamble text, or trailing commas."
        ),
    })
    return base


def _strip_fences(raw: str) -> str:
    raw = re.sub(r'<think>[\s\S]*?</think>', '', raw.strip())
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\s*```$', '', raw)
    return raw.strip()


def _strip_trailing_commas(text: str) -> str:
    return re.sub(r",\s*([}\]])", r"\1", text)


def _extract_balanced_json(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]

    return None


def _loads_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_strip_trailing_commas(text))


def _parse_json(raw: str) -> dict:
    cleaned = _strip_fences(raw)

    try:
        return _loads_json(cleaned)
    except json.JSONDecodeError:
        balanced = _extract_balanced_json(cleaned)
        if balanced:
            try:
                return _loads_json(balanced)
            except json.JSONDecodeError:
                pass

        brace = cleaned.find("{")
        last = cleaned.rfind("}")
        if brace != -1 and last != -1 and last > brace:
            try:
                return _loads_json(cleaned[brace:last + 1])
            except json.JSONDecodeError:
                pass

    raise ValueError(f"Could not parse IR JSON from model response:\n{raw[:300]}")


def _guess_type(init: str | None) -> str:
    if init is None:
        return "any"

    value = str(init).strip()
    if value in ("true", "false"):
        return "boolean"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return "number"
    if value.startswith(("'", '"', "`")):
        return "string"
    if value.startswith("["):
        return "array"
    if value.startswith("{"):
        return "object"
    return "any"


def _prop_from_hint(prop) -> IRProp:
    if isinstance(prop, dict):
        return IRProp(
            name=str(prop.get("name", "")).strip(),
            type=str(prop.get("type", "any")),
            required=bool(prop.get("required", True)),
            default=None if prop.get("default") is None else str(prop.get("default")),
        )

    name = str(prop).strip()
    return IRProp(name=name, type="any", required=True)


def _state_from_hint(state) -> IRState:
    if isinstance(state, dict):
        init = state.get("init")
        init = None if init is None else str(init)
        return IRState(
            name=str(state.get("name", "")).strip(),
            init=init,
            type=str(state.get("type") or _guess_type(init)),
        )

    return IRState(name=str(state).strip())


def _computed_from_hint(computed) -> IRComputed:
    if isinstance(computed, dict):
        return IRComputed(
            name=str(computed.get("name", "")).strip(),
            expression=str(computed.get("expression") or computed.get("value") or ""),
            deps=[str(d) for d in computed.get("deps") or []],
        )

    return IRComputed(name=str(computed).strip(), expression="")


def _lifecycle_from_hint(lifecycle) -> IRLifecycle:
    hook_map = {
        "onEffect": "onUpdate",
        "ngAfterContentInit": "onAfterViewInit",
    }

    if isinstance(lifecycle, dict):
        hook = str(lifecycle.get("hook") or lifecycle.get("name") or "onMount").strip()
        return IRLifecycle(
            hook=hook_map.get(hook, hook),
            body=str(lifecycle.get("body") or lifecycle.get("value") or ""),
        )

    hook = str(lifecycle).strip() or "onMount"
    return IRLifecycle(hook=hook_map.get(hook, hook))


def _method_from_hint(method) -> IRMethod:
    if isinstance(method, dict):
        return IRMethod(
            name=str(method.get("name", "")).strip(),
            params=[str(p) for p in method.get("params") or []],
            body=str(method.get("body") or method.get("value") or ""),
        )

    return IRMethod(name=str(method).strip())


def _import_from_hint(import_hint) -> IRImport:
    if isinstance(import_hint, dict):
        return IRImport(
            source=str(import_hint.get("source", "")),
            specifiers=list(import_hint.get("specifiers", [])),
            default=import_hint.get("default"),
        )

    return IRImport(source=str(import_hint))


def build_facts_ir(summary: dict) -> IR:
    """
    Build the IR deterministically from pre-parser facts.

    With the tree-sitter extractors the facts carry method params/bodies,
    lifecycle bodies and computed expressions, so this is a complete IR.
    With the legacy regex extractors it is a conservative, name-only IR.
    """
    return IR(
        framework=summary.get("framework", "HTML"),
        component=summary.get("component", "App") or "App",
        props=[
            prop for prop in (_prop_from_hint(p) for p in summary.get("props", []))
            if prop.name
        ],
        state=[
            state for state in (_state_from_hint(s) for s in summary.get("state_hints", []))
            if state.name
        ],
        computed=[
            computed for computed in (
                _computed_from_hint(c) for c in summary.get("computed_hints", [])
            )
            if computed.name
        ],
        lifecycle=[
            lifecycle for lifecycle in (
                _lifecycle_from_hint(l) for l in summary.get("lifecycle_hints", [])
            )
            if lifecycle.hook
        ],
        methods=[
            method for method in (_method_from_hint(m) for m in summary.get("method_hints", []))
            if method.name
        ],
        imports=[
            import_item for import_item in (
                _import_from_hint(i) for i in summary.get("imports", [])
            )
            if import_item.source
        ],
        styles=summary.get("styles", ""),
    )


def _get_client():
    from app.ollama_client import OLClient
    return OLClient()


_fallback_ir_from_summary = build_facts_ir


# ── Hybrid mode: LLM fills gaps in the facts IR ───────────────────────────────

_REVIEW_SYSTEM_PROMPT = """You are a frontend code analyser.
You receive a component's source script and an IR (JSON) that a syntax
parser already extracted from it. Everything in the parser IR is correct.

Your job: return the COMPLETE IR as one JSON object with the same schema,
keeping every existing entry unchanged, and ADDING only entries that exist
in the source but are missing from the parser IR.

Never remove, rename, or rewrite existing entries. Never invent entries
that are not in the source.

""" + _IR_SCHEMA + """

Use only these lifecycle hook names:
  onMount | onDestroy | onBeforeMount | onBeforeDestroy | onUpdate |
  onBeforeUpdate | onCreate | onAfterViewInit | onChanges | onEveryRender

Return ONLY one complete valid JSON object.
No markdown fences. No explanation. No preamble. No trailing commas."""

_IR_FIELDS = ("props", "state", "computed", "methods")


def review_reasons(summary: dict, ir: IR) -> list[str]:
    """Why the facts IR should not be trusted on its own (empty list = trust it)."""
    reasons = []
    if summary.get("extractor") != "tree-sitter":
        reasons.append("regex extractor fallback")
    if summary.get("parse_errors"):
        reasons.append("source has syntax errors")
    if not validate(ir).is_valid:
        reasons.append("facts IR failed validation")
    has_logic = bool(summary.get("script_block", "").strip())
    if has_logic and not (ir.state or ir.props or ir.methods or ir.computed or ir.lifecycle):
        reasons.append("script present but no component members found")
    return reasons


def _build_review_prompt(summary: dict, facts_ir: IR) -> list[dict]:
    user_content = (
        f"Framework: {summary['framework']}\n\n"
        f"Parser IR:\n{facts_ir.to_json(indent=2)}\n\n"
        f"Source script:\n```\n{summary.get('script_block', '')}\n```\n\n"
        "Return the complete IR JSON."
    )
    return [
        {"role": "system", "content": _REVIEW_SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]


def merge_ir(facts: IR, extra: IR) -> IR:
    """Facts win: keep every facts entry, add LLM entries whose names are new."""
    merged = IR.from_dict(facts.to_dict())
    for name in _IR_FIELDS:
        existing = {item.name for item in getattr(merged, name)}
        getattr(merged, name).extend(
            item for item in getattr(extra, name) if item.name and item.name not in existing
        )
    hooks = {item.hook for item in merged.lifecycle}
    merged.lifecycle.extend(
        item for item in extra.lifecycle if item.hook not in hooks and _has_logic(item.body)
    )
    if merged.component in ("", "App") and extra.component:
        merged.component = extra.component
    return merged


def _chat_json(client, messages: list[dict], retry_messages) -> dict | None:
    """One LLM call plus one JSON-repair retry; None if both are unparseable."""
    raw = client.chat(messages, max_new_tokens=MAX_TOKENS, temperature=TEMPERATURE)
    try:
        return _parse_json(raw)
    except ValueError as exc:
        raw = client.chat(retry_messages(raw, str(exc)), max_new_tokens=MAX_TOKENS, temperature=TEMPERATURE)
        try:
            return _parse_json(raw)
        except ValueError:
            return None


def _ir_from_data(data: dict | None) -> IR | None:
    """Lenient: small models drift from the schema (e.g. lifecycle {name, value})."""
    if not isinstance(data, dict):
        return None
    try:
        return build_facts_ir({
            "framework":       data.get("framework") or "HTML",
            "component":       data.get("component") or "App",
            "props":           data.get("props") or [],
            "state_hints":     data.get("state") or [],
            "computed_hints":  data.get("computed") or [],
            "lifecycle_hints": data.get("lifecycle") or [],
            "method_hints":    data.get("methods") or [],
            "imports":         data.get("imports") or [],
            "styles":          data.get("styles") if isinstance(data.get("styles"), str) else "",
        })
    except (TypeError, ValueError, AttributeError):
        return None


def _has_logic(body: str) -> bool:
    """False for empty bodies like '', '{}', '() => {}'."""
    return bool(body.replace("=>", "").strip(" \n\t(){};"))


def _hybrid_ir(summary: dict, facts_ir: IR) -> IR:
    reasons = review_reasons(summary, facts_ir)
    if not reasons:
        return facts_ir

    client = _get_client()
    if not client.is_available():
        log.warning("IR review skipped (Ollama unreachable): %s", reasons)
        return facts_ir

    messages = _build_review_prompt(summary, facts_ir)

    def retry(raw: str, error: str) -> list[dict]:
        return messages + [
            {"role": "assistant", "content": raw[:1200]},
            {"role": "user", "content": (
                f"That was not valid JSON ({error}). "
                "Return the complete IR as one valid JSON object only."
            )},
        ]

    extra = _ir_from_data(_chat_json(client, messages, retry))
    if extra is None:
        return facts_ir
    merged = merge_ir(facts_ir, extra)
    return merged if validate(merged).is_valid else facts_ir


# ── Legacy llm mode ───────────────────────────────────────────────────────────

def _legacy_llm_ir(summary: dict, facts_ir: IR) -> IR:
    client = _get_client()
    if not client.is_available():
        return facts_ir

    def json_retry(raw: str, error: str) -> list[dict]:
        return _build_json_retry_prompt(summary, raw, error)

    ir = _ir_from_data(_chat_json(client, _build_prompt(summary), json_retry))
    if ir is None:
        return facts_ir
    result = validate(ir)
    if result.is_valid:
        return ir

    ir = _ir_from_data(_chat_json(client, _build_retry_prompt(summary, result.errors), json_retry))
    return ir if ir is not None and validate(ir).is_valid else facts_ir


# ── Entry ─────────────────────────────────────────────────────────────────────

def ir_mode() -> str:
    mode = os.getenv("IR_MODE", DEFAULT_IR_MODE)
    if mode not in IR_MODES:
        raise ValueError(f"IR_MODE must be one of {IR_MODES}, got '{mode}'")
    return mode


def build_ir(summary: dict) -> IR:
    """
    Convert a pre-parsed summary dict into a validated IR instance.

    The facts IR (built without any LLM) is always computed first and is
    the fallback for every LLM failure, so bad model output never crashes
    the pipeline. IR_MODE picks how much the LLM is involved (see IR_MODES).

    Raises:
        ValueError  if the chosen IR is the facts IR and it is invalid
    """
    facts_ir = build_facts_ir(summary)
    mode = ir_mode()

    if mode == "facts":
        ir = facts_ir
    elif mode == "hybrid":
        ir = _hybrid_ir(summary, facts_ir)
    else:
        ir = _legacy_llm_ir(summary, facts_ir)

    if ir is facts_ir:
        result = validate(facts_ir)
        if not result.is_valid:
            raise ValueError(f"IR extraction failed.\nErrors: {result.errors}")
    return ir
