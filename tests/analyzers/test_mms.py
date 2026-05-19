from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    IntLiteral,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.mms import (
    _emit_datatype_mismatch_issues,
    _emit_dead_tag_issues,
    _emit_duplicate_tag_issues,
    _emit_naming_drift_issues,
    _InterfaceInventoryEntry,
    analyze_mms_interface_variables,
)
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.reporting.icf_report import ICFEntry


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def _issue_kinds(report) -> set[str]:
    return {issue.kind for issue in report.issues}


def _inventory_entry(**overrides: object) -> _InterfaceInventoryEntry:
    entry = {
        "source_kind": "mms",
        "module_path": ["Program", "Unit"],
        "moduletype_name": "MMSWriteVar",
        "parameter_name": "WriteData",
        "source_variable": "ExportValue",
        "source_datatype": "INTEGER",
        "source_leaf_name": "ExportValue",
        "external_tag": "Plant.Result",
        "external_tag_key": "plant.result",
        "tag_family_key": "plant|result",
        "direction": "outgoing",
        "write_fields": (),
        "write_note": None,
    }
    entry.update(overrides)
    return _InterfaceInventoryEntry(**entry)


def test_mms_interface_flags_dead_tags_for_unwritten_outgoing_variables() -> None:
    sender = ModuleTypeInstance(
        header=_hdr("SendToOpc"),
        moduletype_name="MMSWriteVar",
        parametermappings=[
            ParameterMapping(
                target=_varref("RemoteVarName"),
                source_type=const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal="Plant.Result",
            ),
            ParameterMapping(
                target=_varref("LocalVariable"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("ExportValue"),
                source_literal=None,
            ),
        ],
    )
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="ExportValue", datatype=Simple_DataType.INTEGER)],
        submodules=[sender],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_mms_interface_variables(bp)

    dead_tag_issues = [issue for issue in report.issues if issue.kind == "mms.dead_tag"]
    assert len(dead_tag_issues) == 1
    assert "Plant.Result" in dead_tag_issues[0].message


def test_mms_interface_flags_duplicate_tags_and_datatype_mismatch_from_icf_entries() -> None:
    unit_a = SingleModule(
        header=_hdr("UnitA"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Result", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    unit_b = SingleModule(
        header=_hdr("UnitB"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="Result", datatype=Simple_DataType.BOOLEAN)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[unit_a, unit_b],
        modulecode=None,
        moduledef=None,
    )
    entries = [
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section="JournalData_DCStoMES",
            key="ResultCode",
            value="Program:UnitA.Result",
        ),
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=2,
            section="JournalData_DCStoMES",
            key="ResultCode",
            value="Program:UnitB.Result",
        ),
    ]

    report = analyze_mms_interface_variables(bp, icf_entries=entries)

    assert "mms.duplicate_tag" in _issue_kinds(report)
    assert "mms.datatype_mismatch" in _issue_kinds(report)


def test_mms_interface_flags_naming_drift_from_icf_entries() -> None:
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="ResultText", datatype=Simple_DataType.STRING)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
    )
    entries = [
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section="JournalData_DCStoMES",
            key="ResultText",
            value="Program:Unit.ResultText",
        ),
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=2,
            section="JournalData_DCStoMES",
            key="RESULT_TEXT",
            value="Program:Unit.ResultText",
        ),
    ]

    report = analyze_mms_interface_variables(bp, icf_entries=entries)

    naming_drift_issues = [issue for issue in report.issues if issue.kind == "mms.naming_drift"]
    assert len(naming_drift_issues) == 1
    assert "ResultText" in naming_drift_issues[0].message
    assert "RESULT_TEXT" in naming_drift_issues[0].message


def test_mms_interface_collects_nested_typedef_mappings_and_write_locations() -> None:
    wrapper = ModuleTypeDef(
        name="WriterWrapper",
        moduleparameters=[Variable(name="MappedOut", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("SendToOpc"),
                moduletype_name="MMSWriteVar",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("WriteData"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("MappedOut"),
                        source_literal=None,
                    ),
                    ParameterMapping(
                        target=_varref("RemoteVarName"),
                        source_type=const.KEY_VALUE,
                        is_duration=False,
                        is_source_global=False,
                        source=None,
                        source_literal="Plant.Result",
                    ),
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Program.s",
    )
    unit = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="ExportValue", datatype=Simple_DataType.INTEGER)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Wrapper"),
                moduletype_name="WriterWrapper",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("MappedOut"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("ExportValue"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("ExportValue"), IntLiteral(1))],
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Program"),
        datatype_defs=[],
        moduletype_defs=[wrapper],
        localvariables=[],
        submodules=[unit],
        modulecode=None,
        moduledef=None,
        origin_file="Program.s",
    )

    report = analyze_mms_interface_variables(bp)

    assert report.issues == []
    assert len(report.hits) == 1
    hit = report.hits[0]
    assert hit.module_path == ["Program", "Unit", "Wrapper", "SendToOpc"]
    assert hit.source_variable == "ExportValue"


def test_mms_interface_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "mms-interface" in specs
    assert specs["mms-interface"].enabled is True


def test_mms_helper_emitters_skip_entries_without_required_tag_keys() -> None:
    missing_external_key = _inventory_entry(external_tag_key=None)
    missing_family_key = _inventory_entry(tag_family_key=None)
    missing_external_tag = _inventory_entry(external_tag=None)

    assert _emit_duplicate_tag_issues([missing_external_key]) == []
    assert _emit_datatype_mismatch_issues([missing_external_key]) == []
    assert _emit_naming_drift_issues([missing_family_key, missing_external_tag]) == []


def test_mms_dead_tag_helper_skips_missing_tags_and_unknown_write_notes() -> None:
    missing_external_tag = _inventory_entry(external_tag=None)
    unknown_write_note = _inventory_entry(write_note="unknown (variable not found)")

    assert _emit_dead_tag_issues([missing_external_tag, unknown_write_note]) == []
