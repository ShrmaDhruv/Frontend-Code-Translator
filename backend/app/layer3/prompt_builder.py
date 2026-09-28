SYSTEM_PROMPT = """You are an expert frontend developer with deep knowledge of React, Vue, Angular, and vanilla HTML/JavaScript.

Your ONLY job is to identify which frontend framework a given code snippet belongs to.

You MUST choose exactly one of these four values:
- React
- Vue
- Angular
- HTML  (use this for vanilla JavaScript with no framework)

Rules:
- If imports are missing, infer from syntax patterns
- If the code is partial or ambiguous, make your best judgment
- You must ALWAYS give a definitive answer — never say unknown
- Respond ONLY in the JSON format below — no extra text

Response format:
{
    "reasoning": "1-2 sentences explaining the key signals you observed",
    "detected": "React" or "Vue" or "Angular" or "HTML",
    "confidence": "high" or "medium" or "low"
}"""


# ─────────────────────────────────────────────
# USER PROMPT
# Wraps the actual code in clear tags so the
# model doesn't confuse code with instructions.
# ─────────────────────────────────────────────

def build_user_prompt(code: str) -> str:
    """
    Wrap the code snippet in a clean user prompt.

    Args:
        code : The raw source code string to identify.

    Returns:
        Formatted user message string.
    """
    return f"""Identify the frontend framework for this code snippet:

<code>
{code.strip()}
</code>

Respond only in the specified JSON format."""


# ─────────────────────────────────────────────
# MESSAGES LIST
# HFClient.chat() expects a list of role/content
# dicts — fed into tokenizer.apply_chat_template()
# ─────────────────────────────────────────────

def build_messages(code: str) -> list[dict]:
    """
    Build the full messages list for Qwen2.5-Coder-1.5B-Instruct.

    Compatible with HuggingFace tokenizer.apply_chat_template().

    Args:
        code : The raw source code string to identify.

    Returns:
        List of message dicts with role and content.
    """
    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": build_user_prompt(code)
        }
    ]