"""Shared pure helpers for variable analysis."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from sattline_parser.models.ast_model import Simple_DataType, Variable

from ...casefolding import casefold_key

if TYPE_CHECKING:
    from ..variables import VariablesAnalyzer


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
    except Exception:  # noqa: BLE001
        return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()


def matches_root_origin(
    origin_file: str | None,
    root_origin: str | None,
    *,
    analyzed_target_is_library: bool = False,
    origin_lib: str | None = None,
    root_origin_lib: str | None = None,
) -> bool:
    if root_origin_lib and origin_lib and not origin_file:
        # Merged dependency ASTs can drop origin_file while still preserving origin_lib.
        # Treat foreign-library definitions as out of scope for both program and library targets.
        return origin_lib.casefold() == root_origin_lib.casefold()

    if analyzed_target_is_library and root_origin_lib and origin_lib:
        try:
            root_stem = Path(root_origin).stem.casefold() if root_origin else None
        except Exception:  # noqa: BLE001
            root_stem = root_origin.rsplit(".", 1)[0].casefold() if root_origin else None

        # Only treat the library name as authoritative when it identifies the root file itself.
        if root_stem and root_origin_lib.casefold() == root_stem:
            return origin_lib.casefold() == root_origin_lib.casefold()

    if not origin_file:
        return True
    return same_origin_file_stem(origin_file, root_origin)


def merge_variable_env(
    env: dict[str, Variable],
    variables: list[Variable] | None,
) -> dict[str, Variable]:
    merged = dict(env)
    for variable in variables or []:
        merged[casefold_key(variable.name)] = variable
    return merged


class VariablesConstMixin:
    def _is_const_candidate(self: Any, variable: Variable) -> bool:
        return is_const_candidate(self, variable)


__all__ = [
    "VariablesConstMixin",
    "external_mapping_usage",
    "is_const_candidate",
    "matches_root_origin",
    "merge_variable_env",
    "same_origin_file_stem",
]
