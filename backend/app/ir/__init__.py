"""
ir/__init__.py

Public interface for source-code → IR extraction.

Flow:
    raw code + source framework
        ↓
    pre_parser.parse()       → unified summary dict
        ↓
    builder.build_ir()       → validated IR instance
        ↓
    IR ready for translation

Usage:
    from app.ir import extract_ir
    from app.ir.schema import IR

    ir = extract_ir(code, "Vue")
    print(ir.to_json())
"""

from app.ir.pre_parser import parse
from app.ir.builder import build_ir
from app.ir.schema  import IR


def extract_ir(code: str, framework: str) -> IR:
    """
    Full pipeline: raw code → validated IR instance.

    Args:
        code      : Raw source code string
        framework : One of React | Vue | Angular | HTML

    Returns:
        Validated IR instance ready for translation
    """
    summary = parse(code, framework)
    return build_ir(summary)


__all__ = [
    "extract_ir",
    "parse",
    "build_ir",
    "IR",
]
