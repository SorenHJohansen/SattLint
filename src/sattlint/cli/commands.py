"""Headless CLI commands for agents and automation."""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from itertools import chain
from pathlib import Path
from typing import cast

from ..analyzers.catalog import (
    canonicalize_analyzer_keys,
    get_default_analyzer_catalog,
    get_selectable_analyzer_keys,
)
from ..application.analyze import collect_checks_result, no_analyzer_selection_message
from ..application.checks import ChecksRunResult, build_run_record
from ..application.findings import kind_human_label
from ..config.string_capacities import STRING_CAPACITY_KEYS
from ..config.types import ConfigDict
from ..core.progress import (
    AnalysisProgressEvent,
    ProgressCallback,
    encode_progress_line,
)
from ..project.io import discover_project
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
    write_stream,
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
    refresh_ast: bool
    persist_run: bool
    fail_on_findings: bool
    jobs: int | None
    progress: bool


def _output_options(args: argparse.Namespace) -> _OutputOptions:
    return _OutputOptions(
        output_format=str(args.format or "text"),
        output=output_path(args.output),
        quiet=bool(args.quiet),
    )


def _discard_output_file(options: _OutputOptions) -> None:
    """Remove a previous artifact so a failed run cannot be archived as fresh.

    A pipeline that reads the ``--output`` path after a failed run must not see
    the findings from an earlier run.
    """
    if options.output is None:
        return
    with contextlib.suppress(OSError):
        options.output.expanduser().resolve().unlink()


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
        envelope = {"record_type": "envelope", **payload}
        envelope.pop("findings", None)
        finding_records = ({"record_type": "finding", **finding_payload(finding)} for finding in findings)
        emit_ndjson(chain((envelope,), finding_records), output=options.output)
    else:
        emit_text(text_lines, output=options.output)


def _analyze_options(args: argparse.Namespace) -> _AnalyzeOptions:
    return _AnalyzeOptions(
        output=_output_options(args),
        project=None if args.project is None else str(args.project),
        analyzers=tuple(str(value) for value in args.analyzer),
        targets=tuple(str(value) for value in args.target),
        modules=tuple(str(value) for value in args.module),
        use_cache=not bool(args.no_cache),
        refresh_ast=bool(args.refresh_ast),
        persist_run=not bool(args.no_save),
        fail_on_findings=str(args.fail_on) == "any",
        jobs=None if int(args.jobs) == 0 else int(args.jobs),
        progress=bool(args.progress),
    )


def command_project_show(args: argparse.Namespace) -> int:
    project = resolve_project_file(args.project)
    options = _output_options(args)
    project_info = project_payload(project, quiet=options.quiet)
    payload: ProjectShowPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "project show",
        "project": project_info,
    }
    _emit_document(options, payload=payload, text_lines=_project_text(project_info))
    return 0


def _project_text(project: ProjectInfo) -> list[str]:
    paths = project["paths"]
    config_state = "" if project["config"]["exists"] else " (missing)"
    lines = [
        f"Project:   {project['path']}",
        f"Root:      {project['root']}",
        f"Version:   {project['slproj_version']}",
        f"Mode:      {project['mode']}",
        f"Targets:   {', '.join(project['targets']) or '(none)'}",
        f"Analyzers: {', '.join(project['analyzers']) or '(none)'}",
        "String capacities:",
        *(f"  {key}: {project['string_capacities'][key]}" for key in STRING_CAPACITY_KEYS),
    ]
    lines.extend(_analysis_text(project["analysis"]))
    lines.extend(
        [
            f"program_dir: {paths['program_dir']}",
            f"ABB_lib_dir: {paths['ABB_lib_dir']}",
            f"icf_dir: {paths['icf_dir']}",
            f"other_lib_dirs: {', '.join(paths['other_lib_dirs']) or '(none)'}",
            f"Runs:    {project['runs_dir']}",
            f"Review:  {project['review_output_dir']}",
            f"Config:  {project['config']['path']}{config_state}",
        ]
    )
    return lines


def _analysis_text(analysis: Mapping[str, object]) -> list[str]:
    if not analysis:
        return ["Analysis: (defaults)"]
    return ["Analysis:", *(f"  {key}: {_display_value(value)}" for key, value in sorted(analysis.items()))]


def _display_value(value: object) -> str:
    if isinstance(value, Mapping):
        nested = cast(Mapping[str, object], value)
        return ", ".join(f"{key}={_display_value(nested[key])}" for key in sorted(nested))
    if isinstance(value, (list, tuple)):
        return ", ".join(_display_value(item) for item in cast(list[object] | tuple[object, ...], value))
    return str(value)


def command_analyzers_list(args: argparse.Namespace) -> int:
    catalog = get_default_analyzer_catalog()
    analyzers: list[AnalyzerInfo] = [metadata.to_dict() for metadata in catalog.analyzers]
    options = _output_options(args)
    payload: AnalyzersListPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "analyzers list",
        "analyzers": analyzers,
    }
    _emit_document(options, payload=payload, text_lines=_analyzers_text(analyzers))
    return 0


def _analyzers_text(analyzers: list[AnalyzerInfo]) -> list[str]:
    lines = [
        "Analyzers (select with --analyzer KEY):",
        f"  {'Key':<24} {'Category':<12} Name",
    ]
    for entry in analyzers:
        lines.append(f"  {entry['key']:<24} {entry['category']:<12} {entry['name']}")
    return lines


def _resolve_analyzer_keys(requested: tuple[str, ...]) -> list[str]:
    """Validate and canonicalize the analyzer keys a run will use.

    The command line wins; the project's ``analyzers`` list is the fallback. A
    run with neither is an error that names every selectable analyzer.
    """
    if not requested:
        raise CliError(
            no_analyzer_selection_message(),
            code="no_analyzers",
            exit_code=2,
            details={"available": list(get_selectable_analyzer_keys())},
        )
    canonical = list(canonicalize_analyzer_keys(list(requested)))
    known = set(get_selectable_analyzer_keys())
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


def _require_configured_targets(cfg: ConfigDict) -> None:
    configured = [str(value).strip() for value in cast(list[object], cfg.get("analyzed_programs_and_libraries", []))]
    if not any(configured):
        raise CliError(
            "No analysis targets are configured.",
            code="no_targets",
            exit_code=2,
        )


def _capture_run(
    cfg: ConfigDict,
    keys: list[str] | None,
    *,
    use_cache: bool,
    refresh_ast: bool,
    persist_run: bool,
    project_path: str,
    jobs: int | None,
    progress: ProgressCallback | None = None,
) -> ChecksRunResult:
    try:
        return collect_checks_result(
            cfg,
            keys,
            use_cache=use_cache,
            refresh_ast=refresh_ast,
            persist_run=persist_run,
            project_path=project_path,
            jobs=jobs,
            progress=progress,
        )
    except TargetLoadError as exc:
        raise CliError(str(exc), code="target_load_failed", exit_code=2) from exc


def stderr_progress_writer() -> ProgressCallback:
    """Write one progress record per line, flushed so a parent can read it live."""

    def write(event: AnalysisProgressEvent) -> None:
        write_stream(sys.stderr, f"{encode_progress_line(event)}\n")

    return write


def _result_record(result: ChecksRunResult, cfg: ConfigDict, *, project_path: str) -> RunRecord:
    record = build_run_record(result, cfg, project_path=project_path)
    if result.run_id:
        record = replace(record, run_id=result.run_id)
    return record


def command_analyze(args: argparse.Namespace) -> int:
    options = _analyze_options(args)
    project = resolve_project_file(options.project)
    cfg = _apply_target_filter(effective_project_config(project, quiet=options.output.quiet), options.targets)
    keys = _resolve_analyzer_keys(options.analyzers or project.analyzers)
    _require_configured_targets(cfg)
    project_path = str(project.path)
    result = _capture_run(
        cfg,
        keys,
        use_cache=options.use_cache,
        refresh_ast=options.refresh_ast,
        persist_run=options.persist_run,
        project_path=project_path,
        jobs=options.jobs,
        progress=stderr_progress_writer() if options.progress and not options.output.quiet else None,
    )
    if result.cancelled:
        _discard_output_file(options.output)
        _write_diagnostics(result, options)
        return 130
    if not result.selected_analyzers:
        _discard_output_file(options.output)
        raise CliError(
            f"No analyzers matched the request: {', '.join(keys)}.",
            code="no_analyzers",
            exit_code=2,
            details={"requested": list(keys)},
        )
    if result.failures:
        _discard_output_file(options.output)
        if options.output.output_format == "text":
            _write_diagnostics(result, options)
        failed = ", ".join(failure.target_name for failure in result.failures)
        raise CliError(
            f"Analysis stopped because {len(result.failures)} target(s) could not be loaded: {failed}",
            code="target_load_failed",
            exit_code=2,
            details={failure.target_name: failure.message for failure in result.failures},
        )
    if not result.targets:
        _discard_output_file(options.output)
        if options.output.output_format == "text":
            _write_diagnostics(result, options)
            details: Mapping[str, object] = {}
        else:
            details = {"output": list(result.output_lines)}
        raise CliError(
            "Analysis did not produce any target results.",
            code="analysis_preflight_failed",
            exit_code=2,
            details=details,
        )
    analyzer_failures = result.analyzer_failures
    if analyzer_failures:
        _discard_output_file(options.output)
        if options.output.output_format == "text":
            _write_diagnostics(result, options)
        failed_analyzers = ", ".join(failure.analyzer_name for failure in analyzer_failures)
        raise CliError(
            f"Analysis stopped because {len(analyzer_failures)} analyzer(s) failed: {failed_analyzers}",
            code="analyzer_failed",
            exit_code=2,
            details={failure.analyzer_name: failure.message for failure in analyzer_failures},
        )
    _write_diagnostics(result, options)
    record = _result_record(result, cfg, project_path=project_path)
    all_findings = flat_findings(record)
    findings = filter_findings(all_findings, FindingFilters(modules=options.modules))
    summary: AnalyzeSummary = {
        **finding_summary(findings),
        "total_findings": len(all_findings),
        "targets": sum(1 for target in result.targets if not target.is_pseudo),
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


def _discovered_project_path() -> str | None:
    discovered = discover_project()
    return None if discovered is None else str(discovered)


def command_findings(args: argparse.Namespace) -> int:
    options = _output_options(args)
    requested_analyzers = tuple(str(value) for value in args.analyzer)
    if requested_analyzers:
        requested_analyzers = tuple(_resolve_analyzer_keys(requested_analyzers))
    record = resolve_run(args.run, project_path=_discovered_project_path())
    filters = FindingFilters(
        targets=tuple(str(value) for value in args.target),
        analyzers=requested_analyzers,
        modules=tuple(str(value) for value in args.module),
        exact_module=bool(args.exact_module),
        kinds=tuple(str(value) for value in args.kind),
        rules=tuple(str(value) for value in args.rule),
    )
    findings = filter_findings(flat_findings(record), filters)
    matched = len(findings)
    limit = args.limit
    if limit is not None:
        findings = findings[:limit]
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


def _group_label(key: str, group_by: str) -> str:
    if group_by == "kind":
        return kind_human_label(key)
    if group_by == "analyzer":
        catalog = get_default_analyzer_catalog()
        for metadata in catalog.analyzers:
            if metadata.spec.key == key:
                return metadata.spec.name
    return key


def _findings_text(payload: FindingsPayload) -> list[str]:
    summary = payload["summary"]
    lines = [
        f"Run: {payload['run']['run_id']}  Findings: {summary['findings']} (matched {summary.get('matched', 0)})",
    ]
    if payload["groups"]:
        group_by = payload["filters"]["group_by"]
        lines.extend(f"{_group_label(group['key'], group_by)} ({group['count']})" for group in payload["groups"])
        return lines
    lines.extend(_finding_line(finding) for finding in payload["findings"])
    return lines


def command_show(args: argparse.Namespace) -> int:
    options = _output_options(args)
    record = resolve_run(args.run, project_path=_discovered_project_path())
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
