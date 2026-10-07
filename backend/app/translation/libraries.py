"""
Third-party library handling shared by the translation prompt, the validator
and the output guard.

A package written for one framework (react-bootstrap, vuetify, @angular/material)
cannot be imported from another. Each such package is either swapped for its
counterpart in the target framework (same library family) or, for class-based
CSS libraries like Bootstrap, replaced by plain elements with the library's CSS
classes. Framework-neutral packages (lodash, axios, bootstrap's CSS) are kept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

FRAMEWORKS = ("React", "Vue", "Angular")


@dataclass(frozen=True)
class Family:
    name: str
    packages: dict[str, tuple[str, ...]]      # framework -> packages, preferred first
    # Class-based CSS library: plain elements + CSS classes work in every framework.
    css_package: str | None = None
    css_import: str | None = None
    css_url: str | None = None
    css_link_marker: str | None = None        # substring of a <link href> that identifies the library
    class_hint: str = ""


FAMILIES = (
    Family(
        name="Bootstrap",
        packages={
            "React":   ("react-bootstrap", "reactstrap"),
            "Vue":     ("bootstrap-vue-next", "bootstrap-vue"),
            "Angular": ("@ng-bootstrap/ng-bootstrap", "ngx-bootstrap"),
        },
        css_package="bootstrap",
        css_import="bootstrap/dist/css/bootstrap.min.css",
        css_url="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        css_link_marker="bootstrap",
        class_hint='class="card", "card-body", "card-title", "btn btn-primary", "alert alert-success", "form-control"',
    ),
    Family(
        name="Material",
        packages={
            "React":   ("@mui/material", "@material-ui/core"),
            "Vue":     ("vuetify",),
            "Angular": ("@angular/material",),
        },
    ),
    Family(
        name="Ant Design",
        packages={
            "React":   ("antd",),
            "Vue":     ("ant-design-vue",),
            "Angular": ("ng-zorro-antd",),
        },
    ),
    Family(
        name="router",
        packages={
            "React":   ("react-router-dom", "react-router"),
            "Vue":     ("vue-router",),
            "Angular": ("@angular/router",),
        },
    ),
    Family(
        name="Font Awesome",
        packages={
            "React":   ("@fortawesome/react-fontawesome",),
            "Vue":     ("@fortawesome/vue-fontawesome",),
            "Angular": ("@fortawesome/angular-fontawesome",),
        },
    ),
)

# The frameworks' own runtime packages.
CORE_PACKAGES = {
    "React":   {"react", "react-dom", "prop-types"},
    "Vue":     {"vue"},
    "Angular": {"rxjs"},     # plus every @angular/* package
}

# Packages bound to one framework that the naming rules below do not catch.
_BOUND_PACKAGES = {
    "React": {
        "next", "gatsby", "@emotion/react", "@emotion/styled", "styled-components", "@chakra-ui/react",
        "framer-motion", "formik", "recoil", "swr", "@radix-ui",
    },
    "Vue": {"pinia", "vuex", "nuxt", "element-plus", "primevue", "quasar", "naive-ui", "@headlessui/vue", "@vueuse/core"},
    "Angular": {"primeng", "@ngrx/store", "@ngrx/effects"},
}

_NAME_RULES = {
    "React":   re.compile(r"(?:^|[/@-])react(?:$|[/-])|^@mui/|^@material-ui/|^@radix-ui/|^@chakra-ui/"),
    "Vue":     re.compile(r"(?:^|[/@-])vue(?:$|[/-])|^@vue/|^@vueuse/|^vuetify(?:$|/)"),
    "Angular": re.compile(r"^@angular/|^@ng-|^@ngx-|^ng-|^ngx-|^@ngrx/|(?:^|[/-])angular(?:$|[/-])"),
}

_IMPORT = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)["'`]([^"'`\s]+)["'`]"""
)
_STYLESHEET_LINK = re.compile(r"""<link\b[^>]*\bhref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def package_of(specifier: str) -> str | None:
    """npm package of an import specifier; None for relative paths and URLs."""
    if specifier.startswith((".", "/", "~", "#")) or "://" in specifier:
        return None
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") and len(parts) > 1 else parts[0]


_PACKAGE_NAME = re.compile(r"^(?:@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", re.IGNORECASE)


def imported_packages(code: str) -> set[str]:
    """npm packages the code imports (names that are not valid npm names are ignored)."""
    return {
        pkg for spec in _IMPORT.findall(code)
        if (pkg := package_of(spec)) and len(pkg) <= 80 and _PACKAGE_NAME.match(pkg)
    }


def family_of(package: str) -> tuple[Family, str] | None:
    """(family, framework) of a package that belongs to a known library family."""
    for family in FAMILIES:
        for framework, packages in family.packages.items():
            if package in packages:
                return family, framework
    return None


def is_core(package: str, framework: str) -> bool:
    """The framework's own runtime package (react, vue, @angular/core, @angular/forms, ...)."""
    if package in CORE_PACKAGES.get(framework, ()):
        return True
    return framework == "Angular" and package.startswith("@angular/") and family_of(package) is None


def bound_framework(package: str) -> str | None:
    """The framework a package only works in; None for framework-neutral packages."""
    known = family_of(package)
    if known:
        return known[1]
    for framework in FRAMEWORKS:
        if package in CORE_PACKAGES[framework] and package != "rxjs":
            return framework
        if package in _BOUND_PACKAGES[framework] or any(package.startswith(p + "/") for p in _BOUND_PACKAGES[framework]):
            return framework
        if _NAME_RULES[framework].search(package):
            return framework
    return None


def foreign_packages(output: str, target: str) -> list[tuple[str, str]]:
    """(package, framework) for every package the output imports that only works in another framework."""
    found = []
    for package in sorted(imported_packages(output)):
        framework = bound_framework(package)
        if framework and framework != target:
            found.append((package, framework))
    return found


def _css_families(code: str) -> list[Family]:
    """Class-based CSS libraries whose stylesheet the code loads (import or <link>)."""
    packages = imported_packages(code)
    links = [href.lower() for href in _STYLESHEET_LINK.findall(code)]
    return [
        family for family in FAMILIES
        if family.css_package and (
            family.css_package in packages
            or any(family.css_link_marker in href for href in links)
        )
    ]


@dataclass
class LibraryPlan:
    """What the translation should do with the libraries the source uses."""
    notes: list[str] = field(default_factory=list)            # instructions for the prompt
    allowed_packages: set[str] = field(default_factory=set)   # packages the output may add
    allowed_urls: set[str] = field(default_factory=set)       # URLs the output may add
    warnings: list[str] = field(default_factory=list)         # shown to the user with the result


def replacement_hint(package: str, target: str) -> str:
    """How to replace a source-framework package in the target; used in prompts and validator errors."""
    known = family_of(package)
    if not known:
        return (
            f"'{package}' has no known {target} counterpart: do not import it, and render its components "
            "as plain elements with the same content, classes and behaviour"
        )
    family, _ = known
    if family.css_package:
        return (
            f"'{package}' is the {family.name} library: do not import it; use plain HTML elements with "
            f"{family.name} CSS classes instead ({family.class_hint})"
        )
    if target in family.packages:
        return (
            f"'{package}' is a {family.name} library: use its {target} counterpart "
            f"'{family.packages[target][0]}' and that package's own components"
        )
    return (
        f"'{package}' is a {family.name} library with no plain-HTML counterpart: do not import it, and render "
        "its components as plain elements with the same content and behaviour"
    )


def plan(source_code: str, source: str, target: str) -> LibraryPlan:
    result = LibraryPlan()
    css_families = {family.name: family for family in _source_css_families(source_code)}

    for package in sorted(imported_packages(source_code)):
        if bound_framework(package) != source or is_core(package, source):
            continue
        result.notes.append(replacement_hint(package, target))
        known = family_of(package)
        if not known:
            continue
        family, _ = known
        if not family.css_package and target in family.packages:
            result.allowed_packages.update(family.packages[target])

    for family in css_families.values():
        # The notes ask for plain CSS classes, but the family's own package for the target is just as legitimate.
        result.allowed_packages.add(family.css_package)
        result.allowed_packages.update(family.packages.get(target, ()))
        if target == "HTML":
            result.allowed_urls.add(family.css_url)
            result.notes.append(
                f"Load the {family.name} stylesheet with exactly this tag in <head>: "
                f'<link rel="stylesheet" href="{family.css_url}">'
            )
        elif target == "Angular":
            result.notes.append(
                f"Do not import the {family.name} stylesheet in the component file (Angular loads global "
                "CSS from angular.json); only use its CSS classes"
            )
            result.warnings.append(
                f"The component uses {family.name} CSS classes: add '{family.css_import}' to the "
                "\"styles\" array in angular.json"
            )
        else:
            result.notes.append(
                f"Load the {family.name} stylesheet with exactly this import: import '{family.css_import}'"
            )

    return result


# ── Checks on the translated output ───────────────────────────────────────────

_VUE_BUILTIN_TAGS = {
    "Transition", "TransitionGroup", "KeepAlive", "Teleport", "Suspense", "Component", "RouterLink", "RouterView",
}
_COMPONENT_TAG = re.compile(r"<([A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*(?:\.\w+)*|[a-z][\w-]*\.\w[\w.]*)[\s/>]")


def undefined_component_tags(output: str, target: str) -> list[str]:
    """
    JSX-style component tags (<Card>, <Card.Body>) in a template that nothing in the output defines.
    They are what is left when a source-framework UI library is dropped but its markup is kept.
    """
    if target == "Vue":
        template = "\n".join(re.findall(r"<template\b[^>]*>([\s\S]*)</template>", output))
        script = "\n".join(re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", output))
        tags = set(_COMPONENT_TAG.findall(template))
        return sorted(
            tag for tag in tags
            if tag not in _VUE_BUILTIN_TAGS and not re.search(rf"\b{re.escape(tag.split('.')[0])}\b", script)
        )
    if target == "Angular":
        template = "\n".join(re.findall(r"\btemplate\s*:\s*`([\s\S]*?)`", output))
        return sorted(set(_COMPONENT_TAG.findall(template)))
    if target == "HTML":
        markup = re.sub(r"<script\b[\s\S]*?</script>", "", output, flags=re.IGNORECASE)
        return sorted(set(_COMPONENT_TAG.findall(markup)))
    return []


def _source_css_families(source_code: str) -> list[Family]:
    families = {family.name: family for family in _css_families(source_code)}
    for package in imported_packages(source_code):
        known = family_of(package)
        if known and known[0].css_package:
            families[known[0].name] = known[0]
    return list(families.values())


def missing_stylesheets(source_code: str, output: str, target: str) -> list[Family]:
    """CSS libraries the source uses whose stylesheet the output does not load (Angular loads it globally)."""
    if target == "Angular":
        return []
    return [
        family for family in _source_css_families(source_code)
        if not re.search(rf"{re.escape(family.css_link_marker)}[^\"'`\s]*\.css", output, flags=re.IGNORECASE)
    ]
