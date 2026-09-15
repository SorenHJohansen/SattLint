"""Semantic rule-engine data models (``SemanticRule``, ``SemanticIssue``, groups)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SemanticRule:
    id: str
    source: str
    description: str
    explanation: str | None = None
    suggestion: str | None = None
    acceptance_tests: tuple[str, ...] | None = None
    corpus_cases: tuple[str, ...] = ()
    mutation_applicability: str | None = None
    suppression_modes: tuple[str, ...] | None = None
    incremental_safe: bool | None = None
    name: str = ""
    example: str | None = None


@dataclass(frozen=True)
class SemanticIssue:
    rule: SemanticRule
    message: str
    module_path: list[str] | None = None
    data: dict[str, Any] = field(default_factory=lambda: {})
    source_kind: str | None = None


@dataclass(frozen=True)
class SemanticRuleGroup:
    source: str
    rules: tuple[SemanticRule, ...]


__all__ = [
    "SemanticIssue",
    "SemanticRule",
    "SemanticRuleGroup",
]
