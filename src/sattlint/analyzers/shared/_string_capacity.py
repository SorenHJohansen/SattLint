"""String datatype capacities resolved from the project configuration.

The capacities are a property of the SattLine project, not of the analyzer:
callers receive the resolved :class:`StringCapacities` and ask this module for
the capacity of one datatype. Nothing here carries a capacity table, so a
configured value can never be shadowed by a built-in default.
"""

from __future__ import annotations

from sattlint.parser_api import ScalarDatatype

from ...config.string_capacities import StringCapacities

STRING_DATATYPES: frozenset[ScalarDatatype] = frozenset(
    {
        ScalarDatatype.IDENTSTRING,
        ScalarDatatype.TAGSTRING,
        ScalarDatatype.STRING,
        ScalarDatatype.LINESTRING,
        ScalarDatatype.MAXSTRING,
    }
)


def is_string_datatype(datatype: ScalarDatatype | str | None) -> bool:
    """Whether ``datatype`` is one of the five capacity-bounded string types."""
    return isinstance(datatype, ScalarDatatype) and datatype in STRING_DATATYPES


def capacity_for_datatype(capacities: StringCapacities, datatype: ScalarDatatype | str | None) -> int | None:
    """Return the configured capacity of a string datatype, or ``None`` for other types."""
    if not isinstance(datatype, ScalarDatatype):
        return None
    if datatype is ScalarDatatype.IDENTSTRING:
        return capacities.identstring
    if datatype is ScalarDatatype.TAGSTRING:
        return capacities.tagstring
    if datatype is ScalarDatatype.STRING:
        return capacities.string
    if datatype is ScalarDatatype.LINESTRING:
        return capacities.linestring
    if datatype is ScalarDatatype.MAXSTRING:
        return capacities.maxstring
    return None


__all__ = ["STRING_DATATYPES", "capacity_for_datatype", "is_string_datatype"]
