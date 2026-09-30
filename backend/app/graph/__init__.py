"""
graph

LangGraph translation pipeline; app.pipeline.run_pipeline delegates here.
Diagram: docs/pipeline-graph.png

Usage:
    from app.graph import run_graph

    result = run_graph(code, "Vue", "Auto Detect", True, "translate")
"""

from app.graph.builder import get_graph, run_graph

__all__ = ["get_graph", "run_graph"]
