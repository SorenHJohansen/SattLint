"""Focused tests for the compact datatype leaf index."""

from __future__ import annotations

from sattlint.analyzers.variables._datatype_leaf_index import LeafPathIndex


def test_leaf_path_index_matches_exact_prefix_and_subtree() -> None:
    index = LeafPathIndex.from_paths(["A", "B.C", "B.D", "E.F.G"])

    assert index.all_mask == 0b1111
    assert index.mask_for_key("b.c") == 0b0010
    assert index.mask_for_key("b") == 0b0110
    assert index.mask_for_key("e.f") == 0b1000
    assert index.mask_for_key("missing") == 0

    mask, has_whole = index.match(["B", "E.F.G", ""])
    assert has_whole is True
    assert mask == 0b1110

    assert index.mask_for_prefixes(["B.C", "B"]) == 0b0110


def test_leaf_path_index_dedupes_casefold_and_ignores_empty_paths() -> None:
    index = LeafPathIndex.from_paths(["A.B", "a.b", "", "C"])

    assert index.leaf_keys == ("a.b", "c")
    assert index.leaf_paths == ("A.B", "C")
    assert index.all_mask == 0b11


def test_leaf_path_index_empty_has_no_leaves() -> None:
    index = LeafPathIndex.empty()

    assert index.leaf_keys == ()
    assert index.leaf_paths == ()
    assert index.all_mask == 0
    assert index.match(["A", ""]) == (0, True)
