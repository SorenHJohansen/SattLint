from pathlib import Path

from sattlint.analyzers.variables import ICFEntry, validate_icf_entries_against_program
from sattlint.models.ast_model import BasePicture, DataType, ModuleHeader, Simple_DataType, SingleModule, Variable


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


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
