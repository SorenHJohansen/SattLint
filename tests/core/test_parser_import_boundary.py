"""Import-boundary guard for the parser package.

SattLint reads ``sattline-parser`` through one module, ``sattlint.parser_api``.
Every other module in ``src/`` imports the surface, so a parser release that
moves or renames an internal module cannot break imports scattered across the
tree.

The allowlist below is temporary. Each entry names a file that still imports a
parser submodule and is scheduled to move to the surface. Shrink it, never grow
it, and remove it before the release.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "sattlint"
SURFACE_MODULE = SOURCE_ROOT / "parser_api.py"
PARSER_PACKAGE = "sattline_parser"

#: Files that still import the parser directly, mapped to the modules each may
#: still reach. The removal step for each one deletes its entry in the same
#: change.
PENDING_SURFACE_MIGRATION: dict[str, frozenset[str]] = {
    "project/parser_adapter.py": frozenset({"sattline_parser.validation"}),
    "validation/policy.py": frozenset({"sattline_parser.validation"}),
}


@dataclass(frozen=True)
class DirectParserImport:
    """One import statement that reaches the parser package directly."""

    path: str
    line: int
    module: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} imports {self.module}"


def _is_parser_module(name: str) -> bool:
    return name == PARSER_PACKAGE or name.startswith(f"{PARSER_PACKAGE}.")


def _parser_imports(path: Path) -> list[DirectParserImport]:
    relative = path.relative_to(SOURCE_ROOT).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[DirectParserImport] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module is not None and _is_parser_module(node.module):
                found.append(DirectParserImport(relative, node.lineno, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_parser_module(alias.name):
                    found.append(DirectParserImport(relative, node.lineno, alias.name))
    return found


def _direct_imports() -> list[DirectParserImport]:
    violations: list[DirectParserImport] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if path == SURFACE_MODULE:
            continue
        violations.extend(_parser_imports(path))
    return violations


def _unexpected_imports() -> list[DirectParserImport]:
    unexpected: list[DirectParserImport] = []
    for violation in _direct_imports():
        allowed = PENDING_SURFACE_MIGRATION.get(violation.path)
        if allowed is None or violation.module not in allowed:
            unexpected.append(violation)
    return unexpected


def test_only_the_surface_module_imports_the_parser_package() -> None:
    violations = _unexpected_imports()

    assert not violations, "import the parser through sattlint.parser_api:\n" + "\n".join(
        str(violation) for violation in violations
    )


def test_pending_allowlist_entries_are_still_guilty() -> None:
    imported_paths = {violation.path for violation in _direct_imports()}
    stale = sorted(set(PENDING_SURFACE_MIGRATION) - imported_paths)

    assert not stale, "drop these allowlist entries; their files no longer import the parser: " + ", ".join(stale)
