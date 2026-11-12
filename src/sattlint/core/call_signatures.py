from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sattlint.parser_api import BuiltinFunction, BuiltinParameter, get_function_signature

_STATUS_PARAMETER_NAMES = {"status", "debugstatus"}


@dataclass(frozen=True, slots=True)
class CallParameter:
    """Derived view over one parser ``BuiltinParameter``."""

    builtin: BuiltinParameter

    @property
    def name(self) -> str:
        return self.builtin.name

    @property
    def datatype(self) -> str:
        return self.builtin.datatype

    @property
    def direction(self) -> Literal["in", "in var", "out", "inout"]:
        return self.builtin.direction

    @property
    def sorting(self) -> str:
        return self.builtin.sorting

    @property
    def ownership(self) -> str:
        return self.builtin.ownership

    @property
    def channel_kind(self) -> str | None:
        name_key = self.name.casefold()
        datatype_key = self.datatype.casefold()
        if name_key in _STATUS_PARAMETER_NAMES or name_key.endswith("status"):
            return "status"
        if name_key == "asyncoperation" or datatype_key == "asyncoperation":
            return "async-operation"
        return None

    @property
    def is_status_channel(self) -> bool:
        return self.channel_kind is not None and self.direction in {"out", "inout"}


@dataclass(frozen=True, slots=True)
class CallSignature:
    """Derived view over one parser ``BuiltinFunction``."""

    builtin: BuiltinFunction
    source: str = "builtin"

    @property
    def name(self) -> str:
        return self.builtin.name

    @property
    def call_type(self) -> Literal["Function", "Procedure"]:
        return "Function" if self.builtin.kind == "function" else "Procedure"

    @property
    def return_type(self) -> str | None:
        return self.builtin.return_type

    @property
    def parameters(self) -> tuple[CallParameter, ...]:
        return tuple(CallParameter(parameter) for parameter in self.builtin.parameters)

    @property
    def status_parameters(self) -> tuple[CallParameter, ...]:
        return tuple(parameter for parameter in self.parameters if parameter.is_status_channel)


@dataclass(frozen=True, slots=True)
class CallSignatureOccurrence:
    name: str
    call_kind: str
    module_path: tuple[str, ...]
    source_file: str | None
    source_library: str | None
    signature: CallSignature


def resolve_call_signature(name: str | None) -> CallSignature | None:
    if not name:
        return None
    builtin = get_function_signature(name)
    if builtin is None:
        return None
    return CallSignature(builtin=builtin)


__all__ = [
    "CallParameter",
    "CallSignature",
    "CallSignatureOccurrence",
    "resolve_call_signature",
]
