"""Builtin structured datatype catalog for system and library datatypes."""

from __future__ import annotations

from sattline_parser.models.ast_model import Simple_DataType

from ._builtin_datatypes_part1 import BUILTIN_RECORD_SPECS_PART1
from ._builtin_datatypes_part2 import BUILTIN_RECORD_SPECS_PART2
from ._builtin_datatypes_part3 import BUILTIN_RECORD_SPECS_PART3
from ._builtin_datatypes_shared import OPAQUE_BUILTIN_RECORD_NAMES as _OPAQUE_BUILTIN_RECORD_NAMES
from ._builtin_datatypes_shared import BuiltinFieldSpec

BUILTIN_RECORD_SPECS: dict[str, tuple[BuiltinFieldSpec, ...]] = {
    **BUILTIN_RECORD_SPECS_PART1,
    **BUILTIN_RECORD_SPECS_PART2,
    **BUILTIN_RECORD_SPECS_PART3,
}

for _opaque_name in _OPAQUE_BUILTIN_RECORD_NAMES:
    BUILTIN_RECORD_SPECS[_opaque_name] = ()


BUILTIN_DECLARED_DATATYPE_NAMES = tuple(
    dict.fromkeys([datatype.value for datatype in Simple_DataType] + list(BUILTIN_RECORD_SPECS))
)
