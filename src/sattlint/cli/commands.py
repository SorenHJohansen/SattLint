"""Headless CLI commands for agents and automation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from ..analyzers.catalog import (
    canonicalize_analyzer_keys,
    get_actual_cli_analyzer_keys,
    get_default_analyzer_catalog,
)
from ..application.analyze import collect_checks_result
from ..application.checks import ChecksRunResult, build_run_record
from ..application.findings import kind_human_label
from ..config.types import ConfigDict
from ..project.support import TargetLoadError
from ..runs import RunRecord
from ._findings import (
    FindingFilters,
    FlatFinding,
    filter_findings,
    finding_payload,
    finding_summary,
    flat_findings,
    group_findings,
    resolve_run,
    run_payload,
)
from ._output import (
    SCHEMA_VERSION,
    CliError,
    emit_json,
    emit_ndjson,
    emit_text,
    output_path,
)
from ._payloads import (
    AnalyzePayload,
    AnalyzerInfo,
    AnalyzersListPayload,
    AnalyzeSummary,
    FindingGroup,
    FindingPayload,
    FindingsFilters,
    FindingsPayload,
    FindingsSummary,
    GroupBy,
    ProjectInfo,
    ProjectShowPayload,
    ShowPayload,
)
from ._project import effective_project_config, project_payload, resolve_project_file


@dataclass(frozen=True, slots=True)
class _OutputOptions:
    output_format: str
    output: Path | None
    quiet: bool


@dataclass(frozen=True, slots=True)
class _AnalyzeOptions:
    output: _OutputOptions
    project: str | None
    analyzers: tuple[str, ...]
    targets: tuple[str, ...]
    modules: tuple[str, ...]
    use_cache: bool
    persist_run: bool
    fail_on_findings: bool


def _output_options(args: argparse.Namespace) -> _OutputOptions:
    return _OutputOptions(
        output_format=str(args.format or "text"),
        output=output_path(args.output),
        quiet=bool(args.quiet),
    )


def _emit_document(options: _OutputOptions, *, payload: Mapping[str, object], text_lines: Iterable[str]) -> None:
    if options.output_format == "json":
        emit_json(payload, output=options.output)
    else:
        emit_text(text_lines, output=options.output)


def _emit_findings(
    options: _OutputOptions,
    *,
    payload: Mapping[str, object],
    findings: Iterable[FlatFinding],
    text_lines: Iterable[str],
) -> None:
    if options.output_format == "json":
        emit_json(payload, output=options.output)
    elif options.output_format == "ndjson":
        emit_ndjson((finding_payload(finding) for finding in findings), output=options.output)
    else:
        emit_text(text_lines, output=options.output)


def _analyze_options(args: argparse.Namespace) -> _AnalyzeOptions:
    return _AnalyzeOptions(
        output=_output_options(args),
        project=str(args.project) if args.project else None,
        analyzers=tuple(str(value) for value in args.analyzer),
        targets=tuple(str(value) for value in args.target),
        modules=tuple(str(value) for value in args.module),
        use_cache=not bool(args.no_cache),
        persist_run=not bool(args.no_save),
        fail_on_findings=str(args.fail_on) == "any",
    )


def command_project_show(args: argparse.Namespace) -> int:
    project = resolve_project_file(args.project)
    options = _output_options(args)
    project_info = project_payload(project)
    payload: ProjectShowPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "project show",
        "project": project_info,
    }
    _emit_document(options, payload=payload, text_lines=_project_text(project_info))
    return 0


def _project_text(project: ProjectInfo) -> list[str]:
    paths = project["paths"]
    return [
        f"Project: {project['path']}",
        f"Root:    {project['root']}",
        f"Mode:    {project['mode']}",
        f"Targets: {', '.join(project['targets']) or '(none)'}",
        f"program_dir: {paths['program_dir']}",
        f"ABB_lib_dir: {paths['ABB_lib_dir']}",
        f"icf_dir: {paths['icf_dir']}",
        f"other_lib_dirs: {', '.join(paths['other_lib_dirs']) or '(none)'}",
        f"Runs:    {project['runs_dir']}",
        f"Review:  {project['review_output_dir']}",
    ]


def command_analyzers_list(args: argparse.Namespace) -> int:
    catalog = get_default_analyzer_catalog()
    default_keys = set(get_actual_cli_analyzer_keys())
    analyzers: list[AnalyzerInfo] = []
    for metadata in catalog.analyzers:
        entry: AnalyzerInfo = {
            **metadata.to_dict(),
            "default": metadata.spec.key in default_keys,
        }
        analyzers.append(entry)
    options = _output_options(args)
    payload: AnalyzersListPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "analyzers list",
        "analyzers": analyzers,
    }
    _emit_document(options, payload=payload, text_lines=_analyzers_text(analyzers))
    return 0


def _analyzers_text(analyzers: list[AnalyzerInfo]) -> list[str]:
    lines: list[str] = []
    for entry in analyzers:
        marker = "*" if entry["default"] else " "
        lines.append(f"{marker} {entry['key']:<24} {entry['category']:<12} {entry['name']}")
    return lines


def _resolve_analyzer_keys(requested: tuple[str, ...]) -> list[str] | None:
    if not requested:
        return None
    canonical = list(canonicalize_analyzer_keys(list(requested)))
    known = {metadata.spec.key for metadata in get_default_analyzer_catalog().analyzers if metadata.spec.enabled}
    unknown = [key for key in canonical if key not in known]
    if unknown:
        raise CliError(
            f"Unknown analyzer key(s): {', '.join(unknown)}",
            code="unknown_analyzer",
            exit_code=2,
            details={"available": sorted(known)},
        )
    return canonical


def _apply_target_filter(cfg: ConfigDict, requested: tuple[str, ...]) -> ConfigDict:
    if not requested:
        return cfg
    configured = [str(value) for value in cast(list[object], cfg.get("analyzed_programs_and_libraries", []))]
    by_key = {value.casefold(): value for value in configured}
    selected: list[str] = []
    missing: list[str] = []
    for value in requested:
        match = by_key.get(value.casefold())
        if match is None:
            missing.append(value)
        elif match not in selected:
            selected.append(match)
    if missing:
        raise CliError(
            f"Unknown target(s): {', '.join(missing)}",
            code="unknown_target",
            exit_code=2,
            details={"configured": configured},
        )
    filtered = dict(cfg)
    filtered["analyzed_programs_and_libraries"] = selected
    return cast(ConfigDict, filtered)


def _capture_run(
    cfg: ConfigDict,
    keys: list[str] | None,
    *,
    use_cache: bool,
    persist_run: bool,
) -> ChecksRunResult:
    try:
        return collect_checks_result(cfg, keys, use_cache=use_cache, persist_run=persist_run)
    except TargetLoadError as exc:
        raise CliError(str(exc), code="target_load_failed", exit_code=2) from exc


def _result_record(result: ChecksRunResult, cfg: ConfigDict) -> RunRecord:
    record = build_run_record(result, cfg)
    if result.run_id:
        record = replace(record, run_id=result.run_id)
    return record


def command_analyze(args: argparse.Namespace) -> int:
    options = _analyze_options(args)
    project = resolve_project_file(options.project)
    cfg = _apply_target_filter(effective_project_config(project), options.targets)
    keys = _resolve_analyzer_keys(options.analyzers)
    result = _capture_run(cfg, keys, use_cache=options.use_cache, persist_run=options.persist_run)
    if result.cancelled:
        _write_diagnostics(result, options)
        return 130
    if not result.selected_analyzers:
        raise CliError(
            "No analyzers matched the request.",
            code="no_analyzers",
            exit_code=2,
            details={"requested": list(keys or ())},
        )
    if not result.targets:
        raise CliError(
            "Analysis did not load any targets.",
            code="analysis_preflight_failed",
            exit_code=2,
            details={"output": list(result.output_lines)},
        )
    _write_diagnostics(result, options)
    record = _result_record(result, cfg)
    all_findings = flat_findings(record)
    findings = filter_findings(all_findings, FindingFilters(modules=options.modules))
    summary: AnalyzeSummary = {
        **finding_summary(findings),
        "total_findings": len(all_findings),
        "targets": len(result.targets),
        "analyzers": len(result.selected_analyzers),
    }
    payload: AnalyzePayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "analyze",
        "run_id": result.run_id,
        "cancelled": result.cancelled,
        "project": {
            "path": str(project.path),
            "targets": list(cfg.get("analyzed_programs_and_libraries", [])),
        },
        "selected_analyzers": list(result.selected_analyzers),
        "summary": summary,
        "findings": [finding_payload(finding) for finding in findings],
    }
    _emit_findings(options.output, payload=payload, findings=findings, text_lines=_analyze_text(payload))
    if options.fail_on_findings and findings:
        return 1
    return 0


def _write_diagnostics(result: ChecksRunResult, options: _AnalyzeOptions) -> None:
    if not result.output_lines or options.output.quiet:
        return
    sys.stderr.write("\n".join(result.output_lines) + "\n")
    sys.stderr.flush()


def _analyze_text(payload: AnalyzePayload) -> list[str]:
    summary = payload["summary"]
    lines = [
        f"Run: {payload['run_id'] or '(not saved)'}",
        f"Targets: {summary.get('targets', 0)}  Analyzers: {summary.get('analyzers', 0)}  "
        f"Findings: {summary['findings']}",
    ]
    lines.extend(_finding_line(finding) for finding in payload["findings"])
    return lines


def _finding_line(finding: FindingPayload) -> str:
    module = finding["module"] or "(unknown)"
    return f"{module}: {kind_human_label(finding['kind'])} - {finding['message']} ({finding['analyzer']})"


def command_findings(args: argparse.Namespace) -> int:
    options = _output_options(args)
    record = resolve_run(args.run)
    filters = FindingFilters(
        targets=tuple(str(value) for value in args.target),
        analyzers=tuple(str(value) for value in args.analyzer),
        modules=tuple(str(value) for value in args.module),
        exact_module=bool(args.exact_module),
        kinds=tuple(str(value) for value in args.kind),
        rules=tuple(str(value) for value in args.rule),
    )
    findings = filter_findings(flat_findings(record), filters)
    matched = len(findings)
    limit = args.limit
    if limit is not None:
        findings = findings[: int(limit)]
    group_by = cast(GroupBy, str(args.group_by))
    groups: list[FindingGroup] = group_findings(findings, group_by)
    summary: FindingsSummary = {**finding_summary(findings), "matched": matched}
    payload: FindingsPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "findings",
        "run": run_payload(record),
        "filters": FindingsFilters(
            target=list(filters.targets),
            analyzer=list(filters.analyzers),
            module=list(filters.modules),
            exact_module=filters.exact_module,
            kind=list(filters.kinds),
            rule=list(filters.rules),
            group_by=group_by,
            limit=limit,
        ),
        "summary": summary,
        "groups": groups,
        "findings": [finding_payload(finding) for finding in findings],
    }
    _emit_findings(options, payload=payload, findings=findings, text_lines=_findings_text(payload))
    return 0


def _findings_text(payload: FindingsPayload) -> list[str]:
    summary = payload["summary"]
    lines = [
        f"Run: {payload['run']['run_id']}  Findings: {summary['findings']} (matched {summary.get('matched', 0)})",
    ]
    if payload["groups"]:
        lines.extend(f"{group['key']} ({group['count']})" for group in payload["groups"])
        return lines
    lines.extend(_finding_line(finding) for finding in payload["findings"])
    return lines


def command_show(args: argparse.Namespace) -> int:
    options = _output_options(args)
    record = resolve_run(args.run)
    finding_id = str(args.finding_id)
    match = next((finding for finding in flat_findings(record) if finding.id == finding_id), None)
    if match is None:
        raise CliError(
            f"Finding {finding_id!r} was not found in run {record.run_id}.",
            code="finding_not_found",
            exit_code=2,
            details={"run_id": record.run_id},
        )
    payload: ShowPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "show",
        "run": run_payload(record),
        "finding": finding_payload(match),
    }
    if options.output_format == "markdown":
        emit_text(_finding_markdown(payload), output=options.output)
    else:
        _emit_document(options, payload=payload, text_lines=_finding_text(payload))
    return 0


def _finding_text(payload: ShowPayload) -> list[str]:
    finding = payload["finding"]
    lines = [
        f"Finding: {finding['id']}",
        f"Module:  {finding['module'] or '(unknown)'}",
        f"Kind:    {kind_human_label(finding['kind'])}",
    ]
    if finding["site"]:
        lines.append(f"Site:    {finding['site']}")
    lines.extend(
        [
            f"Message: {finding['message']}",
            f"Analyzer: {finding['analyzer']}",
            f"Target:   {finding['target']}",
        ]
    )
    if finding["explanation"]:
        lines.append(f"Explanation: {finding['explanation']}")
    if finding["suggestion"]:
        lines.append(f"Suggestion: {finding['suggestion']}")
    return lines


def _finding_markdown(payload: ShowPayload) -> list[str]:
    finding = payload["finding"]
    lines = [
        f"# {kind_human_label(finding['kind'])}: {finding['module'] or '(unknown)'}",
        "",
        f"- **Finding:** `{finding['id']}`",
        f"- **Run:** `{payload['run']['run_id']}`",
        f"- **Analyzer:** `{finding['analyzer']}`",
        f"- **Target:** `{finding['target']}`",
    ]
    if finding["site"]:
        lines.append(f"- **Site:** `{finding['site']}`")
    lines.extend(["", finding["message"]])
    if finding["explanation"]:
        lines.extend(["", "## Why it matters", "", str(finding["explanation"])])
    if finding["suggestion"]:
        lines.extend(["", "## Suggested fix", "", str(finding["suggestion"])])
    return lines


__all__ = [
    "command_analyze",
    "command_analyzers_list",
    "command_findings",
    "command_project_show",
    "command_show",
]
