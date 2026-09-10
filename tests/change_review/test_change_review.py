# pyright: reportPrivateUsage=false
"""End-to-end Change Review tests: artifacts, output location, serialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sattlint.change_review import (
    ChangeReviewResult,
    build_change_review,
    compute_relevance,
    compute_semantic_diff,
    generate_change_review,
    load_version_snapshot,
)
from sattlint.change_review.serialization.json_serializer import review_to_json
from sattlint.change_review.source import SourceTextProvider
from tests.helpers.change_review_support import (
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
