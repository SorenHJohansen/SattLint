"""Shared types for SattLine builtin metadata."""

from dataclasses import dataclass
from typing import Literal


@dataclass
class Parameter:
    name: str
    datatype: str
    direction: Literal["in", "in var", "out", "inout"]
    sorting: Literal["RS", "WS", "RS/WS", "NoS"]
    ownership: Literal["RO", "WO", "RO/WO", "NoO"]


@dataclass
class BuiltinFunction:
    name: str
    type: Literal["Function", "Procedure"]
    return_type: str | None
    parameters: list[Parameter]
    precision_scangroup: bool


__all__ = ["BuiltinFunction", "Parameter"]
