from __future__ import annotations

import re
from dataclasses import dataclass

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)

from ..casefolding import casefold_equal, casefold_key
from .framework import Issue, format_report_header
from .shared._walk_utils import iter_nested_modules
from .shared.variable_utils import matches_root_origin

_IDENTIFIER_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")


@dataclass
class UnsafeDefaultsReport:
    name: str
    issues: list[Issue]

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Unsafe defaults", self.name, status="ok")
            lines.append("No unsafe default values found.")
            return "\n".join(lines)

        lines = format_report_header("Unsafe defaults", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("  - Boolean defaults:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"      * [{location}] {issue.message}")
        return "\n".join(lines)


class UnsafeDefaultsAnalyzer:
    def __init__(self, base_picture: BasePicture) -> None:
        self.bp = base_picture
        self._issues: list[Issue] = []

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        self._check_variables(root_path, self.bp.localvariables)
        self._walk_modules(self.bp.submodules or [], root_path)

        for moduletype in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(getattr(moduletype, "origin_file", None)):
                continue
            self._walk_moduletype_def(moduletype, root_path)

        return self._issues

    def _walk_moduletype_def(
        self,
        moduletype: ModuleTypeDef,
        root_path: list[str],
    ) -> None:
        module_path = [*root_path, f"TypeDef:{moduletype.name}"]
        self._check_variables(module_path, moduletype.moduleparameters)
        self._check_variables(module_path, moduletype.localvariables)
        self._walk_modules(moduletype.submodules or [], module_path)

    def _walk_modules(
        self,
        children: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_path: list[str],
    ) -> None:
        for child, child_path in iter_nested_modules(children, parent_path=parent_path):
            if not isinstance(child, SingleModule):
                continue
            self._check_variables(child_path, child.moduleparameters)
            self._check_variables(child_path, child.localvariables)

    def _check_variables(
        self,
        module_path: list[str],
        variables: list[Variable] | None,
    ) -> None:
        for variable in variables or []:
            reason = self._unsafe_default_reason(variable)
            if reason is None:
                continue

            self._issues.append(
                Issue(
                    kind="unsafe_defaults.true_boolean_default",
                    message=f"Boolean variable {variable.name!r} defaults to True, {reason}.",
                    module_path=module_path.copy(),
                    data={
                        "variable": variable.name,
                        "default": True,
                        "reason": reason,
                    },
                )
            )

    def _unsafe_default_reason(self, variable: Variable) -> str | None:
        if variable.init_value is not True:
            return None
        if not casefold_equal(variable.datatype_text, "boolean"):
            return None

        tokens = _identifier_tokens(variable.name)
        if "bypass" in tokens:
            return "which can bypass safety checks from startup"
        if "enable" in tokens:
            return "which can activate equipment or logic from startup"
        return None

    def _is_from_root_origin(self, origin_file: str | None) -> bool:
        return matches_root_origin(origin_file, getattr(self.bp, "origin_file", None))


def _identifier_tokens(name: str) -> tuple[str, ...]:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    tokens: list[str] = []
    for part in parts:
        matches = _IDENTIFIER_TOKEN_RE.findall(part)
        if matches:
            tokens.extend(casefold_key(match) for match in matches)
        else:
            tokens.append(casefold_key(part))
    return tuple(tokens)


def analyze_unsafe_defaults(base_picture: BasePicture) -> UnsafeDefaultsReport:
    analyzer = UnsafeDefaultsAnalyzer(base_picture)
    return UnsafeDefaultsReport(name=base_picture.header.name, issues=analyzer.run())
