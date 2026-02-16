"""Variable shadowing analysis (locals hiding outer/global vars)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)
from ..reporting.variables_report import IssueKind, VariableIssue, VariablesReport
from ..resolution.common import resolve_moduletype_def_strict


@dataclass(frozen=True)
class ShadowedVar:
    variable: Variable
    module_path: list[str]


class ShadowingAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._issues: list[VariableIssue] = []

    @property
    def issues(self) -> list[VariableIssue]:
        return self._issues

    def run(self) -> list[VariableIssue]:
        root_path = [self.bp.header.name]
        parent_locals = {
            v.name.casefold(): ShadowedVar(v, root_path)
            for v in (self.bp.localvariables or [])
        }
        self._walk_submodules(
            self.bp.submodules or [],
            parent_path=root_path,
            parent_locals=parent_locals,
            current_library=self.bp.origin_lib,
        )
        return self._issues

    def _walk_submodules(
        self,
        children: Iterable[SingleModule | FrameModule | ModuleTypeInstance],
        parent_path: list[str],
        parent_locals: dict[str, ShadowedVar],
        current_library: str | None,
    ) -> None:
        for child in children:
            child_path = parent_path + [child.header.name]

            if isinstance(child, SingleModule):
                child_locals = list(child.localvariables or [])
                self._check_shadowing(child_locals, parent_locals, child_path)
                next_locals = self._extend_locals(
                    parent_locals, child_locals, child_path
                )
                self._walk_submodules(
                    child.submodules or [],
                    parent_path=child_path,
                    parent_locals=next_locals,
                    current_library=current_library,
                )
            elif isinstance(child, FrameModule):
                self._walk_submodules(
                    child.submodules or [],
                    parent_path=child_path,
                    parent_locals=parent_locals,
                    current_library=current_library,
                )
            elif isinstance(child, ModuleTypeInstance):
                mt = self._resolve_moduletype(child, current_library)
                if mt is None:
                    continue

                child_locals = list(mt.localvariables or [])
                self._check_shadowing(child_locals, parent_locals, child_path)
                next_locals = self._extend_locals(
                    parent_locals, child_locals, child_path
                )
                self._walk_submodules(
                    mt.submodules or [],
                    parent_path=child_path,
                    parent_locals=next_locals,
                    current_library=mt.origin_lib or current_library,
                )

    def _resolve_moduletype(
        self,
        inst: ModuleTypeInstance,
        current_library: str | None,
    ) -> ModuleTypeDef | None:
        try:
            return resolve_moduletype_def_strict(
                self.bp,
                inst.moduletype_name,
                current_library=current_library,
                unavailable_libraries=self._unavailable_libraries,
            )
        except ValueError:
            return None

    def _check_shadowing(
        self,
        locals_: Iterable[Variable],
        parent_locals: dict[str, ShadowedVar],
        module_path: list[str],
    ) -> None:
        for var in locals_:
            key = var.name.casefold()
            parent = parent_locals.get(key)
            if not parent:
                continue
            parent_path = ".".join(parent.module_path)
            self._issues.append(
                VariableIssue(
                    kind=IssueKind.SHADOWING,
                    module_path=module_path.copy(),
                    variable=var,
                    role=f"shadows {parent.variable.name!r} from {parent_path}",
                    source_variable=parent.variable,
                )
            )

    def _extend_locals(
        self,
        parent_locals: dict[str, ShadowedVar],
        locals_: Iterable[Variable],
        module_path: list[str],
    ) -> dict[str, ShadowedVar]:
        merged = dict(parent_locals)
        for var in locals_:
            merged[var.name.casefold()] = ShadowedVar(var, module_path)
        return merged


def analyze_shadowing(
    base_picture: BasePicture,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
) -> VariablesReport:
    """Analyze local variables that hide outer or global variables."""
    _ = debug
    analyzer = ShadowingAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )
    issues = analyzer.run()
    return VariablesReport(basepicture_name=base_picture.header.name, issues=issues)
