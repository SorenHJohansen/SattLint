# pyright: reportPrivateUsage=false

"""SFC analysis for structural dead paths, write races, and state conflicts."""

from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCSubsequence,
    SFCTransitionSub,
)

from ..framework import AnalysisContext, Issue, SimpleReport
from ..shared.target_origin import TargetOriginFilter, build_target_origin_filter_for_basepicture
from ..variables import VariablesAnalyzer
from ._sfc_collectors import _SfcAccessCollector
from ._sfc_guard_logic import (
    _collect_transition_logic_issues,
    _format_branch_path,
)
from ._sfc_module_walk import iter_sfc_modulecodes

_SFC_REACHABILITY_ISSUE_KINDS = frozenset({"sfc_unreachable_transition", "sfc_unreachable_sequence_node"})
_SFC_TRANSITION_LOGIC_ISSUE_KINDS = frozenset({"sfc_duplicate_transition_guard"})


@dataclass(frozen=True)
class SfcReachabilityFinding:
    module_path: tuple[str, ...]
    sequence_name: str
    branch_path: tuple[int, ...]
    node_index: int
    node_label: str
    node_type: str
    terminated_by: dict[str, Any]


def _sequence_node_label(node: object) -> str:
    node_name = getattr(node, "name", None)
    if node_name:
        return f"{type(node).__name__}:{node_name}"
    if isinstance(node, SFCFork):
        return f"SFCFork:{','.join(node.targets)}"
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
            terminated_by = {"kind": "SFCFork", "targets": list(node.targets)}
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
    *,
    moduletype_filter: TargetOriginFilter | None = None,
) -> list[SfcReachabilityFinding]:
    findings: list[SfcReachabilityFinding] = []

    for module_path, modulecode in iter_sfc_modulecodes(base_picture, moduletype_filter=moduletype_filter):
        if modulecode is None:
            continue
        for sequence in modulecode.sequences or []:
            _inspect_sfc_linear_nodes(findings, sequence.code, module_path, sequence.name or "")

    return findings


def _format_terminator(terminated_by: dict[str, Any]) -> str:
    terminator = str(terminated_by.get("kind", "an earlier terminating node"))
    targets = terminated_by.get("targets")
    if isinstance(targets, list | tuple) and targets:
        target_texts: list[str] = []
        for raw_target in cast(list[object] | tuple[object, ...], targets):
            if isinstance(raw_target, str):
                target_texts.append(repr(raw_target))
        rendered_targets = ", ".join(target_texts)
        if rendered_targets:
            return f"{terminator} targeting {rendered_targets}"
    return terminator


def get_variables_collector_class() -> type[VariablesAnalyzer]:
    """Return the SFC-aware variables analyzer class.

    When SFC parallel-branch collection is enabled, the canonical ``variables``
    analyzer is run as this class so parallel-write data is recorded during the
    single canonical traversal instead of a separate SFC walk.
    """
    return _SfcAccessCollector


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
                "terminated_by": dict(finding.terminated_by),
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

    return SimpleReport(name=base_picture.header.name, issues=issues)


__all__ = [
    "SfcReachabilityFinding",
    "analyze_sfc",
    "collect_sfc_reachability_findings",
    "get_variables_collector_class",
    "iter_sfc_modulecodes",
]
