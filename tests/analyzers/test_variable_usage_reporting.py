from __future__ import annotations

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
from sattlint.models.usage import VariableUsage
from sattlint.reporting.variables_report import IssueKind


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
    analyzer = SimpleNamespace(run=lambda: [], _any_var_index={}, _get_usage=lambda variable: None)
    monkeypatch.setattr(reporting, "VariablesAnalyzer", lambda *args, **kwargs: analyzer)

    result = reporting.debug_variable_usage(_base_picture(), "Missing")

    assert result == "No variables named 'Missing' found."


def test_analyze_datatype_usage_reports_read_write_and_no_field_level_accesses(monkeypatch: pytest.MonkeyPatch) -> None:
    used_var = Variable(name="Dv", datatype=IssueKind.UNUSED.value)
    idle_var = Variable(name="Dv", datatype=IssueKind.UNUSED.value)

    used_usage = VariableUsage(usage_locations=[(["Root", "Unit"], "read")])
    used_usage.field_reads["state"] = [["Root", "Unit"]]
    used_usage.field_writes["state"] = [["Root", "Unit"]]
    idle_usage = VariableUsage()
    usage_by_id = {id(used_var): used_usage, id(idle_var): idle_usage}

    analyzer = SimpleNamespace(
        run=lambda: [],
        _any_var_index={"dv": [used_var, idle_var]},
        _get_usage=lambda variable: usage_by_id[id(variable)],
    )
    monkeypatch.setattr(reporting, "VariablesAnalyzer", lambda *args, **kwargs: analyzer)

    result = reporting.analyze_datatype_usage(_base_picture(), "Dv")

    assert "state: READ+WRITE (R:1, W:1)" in result
    assert "No field-level accesses tracked" in result


def test_analyze_module_localvar_fields_handles_prefixed_empty_field_paths_and_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local_var = Variable(name="Dv", datatype="UsageRecord")
    alias_var = Variable(name="Alias", datatype="UsageRecord")
    alias_usage = VariableUsage()
    alias_usage.field_reads["Leaf"] = [["Root", "Unit"]]
    alias_usage.field_reads[""] = [["Root", "Unit"]]
    alias_usage.field_writes[""] = [["Root", "Unit"]]
    usage_by_id = {id(local_var): VariableUsage(), id(alias_var): alias_usage}

    analyzer = SimpleNamespace(
        run=lambda **kwargs: [],
        _alias_links=[],
        _get_usage=lambda variable: usage_by_id[id(variable)],
    )
    monkeypatch.setattr(reporting, "VariablesAnalyzer", lambda *args, **kwargs: analyzer)
    monkeypatch.setattr(
        reporting,
        "resolve_module_by_strict_path",
        lambda *args, **kwargs: SimpleNamespace(
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
    monkeypatch.setattr(reporting, "find_all_aliases", lambda *args, **kwargs: [(alias_var, "Mapped")])
    debug_messages: list[str] = []
    monkeypatch.setattr(
        reporting.log, "debug", lambda message, *args: debug_messages.append(message % args if args else message)
    )

    result = reporting.analyze_module_localvar_fields(_base_picture(), "Unit", "Dv", debug=True)

    assert "Dv.mapped.leaf [READ]" in result
    assert "Dv.mapped [READ/WRITE]" in result
    assert any("Starting analysis without alias back-propagation" in message for message in debug_messages)
    assert any("Aggregating usages from connected aliases" in message for message in debug_messages)


def test_analyze_module_localvar_fields_rejects_invalid_module_type(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = SimpleNamespace(run=lambda **kwargs: [], _alias_links=[], _get_usage=lambda variable: VariableUsage())
    monkeypatch.setattr(reporting, "VariablesAnalyzer", lambda *args, **kwargs: analyzer)
    monkeypatch.setattr(
        reporting,
        "resolve_module_by_strict_path",
        lambda *args, **kwargs: SimpleNamespace(
            node=ModuleTypeDef(
                name="WrongNode",
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                moduledef=None,
                modulecode=None,
                parametermappings=[],
            ),
            path=["Root", "WrongNode"],
            display_path_str="Root.WrongNode",
        ),
    )

    with pytest.raises(ValueError, match="Selected module path does not point"):
        reporting.analyze_module_localvar_fields(_base_picture(), "WrongNode", "Dv")


def test_analyze_module_localvar_fields_rejects_missing_local_var(monkeypatch: pytest.MonkeyPatch) -> None:
    analyzer = SimpleNamespace(run=lambda **kwargs: [], _alias_links=[], _get_usage=lambda variable: VariableUsage())
    monkeypatch.setattr(reporting, "VariablesAnalyzer", lambda *args, **kwargs: analyzer)
    monkeypatch.setattr(
        reporting,
        "resolve_module_by_strict_path",
        lambda *args, **kwargs: SimpleNamespace(
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
        reporting.analyze_module_localvar_fields(_base_picture(), "Unit", "Dv")


def test_analyze_module_localvar_fields_reports_no_field_accesses(monkeypatch: pytest.MonkeyPatch) -> None:
    local_var = Variable(name="Dv", datatype="UsageRecord")
    analyzer = SimpleNamespace(
        run=lambda **kwargs: [],
        _alias_links=[],
        _get_usage=lambda variable: VariableUsage(),
    )
    monkeypatch.setattr(reporting, "VariablesAnalyzer", lambda *args, **kwargs: analyzer)
    monkeypatch.setattr(
        reporting,
        "resolve_module_by_strict_path",
        lambda *args, **kwargs: SimpleNamespace(
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
    monkeypatch.setattr(reporting, "find_all_aliases", lambda *args, **kwargs: [])

    result = reporting.analyze_module_localvar_fields(_base_picture(), "Unit", "Dv")

    assert "No field-level accesses found within this module." in result
