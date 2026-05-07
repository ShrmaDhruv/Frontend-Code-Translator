
import json
import re
from ast_layer.ir_schema import (
    IR,
    IRComputed,
    IRImport,
    IRLifecycle,
    IRMethod,
    IRProp,
    IRState,
)
from ast_layer.ir_validator import validate

MAX_TOKENS = 3000
TEMPERATURE = 0.1

_SYSTEM_PROMPT = """You are a frontend code analyser.
You will receive a pre-parsed structural summary of a frontend component
alongside its raw script block.

Your job is to fill in the following IR schema as a JSON object.
Use the summary hints as a starting point and correct or extend them
using the raw script block.

IR schema:
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
}

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
            default=prop.get("default"),
        )

    name = str(prop).strip()
    return IRProp(name=name, type="any", required=True)


def _state_from_hint(state) -> IRState:
    if isinstance(state, dict):
        init = state.get("init")
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
            expression=str(computed.get("expression", "")),
            deps=list(computed.get("deps", [])),
        )

    return IRComputed(name=str(computed).strip(), expression="")


def _lifecycle_from_hint(lifecycle) -> IRLifecycle:
    hook_map = {
        "onEffect": "onUpdate",
        "ngAfterContentInit": "onAfterViewInit",
    }

    if isinstance(lifecycle, dict):
        hook = str(lifecycle.get("hook", "onMount")).strip()
        return IRLifecycle(
            hook=hook_map.get(hook, hook),
            body=str(lifecycle.get("body", "")),
        )

    hook = str(lifecycle).strip() or "onMount"
    return IRLifecycle(hook=hook_map.get(hook, hook))


def _method_from_hint(method) -> IRMethod:
    if isinstance(method, dict):
        return IRMethod(
            name=str(method.get("name", "")).strip(),
            params=list(method.get("params", [])),
            body=str(method.get("body", "")),
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


def _fallback_ir_from_summary(summary: dict) -> IR:
    """
    Build a conservative IR directly from pre-parser hints.

    This keeps the pipeline alive when the local model returns malformed
    or truncated JSON. It will be less complete than model-filled IR, but
    it preserves the key framework, component, state, props, methods,
    imports, lifecycle, computed values, and styles.
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
    from ollama_client import OLClient
    return OLClient()


def build_ir(summary: dict) -> IR:
    """
    Convert a pre-parsed summary dict into a validated IR instance.

    Args:
        summary : Output of pre_parser.parse()

    Returns:
        IR instance — validated, ready for translation prompt

    Raises:
        RuntimeError  if Ollama is unreachable
        ValueError    if IR cannot be parsed after two attempts
    """
    client = _get_client()

    if not client.is_available():
        ir = _fallback_ir_from_summary(summary)
        result = validate(ir)
        if result.is_valid:
            return ir
        raise ValueError(
            "Ollama is not reachable and fallback IR was invalid.\n"
            f"Errors: {result.errors}"
        )

    messages  = _build_prompt(summary)
    raw       = client.chat(messages, max_new_tokens=MAX_TOKENS, temperature=TEMPERATURE)

    try:
        data = _parse_json(raw)
    except ValueError as exc:
        messages = _build_json_retry_prompt(summary, raw, str(exc))
        raw      = client.chat(messages, max_new_tokens=MAX_TOKENS, temperature=TEMPERATURE)
        try:
            data = _parse_json(raw)
        except ValueError:
            ir = _fallback_ir_from_summary(summary)
            result = validate(ir)
            if not result.is_valid:
                raise ValueError(
                    "IR model returned malformed JSON and fallback IR was invalid.\n"
                    f"Errors: {result.errors}"
                )
            return ir

    ir        = IR.from_dict(data)
    result    = validate(ir)

    if not result.is_valid:
        messages  = _build_retry_prompt(summary, result.errors)
        raw       = client.chat(messages, max_new_tokens=MAX_TOKENS, temperature=TEMPERATURE)
        data      = _parse_json(raw)
        ir        = IR.from_dict(data)
        result    = validate(ir)

        if not result.is_valid:
            fallback = _fallback_ir_from_summary(summary)
            fallback_result = validate(fallback)
            if fallback_result.is_valid:
                return fallback
            raise ValueError(
                f"IR extraction failed after two attempts.\n"
                f"Errors: {result.errors}"
            )

    return ir
