"""Datatype-field analysis (opt-in split from the ``variables`` analyzer).

The three datatype-field issue kinds live in the ``variables`` analyzer but are
only collected when they are explicitly selected. This module exposes them as a
dedicated, opt-in ``datatype-fields`` analyzer: every run scans the reverse
consumers of the analyzed target, so it is more expensive than a plain
``variables`` run and must be chosen explicitly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from ...reporting.variables_report import DATATYPE_FIELD_ANALYSIS_KINDS, VariablesReport
from ..framework import AnalysisContext
from ..variables import analyze_variables as _analyze_variables_impl

__all__ = ["analyze_datatype_fields"]


def analyze_datatype_fields(
    base_picture: BasePicture,
    analysis_context: AnalysisContext | None = None,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
    config: dict[str, Any] | None = None,
    status_update_fn: Callable[[str], None] | None = None,
) -> VariablesReport:
    """Analyze datatype fields: unused, read-only, and never-read fields.

    Delegates to :func:`analyze_variables` with the three datatype-field kinds
    explicitly selected. Reverse-consumer loading is driven by
    ``analyzed_target_is_library`` exactly like the ``variables`` analyzer.
    """
    return _analyze_variables_impl(
        base_picture,
        analysis_context=analysis_context,
        debug=debug,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
        include_dependency_moduletype_usage=None,
        selected_issue_kinds=frozenset(DATATYPE_FIELD_ANALYSIS_KINDS),
        config=config,
        status_update_fn=status_update_fn,
    )
