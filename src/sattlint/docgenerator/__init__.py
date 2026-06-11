"""Document generation helpers for SattLine outputs."""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from ..analyzers.framework import Issue
from .analyzer_ref import (
    build_analyzer_reference_entry,
    build_full_analyzer_reference,
    get_example_fixtures_for_analyzer,
    render_analyzer_reference_markdown,
    save_analyzer_reference_json,
    save_analyzer_reference_markdown,
)


class GenerateDocxFn(Protocol):
    def __call__(
        self,
        root: Any,
        out_path: str | Path,
        *,
        documentation_config: dict[str, Any] | None = None,
        unavailable_libraries: set[str] | None = None,
        upgrade_issues: Sequence[Issue] | None = None,
    ) -> None: ...


generate_docx = cast(GenerateDocxFn, importlib.import_module("sattlint.docgenerator.docgen").generate_docx)

__all__ = [
    "build_analyzer_reference_entry",
    "build_full_analyzer_reference",
    "generate_docx",
    "get_example_fixtures_for_analyzer",
    "render_analyzer_reference_markdown",
    "save_analyzer_reference_json",
    "save_analyzer_reference_markdown",
]
