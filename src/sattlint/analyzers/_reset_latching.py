"""Boolean latching helpers for reset contamination analysis."""

from __future__ import annotations

from typing import Any, cast

from sattline_parser.models.ast_model import (
    ModuleCode,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    Variable,
)

from ..grammar import constants as const
from ..reporting.variables_report import IssueKind, VariableIssue
from ._reset_latching_paths import (
    BooleanPathState,
    all_boolean_paths_cover_false,
    boolean_path_covers_false,
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
from ._reset_path_state import WriteMap

type StmtBranch = tuple[Any, list[Any]]
type IfTuple = tuple[str, list[StmtBranch] | None, list[Any] | None]


def _latch_children_of(obj: Any) -> list[Any] | None:
    children = getattr(obj, "children", None)
    return cast(list[Any], children) if isinstance(children, list) else None


def check_for_modulecode_latching(
    modulecode: ModuleCode,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
) -> None:
    seen: set[tuple[tuple[str, ...], str, str]] = set()

    for equation in modulecode.equations or []:
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
            site=f"SEQ:{sequence_name}",
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
) -> None:
    for statement in statements:
        scan_stmt_for_latching(
            statement,
            env,
            path,
            issues,
            seen,
            site=site,
            sequence_name=sequence_name,
        )


def scan_stmt_for_latching(
    obj: Any,
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None = None,
) -> None:
    if obj is None:
        return
    if hasattr(obj, "data") and obj.data == const.KEY_STATEMENT:
        for child in _latch_children_of(obj) or []:
            scan_stmt_for_latching(
                child,
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
            )
        return
    if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
        _, branches, else_block = cast(IfTuple, obj)
        branch_states: list[tuple[str, list[BooleanPathState]]] = []
        for index, (_condition, branch_statements) in enumerate(branches or []):
            label = "IF" if index == 0 else f"ELSIF:{index}"
            states = collect_boolean_stmt_block_paths(
                branch_statements or [],
                env,
                [BooleanPathState()],
            )
            branch_states.append((label, states or [BooleanPathState()]))
            scan_stmt_block_for_latching(
                branch_statements or [],
                env,
                path,
                issues,
                seen,
                site=f"{site} > {label}",
                sequence_name=sequence_name,
            )
        else_states = (
            collect_boolean_stmt_block_paths(else_block or [], env, [BooleanPathState()])
            if else_block
            else [BooleanPathState()]
        )
        if else_block:
            scan_stmt_block_for_latching(
                else_block or [],
                env,
                path,
                issues,
                seen,
                site=f"{site} > ELSE",
                sequence_name=sequence_name,
            )

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
            )
        return
    if isinstance(obj, list):
        for item in cast(list[Any], obj):
            scan_stmt_for_latching(
                item,
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
            )
        return
    children = _latch_children_of(obj)
    if children is not None:
        for child in children:
            scan_stmt_for_latching(
                child,
                env,
                path,
                issues,
                seen,
                site=site,
                sequence_name=sequence_name,
            )


def scan_seq_nodes_for_latching(
    nodes: list[Any],
    env: dict[str, Variable],
    path: list[str],
    issues: list[VariableIssue],
    seen: set[tuple[tuple[str, ...], str, str]],
    *,
    site: str,
    sequence_name: str | None = None,
) -> None:
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
            )
            scan_stmt_block_for_latching(
                node.code.enter or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:ENTER",
                sequence_name=sequence_name,
            )
            scan_stmt_block_for_latching(
                node.code.active or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:ACTIVE",
                sequence_name=sequence_name,
            )
            scan_stmt_block_for_latching(
                node.code.exit or [],
                env,
                path,
                issues,
                seen,
                site=f"{step_site}:EXIT",
                sequence_name=sequence_name,
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
) -> None:
    true_writes: WriteMap = {}
    for state in branch_states:
        true_writes.update(state.true_writes)

    for key, (variable, field_path) in sorted(true_writes.items(), key=lambda item: (item[0][0], item[0][1])):
        if all_boolean_paths_cover_false(alternative_states, key):
            continue
        issue_key = (tuple(path), key[0], site.casefold())
        if issue_key in seen:
            continue
        seen.add(issue_key)
        issues.append(
            VariableIssue(
                kind=IssueKind.IMPLICIT_LATCH,
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
