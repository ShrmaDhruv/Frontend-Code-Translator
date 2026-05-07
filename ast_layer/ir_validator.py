from dataclasses import dataclass, field
from ast_layer.ir_schema import IR

SUPPORTED_FRAMEWORKS = {"React", "Vue", "Angular", "HTML"}

VALID_HOOKS = {
    "onMount",
    "onDestroy",
    "onBeforeMount",
    "onBeforeDestroy",
    "onUpdate",
    "onBeforeUpdate",
    "onCreate",
    "onAfterViewInit",
    "onChanges",
    "onEveryRender",
}


@dataclass
class ValidationResult:
    is_valid: bool
    errors:   list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate(ir: IR) -> ValidationResult:
    errors   = []
    warnings = []

    if not ir.component or not ir.component.strip():
        errors.append("component name is missing or empty")

    if ir.framework not in SUPPORTED_FRAMEWORKS:
        errors.append(
            f"framework '{ir.framework}' is not one of: "
            f"{', '.join(sorted(SUPPORTED_FRAMEWORKS))}"
        )

    for i, prop in enumerate(ir.props):
        if not prop.name or not prop.name.strip():
            errors.append(f"props[{i}] is missing a name field")

    for i, state in enumerate(ir.state):
        if not state.name or not state.name.strip():
            errors.append(f"state[{i}] is missing a name field")

    for i, method in enumerate(ir.methods):
        if not method.name or not method.name.strip():
            errors.append(f"methods[{i}] is missing a name field")

    for i, lc in enumerate(ir.lifecycle):
        if lc.hook not in VALID_HOOKS:
            errors.append(
                f"lifecycle[{i}] has unknown hook '{lc.hook}'. "
                f"Expected one of: {', '.join(sorted(VALID_HOOKS))}"
            )

    for i, computed in enumerate(ir.computed):
        if not computed.name or not computed.name.strip():
            errors.append(f"computed[{i}] is missing a name field")

    if not ir.state:
        warnings.append("state is empty — may be valid for stateless components")

    if not ir.props:
        warnings.append("props is empty — may be valid for root components")

    if not ir.methods:
        warnings.append("methods is empty")

    for method in ir.methods:
        if not method.body.strip():
            warnings.append(f"method '{method.name}' has an empty body")

    for lc in ir.lifecycle:
        if not lc.body.strip():
            warnings.append(f"lifecycle hook '{lc.hook}' has an empty body")

    for computed in ir.computed:
        if not computed.expression.strip():
            warnings.append(f"computed '{computed.name}' has no expression")

    return ValidationResult(
        is_valid = len(errors) == 0,
        errors   = errors,
        warnings = warnings,
    )
