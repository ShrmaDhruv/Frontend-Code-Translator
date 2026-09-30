"""
ir/regex

Legacy regex extractors. Used only when tree-sitter fails or AST_PARSER=regex
(kept for fallback and eval comparison).
"""

from app.ir.regex import angular, html, react, vue

__all__ = ["angular", "html", "react", "vue"]
