"""SattLine builtin function signatures and metadata.

Abbreviations in this list

PS       allowed in precision scangroup

Type of direction
in       input of a variable, a literal value or an expression
in var   input of a variable
out      output of a variable
inout    in- and output of a variable

Sorting
RS       labelled for reading and sorting
WS       labelled for writing and sorting
RS/WS    labelled for reading, writing and sorting
NoS      labelled for no sorting

Ownership
RO       labelled for reading and ownership
WO       labelled for writing and ownership
RO/WO    labelled for reading, writing and ownership
NoO      labelled as no ownership
"""

from ._sattline_builtin_types import BuiltinFunction, Parameter
from ._sattline_builtins_registry import SATTLINE_BUILTINS

__all__ = [
    "SATTLINE_BUILTINS",
    "BuiltinFunction",
    "Parameter",
    "get_function_signature",
    "is_builtin_function",
]


def is_builtin_function(name: str) -> bool:
    """Check if a function name is a built-in."""
    return name.lower() in SATTLINE_BUILTINS


def get_function_signature(name: str) -> BuiltinFunction | None:
    """Get function signature for validation."""
    return SATTLINE_BUILTINS.get(name.lower())
