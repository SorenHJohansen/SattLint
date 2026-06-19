# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportIncompatibleMethodOverride=false
"""Late ICF helper grouping and path coverage tests split from test_icf_helpers.py."""

from __future__ import annotations

from typing import Any, cast

from tests.test_icf_helpers import (
    BasePicture,
    DataType,
    ICFResolvedEntry,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SimpleNamespace,
    SingleModule,
    Variable,
    _entry,
    _header,
    icf_module,
)


def test_icf_helper_additional_parameter_record_skip_branches(monkeypatch):
    nested = DataType(
        name="NestedRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="Leaf", datatype=Simple_DataType.STRING)],
    )
    root = DataType(
        name="RootRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="Nested", datatype="NestedRecord")],
    )
    type_graph = icf_module.TypeGraph.from_basepicture(
        BasePicture(header=_header("Program"), datatype_defs=[nested, root])
    )
    entry = _entry("Leaf", "Program:Unit.Record.Nested.Leaf", unit="Unit", journal="J", group="JournalData_Parameters")

    weird_root = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype=object(),
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    empty_field_path = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path=".",
        leaf_name="Record",
        datatype=Simple_DataType.STRING,
    )
    unresolved_record = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Missing.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    ghost_record = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="GhostRecord",
        field_path="Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )

    issues = icf_module._validate_parameter_record_completeness(
        type_graph,
        [weird_root, empty_field_path, unresolved_record, ghost_record],
        [
            _entry("Leaf", "H::.", unit="Unit", journal="Other", group="JournalData_Parameters"),
            _entry("Leaf", "H::.", unit="Other", journal="J", group="JournalData_Parameters"),
        ],
    )
    assert issues == []

    original_record = type_graph.record
    call_count = {"RootRecord": 0}

    def _record_once(name: str):
        if name == "RootRecord":
            call_count[name] = call_count.get(name, 0) + 1
            if call_count[name] > 1:
                return None
        return original_record(name)

    monkeypatch.setattr(type_graph, "record", _record_once)
    grouped_entry = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    assert icf_module._validate_parameter_record_completeness(type_graph, [grouped_entry]) == []


def test_icf_helper_remaining_format_and_summary_branches(monkeypatch):
    class _HeaderGhost(str):
        _stripped: str

        def __new__(cls, rendered: str, stripped: str):
            obj = super().__new__(cls, rendered)
            obj._stripped = stripped
            return obj

        def strip(self) -> str:
            return self._stripped

    class _GhostText(str):
        def splitlines(self) -> list[str]:
            return [
                _HeaderGhost("[Unit U]", "[Unit U]"),
                _HeaderGhost("", "[Group G]"),
                _HeaderGhost("", "[Operation O]"),
            ]

        def endswith(self, suffix) -> bool:  # type: ignore[override]
            return True

    formatted = icf_module.format_icf_text(_GhostText("ignored"))
    assert formatted == "[Unit U]\n"

    identical = (("", "", "", "key", "value"),)
    assert icf_module._summarize_signature_diff(identical, identical) == "entry ordering differs"
    assert icf_module._extract_icf_sattline_ref("Program:   ") == (None, None)


def test_icf_helper_remaining_resolution_and_grouping_branches(monkeypatch):
    type_local = Variable(name="TypeLocal", datatype=Simple_DataType.INTEGER)
    type_param = Variable(name="TypeParam", datatype=Simple_DataType.INTEGER)
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

    resolved = SimpleNamespace(
        node=SingleModule(header=_header("Unit"), moduledef=None),
        current_library=None,
        current_file=None,
        display_path_str="Program.Unit",
        path=["Program", "Unit"],
    )
    path_calls: dict[str, int] = {}

    def _always_resolve(_bp, path, moduletype_index=None):
        path_calls[path] = path_calls.get(path, 0) + 1
        if path in {"Program", "Program.Unit", "Program.Unit.Record", "Program.Unit.Record.Field"}:
            if path == "Program.Unit.Record.Field" and path_calls[path] < 3:
                raise ValueError("missing")
            return SimpleNamespace(
                node=resolved.node,
                current_library=None,
                current_file=None,
                display_path_str=path,
                path=path.split("."),
            )
        raise ValueError("missing")

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _always_resolve)
    monkeypatch.setattr(icf_module, "_find_variable_in_module_scope", lambda *_args, **_kwargs: None)
    assert icf_module._resolve_icf_path(base_picture, "Program.Unit.Record.Field") == (None, None, [])
    path_calls["Program.Unit.Record.Field"] = 0
    assert icf_module._describe_unresolved_icf_path(base_picture, "Program.Unit.Record.Field") == (
        "Program.Unit.Record.>>Field<<; missing"
    )

    nested = DataType(
        name="NestedRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="Leaf", datatype=Simple_DataType.STRING)],
    )
    root = DataType(
        name="RootRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="Nested", datatype="NestedRecord"), Variable(name="Other", datatype="NestedRecord")],
    )
    type_graph = icf_module.TypeGraph.from_basepicture(
        BasePicture(header=_header("Program"), datatype_defs=[nested, root])
    )
    entry = _entry("Leaf", "Program:Unit.Record.Nested.Leaf", unit="Unit", journal="J", group="JournalData_Parameters")
    grouped_entry = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    other_unit = ICFResolvedEntry(
        entry=_entry(
            "Leaf", "Program:Other.Record.Nested.Leaf", unit="Other", journal="J", group="JournalData_Parameters"
        ),
        module_path=["Program", "Other"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    other_path = ICFResolvedEntry(
        entry=_entry(
            "Leaf", "Program:Unit.Record.Nested.Leaf", unit="Unit", journal="J", group="JournalData_Parameters"
        ),
        module_path=["Program", "Elsewhere"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    prefix_mismatch = ICFResolvedEntry(
        entry=_entry(
            "Leaf", "Program:Unit.Record.Other.Leaf", unit="Unit", journal="J", group="JournalData_Parameters"
        ),
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Other.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )

    original_record = type_graph.record
    call_count = {"NestedRecord": 0}

    def _record_branch(name: str):
        if name == "NestedRecord":
            call_count[name] = call_count.get(name, 0) + 1
            if call_count[name] > 1:
                return None
        return original_record(name)

    monkeypatch.setattr(type_graph, "record", _record_branch)
    issues = icf_module._validate_parameter_record_completeness(
        type_graph,
        [grouped_entry, other_unit, other_path, prefix_mismatch],
        [
            _entry("Leaf", "H::.", unit="Unit", journal="J", group="WrongGroup"),
        ],
    )
    assert issues == []


def test_icf_helper_final_parse_and_reference_branches(tmp_path, monkeypatch):
    parse_file = tmp_path / "Comments.icf"
    parse_file.write_text("; comment\n# note\n\nKey=Program:Unit.Value\n", encoding="utf-8")
    assert len(icf_module.parse_icf_file(parse_file)) == 1
    assert icf_module._extract_icf_sattline_ref(":Path") == (None, None)

    moduletype = ModuleTypeDef(
        name="WorkerType", moduleparameters=[], localvariables=[], moduledef=None, modulecode=None
    )
    instance = ModuleTypeInstance(header=_header("Child"), moduletype_name="WorkerType")
    monkeypatch.setattr(icf_module, "resolve_moduletype_def_strict", lambda *_args, **_kwargs: moduletype)
    assert (
        icf_module._find_variable_in_module_scope(instance, BasePicture(header=_header("Program")), "missing") is None
    )


def test_icf_helper_final_path_branches(monkeypatch):
    base_picture = BasePicture(header=_header("Program"))

    monkeypatch.setattr(
        icf_module,
        "resolve_module_by_strict_path",
        lambda _bp, path, moduletype_index=None: (
            SimpleNamespace(node=None) if path == "Program.Unit" else (_ for _ in ()).throw(ValueError("missing"))
        ),
    )
    assert icf_module._resolve_icf_path(base_picture, "Program.Unit") == (None, None, [])

    path_calls: dict[str, int] = {}

    def _delayed_prefix_resolve(_bp, path, moduletype_index=None):
        path_calls[path] = path_calls.get(path, 0) + 1
        if path_calls[path] == 1:
            raise ValueError("missing")
        return SimpleNamespace(node=None)

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _delayed_prefix_resolve)
    assert icf_module._describe_unresolved_icf_path(base_picture, "Program.Unit") == "Program.Unit"


def test_icf_helper_final_parameter_grouping_filters():
    nested = DataType(
        name="NestedRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="Leaf", datatype=Simple_DataType.STRING)],
    )
    root = DataType(
        name="RootRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="Nested", datatype="NestedRecord"), Variable(name="Other", datatype="NestedRecord")],
    )
    type_graph = icf_module.TypeGraph.from_basepicture(
        BasePicture(header=_header("Program"), datatype_defs=[nested, root])
    )
    base_entry = _entry(
        "Leaf", "Program:Unit.Record.Nested.Leaf", unit="Unit", journal="J", group="JournalData_Parameters"
    )
    grouped_entry = ICFResolvedEntry(
        entry=base_entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    diff_unit = ICFResolvedEntry(
        entry=_entry(
            "Leaf", "Program:Other.Record.Nested.Leaf", unit="Other", journal="J", group="JournalData_Parameters"
        ),
        module_path=["Program", "Other"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    diff_path = ICFResolvedEntry(
        entry=_entry(
            "Leaf", "Program:Unit.OtherRecord.Nested.Leaf", unit="Unit", journal="J", group="JournalData_Parameters"
        ),
        module_path=["Program", "Elsewhere"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    prefix_mismatch = ICFResolvedEntry(
        entry=_entry(
            "Leaf", "Program:Unit.Record.Other.Leaf", unit="Unit", journal="J", group="JournalData_Parameters"
        ),
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Other.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )

    issues = icf_module._validate_parameter_record_completeness(
        type_graph,
        [grouped_entry, diff_unit, diff_path, prefix_mismatch],
        [
            _entry("Leaf", "H::.", unit="Unit", journal="J", group="WrongGroup"),
        ],
    )
    assert issues == []


def test_icf_helper_final_empty_path_strip_branch():
    class _StripToEmptyPath(str):
        def strip(self) -> str:
            return "Program: "

    assert icf_module._extract_icf_sattline_ref(_StripToEmptyPath("ignored")) == (None, None)


def test_icf_helper_final_prefix_mismatch_filter(monkeypatch):
    fake_type_graph = cast(
        Any,
        SimpleNamespace(
            record=lambda _name: SimpleNamespace(fields_by_key={"leaf": SimpleNamespace(name="Leaf")}),
        ),
    )
    entry = _entry("Leaf", "Program:Unit.Record.Nested.Leaf", unit="Unit", journal="J", group="JournalData_Parameters")
    grouped_entry = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    prefix_mismatch = ICFResolvedEntry(
        entry=_entry(
            "Leaf", "Program:Unit.Record.Other.Child.Leaf", unit="Unit", journal="J", group="JournalData_Parameters"
        ),
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Other.Child.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )

    monkeypatch.setattr(icf_module, "resolve_record_datatype", lambda *_args, **_kwargs: "RecordType")
    assert icf_module._validate_parameter_record_completeness(fake_type_graph, [grouped_entry, prefix_mismatch]) == []
