from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SemanticRule:
    id: str
    source: str
    category: str
    severity: str
    applies_to: str
    description: str
    confidence: str = "likely"
    explanation: str | None = None
    suggestion: str | None = None
    acceptance_tests: tuple[str, ...] | None = None
    corpus_cases: tuple[str, ...] = ()
    mutation_applicability: str | None = None
    suppression_modes: tuple[str, ...] | None = None
    incremental_safe: bool | None = None


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


CATEGORY_ORDER: tuple[str, ...] = (
    "variable-lifecycle",
    "interface-contracts",
    "module-structure",
    "control-flow",
    "engineering-spec",
)

CATEGORY_LABELS: dict[str, str] = {
    "variable-lifecycle": "Variable lifecycle",
    "interface-contracts": "Interface contracts",
    "module-structure": "Module structure",
    "control-flow": "Control flow",
    "engineering-spec": "Engineering spec",
}


__all__ = [
    "CATEGORY_LABELS",
    "CATEGORY_ORDER",
    "SemanticIssue",
    "SemanticRule",
    "SemanticRuleGroup",
]
