from __future__ import annotations

from sattline_parser.models.ast_model import Simple_DataType, Variable

from ..resolution.type_graph import TypeGraph


def resolve_leaf_datatype(
    type_graph: TypeGraph,
    root_var: Variable,
    field_segments: list[str],
) -> Simple_DataType | str | None:
    current_type: Simple_DataType | str | None = root_var.datatype
    for field in field_segments:
        if isinstance(current_type, Simple_DataType):
            return None
        if current_type is None:
            return None
        field_def = type_graph.field(str(current_type), field)
        if field_def is None:
            return None
        current_type = field_def.datatype
    return current_type


def resolve_record_datatype(
    type_graph: TypeGraph,
    root_datatype: Simple_DataType | str | None,
    field_segments: list[str],
) -> str | None:
    current_type: Simple_DataType | str | None = root_datatype
    for field in field_segments:
        if isinstance(current_type, Simple_DataType):
            return None
        if current_type is None:
            return None
        field_def = type_graph.field(str(current_type), field)
        if field_def is None:
            return None
        current_type = field_def.datatype

    if isinstance(current_type, Simple_DataType) or current_type is None:
        return None
    return str(current_type)
