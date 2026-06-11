"""Module-level issue collection helpers for variable analysis."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sattline_parser.models.ast_model import FrameModule, ModuleTypeDef, ModuleTypeInstance, SingleModule, Variable

from ...reporting.variables_report import IssueKind, VariableIssue

if TYPE_CHECKING:
    from . import VariablesAnalyzer


_MODULE_VARIABLE_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.UNUSED,
        IssueKind.READ_ONLY_NON_CONST,
        IssueKind.UI_ONLY,
        IssueKind.PROCEDURE_STATUS,
        IssueKind.NEVER_READ,
        IssueKind.WRITE_WITHOUT_EFFECT,
    }
)


def _selected_issue_kinds(self: object) -> frozenset[IssueKind] | set[IssueKind] | None:
    return getattr(self, "_selected_issue_kinds", None)


def _should_collect_issue_kind(self: object, kind: IssueKind) -> bool:
    selected_kinds = _selected_issue_kinds(self)
    return selected_kinds is None or kind in selected_kinds


def _should_collect_any_issue_kinds(self: object, kinds: frozenset[IssueKind]) -> bool:
    selected_kinds = _selected_issue_kinds(self)
    return selected_kinds is None or bool(selected_kinds & kinds)


def _append_issue(
    self: VariablesAnalyzer,
    kind: IssueKind,
    path: list[str],
    variable: Variable,
    role: str,
    field_path: str | None = None,
) -> None:
    self.append_issue(
        VariableIssue(
            kind=kind,
            module_path=path.copy(),
            variable=variable,
            role=role,
            field_path=field_path,
        )
    )


def _collect_variable_issues(
    self: VariablesAnalyzer,
    variables: list[Variable] | None,
    path: list[str],
    *,
    role: str,
) -> None:
    collect_unused = _should_collect_issue_kind(self, IssueKind.UNUSED)
    collect_procedure_status = _should_collect_issue_kind(self, IssueKind.PROCEDURE_STATUS)
    collect_ui_only = _should_collect_issue_kind(self, IssueKind.UI_ONLY)
    collect_read_only_non_const = _should_collect_issue_kind(self, IssueKind.READ_ONLY_NON_CONST)
    collect_never_read = _should_collect_issue_kind(self, IssueKind.NEVER_READ)
    collect_write_without_effect = _should_collect_issue_kind(self, IssueKind.WRITE_WITHOUT_EFFECT)

    if not (
        collect_unused
        or collect_procedure_status
        or collect_ui_only
        or collect_read_only_non_const
        or collect_never_read
        or collect_write_without_effect
    ):
        return

    for variable in variables or []:
        usage = self.get_usage(variable)
        if collect_unused and usage.is_unused:
            _append_issue(self, IssueKind.UNUSED, path, variable, role=role)
            continue

        procedure_status = self.procedure_status_issue(variable, usage) if collect_procedure_status else None
        if collect_procedure_status and procedure_status is not None:
            status_role, field_path = procedure_status
            _append_issue(
                self,
                IssueKind.PROCEDURE_STATUS,
                path,
                variable,
                role=status_role,
                field_path=field_path,
            )
            continue

        if collect_ui_only and usage.is_display_only:
            _append_issue(self, IssueKind.UI_ONLY, path, variable, role=role)
            continue

        if (
            collect_read_only_non_const
            and role == "localvariable"
            and usage.is_read_only
            and not bool(variable.const)
            and self.is_const_candidate(variable)
        ):
            _append_issue(self, IssueKind.READ_ONLY_NON_CONST, path, variable, role=role)
            continue

        if (
            collect_never_read
            and role == "localvariable"
            and usage.written
            and not usage.read
            and not self.has_ignorable_output_binding(variable)
        ):
            _append_issue(self, IssueKind.NEVER_READ, path, variable, role=role)
            continue

        if (
            collect_write_without_effect
            and usage.read
            and usage.written
            and not self.has_output_effect(variable, path)
            and not self.has_procedure_status_binding(variable)
        ):
            _append_issue(self, IssueKind.WRITE_WITHOUT_EFFECT, path, variable, role=role)


def collect_issues_from_module(
    self: VariablesAnalyzer,
    mod: SingleModule | FrameModule | ModuleTypeInstance,
    path: list[str],
    current_library: str | None = None,
    *,
    resolve_moduletype_def: Callable[..., ModuleTypeDef],
) -> None:
    if not _should_collect_any_issue_kinds(self, _MODULE_VARIABLE_ISSUE_KINDS):
        return

    my_path = [*path, mod.header.name]
    if isinstance(mod, SingleModule):
        _collect_variable_issues(self, mod.moduleparameters, my_path, role="moduleparameter")
        _collect_variable_issues(self, mod.localvariables, my_path, role="localvariable")
        for child in mod.submodules or []:
            collect_issues_from_module(
                self,
                child,
                my_path,
                current_library=current_library,
                resolve_moduletype_def=resolve_moduletype_def,
            )
        return

    if isinstance(mod, FrameModule):
        for child in mod.submodules or []:
            collect_issues_from_module(
                self,
                child,
                my_path,
                current_library=current_library,
                resolve_moduletype_def=resolve_moduletype_def,
            )
        return

    try:
        moduletype = resolve_moduletype_def(
            self.bp,
            mod.moduletype_name,
            current_library=current_library,
            unavailable_libraries=self.unavailable_libraries,
        )
    except ValueError:
        return

    if not self.is_from_root_origin(
        getattr(moduletype, "origin_file", None),
        getattr(moduletype, "origin_lib", None),
    ):
        return

    if self.limit_to_module_path is None:
        return

    _collect_variable_issues(self, moduletype.moduleparameters, my_path, role="moduleparameter")
    _collect_variable_issues(self, moduletype.localvariables, my_path, role="localvariable")

    child_library = moduletype.origin_lib or current_library
    for child in moduletype.submodules or []:
        collect_issues_from_module(
            self,
            child,
            my_path,
            current_library=child_library,
            resolve_moduletype_def=resolve_moduletype_def,
        )
