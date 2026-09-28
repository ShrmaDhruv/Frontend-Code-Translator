"""
base.py — Shared data structures for all framework rule files.
Import Rule and FiredRule from here in every framework module.
"""

import re
from dataclasses import dataclass


@dataclass
class Rule:
    id: str
    pattern: re.Pattern
    weight: int
    reason: str


@dataclass
class FiredRule:
    id: str
    framework: str
    weight: int
    match_count: int
    contribution: int   # weight * match_count
    reason: str
