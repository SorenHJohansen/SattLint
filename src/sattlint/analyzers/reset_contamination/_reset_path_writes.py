"""Write-tracking helpers for reset contamination path collection."""

from __future__ import annotations

from typing import Any, cast

from sattline_parser.models.ast_model import Variable

from ...grammar import constants as const
from ..sattline_builtins import get_function_signature
from ._reset_path_state import WriteKey, WriteMap


def _path_covers_write(reset_writes: WriteMap, key: WriteKey) -> bool:
    var_key, _field_key = key
    return key in reset_writes or (var_key, "") in reset_writes


def _record_mode_write(target: Any, env: dict[str, Variable], state: Any) -> None:
    bucket = state.reset_writes if state.reset_state == "reset" else state.run_writes
    _record_write(target, env, bucket)


def _record_mode_function_call_writes(
    fn_name: str,
    args: list[Any],
    env: dict[str, Variable],
    state: Any,
) -> None:
    bucket = state.reset_writes if state.reset_state == "reset" else state.run_writes
    _record_function_call_writes(fn_name, args, env, bucket)


def _split_var_ref(full_ref: str) -> tuple[str, str]:
    if not full_ref:
        return "", ""
    if "." not in full_ref:
        return full_ref, ""
    base, field_path = full_ref.split(".", 1)
    return base, field_path


def _record_write(target: Any, env: dict[str, Variable], out: WriteMap) -> None:
    if not isinstance(target, dict) or const.KEY_VAR_NAME not in target:
        return
    target_map = cast(dict[str, object], target)
    full_ref = target_map[const.KEY_VAR_NAME]
    if not isinstance(full_ref, str) or not full_ref:
        return
    base, field_path = _split_var_ref(full_ref)
    if not base:
        return
    var = env.get(base.casefold())
    if var is None:
        return
    field_path = field_path or ""
    out[(var.name.casefold(), field_path.casefold())] = (var, field_path)


def _record_function_call_writes(
    fn_name: str,
    args: list[Any],
    env: dict[str, Variable],
    out: WriteMap,
) -> None:
    sig = get_function_signature(fn_name)
    if sig is None:
        return
    for idx, arg in enumerate(args):
        if idx >= len(sig.parameters):
            break
        direction = sig.parameters[idx].direction
        if direction not in ("out", "inout"):
            continue
        if isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
            _record_write(arg, env, out)


path_covers_write = _path_covers_write
record_mode_write = _record_mode_write
record_mode_function_call_writes = _record_mode_function_call_writes
split_var_ref = _split_var_ref
record_write = _record_write
record_function_call_writes = _record_function_call_writes
