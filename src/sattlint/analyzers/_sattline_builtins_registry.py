"""Aggregated SattLine builtin registry."""

from ._sattline_builtin_types import BuiltinFunction
from ._sattline_builtins_part1 import SATTLINE_BUILTINS_PART1
from ._sattline_builtins_part2 import SATTLINE_BUILTINS_PART2
from ._sattline_builtins_part3 import SATTLINE_BUILTINS_PART3
from ._sattline_builtins_part4 import SATTLINE_BUILTINS_PART4
from ._sattline_builtins_part5 import SATTLINE_BUILTINS_PART5

SATTLINE_BUILTINS: dict[str, BuiltinFunction] = {
    **SATTLINE_BUILTINS_PART1,
    **SATTLINE_BUILTINS_PART2,
    **SATTLINE_BUILTINS_PART3,
    **SATTLINE_BUILTINS_PART4,
    **SATTLINE_BUILTINS_PART5,
}

__all__ = ["SATTLINE_BUILTINS"]
