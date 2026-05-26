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
        and variable.datatype is not Simple_DataType.TIME
        and variable.datatype is not Simple_DataType.DURATION
        and not bool(variable.opsave)
        and not bool(variable.secure)
    )


def external_mapping_usage(moduletype_name: str, target_name: str | None) -> tuple[bool, bool] | None:
    mt_key = moduletype_name.casefold()
    target_key = target_name.casefold() if target_name is not None else ""

    if mt_key == "mmsreadwrite":
        if target_key == "inputvariable":
            return (True, False)
        if target_key == "outputvariable":
            return (False, True)

    if mt_key.startswith("mmsread") and target_key in {"localvariable", "outputvariable", "error", "mmsreaderror"}:
        return (False, True)

    if mt_key.startswith("mmswrite") and target_key in {"localvariable", "writedata", "inputvariable"}:
        return (True, False)

    return None


def same_origin_file_stem(origin_file: str | None, root_origin: str | None) -> bool:
    if not origin_file:
        return True
    if not root_origin:
        return False
    try:
        return Path(origin_file).stem.casefold() == Path(root_origin).stem.casefold()
    except Exception:
        return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()


__all__ = ["external_mapping_usage", "is_const_candidate", "same_origin_file_stem"]
