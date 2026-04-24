from pathlib import Path

from sattlint.analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
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


def test_parse_icf_file_tracks_unit_journal_and_group_context(tmp_path):
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


def test_icf_validation_reports_valid_and_invalid_entries():
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
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section=None,
            key="Tag1",
            value="Program:Unit.T.FieldA",
        ),
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=2,
            section=None,
            key="Tag2",
            value="Program:Unit.T.Missing",
        ),
    ]

    report = validate_icf_entries_against_program(
        bp,
        entries,
        expected_program="Program",
    )

    assert report.valid_entries == 1
    assert len(report.issues) == 1
    assert report.issues[0].reason == "invalid field path"


def test_icf_validation_marks_unresolved_module_segment_in_detail():
    display = SingleModule(
        header=_header("Display"),
        moduledef=None,
    )
    level2 = FrameModule(header=_header("L2"), submodules=[display])
    level1 = FrameModule(header=_header("L1"), submodules=[level2])
    unit = SingleModule(
        header=_header("Unit"),
        moduledef=None,
        submodules=[level1],
    )
    start_master = FrameModule(header=_header("StartMaster"), submodules=[unit])
    bp = BasePicture(
        header=_header("Program"),
        submodules=[start_master],
    )

    entries = [
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section=None,
            key="Tag1",
            value="Program:StartMaster.Unit.L1.L2.Dilute.T.OPR_ID",
        )
    ]

    report = validate_icf_entries_against_program(
        bp,
        entries,
        expected_program="Program",
    )

    assert report.valid_entries == 0
    assert len(report.issues) == 1
    assert report.issues[0].reason == "unresolved path"
    assert ">>Dilute<<" in (report.issues[0].detail or "")
    assert "Valid next segments" in (report.issues[0].detail or "")


def test_icf_validation_prefers_draft_moduletype_locals_after_instance_path_resolution():
    dilute_log = DataType(
        name="DiluteLogType",
        description=None,
        datecode=None,
        var_list=[Variable(name="RunNumber", datatype=Simple_DataType.INTEGER)],
    )

    transfer_fallback = ModuleTypeDef(
        name="TransferType",
        origin_lib="ProjectLib",
        origin_file="KaHAXModullLib.x",
        localvariables=[],
    )
    transfer_source = ModuleTypeDef(
        name="TransferType",
        origin_lib="ProjectLib",
        origin_file="KaHAXDiluteLib.s",
        localvariables=[Variable(name="Dilute", datatype="DiluteLogType")],
    )
    wrapper = ModuleTypeDef(
        name="WrapperType",
        origin_lib="ProjectLib",
        origin_file="KaHAXDiluteLib.s",
        submodules=[ModuleTypeInstance(header=_header("Transfer"), moduletype_name="TransferType")],
    )

    bp = BasePicture(
        header=_header("Program"),
        origin_lib="AppLib",
        origin_file="Root.s",
        datatype_defs=[dilute_log],
        moduletype_defs=[transfer_fallback, transfer_source, wrapper],
        submodules=[ModuleTypeInstance(header=_header("Wrapper"), moduletype_name="WrapperType")],
        library_dependencies={"applib": ["projectlib"]},
    )

    entries = [
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section=None,
            key="Tag1",
            value="Program:Wrapper.Transfer.Dilute.RunNumber",
        ),
    ]

    report = validate_icf_entries_against_program(
        bp,
        entries,
        expected_program="Program",
    )

    assert report.valid_entries == 1
    assert report.issues == []


def test_icf_validation_requires_simple_leaf_datatype():
    record = DataType(
        name="Rec",
        description=None,
        datecode=None,
        var_list=[Variable(name="FieldA", datatype=Simple_DataType.INTEGER)],
    )

    unit = SingleModule(
        header=_header("Unit"),
        moduledef=None,
        localvariables=[
            Variable(name="Simple", datatype=Simple_DataType.REAL),
            Variable(name="Complex", datatype="Rec"),
        ],
    )

    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[record],
        submodules=[unit],
    )

    entries = [
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section=None,
            key="Tag1",
            value="Program:Unit.Simple",
        ),
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=2,
            section=None,
            key="Tag2",
            value="Program:Unit.Complex",
        ),
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=3,
            section=None,
            key="Tag3",
            value="Program:Unit.Complex.FieldA",
        ),
    ]

    report = validate_icf_entries_against_program(
        bp,
        entries,
        expected_program="Program",
    )

    assert report.valid_entries == 2
    assert len(report.issues) == 1
    assert report.issues[0].reason == "invalid field path"
    assert report.issues[0].detail == "non-simple datatype Rec referenced without field path"


def test_icf_validation_exposes_resolved_entries_for_reuse():
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
        ICFEntry(
            file_path=Path("Program.icf"),
            line_no=1,
            section="JournalData_DCStoMES",
            key="Tag1",
            value="Program:Unit.T.FieldA",
        ),
    ]

    report = validate_icf_entries_against_program(
        bp,
        entries,
        expected_program="Program",
    )

    assert report.valid_entries == 1
    assert len(report.resolved_entries) == 1
    assert report.resolved_entries[0].module_path == ["Program", "Unit"]
    assert report.resolved_entries[0].field_path == "FieldA"
    assert report.resolved_entries[0].leaf_name == "FieldA"
    assert report.resolved_entries[0].datatype is Simple_DataType.INTEGER


def test_icf_validation_flags_unit_and_group_mismatches():
    channel = DataType(
        name="Channel",
        description=None,
        datecode=None,
        var_list=[Variable(name="OPR_ID", datatype=Simple_DataType.INTEGER)],
    )
    journal = DataType(
        name="JournalRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="T", datatype="Channel"),
            Variable(name="S", datatype="Channel"),
            Variable(name="J", datatype=Simple_DataType.INTEGER),
        ],
    )
    unit = SingleModule(
        header=_header("KaHA221A"),
        moduledef=None,
        localvariables=[Variable(name="HygienicStatus", datatype="JournalRecord")],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[channel, journal],
        submodules=[unit],
    )

    entries = [
        _entry(
            "OPR_ID",
            "Program:KaHA221A.HygienicStatus.T.OPR_ID",
            unit="KaHA221B",
            journal="HygienicStatus",
            group="JournalData_DCStoMES",
        ),
        _entry(
            "Tag1",
            "Program:KaHA221A.HygienicStatus.OPR_ID",
            line_no=2,
            unit="KaHA221A",
            journal="OtherJournal",
            group="JournalData_Parameters",
        ),
        _entry(
            "OPR_ID",
            "Program:KaHA221A.HygienicStatus.S.OPR_ID",
            line_no=3,
            unit="KaHA221A",
            journal="HygienicStatus",
            group="JournalData_DCStoMES",
        ),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="Program")
    reasons = [issue.reason for issue in report.issues]

    assert "unit tag mismatch" in reasons
    assert "group tag mismatch" in reasons


def test_icf_validation_flags_missing_journal_parameter_record_fields():
    dilute = DataType(
        name="DiluteRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="RunNumber", datatype=Simple_DataType.INTEGER),
            Variable(name="Duration", datatype=Simple_DataType.INTEGER),
            Variable(name="PWVolume", datatype=Simple_DataType.REAL),
        ],
    )
    unit = SingleModule(
        header=_header("KaHA221X"),
        moduledef=None,
        localvariables=[Variable(name="Dilute", datatype="DiluteRecord")],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[dilute],
        submodules=[unit],
    )

    entries = [
        _entry(
            "RunNumber",
            "Program:KaHA221X.Dilute.RunNumber",
            unit="KaHA221X",
            journal="Transfer",
            group="JournalData_Parameters",
        ),
        _entry(
            "Duration",
            "Program:KaHA221X.Dilute.Duration",
            line_no=2,
            unit="KaHA221X",
            journal="Transfer",
            group="JournalData_Parameters",
        ),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="Program")
    summary = report.summary()

    assert any(issue.reason == "missing journal parameter fields" for issue in report.issues)
    assert any("PWVolume" in (issue.detail or "") for issue in report.issues)
    assert "record Dilute missing 1 fields: PWVolume" in summary
    assert "RunNumber =>" not in summary


def test_icf_validation_treats_nested_parameter_descendants_as_parent_record_coverage():
    user = DataType(
        name="UserRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="UserID", datatype=Simple_DataType.STRING),
            Variable(name="UserName", datatype=Simple_DataType.STRING),
        ],
    )
    log_value = DataType(
        name="LogValueRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="status", datatype=Simple_DataType.INTEGER),
            Variable(name="meaning", datatype=Simple_DataType.STRING),
            Variable(name="User", datatype="UserRecord"),
        ],
    )
    unit = SingleModule(
        header=_header("KaHA221A"),
        moduledef=None,
        localvariables=[Variable(name="LogValue", datatype="LogValueRecord")],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[user, log_value],
        submodules=[unit],
    )

    entries = [
        _entry(
            "Status",
            "Program:KaHA221A.LogValue.status",
            unit="KaHA221A",
            journal="HygienicStatus",
            group="JournalData_Parameters",
        ),
        _entry(
            "Meaning",
            "Program:KaHA221A.LogValue.meaning",
            line_no=2,
            unit="KaHA221A",
            journal="HygienicStatus",
            group="JournalData_Parameters",
        ),
        _entry(
            "UserID",
            "Program:KaHA221A.LogValue.User.UserID",
            line_no=3,
            unit="KaHA221A",
            journal="HygienicStatus",
            group="JournalData_Parameters",
        ),
        _entry(
            "UserName",
            "Program:KaHA221A.LogValue.User.UserName",
            line_no=4,
            unit="KaHA221A",
            journal="HygienicStatus",
            group="JournalData_Parameters",
        ),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="Program")

    assert report.valid_entries == 4
    assert not any(issue.reason == "missing journal parameter fields" for issue in report.issues)


def test_icf_validation_checks_nested_journal_parameter_record_only():
    cry_fill = DataType(
        name="CryFillRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Tid_Start", datatype=Simple_DataType.TIME),
            Variable(name="Tid_Stop", datatype=Simple_DataType.TIME),
        ],
    )
    dv = DataType(
        name="DvRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="AIT001AlarmEnable", datatype=Simple_DataType.BOOLEAN),
            Variable(name="AITT001EnableAlarm", datatype=Simple_DataType.BOOLEAN),
            Variable(name="CRY_Fyld1", datatype="CryFillRecord"),
        ],
    )
    unit = SingleModule(
        header=_header("KaHA265A"),
        moduledef=None,
        localvariables=[Variable(name="Dv", datatype="DvRecord")],
    )
    bp = BasePicture(
        header=_header("KaHAIsoFK3"),
        datatype_defs=[cry_fill, dv],
        submodules=[unit],
    )

    entries = [
        _entry(
            "Tid_Start",
            "KaHAIsoFK3:KaHA265A.Dv.CRY_Fyld1.Tid_Start",
            unit="KaHA265A",
            journal="CRY_Fyld1 ,CRY_Fyld1",
            group="JournalData_Parameters",
        ),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="KaHAIsoFK3")

    issue = next(issue for issue in report.issues if issue.reason == "missing journal parameter fields")
    assert "Dv.CRY_Fyld1" in (issue.detail or "")
    assert "Tid_Stop" in (issue.detail or "")
    assert "AIT001AlarmEnable" not in (issue.detail or "")
    assert "AITT001EnableAlarm" not in (issue.detail or "")


def test_icf_validation_accepts_flattened_statechange_channel_names():
    response = DataType(
        name="ResponseRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="RESULT_CODE", datatype=Simple_DataType.INTEGER),
            Variable(name="RESULT_TEXT", datatype=Simple_DataType.STRING),
            Variable(name="RET_VAL", datatype=Simple_DataType.INTEGER),
            Variable(name="RET_TEXT", datatype=Simple_DataType.STRING),
        ],
    )
    unit = SingleModule(
        header=_header("KaHA221B"),
        moduledef=None,
        localvariables=[
            Variable(name="PUC_Stop_STATE_NO", datatype=Simple_DataType.INTEGER),
            Variable(name="PUC_Stop_S", datatype="ResponseRecord"),
        ],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[response],
        submodules=[unit],
    )

    entries = [
        _entry(
            "STATE_NO",
            "Program:KaHA221B.PUC_Stop_STATE_NO",
            unit="KaHA221B",
            group="StateChange_DCStoMES",
        ),
        _entry(
            "RESULT_CODE",
            "Program:KaHA221B.PUC_Stop_S.RESULT_CODE",
            line_no=2,
            unit="KaHA221B",
            group="StateChange_MEStoDCS",
        ),
        _entry(
            "RESULT_TEXT",
            "Program:KaHA221B.PUC_Stop_S.RESULT_TEXT",
            line_no=3,
            unit="KaHA221B",
            group="StateChange_MEStoDCS",
        ),
        _entry(
            "LMES_RET_VAL",
            "Program:KaHA221B.PUC_Stop_S.RET_VAL",
            line_no=4,
            unit="KaHA221B",
            group="StateChange_MEStoDCS",
        ),
        _entry(
            "LMES_RET_TEXT",
            "Program:KaHA221B.PUC_Stop_S.RET_TEXT",
            line_no=5,
            unit="KaHA221B",
            group="StateChange_MEStoDCS",
        ),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="Program")

    assert not any(issue.reason == "group tag mismatch" for issue in report.issues)


def test_icf_validation_flags_unit_structure_drift_within_same_sattline_type_only():
    channel = DataType(
        name="Channel",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="OPR_ID", datatype=Simple_DataType.INTEGER),
            Variable(name="CR_ID", datatype=Simple_DataType.INTEGER),
        ],
    )
    journal = DataType(
        name="JournalRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="T", datatype="Channel")],
    )
    appl_tank = ModuleTypeDef(
        name="ApplTank",
        localvariables=[Variable(name="HygienicStatus", datatype="JournalRecord")],
    )
    r_unit = ModuleTypeDef(
        name="RUnit",
        localvariables=[Variable(name="HygienicStatus", datatype="JournalRecord")],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[channel, journal],
        moduletype_defs=[appl_tank, r_unit],
        submodules=[
            FrameModule(
                header=_header("StartMaster"),
                submodules=[
                    ModuleTypeInstance(header=_header("KaHA221A"), moduletype_name="ApplTank"),
                    ModuleTypeInstance(header=_header("KaHA221B"), moduletype_name="ApplTank"),
                    ModuleTypeInstance(header=_header("KaHA221R"), moduletype_name="RUnit"),
                ],
            )
        ],
    )

    entries = [
        _entry(
            "OPR_ID",
            "Program:StartMaster.KaHA221A.HygienicStatus.T.OPR_ID",
            unit="KaHA221A",
            journal="HygienicStatus",
            group="JournalData_DCStoMES",
        ),
        _entry(
            "CR_ID",
            "Program:StartMaster.KaHA221A.HygienicStatus.T.CR_ID",
            line_no=2,
            unit="KaHA221A",
            journal="HygienicStatus",
            group="JournalData_DCStoMES",
        ),
        _entry(
            "OPR_ID",
            "Program:StartMaster.KaHA221B.HygienicStatus.T.OPR_ID",
            line_no=3,
            unit="KaHA221B",
            journal="HygienicStatus",
            group="JournalData_DCStoMES",
        ),
        _entry(
            "OPR_ID",
            "Program:StartMaster.KaHA221R.HygienicStatus.T.OPR_ID",
            line_no=4,
            unit="KaHA221R",
            journal="HygienicStatus",
            group="JournalData_DCStoMES",
        ),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="Program")
    summary = report.summary()

    drift_issues = [issue for issue in report.issues if issue.reason == "unit structure drift"]
    assert len(drift_issues) == 1
    assert drift_issues[0].entry.unit == "KaHA221B"
    assert drift_issues[0].detail == "unit type ApplTank differs from KaHA221A: missing 1 entries"
    assert "OPR_ID =>" not in summary


def test_icf_validation_ignores_case_only_key_differences_for_unit_structure():
    record = DataType(
        name="RecipeRecord",
        description=None,
        datecode=None,
        var_list=[Variable(name="tid_henstandMax", datatype=Simple_DataType.REAL)],
    )
    appl_tank = ModuleTypeDef(
        name="ApplTank",
        localvariables=[Variable(name="MR", datatype="RecipeRecord")],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[record],
        moduletype_defs=[appl_tank],
        submodules=[
            FrameModule(
                header=_header("StartMaster"),
                submodules=[
                    ModuleTypeInstance(header=_header("KaHA221A"), moduletype_name="ApplTank"),
                    ModuleTypeInstance(header=_header("KaHA221B"), moduletype_name="ApplTank"),
                ],
            )
        ],
    )

    entries = [
        _entry(
            "tid_henstandMax_VALUE",
            "Program:StartMaster.KaHA221A.MR.tid_henstandMax",
            unit="KaHA221A",
            group="Recipe_Parameters",
        ),
        _entry(
            "Tid_HenstandMax_VALUE",
            "Program:StartMaster.KaHA221B.MR.tid_henstandMax",
            line_no=2,
            unit="KaHA221B",
            group="Recipe_Parameters",
        ),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="Program")

    assert not any(issue.reason == "unit structure drift" for issue in report.issues)


def test_icf_validation_treats_acssignoff_meaning_as_optional_parameter_field():
    user = DataType(
        name="ACSUserType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="UserID", datatype=Simple_DataType.STRING),
            Variable(name="UserName", datatype=Simple_DataType.STRING),
        ],
    )
    signoff = DataType(
        name="ACSSignOffType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Time", datatype=Simple_DataType.TIME),
            Variable(name="User", datatype="ACSUserType"),
            Variable(name="Privilege", datatype=Simple_DataType.STRING),
            Variable(name="SignOffResult", datatype=Simple_DataType.STRING),
            Variable(name="Meaning", datatype=Simple_DataType.STRING),
        ],
    )
    signoff_log = DataType(
        name="ACSSignOffLOGData",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="SignOffResult", datatype="ACSSignOffType"),
            Variable(name="Description", datatype=Simple_DataType.STRING),
            Variable(name="Answer", datatype=Simple_DataType.STRING),
            Variable(name="LogTag", datatype=Simple_DataType.STRING),
        ],
    )
    unit = SingleModule(
        header=_header("KaHA221A"),
        moduledef=None,
        localvariables=[Variable(name="HSSetLogData", datatype="ACSSignOffLOGData")],
    )
    bp = BasePicture(
        header=_header("Program"),
        datatype_defs=[user, signoff, signoff_log],
        submodules=[unit],
    )

    entries = [
        _entry(
            "UserID",
            "Program:KaHA221A.HSSetLogData.SignOffResult.User.UserID",
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
        _entry(
            "UserName",
            "Program:KaHA221A.HSSetLogData.SignOffResult.User.UserName",
            line_no=2,
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
        _entry(
            "Time",
            "Program:KaHA221A.HSSetLogData.SignOffResult.Time",
            line_no=3,
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
        _entry(
            "Privilege",
            "Program:KaHA221A.HSSetLogData.SignOffResult.Privilege",
            line_no=4,
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
        _entry(
            "SignOffResult",
            "Program:KaHA221A.HSSetLogData.SignOffResult.SignOffResult",
            line_no=5,
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
        _entry(
            "Description",
            "Program:KaHA221A.HSSetLogData.Description",
            line_no=6,
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
        _entry(
            "Answer",
            "Program:KaHA221A.HSSetLogData.Answer",
            line_no=7,
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
        _entry(
            "LogTag",
            "Program:KaHA221A.HSSetLogData.LogTag",
            line_no=8,
            unit="KaHA221A",
            journal="HSSignOffLog",
            group="JournalData_Parameters",
        ),
    ]

    report = validate_icf_entries_against_program(bp, entries, expected_program="Program")

    assert report.valid_entries == 8
    assert not any(issue.reason == "missing journal parameter fields" for issue in report.issues)
