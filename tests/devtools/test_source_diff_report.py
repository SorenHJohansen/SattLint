import json
from pathlib import Path
from typing import Any

from pytest import CaptureFixture, MonkeyPatch

from sattlint.devtools import source_diff_report

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "source_diff"


def _sections_by_kind(pair: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {section["kind"]: section for section in pair["sections"]}


def test_build_source_diff_report_explicit_pair_classifies_structural_change():
    report = source_diff_report.build_source_diff_report(
        FIXTURE_ROOT,
        draft_file="WidgetReview.s",
        official_file="WidgetReview.x",
    )

    assert report["status"] == "ok"
    assert report["summary"] == {
        "compared_pair_count": 1,
        "changed_pair_count": 1,
        "identical_pair_count": 0,
        "layout_only_pair_count": 0,
        "structural_pair_count": 1,
        "error_count": 0,
    }
    pair = report["pairs"][0]
    assert pair["pair_name"] == "WidgetReview"
    assert pair["classification"] == "structural"
    assert pair["status"] == "ok"
    assert pair["parse_checks"] == {"draft_parse_ok": True, "official_parse_ok": True}
    assert pair["validation_checks"] == {"draft_validation_ok": True, "official_validation_ok": True}
    assert pair["summary"]["changed_line_count"] > 0
    sections = _sections_by_kind(pair)
    assert sections["ast-overview"]["changed"] is True
    assert "Changed BasePicture module code" in sections["ast-overview"]["items"]
    assert sections["basepicture"]["changed"] is True
    basepicture_entry = sections["basepicture"]["entries"][0]
    assert basepicture_entry["module_kind"] == "basepicture"
    assert basepicture_entry["details"] == [
        "Changed variable Flag (init 1 -> 0)",
        "Changed equation Main (code changed)",
    ]
    assert sections["changed-datatypes"] == {
        "kind": "changed-datatypes",
        "title": "Changed Datatypes",
        "changed": False,
        "items": ["No datatype changes."],
        "entries": [],
    }
    assert sections["changed-moduletypes"] == {
        "kind": "changed-moduletypes",
        "title": "Changed Moduletypes",
        "changed": False,
        "items": ["No moduletype changes."],
        "entries": [],
    }
    assert sections["changed-singlemodules"] == {
        "kind": "changed-singlemodules",
        "title": "Changed Singlemodules",
        "changed": False,
        "items": ["No singlemodule changes."],
        "entries": [],
    }


def test_build_source_diff_report_discovery_classifies_layout_only_and_structural_pairs():
    report = source_diff_report.build_source_diff_report(
        FIXTURE_ROOT,
        discover_pairs=True,
    )

    assert report["status"] == "ok"
    assert report["summary"] == {
        "compared_pair_count": 2,
        "changed_pair_count": 2,
        "identical_pair_count": 0,
        "layout_only_pair_count": 1,
        "structural_pair_count": 1,
        "error_count": 0,
    }
    by_name = {pair["pair_name"]: pair for pair in report["pairs"]}
    assert by_name["LayoutReview"]["classification"] == "layout-only"
    assert by_name["WidgetReview"]["classification"] == "structural"
    assert _sections_by_kind(by_name["LayoutReview"])["ast-overview"]["changed"] is False
    assert _sections_by_kind(by_name["LayoutReview"])["basepicture"]["changed"] is False
    assert _sections_by_kind(by_name["WidgetReview"])["ast-overview"]["changed"] is True


def test_build_source_diff_report_builds_ast_sections_for_datatypes_and_modules(tmp_path: Path) -> None:
    draft_file = tmp_path / "ShapeReview.s"
    official_file = tmp_path / "ShapeReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "TYPEDEFINITIONS\n"
        "    SampleRecord = RECORD DateCode_ 2\n"
        "        Field: integer;\n"
        "        Backup: integer;\n"
        "    ENDDEF (*SampleRecord*);\n"
        "TYPEDEFINITIONS\n"
        "    SampleType = MODULEDEFINITION DateCode_ 3\n"
        "    MODULEPARAMETERS\n"
        "        Input: integer;\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 0;\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*SampleType*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "TYPEDEFINITIONS\n"
        "    SampleRecord = RECORD DateCode_ 2\n"
        "        Field: real;\n"
        "        Backup: integer;\n"
        "    ENDDEF (*SampleRecord*);\n"
        "TYPEDEFINITIONS\n"
        "    SampleType = MODULEDEFINITION DateCode_ 3\n"
        "    MODULEPARAMETERS\n"
        "        Input: real;\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 1;\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*SampleType*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="ShapeReview.s",
        official_file="ShapeReview.x",
    )

    assert report["status"] == "ok"
    pair = report["pairs"][0]
    sections = _sections_by_kind(pair)
    assert sections["changed-datatypes"]["changed"] is True
    assert sections["changed-datatypes"]["items"] == ["Changed datatype SampleRecord"]
    assert sections["changed-datatypes"]["entries"] == [
        {
            "name": "SampleRecord",
            "change_kind": "changed",
            "details": ["Changed field Field (datatype real -> integer)"],
        }
    ]
    assert sections["changed-moduletypes"]["changed"] is True
    assert sections["changed-moduletypes"]["items"] == ["Changed moduletype SampleType"]
    assert sections["changed-moduletypes"]["entries"] == [
        {
            "name": "SampleType",
            "module_kind": "moduletype",
            "change_kind": "changed",
            "details": [
                "Changed parameter Input (datatype real -> integer)",
                "Changed variable Counter (init 1 -> 0)",
            ],
            "code_diffs": [],
        }
    ]
    assert sections["changed-singlemodules"]["changed"] is False


def test_build_source_diff_report_uses_draft_as_current_for_added_and_removed_fields(tmp_path: Path) -> None:
    draft_file = tmp_path / "FieldDirectionReview.s"
    official_file = tmp_path / "FieldDirectionReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 11\n"
        "TYPEDEFINITIONS\n"
        "    SampleRecord = RECORD DateCode_ 22\n"
        "        KeepField: integer;\n"
        "        AddedField: boolean;\n"
        "    ENDDEF (*SampleRecord*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 11\n"
        "TYPEDEFINITIONS\n"
        "    SampleRecord = RECORD DateCode_ 22\n"
        "        KeepField: integer;\n"
        "        RemovedField: boolean;\n"
        "    ENDDEF (*SampleRecord*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="FieldDirectionReview.s",
        official_file="FieldDirectionReview.x",
    )

    entries = _sections_by_kind(report["pairs"][0])["changed-datatypes"]["entries"]
    assert entries == [
        {
            "name": "SampleRecord",
            "change_kind": "changed",
            "details": [
                "Added field AddedField [boolean]",
                "Removed field RemovedField [boolean]",
            ],
        }
    ]


def test_build_source_diff_report_added_moduletype_reports_added_equations(tmp_path: Path) -> None:
    draft_file = tmp_path / "AddedTypeReview.s"
    official_file = tmp_path / "AddedTypeReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "TYPEDEFINITIONS\n"
        "    NewType = MODULEDEFINITION DateCode_ 2\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 0;\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( 0.0 , 0.0 ) ( 2.0 , 1.4 )\n"
        "    ModuleCode\n"
        "    EQUATIONBLOCK FirstEq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        "        Counter = 1;\n"
        "    EQUATIONBLOCK SecondEq COORD 0.0, 0.2 OBJSIZE 1.0, 1.0 :\n"
        "        Counter = Counter + 1;\n"
        "    ENDDEF (*NewType*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="AddedTypeReview.s",
        official_file="AddedTypeReview.x",
    )

    entries = _sections_by_kind(report["pairs"][0])["changed-moduletypes"]["entries"]
    assert entries == [
        {
            "name": "NewType",
            "module_kind": "moduletype",
            "change_kind": "added",
            "details": [
                "Added variable Counter [integer]",
                "Added moduledef clipping_bounds (<none> -> ((0.0, 0.0), (2.0, 1.4)))",
                "Added moduledef grid (<none> -> 0.2)",
                "Added moduledef zoomable (<none> -> False)",
                "Added equation FirstEq",
                "Added equation SecondEq",
            ],
            "code_diffs": [],
        }
    ]


def test_build_source_diff_report_groups_changed_singlemodules_separately(tmp_path: Path) -> None:
    draft_file = tmp_path / "InlineReview.s"
    official_file = tmp_path / "InlineReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "SUBMODULES\n"
        "    Child Invocation\n"
        "        ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 2\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 0;\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ModuleCode\n"
        "    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        "        Counter = Counter + 1;\n"
        "    ENDDEF (*Child*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "SUBMODULES\n"
        "    Child Invocation\n"
        "        ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 2\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 1;\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ModuleCode\n"
        "    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        "        Counter = Counter + 2;\n"
        "    ENDDEF (*Child*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="InlineReview.s",
        official_file="InlineReview.x",
    )

    sections = _sections_by_kind(report["pairs"][0])
    assert sections["changed-moduletypes"]["changed"] is False
    assert sections["changed-singlemodules"]["changed"] is True
    assert sections["changed-singlemodules"]["items"] == ["Changed singlemodule Child"]
    assert sections["changed-singlemodules"]["entries"] == [
        {
            "name": "Child",
            "module_kind": "singlemodule",
            "change_kind": "changed",
            "details": [
                "Changed variable Counter (init 1 -> 0)",
                "Changed equation Main (code changed)",
            ],
            "code_diffs": [
                {
                    "label": "Equation Main",
                    "diff_lines": [
                        "--- previous equation Main",
                        "+++ draft equation Main",
                        "@@ -1 +1 @@",
                        "-Counter = (Counter + 2)",
                        "+Counter = (Counter + 1)",
                    ],
                }
            ],
        }
    ]


def test_build_source_diff_report_collapses_singlemodule_promotions_to_moduletype(tmp_path: Path) -> None:
    draft_file = tmp_path / "PromotionReview.s"
    official_file = tmp_path / "PromotionReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "TYPEDEFINITIONS\n"
        "    ParentType = MODULEDEFINITION DateCode_ 2\n"
        "    MODULEPARAMETERS\n"
        "        Input: integer;\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 1;\n"
        "    SUBMODULES\n"
        "        Child Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 3\n"
        "        ModuleDef\n"
        "        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "        ENDDEF (*Child*);\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*ParentType*);\n"
        "SUBMODULES\n"
        "    Parent Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : ParentType;\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "SUBMODULES\n"
        "    Parent Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 2\n"
        "    MODULEPARAMETERS\n"
        "        Input: integer;\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 1;\n"
        "    SUBMODULES\n"
        "        Child Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 3\n"
        "        ModuleDef\n"
        "        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "        ENDDEF (*Child*);\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*Parent*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="PromotionReview.s",
        official_file="PromotionReview.x",
    )

    sections = _sections_by_kind(report["pairs"][0])
    assert sections["changed-moduletypes"]["items"] == ["Added moduletype ParentType"]
    assert sections["changed-moduletypes"]["entries"] == [
        {
            "name": "ParentType",
            "module_kind": "moduletype",
            "change_kind": "added",
            "details": ["Extracted from inline singlemodule Parent"],
            "code_diffs": [],
        }
    ]
    assert sections["changed-singlemodules"]["items"] == ["Changed singlemodule Parent"]
    assert sections["changed-singlemodules"]["entries"] == [
        {
            "name": "Parent",
            "module_kind": "singlemodule",
            "change_kind": "changed",
            "details": ["Promoted to moduletype ParentType"],
            "code_diffs": [],
        }
    ]


def test_build_source_diff_report_collapses_extracted_singlemodule_subtree_to_added_moduletype(tmp_path: Path) -> None:
    draft_file = tmp_path / "ExtractionReview.s"
    official_file = tmp_path / "ExtractionReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "TYPEDEFINITIONS\n"
        "    ParentType = MODULEDEFINITION DateCode_ 2\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 1;\n"
        "    SUBMODULES\n"
        "        Child Invocation\n"
        "            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 3\n"
        "        ModuleDef\n"
        "        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "        ENDDEF (*Child*);\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*ParentType*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "SUBMODULES\n"
        "    Parent Invocation\n"
        "        ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 2\n"
        "    LOCALVARIABLES\n"
        "        Counter: integer := 1;\n"
        "    SUBMODULES\n"
        "        Child Invocation\n"
        "            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 3\n"
        "        ModuleDef\n"
        "        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "        ENDDEF (*Child*);\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*Parent*);\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="ExtractionReview.s",
        official_file="ExtractionReview.x",
    )

    sections = _sections_by_kind(report["pairs"][0])
    assert sections["changed-moduletypes"]["entries"] == [
        {
            "name": "ParentType",
            "module_kind": "moduletype",
            "change_kind": "added",
            "details": ["Extracted from inline singlemodule Parent"],
            "code_diffs": [],
        }
    ]
    assert sections["changed-singlemodules"]["items"] == ["Changed singlemodule Parent"]
    assert sections["changed-singlemodules"]["entries"] == [
        {
            "name": "Parent",
            "module_kind": "singlemodule",
            "change_kind": "changed",
            "details": ["Promoted to moduletype ParentType"],
            "code_diffs": [],
        }
    ]


def test_build_source_diff_report_keeps_sections_when_validation_fails(tmp_path: Path) -> None:
    draft_file = tmp_path / "ExternalLikeReview.s"
    official_file = tmp_path / "ExternalLikeReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "LOCALVARIABLES\n"
        "    MissingDep: UnknownType;\n"
        "    Flag: integer := 0;\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ModuleCode\n"
        "   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        "      Flag = Flag + 1;\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "LOCALVARIABLES\n"
        "    MissingDep: UnknownType;\n"
        "    Flag: integer := 1;\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ModuleCode\n"
        "   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        "      Flag = Flag + 2;\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="ExternalLikeReview.s",
        official_file="ExternalLikeReview.x",
    )

    assert report["status"] == "partial"
    assert report["summary"] == {
        "compared_pair_count": 1,
        "changed_pair_count": 1,
        "identical_pair_count": 0,
        "layout_only_pair_count": 0,
        "structural_pair_count": 1,
        "error_count": 1,
    }
    pair = report["pairs"][0]
    assert pair["status"] == "partial"
    assert pair["classification"] == "structural"
    assert pair["parse_checks"] == {"draft_parse_ok": True, "official_parse_ok": True}
    assert pair["validation_checks"] == {"draft_validation_ok": False, "official_validation_ok": False}
    sections = _sections_by_kind(pair)
    assert sections["basepicture"]["changed"] is True
    assert sections["basepicture"]["entries"][0]["details"] == [
        "Changed variable Flag (init 1 -> 0)",
        "Changed equation Main (code changed)",
    ]
    assert pair["errors"] == [
        {
            "side": "draft",
            "phase": "validation",
            "error": "BasePicture variable 'MissingDep' uses unknown datatype 'UnknownType'",
            "error_type": "StructuralValidationError",
        },
        {
            "side": "official",
            "phase": "validation",
            "error": "BasePicture variable 'MissingDep' uses unknown datatype 'UnknownType'",
            "error_type": "StructuralValidationError",
        },
    ]


def test_build_source_diff_report_reports_missing_explicit_pair():
    report = source_diff_report.build_source_diff_report(
        FIXTURE_ROOT,
        draft_file="WidgetReview.s",
        official_file="MissingReview.x",
    )

    assert report["status"] == "error"
    assert report["pairs"] == []
    assert report["selection_errors"] == [
        {
            "draft_file": "WidgetReview.s",
            "official_file": "MissingReview.x",
            "message": "Draft or official source file does not exist.",
        }
    ]


def test_build_source_diff_report_classifies_parse_failure_as_error(tmp_path: Path) -> None:
    draft_file = tmp_path / "BrokenReview.s"
    official_file = tmp_path / "BrokenReview.x"
    draft_file.write_text(
        '"Syntax version 2.23, date: 2026-05-28-10:00:00.000 N"\n'
        '"Original file date: ---"\n'
        '"Program date: 2026-05-28-10:00:00.000, name: BrokenReview"\n'
        "\n"
        "BasePicture Invocation\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text((FIXTURE_ROOT / "WidgetReview.x").read_text(encoding="utf-8"), encoding="utf-8")

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="BrokenReview.s",
        official_file="BrokenReview.x",
    )

    assert report["status"] == "partial"
    assert report["summary"]["error_count"] == 1
    pair = report["pairs"][0]
    assert pair["classification"] == "error"
    assert pair["status"] == "error"
    assert pair["parse_checks"] == {"draft_parse_ok": False, "official_parse_ok": True}
    assert pair["validation_checks"] == {"draft_validation_ok": False, "official_validation_ok": True}
    assert pair["errors"][0]["side"] == "draft"
    assert pair["errors"][0]["phase"] == "parse"


def test_build_source_diff_report_reads_cp1252_encoded_source_pairs(tmp_path: Path) -> None:
    draft_file = tmp_path / "LegacyReview.s"
    official_file = tmp_path / "LegacyReview.x"
    draft_text = (
        (FIXTURE_ROOT / "WidgetReview.s")
        .read_text(encoding="utf-8")
        .replace(
            '"Original file date: ---"',
            '"Original file date: S\u00f8ren legacy draft"',
        )
    )
    official_text = (
        (FIXTURE_ROOT / "WidgetReview.x")
        .read_text(encoding="utf-8")
        .replace(
            '"Original file date: ---"',
            '"Original file date: S\u00f8ren legacy official"',
        )
    )
    draft_file.write_bytes(draft_text.encode("cp1252"))
    official_file.write_bytes(official_text.encode("cp1252"))

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="LegacyReview.s",
        official_file="LegacyReview.x",
    )

    assert report["status"] == "ok"
    assert report["summary"]["compared_pair_count"] == 1
    assert report["summary"]["structural_pair_count"] == 1
    pair = report["pairs"][0]
    assert pair["status"] == "ok"
    assert pair["classification"] == "structural"
    assert pair["parse_checks"] == {"draft_parse_ok": True, "official_parse_ok": True}
    assert pair["validation_checks"] == {"draft_validation_ok": True, "official_validation_ok": True}
    assert pair["errors"] == []


def test_render_markdown_includes_review_sections_and_diff_block() -> None:
    report = source_diff_report.build_source_diff_report(
        FIXTURE_ROOT,
        draft_file="WidgetReview.s",
        official_file="WidgetReview.x",
    )

    markdown = source_diff_report.render_markdown(report)
    assert "# SattLint .s/.x Diff Report" in markdown
    assert "## WidgetReview" in markdown
    assert "Classification: structural" in markdown
    assert "### AST Overview" in markdown
    assert "### BasePicture" in markdown
    assert "#### BasePicture" in markdown
    assert "- Changed variable Flag (init 1 -> 0)" in markdown
    assert "##### Equation Main" in markdown
    assert "```diff" in markdown
    assert "-Flag = (Flag + 2)" in markdown
    assert "+Flag = (Flag + 1)" in markdown


def test_render_markdown_keeps_sections_for_partial_pairs(tmp_path: Path) -> None:
    draft_file = tmp_path / "ExternalLikeReview.s"
    official_file = tmp_path / "ExternalLikeReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "LOCALVARIABLES\n"
        "    MissingDep: UnknownType;\n"
        "    Flag: integer := 0;\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )
    official_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "LOCALVARIABLES\n"
        "    MissingDep: UnknownType;\n"
        "    Flag: integer := 1;\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="ExternalLikeReview.s",
        official_file="ExternalLikeReview.x",
    )

    markdown = source_diff_report.render_markdown(report)
    assert "Status: partial" in markdown
    assert "- draft validation: StructuralValidationError" in markdown
    assert "### BasePicture" in markdown
    assert "No AST comparison sections available." not in markdown


def test_main_writes_json_and_markdown_reports(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    expected_report: dict[str, Any] = {
        "generated_by": "sattlint.devtools.source_diff_report",
        "report_kind": "source-diff-report",
        "status": "ok",
        "workspace_root": ".",
        "summary": {
            "compared_pair_count": 1,
            "changed_pair_count": 1,
            "identical_pair_count": 0,
            "layout_only_pair_count": 0,
            "structural_pair_count": 1,
            "error_count": 0,
        },
        "pairs": [
            {
                "pair_name": "WidgetReview",
                "draft_file": "WidgetReview.s",
                "official_file": "WidgetReview.x",
                "status": "ok",
                "classification": "structural",
                "changed": True,
                "parse_checks": {"draft_parse_ok": True, "official_parse_ok": True},
                "validation_checks": {"draft_validation_ok": True, "official_validation_ok": True},
                "summary": {"addition_count": 1, "deletion_count": 1, "changed_line_count": 2},
                "sections": [
                    {
                        "kind": "ast-overview",
                        "title": "AST Overview",
                        "changed": True,
                        "items": ["Changed BasePicture module code"],
                    },
                    {
                        "kind": "basepicture",
                        "title": "BasePicture",
                        "changed": True,
                        "items": ["Changed BasePicture"],
                        "entries": [
                            {
                                "name": "BasePicture",
                                "module_kind": "basepicture",
                                "change_kind": "changed",
                                "details": ["Changed variable Flag (init 1 -> 0)"],
                                "code_diffs": [],
                            }
                        ],
                    },
                    {
                        "kind": "changed-datatypes",
                        "title": "Changed Datatypes",
                        "changed": False,
                        "items": ["No datatype changes."],
                        "entries": [],
                    },
                    {
                        "kind": "changed-moduletypes",
                        "title": "Changed Moduletypes",
                        "changed": False,
                        "items": ["No moduletype changes."],
                        "entries": [],
                    },
                    {
                        "kind": "changed-singlemodules",
                        "title": "Changed Singlemodules",
                        "changed": False,
                        "items": ["No singlemodule changes."],
                        "entries": [],
                    },
                ],
                "errors": [],
            }
        ],
        "selection_errors": [],
    }

    def _build_source_diff_report(*_args: object, **kwargs: object) -> dict[str, Any]:
        progress_callback = kwargs.get("progress_callback")
        assert progress_callback is not None
        assert callable(progress_callback)
        progress_callback("Source diff: resolving comparison pairs")
        return expected_report

    monkeypatch.setattr(source_diff_report, "build_source_diff_report", _build_source_diff_report)

    output_dir = tmp_path / "artifacts"
    exit_code = source_diff_report.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--discover-pairs",
            "--format",
            "markdown",
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Source diff: resolving comparison pairs" in captured.err
    assert "# SattLint .s/.x Diff Report" in captured.out
    assert (
        json.loads((output_dir / source_diff_report.DEFAULT_JSON_OUTPUT_FILENAME).read_text(encoding="utf-8"))
        == expected_report
    )
    assert "## WidgetReview" in (output_dir / source_diff_report.DEFAULT_MARKDOWN_OUTPUT_FILENAME).read_text(
        encoding="utf-8"
    )


def test_main_returns_failure_when_output_write_fails(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    expected_report: dict[str, Any] = {
        "generated_by": "sattlint.devtools.source_diff_report",
        "report_kind": "source-diff-report",
        "status": "ok",
        "workspace_root": ".",
        "summary": {
            "compared_pair_count": 0,
            "changed_pair_count": 0,
            "identical_pair_count": 0,
            "layout_only_pair_count": 0,
            "structural_pair_count": 0,
            "error_count": 0,
        },
        "pairs": [],
        "selection_errors": [],
    }

    def _build_source_diff_report(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return expected_report

    monkeypatch.setattr(
        source_diff_report,
        "build_source_diff_report",
        _build_source_diff_report,
    )

    def _raise_locked(*_args: object, **_kwargs: object) -> tuple[Path, Path]:
        raise PermissionError("locked")

    monkeypatch.setattr(
        source_diff_report,
        "_write_report_artifacts",
        _raise_locked,
    )

    exit_code = source_diff_report.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--discover-pairs",
            "--no-progress",
            "--output-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == expected_report
    assert "source diff output error: locked" in captured.err
