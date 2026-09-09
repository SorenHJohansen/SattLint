"""Stable dispatch facade for registry-backed analysis entrypoints.

Non-analyzer layers should import registry-backed analyzer selection and
execution through this module rather than depending on analyzer-internal
dispatch helpers directly.
"""

from __future__ import annotations

from ._registry_dispatch import (
    collect_lsp_report_issues,
    get_cli_dispatch_analyzers,
    get_lsp_projection_analyzers,
    get_registry_analyzer_spec,
    get_semantic_contributor_specs,
    run_registry_analyzer,
    run_variables_registry_report,
)

__all__ = [
    "collect_lsp_report_issues",
    "get_cli_dispatch_analyzers",
    "get_lsp_projection_analyzers",
    "get_registry_analyzer_spec",
    "get_semantic_contributor_specs",
    "run_registry_analyzer",
    "run_variables_registry_report",
]
