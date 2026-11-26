"""Release state consistency checks.

A release names one version in three places: the package version, the newest
dated changelog section, and the release tag. These checks compare the first
two from the working tree, so they stay independent of git metadata and run on
every normal gate. The tag comparison needs a tag, so CI performs it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION_FILE = ROOT / "src" / "sattlint" / "__version__.py"

_VERSION_DEFINITION = re.compile(r'^__version__ = "(?P<version>[0-9.]+)"$', re.MULTILINE)
_CALENDAR_VERSION = re.compile(r"[0-9]{4}\.[0-9]+\.[0-9]+")
_SECTION_HEADING = re.compile(
    r"^## \[(?P<label>[^\]]+)\](?: - (?P<release_date>[0-9]{4}-[0-9]{2}-[0-9]{2}))?\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Section:
    """One level-two changelog section and the text below it."""

    label: str
    release_date: str | None
    body: str


def package_version() -> str:
    """Return the version declared in the package version module."""
    match = _VERSION_DEFINITION.search(VERSION_FILE.read_text(encoding="utf-8"))
    assert match is not None, "src/sattlint/__version__.py does not declare __version__"
    return match.group("version")


def changelog_sections() -> list[Section]:
    """Return the changelog sections in file order, each with its own body."""
    text = CHANGELOG.read_text(encoding="utf-8")
    headings = list(_SECTION_HEADING.finditer(text))
    sections: list[Section] = []
    for index, heading in enumerate(headings):
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections.append(
            Section(
                label=heading.group("label"),
                release_date=heading.group("release_date"),
                body=text[heading.end() : body_end],
            )
        )
    return sections


def dated_sections() -> list[Section]:
    """Return the dated release sections in file order, newest first."""
    return [section for section in changelog_sections() if section.release_date is not None]


def test_package_version_uses_calendar_versioning() -> None:
    assert _CALENDAR_VERSION.fullmatch(package_version()) is not None


def test_package_version_matches_newest_dated_changelog_section() -> None:
    version = package_version()
    dated = dated_sections()

    assert dated, "CHANGELOG.md has no dated release section"
    assert dated[0].label == version, (
        f"the package version is {version} but the newest dated changelog section is {dated[0].label}"
    )


def test_unreleased_is_the_first_section_and_holds_no_release() -> None:
    sections = changelog_sections()

    assert sections, "CHANGELOG.md has no sections"
    unreleased = [section for section in sections if section.label == "Unreleased"]
    assert len(unreleased) == 1, "CHANGELOG.md must keep exactly one [Unreleased] section"
    assert sections[0].label == "Unreleased", "[Unreleased] must sit above the dated sections"
    assert unreleased[0].release_date is None, "[Unreleased] must not carry a release date"
    assert "## [" not in unreleased[0].body, "a dated section was nested inside [Unreleased]"


def test_each_version_is_described_by_one_section() -> None:
    labels = [section.label for section in changelog_sections()]
    duplicates = sorted({label for label in labels if labels.count(label) > 1})

    assert duplicates == [], f"CHANGELOG.md repeats a section for {duplicates}"
