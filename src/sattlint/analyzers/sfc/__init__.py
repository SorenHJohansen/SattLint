# pyright: reportPrivateUsage=false

"""SFC analysis for structural dead paths, write races, and state conflicts."""

from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from sattlint.parser_api import (
    BasePicture,
    CodeComment,
    SFCAlternative,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
)

from ..framework import AnalysisContext, Issue, SimpleReport
from ..shared.module_code_walk import iter_modulecodes
from ..shared.target_origin import TargetOriginFilter, build_target_origin_filter_for_basepicture
from ._sfc_fork_checks import (
    SFC_CROSS_SEQUENCE_FORK_KIND,
    SFC_FORK_ISSUE_KINDS,
    collect_sfc_fork_findings,
)
from ._sfc_guard_logic import (
    _collect_transition_logic_issues,
    _format_branch_path,
)

_SFC_REACHABILITY_ISSUE_KINDS = frozenset({"sfc_unreachable_transition", "sfc_unreachable_sequence_node"})
_SFC_TRANSITION_LOGIC_ISSUE_KINDS = frozenset({"sfc_duplicate_transition_guard"})
_SFC_INITIAL_STEP_ISSUE_KINDS = frozenset({"sfc_missing_initial_step"})


@dataclass(frozen=True)
class SfcTerminator:
    """The node whose control flow makes a following element unreachable."""

    kind: str
    targets: tuple[str, ...] = ()

    def to_data(self) -> dict[str, object]:
        return {"kind": self.kind, "targets": list(self.targets)}


@dataclass(frozen=True)
class SfcReachabilityFinding:
    module_path: tuple[str, ...]
    sequence_name: str
    branch_path: tuple[int, ...]
    node_index: int
    node_label: str
    node_type: str
    terminated_by: SfcTerminator


def _sequence_node_label(node: object) -> str:
    node_name = getattr(node, "name", None)
    if node_name:
        return f"{type(node).__name__}:{node_name}"
    return type(node).__name__


def _node_fork_terminator(node: object) -> SfcTerminator | None:
    fork = getattr(node, "fork", None)
    if not isinstance(fork, SFCFork):
        return None
    return SfcTerminator(kind="SFCFork", targets=tuple(fork.targets))


def _is_forward_fork_target(node: object, terminator: SfcTerminator) -> bool:
    """A later node named by the fork is reachable through that fork."""
    if terminator.kind != "SFCFork" or not terminator.targets:
        return False
    name = getattr(node, "name", None)
    if not name:
        return False
    folded = name.casefold()
    return any(target.casefold() == folded for target in terminator.targets)


def _is_empty_step(node: object) -> bool:
    """A step with no code and no fork; the grammar needs one to close a branch."""
    if not isinstance(node, SFCStep) or node.fork is not None:
        return False
    code = node.code
    return not (code.enter or code.active or code.exit)


def _inspect_sfc_linear_nodes(
    findings: list[SfcReachabilityFinding],
    nodes: SequenceABC[object] | None,
    module_path: list[str],
    sequence_name: str,
    branch_path: tuple[int, ...] = (),
    *,
    enclosing_parallel: bool = False,
) -> None:
    terminated_by: SfcTerminator | None = None
    linear_nodes = list(nodes or [])
    last_index = len(linear_nodes) - 1
    for index, node in enumerate(linear_nodes):
        if terminated_by is not None:
            closes_parallel_branch = (
                enclosing_parallel and index == last_index and terminated_by.kind == "SFCFork" and _is_empty_step(node)
            )
            if closes_parallel_branch:
                continue
            if _is_forward_fork_target(node, terminated_by):
                terminated_by = None
            else:
                findings.append(
                    SfcReachabilityFinding(
                        module_path=tuple(module_path),
                        sequence_name=sequence_name,
                        branch_path=branch_path,
                        node_index=index,
                        node_label=_sequence_node_label(node),
                        node_type=type(node).__name__,
                        terminated_by=terminated_by,
                    )
                )
                continue

        if isinstance(node, SFCAlternative | SFCParallel):
            for branch_index, branch in enumerate(node.branches or []):
                _inspect_sfc_linear_nodes(
                    findings,
                    branch,
                    module_path,
                    sequence_name,
                    (*branch_path, branch_index),
                    enclosing_parallel=isinstance(node, SFCParallel),
                )
            continue

        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            _inspect_sfc_linear_nodes(
                findings,
                node.body,
                module_path,
                sequence_name,
                branch_path,
                enclosing_parallel=enclosing_parallel,
            )
            continue

        fork_terminator = _node_fork_terminator(node)
        if fork_terminator is not None:
            terminated_by = fork_terminator


def collect_sfc_reachability_findings(
    base_picture: BasePicture,
    *,
    moduletype_filter: TargetOriginFilter | None = None,
) -> list[SfcReachabilityFinding]:
    findings: list[SfcReachabilityFinding] = []

    for module_path, modulecode in iter_modulecodes(base_picture, moduletype_filter=moduletype_filter):
        if modulecode is None:
            continue
        for sequence in modulecode.sequences or []:
            _inspect_sfc_linear_nodes(findings, sequence.code, module_path, sequence.name or "")

    return findings


def _collect_initial_step_issues(
    base_picture: BasePicture,
    *,
    moduletype_filter: TargetOriginFilter | None = None,
) -> list[Issue]:
    issues: list[Issue] = []
    for module_path, modulecode in iter_modulecodes(base_picture, moduletype_filter=moduletype_filter):
        if modulecode is None:
            continue
        for sequence in modulecode.sequences or []:
            first = next((node for node in sequence.code or [] if not isinstance(node, CodeComment)), None)
            if isinstance(first, SFCStep) and first.kind.casefold() == "init":
                continue
            name = sequence.name or "<unnamed>"
            issues.append(
                Issue(
                    kind="sfc_missing_initial_step",
                    message=f"Sequence {name!r} must begin with an initial step (SEQINITSTEP).",
                    module_path=module_path.copy(),
                    explanation="The initial step establishes the sequence's entry state before transitions or normal steps run.",
                    suggestion="Move the existing initial step to the start, or add a SEQINITSTEP if it is missing.",
                    data={"sequence": name, "site": f"SQ:{name}", "context": "Missing initial step at sequence start"},
                )
            )
    return issues


def _collect_fork_issues(
    base_picture: BasePicture,
    *,
    moduletype_filter: TargetOriginFilter | None = None,
    selected_issue_kinds: AbstractSet[str] | None = None,
) -> list[Issue]:
    issues: list[Issue] = []
    for finding in collect_sfc_fork_findings(base_picture, moduletype_filter=moduletype_filter):
        if selected_issue_kinds is not None and finding.kind not in selected_issue_kinds:
            continue
        host = finding.host_name or "<unnamed>"
        host_type = finding.host_type.capitalize()
        sequence = finding.sequence_name or "<unnamed>"
        target_sequence = finding.target_sequence or "<unnamed>"
        if finding.kind == SFC_CROSS_SEQUENCE_FORK_KIND:
            message = (
                f"{host_type} {host!r} in sequence {sequence!r} forks to "
                f"{finding.target!r} in sequence {target_sequence!r}."
            )
            explanation = (
                "A fork into another sequence bypasses that sequence's own entry step, "
                "so its initial step and state may never run."
            )
            suggestion = "Fork within the same sequence, or start the other sequence through its own initial step."
        elif finding.host_name and finding.target.casefold() == finding.host_name.casefold():
            message = f"{host_type} {host!r} in sequence {sequence!r} forks back to itself."
            explanation = (
                "A fork back to the same step re-enters a step that is already active, "
                "which can repeat its ENTER/EXIT code in the same scan or create a tight loop."
            )
            suggestion = (
                "Name a different target, or remove the fork when the transition already continues the sequence."
            )
        else:
            message = f"{host_type} {host!r} in sequence {sequence!r} forks back to its own step {finding.target!r}."
            explanation = (
                "The transition forks back to the step it belongs to, so the step never "
                "advances to the rest of the sequence."
            )
            suggestion = (
                "Remove the fork when the transition should continue forward, or target the next step explicitly."
            )
        issues.append(
            Issue(
                kind=finding.kind,
                message=message,
                module_path=list(finding.module_path),
                data={
                    "sequence": sequence,
                    "host": finding.host_name,
                    "host_type": finding.host_type,
                    "target": finding.target,
                    "target_sequence": target_sequence,
                    "site": f"SQ:{sequence}",
                    "context": finding.host_label,
                },
                explanation=explanation,
                suggestion=suggestion,
            )
        )
    return issues


def _format_terminator(terminated_by: SfcTerminator) -> str:
    if terminated_by.targets:
        rendered_targets = ", ".join(repr(target) for target in terminated_by.targets)
        if rendered_targets:
            return f"{terminated_by.kind} targeting {rendered_targets}"
    return terminated_by.kind


def analyze_sfc(
    base_picture: BasePicture,
    analysis_context: AnalysisContext | None = None,
    selected_issue_kinds: AbstractSet[str] | None = None,
) -> SimpleReport:
    normalized_selected_issue_kinds = frozenset(selected_issue_kinds) if selected_issue_kinds is not None else None

    def _should_collect_any_issue_kinds(issue_kinds: frozenset[str]) -> bool:
        return normalized_selected_issue_kinds is None or bool(normalized_selected_issue_kinds & issue_kinds)

    moduletype_filter = build_target_origin_filter_for_basepicture(
        base_picture,
        analyzed_target_is_library=bool(analysis_context is not None and analysis_context.target_is_library),
    )

    issues: list[Issue] = []
    if _should_collect_any_issue_kinds(_SFC_INITIAL_STEP_ISSUE_KINDS):
        issues.extend(_collect_initial_step_issues(base_picture, moduletype_filter=moduletype_filter))
    if _should_collect_any_issue_kinds(_SFC_REACHABILITY_ISSUE_KINDS):
        for finding in collect_sfc_reachability_findings(base_picture, moduletype_filter=moduletype_filter):
            branch_context = _format_branch_path(finding.branch_path)
            terminator = _format_terminator(finding.terminated_by)
            data = {
                "sequence": finding.sequence_name,
                "branch_path": list(finding.branch_path),
                "node_index": finding.node_index,
                "node_label": finding.node_label,
                "node_type": finding.node_type,
                "terminated_by": finding.terminated_by.to_data(),
                "site": f"SQ:{finding.sequence_name}{branch_context}",
                "context": finding.node_label,
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

    if _should_collect_any_issue_kinds(_SFC_TRANSITION_LOGIC_ISSUE_KINDS):
        issues.extend(_collect_transition_logic_issues(base_picture, moduletype_filter=moduletype_filter))
    if _should_collect_any_issue_kinds(SFC_FORK_ISSUE_KINDS):
        issues.extend(
            _collect_fork_issues(
                base_picture,
                moduletype_filter=moduletype_filter,
                selected_issue_kinds=normalized_selected_issue_kinds,
            )
        )

    return SimpleReport(name=base_picture.header.name, issues=issues)


__all__ = [
    "SfcReachabilityFinding",
    "SfcTerminator",
    "analyze_sfc",
    "collect_sfc_reachability_findings",
    "iter_modulecodes",
]
