# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Semantic invariant tests (Phase 18).

Independent of individual analyzers: every reference resolves to a definition
(or an explicit unresolved state), canonical identities are unique, builds are
deterministic, source locations are valid, and repeated builds are equivalent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sattlint.core import semantic as semantic_core_module
from sattlint.core._semantic_snapshot import SemanticSnapshot
from tests.helpers.app_menus_support import VALID_SINGLE_FILE


@pytest.fixture()
def snapshot(tmp_path: Path) -> SemanticSnapshot:
    entry_file = tmp_path / "Invocation.s"
    return semantic_core_module.load_source_snapshot(
        entry_file,
        VALID_SINGLE_FILE,
        workspace_root=tmp_path,
        collect_variable_diagnostics=True,
        debug=True,
    )


def test_repeated_builds_are_equivalent(tmp_path: Path) -> None:
    entry_file = tmp_path / "Invocation.s"
    first = semantic_core_module.load_source_snapshot(
        entry_file,
        VALID_SINGLE_FILE,
        workspace_root=tmp_path,
        collect_variable_diagnostics=True,
    )
    second = semantic_core_module.load_source_snapshot(
        entry_file,
        VALID_SINGLE_FILE,
        workspace_root=tmp_path,
        collect_variable_diagnostics=True,
    )

    assert [definition.canonical_path for definition in first.definitions] == [
        definition.canonical_path for definition in second.definitions
    ]
    assert first.to_snapshot_dict() == second.to_snapshot_dict()


def test_canonical_identities_are_unique(snapshot: SemanticSnapshot) -> None:
    canonical_paths = [definition.canonical_path.casefold() for definition in snapshot.definitions]
    assert len(canonical_paths) == len(set(canonical_paths))

    definition_keys = [
        tuple(segment.casefold() for segment in definition.canonical_path.split("."))
        for definition in snapshot.definitions
    ]
    assert len(definition_keys) == len(set(definition_keys))


def test_definitions_are_indexed_by_canonical_key(snapshot: SemanticSnapshot) -> None:
    for definition in snapshot.definitions:
        definition_key = tuple(segment.casefold() for segment in definition.canonical_path.split("."))
        assert definition_key in snapshot._definitions_by_key
        assert snapshot._definitions_by_key[definition_key].canonical_path == definition.canonical_path


def test_references_have_valid_identity_and_locations(snapshot: SemanticSnapshot) -> None:
    for references in snapshot._references_by_definition_key.values():
        for reference in references:
            assert reference.canonical_path
            assert reference.line >= 0
            assert reference.column >= 0
            assert reference.length >= 0
            assert reference.text


def test_source_locations_are_valid(snapshot: SemanticSnapshot) -> None:
    for definition in snapshot.definitions:
        if definition.declaration_span is None:
            continue
        assert definition.declaration_span.line >= 0
        assert definition.declaration_span.column >= 0

    for occurrences in snapshot._references_by_file.values():
        for occurrence in occurrences:
            assert occurrence.line >= 0
            assert occurrence.column >= 0
            assert occurrence.text


def test_definition_query_is_deterministic(snapshot: SemanticSnapshot) -> None:
    first = snapshot.find_definitions("Invocation")
    second = snapshot.find_definitions("Invocation")
    assert [(definition.canonical_path, definition.kind) for definition in first] == [
        (definition.canonical_path, definition.kind) for definition in second
    ]


def test_all_definitions_have_kind_and_declaration_paths(snapshot: SemanticSnapshot) -> None:
    for definition in snapshot.definitions:
        assert definition.kind
        assert definition.declaration_module_path
        assert definition.canonical_path
        assert definition.display_module_path
