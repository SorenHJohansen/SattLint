"""Shared selection and execution helpers for registry-backed analyzers."""

from __future__ import annotations

from .._registry_dispatch import (
    get_cli_dispatch_analyzers,
    get_lsp_projection_analyzers,
    get_registry_analyzer_spec,
    get_semantic_contributor_specs,
    run_registry_analyzer,
)

__all__ = [
    "get_cli_dispatch_analyzers",
    "get_lsp_projection_analyzers",
    "get_registry_analyzer_spec",
    "get_semantic_contributor_specs",
    "run_registry_analyzer",
]
