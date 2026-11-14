"""Check that every relative Markdown link in the repository resolves.

The documentation set is part of the product. This script keeps it honest by
failing when a Markdown file links to a path that does not exist, which is how
links to removed files survive a release.

Usage::

    python scripts/check_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".benchmarks",
        "artifacts",
        "build",
        "cache-dir",
        "custom-cache-dir",
        "dist",
        "htmlcov",
        "node_modules",
        "report-cache-dir",
    }
)
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp:", "git@")
# The upgrade plan is a historical record that intentionally names paths that
# were later removed or renamed, so its links are not part of the live docs set.
IGNORED_PATHS = frozenset({"docs/parser-upgrade-plan.md"})
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def markdown_files() -> list[Path]:
    """Every Markdown file the gate owns, excluding generated trees."""
    files: list[Path] = []
    for path in ROOT.rglob("*.md"):
        relative = path.relative_to(ROOT)
        if str(relative) in IGNORED_PATHS or SKIP_DIRS.intersection(relative.parts):
            continue
        files.append(path)
    return sorted(files)


def _without_fences(text: str) -> str:
    """Remove fenced code blocks so examples are not treated as links."""
    return FENCE_RE.sub("", text)


def _link_targets(text: str) -> list[str]:
    return [target.strip() for target in LINK_RE.findall(_without_fences(text))]


def _is_external(target: str) -> bool:
    return target.startswith(("#", "<")) or target.startswith(EXTERNAL_PREFIXES)


def _relative_path(target: str) -> str:
    """Strip an optional title and a fragment from a Markdown link target."""
    path = target.split(" ", 1)[0].strip("<>")
    return unquote(path.split("#", 1)[0])


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    for target in _link_targets(path.read_text(encoding="utf-8")):
        if not target or _is_external(target):
            continue
        relative = _relative_path(target)
        if not relative:
            continue
        if not (path.parent / relative).resolve().exists():
            errors.append(f"{path.relative_to(ROOT)}: missing link target {target}")
    return errors


def main() -> int:
    errors: list[str] = []
    files = markdown_files()
    for path in files:
        errors.extend(check_file(path))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"{len(errors)} broken link(s) in {len(files)} Markdown file(s)", file=sys.stderr)
        return 1
    print(f"Checked {len(files)} Markdown file(s): all relative links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
