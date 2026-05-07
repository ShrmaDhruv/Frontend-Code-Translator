from ast_layer import react_extractor
from ast_layer import vue_extractor
from ast_layer import angular_extractor
from ast_layer import html_extractor

SUPPORTED_FRAMEWORKS = {"React", "Vue", "Angular", "HTML"}

_EXTRACTORS = {
    "React":   react_extractor.extract,
    "Vue":     vue_extractor.extract,
    "Angular": angular_extractor.extract,
    "HTML":    html_extractor.extract,
}


def parse(code: str, framework: str) -> dict:
    """
    Dispatch raw code to the correct framework extractor.

    Args:
        code      : Raw source code string
        framework : One of React | Vue | Angular | HTML

    Returns:
        Unified summary dict ready for ir_builder.py

    Raises:
        ValueError  if framework is not one of the four supported values
    """
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(
            f"Unsupported framework: '{framework}'. "
            f"Expected one of: {', '.join(sorted(SUPPORTED_FRAMEWORKS))}"
        )

    extractor = _EXTRACTORS[framework]
    summary   = extractor(code)

    return _normalise(summary, framework)


def _normalise(summary: dict, framework: str) -> dict:
    """
    Ensure every summary dict has the same keys regardless of framework.
    Missing keys get safe empty defaults so ir_builder never KeyErrors.
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
