# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Project graph invariant tests (Phase 19).

Unique nodes, deterministic dependency edges, missing-dependency tracking,
unavailable-vs-missing distinction, strict/non-strict behavior, and repeated
load equivalence.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sattline_parser import parse_source_text as parser_core_parse_source_text

from sattlint.models.project_graph import ProjectGraph, merge_project_basepicture
from sattlint.project.loader_base import record_missing_library
from tests.helpers.app_menus_support import VALID_SINGLE_FILE


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
