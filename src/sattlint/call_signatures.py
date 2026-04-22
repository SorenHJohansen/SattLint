from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .analyzers.sattline_builtins import get_function_signature

_STATUS_PARAMETER_NAMES = {"status", "debugstatus"}


@dataclass(frozen=True, slots=True)
class CallParameterSignature:
    name: str
    datatype: str
    direction: Literal["in", "in var", "out", "inout"]
    sorting: str
    ownership: str

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
    name: str
    call_type: Literal["Function", "Procedure"]
    return_type: str | None
    parameters: tuple[CallParameterSignature, ...]
    source: str = "builtin"

    @property
    def status_parameters(self) -> tuple[CallParameterSignature, ...]:
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

    return CallSignature(
        name=builtin.name,
        call_type=builtin.type,
        return_type=builtin.return_type,
        parameters=tuple(
            CallParameterSignature(
                name=parameter.name,
                datatype=parameter.datatype,
                direction=parameter.direction,
                sorting=parameter.sorting,
                ownership=parameter.ownership,
            )
            for parameter in builtin.parameters
        ),
    )


__all__ = [
    "CallParameterSignature",
    "CallSignature",
    "CallSignatureOccurrence",
    "resolve_call_signature",
]
