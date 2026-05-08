from __future__ import annotations

import codecs
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.analyzers import _icf_datatype_resolution as icf_datatype_module
from sattlint.analyzers import icf as icf_module
from sattlint.reporting.icf_report import ICFEntry, ICFResolvedEntry


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _entry(
    key: str,
    value: str,
    *,
    line_no: int = 1,
    section: str | None = None,
    unit: str | None = None,
    journal: str | None = None,
    group: str | None = None,
) -> ICFEntry:
    return ICFEntry(
        file_path=Path("Program.icf"),
        line_no=line_no,
        section=section,
        key=key,
        value=value,
        unit=unit,
        journal=journal,
        group=group,
    )


class _ReplaceOnlyBytes(bytes):
    def decode(self, encoding: str = "utf-8", errors: str = "strict") -> str:
        if errors == "replace":
            return super().decode("latin-1", errors="replace")
        raise UnicodeDecodeError(encoding, b"\xff", 0, 1, "forced failure")


def test_icf_helper_decode_and_format_edges(tmp_path):
    text, encoding, has_bom = icf_module._decode_icf_text(codecs.BOM_UTF8 + b"\xff")
    assert text == "ÿ"
    assert encoding == "cp1252"
    assert has_bom is False

    replace_text, replace_encoding, replace_bom = icf_module._decode_icf_text(_ReplaceOnlyBytes(b"\xff"))
    assert replace_text == "ÿ"
    assert replace_encoding == "latin-1"
    assert replace_bom is False

    assert icf_module._header_spacing("Unknown") == 1
    assert icf_module.format_icf_text("no headers here") == "no headers here"

    formatted = icf_module.format_icf_text("\n\n[Unit UnitA]\nValue=1\n\n\n[Group G]\n")
    assert formatted == "[Unit UnitA]\nValue=1\n\n[Group G]\n"

    icf_file = tmp_path / "Program.icf"
    icf_file.write_bytes(codecs.BOM_UTF8 + b"[Unit UnitA]\r\n[Group G]\r\n")
    result = icf_module.format_icf_file(icf_file)

    assert result.changed is True
    assert icf_file.read_bytes().startswith(codecs.BOM_UTF8)
    assert b"\r\n\r\n[Group G]\r\n" in icf_file.read_bytes()


def test_icf_helper_parse_and_extract_edge_cases(tmp_path):
    icf_file = tmp_path / "Program.icf"
    icf_file.write_text(
        "[Unit KaHA221A]\n[Other Ignored]\nnot an assignment\nKey = Program:KaHA221A.Value\n",
        encoding="utf-8",
    )

    entries = icf_module.parse_icf_file(icf_file)

    assert len(entries) == 1
    assert entries[0].unit == "KaHA221A"
    assert entries[0].operation is None
    assert entries[0].journal is None
    assert entries[0].group is None

    assert icf_module._extract_icf_sattline_ref("Program:") == (None, None)
    assert icf_module._extract_icf_sattline_ref("NoColon") == (None, None)
    assert icf_module._is_placeholder_icf_value("H::.") is True
    assert icf_module._is_placeholder_icf_value("Program:Unit.Value") is False


def test_icf_helper_resolve_unit_type_and_signature_diff(monkeypatch):
    base_picture = BasePicture(header=_header("Program"), submodules=[])
    instance = ModuleTypeInstance(header=_header("KaHA221A"), moduletype_name="TankType")
    family_module = SingleModule(header=_header("KaHA221B"), moduledef=None)

    def _resolve_module(_bp, path, moduletype_index=None):
        if path == "KaHA221A":
            return SimpleNamespace(node=instance)
        if path == "KaHA221B":
            return SimpleNamespace(node=family_module)
        raise ValueError("missing")

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _resolve_module)

    assert icf_module._resolve_unit_type_label(base_picture, "KaHA221A", [_entry("K", "Program:KaHA221A.T.K")]) == (
        "moduletype:tanktype",
        "TankType",
    )
    assert icf_module._resolve_unit_type_label(base_picture, "KaHA221B", [_entry("K", "Program:KaHA221B.T.K")]) == (
        "family:kaha221",
        "family KaHA221",
    )

    extra_only = icf_module._summarize_signature_diff((), (("", "", "", "key", "value"),))
    count_only = icf_module._summarize_signature_diff(
        (("", "", "", "key", "value"), ("", "", "", "key", "value")),
        (("", "", "", "key", "value"),),
    )
    ordering = icf_module._summarize_signature_diff(
        (
            ("Op", "", "", "key-a", "value-a"),
            ("", "Journal", "", "key-b", "value-b"),
        ),
        (
            ("", "Journal", "", "key-b", "value-b"),
            ("Op", "", "", "key-a", "value-a"),
        ),
    )

    assert "extra 1 entries" in extra_only
    assert "entry count 1 != 2" in count_only
    assert "entry ordering differs" in ordering


def test_icf_helper_find_variable_and_path_description_edges(monkeypatch):
    local_var = Variable(name="Local", datatype=Simple_DataType.INTEGER)
    param_var = Variable(name="Param", datatype=Simple_DataType.INTEGER)
    type_local = Variable(name="TypeLocal", datatype=Simple_DataType.INTEGER)
    type_param = Variable(name="TypeParam", datatype=Simple_DataType.INTEGER)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[type_param],
        localvariables=[type_local],
        moduledef=None,
        modulecode=None,
    )
    single = SingleModule(
        header=_header("Unit"),
        moduledef=None,
        moduleparameters=[param_var],
        localvariables=[local_var],
    )
    base_picture = BasePicture(header=_header("Program"), moduletype_defs=[moduletype], submodules=[single])
    instance = ModuleTypeInstance(header=_header("Child"), moduletype_name="WorkerType")

    monkeypatch.setattr(
        icf_module,
        "resolve_moduletype_def_strict",
        lambda *_args, **_kwargs: moduletype,
    )

    assert icf_module._find_variable_in_module_scope(single, base_picture, "local") is local_var
    assert icf_module._find_variable_in_module_scope(single, base_picture, "param") is param_var
    assert icf_module._find_variable_in_module_scope(moduletype, base_picture, "typelocal") is type_local
    assert icf_module._find_variable_in_module_scope(moduletype, base_picture, "typeparam") is type_param
    assert icf_module._find_variable_in_module_scope(instance, base_picture, "typelocal") is type_local

    monkeypatch.setattr(
        icf_module,
        "resolve_moduletype_def_strict",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("missing type")),
    )
    assert icf_module._find_variable_in_module_scope(instance, base_picture, "missing") is None
    assert icf_module._find_variable_in_module_scope(object(), base_picture, "missing") is None

    resolved = SimpleNamespace(
        node=single,
        current_library=None,
        current_file=None,
        display_path_str="Program.Unit",
        path=["Program", "Unit"],
    )

    path_calls: dict[str, int] = {}

    def _resolve_path(_bp, path, moduletype_index=None):
        path_calls[path] = path_calls.get(path, 0) + 1
        if path == "Program.Unit":
            return resolved
        if path == "Program.Unit.Local":
            return SimpleNamespace(
                node=single,
                current_library=None,
                current_file=None,
                display_path_str="Program.Unit.Local",
                path=["Program", "Unit", "Local"],
            )
        if path == "Program.Unit.Missing" and path_calls[path] > 1:
            return SimpleNamespace(
                node=single,
                current_library=None,
                current_file=None,
                display_path_str="Program.Unit.Missing",
                path=["Program", "Unit", "Missing"],
            )
        raise ValueError("strict path missing")

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _resolve_path)

    assert icf_module._resolve_icf_path(base_picture, "") == (None, None, [])
    assert icf_module._resolve_icf_path(base_picture, "Program.Unit.Local.Field") == (resolved, local_var, ["Field"])

    monkeypatch.setattr(icf_module, "_find_variable_in_module_scope", lambda *_args, **_kwargs: None)
    unresolved = icf_module._describe_unresolved_icf_path(base_picture, "Program.Unit.Local")
    assert "resolved to module path Program.Unit.Local" in unresolved

    variable_missing = icf_module._describe_unresolved_icf_path(base_picture, "Program.Unit.Missing")
    assert "variable 'Missing' not found under module Program.Unit" in variable_missing

    def _raising_resolve(_bp, path, moduletype_index=None):
        if path == "Program":
            raise ValueError("bad root")
        raise ValueError("still missing")

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _raising_resolve)
    assert "bad root" in icf_module._describe_unresolved_icf_path(base_picture, "Program.Unit")


def test_icf_helper_validation_edges_and_case_only_regression(monkeypatch):
    signoff_log = DataType(
        name="ACSSignOffLOGData",
        description=None,
        datecode=None,
        var_list=[Variable(name="LogTag", datatype=Simple_DataType.STRING)],
    )
    unit = SingleModule(
        header=_header("KaHA221A"),
        moduledef=None,
        localvariables=[Variable(name="HSSetLogData", datatype="ACSSignOffLOGData")],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[signoff_log],
        submodules=[unit],
    )
    type_graph = icf_module.TypeGraph.from_basepicture(bp)

    ok, detail = icf_module._validate_field_path(type_graph, unit.localvariables[0], [])
    assert ok is False
    assert "non-simple datatype" in str(detail)

    field_ok, field_detail = icf_module._validate_field_path(type_graph, unit.localvariables[0], ["Missing"])
    assert field_ok is False
    assert "not found" in str(field_detail)

    assert (
        icf_module._validate_entry_key_case(
            _entry("LogTag", "Program:KaHA221A.HSSetLogData.LogTag"), variable_name="LogTag", field_segments=[]
        )
        is None
    )

    context_issues = icf_module._validate_entry_context(
        _entry(
            "OPR_ID",
            "Program:WrongUnit.BadPath",
            unit="KaHA221A",
            group="JournalData_DCStoMES",
        ),
        "WrongUnit.BadPath",
    )
    assert {issue.reason for issue in context_issues} == {"unit tag mismatch", "group tag mismatch"}

    entries = [
        _entry(
            "LOGTAG",
            "Program:KaHA221A.HSSetLogData.LogTag",
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
        _entry(
            "LogTag",
            "Program:KaHA221A.HSSetLogData.LogTag",
            line_no=2,
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
    ]
    report = icf_module.validate_icf_entries_against_program(bp, entries, expected_program="Program")
    assert report.valid_entries == 1
    assert len(report.issues) == 1
    assert report.issues[0].reason == "key case mismatch"

    placeholder = _entry("A", "H::.")
    unparseable = _entry("B", "not a path", line_no=2)
    mismatch = _entry("C", "Other:KaHA221A.HSSetLogData.LogTag", line_no=3)
    invalid_leaf = _entry("D", "Program:KaHA221A.HSSetLogData.LogTag", line_no=4)

    monkeypatch.setattr(icf_module, "resolve_leaf_datatype", lambda *_args, **_kwargs: None)
    mixed_report = icf_module.validate_icf_entries_against_program(
        bp,
        [placeholder, unparseable, mismatch, invalid_leaf],
        expected_program="Program",
    )

    assert mixed_report.skipped_entries == 2
    assert {issue.reason for issue in mixed_report.issues} == {"program mismatch", "invalid field path"}


def test_icf_helper_parameter_completeness_and_unit_structure_edges():
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
    bp = BasePicture(header=_header("Program"), datatype_defs=[nested, root], submodules=[])
    type_graph = icf_module.TypeGraph.from_basepicture(bp)
    entry = _entry("Leaf", "Program:Unit.Record.Nested.Leaf", unit="Unit", journal="J", group="JournalData_Parameters")

    direct_entry = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path="Nested.Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.STRING,
    )
    placeholder_mismatch = _entry("Leaf", "H::.", unit="Other", journal="Other", group="JournalData_Parameters")

    issues = icf_module._validate_parameter_record_completeness(type_graph, [direct_entry], [placeholder_mismatch])
    assert issues == []

    pathless_entry = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype="RootRecord",
        field_path=None,
        leaf_name="Record",
        datatype=Simple_DataType.STRING,
    )
    simple_entry = ICFResolvedEntry(
        entry=entry,
        module_path=["Program", "Unit"],
        variable_name="Record",
        root_datatype=Simple_DataType.INTEGER,
        field_path="Leaf",
        leaf_name="Leaf",
        datatype=Simple_DataType.INTEGER,
    )
    assert icf_module._validate_parameter_record_completeness(type_graph, [pathless_entry, simple_entry]) == []

    structure_entries = [
        _entry("Key", "not-a-ref", unit="KaHA221A", group="JournalData_Parameters"),
        _entry("Other", "Program:KaHA221B.Path", line_no=2, unit="KaHA221B", group="JournalData_Parameters"),
    ]
    structure_issues = icf_module._validate_unit_structure(
        BasePicture(
            header=_header("Program"),
            submodules=[
                SingleModule(header=_header("KaHA221A"), moduledef=None),
                SingleModule(header=_header("KaHA221B"), moduledef=None),
            ],
        ),
        structure_entries,
    )
    assert len(structure_issues) == 1
    assert structure_issues[0].reason == "unit structure drift"


def test_icf_helper_additional_format_summary_and_parse_branches(tmp_path, monkeypatch):
    formatted = icf_module.format_icf_text("[Unit U]\n[Group G]\n[Operation O]\n")
    assert formatted == "[Unit U]\n\n[Group G]\n\n\n[Operation O]\n"

    parse_file = tmp_path / "Ops.icf"
    parse_file.write_text(
        "[Unit KaHA221A]\n[Operation Start]\n[Journal HygienicStatus]\nKey=Program:KaHA221A.Value\n",
        encoding="utf-8",
    )
    parsed = icf_module.parse_icf_file(parse_file)
    assert parsed[0].operation == "Start"
    assert parsed[0].journal == "HygienicStatus"

    assert icf_module._path_endswith(["OnlyOne"], ("A", "B")) is False

    overflow = icf_module._summarize_signature_diff(
        (),
        (
            ("", "", "", "a", "1"),
            ("", "", "", "b", "2"),
            ("", "", "", "c", "3"),
            ("", "", "", "d", "4"),
        ),
    )
    assert "..." in overflow
    assert icf_module._summarize_signature_diff((), ()) == "entry ordering differs"

    monkeypatch.setattr(
        icf_module,
        "resolve_module_by_strict_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("missing")),
    )
    fallback = icf_module._resolve_unit_type_label(
        BasePicture(header=_header("Program"), submodules=[]),
        "KaHA221A",
        [_entry("K", "Program:KaHA221A.T.K")],
    )
    assert fallback == ("family:kaha221", "family KaHA221")


def test_icf_helper_additional_path_and_field_validation_branches(monkeypatch):
    record = DataType(
        name="NestedRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="Inner", datatype="LeafRecord")],
    )
    leaf = DataType(
        name="LeafRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
    )
    bp = BasePicture(header=_header("Program"), datatype_defs=[record, leaf], submodules=[])
    type_graph = icf_module.TypeGraph.from_basepicture(bp)
    record_var = Variable(name="Rec", datatype="NestedRecord")
    simple_var = Variable(name="Count", datatype=Simple_DataType.INTEGER)
    unknown_var = SimpleNamespace(name="Mystery", datatype=None)

    assert icf_module._validate_field_path(type_graph, simple_var, ["Field"]) == (
        False,
        "datatype integer has no field 'Field'",
    )
    assert icf_module._validate_field_path(type_graph, cast(Any, unknown_var), ["Field"]) == (
        False,
        "field 'Field' not found in datatype None",
    )
    final_record_ok, final_record_detail = icf_module._validate_field_path(type_graph, record_var, ["Inner"])
    assert final_record_ok is False
    assert final_record_detail == "non-simple datatype LeafRecord referenced without field path"

    assert icf_datatype_module.resolve_leaf_datatype(type_graph, simple_var, ["Field"]) is None
    assert icf_datatype_module.resolve_leaf_datatype(type_graph, cast(Any, unknown_var), ["Field"]) is None
    assert icf_datatype_module.resolve_leaf_datatype(type_graph, record_var, ["Missing"]) is None
    assert icf_datatype_module.resolve_record_datatype(type_graph, simple_var.datatype, ["Field"]) is None
    assert icf_datatype_module.resolve_record_datatype(type_graph, unknown_var.datatype, ["Field"]) is None
    assert icf_datatype_module.resolve_record_datatype(type_graph, record_var.datatype, ["Missing"]) is None
    assert icf_datatype_module.resolve_record_datatype(type_graph, record_var.datatype, ["Inner", "Value"]) is None

    resolved = SimpleNamespace(
        node=SingleModule(header=_header("Unit"), moduledef=None, localvariables=[record_var]),
        current_library=None,
        current_file=None,
        display_path_str="Program.Unit",
        path=["Program", "Unit"],
    )

    def _resolve_for_paths(_bp, path, moduletype_index=None):
        if path == "Program.Unit":
            return resolved
        raise ValueError("missing")

    monkeypatch.setattr(icf_module, "resolve_module_by_strict_path", _resolve_for_paths)
    monkeypatch.setattr(icf_module, "_find_variable_in_module_scope", lambda *_args, **_kwargs: None)
    assert icf_module._resolve_icf_path(bp, "Program.Unit.Record.Field") == (None, None, [])

    monkeypatch.setattr(icf_module, "_find_variable_in_module_scope", lambda *_args, **_kwargs: record_var)
    unresolved = icf_module._describe_unresolved_icf_path(bp, "Program.Unit.Record.Field")
    assert "unresolved after variable 'Rec' under module Program.Unit" in unresolved
    assert icf_module._describe_unresolved_icf_path(bp, "") == ""


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
