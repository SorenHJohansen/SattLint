# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false
from ._source_diff_report_test_support import *


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


def test_source_diff_helper_misc_branches(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "CompressedReview.s"
    sample_path.write_text("compressed", encoding="utf-8")

    monkeypatch.setattr(source_diff_report, "read_text_with_fallback", lambda path: f"raw:{path.name}")
    monkeypatch.setattr(source_diff_report, "is_compressed", lambda text: text.startswith("raw:"))
    monkeypatch.setattr(source_diff_report, "preprocess_sl_text", lambda text: (f"expanded:{text}", {"kind": "zip"}))

    assert source_diff_report._pair_name(Path("Draft.s"), Path("Official.x")) == "Draft vs Official"
    assert source_diff_report._read_source_text(sample_path) == "expanded:raw:CompressedReview.s"
    assert source_diff_report._stable_signature_value(
        [1, SimpleNamespace(span=SourceSpan(start=0, end=0, line=3, column=4))]
    ) == (
        1,
        "namespace(span=SourceSpan(start=0, end=0, line=0, column=0))",
    )
    assert source_diff_report._module_header_signature(None) is None
    assert source_diff_report._moduledef_signature(None) is None

    frame_module = FrameModule(
        header=ModuleHeader(name="FrameChild", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
    )
    instance_module = ModuleTypeInstance(
        header=ModuleHeader(name="InstChild", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduletype_name="ChildType",
    )

    assert source_diff_report._submodule_signature(frame_module)[0] == "frame-module"
    assert source_diff_report._submodule_kind(frame_module) == "framemodule"
    assert source_diff_report._format_qualifiers({"qualifiers": ("state", "secure")}) == "state, secure"
    assert (
        source_diff_report._format_submodule_summary(source_diff_report._submodule_detail(instance_module))
        == "InstChild [instance:ChildType]"
    )


def test_source_diff_detail_helpers_cover_unhit_fragments() -> None:
    variable_details = source_diff_report._diff_variable_details(
        "variable",
        [
            {
                "name": "Stateful",
                "datatype": "integer",
                "qualifiers": ("state",),
                "init_value": "0",
                "description": "draft",
                "init_is_duration": True,
            }
        ],
        [
            {
                "name": "Stateful",
                "datatype": "integer",
                "qualifiers": (),
                "init_value": "0",
                "description": "official",
                "init_is_duration": False,
            }
        ],
    )

    assert variable_details == [
        "Changed variable Stateful (qualifiers none -> state; description official -> draft; init_is_duration False -> True)"
    ]

    submodule_details = source_diff_report._diff_submodule_details(
        [
            {
                "name": "AddedChild",
                "kind": "singlemodule",
                "parameter_mappings": (),
                "signature": ("added",),
            },
            {
                "name": "StableChild",
                "kind": "singlemodule",
                "parameter_mappings": (),
                "signature": ("same",),
            },
            {
                "name": "InstanceChild",
                "kind": "moduletype-instance",
                "moduletype_name": "DraftType",
                "parameter_mappings": ("In := Value",),
                "signature": ("changed",),
            },
        ],
        [
            {
                "name": "RemovedChild",
                "kind": "singlemodule",
                "parameter_mappings": (),
                "signature": ("removed",),
            },
            {
                "name": "StableChild",
                "kind": "singlemodule",
                "parameter_mappings": (),
                "signature": ("same",),
            },
            {
                "name": "InstanceChild",
                "kind": "moduletype-instance",
                "moduletype_name": "OfficialType",
                "parameter_mappings": (),
                "signature": ("other",),
            },
        ],
    )

    assert submodule_details == [
        "Added submodule AddedChild [singlemodule]",
        "Removed submodule RemovedChild [singlemodule]",
        "Changed submodule InstanceChild (moduletype OfficialType -> DraftType; parameter mappings changed; definition changed)",
    ]

    entity_details, entity_code_diffs = source_diff_report._diff_modulecode_entities(
        "sequence",
        {
            "added": {"name": "AddedSeq", "code_lines": ("draft",)},
            "same": {
                "name": "SameSeq",
                "type": "sequence",
                "position": (0.0, 0.0),
                "size": (1.0, 1.0),
                "seqcontrol": False,
                "seqtimer": False,
                "code_lines": ("same",),
            },
            "changed": {
                "name": "ChangedSeq",
                "type": "open",
                "position": (1.0, 1.0),
                "size": (2.0, 2.0),
                "seqcontrol": True,
                "seqtimer": False,
                "code_lines": ("same",),
            },
        },
        {
            "removed": {"name": "RemovedSeq", "code_lines": ("official",)},
            "same": {
                "name": "SameSeq",
                "type": "sequence",
                "position": (0.0, 0.0),
                "size": (1.0, 1.0),
                "seqcontrol": False,
                "seqtimer": False,
                "code_lines": ("same",),
            },
            "changed": {
                "name": "ChangedSeq",
                "type": "sequence",
                "position": (0.0, 0.0),
                "size": (1.0, 1.0),
                "seqcontrol": False,
                "seqtimer": False,
                "code_lines": ("same",),
            },
        },
    )

    assert entity_details == [
        "Added sequence AddedSeq",
        "Removed sequence RemovedSeq",
        "Changed sequence ChangedSeq (type sequence -> open; position (0.0, 0.0) -> (1.0, 1.0); size (1.0, 1.0) -> (2.0, 2.0); seqcontrol False -> True)",
    ]
    assert entity_code_diffs == []


def test_source_diff_promotion_and_module_entry_edge_cases() -> None:
    official_inline = {
        ("frame",): {
            "name": "Frame",
            "module_kind": "framemodule",
            "parameters": [],
            "variables": [],
            "submodules": [],
            "moduledef": source_diff_report._moduledef_detail(None),
            "modulecode": source_diff_report._modulecode_detail(None),
        },
        ("parent",): {
            "name": "Parent",
            "module_kind": "singlemodule",
            "parameters": [],
            "variables": [],
            "submodules": [],
            "moduledef": source_diff_report._moduledef_detail(None),
            "modulecode": source_diff_report._modulecode_detail(None),
        },
    }
    draft_bp = _basepicture(
        moduletype_defs=[ModuleTypeDef(name="ParentType")],
        submodules=[
            ModuleTypeInstance(
                header=ModuleHeader(name="Parent", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduletype_name="ParentType",
                parametermappings=["Input := Flag"],
            )
        ],
    )
    official_bp = _basepicture()

    entries, promoted_roots, promoted_sources = source_diff_report._collect_promoted_singlemodule_entries(
        draft_bp=draft_bp,
        official_bp=official_bp,
        official_inline=official_inline,
    )

    assert entries == [
        {
            "name": "Parent",
            "module_kind": "singlemodule",
            "change_kind": "changed",
            "details": [
                "Promoted to moduletype ParentType",
                "Parameter mappings updated on promoted moduletype instance",
            ],
            "code_diffs": [],
        }
    ]
    assert promoted_roots == {("parent",)}
    assert promoted_sources == {"parenttype": "Parent"}

    removed_entry = source_diff_report._build_module_entry(
        "RemovedChild",
        change_kind="removed",
        draft=None,
        official=_empty_module_detail(),
    )
    assert removed_entry["details"] == []

    with pytest.raises(ValueError, match="module entry diff requires both draft and official details"):
        source_diff_report._build_module_entry(
            "Broken",
            change_kind="changed",
            draft=None,
            official=None,
        )


def test_source_diff_named_sections_and_datatype_branches() -> None:
    section = source_diff_report._build_named_entries_section(
        kind="named",
        title="Named",
        label="module",
        draft_map={
            "added": ("Added", _empty_module_detail()),
            "same": ("Same", _empty_module_detail()),
        },
        official_map={
            "removed": ("Removed", _empty_module_detail()),
            "same": ("Same", _empty_module_detail()),
        },
        empty_message="No changes.",
    )

    assert section["items"] == ["Added module Added", "Removed module Removed"]

    draft_bp = _basepicture(
        datatype_defs=[
            DataType(
                name="AddedRecord", description=None, datecode=10, var_list=[Variable(name="A", datatype="integer")]
            ),
            DataType(name="ChangedRecord", description="draft", datecode=2, var_list=[]),
            DataType(name="SameRecord", description="same", datecode=5, var_list=[]),
        ]
    )
    official_bp = _basepicture(
        datatype_defs=[
            DataType(
                name="RemovedRecord", description=None, datecode=11, var_list=[Variable(name="B", datatype="real")]
            ),
            DataType(name="ChangedRecord", description="official", datecode=1, var_list=[]),
            DataType(name="SameRecord", description="same", datecode=5, var_list=[]),
        ]
    )

    datatype_section = source_diff_report._build_datatype_section(draft_bp, official_bp)

    assert datatype_section["items"] == [
        "Added datatype AddedRecord",
        "Removed datatype RemovedRecord",
        "Changed datatype ChangedRecord",
    ]
    assert datatype_section["entries"] == [
        {
            "name": "AddedRecord",
            "change_kind": "added",
            "details": ["Added field A [integer]"],
        },
        {
            "name": "RemovedRecord",
            "change_kind": "removed",
            "details": ["Removed field B [real]"],
        },
        {
            "name": "ChangedRecord",
            "change_kind": "changed",
            "details": ["Changed description official -> draft", "Changed datecode 1 -> 2"],
        },
    ]


def test_source_diff_moduletype_singlemodule_and_ast_sections_misc_branches() -> None:
    draft_bp = _basepicture(
        moduletype_defs=[ModuleTypeDef(name="SameType"), ModuleTypeDef(name="AddedType")],
        moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (2.0, 2.0))),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="Inline", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(),
            )
        ],
    )
    official_bp = _basepicture(
        moduletype_defs=[ModuleTypeDef(name="SameType"), ModuleTypeDef(name="RemovedType")],
        moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
        submodules=[],
    )

    moduletype_section = source_diff_report._build_moduletype_section(draft_bp, official_bp)
    assert moduletype_section["items"] == ["Added moduletype AddedType", "Removed moduletype RemovedType"]

    singlemodule_section = source_diff_report._build_singlemodule_section(draft_bp, official_bp)
    assert singlemodule_section["items"] == ["Added singlemodule Inline"]

    ast_sections = source_diff_report._build_ast_comparison_sections(draft_bp, official_bp)
    assert "Changed BasePicture module definition" in ast_sections[0]["items"]
    assert "Changed BasePicture submodule tree" in ast_sections[0]["items"]


def test_source_diff_discovery_and_parse_selection_edge_cases(tmp_path: Path) -> None:
    assert source_diff_report._parse_side_for_report(None, source_path=tmp_path / "none.s", side="draft") == (
        None,
        False,
        False,
        [],
    )

    pair_dir = tmp_path / "pair"
    pair_dir.mkdir()
    (pair_dir / "alpha.s").write_text("draft", encoding="utf-8")
    (pair_dir / "alpha.x").write_text("official", encoding="utf-8")
    (pair_dir / "lonely.s").write_text("draft", encoding="utf-8")
    (pair_dir / "notes.txt").write_text("ignore", encoding="utf-8")
    (pair_dir / "nested").mkdir()

    discovered = source_diff_report._discover_pairs(tmp_path)
    assert discovered == [((pair_dir / "alpha.s").resolve(), (pair_dir / "alpha.x").resolve())]

    explicit_pairs, explicit_errors = source_diff_report._resolve_explicit_pair(
        workspace_root=tmp_path,
        draft_file="only-draft.s",
        official_file=None,
    )
    assert explicit_pairs == []
    assert explicit_errors == [
        {
            "draft_file": "only-draft.s",
            "official_file": "",
            "message": "Explicit pair mode requires both --draft-file and --official-file.",
        }
    ]


def test_source_diff_build_pair_report_read_errors_and_identical_classification(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    draft_file = tmp_path / "SameReview.s"
    official_file = tmp_path / "SameReview.x"
    draft_file.write_text("draft", encoding="utf-8")
    official_file.write_text("official", encoding="utf-8")

    def _read_with_failures(path: Path) -> str:
        if path.suffix == ".s":
            raise OSError("draft missing")
        raise UnicodeError("official decode")

    monkeypatch.setattr(source_diff_report, "_read_source_text", _read_with_failures)

    error_report = source_diff_report.build_pair_report(draft_file, official_file, workspace_root=tmp_path)
    assert error_report["status"] == "error"
    assert error_report["errors"] == [
        {"side": "draft", "error": "draft missing", "error_type": "OSError"},
        {"side": "official", "error": "official decode", "error_type": "UnicodeError"},
    ]

    monkeypatch.setattr(source_diff_report, "_read_source_text", lambda _path: "same text")
    monkeypatch.setattr(
        source_diff_report,
        "_parse_side_for_report",
        lambda source_text, *, source_path, side: (_basepicture(), True, True, []),
    )
    monkeypatch.setattr(source_diff_report, "build_unified_diff_lines", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        source_diff_report,
        "summarize_unified_diff_lines",
        lambda diff_lines: {"addition_count": 0, "deletion_count": 0, "changed_line_count": 0},
    )
    monkeypatch.setattr(source_diff_report, "_build_ast_comparison_sections", lambda draft_bp, official_bp: [])

    identical_report = source_diff_report.build_pair_report(draft_file, official_file, workspace_root=tmp_path)
    assert identical_report["classification"] == "identical"
    assert identical_report["status"] == "ok"


def test_source_diff_report_build_and_render_edge_cases(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    progress_messages: list[str] = []
    draft_file = (tmp_path / "Alpha.s").resolve()
    official_file = (tmp_path / "Alpha.x").resolve()
    draft_file.write_text("draft", encoding="utf-8")
    official_file.write_text("official", encoding="utf-8")

    monkeypatch.setattr(
        source_diff_report,
        "_resolve_explicit_pair",
        lambda **kwargs: ([(draft_file, official_file)], []),
    )
    monkeypatch.setattr(
        source_diff_report,
        "build_pair_report",
        lambda resolved_draft, resolved_official, *, workspace_root: {
            "pair_name": "Alpha",
            "draft_file": "Alpha.s",
            "official_file": "Alpha.x",
            "status": "ok",
            "classification": "structural",
            "changed": True,
            "parse_checks": {"draft_parse_ok": True, "official_parse_ok": True},
            "validation_checks": {"draft_validation_ok": True, "official_validation_ok": True},
            "summary": {"addition_count": 0, "deletion_count": 0, "changed_line_count": 1},
            "sections": [],
            "errors": [],
        },
    )

    report = source_diff_report.build_source_diff_report(
        tmp_path,
        progress_callback=progress_messages.append,
    )

    assert progress_messages == [
        "Source diff: resolving comparison pairs",
        "Source diff: comparing 1/1 Alpha.s",
    ]
    assert report["summary"]["changed_pair_count"] == 1

    monkeypatch.setattr(source_diff_report, "_resolve_explicit_pair", lambda **kwargs: ([], []))
    monkeypatch.setattr(source_diff_report, "_discover_pairs", lambda workspace_root: [])

    discovered_report = source_diff_report.build_source_diff_report(tmp_path, discover_pairs=True)
    assert discovered_report["selection_errors"] == [
        {
            "draft_file": "",
            "official_file": "",
            "message": "No same-basename .s/.x pairs were found. Use --draft-file and --official-file to compare one explicit pair.",
        }
    ]

    prompt_report = source_diff_report.build_source_diff_report(tmp_path)
    assert prompt_report["selection_errors"] == [
        {
            "draft_file": "",
            "official_file": "",
            "message": "Select one explicit pair with --draft-file and --official-file, or use --discover-pairs.",
        }
    ]

    markdown = source_diff_report.render_markdown(
        {
            "status": "error",
            "summary": {
                "compared_pair_count": 0,
                "changed_pair_count": 0,
                "identical_pair_count": 0,
                "layout_only_pair_count": 0,
                "structural_pair_count": 0,
                "error_count": 1,
            },
            "selection_errors": [{"message": "pick one pair"}],
            "pairs": [
                {
                    "pair_name": "Alpha",
                    "draft_file": "Alpha.s",
                    "official_file": "Alpha.x",
                    "status": "error",
                    "classification": "error",
                    "summary": {"changed_line_count": 0},
                    "errors": [],
                    "sections": [],
                }
            ],
        }
    )
    assert "## Selection Errors" in markdown
    assert "- pick one pair" in markdown
    assert "No AST comparison sections available." in markdown


def test_source_diff_main_returns_exit_2_via_module_entrypoint(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["sattlint-source-diff-report"],
    )

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(Path(source_diff_report.__file__)), run_name="__main__")

    captured = capsys.readouterr()
    assert excinfo.value.code == 2
    assert '"status": "error"' in captured.out
