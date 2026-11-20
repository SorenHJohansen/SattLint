from __future__ import annotations

from sattlint.parser_api import ScalarDatatype, Variable

from ...resolution.type_graph import FieldDef, TypeGraph, resolve_record


def _field_def(
    type_graph: TypeGraph,
    record_type: str,
    field_name: str,
    library: str | None,
) -> tuple[FieldDef, str | None] | None:
    """Resolve one field and report the library that declares the record.

    The returned library becomes the lookup scope for the field's own datatype,
    because a field's type belongs to the library that declares the record. ICF
    validation has no warning channel per entry, so an undecidable record name
    leaves the field unresolved.
    """
    record = resolve_record(type_graph, record_type, library=library)
    if record is None:
        return None
    field_def = record.fields_by_key.get(field_name.casefold())
    if field_def is None:
        return None
    return field_def, record.library


def resolve_leaf_datatype(
    type_graph: TypeGraph,
    root_var: Variable,
    field_segments: list[str],
    *,
    library: str | None = None,
) -> ScalarDatatype | str | None:
    """Walk a reference down to its leaf datatype.

    ``library`` is the library whose module the ICF entry addresses. An
    undecidable record name has no known layout, so the leaf stays unresolved.
    """
    current_type: ScalarDatatype | str = root_var.datatype
    field_library = library
    for field in field_segments:
        if isinstance(current_type, ScalarDatatype):
            return None
        resolved = _field_def(type_graph, str(current_type), field, field_library)
        if resolved is None:
            return None
        field_def, field_library = resolved
        current_type = field_def.datatype
    return current_type


def resolve_record_datatype(
    type_graph: TypeGraph,
    root_datatype: ScalarDatatype | str | None,
    field_segments: list[str],
    *,
    library: str | None = None,
) -> str | None:
    """Walk a reference down to the record that contains its leaf field."""
    current_type: ScalarDatatype | str | None = root_datatype
    field_library = library
    for field in field_segments:
        if isinstance(current_type, ScalarDatatype):
            return None
        if current_type is None:
            return None
        resolved = _field_def(type_graph, str(current_type), field, field_library)
        if resolved is None:
            return None
        field_def, field_library = resolved
        current_type = field_def.datatype

    if isinstance(current_type, ScalarDatatype) or current_type is None:
        return None
    return str(current_type)
