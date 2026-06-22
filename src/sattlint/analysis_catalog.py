"""Stable facade for registry-backed analyzer catalog and selection helpers.

Non-analyzer layers should import analyzer catalog metadata and selection
through this module rather than depending on ``sattlint.analyzers.registry``
directly.
"""

from __future__ import annotations

from .analyzers import registry as analyzer_registry
from .analyzers.framework import AnalyzerSpec
from .analyzers.registry import (
    AnalyzerCatalog,
    AnalyzerMetadata,
    RuleMetadata,
)


def canonicalize_analyzer_key(key: str) -> str:
    return analyzer_registry.canonicalize_analyzer_key(key)


def canonicalize_analyzer_keys(keys: tuple[str, ...] | list[str] | set[str]) -> tuple[str, ...]:
    return analyzer_registry.canonicalize_analyzer_keys(keys)


def get_actual_cli_analyzer_keys() -> tuple[str, ...]:
    return analyzer_registry.get_actual_cli_analyzer_keys()


def get_actual_lsp_analyzer_keys() -> tuple[str, ...]:
    return analyzer_registry.get_actual_lsp_analyzer_keys()


def get_declared_cli_analyzer_keys() -> tuple[str, ...]:
    return analyzer_registry.get_declared_cli_analyzer_keys()


def get_declared_lsp_analyzer_keys() -> tuple[str, ...]:
    return analyzer_registry.get_declared_lsp_analyzer_keys()


def get_default_analyzer_catalog() -> AnalyzerCatalog:
    return analyzer_registry.get_default_analyzer_catalog()


def get_default_cli_analyzers() -> list[AnalyzerSpec]:
    return analyzer_registry.get_default_cli_analyzers()


def get_selectable_analyzers() -> list[AnalyzerSpec]:
    return analyzer_registry.get_selectable_analyzers()


__all__ = [
    "AnalyzerCatalog",
    "AnalyzerMetadata",
    "RuleMetadata",
    "canonicalize_analyzer_key",
    "canonicalize_analyzer_keys",
    "get_actual_cli_analyzer_keys",
    "get_actual_lsp_analyzer_keys",
    "get_declared_cli_analyzer_keys",
    "get_declared_lsp_analyzer_keys",
    "get_default_analyzer_catalog",
    "get_default_cli_analyzers",
    "get_selectable_analyzers",
]
