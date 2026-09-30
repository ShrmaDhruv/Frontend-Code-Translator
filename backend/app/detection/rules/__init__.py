"""
rules/__init__.py

Makes `rules` a Python package and exposes all rule lists
and shared types from a single import point.

Usage (import everything at once):
    from app.detection.rules import REACT_RULES, VUE_RULES, ANGULAR_RULES, HTML_RULES
    from app.detection.rules import Rule, FiredRule

Usage (import individual framework):
    from app.detection.rules.react_rules import REACT_RULES
    from app.detection.rules.vue_rules import VUE_RULES
    from app.detection.rules.angular_rules import ANGULAR_RULES
    from app.detection.rules.html_rules import HTML_RULES
"""

from app.detection.rules.base import Rule, FiredRule
from app.detection.rules.react_rules import REACT_RULES
from app.detection.rules.vue_rules import VUE_RULES
from app.detection.rules.angular_rules import ANGULAR_RULES
from app.detection.rules.html_rules import HTML_RULES

__all__ = [
    "Rule",
    "FiredRule",
    "REACT_RULES",
    "VUE_RULES",
    "ANGULAR_RULES",
    "HTML_RULES",
]
