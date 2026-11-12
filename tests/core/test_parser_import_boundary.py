"""Import-boundary guard for the parser package.

SattLint reads ``sattline-parser`` through one module, ``sattlint.parser_api``.
Every other module in ``src/`` imports the surface, so a parser release that
moves or renames an internal module cannot break imports scattered across the
tree.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "sattlint"
SURFACE_MODULE = SOURCE_ROOT / "parser_api.py"
PARSER_PACKAGE = "sattline_parser"


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


def test_only_the_surface_module_imports_the_parser_package() -> None:
    assert _parser_imports(SURFACE_MODULE), "the scan found no parser import in the surface module"

    violations = _direct_imports()

    assert not violations, "import the parser through sattlint.parser_api:\n" + "\n".join(
        str(violation) for violation in violations
    )
