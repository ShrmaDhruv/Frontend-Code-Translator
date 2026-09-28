"""
ast_layer/__init__.py

Public interface for the AST extraction pipeline.

Flow:
    raw code + source framework
        ↓
    pre_parser.parse()       → unified summary dict
        ↓
    ir_builder.build_ir()    → validated IR instance
        ↓
    IR ready for translation

Usage:
    from app.ast_layer import extract_ir
    from app.ast_layer.ir_schema import IR

    ir = extract_ir(code, "Vue")
    print(ir.to_json())
"""

from app.ast_layer.pre_parser import parse
from app.ast_layer.ir_builder import build_ir
from app.ast_layer.ir_schema  import IR


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
