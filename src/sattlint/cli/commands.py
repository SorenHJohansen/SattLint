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
from ..application.checks import ChecksRunResult, TargetLoadFailure, build_run_record
from ..application.findings import format_source_location, kind_human_label
from ..config.string_capacities import STRING_CAPACITY_KEYS
from ..config.types import ConfigDict
from ..core.progress import (
    AnalysisProgressEvent,
    ProgressCallback,
    encode_progress_line,
)
from ..project.io import ProjectAmbiguousError, discover_project_result
from ..project.models import SattLintProjectFile
from ..project.support import TARGET_FAILURE_DETAIL_LIMIT, TargetLoadError, get_analyzed_targets
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
    TargetLoadFailurePayload,
)
from ._project import drain_config_warnings, effective_project_config, project_payload, resolve_project_file


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


def _ambiguous_project_error(exc: ProjectAmbiguousError) -> CliError:
    return CliError(
        str(exc),
        code="project_ambiguous",
        exit_code=2,
        details={"candidates": [str(candidate) for candidate in exc.candidates]},
    )


def _resolve_project(raw: str | None) -> SattLintProjectFile:
    """Resolve the project file for a command, including discovery.

    An explicit path skips discovery entirely. Discovery ambiguity becomes a
    CLI error that lists the candidates.
    """
    try:
        return resolve_project_file(raw)
    except ProjectAmbiguousError as exc:
        raise _ambiguous_project_error(exc) from exc


def command_project_show(args: argparse.Namespace) -> int:
    project = _resolve_project(args.project)
    options = _output_options(args)
    _drain_quiet_warnings(options)
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


def _configured_target_count(cfg: ConfigDict) -> int:
    return len(get_analyzed_targets(cfg))


def _is_partial_run(result: ChecksRunResult, configured_targets: int) -> bool:
    """True when at least one target loaded and not every target failed.

    Fewer than one loaded target is still an error: there is nothing to report,
    so the command must not present an empty list as a result. A failure count
    that covers every configured target is also an error, because the run never
    produced a usable analysis.
    """
    analyzed = sum(1 for target in result.targets if not target.is_pseudo)
    if analyzed < 1:
        return False
    return len(result.failures) < configured_targets


def _failure_payload(failure: TargetLoadFailure) -> TargetLoadFailurePayload:
    return {
        "target": failure.target_name,
        "kind": failure.kind,
        "message": failure.message,
        "path": failure.path,
        "line": failure.line,
        "column": failure.column,
    }


def _bounded_failures(failures: tuple[TargetLoadFailure, ...]) -> list[TargetLoadFailurePayload]:
    return [_failure_payload(failure) for failure in failures[:TARGET_FAILURE_DETAIL_LIMIT]]


def _target_load_error(failures: tuple[TargetLoadFailure, ...]) -> CliError:
    shown = failures[:TARGET_FAILURE_DETAIL_LIMIT]
    omitted = len(failures) - len(shown)
    names = ", ".join(failure.target_name for failure in shown)
    if omitted:
        names = f"{names}, ... and {omitted} more"
    details: dict[str, object] = {failure.target_name: failure.message for failure in shown}
    if omitted:
        details["omitted"] = f"{omitted} more target(s)"
    return CliError(
        f"Analysis stopped because {len(failures)} target(s) could not be loaded: {names}. "
        "Fix the reported problems, then rerun.",
        code="target_load_failed",
        exit_code=2,
        details=details,
    )


def _drain_quiet_warnings(options: _OutputOptions) -> None:
    """Drop collected warnings when the caller asked for quiet output.

    The unknown-project-key warnings are written by the CLI entry point after a
    command returns, so a quiet command has to discard them before that point.
    """
    if options.quiet:
        drain_config_warnings()


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
    project = _resolve_project(options.project)
    _drain_quiet_warnings(options.output)
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
    partial_failures: tuple[TargetLoadFailure, ...] = ()
    if result.failures:
        if not _is_partial_run(result, _configured_target_count(cfg)):
            _discard_output_file(options.output)
            if options.output.output_format == "text":
                _write_diagnostics(result, options)
            raise _target_load_error(result.failures)
        partial_failures = result.failures
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
    if partial_failures:
        payload["failures"] = _bounded_failures(partial_failures)
        payload["failed_targets"] = len(partial_failures)
    _emit_findings(options.output, payload=payload, findings=findings, text_lines=_analyze_text(payload))
    if partial_failures:
        return 2
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
    failed_total = payload.get("failed_targets", 0)
    if failed_total:
        lines.append(f"Failed targets ({failed_total}):")
        for failure in payload.get("failures", []):
            message_lines = failure["message"].splitlines() or [""]
            lines.append(f"  - {failure['target']} ({failure['kind']}): {message_lines[0]}")
            lines.extend(f"    {line}" for line in message_lines[1:])
        omitted = failed_total - len(payload.get("failures", []))
        if omitted:
            lines.append(f"  - ... and {omitted} more")
        lines.append("Fix the failed targets, then rerun. The other targets' results above are complete.")
    lines.extend(_finding_line(finding) for finding in payload["findings"])
    return lines


def _finding_line(finding: FindingPayload) -> str:
    module = finding["module"] or "(unknown)"
    location = format_source_location(
        file=finding["file"],
        line=finding["line"],
        column=finding["column"],
        end_line=finding["end_line"],
    )
    prefix = f"{location}  " if location else ""
    return f"{prefix}{module}: {kind_human_label(finding['kind'])} - {finding['message']} ({finding['analyzer']})"


_LATEST_SELECTOR = "latest"


def _scoped_project_path(raw: str | None) -> str | None:
    """Return the project path that scopes a stored-run query.

    An explicit ``--project`` names the scope directly and skips discovery.
    Otherwise discovery walks up from the working directory. ``None`` means no
    project could be found.
    """
    if raw is not None:
        return str(_resolve_project(raw).path)
    discovery = discover_project_result()
    try:
        selected = discovery.selected_path()
    except ProjectAmbiguousError as exc:
        raise _ambiguous_project_error(exc) from exc
    return None if selected is None else str(selected)


def _run_scope(args: argparse.Namespace) -> tuple[str, str | None]:
    """Resolve a query's project scope.

    An explicit ``--project`` names it directly; otherwise it comes from
    discovery and may be absent. An explicit run id already names the run, so
    it neither needs discovery nor fails because discovery is ambiguous.
    """
    selector = str(args.run)
    raw_project = args.project
    if raw_project is None and selector.strip().casefold() != _LATEST_SELECTOR:
        return selector, None
    return selector, _scoped_project_path(raw_project)


def command_findings(args: argparse.Namespace) -> int:
    options = _output_options(args)
    requested_analyzers = tuple(str(value) for value in args.analyzer)
    if requested_analyzers:
        requested_analyzers = tuple(_resolve_analyzer_keys(requested_analyzers))
    selector, project_path = _run_scope(args)
    _drain_quiet_warnings(options)
    record = resolve_run(selector, project_path=project_path, require_project_scope=True)
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
        "run": run_payload(record, project_path=project_path),
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


def _run_header(run: Mapping[str, object]) -> str:
    header = f"Run: {run['run_id']}"
    project_path = str(run.get("project_path") or "")
    if project_path:
        header = f"{header}  Project: {project_path}"
    return header


def _findings_text(payload: FindingsPayload) -> list[str]:
    summary = payload["summary"]
    lines = [
        f"{_run_header(payload['run'])}  Findings: {summary['findings']} (matched {summary.get('matched', 0)})",
    ]
    if payload["groups"]:
        group_by = payload["filters"]["group_by"]
        lines.extend(f"{_group_label(group['key'], group_by)} ({group['count']})" for group in payload["groups"])
        return lines
    lines.extend(_finding_line(finding) for finding in payload["findings"])
    return lines


def command_show(args: argparse.Namespace) -> int:
    options = _output_options(args)
    selector, project_path = _run_scope(args)
    _drain_quiet_warnings(options)
    record = resolve_run(selector, project_path=project_path, require_project_scope=True)
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
        "run": run_payload(record, project_path=project_path),
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
    if finding["file"]:
        lines.append(f"File:    {finding['file']}")
    if finding["line"] is not None:
        line = f"{finding['line']}"
        if finding["end_line"] is not None and finding["end_line"] > finding["line"]:
            line = f"{line}-{finding['end_line']}"
        lines.append(f"Line:    {line}")
    if finding["column"] is not None:
        lines.append(f"Column:  {finding['column']}")
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
    location = format_source_location(
        file=finding["file"],
        line=finding["line"],
        column=finding["column"],
        end_line=finding["end_line"],
    )
    if location:
        lines.append(f"- **Location:** `{location}`")
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
