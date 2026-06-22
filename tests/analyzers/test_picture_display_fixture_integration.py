from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    GraphicsBinding,
    ModuleDef,
    ModuleHeader,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint.analyzers.picture_display_paths import analyze_picture_display_paths
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.engine import (
    CodeMode,
    SattLineProjectLoader,
    SattLineProjectLoaderConfig,
    merge_project_basepicture,
)
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.picture_display_paths import PictureDisplayOccurrence

SAMPLE_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_sattline_files"
CORPUS_ANALYZER_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "corpus" / "semantic" / "analyzer"


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _varref(name: str) -> dict[str, str]:
    return {"var_name": name}


def _resolve_fixture_path(stem: str) -> Path:
    for fixture_dir in (SAMPLE_FIXTURE_DIR, CORPUS_ANALYZER_FIXTURE_DIR):
        fixture = fixture_dir / f"{stem}.s"
        if fixture.exists():
            return fixture
    raise FileNotFoundError(stem)


def _load_fixture_base_picture(stem: str) -> BasePicture:
    fixture = _resolve_fixture_path(stem)
    loader = SattLineProjectLoader(
        SattLineProjectLoaderConfig(
            program_dir=fixture.parent,
            other_lib_dirs=[],
            abb_lib_dir=fixture.parent,
            mode=CodeMode.DRAFT,
            scan_root_only=True,
            debug=False,
            use_file_ast_cache=False,
        )
    )
    graph = loader.resolve(fixture.stem, strict=False)
    return merge_project_basepicture(graph.ast_by_name[fixture.stem], graph)


def test_picture_display_path_analyzer_uses_real_string_fixture() -> None:
    base_picture = _load_fixture_base_picture("TestStringsInPictureDisplay")

    report = analyze_picture_display_paths(base_picture)

    assert len(base_picture.graphics_picture_display_records) == 1
    assert len(base_picture.graphics_picture_display_occurrences) == 1
    assert [
        (row.index_token, row.kind, row.raw_text) for row in base_picture.graphics_picture_display_records[0].path_rows
    ] == [("1", "variable_invalid", "PathOK"), ("2", "variable_invalid", "PathNotOK")]
    assert len(report.issues) == 1
    assert "PathNotOK" in report.issues[0].message
    assert "+T+ToggleParWindow" in report.issues[0].message
    assert "PathOK" not in report.issues[0].message


def test_variable_invalid_picture_display_rows_do_not_count_as_usage() -> None:
    path_var = Variable(name="PathAIT", datatype=Simple_DataType.LINESTRING)
    base_picture = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("DisplayModule"),
                moduledef=ModuleDef(),
                moduleparameters=[],
                localvariables=[path_var],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )
    base_picture.graphics_bindings = [
        GraphicsBinding(
            kind="var",
            raw_text="PathAIT",
            value=_varref("PathAIT"),
            span=SourceSpan(line=2, column=5),
        )
    ]
    base_picture.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "DisplayModule"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_row_lines=(2,),
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token=str(1),
                        index_value=1,
                        kind="variable_invalid",
                        raw_text="PathAIT",
                        span=SourceSpan(line=2, column=5),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(base_picture)
    analyzer.run()

    assert any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is path_var
        and issue.module_path == ["BasePicture", "DisplayModule"]
        for issue in analyzer.issues
    )
