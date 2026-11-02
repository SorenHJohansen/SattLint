"""Finding flattening, stable identifiers, filtering, and grouping for the CLI."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, replace
from typing import Any

from ..analyzers.catalog import canonicalize_analyzer_keys
from ..application.findings import AnalysisFinding
from ..runs import RunRecord, list_runs, load_run
from ._output import CliError


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
    raw = finding.data.get("context")
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


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
    )
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"f_{digest[:12]}"


def flat_findings(record: RunRecord) -> list[FlatFinding]:
    """Flatten a run into deduplicated, deterministically ordered findings.

    Identical findings (same target, analyzer, kind, rule, module, site,
    context, and message) are represented once with an occurrence count.
    """
    counts: dict[tuple[str, str, str, str | None, tuple[str, ...], str | None, str | None, str], int] = {}
    representatives: dict[
        tuple[str, str, str, str | None, tuple[str, ...], str | None, str | None, str],
        FlatFinding,
    ] = {}
    for target in record.targets:
        for analyzer in target.analyzers:
            for finding in analyzer.findings:
                site = _finding_site(finding)
                context = _finding_context(finding)
                key = (
                    target.target_name,
                    analyzer.key,
                    finding.kind,
                    finding.rule_id,
                    finding.module_path,
                    site,
                    context,
                    finding.message,
                )
                counts[key] = counts.get(key, 0) + 1
                if key not in representatives:
                    representatives[key] = FlatFinding(
                        id=_finding_id(
                            target=target.target_name,
                            analyzer_key=analyzer.key,
                            finding=finding,
                            site=site,
                            context=context,
                        ),
                        target=target.target_name,
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


def finding_payload(finding: FlatFinding) -> dict[str, Any]:
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
        if rules and (finding.finding.rule_id or "").casefold() not in rules:
            continue
        if not _matches_module(finding.module, filters.modules, exact=filters.exact_module):
            continue
        selected.append(finding)
    return selected


def group_findings(findings: Iterable[FlatFinding], group_by: str) -> list[dict[str, Any]]:
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


def resolve_run(run_id: str | None) -> RunRecord:
    selector = (run_id or "latest").strip() or "latest"
    summaries = list_runs()
    if not summaries:
        raise CliError(
            "No analysis runs are available. Run 'sattlint analyze' first.",
            code="no_runs",
            exit_code=2,
        )
    if selector == "latest":
        selected = summaries[0].run_id
    elif any(summary.run_id == selector for summary in summaries):
        selected = selector
    else:
        matches = [summary.run_id for summary in summaries if summary.run_id.startswith(selector)]
        if len(matches) != 1:
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


def run_payload(record: RunRecord) -> dict[str, object]:
    return {
        "run_id": record.run_id,
        "started_at": record.started_at,
        "finished_at": record.finished_at,
        "project_tag": record.project_tag,
        "selected_analyzers": list(record.selected_analyzers),
        "cancelled": record.cancelled,
    }


def finding_summary(findings: Iterable[FlatFinding]) -> dict[str, object]:
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
