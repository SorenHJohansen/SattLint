from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Protocol, cast

ROOT = Path(__file__).resolve().parent.parent


class DocsChecker(Protocol):
    def github_slug(self, text: str) -> str: ...

    def heading_anchors(self, text: str) -> set[str]: ...

    def check_file(self, path: Path, root: Path) -> list[str]: ...

    def check_docs_index(self, root: Path) -> list[str]: ...

    def check_root_entry(self, root: Path) -> list[str]: ...


def _load_checker() -> DocsChecker:
    spec = importlib.util.spec_from_file_location("sattlint_check_docs", ROOT / "scripts" / "check_docs.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load scripts/check_docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(DocsChecker, module)


CHECKER = _load_checker()


def test_github_slug_matches_heading_style() -> None:
    assert CHECKER.github_slug("Analyzer settings") == "analyzer-settings"
    assert CHECKER.github_slug("CLI and `code`") == "cli-and-code"
    assert CHECKER.github_slug("What's new?") == "whats-new"
    assert CHECKER.github_slug("A_B") == "a_b"
    assert CHECKER.github_slug("  spaced  ") == "spaced"


def test_heading_anchors_number_duplicates() -> None:
    anchors = CHECKER.heading_anchors("# Title\n\n## Same\n\n## Same\n\n## Same\n")
    assert anchors == {"title", "same", "same-1", "same-2"}


def test_check_file_reports_missing_anchor(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text(
        "# Page\n\n## Section\n\n[ok](#section)\n\n[bad](#missing)\n",
        encoding="utf-8",
    )

    errors = CHECKER.check_file(page, tmp_path)

    assert len(errors) == 1
    assert "missing heading anchor #missing" in errors[0]


def test_check_file_accepts_duplicate_anchor_suffix(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text(
        "# Page\n\n## Same\n\n## Same\n\n[second](#same-1)\n",
        encoding="utf-8",
    )

    assert CHECKER.check_file(page, tmp_path) == []


def test_check_file_ignores_code_spans_and_external_links(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text(
        "# Page\n\n"
        "```bash\n"
        "[not a link](missing.md)\n"
        "```\n\n"
        "Inline `[also not a link](missing.md)` text.\n\n"
        "[external](https://example.com/missing)\n",
        encoding="utf-8",
    )

    assert CHECKER.check_file(page, tmp_path) == []


def test_check_file_follows_relative_markdown_anchor(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("# Target\n\n## Known heading\n", encoding="utf-8")
    page = tmp_path / "page.md"
    page.write_text("[good](target.md#known-heading)\n\n[bad](target.md#unknown)\n", encoding="utf-8")

    errors = CHECKER.check_file(page, tmp_path)

    assert len(errors) == 1
    assert "missing heading anchor #unknown in target.md" in errors[0]


def test_check_docs_index_requires_every_page(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n\n[One](one.md)\n", encoding="utf-8")
    (docs / "one.md").write_text("# One\n", encoding="utf-8")
    (docs / "two.md").write_text("# Two\n", encoding="utf-8")

    errors = CHECKER.check_docs_index(tmp_path)

    assert errors == ["docs/two.md: not linked from docs/README.md"]


def test_check_root_entry_requires_docs_index_link(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.md").write_text("# Docs\n", encoding="utf-8")
    readme = tmp_path / "README.md"

    readme.write_text("# Project\n\n[docs](docs/README.md)\n", encoding="utf-8")
    assert CHECKER.check_root_entry(tmp_path) == []

    readme.write_text("# Project\n", encoding="utf-8")
    assert CHECKER.check_root_entry(tmp_path) == ["README.md: must link to docs/README.md"]
