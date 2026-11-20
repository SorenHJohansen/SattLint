# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false, reportAttributeAccessIssue=false
"""Production modules never import test packages or corpus helpers."""

from __future__ import annotations

import ast
from pathlib import Path


def test_production_code_does_not_import_tests_or_corpus() -> None:
    src_dir = Path(__file__).resolve().parents[2] / "src" / "sattlint"
    violations: list[str] = []
    for path in sorted(src_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "tests" or node.module.startswith("tests."):
                    violations.append(f"{path}: imports {node.module}")
                    break
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "tests" or alias.name.startswith("tests."):
                        violations.append(f"{path}: imports {alias.name}")
                        break
    assert violations == [], f"production modules import tests/corpus: {violations}"
