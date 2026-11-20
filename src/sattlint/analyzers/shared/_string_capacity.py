"""String datatype capacities shared by string inference and mapping validation."""

from __future__ import annotations

from sattlint.parser_api import ScalarDatatype

STRING_CAPACITIES: dict[ScalarDatatype, int] = {
    ScalarDatatype.IDENTSTRING: 15,
    ScalarDatatype.TAGSTRING: 30,
    ScalarDatatype.STRING: 40,
    ScalarDatatype.LINESTRING: 80,
    ScalarDatatype.MAXSTRING: 140,
}


def string_capacity_for_datatype(datatype: ScalarDatatype | str | None) -> int | None:
    """Return the fixed capacity of a string datatype, or ``None`` for other types."""
    if isinstance(datatype, ScalarDatatype):
        return STRING_CAPACITIES.get(datatype)
    return None
