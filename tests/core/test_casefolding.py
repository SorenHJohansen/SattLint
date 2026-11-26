"""Unit identity versus plain text normalization.

The parser owns SattLine name identity: its CP1252 table folds ``Library`` and
``library`` together and leaves ``Straße`` distinct from ``STRASSE``. Unicode
case folding is a different rule and must not be used to match names the parser
owns.
"""

from __future__ import annotations

from sattlint.core.origin import is_root_origin
from sattlint.utils.casefolding import casefold_key, dedupe_unit_names, is_anytype_name, unit_equal, unit_key


def test_unit_key_folds_ascii_names_by_language_identity() -> None:
    assert unit_key("library") == "LIBRARY"
    assert unit_equal("Library", "library")


def test_unit_key_keeps_casefold_collisions_apart() -> None:
    assert casefold_key("Straße") == "strasse"
    assert unit_key("Straße") == "STRAßE"
    assert not unit_equal("Straße", "STRASSE")


def test_dedupe_unit_names_keeps_one_spelling_per_identity() -> None:
    assert dedupe_unit_names(["Library", "library", "Straße", "STRASSE", " "]) == [
        "Library",
        "Straße",
        "STRASSE",
    ]


def test_is_anytype_name_uses_language_identity() -> None:
    assert is_anytype_name("AnyType")
    assert not is_anytype_name("AnyType_")


def test_root_origin_matching_uses_language_identity() -> None:
    assert is_root_origin(
        "Library.s",
        "Lib",
        root_origin_file="library.s",
        root_origin_library="LIB",
    )
    assert not is_root_origin(
        "Straße.s",
        "Lib",
        root_origin_file="STRASSE.s",
        root_origin_library="Lib",
    )
