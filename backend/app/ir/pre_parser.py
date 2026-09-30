import logging
import os

from app.ir import regex, treesitter

log = logging.getLogger(__name__)

SUPPORTED_FRAMEWORKS = {"React", "Vue", "Angular", "HTML"}

# "tree-sitter" (default) or "regex" (legacy extractors, kept as fallback and for eval comparison)
AST_PARSER = os.getenv("AST_PARSER", "tree-sitter")

_REGEX_EXTRACTORS = {
    "React":   regex.react.extract,
    "Vue":     regex.vue.extract,
    "Angular": regex.angular.extract,
    "HTML":    regex.html.extract,
}


def parse(code: str, framework: str) -> dict:
    """
    Dispatch raw code to the correct framework extractor.

    Args:
        code      : Raw source code string
        framework : One of React | Vue | Angular | HTML

    Returns:
        Unified summary dict ready for builder.py

    Raises:
        ValueError  if framework is not one of the four supported values
    """
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(
            f"Unsupported framework: '{framework}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_FRAMEWORKS))}"
        )

    if os.getenv("AST_PARSER", AST_PARSER) != "regex":
        try:
            return _normalise(treesitter.extract(code, framework), framework)
        except Exception as exc:
            log.warning("tree-sitter extraction failed for %s, using regex: %s", framework, exc)

    summary = _REGEX_EXTRACTORS[framework](code)
    summary["extractor"] = "regex"
    return _normalise(summary, framework)


def _normalise(summary: dict, framework: str) -> dict:
    """
    Ensure every summary dict has the same keys regardless of framework.
    Missing keys get safe empty defaults so builder never KeyErrors.
    """
    defaults = {
        "framework":        framework,
        "component":        "App",
        "imports":          [],
        "props":            [],
        "state_hints":      [],
        "lifecycle_hints":  [],
        "computed_hints":   [],
        "method_hints":     [],
        "event_hints":      [],
        "script_block":     "",
        "styles":           "",
        "template_hints": {
            "conditionals": [],
            "loops":        [],
            "bindings":     [],
            "events":       [],
            "models":       [],
        },
    }

    for key, default in defaults.items():
        if key not in summary:
            summary[key] = default

    if "template_hints" in summary:
        for k, v in defaults["template_hints"].items():
            if k not in summary["template_hints"]:
                summary["template_hints"][k] = v

    return summary
