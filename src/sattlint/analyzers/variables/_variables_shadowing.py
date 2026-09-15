"""Variable shadowing collection inside the variables analyzer."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)

from ...reporting.variables_report import IssueKind, VariableIssue
from ...resolution.common import resolve_moduletype_def_strict
from ...utils.casefolding import casefold_key


@dataclass(frozen=True)
class _ShadowedVar:
    variable: Variable
    module_path: list[str]


def _typed_base_picture(self: Any) -> BasePicture:
    return cast(BasePicture, self.bp)


def collect_shadowing_issues(self: Any) -> None:
    """Append ``IssueKind.SHADOWING`` issues for locals hiding outer names."""
    if getattr(self, "_limit_to_module_path", None) is not None:
        return

    bp = _typed_base_picture(self)
    root_path = [bp.header.name]
    parent_locals = {
        casefold_key(variable.name): _ShadowedVar(variable, root_path) for variable in (bp.localvariables or [])
    }
    _walk_shadowing_submodules(
        self,
        bp,
        bp.submodules or [],
        parent_path=root_path,
        parent_locals=parent_locals,
        current_library=getattr(bp, "origin_lib", None),
    )


def _walk_shadowing_submodules(
    self: Any,
    bp: BasePicture,
    children: Iterable[SingleModule | FrameModule | ModuleTypeInstance],
    parent_path: list[str],
    parent_locals: dict[str, _ShadowedVar],
    current_library: str | None,
) -> None:
    for child in children:
        child_path = [*parent_path, child.header.name]

        if isinstance(child, SingleModule):
            child_locals = list(child.localvariables or [])
            _check_shadowing(self, child_locals, parent_locals, child_path)
            next_locals = _extend_locals(parent_locals, child_locals, child_path)
            _walk_shadowing_submodules(
                self,
                bp,
                child.submodules or [],
                parent_path=child_path,
                parent_locals=next_locals,
                current_library=current_library,
            )
        elif isinstance(child, FrameModule):
            _walk_shadowing_submodules(
                self,
                bp,
                child.submodules or [],
                parent_path=child_path,
                parent_locals=parent_locals,
                current_library=current_library,
            )
        else:
            moduletype = _resolve_moduletype(self, bp, child, current_library)
            if moduletype is None:
                continue
            if not self._is_from_root_origin(
                getattr(moduletype, "origin_file", None),
                getattr(moduletype, "origin_lib", None),
            ):
                continue

            child_locals = list(moduletype.localvariables or [])
            _check_shadowing(self, child_locals, parent_locals, child_path)
            next_locals = _extend_locals(parent_locals, child_locals, child_path)
            _walk_shadowing_submodules(
                self,
                bp,
                moduletype.submodules or [],
                parent_path=child_path,
                parent_locals=next_locals,
                current_library=moduletype.origin_lib or current_library,
            )


def _resolve_moduletype(
    self: Any,
    bp: BasePicture,
    inst: ModuleTypeInstance,
    current_library: str | None,
) -> ModuleTypeDef | None:
    try:
        return resolve_moduletype_def_strict(
            bp,
            inst.moduletype_name,
            current_library=current_library,
            unavailable_libraries=getattr(self, "_unavailable_libraries", None) or set(),
        )
    except ValueError:
        return None


def _check_shadowing(
    self: Any,
    locals_: Iterable[Variable],
    parent_locals: dict[str, _ShadowedVar],
    module_path: list[str],
) -> None:
    append_issue = getattr(self, "_append_issue", None)
    for var in locals_:
        key = casefold_key(var.name)
        parent = parent_locals.get(key)
        if not parent:
            continue
        parent_path = ".".join(parent.module_path)
        issue = VariableIssue(
            kind=IssueKind.SHADOWING,
            module_path=module_path.copy(),
            variable=var,
            role=f"shadows {parent.variable.name!r} from {parent_path}",
            source_variable=parent.variable,
        )
        if callable(append_issue):
            append_issue(issue)
        else:
            self._issues.append(issue)


def _extend_locals(
    parent_locals: dict[str, _ShadowedVar],
    locals_: Iterable[Variable],
    module_path: list[str],
) -> dict[str, _ShadowedVar]:
    merged = dict(parent_locals)
    for var in locals_:
        merged[casefold_key(var.name)] = _ShadowedVar(var, module_path)
    return merged


__all__ = ["collect_shadowing_issues"]
