"""Finding flattening, stable identifiers, filtering, and grouping for the CLI."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, replace

from ..analyzers.catalog import canonicalize_analyzer_keys
from ..application.findings import AnalysisFinding
from ..runs import RunRecord, list_runs, load_run
from ._output import CliError
from ._payloads import FindingGroup, FindingPayload, FindingSummary, GroupBy, RunPayload

_PROJECT_ANALYZER_TARGET = ""


@dataclass(frozen=True, slots=True)
class FlatFinding:
    """One deduplicated finding with its target/analyzer context."""

    id: str
    target: str
    analyzer_key: str
    analyzer_name: str
    finding: AnalysisFinding
    module_path: tuple[str, ...]
    site: str | None
    context: str | None
    occurrence_count: int

    @property
    def module(self) -> str:
        return ".".join(self.module_path)


def _finding_site(finding: AnalysisFinding) -> str | None:
    raw = finding.data.get("site")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _finding_context(finding: AnalysisFinding) -> str | None:
    raw = finding.data.get("relation", finding.data.get("context"))
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _stable_repr(value: object) -> str:
    """A repr that never includes a memory address."""
    return f"<{type(value).__name__}>"


def _finding_data_key(finding: AnalysisFinding) -> str:
    """A stable fingerprint of the finding payload.

    Two findings can share a message and site but carry different detail (for
    example different previous writes). Collapsing them would keep only the
    first payload, so the data payload is part of finding identity.
    """
    try:
        return json.dumps(finding.data, sort_keys=True, default=_stable_repr, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(finding.data)


def _finding_id(
    *,
    target: str,
    analyzer_key: str,
    finding: AnalysisFinding,
    site: str | None,
    context: str | None,
) -> str:
    parts = (
        target,
        analyzer_key,
        finding.kind,
        finding.rule_id or "",
        ".".join(finding.module_path),
        site or "",
        context or "",
        finding.message,
        _finding_data_key(finding),
    )
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"f_{digest[:12]}"


def flat_findings(record: RunRecord) -> list[FlatFinding]:
    """Flatten a run into deterministically ordered findings.

    Repeated identical findings (same target, analyzer, kind, rule, module,
    site, context, and message) collapse into one entry with an occurrence
    count.
    """
    counts: dict[tuple[str, str, str, str | None, tuple[str, ...], str | None, str | None, str, str], int] = {}
    representatives: dict[
        tuple[str, str, str, str | None, tuple[str, ...], str | None, str | None, str, str],
        FlatFinding,
    ] = {}
    project_analyzers = getattr(record, "project_analyzers", ())
    targets_with_analyzers = [
        *((target.target_name, analyzer) for target in record.targets for analyzer in target.analyzers),
        *((_PROJECT_ANALYZER_TARGET, analyzer) for analyzer in project_analyzers),
    ]
    for target_name, analyzer in targets_with_analyzers:
        for finding in analyzer.findings:
            site = _finding_site(finding)
            context = _finding_context(finding)
            key = (
                target_name,
                analyzer.key,
                finding.kind,
                finding.rule_id,
                finding.module_path,
                site,
                context,
                finding.message,
                _finding_data_key(finding),
            )
            counts[key] = counts.get(key, 0) + 1
            if key not in representatives:
                representatives[key] = FlatFinding(
                    id=_finding_id(
                        target=target_name,
                        analyzer_key=analyzer.key,
                        finding=finding,
                        site=site,
                        context=context,
                    ),
                    target=target_name,
                    analyzer_key=analyzer.key,
                    analyzer_name=analyzer.name,
                    finding=finding,
                    module_path=finding.module_path,
                    site=site,
                    context=context,
                    occurrence_count=0,
                )
    flattened = [replace(entry, occurrence_count=counts[key]) for key, entry in representatives.items()]
    flattened.sort(
        key=lambda item: (
            item.target.casefold(),
            item.module.casefold(),
            item.analyzer_key.casefold(),
            item.finding.kind.casefold(),
            (item.site or "").casefold(),
            (item.finding.rule_id or "").casefold(),
            item.finding.message.casefold(),
        )
    )
    return flattened


def finding_payload(finding: FlatFinding) -> FindingPayload:
    analysis = finding.finding
    return {
        "id": finding.id,
        "target": finding.target,
        "analyzer": finding.analyzer_key,
        "analyzer_name": finding.analyzer_name,
        "kind": analysis.kind,
        "rule_id": analysis.rule_id,
        "module_path": list(finding.module_path),
        "module": finding.module,
        "site": finding.site,
        "context": finding.context,
        "message": analysis.message,
        "explanation": analysis.explanation,
        "suggestion": analysis.suggestion,
        "occurrence_count": finding.occurrence_count,
        "data": dict(analysis.data),
    }


@dataclass(frozen=True, slots=True)
class FindingFilters:
    targets: tuple[str, ...] = ()
    analyzers: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    exact_module: bool = False
    kinds: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()


def _normalized_module_pattern(value: str) -> str:
    return value.strip().replace("/", ".").removesuffix(".*").strip(".").casefold()


def _matches_module(module: str, patterns: tuple[str, ...], *, exact: bool) -> bool:
    if not patterns:
        return True
    normalized = module.casefold()
    for raw in patterns:
        pattern = _normalized_module_pattern(raw)
        if not pattern:
            continue
        if normalized == pattern:
            return True
        if not exact and normalized.startswith(f"{pattern}."):
            return True
    return False


def filter_findings(findings: Iterable[FlatFinding], filters: FindingFilters) -> list[FlatFinding]:
    targets = {value.casefold() for value in filters.targets}
    analyzers = set(canonicalize_analyzer_keys(list(filters.analyzers)))
    kinds = {value.casefold() for value in filters.kinds}
    rules = {value.casefold() for value in filters.rules}
    selected: list[FlatFinding] = []
    for finding in findings:
        if targets and finding.target.casefold() not in targets:
            continue
        if analyzers and finding.analyzer_key not in analyzers:
            continue
        if kinds and finding.finding.kind.casefold() not in kinds:
            continue
        if rules and (finding.finding.rule_id or finding.finding.kind).casefold() not in rules:
            continue
        if not _matches_module(finding.module, filters.modules, exact=filters.exact_module):
            continue
        selected.append(finding)
    return selected


def group_findings(findings: Iterable[FlatFinding], group_by: GroupBy) -> list[FindingGroup]:
    if group_by == "none":
        return []

    def _group_key(item: FlatFinding) -> str:
        if group_by == "module":
            return item.module or "(unknown)"
        if group_by == "analyzer":
            return item.analyzer_key
        return item.finding.kind

    buckets: dict[str, list[str]] = {}
    for finding in findings:
        buckets.setdefault(_group_key(finding), []).append(finding.id)
    return [
        {"key": key, "group_by": group_by, "count": len(ids), "finding_ids": ids}
        for key, ids in sorted(buckets.items(), key=lambda item: item[0].casefold())
    ]


def _same_project_path(left: str, right: str) -> bool:
    return os.path.normcase(left) == os.path.normcase(right)


def resolve_run(run_id: str | None, *, project_path: str | None = None) -> RunRecord:
    selector = "latest" if run_id is None else run_id.strip()
    if not selector:
        raise CliError(
            "Run selector is empty. Use 'latest', a run id, or a unique run-id prefix.",
            code="run_invalid",
            exit_code=2,
        )
    summaries = list_runs()
    if not summaries:
        raise CliError(
            "No analysis runs are available. Run 'sattlint analyze' first.",
            code="no_runs",
            exit_code=2,
        )
    if selector == "latest":
        # `latest` means the newest run for the project being inspected, not
        # the newest run on the machine.
        if project_path:
            matching = [
                summary
                for summary in summaries
                if summary.project_path and _same_project_path(summary.project_path, project_path)
            ]
            if matching:
                summaries = matching
        # The newest record can be unreadable (truncated by a crash, written by
        # an older schema). Fall back to the newest record that loads.
        for summary in summaries:
            record = load_run(summary.run_id)
            if record is not None:
                return record
        raise CliError(
            "No stored analysis run could be loaded.",
            code="run_not_found",
            exit_code=2,
            details={"available": [summary.run_id for summary in summaries[:5]]},
        )
    if any(summary.run_id == selector for summary in summaries):
        selected = selector
    else:
        matches = [summary.run_id for summary in summaries if summary.run_id.startswith(selector)]
        if len(matches) > 1:
            raise CliError(
                f"Run prefix {selector!r} is ambiguous.",
                code="run_ambiguous",
                exit_code=2,
                details={"matches": matches[:5]},
            )
        if not matches:
            raise CliError(
                f"Run {selector!r} was not found.",
                code="run_not_found",
                exit_code=2,
                details={"available": [summary.run_id for summary in summaries[:5]]},
            )
        selected = matches[0]
    record = load_run(selected)
    if record is None:
        raise CliError(
            f"Run {selected!r} could not be loaded.",
            code="run_not_found",
            exit_code=2,
        )
    return record


def run_payload(record: RunRecord) -> RunPayload:
    return {
        "run_id": record.run_id,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "project_tag": record.project_tag,
        "project_path": record.project_path,
        "selected_analyzers": list(record.selected_analyzers),
        "cancelled": record.cancelled,
    }


def finding_summary(findings: Iterable[FlatFinding]) -> FindingSummary:
    items = list(findings)
    by_analyzer: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_module: dict[str, int] = {}
    for finding in items:
        by_analyzer[finding.analyzer_key] = by_analyzer.get(finding.analyzer_key, 0) + 1
        by_kind[finding.finding.kind] = by_kind.get(finding.finding.kind, 0) + 1
        module = finding.module or "(unknown)"
        by_module[module] = by_module.get(module, 0) + 1
    return {
        "findings": len(items),
        "occurrences": sum(finding.occurrence_count for finding in items),
        "by_analyzer": dict(sorted(by_analyzer.items())),
        "by_kind": dict(sorted(by_kind.items())),
        "by_module": dict(sorted(by_module.items())),
    }


__all__ = [
    "FindingFilters",
    "FlatFinding",
    "filter_findings",
    "finding_payload",
    "finding_summary",
    "flat_findings",
    "group_findings",
    "resolve_run",
    "run_payload",
]
