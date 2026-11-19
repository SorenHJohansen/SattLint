# pyright: reportPrivateUsage=false
"""End-to-end Change Review tests: artifacts, output location, serialization."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    CodeComment,
    CodeItem,
    Equation,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ScalarDatatype,
    Sequence,
    SFCBodyItem,
    SFCCodeBlocks,
    SFCStep,
    SFCTransition,
    Variable,
)
from sattline_parser.models.expressions import Assignment, VarRef

from sattlint.change_review import (
    ChangeKind,
    ChangeReviewResult,
    build_change_review,
    compute_relevance,
    compute_semantic_diff,
    generate_change_review,
    load_version_snapshot,
)
from sattlint.change_review._code_model import _iter_code_statements, build_code_model
from sattlint.change_review.artifacts import write_review_artifacts
from sattlint.change_review.review import ChangeReview, ReviewMetadata, ReviewSizeStats, _expand_block_start
from sattlint.change_review.serialization.json_serializer import review_to_json
from sattlint.change_review.source import SourceTextProvider
from sattlint.core.semantic import build_snapshot_from_loaded_project
from sattlint.models.project_graph import ProjectGraph
from tests.helpers.change_review_support import (
    CONNECTION_PROGRAM,
    CONNECTION_PROGRAM_ALT_SOURCE,
    DRAFT_PROGRAM,
    FUNCTION_BLOCK_DRAFT,
    FUNCTION_BLOCK_OFFICIAL,
    OFFICIAL_PROGRAM,
    build_cfg,
    load_pair,
    write_project,
)

pytestmark = pytest.mark.unit


def test_generate_change_review_writes_json_and_markdown(tmp_path: Path):
    cfg = build_cfg(tmp_path)
    output_dir = tmp_path / "change-review"

    result: ChangeReviewResult = generate_change_review(cfg, "Demo", output_dir=output_dir)

    assert result.json_path.exists()
    assert result.markdown_path.exists()
    assert result.json_path.suffix == ".json"
    assert result.markdown_path.suffix == ".md"

    review = result.review
    assert review.metadata.project == "Demo"
    assert review.size_stats.semantic_change_count >= 1
    assert review.size_stats.total_project_source_size > 0
    assert review.size_stats.selected_source_size > 0
    assert review.size_stats.artifact_size > review.size_stats.selected_source_size
    assert review.size_stats.source_reduction_percent < 100.0


def test_configured_output_location_is_respected(tmp_path: Path):
    output_dir = tmp_path / "custom" / "nested"
    cfg = build_cfg(tmp_path, review_output_dir=str(output_dir))

    result = generate_change_review(cfg, "Demo", output_dir=output_dir)

    assert result.json_path.parent == output_dir
    assert result.markdown_path.parent == output_dir
    assert output_dir.is_dir()


def test_json_and_markdown_correspond_to_same_review(tmp_path: Path):
    cfg = build_cfg(tmp_path)
    result = generate_change_review(cfg, "Demo", output_dir=tmp_path / "out")

    parsed = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert parsed["metadata"]["project"] == "Demo"
    assert parsed["size_stats"]["semantic_change_count"] == result.review.size_stats.semantic_change_count
    assert len(parsed["changes"]) == len(result.review.changes)
    assert len(parsed["context"]) == len(result.review.context)
    assert len(parsed["variable_definitions"]) == len(result.review.variable_definitions)

    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "# SattLint Change Review" in markdown
    assert str(result.review.size_stats.semantic_change_count) in markdown


def test_markdown_shows_block_source(tmp_path: Path):
    cfg = build_cfg(tmp_path)
    result = generate_change_review(cfg, "Demo", output_dir=tmp_path / "out")
    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "*Context: equation Main*" in markdown
    assert "## Relevant Blocks / Sequences" in markdown
    assert "ValveOpen = Flow > 5" in markdown
    assert "#### Official" in markdown and "#### Draft" in markdown


def test_markdown_contains_semantic_context_and_scope(tmp_path: Path):
    cfg = build_cfg(tmp_path)
    result = generate_change_review(cfg, "Demo", output_dir=tmp_path / "out")
    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "#### Direct semantic context" in markdown
    assert "## Review Scope" in markdown
    assert "**Direct reads:**" in markdown
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert all("semantic_context" in change for change in payload["changes"])


def test_review_json_schema_separates_changes_blocks_and_definitions(tmp_path: Path):
    cfg = build_cfg(tmp_path)
    result = generate_change_review(cfg, "Demo", output_dir=tmp_path / "out")
    payload = json.loads(review_to_json(result.review))
    assert set(payload) == {"metadata", "size_stats", "changes", "context", "variable_definitions"}
    for change in payload["changes"]:
        assert "symbol" in change and "kind" in change
    for block in payload["context"]:
        assert block.get("reasons")
    for fact in payload["variable_definitions"]:
        assert "reason" in fact


def test_no_static_analyzer_is_invoked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def _fail(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("Static analyzer invoked during Change Review generation")

    monkeypatch.setattr("sattlint.analyzers.registry.get_default_analyzer_catalog", _fail)
    cfg = build_cfg(tmp_path)
    result = generate_change_review(cfg, "Demo", output_dir=tmp_path / "out")
    assert result.json_path.exists()


def test_review_snapshot_collects_no_diagnostics(tmp_path: Path):
    cfg = build_cfg(tmp_path)
    official = load_version_snapshot(cfg, "Demo", mode="official")
    assert official.snapshot.diagnostics == ()


def test_function_block_change_produces_compact_review(tmp_path: Path):
    program_dir = tmp_path / "programs"
    write_project(program_dir, name="Demo", official_text=FUNCTION_BLOCK_OFFICIAL, draft_text=FUNCTION_BLOCK_DRAFT)
    cfg = build_cfg(tmp_path, program_dir=program_dir)
    result = generate_change_review(cfg, "Demo", output_dir=tmp_path / "out")
    kinds = {change.kind.value for change in result.review.changes}
    assert "expression_changed" in kinds
    assert result.review.size_stats.source_reduction_percent > 50.0


def _large_program() -> str:
    header = (
        '"Syntax version 2.23, date: 2026-04-20-12:00:00.000 N"\n'
        '"Original file date: ---"\n'
        '"Program date: 2026-04-20-12:00:00.000, name: Demo"\n'
        "\n"
        "BasePicture Invocation\n"
        "   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0\n"
        "    ) : MODULEDEFINITION DateCode_ 1\n"
        "\n"
        "LOCALVARIABLES\n"
    )
    variables = "".join(f"   Var{i}: integer := {i};\n" for i in range(120))
    code: list[str] = ["\nModuleDef\nClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\nModuleCode\n"]
    code.append("   EQUATIONBLOCK B0 COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n      Var0 = 0;\n")
    for i in range(1, 120):
        code.append(f"   EQUATIONBLOCK B{i} COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :\n      Var{i} = Var{i - 1} + 1;\n")
    code.append("\nENDDEF (*BasePicture*);\n")
    return header + variables + "".join(code)


def test_context_is_far_smaller_than_project_for_large_program(tmp_path: Path):
    official = _large_program()
    draft = official.replace("      Var1 = Var0 + 1;", "      Var1 = Var0 + 2;")

    official_version, draft_version, _cfg = load_pair(tmp_path, official, draft)
    provider = SourceTextProvider({**official_version.source_files, **draft_version.source_files})
    changes = compute_semantic_diff(official_version, draft_version)
    relevance = compute_relevance(official_version, draft_version, changes)
    review = build_change_review(official_version, draft_version, changes, relevance, snippet_provider=provider)
    assert review.size_stats.semantic_change_count == 1
    assert review.size_stats.selected_source_size < review.size_stats.total_project_source_size / 4


def test_metadata_overhead_is_compact(tmp_path: Path):
    cfg = build_cfg(tmp_path)
    result = generate_change_review(cfg, "Demo", output_dir=tmp_path / "out")
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    for change in payload["changes"]:
        context = change.get("semantic_context")
        if not context:
            continue
        assert all(isinstance(read, str) for read in context["direct_reads"])
        assert all(isinstance(write, str) for write in context["direct_writes"])
    facts = payload["variable_definitions"]
    symbols = [fact["symbol"] for fact in facts]
    assert len(symbols) == len(set(symbols))
    assert result.review.size_stats.artifact_size >= result.review.size_stats.selected_source_size


def test_draft_and_official_programs_unused_when_unrelated(tmp_path: Path):
    assert OFFICIAL_PROGRAM != DRAFT_PROGRAM


def _moduletype(name: str, *, origin_file: str, origin_lib: str) -> ModuleTypeDef:
    return ModuleTypeDef(
        name=name,
        moduleparameters=[],
        localvariables=[Variable(name=f"{name}Value", datatype=ScalarDatatype.INTEGER)],
        moduledef=ModuleDef(),
        modulecode=ModuleCode(sequences=[], equationblocks=[]),
        origin_file=origin_file,
        origin_lib=origin_lib,
    )


def test_change_review_snapshot_can_exclude_dependency_moduletypes(tmp_path: Path):
    root_type = _moduletype("RootType", origin_file="Demo.s", origin_lib="DemoLib")
    dependency_type = _moduletype("DependencyType", origin_file="Dependency.x", origin_lib="OtherLib")
    bp = BasePicture(
        header=ModuleHeader(name="Demo", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Demo",
        moduletype_defs=[root_type, dependency_type],
        moduledef=ModuleDef(),
        origin_file="Demo.s",
        origin_lib="DemoLib",
    )

    snapshot = build_snapshot_from_loaded_project(
        bp,
        ProjectGraph(),
        entry_file=tmp_path / "Demo.s",
        workspace_root=tmp_path,
        include_dependency_modules=False,
    )

    paths = {definition.canonical_path for definition in snapshot.definitions}
    assert any(path.startswith("RootType") for path in paths)
    assert not any(path.startswith("DependencyType") for path in paths)


def test_comment_only_edit_keeps_statement_keys_stable() -> None:
    def _module_code(*, with_comments: bool) -> ModuleCode:
        sequence_nodes: list[SFCBodyItem] = []
        if with_comments:
            sequence_nodes.append(CodeComment(text="a note"))
        sequence_nodes.append(SFCStep(kind="step", name="Start", code=SFCCodeBlocks()))
        if with_comments:
            sequence_nodes.append(CodeComment(text="another note"))
        sequence_nodes.append(SFCTransition(name="Go", condition=True))
        equation_code: list[CodeItem] = []
        if with_comments:
            equation_code.append(CodeComment(text="equation note"))
        equation_code.append(Assignment(target=VarRef(name="X"), value=1))
        return ModuleCode(
            sequences=[
                Sequence(
                    name="Main",
                    type="SEQUENCE",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=sequence_nodes,
                )
            ],
            equationblocks=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=equation_code,
                )
            ],
        )

    without_keys = [key for key, _statement, _kind, _span in _iter_code_statements(_module_code(with_comments=False))]
    with_keys = [key for key, _statement, _kind, _span in _iter_code_statements(_module_code(with_comments=True))]

    assert with_keys == without_keys


def test_artifacts_include_module_connection_changes(tmp_path: Path):
    program_dir = tmp_path / "programs"
    write_project(
        program_dir,
        name="Demo",
        official_text=CONNECTION_PROGRAM,
        draft_text=CONNECTION_PROGRAM_ALT_SOURCE,
    )
    cfg = build_cfg(tmp_path, program_dir=program_dir)
    result = generate_change_review(cfg, "Demo", output_dir=tmp_path / "out")

    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    connection_changes = [change for change in payload["changes"] if change["kind"] == "connection_changed"]
    assert len(connection_changes) == 1
    assert connection_changes[0]["official"] == "Open => StartCmd"
    assert connection_changes[0]["draft"] == "Open => AltCmd"

    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "Connection 'Open' changed" in markdown
    assert "Open => StartCmd" in markdown
    assert "Open => AltCmd" in markdown


WATCH_PROGRAM = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Flow: integer := 0;
   ValveOpen: boolean := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      ValveOpen = Flow > 0;
   EQUATIONBLOCK Watch COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      Flow = Flow + 1;

ENDDEF (*BasePicture*);
"""

WATCH_PROGRAM_DRAFT = """\
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: Demo"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   Flow: integer := 0;
   ValveOpen: boolean := False;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      ValveOpen = Flow > 5;
   EQUATIONBLOCK Watch COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
      ValveOpen = False;

ENDDEF (*BasePicture*);
"""


def test_block_that_stopped_touching_a_variable_stays_in_context(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, WATCH_PROGRAM, WATCH_PROGRAM_DRAFT)
    provider = SourceTextProvider({**official.source_files, **draft.source_files})
    changes = compute_semantic_diff(official, draft)
    relevance = compute_relevance(official, draft, changes)
    review = build_change_review(official, draft, changes, relevance, snippet_provider=provider)

    watch_reasons = [reason for block in review.context if block.name == "Watch" for reason in block.reasons]
    assert any("No longer" in reason and "Flow" in reason for reason in watch_reasons)


def test_removed_call_is_not_listed_as_a_callee(tmp_path: Path):
    official_text = OFFICIAL_PROGRAM.replace(
        "      ValveOpen = Flow > 0;",
        "      ValveOpen = Flow > 0;\n      Flow = GetTime();",
    )
    draft_text = OFFICIAL_PROGRAM.replace(
        "      ValveOpen = Flow > 0;",
        "      ValveOpen = Flow > 5;",
    )
    official, draft, _cfg = load_pair(tmp_path, official_text, draft_text)
    changes = compute_semantic_diff(official, draft)
    relevance = compute_relevance(official, draft, changes)

    assert changes
    contexts = dict(relevance.change_contexts)
    for index, change in enumerate(changes):
        if change.kind is ChangeKind.REMOVED:
            continue
        context = contexts.get(index)
        if context is not None:
            assert "GetTime" not in {fact.symbol for fact in context.callees}


def test_selected_source_size_uses_utf8_bytes(tmp_path: Path):
    official_text = OFFICIAL_PROGRAM.replace(
        "   Flow: integer := 0;",
        '   Flow: integer := 0;\n   Msg: string := "Grüße";',
    ).replace("      Flow = 0;", '      Flow = 0;\n      Msg = "Grüße";')
    draft_text = official_text.replace('Msg = "Grüße";', 'Msg = "Grüße!";')
    official, draft, _cfg = load_pair(tmp_path, official_text, draft_text)
    provider = SourceTextProvider({**official.source_files, **draft.source_files})
    changes = compute_semantic_diff(official, draft)
    relevance = compute_relevance(official, draft, changes)
    review = build_change_review(official, draft, changes, relevance, snippet_provider=provider)

    sources = [
        text
        for block in review.context
        for text in (block.source, block.official_source, block.draft_source)
        if text is not None
    ]
    assert any(any(ord(character) > 127 for character in source) for source in sources)
    assert review.size_stats.selected_source_size == sum(len(source.encode("utf-8")) for source in sources)
    assert review.size_stats.selected_source_size > sum(len(source) for source in sources)


def test_context_reports_the_official_and_draft_location_of_a_changed_block(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, OFFICIAL_PROGRAM, DRAFT_PROGRAM)
    provider = SourceTextProvider({**official.source_files, **draft.source_files})
    changes = compute_semantic_diff(official, draft)
    relevance = compute_relevance(official, draft, changes)
    review = build_change_review(official, draft, changes, relevance, snippet_provider=provider)

    changed = next(block for block in review.context if block.role == "changed")
    assert changed.official_file == "Demo.x"
    assert changed.draft_file == "Demo.s"
    assert changed.official_line_start is not None
    assert changed.draft_line_start is not None


def test_relevant_block_stat_matches_the_blocks_the_review_renders(tmp_path: Path):
    official, draft, _cfg = load_pair(tmp_path, WATCH_PROGRAM, WATCH_PROGRAM_DRAFT)
    provider = SourceTextProvider({**official.source_files, **draft.source_files})
    changes = compute_semantic_diff(official, draft)
    relevance = compute_relevance(official, draft, changes)
    review = build_change_review(official, draft, changes, relevance, snippet_provider=provider)

    assert review.size_stats.relevant_block_count == len(review.context)


def test_ambiguous_root_module_type_fails_instead_of_picking_one(tmp_path: Path) -> None:
    first = _moduletype("Dup", origin_file="Demo.s", origin_lib="DemoLib")
    second = _moduletype("Dup", origin_file="nested/Demo.s", origin_lib="DemoLib")
    instance = ModuleTypeInstance(
        header=ModuleHeader(name="Unit", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduletype_name="Dup",
        parametermappings=[],
    )
    bp = BasePicture(
        header=ModuleHeader(name="Demo", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Demo",
        moduletype_defs=[first, second],
        submodules=[instance],
        moduledef=ModuleDef(),
        origin_file="Demo.s",
        origin_lib="DemoLib",
    )
    snapshot = build_snapshot_from_loaded_project(
        bp,
        ProjectGraph(),
        entry_file=tmp_path / "Demo.s",
        workspace_root=tmp_path,
        include_dependency_modules=False,
    )

    with pytest.raises(ValueError, match="Ambiguous module type 'Dup'"):
        build_code_model(snapshot, include_dependency_modules=False)


def _review_with_timestamp(generated_at: str):
    return ChangeReview(
        metadata=ReviewMetadata(
            project="Demo",
            official_revision="official",
            draft_revision="draft",
            generated_at=generated_at,
        ),
        changes=(),
        context=(),
        variable_definitions=(),
        size_stats=ReviewSizeStats(
            total_project_source_size=0,
            selected_source_size=0,
            metadata_size=0,
            artifact_size=0,
            source_reduction_percent=0.0,
            semantic_change_count=0,
            relevant_block_count=0,
            relevant_variable_count=0,
            contextual_block_count=0,
        ),
    )


def test_artifact_names_use_the_review_utc_timestamp(tmp_path: Path):
    review = _review_with_timestamp("2026-11-19T10:20:30.123456+02:00")
    json_path, markdown_path = write_review_artifacts(review, tmp_path)

    assert "20261119T082030.123456Z" in json_path.name
    assert json_path.stem == markdown_path.stem

    same_second = _review_with_timestamp("2026-11-19T08:20:30.654321+00:00")
    later_json, _markdown = write_review_artifacts(same_second, tmp_path)

    assert later_json.name != json_path.name


def test_block_header_search_is_case_insensitive_and_prefers_the_nearest_match():
    source = {
        1: "EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :",
        2: "   X = 1;",
        3: "   equationblock main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :",
        4: "   X = 2;",
        6: "   X = 3;",
    }

    class _Provider:
        def lines(self, _file: str, start: int, _end: int, *, library: str | None = None) -> str | None:
            return source.get(start, "")

    block = SimpleNamespace(kind="equation", name="Main", line_start=6, source_file="Demo.x", source_library=None)

    assert _expand_block_start(cast(Any, _Provider()), cast(Any, block)) == 3
