"""SFC analysis for structural dead paths, write races, and state conflicts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from itertools import product
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
)

from ..resolution.paths import CanonicalPath
from ._sfc_collectors import StepContract, _SfcAccessCollector, _SfcStepContractCollector
from ._sfc_guard_logic import (
    _collect_transition_logic_issues,
    _conflict_rep,
    _format_branch_path,
    _paths_conflict,
)
from ._sfc_module_walk import iter_sfc_modulecodes
from .framework import Issue, SimpleReport

type StepSet = frozenset[str]
type ExclusiveStepGroup = tuple[str, ...]


@dataclass(frozen=True)
class SfcReachabilityFinding:
    module_path: tuple[str, ...]
    sequence_name: str
    branch_path: tuple[int, ...]
    node_index: int
    node_label: str
    node_type: str
    terminated_by: dict[str, Any]


def _normalize_step_groups(
    step_groups: Iterable[Iterable[str]] | None,
) -> tuple[ExclusiveStepGroup, ...]:
    if step_groups is None:
        return ()

    groups: list[ExclusiveStepGroup] = []
    for group in step_groups:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in group:
            if not isinstance(item, str):
                continue
            name = item.strip()
            if not name:
                continue
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(name)
        if len(normalized) >= 2:
            groups.append(tuple(normalized))

    return tuple(groups)


def normalize_mutually_exclusive_step_sets(raw: object) -> tuple[ExclusiveStepGroup, ...]:
    if not isinstance(raw, list):
        return ()
    return _normalize_step_groups(group for group in raw if isinstance(group, list | tuple | set))


def get_configured_mutually_exclusive_step_sets(
    config: dict[str, Any] | None,
) -> tuple[ExclusiveStepGroup, ...]:
    if not isinstance(config, dict):
        return ()
    analysis = config.get("analysis", {})
    if not isinstance(analysis, dict):
        return ()
    sfc_config = analysis.get("sfc", {})
    if not isinstance(sfc_config, dict):
        return ()
    return normalize_mutually_exclusive_step_sets(sfc_config.get("mutually_exclusive_steps", []))


def _normalize_step_contract_refs(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return tuple(normalized)


def _normalize_step_contract(raw: object) -> StepContract:
    if not isinstance(raw, dict):
        return StepContract()

    return StepContract(
        required_enter_writes=_normalize_step_contract_refs(raw.get("required_enter_writes", [])),
        required_exit_writes=_normalize_step_contract_refs(raw.get("required_exit_writes", [])),
    )


def normalize_step_contracts(raw: object) -> dict[str, StepContract]:
    if not isinstance(raw, Mapping):
        return {}

    normalized: dict[str, StepContract] = {}
    for step_name, contract_raw in raw.items():
        if not isinstance(step_name, str):
            continue
        name = step_name.strip()
        if not name:
            continue
        contract = _normalize_step_contract(contract_raw)
        if not contract.required_enter_writes and not contract.required_exit_writes:
            continue
        normalized[name.casefold()] = contract
    return normalized


def get_configured_step_contracts(
    config: dict[str, Any] | None,
) -> dict[str, StepContract]:
    if not isinstance(config, dict):
        return {}
    analysis = config.get("analysis", {})
    if not isinstance(analysis, dict):
        return {}
    sfc_config = analysis.get("sfc", {})
    if not isinstance(sfc_config, dict):
        return {}
    return normalize_step_contracts(sfc_config.get("step_contracts", {}))


def _sequence_node_label(node: object) -> str:
    node_name = getattr(node, "name", None)
    if node_name:
        return f"{type(node).__name__}:{node_name}"
    if isinstance(node, SFCFork):
        return f"SFCFork:{node.target}"
    return type(node).__name__


def _inspect_sfc_linear_nodes(
    findings: list[SfcReachabilityFinding],
    nodes: SequenceABC[object] | None,
    module_path: list[str],
    sequence_name: str,
    branch_path: tuple[int, ...] = (),
) -> None:
    terminated_by: dict[str, Any] | None = None
    for index, node in enumerate(nodes or []):
        if terminated_by is not None:
            findings.append(
                SfcReachabilityFinding(
                    module_path=tuple(module_path),
                    sequence_name=sequence_name,
                    branch_path=branch_path,
                    node_index=index,
                    node_label=_sequence_node_label(node),
                    node_type=type(node).__name__,
                    terminated_by=dict(terminated_by),
                )
            )
            continue

        if isinstance(node, SFCBreak):
            terminated_by = {"kind": "SFCBreak"}
            continue

        if isinstance(node, SFCFork):
            terminated_by = {"kind": "SFCFork", "target": node.target}
            continue

        if isinstance(node, SFCAlternative | SFCParallel):
            for branch_index, branch in enumerate(node.branches or []):
                _inspect_sfc_linear_nodes(
                    findings,
                    branch,
                    module_path,
                    sequence_name,
                    (*branch_path, branch_index),
                )
            continue

        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            _inspect_sfc_linear_nodes(findings, node.body, module_path, sequence_name, branch_path)


def collect_sfc_reachability_findings(
    base_picture: BasePicture,
) -> list[SfcReachabilityFinding]:
    findings: list[SfcReachabilityFinding] = []

    for module_path, modulecode in iter_sfc_modulecodes(base_picture):
        if modulecode is None:
            continue
        for sequence in modulecode.sequences or []:
            if isinstance(sequence, Sequence):
                _inspect_sfc_linear_nodes(findings, sequence.code, module_path, sequence.name)

    return findings


def _collect_active_step_sets(nodes: list[object] | None) -> set[StepSet]:
    active_sets: set[StepSet] = set()

    for node in nodes or []:
        if isinstance(node, SFCStep):
            active_sets.add(frozenset({node.name}))
            continue

        if isinstance(node, SFCTransition | SFCFork | SFCBreak):
            continue

        if isinstance(node, SFCAlternative):
            for branch in node.branches or []:
                active_sets.update(_collect_active_step_sets(branch))
            continue

        if isinstance(node, SFCParallel):
            branch_sets: list[set[StepSet]] = []
            for branch in node.branches or []:
                states = _collect_active_step_sets(branch)
                branch_sets.append(states or {frozenset()})

            for branch_combo in product(*branch_sets):
                merged: set[str] = set()
                for state_set in branch_combo:
                    merged.update(state_set)
                if merged:
                    active_sets.add(frozenset(merged))
            continue

        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            active_sets.update(_collect_active_step_sets(node.body))

    return active_sets


def _find_illegal_state_combinations(
    active_step_sets: Iterable[StepSet],
    mutually_exclusive_steps: tuple[ExclusiveStepGroup, ...],
) -> list[tuple[str, ...]]:
    conflicts: dict[tuple[str, ...], None] = {}

    for active_steps in active_step_sets:
        active_keys = {name.casefold() for name in active_steps}
        for group in mutually_exclusive_steps:
            overlap = tuple(name for name in group if name.casefold() in active_keys)
            if len(overlap) >= 2:
                conflicts[overlap] = None

    return sorted(conflicts.keys())


def _collect_illegal_state_combination_issues(
    base_picture: BasePicture,
    mutually_exclusive_steps: tuple[ExclusiveStepGroup, ...],
) -> list[Issue]:
    issues: list[Issue] = []

    if not mutually_exclusive_steps:
        return issues

    for module_path, modulecode in iter_sfc_modulecodes(base_picture):
        if modulecode is None:
            continue
        for sequence in modulecode.sequences or []:
            if not isinstance(sequence, Sequence):
                continue

            conflicts = _find_illegal_state_combinations(
                _collect_active_step_sets(sequence.code or []),
                mutually_exclusive_steps,
            )
            if not conflicts:
                continue

            preview = "; ".join(" + ".join(combo) for combo in conflicts[:4])
            if len(conflicts) > 4:
                preview = f"{preview}; ... (+{len(conflicts) - 4} more)"

            issues.append(
                Issue(
                    kind="sfc_illegal_state_combination",
                    message=(
                        f"Sequence {sequence.name!r} can activate mutually exclusive step combinations: {preview}"
                    ),
                    module_path=module_path.copy(),
                    data={
                        "sequence": sequence.name,
                        "conflicts": [list(combo) for combo in conflicts],
                    },
                )
            )

    return issues


def _format_terminator(terminated_by: dict[str, Any]) -> str:
    terminator = str(terminated_by.get("kind", "an earlier terminating node"))
    target = terminated_by.get("target")
    if target:
        return f"{terminator} targeting {target!r}"
    return terminator


def analyze_sfc(
    base_picture: BasePicture,
    mutually_exclusive_steps: Iterable[Iterable[str]] | None = None,
    step_contracts: Mapping[str, object] | None = None,
) -> SimpleReport:
    collector = _SfcAccessCollector(base_picture)
    collector.run()
    normalized_groups = _normalize_step_groups(mutually_exclusive_steps)
    normalized_step_contracts = normalize_step_contracts(step_contracts)

    issues: list[Issue] = []
    for key, branch_writes in collector.parallel_writes.items():
        conflicts: dict[tuple[str, ...], CanonicalPath] = {}
        branch_ids = sorted(branch_writes.keys())
        for index, left in enumerate(branch_ids):
            for right in branch_ids[index + 1 :]:
                for left_path in branch_writes[left]:
                    for right_path in branch_writes[right]:
                        if _paths_conflict(left_path, right_path):
                            rep = _conflict_rep(left_path, right_path)
                            conflicts.setdefault(rep.key(), rep)

        if not conflicts:
            continue

        meta = collector.parallel_meta.get(key)
        seq_name = meta.sequence_name if meta else "<unnamed>"
        conflict_list = sorted(str(path) for path in conflicts.values())
        preview = ", ".join(conflict_list[:6])
        if len(conflict_list) > 6:
            preview = f"{preview}, ... (+{len(conflict_list) - 6} more)"

        issues.append(
            Issue(
                kind="sfc_parallel_write_race",
                message=(f"Parallel branches in sequence {seq_name!r} write to the same variable(s): {preview}"),
                module_path=meta.module_path if meta else None,
                data={
                    "sequence": seq_name,
                    "parallel_id": meta.parallel_id if meta else None,
                    "conflicts": conflict_list,
                },
            )
        )

    for finding in collect_sfc_reachability_findings(base_picture):
        branch_context = _format_branch_path(finding.branch_path)
        terminator = _format_terminator(finding.terminated_by)
        data = {
            "sequence": finding.sequence_name,
            "branch_path": list(finding.branch_path),
            "node_index": finding.node_index,
            "node_label": finding.node_label,
            "node_type": finding.node_type,
            "terminated_by": dict(finding.terminated_by),
        }
        if finding.node_type in {"SFCTransition", "SFCTransitionSub"}:
            issues.append(
                Issue(
                    kind="sfc_unreachable_transition",
                    message=(
                        f"Transition {finding.node_label!r} in sequence {finding.sequence_name!r}{branch_context} "
                        f"can never fire because {terminator} terminates that path earlier."
                    ),
                    module_path=list(finding.module_path),
                    data=data,
                )
            )
        else:
            issues.append(
                Issue(
                    kind="sfc_unreachable_sequence_node",
                    message=(
                        f"Sequence {finding.sequence_name!r}{branch_context} contains unreachable node "
                        f"{finding.node_label!r} because {terminator} terminates that path earlier."
                    ),
                    module_path=list(finding.module_path),
                    data=data,
                )
            )

    issues.extend(_collect_transition_logic_issues(base_picture))

    issues.extend(_collect_illegal_state_combination_issues(base_picture, normalized_groups))

    if normalized_step_contracts:
        contract_collector = _SfcStepContractCollector(
            base_picture,
            normalized_step_contracts,
        )
        issues.extend(contract_collector.collect())

    return SimpleReport(name=base_picture.header.name, issues=issues)
