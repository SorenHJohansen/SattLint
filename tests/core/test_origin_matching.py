"""Origin ownership compares whole file names, not just stems."""

from __future__ import annotations

from sattlint.core.origin import is_root_origin


def test_draft_and_official_bodies_of_one_program_are_distinct_origins() -> None:
    assert not is_root_origin(
        "Main.x",
        "Library",
        root_origin_file="Main.s",
        root_origin_library="Library",
    )


def test_same_file_name_in_the_same_library_is_the_root_origin() -> None:
    assert is_root_origin(
        "Other/Main.s",
        "Library",
        root_origin_file="Main.s",
        root_origin_library="Library",
    )
