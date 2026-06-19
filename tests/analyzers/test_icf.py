# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false
from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.analyzers.icf import (
    format_icf_text,
    parse_icf_file,
    validate_icf_entries_against_program,
)
from sattlint.reporting.icf_report import ICFEntry


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


def test_parse_icf_file_tracks_unit_journal_and_group_context(tmp_path) -> None:
    icf_file = tmp_path / "Program.icf"
    icf_file.write_text(
        "[Unit KaHA221A]\n"
        "[Journal HygienicStatus]\n"
        "[Group JournalData_DCStoMES]\n"
        "OPR_ID=F::Program:StartMaster.KaHA221A.HygienicStatus.T.OPR_ID\n",
        encoding="utf-8",
    )

    entries = parse_icf_file(icf_file)

    assert len(entries) == 1
    assert entries[0].unit == "KaHA221A"
    assert entries[0].journal == "HygienicStatus"
    assert entries[0].group == "JournalData_DCStoMES"


def test_format_icf_text_preserves_nonblank_content_and_distinguishes_major_headers() -> None:
    source = (
        "; header\n"
        "\n"
        "[Unit UnitA]\n"
        "[Journal JournalA]\n"
        "[Group JournalData_DCStoMES]\n"
        "OPR_ID=F::Program:UnitA.JournalA.T.OPR_ID\n"
        "[Operation OpStart]\n"
        "[Group StateChange_DCStoMES]\n"
        "STATE_NO=F::Program:UnitA.OpStart.STATE_NO\n"
    )

    formatted = format_icf_text(source)

    assert [line for line in formatted.splitlines() if line.strip()] == [
        line for line in source.splitlines() if line.strip()
    ]
    assert "\n\n[Journal JournalA]" in formatted
    assert "\n\n[Operation OpStart]" in formatted
    assert format_icf_text(formatted) == formatted


def test_icf_validation_reports_valid_and_invalid_entries() -> None:
    record = DataType(
        name="Rec",
        description=None,
        datecode=None,
        var_list=[Variable(name="FieldA", datatype=Simple_DataType.INTEGER)],
    )
    unit = SingleModule(
        header=_header("Unit"),
        moduledef=None,
        localvariables=[Variable(name="T", datatype="Rec")],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[record],
        submodules=[unit],
    )
    entries = [
        _entry("Tag1", "Program:Unit.T.FieldA", line_no=1),
        _entry("Tag2", "Program:Unit.T.Missing", line_no=2),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="Program")

    assert report.valid_entries == 1
    assert len(report.issues) == 1
    assert report.issues[0].reason == "invalid field path"


def test_icf_validation_skips_placeholder_h_dot_value() -> None:
    bp = BasePicture(
        header=_header("KaHAIsoFK3"),
        submodules=[SingleModule(header=_header("KaHA265A"), moduledef=None)],
    )
    entries = [
        _entry(
            "Fyld_TidTotal",
            "H::.",
            unit="KaHA265A",
            journal="CRY_Fyld1 ,CRY_Fyld1",
            group="JournalData_Parameters",
        )
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="KaHAIsoFK3")

    assert report.skipped_entries == 1
    assert report.valid_entries == 0
    assert len(report.skipped_details) == 1
    assert report.skipped_details[0].reason == "placeholder value"
