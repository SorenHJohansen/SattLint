"""Focused coverage tests for _variables_execution helper branches."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sattline_parser.models.ast_model import BasePicture, ModuleHeader, ModuleTypeDef, Simple_DataType, Variable
from sattlint.analyzers import _variables_execution as variables_execution_module
from sattlint.analyzers.variables import IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


class _UsageStub:
    def __init__(
        self,
        *,
        is_unused: bool = False,
        is_display_only: bool = False,
        is_read_only: bool = False,
        read: bool = False,
        written: bool = False,
    ) -> None:
        self.is_unused = is_unused
        self.is_display_only = is_display_only
        self.is_read_only = is_read_only
        self.read = read
        self.written = written


def test_variables_execution_collect_basepicture_issues_covers_procedure_status_branch() -> None:
    procedure_var = Variable(name="ProcedureVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[procedure_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []
    helper: Any = SimpleNamespace(
        bp=bp,
        _get_usage=lambda variable: _UsageStub(read=True) if variable is procedure_var else _UsageStub(),
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_var else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
        _collect_issues_from_module=lambda *args, **kwargs: None,
    )

    variables_execution_module._collect_basepicture_issues(helper, ["Root"])

    assert issues == [(IssueKind.PROCEDURE_STATUS, ("Root",), "ProcedureVar", "procedure-status", "Status")]


def test_variables_execution_collect_basepicture_issues_covers_write_without_effect_branch() -> None:
    effect_var = Variable(name="EffectVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[effect_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []
    helper: Any = SimpleNamespace(
        bp=bp,
        _get_usage=lambda variable: _UsageStub(read=True, written=True) if variable is effect_var else _UsageStub(),
        _procedure_status_issue=lambda variable, usage: None,
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
        _collect_issues_from_module=lambda *args, **kwargs: None,
    )

    variables_execution_module._collect_basepicture_issues(helper, ["Root"])

    assert issues == [(IssueKind.WRITE_WITHOUT_EFFECT, ("Root",), "EffectVar", "localvariable", None)]


def test_variables_execution_collect_typedef_issues_covers_moduleparameter_procedure_status_branch() -> None:
    procedure_param = Variable(name="ProcedureParam", datatype=Simple_DataType.INTEGER)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[procedure_param],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[moduletype],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []
    helper: Any = SimpleNamespace(
        bp=bp,
        _limit_to_module_path=None,
        _analyze_typedef=lambda *args, **kwargs: None,
        _compute_effective_output_keys=lambda: set(),
        _is_from_root_origin=lambda origin, origin_lib=None: True,
        _get_usage=lambda variable: _UsageStub(read=True) if variable is procedure_param else _UsageStub(),
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_param else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
        _collect_issues_from_module=lambda *args, **kwargs: None,
    )

    variables_execution_module._collect_typedef_issues(helper)

    assert issues == [
        (
            IssueKind.PROCEDURE_STATUS,
            ("Root", "TypeDef:WorkerType"),
            "ProcedureParam",
            "procedure-status",
            "Status",
        )
    ]


def test_variables_execution_collect_typedef_issues_returns_early_for_scoped_runs() -> None:
    helper: Any = SimpleNamespace(
        _limit_to_module_path=["Root", "Scoped"],
        bp=SimpleNamespace(moduletype_defs=[object()]),
        _analyze_typedef=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    assert variables_execution_module._collect_typedef_issues(helper) is None
