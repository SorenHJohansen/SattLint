"""Reset contamination detection for SattLine modules.

A variable is 'reset contaminated' when it is written during a run condition
(i.e. when a sequence's .Reset flag is False) but never reset when .Reset is
True. This means the variable will retain stale state across equipment resets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Variable,
)
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution.common import path_startswith_casefold
from .sattline_builtins import get_function_signature


def detect_reset_contamination(
    bp: BasePicture,
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None = None,
) -> None:
    """Scan all SingleModules and ModuleTypeDefs for reset-contaminated variables.

    Appends any found issues directly to *issues*.
    """
    root_path = [bp.header.name]
    root_origin = getattr(bp, "origin_file", None)

    for mod in bp.submodules or []:
        _collect_from_module(mod, root_path, issues, limit_to_module_path)

    if limit_to_module_path is not None:
        return

    for mt in bp.moduletype_defs or []:
        if not _is_from_root_origin(getattr(mt, "origin_file", None), root_origin):
            continue
        td_path = [bp.header.name, f"TypeDef:{mt.name}"]
        _check_for_typedef(mt, td_path, issues)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_from_root_origin(origin_file: str | None, root_origin: str | None) -> bool:
    if not origin_file:
        return True
    if not root_origin:
        return False
    try:
        return Path(origin_file).stem.lower() == Path(root_origin).stem.lower()
    except Exception:
        return (
            origin_file.rsplit(".", 1)[0].lower()
            == root_origin.rsplit(".", 1)[0].lower()
        )


def _should_analyze_path(path: list[str], limit_to_module_path: list[str] | None) -> bool:
    if limit_to_module_path is None:
        return True
    return (
        path_startswith_casefold(limit_to_module_path, path)
        or path_startswith_casefold(path, limit_to_module_path)
    )


def _collect_from_module(
    mod: SingleModule | FrameModule | ModuleTypeInstance,
    path: list[str],
    issues: list[VariableIssue],
    limit_to_module_path: list[str] | None,
) -> None:
    if isinstance(mod, SingleModule):
        mod_path = path + [mod.header.name]
        if _should_analyze_path(mod_path, limit_to_module_path):
            _check_for_single(mod, mod_path, issues)
        for ch in mod.submodules or []:
            _collect_from_module(ch, mod_path, issues, limit_to_module_path)
    elif isinstance(mod, FrameModule):
        mod_path = path + [mod.header.name]
        for ch in mod.submodules or []:
            _collect_from_module(ch, mod_path, issues, limit_to_module_path)


def _build_local_env(
    moduleparameters: list[Variable] | None,
    localvariables: list[Variable] | None,
) -> dict[str, Variable]:
    env: dict[str, Variable] = {}
    for v in moduleparameters or []:
        env[v.name.casefold()] = v
    for v in localvariables or []:
        env[v.name.casefold()] = v
    return env


def _check_for_single(
    mod: SingleModule, path: list[str], issues: list[VariableIssue]
) -> None:
    if mod.modulecode is None:
        return
    env = _build_local_env(mod.moduleparameters, mod.localvariables)
    _check_for_modulecode(mod.modulecode, env, path, issues)


def _check_for_typedef(
    mt: ModuleTypeDef, path: list[str], issues: list[VariableIssue]
) -> None:
    if mt.modulecode is None:
        return
    env = _build_local_env(mt.moduleparameters, mt.localvariables)
    _check_for_modulecode(mt.modulecode, env, path, issues)


def _check_for_modulecode(
    modulecode: ModuleCode,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
) -> None:
    sequences = list(modulecode.sequences or [])
    if not sequences:
        return

    var_refs = _collect_var_refs(modulecode)
    for seq in sequences:
        seq_name = getattr(seq, "name", "")
        if not seq_name:
            continue
        reset_ref = f"{seq_name}.Reset"
        reset_ref_cf = reset_ref.casefold()
        if reset_ref_cf not in var_refs:
            continue

        reset_old_vars = _collect_reset_old_vars(modulecode, reset_ref_cf)
        run_writes: dict[tuple[str, str], tuple[Variable, str]] = {}
        reset_writes: dict[tuple[str, str], tuple[Variable, str]] = {}

        _collect_writes_in_modulecode(
            modulecode,
            env,
            reset_ref_cf,
            {v.casefold() for v in reset_old_vars},
            run_writes,
            reset_writes,
        )

        if not run_writes:
            continue

        reset_whole_vars = {
            key[0] for key, (_, field_path) in reset_writes.items() if not field_path
        }
        reset_keys = set(reset_writes.keys())
        reset_old_cf = {v.casefold() for v in reset_old_vars}

        for key, (var, field_path) in sorted(
            run_writes.items(), key=lambda item: (item[0][0], item[0][1])
        ):
            var_key, _field_key = key
            if var_key in reset_old_cf:
                continue
            if var_key in reset_whole_vars:
                continue
            if key in reset_keys:
                continue

            issues.append(
                VariableIssue(
                    kind=IssueKind.RESET_CONTAMINATION,
                    module_path=path.copy(),
                    variable=var,
                    role="localvariable",
                    field_path=field_path or None,
                    sequence_name=seq_name,
                    reset_variable=reset_ref,
                )
            )


def _collect_var_refs(modulecode: ModuleCode) -> set[str]:
    refs: set[str] = set()

    def visit(obj: Any) -> None:
        if obj is None:
            return
        if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
            full = obj[const.KEY_VAR_NAME]
            if isinstance(full, str) and full:
                refs.add(full.casefold())
            return
        if isinstance(obj, list):
            for it in obj:
                visit(it)
            return
        if isinstance(obj, tuple):
            for it in obj[1:]:
                visit(it)
            return
        if hasattr(obj, "children"):
            for ch in getattr(obj, "children", []):
                visit(ch)

    for seq in modulecode.sequences or []:
        for node in seq.code or []:
            visit(node)
    for eq in modulecode.equations or []:
        for stmt in eq.code or []:
            visit(stmt)

    return refs


def _collect_reset_old_vars(modulecode: ModuleCode, reset_ref_cf: str) -> set[str]:
    reset_old_vars: set[str] = set()

    def visit(obj: Any) -> None:
        if obj is None:
            return
        if hasattr(obj, "data") and getattr(obj, "data") == const.KEY_STATEMENT:
            for ch in getattr(obj, "children", []):
                visit(ch)
            return
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
            _, target, expr = obj
            if (
                isinstance(expr, dict)
                and const.KEY_VAR_NAME in expr
                and isinstance(expr[const.KEY_VAR_NAME], str)
                and expr[const.KEY_VAR_NAME].casefold() == reset_ref_cf
            ):
                if isinstance(target, dict) and const.KEY_VAR_NAME in target:
                    tgt = target[const.KEY_VAR_NAME]
                    if isinstance(tgt, str) and tgt:
                        reset_old_vars.add(tgt)
            visit(expr)
            return
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = obj
            for cond, stmts in branches or []:
                visit(cond)
                for st in stmts or []:
                    visit(st)
            for st in else_block or []:
                visit(st)
            return
        if isinstance(obj, list):
            for it in obj:
                visit(it)
            return
        if isinstance(obj, tuple):
            for it in obj[1:]:
                visit(it)
            return
        if hasattr(obj, "children"):
            for ch in getattr(obj, "children", []):
                visit(ch)

    for seq in modulecode.sequences or []:
        for node in seq.code or []:
            visit(node)
    for eq in modulecode.equations or []:
        for stmt in eq.code or []:
            visit(stmt)

    return reset_old_vars


def _collect_writes_in_modulecode(
    modulecode: ModuleCode,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    run_writes: dict[tuple[str, str], tuple[Variable, str]],
    reset_writes: dict[tuple[str, str], tuple[Variable, str]],
) -> None:
    for eq in modulecode.equations or []:
        for stmt in eq.code or []:
            _collect_writes_in_stmt(
                stmt, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode="run"
            )

    for seq in modulecode.sequences or []:
        for node in seq.code or []:
            _collect_writes_in_seq_node(
                node, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes
            )


def _collect_writes_in_seq_node(
    node: Any,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    run_writes: dict[tuple[str, str], tuple[Variable, str]],
    reset_writes: dict[tuple[str, str], tuple[Variable, str]],
) -> None:
    if isinstance(node, SFCStep):
        for stmt in node.code.enter or []:
            _collect_writes_in_stmt(stmt, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode="run")
        for stmt in node.code.active or []:
            _collect_writes_in_stmt(stmt, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode="run")
        for stmt in node.code.exit or []:
            _collect_writes_in_stmt(stmt, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode="run")
        return

    if isinstance(node, SFCTransition):
        return

    if isinstance(node, SFCAlternative):
        for branch in node.branches or []:
            for sub in branch or []:
                _collect_writes_in_seq_node(sub, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes)
        return

    if isinstance(node, SFCParallel):
        for branch in node.branches or []:
            for sub in branch or []:
                _collect_writes_in_seq_node(sub, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes)
        return

    if isinstance(node, SFCSubsequence):
        for sub in node.body or []:
            _collect_writes_in_seq_node(sub, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes)
        return

    if isinstance(node, SFCTransitionSub):
        for sub in node.body or []:
            _collect_writes_in_seq_node(sub, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes)
        return


def _collect_writes_in_stmt(
    obj: Any,
    env: dict[str, Variable],
    reset_ref_cf: str,
    reset_old_vars_cf: set[str],
    run_writes: dict[tuple[str, str], tuple[Variable, str]],
    reset_writes: dict[tuple[str, str], tuple[Variable, str]],
    mode: str,
) -> None:
    if obj is None:
        return
    if hasattr(obj, "data") and getattr(obj, "data") == const.KEY_STATEMENT:
        for ch in getattr(obj, "children", []):
            _collect_writes_in_stmt(ch, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = obj
        saw_run = False
        saw_reset = False
        for cond, stmts in branches or []:
            cond_flags = _classify_reset_condition(cond, reset_ref_cf, reset_old_vars_cf)
            branch_mode = mode
            if cond_flags["run"] and not cond_flags["reset"]:
                branch_mode = "run"
            elif cond_flags["reset"] and not cond_flags["run"]:
                branch_mode = "reset"
            if cond_flags["run"]:
                saw_run = True
            if cond_flags["reset"]:
                saw_reset = True
            for st in stmts or []:
                _collect_writes_in_stmt(st, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, branch_mode)
        if else_block:
            else_mode = mode
            if saw_run and not saw_reset:
                else_mode = "reset"
            elif saw_reset and not saw_run:
                else_mode = "run"
            for st in else_block or []:
                _collect_writes_in_stmt(st, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, else_mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
        _, target, expr = obj
        if mode in ("run", "reset"):
            write_bucket = run_writes if mode == "run" else reset_writes
            _record_write(target, env, write_bucket)
        _collect_writes_in_stmt(expr, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
        _, fn_name, args = obj
        if mode in ("run", "reset"):
            write_bucket = run_writes if mode == "run" else reset_writes
            _record_function_call_writes(fn_name, args or [], env, write_bucket)
        for arg in args or []:
            _collect_writes_in_stmt(arg, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
        _, branches, else_expr = obj
        for cond, then_expr in branches or []:
            _collect_writes_in_stmt(cond, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
            _collect_writes_in_stmt(then_expr, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        if else_expr is not None:
            _collect_writes_in_stmt(else_expr, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
        _, left, pairs = obj
        _collect_writes_in_stmt(left, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        for _sym, rhs in pairs or []:
            _collect_writes_in_stmt(rhs, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
        _, left, parts = obj
        _collect_writes_in_stmt(left, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        for _opval, rhs in parts or []:
            _collect_writes_in_stmt(rhs, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_PLUS, const.KEY_MINUS):
        _collect_writes_in_stmt(obj[1], env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND):
        for sub in obj[1] or []:
            _collect_writes_in_stmt(sub, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
        _collect_writes_in_stmt(obj[1], env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if isinstance(obj, list):
        for it in obj:
            _collect_writes_in_stmt(it, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)
        return

    if hasattr(obj, "children"):
        for ch in getattr(obj, "children", []):
            _collect_writes_in_stmt(ch, env, reset_ref_cf, reset_old_vars_cf, run_writes, reset_writes, mode)


def _classify_reset_condition(
    cond: Any, reset_ref_cf: str, reset_old_vars_cf: set[str]
) -> dict[str, bool]:
    positives: set[str] = set()
    negatives: set[str] = set()

    def visit(obj: Any, negated: bool) -> None:
        if obj is None:
            return
        if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
            full = obj[const.KEY_VAR_NAME]
            if isinstance(full, str) and full:
                name_cf = full.casefold()
                if name_cf == reset_ref_cf or name_cf in reset_old_vars_cf:
                    if negated:
                        negatives.add(name_cf)
                    else:
                        positives.add(name_cf)
            return
        if isinstance(obj, tuple) and obj:
            if obj[0] == const.GRAMMAR_VALUE_NOT:
                visit(obj[1], not negated)
                return
            for it in obj[1:]:
                visit(it, negated)
            return
        if isinstance(obj, list):
            for it in obj:
                visit(it, negated)
            return
        if hasattr(obj, "children"):
            for ch in getattr(obj, "children", []):
                visit(ch, negated)

    visit(cond, False)

    is_run = reset_ref_cf in negatives
    is_reset = reset_ref_cf in positives or bool(negatives & reset_old_vars_cf)
    return {"run": is_run, "reset": is_reset}


def _split_var_ref(full_ref: str) -> tuple[str, str]:
    if not full_ref:
        return "", ""
    if "." not in full_ref:
        return full_ref, ""
    base, field_path = full_ref.split(".", 1)
    return base, field_path


def _record_write(
    target: Any,
    env: dict[str, Variable],
    out: dict[tuple[str, str], tuple[Variable, str]],
) -> None:
    if not isinstance(target, dict) or const.KEY_VAR_NAME not in target:
        return
    full_ref = target[const.KEY_VAR_NAME]
    if not isinstance(full_ref, str) or not full_ref:
        return
    base, field_path = _split_var_ref(full_ref)
    if not base:
        return
    var = env.get(base.casefold())
    if var is None:
        return
    field_path = field_path or ""
    key = (var.name.casefold(), field_path.casefold())
    out[key] = (var, field_path)


def _record_function_call_writes(
    fn_name: str,
    args: list[Any],
    env: dict[str, Variable],
    out: dict[tuple[str, str], tuple[Variable, str]],
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
