"""Guard against reflective AST traversal in analyzer-facing code.

Analyzers read the parser model through typed fields and the parser ``walk``
API. They must not guess at legacy shapes, so this test rejects the patterns the
migration removed:

* ``__dict__`` enumeration,
* ``children`` attribute or reflective lookup,
* Lark ``.data`` tree sniffing,
* parser tuple-tag constants.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    REPO_ROOT / "src" / "sattlint" / "analyzers",
    REPO_ROOT / "src" / "sattlint" / "core",
    REPO_ROOT / "src" / "sattlint" / "change_review",
    REPO_ROOT / "src" / "sattlint" / "resolution",
)

#: Patterns that only make sense against a retained parse tree or legacy tuple.
FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("__dict__ enumeration", re.compile(r"\b__dict__\b")),
    ("children attribute access", re.compile(r"\.children\b")),
    ("reflective children lookup", re.compile(r"""getattr\s*\([^)]*["']children["']""")),
    ("children hasattr check", re.compile(r"""hasattr\s*\([^)]*["']children["']""")),
    ("Lark tree data access", re.compile(r"\.data\b")),
    ("parser tuple-tag constants", re.compile(r"\bconst\.[A-Z_]+")),
)


def _scanned_sources() -> list[Path]:
    return sorted(path for root in SCAN_ROOTS for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_guard_patterns_match_known_reflective_samples() -> None:
    samples = (
        ("node.__dict__.values()", "__dict__ enumeration"),
        ("node.children", "children attribute access"),
        ('getattr(node, "children", None)', "reflective children lookup"),
        ('hasattr(node, "children")', "children hasattr check"),
        ("node.data == 'statement'", "Lark tree data access"),
        ("const.KEY_VAR_NAME", "parser tuple-tag constants"),
    )

    for sample, expected_label in samples:
        labels = {label for label, pattern in FORBIDDEN_PATTERNS if pattern.search(sample)}
        assert expected_label in labels, f"guard pattern for {expected_label!r} no longer matches {sample!r}"


def test_analyzer_code_has_no_reflective_ast_traversal() -> None:
    violations: list[str] = []

    for path in _scanned_sources():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for label, pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    relative = path.relative_to(REPO_ROOT)
                    violations.append(f"{relative}:{line_number}: {label}: {line.strip()}")

    assert not violations, "reflective AST traversal is not allowed in analyzer code:\n" + "\n".join(violations)
