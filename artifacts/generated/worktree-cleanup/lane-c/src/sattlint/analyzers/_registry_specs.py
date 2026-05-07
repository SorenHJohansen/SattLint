"""Typed spec-facing registry exports for future registry split work."""

from __future__ import annotations

from .framework import AnalyzerSpec
from .registry import AnalyzerCatalog, AnalyzerMetadata, RuleMetadata

__all__ = [
    "AnalyzerCatalog",
    "AnalyzerMetadata",
    "AnalyzerSpec",
    "RuleMetadata",
]
