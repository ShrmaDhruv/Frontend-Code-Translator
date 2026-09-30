"""
graph

LangGraph version of the translation pipeline. Selected with
PIPELINE_ENGINE=graph; app.pipeline.run_pipeline dispatches here.

Usage:
    from app.graph import run_graph

    result = run_graph(code, "Vue", "Auto Detect", True, "translate")
"""

from app.graph.builder import get_graph, run_graph

__all__ = ["get_graph", "run_graph"]
