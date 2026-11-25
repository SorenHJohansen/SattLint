"""Boolean latching helpers for reset contamination analysis."""

from __future__ import annotations

from typing import Any, cast

from sattlint.parser_api import (
    Assignment,
    FuncCallStmt,
    IfStmt,
    ModuleCode,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    Variable,
)

from ...reporting.variables_report import ImplicitLatchIssue, VariableIssue
from ._reset_latching_paths import (
    BooleanPathState,
    all_boolean_paths_cover_false,
    boolean_path_covers_false,
    boolean_write_key,
    collect_boolean_seq_block_paths,
    collect_boolean_seq_node_paths,
    collect_boolean_stmt_block_paths,
    collect_boolean_stmt_paths,
    literal_boolean,
    merge_boolean_parallel_branch_results,
    record_boolean_assignment,
    record_boolean_function_call,
    record_boolean_write,
)
from ._reset_path_state import WriteKey, WriteMap


def check_for_modulecode_latching(
    modulecode: ModuleCode,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
) -> None:
    seen: set[tuple[tuple[str, ...], str, str]] = set()

    for equation in modulecode.equationblocks or []:
        equation_name = getattr(equation, "name", "<unnamed>")
        scan_stmt_block_for_latching(
            equation.code or [],
            env,
            path,
            issues,
            seen,
            site=f"EQ:{equation_name}",
        )

    for sequence in modulecode.sequences or []:
        sequence_name = getattr(sequence, "name", "<unnamed>")
        scan_seq_nodes_for_latching(
            sequence.code or [],
            env,
            path,
            issues,
            seen,
            site=f"SQ:{sequence_name}",
            sequence_name=sequence_name,
        )


def scan_stmt_block_for_latching(
    statements: list[Any],
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None = None,
    cleared_keys: set[WriteKey] | None = None,
) -> None:
    _scan_stmt_block_stateful(
        statements,
        env,
        path,
        issues,
        seen,
        site=site,
        sequence_name=sequence_name,
        incoming=[BooleanPathState()],
        cleared_keys=set(cleared_keys or ()),
    )


def _scan_stmt_block_stateful(
    statements: list[Any],
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None,
    incoming: list[BooleanPathState],
    cleared_keys: set[WriteKey],
) -> list[BooleanPathState]:
    block_clears = set(cleared_keys)
    block_clears |= _collect_top_level_false_keys(statements, env)
    states = incoming or [BooleanPathState()]
    for statement in statements:
        states = _scan_stmt_for_latching_stateful(
            statement,
            env,
            path,
            issues,
            seen,
            site=site,
            sequence_name=sequence_name,
            incoming=states,
            cleared_keys=block_clears,
        )
    return states


def scan_stmt_for_latching(
    obj: Any,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None = None,
    cleared_keys: set[WriteKey] | None = None,
) -> None:
    _scan_stmt_for_latching_stateful(
        obj,
        env,
        path,
        issues,
        seen,
        site=site,
        sequence_name=sequence_name,
        incoming=[BooleanPathState()],
        cleared_keys=set(cleared_keys or ()),
    )


def _scan_stmt_for_latching_stateful(
    obj: Any,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None,
    incoming: list[BooleanPathState],
    cleared_keys: set[WriteKey],
) -> list[BooleanPathState]:
    if obj is None:
        return incoming
    if isinstance(obj, IfStmt):
        incoming_states = incoming or [BooleanPathState()]
        branch_states: list[tuple[str, list[BooleanPathState]]] = []
        for index, (_condition, branch_statements) in enumerate(obj.branches or []):
            label = "IF" if index == 0 else f"ELSIF:{index}"
            statements = list(branch_statements) or []
            states = _scan_stmt_block_stateful(
                statements,
                env,
                path,
                issues,
                seen,
                site=f"{site} > {label}",
                sequence_name=sequence_name,
                incoming=[state.clone() for state in incoming_states],
                cleared_keys=cleared_keys | _collect_top_level_false_keys(statements, env),
            )
            branch_states.append((label, states or [BooleanPathState()]))
        else_statements = list(obj.else_block or ())
        if else_statements:
            else_states = _scan_stmt_block_stateful(
                else_statements,
                env,
                path,
                issues,
                seen,
                site=f"{site} > ELSE",
                sequence_name=sequence_name,
                incoming=[state.clone() for state in incoming_states],
                cleared_keys=cleared_keys | _collect_top_level_false_keys(else_statements, env),
            )
        else:
            else_states = [state.clone() for state in incoming_states]

        for label, states in branch_states:
            alternative_states = [
                alternative_state
                for other_label, other_states in branch_states
                if other_label != label
                for alternative_state in other_states
            ]
            alternative_states.extend(else_states)
            emit_branch_latch_issues(
                states,
                alternative_states or [BooleanPathState()],
                path,
                issues,
                seen,
                site=f"{site} > {label}",
                role_prefix="implicit latch across alternative paths",
                sequence_name=sequence_name,
                cleared_keys=cleared_keys,
            )
        return [*[state for _label, states in branch_states for state in states], *else_states]
    if isinstance(obj, (list, tuple)):
        states = incoming
        for item in cast(list[Any] | tuple[Any, ...], obj):
            states = _scan_stmt_for_latching_stateful(
                item,
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
                incoming=states,
                cleared_keys=cleared_keys,
            )
        return states
    return collect_boolean_stmt_paths(obj, env, incoming)


def _collect_top_level_false_keys(
    statements: list[Any],
    env: dict[str, Variable],
) -> set[WriteKey]:
    """False writes that run unconditionally in this statement list.

    A false write at the top level of an equation block or a branch means the
    value is reset every time that block runs, so a latch inside a nested
    branch is not a latch.
    """
    keys: set[WriteKey] = set()
    for statement in statements:
        if isinstance(statement, Assignment):
            if literal_boolean(statement.value) is False:
                key = boolean_write_key(statement.target, env)
                if key is not None:
                    keys.add(key)
        elif isinstance(statement, FuncCallStmt):
            call = statement.call
            if (
                call.name.casefold() == "setbooleanvalue"
                and len(call.args) >= 2
                and literal_boolean(call.args[1]) is False
            ):
                key = boolean_write_key(call.args[0], env)
                if key is not None:
                    keys.add(key)
    return keys


def _sequence_init_false_keys(
    nodes: list[Any],
    env: dict[str, Variable],
) -> set[WriteKey]:
    """False writes in the first init step; it runs before any latch can persist."""
    keys: set[WriteKey] = set()
    for node in nodes:
        if not isinstance(node, SFCStep) or node.kind != "init":
            continue
        keys |= _collect_top_level_false_keys(node.code.enter or [], env)
        keys |= _collect_top_level_false_keys(node.code.active or [], env)
        keys |= _collect_top_level_false_keys(node.code.exit or [], env)
    return keys


def scan_seq_nodes_for_latching(
    nodes: list[Any],
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None = None,
    cleared_keys: set[WriteKey] | None = None,
) -> None:
    sequence_clears = set(cleared_keys or ())
    sequence_clears |= _sequence_init_false_keys(nodes, env)
    for node in nodes:
        if isinstance(node, SFCStep):
            step_site = f"{site} > STEP:{node.name}"
            entry_states = collect_boolean_stmt_block_paths(
                node.code.enter or [],
                env,
                [BooleanPathState()],
            )
            active_states = collect_boolean_stmt_block_paths(
                node.code.active or [],
                env,
                entry_states or [BooleanPathState()],
            )
            exit_states = collect_boolean_stmt_block_paths(
                node.code.exit or [],
                env,
                [BooleanPathState()],
            )
            emit_branch_latch_issues(
                active_states or [BooleanPathState()],
                exit_states or [BooleanPathState()],
                path,
                issues,
                seen,
                site=step_site,
                role_prefix="implicit latch across step exit",
                sequence_name=sequence_name,
                cleared_keys=sequence_clears,
            )
            scan_stmt_block_for_latching(
                node.code.enter or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:ENTER",
                sequence_name=sequence_name,
                cleared_keys=sequence_clears,
            )
            scan_stmt_block_for_latching(
                node.code.active or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:ACTIVE",
                sequence_name=sequence_name,
                cleared_keys=sequence_clears,
            )
            scan_stmt_block_for_latching(
                node.code.exit or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:EXIT",
                sequence_name=sequence_name,
                cleared_keys=sequence_clears,
            )
            continue
        if isinstance(node, SFCAlternative):
            branch_states: list[tuple[str, list[BooleanPathState]]] = []
            for index, branch in enumerate(node.branches or []):
                label = f"ALT:{index + 1}"
                states = collect_boolean_seq_block_paths(
                    branch or [],
                    env,
                    [BooleanPathState()],
                )
                branch_states.append((label, states or [BooleanPathState()]))
                scan_seq_nodes_for_latching(
                    branch or [],
                    env,
                    path,
                    issues,
                    seen,
                    site=f"{site} > {label}",
                    sequence_name=sequence_name,
                    cleared_keys=sequence_clears,
                )
            for label, states in branch_states:
                alternative_states = [
                    alternative_state
                    for other_label, other_states in branch_states
                    if other_label != label
                    for alternative_state in other_states
                ]
                emit_branch_latch_issues(
                    states,
                    alternative_states or [BooleanPathState()],
                    path,
                    issues,
                    seen,
                    site=f"{site} > {label}",
                    role_prefix="implicit latch across SFC alternatives",
                    sequence_name=sequence_name,
                    cleared_keys=sequence_clears,
                )
            continue
        if isinstance(node, SFCParallel):
            for index, branch in enumerate(node.branches or []):
                scan_seq_nodes_for_latching(
                    branch or [],
                    env,
                    path,
                    issues,
                    seen,
                    site=f"{site} > PAR:{index + 1}",
                    sequence_name=sequence_name,
                    cleared_keys=sequence_clears,
                )
            continue
        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            scan_seq_nodes_for_latching(
                node.body or [],
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
                cleared_keys=sequence_clears,
            )


def emit_branch_latch_issues(
    branch_states: list[BooleanPathState],
    alternative_states: list[BooleanPathState],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    role_prefix: str,
    sequence_name: str | None,
    cleared_keys: set[WriteKey] | None = None,
) -> None:
    true_writes: WriteMap = {}
    for state in branch_states:
        true_writes.update(state.true_writes)

    cleared = cleared_keys or set()
    for key, (variable, field_path) in sorted(true_writes.items(), key=lambda item: (item[0][0], item[0][1])):
        if key in cleared:
            continue
        if all_boolean_paths_cover_false(alternative_states, key):
            continue
        issue_key = (tuple(path), f"{key[0]}.{key[1]}" if key[1] else key[0], site.casefold())
        if issue_key in seen:
            continue
        seen.add(issue_key)
        issues.append(
            ImplicitLatchIssue(
                module_path=path.copy(),
                variable=variable,
                role=f"{role_prefix} at {site}",
                field_path=field_path or None,
                sequence_name=sequence_name,
                site=site,
            )
        )


__all__ = [
    "BooleanPathState",
    "all_boolean_paths_cover_false",
    "boolean_path_covers_false",
    "check_for_modulecode_latching",
    "collect_boolean_seq_block_paths",
    "collect_boolean_seq_node_paths",
    "collect_boolean_stmt_block_paths",
    "collect_boolean_stmt_paths",
    "emit_branch_latch_issues",
    "literal_boolean",
    "merge_boolean_parallel_branch_results",
    "record_boolean_assignment",
    "record_boolean_function_call",
    "record_boolean_write",
    "scan_seq_nodes_for_latching",
    "scan_stmt_block_for_latching",
    "scan_stmt_for_latching",
]
