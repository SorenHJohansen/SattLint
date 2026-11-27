"""Analyzers read parser collections that arrive as tuples.

The parser emits AST child collections as tuples. A walker that only accepts a
list sees an empty block and reports nothing, so this test runs an analyzer over
a project-loaded picture rather than a hand-built list-shaped AST.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from sattlint.analyzers.cyclomatic_complexity import analyze_cyclomatic_complexity
from sattlint.parser_api import BasePicture
from tests.helpers.project_loading import load_target_project

FIXTURE = (
    Path(__file__).resolve().parent.parent / "fixtures" / "corpus" / "semantic" / "analyzer" / "TestStringsDisplay.s"
)


def _loaded_base_picture() -> BasePicture:
    base_picture, _graph = load_target_project(FIXTURE)
    return base_picture


def test_loaded_collections_are_tuples() -> None:
    base_picture = _loaded_base_picture()
    modulecode = base_picture.modulecode
    assert modulecode is not None

    equationblocks = modulecode.equationblocks
    assert equationblocks is not None
    equation = cast(object, equationblocks[0])
    assert isinstance(getattr(equation, "code", None), tuple)


def test_cyclomatic_complexity_counts_project_loaded_equation_blocks() -> None:
    base_picture = _loaded_base_picture()

    report = analyze_cyclomatic_complexity(base_picture, equation_block_threshold=0)

    equations = {issue.data["equation"] for issue in report.issues if issue.data}
    assert equations == {"Start_SetStrings", "Counter", "Start_Init"}
