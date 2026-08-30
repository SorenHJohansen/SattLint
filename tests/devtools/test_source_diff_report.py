# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false
from ._source_diff_report_test_support import *


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


def test_build_source_diff_report_surfaces_nested_moduletype_code_diffs(tmp_path: Path) -> None:
    draft_file = tmp_path / "NestedTypeReview.s"
    official_file = tmp_path / "NestedTypeReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "TYPEDEFINITIONS\n"
        "    ParentType = MODULEDEFINITION DateCode_ 2\n"
        "    SUBMODULES\n"
        "        L1 Invocation\n"
        "            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 3\n"
        "        LOCALVARIABLES\n"
        "            Counter: integer := 0;\n"
        "        ModuleDef\n"
        "        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "        ModuleCode\n"
        "        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        "            Counter = Counter + 1;\n"
        "        ENDDEF (*L1*);\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*ParentType*);\n"
        "SUBMODULES\n"
        "    Root Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : ParentType;\n"
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
        "    ParentType = MODULEDEFINITION DateCode_ 2\n"
        "    SUBMODULES\n"
        "        L1 Invocation\n"
        "            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 3\n"
        "        LOCALVARIABLES\n"
        "            Counter: integer := 0;\n"
        "        ModuleDef\n"
        "        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "        ModuleCode\n"
        "        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n"
        "            Counter = Counter + 2;\n"
        "        ENDDEF (*L1*);\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*ParentType*);\n"
        "SUBMODULES\n"
        "    Root Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : ParentType;\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="NestedTypeReview.s",
        official_file="NestedTypeReview.x",
    )

    sections = _sections_by_kind(report["pairs"][0])
    assert sections["changed-moduletypes"]["changed"] is True
    assert sections["changed-moduletypes"]["items"] == ["Changed moduletype ParentType"]
    assert sections["changed-moduletypes"]["entries"] == [
        {
            "name": "ParentType",
            "module_kind": "moduletype",
            "change_kind": "changed",
            "details": ["Changed submodule L1 (definition changed)"],
            "code_diffs": [
                {
                    "label": "L1 / Equation Main",
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


def test_build_source_diff_report_surfaces_nested_moduletype_sequence_transition_diffs(tmp_path: Path) -> None:
    draft_file = tmp_path / "NestedTypeSequenceReview.s"
    official_file = tmp_path / "NestedTypeSequenceReview.x"
    draft_file.write_text(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "TYPEDEFINITIONS\n"
        "    ParentType = MODULEDEFINITION DateCode_ 2\n"
        "    SUBMODULES\n"
        "        L1 Invocation\n"
        "            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 3\n"
        "        LOCALVARIABLES\n"
        "            Ready: boolean := False;\n"
        "        ModuleDef\n"
        "        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "        ModuleCode\n"
        "            SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0\n"
        "                SEQINITSTEP Start\n"
        "                SEQTRANSITION Tr1 WAIT_FOR Ready\n"
        "                SEQSTEP Running\n"
        "            ENDSEQUENCE\n"
        "        ENDDEF (*L1*);\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*ParentType*);\n"
        "SUBMODULES\n"
        "    Root Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : ParentType;\n"
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
        "    ParentType = MODULEDEFINITION DateCode_ 2\n"
        "    SUBMODULES\n"
        "        L1 Invocation\n"
        "            ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : MODULEDEFINITION DateCode_ 3\n"
        "        LOCALVARIABLES\n"
        "            Ready: boolean := False;\n"
        "        ModuleDef\n"
        "        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "        ModuleCode\n"
        "            SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0\n"
        "                SEQINITSTEP Start\n"
        "                SEQTRANSITION Tr1 WAIT_FOR False\n"
        "                SEQSTEP Running\n"
        "            ENDSEQUENCE\n"
        "        ENDDEF (*L1*);\n"
        "    ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    ENDDEF (*ParentType*);\n"
        "SUBMODULES\n"
        "    Root Invocation ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0 ) : ParentType;\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        draft_file="NestedTypeSequenceReview.s",
        official_file="NestedTypeSequenceReview.x",
    )

    sections = _sections_by_kind(report["pairs"][0])
    assert sections["changed-moduletypes"]["entries"] == [
        {
            "name": "ParentType",
            "module_kind": "moduletype",
            "change_kind": "changed",
            "details": ["Changed submodule L1 (definition changed)"],
            "code_diffs": [
                {
                    "label": "L1 / Sequence MainSeq",
                    "diff_lines": [
                        "--- previous sequence MainSeq",
                        "+++ draft sequence MainSeq",
                        "@@ -1,3 +1,3 @@",
                        " InitStep Start",
                        "-Transition Tr1 WAIT_FOR False",
                        "+Transition Tr1 WAIT_FOR Ready",
                        " Step Running",
                    ],
                }
            ],
        }
    ]


def test_moduletype_detail_ignores_nested_source_span_only_header_changes() -> None:
    def build_moduletype(line: int) -> ModuleTypeDef:
        return ModuleTypeDef(
            name="ParentType",
            submodules=[
                SingleModule(
                    header=ModuleHeader(
                        name="L1",
                        invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0),
                        enable_tail={"expr": "Ready", "span": SourceSpan(start=0, end=0, line=line, column=2)},
                    ),
                    moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
                )
            ],
            moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
        )

    assert source_diff_report._moduletype_detail(build_moduletype(10)) == source_diff_report._moduletype_detail(
        build_moduletype(20)
    )


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
