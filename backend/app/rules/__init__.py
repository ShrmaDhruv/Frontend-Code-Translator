"""
rules/__init__.py

Makes `rules` a Python package and exposes all rule lists
and shared types from a single import point.

Usage (import everything at once):
    from app.rules import REACT_RULES, VUE_RULES, ANGULAR_RULES, HTML_RULES
    from app.rules import Rule, FiredRule

Usage (import individual framework):
    from app.rules.react_rules import REACT_RULES
    from app.rules.vue_rules import VUE_RULES
    from app.rules.angular_rules import ANGULAR_RULES
    from app.rules.html_rules import HTML_RULES
"""

from app.rules.base import Rule, FiredRule
from app.rules.react_rules import REACT_RULES
from app.rules.vue_rules import VUE_RULES
from app.rules.angular_rules import ANGULAR_RULES
from app.rules.html_rules import HTML_RULES

__all__ = [
    "Rule",
    "FiredRule",
    "REACT_RULES",
    "VUE_RULES",
    "ANGULAR_RULES",
    "HTML_RULES",
]
