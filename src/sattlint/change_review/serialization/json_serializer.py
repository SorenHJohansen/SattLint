"""JSON serialization of a ``ChangeReview``.

The JSON payload is a direct, stable projection of the canonical review model:
metadata, changes (each with its semantic context), relevant symbols with their
facts and inclusion reasons, selected context, and size statistics. The same
serializer backs both the file artifact and any machine consumer.
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from pathlib import Path
from typing import Any, cast

from ..facts import ChangeSemanticContext, SymbolFact
from ..review import ChangeReview


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
        "priority": fact.priority,
        "kind": fact.kind,
        "datatype": fact.datatype,
        "defined_by": fact.defined_by,
        "produced_by": list(fact.produced_by),
        "consumed_by": list(fact.consumed_by),
        "containing_object": fact.containing_object,
    }


def _semantic_context_dict(context: ChangeSemanticContext) -> dict[str, Any]:
    return {
        "reads": [_symbol_fact_dict(fact) for fact in context.reads],
        "produces": [_symbol_fact_dict(fact) for fact in context.produces],
        "producers": [_symbol_fact_dict(fact) for fact in context.producers],
        "consumers": [_symbol_fact_dict(fact) for fact in context.consumers],
        "callers": [_symbol_fact_dict(fact) for fact in context.callers],
        "callees": [_symbol_fact_dict(fact) for fact in context.callees],
        "containing_object": context.containing_object,
        "sequence_name": context.sequence_name,
        "previous_state": context.previous_state,
        "next_state": context.next_state,
        "containing_state": context.containing_state,
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
            "selected_context_size": review.size_stats.selected_context_size,
            "reduction_percent": review.size_stats.reduction_percent,
            "semantic_change_count": review.size_stats.semantic_change_count,
            "relevant_symbol_count": review.size_stats.relevant_symbol_count,
            "contextual_symbol_count": review.size_stats.contextual_symbol_count,
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
        "relevant_symbols": [_symbol_fact_dict(fact) for fact in review.relevant_symbols],
        "context": [
            {
                "symbol": block.symbol,
                "role": block.role,
                "reason": block.reason,
                "file": block.file,
                "line_start": block.line_start,
                "line_end": block.line_end,
                "official_source": block.official_source,
                "draft_source": block.draft_source,
                "source": block.source,
            }
            for block in review.context
        ],
    }


def review_to_json(review: ChangeReview) -> str:
    """Serialize the review as indented JSON text."""
    return json.dumps(review_to_dict(review), indent=2, ensure_ascii=False)
