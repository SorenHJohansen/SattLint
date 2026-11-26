"""SEQFORK target checks: a self-loop or a jump into another sequence.

The parser resolves fork targets across the whole module code block, so a
target can legally name an element in a different sequence. These checks report
the two shapes that resolver accepts but that a step diagram normally does not
intend: a host that forks back to its own step, and a fork that leaves its
sequence.
"""

from __future__ import annotations

from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass
from typing import Literal

from sattlint.parser_api import (
    BasePicture,
    ModuleCode,
    SFCAlternative,
    SFCBodyItem,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
)

from ..shared.target_origin import TargetOriginFilter
from ._sfc_module_walk import iter_sfc_modulecodes

SFC_SELF_FORK_KIND = "sfc_self_fork"
SFC_CROSS_SEQUENCE_FORK_KIND = "sfc_cross_sequence_fork"
SFC_FORK_ISSUE_KINDS: frozenset[str] = frozenset({SFC_SELF_FORK_KIND, SFC_CROSS_SEQUENCE_FORK_KIND})

type SfcHostType = Literal["step", "transition"]


@dataclass(frozen=True, slots=True)
class SfcNamedElement:
    name: str
    kind: SfcHostType
    sequence_index: int
    sequence_name: str | None


@dataclass(frozen=True, slots=True)
class SfcNameRegistry:
    """Legal fork targets and the parser's module-wide occurrence count."""

    elements: dict[str, tuple[SfcNamedElement, ...]]
    counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class SfcForkFinding:
    kind: str
    module_path: tuple[str, ...]
    sequence_index: int
    sequence_name: str | None
    host_label: str
    host_name: str | None
    host_type: SfcHostType
    target: str
    target_sequence_index: int | None
    target_sequence: str | None


def collect_sfc_fork_findings(
    base_picture: BasePicture,
    *,
    moduletype_filter: TargetOriginFilter | None = None,
) -> list[SfcForkFinding]:
    findings: list[SfcForkFinding] = []
    for module_path, modulecode in iter_sfc_modulecodes(base_picture, moduletype_filter=moduletype_filter):
        if modulecode is None:
            continue
        registry = _name_registry(modulecode)
        for index, sequence in enumerate(modulecode.sequences or []):
            _scan_forks(
                sequence.code,
                index,
                sequence.name,
                registry,
                None,
                tuple(module_path),
                findings,
            )
    return _dedupe(findings)


def _name_registry(modulecode: ModuleCode) -> SfcNameRegistry:
    elements: dict[str, list[SfcNamedElement]] = {}
    counts: dict[str, int] = {}
    for index, sequence in enumerate(modulecode.sequences or []):
        _collect_named_elements(sequence.code, index, sequence.name, elements, counts)
    return SfcNameRegistry(
        elements={key: tuple(value) for key, value in elements.items()},
        counts=counts,
    )


def _record_name(counts: dict[str, int], name: str | None) -> None:
    if not name:
        return
    key = name.casefold()
    counts[key] = counts.get(key, 0) + 1


def _add_element(
    elements: dict[str, list[SfcNamedElement]],
    name: str | None,
    kind: SfcHostType,
    sequence_index: int,
    sequence_name: str | None,
) -> None:
    if not name:
        return
    elements.setdefault(name.casefold(), []).append(
        SfcNamedElement(
            name=name,
            kind=kind,
            sequence_index=sequence_index,
            sequence_name=sequence_name,
        )
    )


def _collect_named_elements(
    nodes: SequenceABC[SFCBodyItem],
    sequence_index: int,
    sequence_name: str | None,
    elements: dict[str, list[SfcNamedElement]],
    counts: dict[str, int],
) -> None:
    for node in nodes:
        if isinstance(node, SFCStep):
            _record_name(counts, node.name)
            _add_element(elements, node.name, "step", sequence_index, sequence_name)
            continue
        if isinstance(node, SFCTransition):
            _record_name(counts, node.name)
            _add_element(elements, node.name, "transition", sequence_index, sequence_name)
            continue
        if isinstance(node, SFCAlternative | SFCParallel):
            for branch in node.branches or []:
                _collect_named_elements(branch, sequence_index, sequence_name, elements, counts)
            continue
        if isinstance(node, SFCSubsequence):
            # A plain SUBSEQUENCE name is not a legal target, but the parser
            # still counts it when deciding whether a target is ambiguous.
            _record_name(counts, node.name)
            if node.kind == "substep":
                _add_element(elements, node.name, "step", sequence_index, sequence_name)
            _collect_named_elements(node.body or [], sequence_index, sequence_name, elements, counts)
            continue
        if isinstance(node, SFCTransitionSub):
            _record_name(counts, node.name)
            _add_element(elements, node.name, "transition", sequence_index, sequence_name)
            _collect_named_elements(node.body or [], sequence_index, sequence_name, elements, counts)


def _scan_forks(
    nodes: SequenceABC[SFCBodyItem],
    sequence_index: int,
    sequence_name: str | None,
    registry: SfcNameRegistry,
    owning_step: SFCStep | SFCSubsequence | None,
    module_path: tuple[str, ...],
    findings: list[SfcForkFinding],
) -> None:
    for node in nodes:
        if isinstance(node, SFCStep):
            _check_fork(
                node,
                "step",
                sequence_index,
                sequence_name,
                registry,
                node,
                module_path,
                findings,
            )
            owning_step = node
            continue
        if isinstance(node, SFCTransition):
            _check_fork(
                node,
                "transition",
                sequence_index,
                sequence_name,
                registry,
                owning_step,
                module_path,
                findings,
            )
            owning_step = None
            continue
        if isinstance(node, SFCAlternative):
            for branch in node.branches or []:
                _scan_forks(
                    branch,
                    sequence_index,
                    sequence_name,
                    registry,
                    owning_step,
                    module_path,
                    findings,
                )
            owning_step = None
            continue
        if isinstance(node, SFCParallel):
            for branch in node.branches or []:
                _scan_forks(
                    branch,
                    sequence_index,
                    sequence_name,
                    registry,
                    None,
                    module_path,
                    findings,
                )
            owning_step = None
            continue
        if isinstance(node, SFCSubsequence):
            _scan_forks(
                node.body or [],
                sequence_index,
                sequence_name,
                registry,
                None,
                module_path,
                findings,
            )
            owning_step = node if node.kind == "substep" else None
            continue
        if isinstance(node, SFCTransitionSub):
            _scan_forks(
                node.body or [],
                sequence_index,
                sequence_name,
                registry,
                owning_step,
                module_path,
                findings,
            )
            owning_step = None


def _check_fork(
    host: SFCStep | SFCTransition,
    host_type: SfcHostType,
    sequence_index: int,
    sequence_name: str | None,
    registry: SfcNameRegistry,
    owning_step: SFCStep | SFCSubsequence | None,
    module_path: tuple[str, ...],
    findings: list[SfcForkFinding],
) -> None:
    fork = host.fork
    if fork is None:
        return
    host_name = host.name
    host_label = _host_label(host, host_type)
    for target in fork.targets:
        target_key = target.casefold()
        if registry.counts.get(target_key, 0) != 1:
            continue
        matches = registry.elements.get(target_key, ())
        if len(matches) != 1:
            continue
        match = matches[0]
        if match.sequence_index != sequence_index:
            findings.append(
                _finding(
                    SFC_CROSS_SEQUENCE_FORK_KIND,
                    module_path,
                    sequence_index,
                    sequence_name,
                    host_label,
                    host_name,
                    host_type,
                    match,
                )
            )
            continue
        if host_name and match.kind == host_type and target_key == host_name.casefold():
            findings.append(
                _finding(
                    SFC_SELF_FORK_KIND,
                    module_path,
                    sequence_index,
                    sequence_name,
                    host_label,
                    host_name,
                    host_type,
                    match,
                )
            )
            continue
        if (
            host_type == "transition"
            and owning_step is not None
            and owning_step.name
            and match.kind == "step"
            and target_key == owning_step.name.casefold()
        ):
            findings.append(
                _finding(
                    SFC_SELF_FORK_KIND,
                    module_path,
                    sequence_index,
                    sequence_name,
                    host_label,
                    host_name,
                    host_type,
                    match,
                )
            )


def _finding(
    kind: str,
    module_path: tuple[str, ...],
    sequence_index: int,
    sequence_name: str | None,
    host_label: str,
    host_name: str | None,
    host_type: SfcHostType,
    match: SfcNamedElement,
) -> SfcForkFinding:
    return SfcForkFinding(
        kind=kind,
        module_path=module_path,
        sequence_index=sequence_index,
        sequence_name=sequence_name,
        host_label=host_label,
        host_name=host_name,
        host_type=host_type,
        target=match.name,
        target_sequence_index=match.sequence_index,
        target_sequence=match.sequence_name,
    )


def _host_label(host: SFCStep | SFCTransition, host_type: SfcHostType) -> str:
    name = host.name or "<unnamed>"
    return f"{host_type} {name!r}"


def _dedupe(findings: list[SfcForkFinding]) -> list[SfcForkFinding]:
    unique: dict[tuple[object, ...], SfcForkFinding] = {}
    for finding in findings:
        key = (
            finding.kind,
            finding.module_path,
            finding.sequence_index,
            finding.sequence_name,
            finding.host_label,
            finding.target,
            finding.target_sequence_index,
            finding.target_sequence,
        )
        unique.setdefault(key, finding)
    return sorted(
        unique.values(),
        key=lambda finding: (
            finding.module_path,
            finding.sequence_index,
            finding.sequence_name or "",
            finding.host_label,
            finding.kind,
            finding.target,
        ),
    )


__all__ = [
    "SFC_CROSS_SEQUENCE_FORK_KIND",
    "SFC_FORK_ISSUE_KINDS",
    "SFC_SELF_FORK_KIND",
    "SfcForkFinding",
    "SfcNameRegistry",
    "SfcNamedElement",
    "collect_sfc_fork_findings",
]
