"""Shared pure helpers for variable analysis."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sattline_parser.models.ast_model import Simple_DataType, Variable

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


def is_const_candidate(self: VariablesAnalyzer, variable: Variable) -> bool:
    return (
        isinstance(variable.datatype, Simple_DataType)
        and variable.datatype is not Simple_DataType.DURATION
        and not bool(variable.opsave)
        and not bool(variable.secure)
    )


def same_origin_file_stem(origin_file: str | None, root_origin: str | None) -> bool:
    if not origin_file:
        return True
    if not root_origin:
        return False
    try:
        return Path(origin_file).stem.casefold() == Path(root_origin).stem.casefold()
    except Exception:
        return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()


__all__ = ["is_const_candidate", "same_origin_file_stem"]
