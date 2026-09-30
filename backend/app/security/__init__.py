"""
Security guardrails.

    api_limits    Layer 1: body size, rate limit, concurrency cap, security headers (app/main.py)
    input_guard   Layer 2: sanitize + inspect user code (graph: run_graph + check_input node)
    prompt_guard  Layer 3: random-boundary tags, untrusted-input rules, canary (prompt builders)

Plan and rationale: claude-logs/security-plan.md
"""

from app.security.input_guard import InputVerdict, inspect_input, sanitize_input

__all__ = ["InputVerdict", "inspect_input", "sanitize_input"]
