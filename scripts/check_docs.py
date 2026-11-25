"""Check that the Markdown documentation is internally consistent.

The documentation set is part of the product. This script keeps it honest by
failing when:

- a relative link points at a path that does not exist;
- a fragment points at a heading that does not exist in the target page;
- a page under ``docs/`` is not linked from the documentation index;
- the root README does not point at the documentation index.

Fenced code blocks and inline code spans are ignored so examples are not
treated as links. External URLs are not fetched: the check is deterministic and
network-free.

Usage::

    python scripts/check_docs.py
"""

from __future__ import annotations

import fnmatch
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
        "venv",
    }
)
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "ftp:", "git@", "//")
# The upgrade plans are historical records that intentionally name paths that
# were later removed or renamed, so their links are not part of the live docs
# set. New versioned plans are matched by pattern rather than by exact name.
IGNORED_PATTERNS = ("docs/parser-upgrade-plan*.md",)
# Allow one level of balanced parentheses inside a link target, which is how
# paths such as ``docs/api_(old).md`` appear in Markdown.
LINK_RE = re.compile(r"\[[^\]]*\]\(((?:[^()\\]|\\.|\([^()]*\))*)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
HTML_ANCHOR_RE = re.compile(r"<a\s+[^>]*(?:name|id)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
MARKDOWN_LINK_TEXT_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
NON_SLUG_RE = re.compile(r"[^\w\- ]", re.UNICODE)


def _without_fences(text: str) -> str:
    """Remove fenced code blocks so examples are not treated as links."""
    return FENCE_RE.sub("", text)


def _without_code(text: str) -> str:
    """Remove fenced blocks and inline code spans."""
    return INLINE_CODE_RE.sub("", _without_fences(text))


def _link_targets(text: str) -> list[str]:
    return [target.strip() for target in LINK_RE.findall(_without_code(text))]


def _is_external(target: str) -> bool:
    return target.startswith("<") or target.startswith(EXTERNAL_PREFIXES)


def _split_target(target: str) -> tuple[str, str]:
    """Split a Markdown link target into a path and a decoded fragment."""
    stripped = target.strip()
    if stripped.startswith("<") and ">" in stripped:
        stripped = stripped[1 : stripped.index(">")]
    else:
        stripped = stripped.split(" ", 1)[0]
    path, _, fragment = stripped.partition("#")
    return unquote(path), unquote(fragment)


def _heading_text(raw: str) -> str:
    text = HTML_TAG_RE.sub("", raw)
    text = MARKDOWN_IMAGE_RE.sub(r"\1", text)
    text = MARKDOWN_LINK_TEXT_RE.sub(r"\1", text)
    for marker in ("`", "*", "~"):
        text = text.replace(marker, "")
    return text.strip()


def github_slug(text: str) -> str:
    """Return the GitHub-style heading anchor for one heading's text."""
    lowered = _heading_text(text).casefold()
    cleaned = NON_SLUG_RE.sub("", lowered)
    slug = re.sub(r"\s+", "-", cleaned).strip("-")
    return slug


def heading_anchors(text: str) -> set[str]:
    """Every fragment a Markdown document exposes, including duplicate suffixes."""
    anchors = set(HTML_ANCHOR_RE.findall(_without_fences(text)))
    counts: dict[str, int] = {}
    for raw_heading in HEADING_RE.findall(_without_fences(text)):
        base = github_slug(raw_heading[1])
        if not base:
            continue
        number = counts.get(base, 0)
        slug = base if number == 0 else f"{base}-{number}"
        while slug in anchors:
            number += 1
            slug = f"{base}-{number}"
        counts[base] = number + 1
        anchors.add(slug)
    return anchors


def _is_ignored(relative: Path) -> bool:
    posix = relative.as_posix()
    return any(fnmatch.fnmatchcase(posix, pattern) for pattern in IGNORED_PATTERNS)


def markdown_files(root: Path = ROOT) -> list[Path]:
    """Every Markdown file the gate owns, excluding generated root trees."""
    files: list[Path] = []
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in SKIP_DIRS:
            continue
        if _is_ignored(relative):
            continue
        files.append(path)
    return sorted(files)


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _check_anchor(
    path: Path,
    fragment: str,
    target_text: str,
    target_label: str,
    root: Path,
) -> list[str]:
    anchors = heading_anchors(target_text)
    if fragment in anchors or fragment == "":
        return []
    return [f"{_display_path(path, root)}: missing heading anchor #{fragment} in {target_label}"]


def check_file(path: Path, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for target in _link_targets(text):
        if not target or _is_external(target):
            continue
        relative_target, fragment = _split_target(target)
        if not relative_target and not fragment:
            continue
        target_path = (path.parent / relative_target).resolve() if relative_target else path.resolve()
        if relative_target and not target_path.exists():
            errors.append(f"{_display_path(path, root)}: missing link target {target}")
            continue
        if not fragment or target_path.suffix.casefold() != ".md" or not target_path.is_file():
            continue
        errors.extend(
            _check_anchor(
                path,
                fragment,
                target_path.read_text(encoding="utf-8"),
                _display_path(target_path, root),
                root,
            )
        )
    return errors


def check_docs_index(root: Path = ROOT) -> list[str]:
    """Every page under docs/ must be linked from docs/README.md."""
    docs_dir = root / "docs"
    index_path = docs_dir / "README.md"
    if not index_path.is_file():
        return ["docs/README.md: documentation index is missing"]

    indexed: set[Path] = set()
    for target in _link_targets(index_path.read_text(encoding="utf-8")):
        if not target or _is_external(target):
            continue
        relative_target, _fragment = _split_target(target)
        if not relative_target:
            continue
        indexed.add((index_path.parent / relative_target).resolve())

    errors: list[str] = []
    for page in sorted(docs_dir.rglob("*.md")):
        if page.resolve() == index_path.resolve():
            continue
        if page.resolve() not in indexed:
            errors.append(f"{_display_path(page, root)}: not linked from docs/README.md")
    return errors


def check_root_entry(root: Path = ROOT) -> list[str]:
    """The root README must point at the canonical docs index."""
    readme = root / "README.md"
    if not readme.is_file():
        return ["README.md: root README is missing"]
    docs_index = (root / "docs" / "README.md").resolve()
    for target in _link_targets(readme.read_text(encoding="utf-8")):
        if not target or _is_external(target):
            continue
        relative_target, _fragment = _split_target(target)
        if not relative_target:
            continue
        if (readme.parent / relative_target).resolve() == docs_index:
            return []
    return ["README.md: must link to docs/README.md"]


def main() -> int:
    errors: list[str] = []
    files = markdown_files()
    for path in files:
        errors.extend(check_file(path))
    errors.extend(check_docs_index())
    errors.extend(check_root_entry())
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"{len(errors)} documentation problem(s) in {len(files)} Markdown file(s)", file=sys.stderr)
        return 1
    print(f"Checked {len(files)} Markdown file(s): links, anchors, and docs index resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
