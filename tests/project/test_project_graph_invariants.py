# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Project graph invariant tests (Phase 19).

Unique nodes, deterministic dependency edges, missing-dependency tracking,
unavailable-vs-missing distinction, strict/non-strict behavior, and repeated
load equivalence.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sattline_parser import parse_source_text as parser_core_parse_source_text

from sattlint.models.project_graph import ProjectGraph, merge_project_basepicture
from sattlint.project.parser_adapter import record_missing_library
from tests.helpers.app_menus_support import VALID_SINGLE_FILE


def _picture_named(name: str):
    return replace(parser_core_parse_source_text(VALID_SINGLE_FILE), name=name)


@pytest.fixture()
def graph() -> ProjectGraph:
    return ProjectGraph()


@pytest.fixture()
def base_picture():
    return parser_core_parse_source_text(VALID_SINGLE_FILE)


def test_index_from_basepic_records_unique_nodes_and_origins(graph: ProjectGraph, base_picture) -> None:
    source_path = Path("/tmp/programs/Invocation.s")
    graph.index_from_basepic(base_picture, source_path=source_path, library_name="programs")

    assert graph.source_files == {source_path}
    root_origin = graph.root_origin_for_basepicture(base_picture)
    assert root_origin is not None
    assert root_origin.source_path == source_path
    assert root_origin.library_name == "programs"


def test_root_origin_resolves_each_program_by_identity(graph: ProjectGraph, base_picture) -> None:
    other = _picture_named("Other")
    first_path = Path("/tmp/lib-a/Invocation.s")
    second_path = Path("/tmp/lib-b/Other.s")

    graph.ast_by_name["Invocation"] = base_picture
    graph.ast_by_name["Other"] = other
    graph.index_from_basepic(base_picture, source_path=first_path, library_name="lib-a", program_name="Invocation")
    graph.index_from_basepic(other, source_path=second_path, library_name="lib-b", program_name="Other")

    first_origin = graph.root_origin_for_basepicture(base_picture)
    second_origin = graph.root_origin_for_basepicture(other)
    assert first_origin is not None
    assert second_origin is not None
    assert first_origin.source_path == first_path
    assert first_origin.library_name == "lib-a"
    assert second_origin.source_path == second_path
    assert second_origin.library_name == "lib-b"

    merged = replace(base_picture, origin_file=base_picture.origin_file, origin_lib=base_picture.origin_lib)
    merged_origin = graph.root_origin_for_basepicture(merged)
    assert merged_origin is not None
    assert merged_origin.source_path == first_path


def test_repeated_indexing_produces_deterministic_keys(graph: ProjectGraph, base_picture) -> None:
    source_path = Path("/tmp/programs/Invocation.s")
    graph.index_from_basepic(base_picture, source_path=source_path, library_name="programs")
    first_keys = tuple(sorted(graph.moduletype_defs.keys()))
    first_sources = set(graph.source_files)

    graph.index_from_basepic(base_picture, source_path=source_path, library_name="programs")
    assert tuple(sorted(graph.moduletype_defs.keys())) == first_keys
    assert set(graph.source_files) == first_sources


def test_merge_project_basepicture_is_deterministic(graph: ProjectGraph, base_picture) -> None:
    graph.index_from_basepic(base_picture, source_path=Path("/tmp/programs/Invocation.s"), library_name="programs")
    first = merge_project_basepicture(base_picture, graph)
    second = merge_project_basepicture(base_picture, graph)

    assert first is not base_picture
    assert first.header is base_picture.header
    assert [definition.name for definition in first.datatype_defs] == [
        definition.name for definition in second.datatype_defs
    ]
    assert [definition.name for definition in first.moduletype_defs] == [
        definition.name for definition in second.moduletype_defs
    ]


def test_record_missing_library_non_strict_records_missing(graph: ProjectGraph) -> None:
    record_missing_library(graph, name="MissingLib", mode="draft", strict=False)

    assert any("Missing code file for 'MissingLib'" in message for message in graph.missing)
    assert "missinglib" in graph.unavailable_libraries
    failure = graph.failures["missinglib"]
    assert failure.name == "MissingLib"
    assert failure.message == graph.missing[0]


def test_record_missing_library_strict_raises_without_side_effects(graph: ProjectGraph) -> None:
    with pytest.raises(FileNotFoundError, match="Missing code file for 'MissingLib'"):
        record_missing_library(graph, name="MissingLib", mode="draft", strict=True)

    assert graph.missing == []
    assert "missinglib" not in graph.unavailable_libraries


def test_record_missing_library_controllib_is_missing_like_any_other(graph: ProjectGraph) -> None:
    record_missing_library(graph, name="ControlLib", mode="official", strict=False)

    assert "controllib" in graph.unavailable_libraries
    assert any("Missing code file for 'ControlLib'" in message for message in graph.missing)


def test_library_dependencies_edges_are_casefolded_and_deterministic(graph: ProjectGraph) -> None:
    graph.add_library_dependencies("ProgramA", ["LibB", "libc"])
    graph.add_library_dependencies("PROGRAMA", ["LibB"])

    assert graph.library_dependencies["programa"] == {"libb", "libc"}


def test_root_origin_is_distinct_for_programs_that_share_the_basepicture_header(graph: ProjectGraph) -> None:
    first = parser_core_parse_source_text(VALID_SINGLE_FILE)
    second = parser_core_parse_source_text(VALID_SINGLE_FILE)
    first_path = Path("/tmp/lib-a/Shared.s")
    second_path = Path("/tmp/lib-b/Shared.s")

    graph.ast_by_name["First"] = replace(first, origin_file="Shared.s", origin_lib="LibA")
    graph.ast_by_name["Second"] = replace(second, origin_file="Shared.s", origin_lib="LibB")
    graph.index_from_basepic(
        graph.ast_by_name["First"], source_path=first_path, library_name="LibA", program_name="First"
    )
    graph.index_from_basepic(
        graph.ast_by_name["Second"], source_path=second_path, library_name="LibB", program_name="Second"
    )

    first_origin = graph.root_origin_for_name("First")
    second_origin = graph.root_origin_for_name("Second")
    assert first_origin is not None and first_origin.source_path == first_path
    assert second_origin is not None and second_origin.source_path == second_path
    first_by_picture = graph.root_origin_for_basepicture(graph.ast_by_name["First"])
    second_by_picture = graph.root_origin_for_basepicture(graph.ast_by_name["Second"])
    assert first_by_picture is not None and first_by_picture.source_path == first_path
    assert second_by_picture is not None and second_by_picture.source_path == second_path
    assert first_by_picture is not None and second_by_picture is not None
    assert first_by_picture is not second_by_picture
