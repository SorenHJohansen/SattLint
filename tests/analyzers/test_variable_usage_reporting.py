# These tests deliberately exercise private analyzer seams.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)

from sattlint.analyzers import variable_usage_reporting as reporting
from sattlint.models.usage import AccessKind, VariableUsage
from sattlint.reporting.variables_report import IssueKind
from sattlint.resolution.common import ResolvedModulePath

type AliasLink = tuple[Variable, Variable, str]


class _FakeVariableAnalyzer:
    """Typed stand-in for the variable analyzer facade used by the reporting helpers."""

    def __init__(
        self,
        *,
        any_var_index: dict[str, list[Variable]] | None = None,
        alias_links: list[AliasLink] | None = None,
        usage_by_id: dict[int, VariableUsage] | None = None,
        usage: VariableUsage | None = None,
    ) -> None:
        self.any_var_index = any_var_index if any_var_index is not None else {}
        self.alias_links = alias_links if alias_links is not None else []
        self._usage_by_id = usage_by_id
        self._usage = usage

    def run(self, **_kwargs: object) -> list[object]:
        return []

    def get_usage(self, variable: Variable) -> VariableUsage | None:
        if self._usage_by_id is not None:
            mapped = self._usage_by_id.get(id(variable))
            if mapped is not None:
                return mapped
        return self._usage


def _returns[T](value: T) -> Callable[..., T]:
    """Build a patch target that ignores its arguments and returns ``value``."""

    def factory(*_args: object, **_kwargs: object) -> T:
        return value

    return factory


def _patch_analyzer(monkeypatch: pytest.MonkeyPatch, analyzer: _FakeVariableAnalyzer) -> None:
    monkeypatch.setattr(reporting, "VariablesAnalyzer", _returns(analyzer))


def _record_debug(messages: list[str]) -> Callable[..., None]:
    def record(message: object, *args: object) -> None:
        text = str(message)
        messages.append(text % args if args else text)

    return record


def _patch_resolved_module(
    monkeypatch: pytest.MonkeyPatch,
    resolved: ResolvedModulePath,
) -> None:
    monkeypatch.setattr(reporting, "resolve_module_by_strict_path", _returns(resolved))


def _patch_dynamic_module(
    monkeypatch: pytest.MonkeyPatch,
    node: object,
    *,
    path: list[str],
) -> None:
    """Patch strict-path resolution with a node kind the resolver would not hand back."""
    stub = SimpleNamespace(node=node, path=path, display_path_str=".".join(path))
    monkeypatch.setattr(reporting, "resolve_module_by_strict_path", _returns(stub))


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _base_picture(*, submodules: list[SingleModule | FrameModule | ModuleTypeInstance] | None = None) -> BasePicture:
    return BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=submodules or [],
        modulecode=None,
        moduledef=None,
    )


def test_find_module_instances_walks_nested_singlemodule_branch() -> None:
    wanted = ModuleTypeInstance(header=_hdr("WantedNested"), moduletype_name="WantedType", parametermappings=[])
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[wanted],
        modulecode=None,
        parametermappings=[],
    )
    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    results = reporting._find_module_instances(_base_picture(submodules=[parent]), "WantedType")

    assert [(module.header.name, path) for module, path in results] == [
        ("WantedNested", ["Root", "Parent", "Child", "WantedNested"])
    ]


def test_debug_variable_usage_returns_not_found_when_name_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = _FakeVariableAnalyzer()
    _patch_analyzer(monkeypatch, analyzer)

    result = reporting.debug_variable_usage(_base_picture(), "Missing")

    assert result == "No variables named 'Missing' found."


def test_report_datatype_usage_reports_read_write_and_no_field_level_accesses(monkeypatch: pytest.MonkeyPatch) -> None:
    used_var = Variable(name="Dv", datatype=IssueKind.UNUSED.value)
    idle_var = Variable(name="Dv", datatype=IssueKind.UNUSED.value)

    used_usage = VariableUsage(usage_locations=[(["Root", "Unit"], AccessKind.READ)])
    used_usage.field_reads["state"] = [["Root", "Unit"]]
    used_usage.field_writes["state"] = [["Root", "Unit"]]
    idle_usage = VariableUsage()
    usage_by_id = {id(used_var): used_usage, id(idle_var): idle_usage}

    analyzer = _FakeVariableAnalyzer(any_var_index={"dv": [used_var, idle_var]}, usage_by_id=usage_by_id)
    _patch_analyzer(monkeypatch, analyzer)

    result = reporting.report_datatype_usage(_base_picture(), "Dv")

    assert "state: READ+WRITE (R:1, W:1)" in result
    assert "No field-level accesses tracked" in result


def test_report_module_localvar_fields_handles_prefixed_empty_field_paths_and_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_var = Variable(name="Dv", datatype="UsageRecord")
    alias_var = Variable(name="Alias", datatype="UsageRecord")
    alias_usage = VariableUsage()
    alias_usage.field_reads["Leaf"] = [["Root", "Unit"]]
    alias_usage.field_reads[""] = [["Root", "Unit"]]
    alias_usage.field_writes[""] = [["Root", "Unit"]]
    usage_by_id = {id(local_var): VariableUsage(), id(alias_var): alias_usage}

    analyzer = _FakeVariableAnalyzer(usage_by_id=usage_by_id)
    _patch_analyzer(monkeypatch, analyzer)
    _patch_resolved_module(
        monkeypatch,
        ResolvedModulePath(
            node=SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[local_var],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            path=["Root", "Unit"],
            display_path_str="Root.Unit",
        ),
    )
    monkeypatch.setattr(reporting, "find_all_aliases", _returns([(alias_var, "Mapped")]))
    debug_messages: list[str] = []
    monkeypatch.setattr(reporting.log, "debug", _record_debug(debug_messages))

    result = reporting.report_module_localvar_fields(_base_picture(), "Unit", "Dv", debug=True)

    assert "Dv.mapped.leaf [READ]" in result
    assert "Dv.mapped [READ/WRITE]" in result
    assert any("Starting analysis without alias back-propagation" in message for message in debug_messages)
    assert any("Aggregating usages from connected aliases" in message for message in debug_messages)


def test_report_module_localvar_fields_rejects_invalid_module_type(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = _FakeVariableAnalyzer(usage=VariableUsage())
    _patch_analyzer(monkeypatch, analyzer)
    _patch_dynamic_module(
        monkeypatch,
        ModuleTypeDef(
            name="WrongNode",
            moduleparameters=[],
            localvariables=[],
            submodules=[],
            moduledef=None,
            modulecode=None,
        ),
        path=["Root", "WrongNode"],
    )

    with pytest.raises(ValueError, match="Selected module path does not point"):
        reporting.report_module_localvar_fields(_base_picture(), "WrongNode", "Dv")


def test_report_module_localvar_fields_rejects_missing_local_var(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = _FakeVariableAnalyzer(usage=VariableUsage())
    _patch_analyzer(monkeypatch, analyzer)
    _patch_resolved_module(
        monkeypatch,
        ResolvedModulePath(
            node=SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            path=["Root", "Unit"],
            display_path_str="Root.Unit",
        ),
    )

    with pytest.raises(ValueError, match="Local variable 'Dv' not found"):
        reporting.report_module_localvar_fields(_base_picture(), "Unit", "Dv")


def test_report_module_localvar_fields_reports_no_field_accesses(monkeypatch: pytest.MonkeyPatch) -> None:
    local_var = Variable(name="Dv", datatype="UsageRecord")
    analyzer = _FakeVariableAnalyzer(usage=VariableUsage())
    _patch_analyzer(monkeypatch, analyzer)
    _patch_resolved_module(
        monkeypatch,
        ResolvedModulePath(
            node=SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[local_var],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            path=["Root", "Unit"],
            display_path_str="Root.Unit",
        ),
    )
    no_aliases: list[tuple[Variable, str]] = []
    monkeypatch.setattr(reporting, "find_all_aliases", _returns(no_aliases))

    result = reporting.report_module_localvar_fields(_base_picture(), "Unit", "Dv")

    assert "No field-level accesses found within this module." in result


def test_debug_variable_usage_reports_field_and_whole_variable_details(monkeypatch: pytest.MonkeyPatch) -> None:
    variable = Variable(name="Dv", datatype=IssueKind.UNUSED.value)
    usage = VariableUsage(
        usage_locations=[
            (["Root", "Unit"], AccessKind.READ),
            (["Root", "Unit"], AccessKind.READ),
            (["Root", "Area"], AccessKind.WRITE),
        ]
    )
    usage.read = True
    usage.written = True
    usage.field_reads["state"] = [["Root", "Unit"], ["Root", "Unit"], ["Root", "Area"]]
    usage.field_writes["state"] = [["Root", "Unit"], ["Root", "Unit"]]

    analyzer = _FakeVariableAnalyzer(any_var_index={"dv": [variable]}, usage=usage)
    _patch_analyzer(monkeypatch, analyzer)

    result = reporting.debug_variable_usage(_base_picture(), "Dv")

    assert "Usage report for variable name 'Dv' (1 declaration(s)):" in result
    assert "Field reads:" in result
    assert "Root -> Unit (2x)" in result
    assert "Field writes:" in result
    assert "Whole variable:" in result
    assert "R:2 | Root -> Unit" in result
    assert "W:1 | Root -> Area" in result


def test_report_datatype_usage_reports_missing_and_single_direction_accesses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_analyzer = _FakeVariableAnalyzer(usage=VariableUsage())
    _patch_analyzer(monkeypatch, missing_analyzer)

    assert reporting.report_datatype_usage(_base_picture(), "Missing") == "Variable 'Missing' not found."

    read_var = Variable(name="Dv", datatype=IssueKind.UNUSED.value)
    write_var = Variable(name="Dv", datatype=IssueKind.UNUSED.value)
    read_usage = VariableUsage(usage_locations=[(["Root", "Unit"], AccessKind.READ)])
    read_usage.field_reads["read_leaf"] = [["Root", "Unit"]]
    write_usage = VariableUsage(usage_locations=[])
    write_usage.field_writes["write_leaf"] = [["Root", "Unit"], ["Root", "Unit"]]
    usage_by_id = {id(read_var): read_usage, id(write_var): write_usage}

    populated_analyzer = _FakeVariableAnalyzer(any_var_index={"dv": [read_var, write_var]}, usage_by_id=usage_by_id)
    _patch_analyzer(monkeypatch, populated_analyzer)

    result = reporting.report_datatype_usage(_base_picture(), "Dv")

    assert "read_leaf: READ (R:1, W:0)" in result
    assert "write_leaf: WRITE (R:0, W:2)" in result
    assert "Location: Unknown" in result


def test_report_module_localvar_fields_reports_whole_variable_accesses(monkeypatch: pytest.MonkeyPatch) -> None:
    local_var = Variable(name="Dv", datatype="UsageRecord")
    usage = VariableUsage(
        usage_locations=[
            (["Root", "Unit"], AccessKind.READ),
            (["Root", "Unit"], AccessKind.READ),
            (["Root", "Unit", "Child"], AccessKind.WRITE),
            (["Elsewhere"], AccessKind.WRITE),
        ]
    )
    analyzer = _FakeVariableAnalyzer(usage=usage)
    _patch_analyzer(monkeypatch, analyzer)
    _patch_resolved_module(
        monkeypatch,
        ResolvedModulePath(
            node=SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[local_var],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            ),
            path=["Root", "Unit"],
            display_path_str="Root.Unit",
        ),
    )
    no_aliases: list[tuple[Variable, str]] = []
    monkeypatch.setattr(reporting, "find_all_aliases", _returns(no_aliases))

    result = reporting.report_module_localvar_fields(_base_picture(), "Unit", "Dv")

    assert "No field-level accesses found within this module." in result
    assert "WHOLE VARIABLE ACCESSES:" in result
    assert "Reads (2 total, 1 unique location(s)):" in result
    assert "Writes (1 total, 1 unique location(s)):" in result
    assert "Root -> Unit (2x)" in result
    assert "Root -> Unit -> Child" in result
    assert "Whole variable reads: 2" in result
    assert "Whole variable writes: 1" in result


def test_reporting_reads_analyzer_state_through_the_facade() -> None:
    # The facade exposes ``any_var_index``, ``alias_links`` and ``get_usage``;
    # a private-attribute probe would silently keep working after a rename, so
    # the reflection helpers must not come back.
    for helper_name in ("_analyzer_any_var_index", "_analyzer_alias_links", "_analyzer_usage"):
        assert not hasattr(reporting, helper_name)
