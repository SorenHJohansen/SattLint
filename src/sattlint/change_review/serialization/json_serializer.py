"""JSON serialization of a ``ChangeReview``.

The JSON payload is a direct, stable projection of the canonical review model:
metadata, changes (each with direct semantic context and containing/related
blocks), the selected equation blocks/sequences with complete source and
reasons, variable definitions with real source, and size statistics.
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any, cast

from ..facts import BlockContext, ChangeSemanticContext, SymbolFact
from ..review import ChangeReview, ReviewContextBlock


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return str(value.value if hasattr(value, "value") else value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple | list):
        return [_jsonable(item) for item in cast(tuple[Any, ...] | list[Any], value)]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in cast(dict[Any, Any], value).items()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in dataclasses.fields(value) if field.repr}
    return str(value)


def _location_dict(location: Any) -> dict[str, Any]:
    if location is None:
        return {}
    return {
        "file": getattr(location, "file", None),
        "line": getattr(location, "line", None),
        "column": getattr(location, "column", None),
    }


def _symbol_fact_dict(fact: SymbolFact) -> dict[str, Any]:
    return {
        "symbol": fact.symbol,
        "name": fact.name,
        "role": fact.role,
        "reason": fact.reason,
        "kind": fact.kind,
        "datatype": fact.datatype,
        "declared_by": fact.declared_by,
        "written_by": list(fact.written_by),
        "read_by": list(fact.read_by),
        "declaration_source": fact.declaration_source,
        "official_definition_source": fact.official_definition_source,
        "draft_definition_source": fact.draft_definition_source,
    }


def _block_context_dict(block: BlockContext) -> dict[str, Any]:
    return {
        "symbol": block.symbol,
        "role": block.role,
        "reasons": list(block.reasons),
    }


def _semantic_context_dict(context: ChangeSemanticContext) -> dict[str, Any]:
    return {
        "direct_reads": [fact.symbol for fact in context.reads],
        "direct_writes": [fact.symbol for fact in context.produces],
        "callees": [fact.symbol for fact in context.callees],
        "containing_object": context.containing_object,
        "sequence_name": context.sequence_name,
        "previous_state": context.previous_state,
        "next_state": context.next_state,
        "containing_block": (
            _block_context_dict(context.containing_block) if context.containing_block is not None else None
        ),
        "related_blocks": [_block_context_dict(block) for block in context.related_blocks],
    }


def _context_block_dict(block: ReviewContextBlock) -> dict[str, Any]:
    return {
        "symbol": block.symbol,
        "module_path": list(block.module_path),
        "kind": block.kind,
        "name": block.name,
        "role": block.role,
        "reasons": list(block.reasons),
        "reads": list(block.reads),
        "writes": list(block.writes),
        "file": block.file,
        "line_start": block.line_start,
        "line_end": block.line_end,
        "official_source": block.official_source,
        "draft_source": block.draft_source,
        "source": block.source,
        "sequence_name": block.sequence_name,
        "previous_state": block.previous_state,
        "next_state": block.next_state,
    }


def review_to_dict(review: ChangeReview) -> dict[str, Any]:
    """Project the canonical review model onto the stable JSON schema."""
    return {
        "metadata": {
            "project": review.metadata.project,
            "official_revision": review.metadata.official_revision,
            "draft_revision": review.metadata.draft_revision,
            "generated_at": review.metadata.generated_at,
        },
        "size_stats": {
            "total_project_source_size": review.size_stats.total_project_source_size,
            "selected_source_size": review.size_stats.selected_source_size,
            "metadata_size": review.size_stats.metadata_size,
            "artifact_size": review.size_stats.artifact_size,
            "source_reduction_percent": review.size_stats.source_reduction_percent,
            "semantic_change_count": review.size_stats.semantic_change_count,
            "relevant_block_count": review.size_stats.relevant_block_count,
            "relevant_variable_count": review.size_stats.relevant_variable_count,
            "contextual_block_count": review.size_stats.contextual_block_count,
        },
        "changes": [
            {
                "symbol": change.symbol,
                "module_path": list(change.module_path),
                "kind": change.kind.value,
                "detail": change.detail,
                "official": _jsonable(change.official),
                "draft": _jsonable(change.draft),
                "location": _location_dict(change.location),
                "draft_location": _location_dict(change.draft_location),
                "containing_symbol": change.containing_symbol,
                "statement_context": change.statement_context,
                "semantic_context": (
                    _semantic_context_dict(change.semantic_context) if change.semantic_context is not None else None
                ),
            }
            for change in review.changes
        ],
        "context": [_context_block_dict(block) for block in review.context],
        "variable_definitions": [_symbol_fact_dict(fact) for fact in review.variable_definitions],
    }


def review_to_json(review: ChangeReview) -> str:
    """Serialize the review as indented JSON text."""
    return json.dumps(review_to_dict(review), indent=2, ensure_ascii=False)
