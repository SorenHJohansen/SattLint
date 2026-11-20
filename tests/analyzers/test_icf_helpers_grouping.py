# These tests deliberately exercise private analyzer seams.
# pyright: reportPrivateUsage=false

"""Late ICF helper grouping and path coverage tests split from test_icf_helpers.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from sattlint.resolution.common import ResolvedModulePath
from tests.analyzers.test_icf_helpers import (
    BasePicture,
    ModuleTypeDef,
    ModuleTypeInstance,
    ScalarDatatype,
    SimpleNamespace,
    SingleModule,
    Variable,
    _header,
    icf_module,
    summarize_icf_unit_drift,
)


def test_icf_helper_remaining_summary_branches(monkeypatch: pytest.MonkeyPatch):
    identical = (("", "", "", "key", "value"),)
    drift = icf_module._build_unit_drift("Current", "Type", "Reference", identical, identical)
    assert summarize_icf_unit_drift(drift).endswith("entry ordering differs")
    assert icf_module._extract_icf_sattline_ref("Program:   ") == (None, None)


def test_icf_helper_remaining_resolution_branches(monkeypatch: pytest.MonkeyPatch):
    type_local = Variable(name="TypeLocal", datatype=ScalarDatatype.INTEGER)
    type_param = Variable(name="TypeParam", datatype=ScalarDatatype.INTEGER)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[type_param],
        localvariables=[type_local],
        moduledef=None,
        modulecode=None,
    )
    instance = ModuleTypeInstance(header=_header("Child"), moduletype_name="WorkerType")
    base_picture = BasePicture(header=_header("Program"), moduletype_defs=[moduletype])

    assert (
        icf_module._find_variable_in_module_scope(
            instance,
            base_picture,
            "typelocal",
            moduletype_index={"workertype": [moduletype]},
        )
        is type_local
    )
    assert (
        icf_module._find_variable_in_module_scope(
            instance,
            base_picture,
            "typeparam",
            moduletype_index={"workertype": [moduletype]},
        )
        is type_param
    )
    assert icf_module._find_variable_in_module_scope(moduletype, base_picture, "missing") is None

    resolved = ResolvedModulePath(
        node=SingleModule(header=_header("Unit"), moduledef=None),
        display_path_str="Program.Unit",
        path=["Program", "Unit"],
    )
    path_calls: dict[str, int] = {}

    def _always_resolve(
        _bp: BasePicture,
        path: str,
        moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    ) -> ResolvedModulePath:
        del moduletype_index
        path_calls[path] = path_calls.get(path, 0) + 1
        if path in {"Program", "Program.Unit", "Program.Unit.Record", "Program.Unit.Record.Field"}:
            if path == "Program.Unit.Record.Field" and path_calls[path] < 3:
                raise ValueError("missing")
            return ResolvedModulePath(node=resolved.node, display_path_str=path, path=path.split("."))
        raise ValueError("missing")

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _always_resolve)

    def _no_variable(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(icf_module, "_find_variable_in_module_scope", _no_variable)
    assert icf_module._resolve_icf_path(base_picture, "Program.Unit.Record.Field") == (None, None, [])
    path_calls["Program.Unit.Record.Field"] = 0
    assert icf_module._describe_unresolved_icf_path(base_picture, "Program.Unit.Record.Field") == (
        "Program.Unit.Record.>>Field<<; missing"
    )


def test_icf_helper_final_parse_and_reference_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    parse_file = tmp_path / "Comments.icf"
    parse_file.write_text("; comment\n# note\n\nKey=Program:Unit.Value\n", encoding="utf-8")
    assert len(icf_module.parse_icf_file(parse_file)) == 1
    assert icf_module._extract_icf_sattline_ref(":Path") == (None, None)

    moduletype = ModuleTypeDef(
        name="WorkerType", moduleparameters=[], localvariables=[], moduledef=None, modulecode=None
    )
    instance = ModuleTypeInstance(header=_header("Child"), moduletype_name="WorkerType")

    def _resolve_moduletype(*_args: object, **_kwargs: object) -> ModuleTypeDef:
        return moduletype

    monkeypatch.setattr(icf_module, "resolve_moduletype_def_strict", _resolve_moduletype)
    assert (
        icf_module._find_variable_in_module_scope(instance, BasePicture(header=_header("Program")), "missing") is None
    )


def test_icf_helper_final_path_branches(monkeypatch: pytest.MonkeyPatch):
    base_picture = BasePicture(header=_header("Program"))

    def _resolve_without_node(
        _bp: BasePicture,
        path: str,
        moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    ) -> SimpleNamespace:
        del moduletype_index
        if path == "Program.Unit":
            return SimpleNamespace(node=None)
        raise ValueError("missing")

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _resolve_without_node)
    assert icf_module._resolve_icf_path(base_picture, "Program.Unit") == (None, None, [])

    path_calls: dict[str, int] = {}

    def _delayed_prefix_resolve(
        _bp: BasePicture,
        path: str,
        moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    ) -> SimpleNamespace:
        del moduletype_index
        path_calls[path] = path_calls.get(path, 0) + 1
        if path_calls[path] == 1:
            raise ValueError("missing")
        return SimpleNamespace(node=None)

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _delayed_prefix_resolve)
    assert icf_module._describe_unresolved_icf_path(base_picture, "Program.Unit") == "Program.Unit"


def test_icf_helper_final_empty_path_strip_branch():
    class _StripToEmptyPath(str):
        def strip(self, _chars: str | None = None) -> str:
            return "Program: "

    assert icf_module._extract_icf_sattline_ref(_StripToEmptyPath("ignored")) == (None, None)
