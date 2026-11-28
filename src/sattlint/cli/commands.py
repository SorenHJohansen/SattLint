"""Headless CLI commands for agents and automation."""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from itertools import chain
from pathlib import Path
from typing import TypedDict, cast

from ..__version__ import __version__
from ..analyzers.catalog import (
    canonicalize_analyzer_keys,
    get_default_analyzer_catalog,
    get_selectable_analyzer_keys,
)
from ..application.analyze import collect_checks_result, no_analyzer_selection_message
from ..application.change_review import (
    ChangeReviewError,
    ChangeReviewNoTargetsError,
    ChangeReviewOutcome,
    ChangeReviewOutputError,
    run_change_review,
)
from ..application.checks import AnalyzerFailure, ChecksRunResult, TargetLoadFailure, build_run_record
from ..application.findings import format_source_location, kind_human_label
from ..config.string_capacities import STRING_CAPACITY_KEYS
from ..config.types import ConfigDict
from ..config.validation import validate_loaded_config
from ..core.progress import (
    AnalysisProgressEvent,
    ProgressCallback,
    encode_progress_line,
)
from ..project.io import SLPROJ_FILENAME, ProjectAmbiguousError, discover_project_result, init_project
from ..project.models import SattLintProjectFile
from ..project.support import TARGET_FAILURE_DETAIL_LIMIT, TargetLoadError, get_analyzed_targets
from ..project.targets import ProjectTarget, scan_project_targets
from ..runs import (
    BASELINE_FILENAME,
    RUN_STATUS_FAILED,
    RUN_STATUS_OK,
    Baseline,
    BaselineDiff,
    BaselineDiffEntry,
    BaselineEntry,
    BaselineInvalidError,
    BaselineNotFoundError,
    BaselineWriteError,
    PruneReport,
    RunAnalyzerRecord,
    RunFailure,
    RunRecord,
    RunStatus,
    RunSummary,
    SkippedRun,
    baseline_fails,
    delete_run,
    diff_baseline,
    load_baseline,
    prune_unreadable_runs,
    relative_source_file,
    run_history_policy,
    save_baseline,
    save_run_for_history,
    scan_runs,
    utc_now_iso,
)
from ..utils.terminal_text import sanitize_terminal_text
from ._findings import (
    FindingFilters,
    FlatFinding,
    filter_findings,
    finding_payload,
    finding_summary,
    flat_findings,
    group_findings,
    normalize_finding_filters,
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
    BaselineBlockPayload,
    BaselineDiffEntryPayload,
    BaselineDiffPayload,
    BaselineUpdatePayload,
    FailOn,
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
from ._sarif import build_sarif


class _RunSummaryPayload(TypedDict):
    run_id: str
    started_at: str
    finished_at: str
    project_tag: str
    project_path: str
    target_count: int
    analyzer_count: int
    finding_count: int
    failure_count: int
    status: RunStatus


class _SkippedRunPayload(TypedDict):
    run_id: str
    reason: str
    detail: str


class RunsListPayload(TypedDict):
    schema_version: int
    command: str
    project: str
    runs: list[_RunSummaryPayload]
    skipped: list[_SkippedRunPayload]
    skipped_count: int


class _RunAnalyzerPayload(TypedDict):
    target: str
    key: str
    name: str
    status: str
    finding_count: int
    issue_count: int | None
    duration_ms: float | None
    summary: str | None
    skip_reason: str | None


class _RunFailurePayload(TypedDict):
    kind: str
    target: str
    analyzer: str
    message: str
    path: str | None
    line: int | None
    column: int | None


class RunShowPayload(TypedDict):
    schema_version: int
    command: str
    run: _RunSummaryPayload
    cancelled: bool
    selected_analyzers: list[str]
    truncated: bool
    truncation_note: str
    failure_message: str
    failure_reason: str
    analyzers: list[_RunAnalyzerPayload]
    failures: list[_RunFailurePayload]
    output_line_count: int


class RunsPrunePayload(TypedDict):
    schema_version: int
    command: str
    removed: int
    unreadable: int
    over_limit: int
    kept: int
    removed_run_ids: list[str]


class _ReviewTargetPayload(TypedDict):
    target: str
    json: str
    markdown: str


class _ReviewFailurePayload(TypedDict):
    target: str
    message: str


class ReviewPayload(TypedDict):
    schema_version: int
    command: str
    project: str
    output_dir: str
    targets: list[_ReviewTargetPayload]
    failures: list[_ReviewFailurePayload]
    generated_targets: int
    failed_targets: int


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
    fail_on: FailOn
    jobs: int | None
    progress: bool
    baseline: Path | None


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
    elif options.output_format == "sarif":
        run_id = payload.get("run_id")
        emit_json(
            build_sarif(findings, run_id=run_id if isinstance(run_id, str) else None),
            output=options.output,
        )
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
        fail_on=cast(FailOn, str(args.fail_on)),
        jobs=None if int(args.jobs) == 0 else int(args.jobs),
        progress=bool(args.progress),
        baseline=output_path(args.baseline),
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


class _ProjectTargetPayload(TypedDict):
    name: str
    kind: str
    path: str


class ProjectTargetsPayload(TypedDict):
    schema_version: int
    command: str
    project: str
    targets: list[_ProjectTargetPayload]
    warnings: list[str]
    errors: list[str]


class ProjectCheckPayload(TypedDict):
    schema_version: int
    command: str
    project: str
    ok: bool
    errors: list[str]
    warnings: list[str]
    target_count: int


class ProjectInitPayload(TypedDict):
    schema_version: int
    command: str
    path: str
    created: bool


def _project_target_payload(target: ProjectTarget) -> _ProjectTargetPayload:
    return {
        "name": target.name,
        "kind": target.kind,
        "path": str(target.path),
    }


def command_project_targets(args: argparse.Namespace) -> int:
    """List every target the configured roots provide, with its inferred kind."""
    options = _output_options(args)
    project = _resolve_project(args.project)
    _drain_quiet_warnings(options)
    scan = scan_project_targets(effective_project_config(project, quiet=options.quiet))
    payload: ProjectTargetsPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "project targets",
        "project": str(project.path),
        "targets": [_project_target_payload(target) for target in scan.targets],
        "warnings": list(scan.warnings),
        "errors": list(scan.errors),
    }
    _emit_document(options, payload=payload, text_lines=_project_targets_text(payload))
    return 1 if scan.errors else 0


def _project_targets_text(payload: ProjectTargetsPayload) -> list[str]:
    lines = [f"Project: {payload['project']}", f"Targets: {len(payload['targets'])}"]
    for target in payload["targets"]:
        lines.append(f"  {target['name']}  {target['kind']}  {target['path']}")
    if payload["warnings"]:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in payload["warnings"])
    if payload["errors"]:
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in payload["errors"])
    return lines


def command_project_check(args: argparse.Namespace) -> int:
    """Validate the project schema, configured roots, and target identity."""
    options = _output_options(args)
    project = _resolve_project(args.project)
    _drain_quiet_warnings(options)
    cfg = effective_project_config(project, quiet=options.quiet)
    validation = validate_loaded_config(cfg)
    scan = scan_project_targets(cfg)
    errors = [f"{error.key_path}: {error.message}" for error in validation.errors] + list(scan.errors)
    warnings = [*project.warnings, *scan.warnings]
    payload: ProjectCheckPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "project check",
        "project": str(project.path),
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "target_count": len(scan.targets),
    }
    _emit_document(options, payload=payload, text_lines=_project_check_text(payload))
    return 0 if not errors else 1


def _project_check_text(payload: ProjectCheckPayload) -> list[str]:
    lines = [
        f"Project: {payload['project']}",
        f"Targets: {payload['target_count']}",
        "Result:  " + ("ok" if payload["ok"] else "failed"),
    ]
    if payload["warnings"]:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in payload["warnings"])
    if payload["errors"]:
        lines.append("Errors:")
        lines.extend(f"  - {error}" for error in payload["errors"])
    return lines


def command_project_init(args: argparse.Namespace) -> int:
    """Scaffold a minimal version 2 project file at the requested path."""
    options = _output_options(args)
    raw = str(args.path or ".").strip() or "."
    target = Path(raw).expanduser()
    if target.is_dir() or raw.endswith(("/", "\\")):
        target = target / SLPROJ_FILENAME
    elif target.suffix.lower() != SLPROJ_FILENAME:
        target = target.with_suffix(SLPROJ_FILENAME)
    target = target.resolve()
    try:
        project = init_project(target)
    except FileExistsError as exc:
        raise CliError(str(exc), code="project_exists", exit_code=2) from exc
    except (OSError, ValueError) as exc:
        raise CliError(f"Could not create project {target}: {exc}", code="project_write_failed", exit_code=2) from exc
    payload: ProjectInitPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "project init",
        "path": str(project.path),
        "created": True,
    }
    _emit_document(options, payload=payload, text_lines=[f"Created project: {project.path}"])
    return 0


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


def _project_tag(cfg: ConfigDict) -> str:
    targets = cast(list[object], cfg.get("analyzed_programs_and_libraries", []))
    return ", ".join(str(target) for target in targets if str(target).strip())


def _run_failure_from_load(failure: TargetLoadFailure) -> RunFailure:
    return RunFailure(
        kind="target",
        message=failure.message,
        target=failure.target_name,
        path=failure.path,
        line=failure.line,
        column=failure.column,
    )


def _run_failure_from_analyzer(failure: AnalyzerFailure) -> RunFailure:
    return RunFailure(
        kind="analyzer",
        message=failure.message,
        target=failure.target_name,
        analyzer=failure.analyzer_name,
    )


def _failure_record(
    cfg: ConfigDict,
    *,
    project_path: str,
    status: RunStatus,
    failures: tuple[RunFailure, ...],
    message: str,
    result: ChecksRunResult | None = None,
) -> RunRecord:
    if result is None:
        now = utc_now_iso()
        record = RunRecord(
            run_id="",
            started_at=now,
            finished_at=now,
            project_tag=_project_tag(cfg),
            project_path=project_path,
        )
    else:
        record = _result_record(result, cfg, project_path=project_path)
    return replace(record, status=status, failures=failures, failure_message=message or None)


def _save_failure_record(
    cfg: ConfigDict,
    *,
    project_path: str,
    status: RunStatus,
    failures: tuple[RunFailure, ...],
    message: str,
    result: ChecksRunResult | None = None,
) -> RunRecord | None:
    """Store a run that did not complete, so ``latest`` cannot show an older success.

    A failed analysis used to leave no record, which made ``latest`` resolve to
    the previous successful run. The stored record carries the status and the
    failure detail that ``runs show`` reports.
    """
    if result is not None and result.run_id:
        # The checks pipeline may already have stored an empty record for a run
        # that then failed; the failure record replaces it.
        delete_run(result.run_id)
    record = _failure_record(
        cfg,
        project_path=project_path,
        status=status,
        failures=failures,
        message=message,
        result=result,
    )
    return save_run_for_history(record, policy=run_history_policy(cfg))


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
        if persist_run:
            _save_failure_record(
                cfg,
                project_path=project_path,
                status=RUN_STATUS_FAILED,
                failures=(),
                message=str(exc),
            )
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


def _admit_run_result(
    result: ChecksRunResult,
    cfg: ConfigDict,
    options: _AnalyzeOptions,
    *,
    project_path: str,
    keys: list[str],
) -> tuple[TargetLoadFailure, ...]:
    """Reject a run that cannot be reported as current, recording it first.

    A run that stopped before producing a usable result set is stored with a
    failure status, so ``findings --run latest`` cannot fall back to an older
    successful run. A partial run is reported to the caller and stays out of
    history, as the load-failure contract requires.
    """
    if not result.selected_analyzers:
        _discard_output_file(options.output)
        if options.persist_run:
            _save_failure_record(
                cfg,
                project_path=project_path,
                status=RUN_STATUS_FAILED,
                failures=(),
                message=f"No analyzers matched the request: {', '.join(keys)}.",
                result=result,
            )
        raise CliError(
            f"No analyzers matched the request: {', '.join(keys)}.",
            code="no_analyzers",
            exit_code=2,
            details={"requested": list(keys)},
        )
    if result.failures:
        failures = tuple(_run_failure_from_load(failure) for failure in result.failures)
        if not _is_partial_run(result, _configured_target_count(cfg)):
            _discard_output_file(options.output)
            if options.output.output_format == "text":
                _write_diagnostics(result, options)
            if options.persist_run:
                _save_failure_record(
                    cfg,
                    project_path=project_path,
                    status=RUN_STATUS_FAILED,
                    failures=failures,
                    message=f"Analysis stopped because {len(result.failures)} target(s) could not be loaded.",
                    result=result,
                )
            raise _target_load_error(result.failures)
        # A partial run stays out of history: it is reported now, and it must
        # never be mistaken for a complete stored result later.
        return result.failures
    if not result.targets:
        _discard_output_file(options.output)
        if options.persist_run:
            _save_failure_record(
                cfg,
                project_path=project_path,
                status=RUN_STATUS_FAILED,
                failures=(),
                message="Analysis did not produce any target results.",
                result=result,
            )
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
        if options.persist_run and not result.run_id:
            # A stubbed or interrupted pipeline may not have stored the record;
            # mark the failure so ``latest`` cannot fall back to an older run.
            _save_failure_record(
                cfg,
                project_path=project_path,
                status=RUN_STATUS_FAILED,
                failures=tuple(_run_failure_from_analyzer(failure) for failure in analyzer_failures),
                message=f"{len(analyzer_failures)} analyzer(s) failed.",
                result=result,
            )
        failed_analyzers = ", ".join(failure.analyzer_name for failure in analyzer_failures)
        raise CliError(
            f"Analysis stopped because {len(analyzer_failures)} analyzer(s) failed: {failed_analyzers}",
            code="analyzer_failed",
            exit_code=2,
            details={failure.analyzer_name: failure.message for failure in analyzer_failures},
        )
    return ()


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


def _baseline_not_found_error(path: Path) -> CliError:
    return CliError(
        f"Baseline file {path} was not found. Run 'sattlint baseline update' to create it.",
        code="baseline_not_found",
        exit_code=2,
        details={"path": str(path)},
    )


def _load_baseline_for_cli(path: Path) -> Baseline:
    try:
        return load_baseline(path)
    except BaselineNotFoundError as exc:
        raise _baseline_not_found_error(path) from exc
    except BaselineInvalidError as exc:
        raise CliError(
            str(exc),
            code="baseline_invalid",
            exit_code=2,
            details={"path": str(path)},
        ) from exc


def _baseline_entries(findings: Iterable[FlatFinding], project_root: Path) -> list[BaselineEntry]:
    return [
        BaselineEntry(
            identity=finding.id,
            analyzer=finding.analyzer_key,
            kind=finding.finding.kind,
            severity=finding.severity,
            module_path=finding.module_path,
            file=relative_source_file(finding.finding.file, project_root),
            line=finding.finding.line,
            message=finding.finding.message,
        )
        for finding in findings
    ]


def _baseline_entry_payload(entry: BaselineDiffEntry) -> BaselineDiffEntryPayload:
    payload: BaselineDiffEntryPayload = {
        "status": entry.status,
        "identity": entry.identity,
        "analyzer": entry.analyzer,
        "kind": entry.kind,
        "severity": entry.severity,
        "module": entry.module,
        "file": entry.file,
        "line": entry.line,
        "message": entry.message,
    }
    if entry.status == "moved":
        payload["previous_file"] = entry.previous_file
        payload["previous_line"] = entry.previous_line
    elif entry.status == "changed" and entry.previous_severity is not None:
        payload["previous_severity"] = entry.previous_severity
    return payload


def _baseline_block(path: Path, diff: BaselineDiff) -> BaselineBlockPayload:
    return {
        "path": str(path),
        "added": diff.count("added"),
        "moved": diff.count("moved"),
        "changed": diff.count("changed"),
        "stale": diff.count("stale"),
        "unchanged": diff.count("unchanged"),
        "entries": [_baseline_entry_payload(entry) for entry in diff.reported],
    }


def _baseline_counts_text(block: BaselineBlockPayload) -> str:
    return (
        f"Baseline: {block['path']}  Added: {block['added']}  Moved: {block['moved']}  "
        f"Changed: {block['changed']}  Stale: {block['stale']}  Unchanged: {block['unchanged']}"
    )


def _resolved_project_root(record: RunRecord, project_path: str | None) -> Path | None:
    raw = project_path or record.project_path
    return Path(raw).expanduser().parent.resolve() if raw else None


def _baseline_target_path(args: argparse.Namespace, root: Path | None) -> Path:
    raw = getattr(args, "path", None)
    if raw is not None:
        text = str(raw).strip()
        if not text:
            raise CliError("--path must not be empty.", code="usage_error", exit_code=2)
        return Path(text).expanduser()
    if root is None:
        raise CliError(
            "No project could be resolved, so the baseline path is unknown. Pass --project PATH or --path PATH.",
            code="project_not_found",
            exit_code=2,
        )
    return root / BASELINE_FILENAME


def _resolve_baseline_run(args: argparse.Namespace) -> tuple[RunRecord, str | None, Path, Path]:
    """Resolve the run, its project root, and the baseline path for a command."""
    selector, project_path = _run_scope(args)
    record = _resolve_query_run(selector, project_path)
    root = _resolved_project_root(record, project_path)
    path = _baseline_target_path(args, root)
    effective_root = root if root is not None else path.resolve().parent
    return record, project_path, effective_root, path


def _resolve_analyze_baseline(path: Path | None, project_root: Path) -> Path | None:
    """Resolve a relative analyze baseline against the project, not the CWD."""
    if path is None:
        return None
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return (project_root / expanded).resolve()


def _load_analyze_baseline(path: Path | None, project_root: Path) -> tuple[Path | None, Baseline | None]:
    resolved = _resolve_analyze_baseline(path, project_root)
    return resolved, None if resolved is None else _load_baseline_for_cli(resolved)


def command_analyze(args: argparse.Namespace) -> int:
    options = _analyze_options(args)
    project = _resolve_project(options.project)
    _drain_quiet_warnings(options.output)
    baseline_path, baseline = _load_analyze_baseline(options.baseline, project.root)
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
    partial_failures = _admit_run_result(result, cfg, options, project_path=project_path, keys=keys)
    _write_diagnostics(result, options)
    record = _result_record(result, cfg, project_path=project_path)
    all_findings = flat_findings(record)
    findings = filter_findings(all_findings, FindingFilters(modules=options.modules))
    baseline_diff = None if baseline is None else diff_baseline(baseline, _baseline_entries(findings, project.root))
    summary: AnalyzeSummary = {
        **finding_summary(findings),
        "total_findings": len(all_findings),
        "targets": sum(1 for target in result.targets if not target.is_pseudo),
        "analyzers": len(result.selected_analyzers),
        "fail_on": options.fail_on,
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
    _attach_baseline(payload, baseline_path, baseline_diff)
    _emit_findings(options.output, payload=payload, findings=findings, text_lines=_analyze_text(payload))
    return _analyze_exit_code(
        findings=findings,
        fail_on=options.fail_on,
        baseline_diff=baseline_diff,
        partial_failures=partial_failures,
    )


def command_review(args: argparse.Namespace) -> int:
    """Generate Change Review artifacts for the selected targets.

    Exit codes: 0 when every selected target generated artifacts, 1 when some
    targets generated artifacts and some failed, and 2 when nothing was
    generated or the input cannot be reviewed.
    """
    options = _output_options(args)
    project = _resolve_project(args.project)
    _drain_quiet_warnings(options)
    cfg = _apply_target_filter(
        effective_project_config(project, quiet=options.quiet),
        tuple(str(value) for value in args.target),
    )
    _require_configured_targets(cfg)
    targets = get_analyzed_targets(cfg)
    output_dir = _review_output_dir(args.output_dir)
    try:
        outcome = run_change_review(cfg, targets, output_dir=output_dir)
    except ChangeReviewNoTargetsError as exc:
        raise CliError(str(exc), code="no_targets", exit_code=2) from exc
    except ChangeReviewOutputError as exc:
        raise CliError(str(exc), code="review_output_dir", exit_code=2) from exc
    except ChangeReviewError as exc:
        raise CliError(str(exc), code="review_failed", exit_code=2) from exc

    if not outcome.generated:
        _discard_output_file(options)
        raise CliError(
            "Change Review failed for every target and no artifacts were generated.",
            code="review_failed",
            exit_code=2,
            details={
                "failures": [{"target": failure.target, "message": failure.message} for failure in outcome.failures],
            },
        )

    payload = _review_payload(project.path, outcome)
    _emit_document(options, payload=payload, text_lines=_review_text(payload))
    return _review_exit_code(outcome)


def _review_output_dir(raw: object) -> Path | None:
    if raw is None:
        return None
    try:
        return Path(str(raw)).expanduser().resolve()
    except (OSError, RuntimeError) as exc:
        raise CliError(
            f"Review output directory is not usable: {raw}",
            code="review_output_dir",
            exit_code=2,
        ) from exc


def _review_payload(project_path: Path, outcome: ChangeReviewOutcome) -> ReviewPayload:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": "review",
        "project": str(project_path),
        "output_dir": str(Path(outcome.output_dir).resolve()),
        "targets": [
            {
                "target": generated.target,
                "json": str(Path(generated.json_path).resolve()),
                "markdown": str(Path(generated.markdown_path).resolve()),
            }
            for generated in outcome.generated
        ],
        "failures": [{"target": failure.target, "message": failure.message} for failure in outcome.failures],
        "generated_targets": outcome.generated_targets,
        "failed_targets": outcome.failed_targets,
    }


def _review_exit_code(outcome: ChangeReviewOutcome) -> int:
    if outcome.failures:
        return 1
    return 0


def _review_text(payload: ReviewPayload) -> list[str]:
    lines = [
        f"Change Review for {payload['project']}",
        f"Output: {payload['output_dir']}",
        f"Generated: {payload['generated_targets']} target(s)",
    ]
    for entry in payload["targets"]:
        lines.append(f"- {entry['target']}")
        lines.append(f"  JSON: {entry['json']}")
        lines.append(f"  Markdown: {entry['markdown']}")
    if payload["failures"]:
        lines.append(f"Failed: {payload['failed_targets']} target(s)")
        for failure in payload["failures"]:
            lines.append(f"- {failure['target']}: {failure['message']}")
    return lines


def _attach_baseline(
    payload: AnalyzePayload,
    path: Path | None,
    diff: BaselineDiff | None,
) -> None:
    if diff is not None and path is not None:
        payload["baseline"] = _baseline_block(path, diff)


def _analyze_exit_code(
    *,
    findings: list[FlatFinding],
    fail_on: FailOn,
    baseline_diff: BaselineDiff | None,
    partial_failures: tuple[TargetLoadFailure, ...],
) -> int:
    if partial_failures:
        return 2
    if baseline_diff is not None:
        return 1 if baseline_fails(baseline_diff, fail_on) else 0
    return 1 if _findings_reach_threshold(findings, fail_on) else 0


def _findings_reach_threshold(findings: Iterable[FlatFinding], fail_on: FailOn) -> bool:
    """Whether the filtered findings should fail the run at this threshold."""
    if fail_on == "none":
        return False
    for finding in findings:
        if fail_on == "any":
            return True
        if fail_on == "warning" and finding.severity in {"warning", "error"}:
            return True
        if fail_on == "error" and finding.severity == "error":
            return True
    return False


def _write_diagnostics(result: ChecksRunResult, options: _AnalyzeOptions) -> None:
    """Write human diagnostics through the shared sanitized stderr sink.

    The lines can carry target and file names from the project, so they are
    sanitized per line and cannot inject extra lines.
    """
    if not result.output_lines or options.output.quiet:
        return
    lines = (sanitize_terminal_text(line, keep_tabs=True) for line in result.output_lines)
    write_stream(sys.stderr, "\n".join(lines) + "\n")


def _analyze_text(payload: AnalyzePayload) -> list[str]:
    summary = payload["summary"]
    lines = [
        f"Run: {payload['run_id'] or '(not saved)'}",
        f"Targets: {summary.get('targets', 0)}  Analyzers: {summary.get('analyzers', 0)}  "
        f"Findings: {summary['findings']}  Fail on: {summary.get('fail_on', 'any')}",
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
    baseline_block = payload.get("baseline")
    if baseline_block is not None:
        lines.append(_baseline_counts_text(baseline_block))
    lines.extend(_finding_line(finding) for finding in payload["findings"])
    return lines


def _finding_line(finding: FindingPayload) -> str:
    module = finding["module"] or "(unknown)"
    target = finding["target"] or "(project)"
    location = format_source_location(
        file=finding["file"],
        line=finding["line"],
        column=finding["column"],
        end_line=finding["end_line"],
    )
    tag = f"[{finding['severity']}] "
    prefix = f"{tag}{target}  {location}  " if location else f"{tag}{target}  "
    return f"{prefix}{module}: {kind_human_label(finding['kind'])} - {finding['message']} ({finding['analyzer']})"


_LATEST_SELECTOR = "latest"

_SKIP_REASON_LABELS = {
    "unknown_schema": "its schema version is not supported by this build",
    "unreadable": "the record could not be read",
}


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
    return _selector_scope(str(args.run), args.project)


def _selector_scope(selector: str, raw_project: str | None) -> tuple[str, str | None]:
    if raw_project is None and selector.strip().casefold() != _LATEST_SELECTOR:
        return selector, None
    return selector, _scoped_project_path(raw_project)


def _same_project_path(left: str, right: str) -> bool:
    return os.path.normcase(left) == os.path.normcase(right)


def _in_project_scope(project_path: str, scope: str | None) -> bool:
    """Whether a stored run belongs to the query's project scope.

    Without a scope every run matches. With one, a run recorded before project
    scoping existed has no path and never matches, mirroring ``latest``.
    """
    if scope is None:
        return True
    return bool(project_path) and _same_project_path(project_path, scope)


def _newer_unreadable_run(run_id: str, *, project_path: str | None) -> SkippedRun | None:
    """The newest record that outranks *run_id* but could not be resolved.

    Run ids sort by the timestamp they start with, so a lexical comparison
    finds a record newer than the one ``latest`` resolved. Two cases count: a
    skipped record, and a listed record that ``latest`` passed over because its
    run file could not be loaded (a summary sidecar can outlive a record that a
    later build replaced). A record with no readable project path cannot be
    attributed, so it is treated as inside the scope.
    """
    scan = scan_runs()
    for skipped in scan.skipped:
        if skipped.run_id <= run_id:
            continue
        if project_path and skipped.project_path and not _same_project_path(skipped.project_path, project_path):
            continue
        return skipped
    for summary in scan.summaries:
        if summary.run_id <= run_id:
            continue
        if not _in_project_scope(summary.project_path, project_path):
            continue
        return SkippedRun(
            run_id=summary.run_id,
            reason="unreadable",
            detail="the record could not be loaded",
            project_path=summary.project_path,
        )
    return None


def _run_failure_reason(record: RunRecord) -> str:
    if record.failure_message:
        return record.failure_message.rstrip(".")
    failed = record.failed_analyzers
    if failed:
        shown = ", ".join(analyzer.name for analyzer in failed[:3])
        omitted = len(failed) - min(len(failed), 3)
        return f"{len(failed)} analyzer(s) failed: {shown}" + (f", and {omitted} more" if omitted else "")
    if record.failures:
        return record.failures[0].message.rstrip(".")
    if record.cancelled:
        return "the run was cancelled"
    return "no detail was recorded"


def _require_complete_run(record: RunRecord) -> None:
    """Refuse to present a failed run's stored findings as current.

    A target-load failure stores no findings at all, and an analyzer failure
    leaves an incomplete set, so the newest record is not a usable answer.
    """
    if record.effective_status != RUN_STATUS_FAILED:
        return
    raise CliError(
        f"Run {record.run_id} did not complete: {_run_failure_reason(record)}. Its stored findings are "
        "incomplete, so they are not returned as current. Inspect it with 'sattlint runs show', or pass "
        "--run ID to read a specific run.",
        code="run_failed",
        exit_code=2,
        details={"run_id": record.run_id, "status": record.effective_status},
    )


def _resolve_query_run(
    selector: str,
    project_path: str | None,
    *,
    allow_failed: bool = False,
) -> RunRecord:
    """Resolve a stored run for a query and refuse a misleading answer."""
    record = resolve_run(selector, project_path=project_path, require_project_scope=True)
    if selector.strip().casefold() == _LATEST_SELECTOR:
        unreadable = _newer_unreadable_run(record.run_id, project_path=project_path)
        if unreadable is not None:
            label = _SKIP_REASON_LABELS.get(unreadable.reason, unreadable.reason)
            raise CliError(
                f"Run {unreadable.run_id} is newer than the selected run but cannot be read: {label}. "
                "Run 'sattlint runs prune' to remove it, or pass --run ID to read a specific run.",
                code="run_unreadable",
                exit_code=2,
                details={
                    "run_id": unreadable.run_id,
                    "reason": unreadable.reason,
                    "detail": unreadable.detail,
                },
            )
    if not allow_failed:
        _require_complete_run(record)
    return record


def command_findings(args: argparse.Namespace) -> int:
    options = _output_options(args)
    requested_analyzers = tuple(str(value) for value in args.analyzer)
    if requested_analyzers:
        requested_analyzers = tuple(_resolve_analyzer_keys(requested_analyzers))
    selector, project_path = _run_scope(args)
    _drain_quiet_warnings(options)
    record = _resolve_query_run(selector, project_path)
    flattened = flat_findings(record)
    kinds, rules = normalize_finding_filters(
        (str(value) for value in args.kind),
        (str(value) for value in args.rule),
        record_kinds=(finding.finding.kind for finding in flattened),
        record_rules=(finding.finding.rule_id for finding in flattened if finding.finding.rule_id),
    )
    filters = FindingFilters(
        targets=tuple(str(value) for value in args.target),
        analyzers=requested_analyzers,
        modules=tuple(str(value) for value in args.module),
        exact_module=bool(args.exact_module),
        kinds=kinds,
        rules=rules,
    )
    findings = filter_findings(flattened, filters)
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
    truncation_note = run.get("truncation_note")
    if run.get("truncated") and isinstance(truncation_note, str) and truncation_note:
        header = f"{header}  Stored record truncated: {truncation_note}"
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
    record = _resolve_query_run(selector, project_path)
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
        f"Severity: {finding['severity']}",
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
        f"- **Severity:** `{finding['severity']}`",
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


def command_baseline_update(args: argparse.Namespace) -> int:
    """Accept the current findings as the checked-in baseline."""
    options = _output_options(args)
    record, _project_path, root, path = _resolve_baseline_run(args)
    _drain_quiet_warnings(options)
    entries = _baseline_entries(flat_findings(record), root)
    existing = _load_baseline_for_cli(path) if path.exists() else None
    generated_by = f"sattlint {__version__}"
    created = utc_now_iso()
    baseline = Baseline.create(entries, generated_by=generated_by, created=created)
    try:
        save_baseline(baseline, path)
    except BaselineWriteError as exc:
        raise CliError(
            str(exc),
            code="baseline_write_failed",
            exit_code=2,
            details={"path": str(path)},
        ) from exc
    payload: BaselineUpdatePayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "baseline update",
        "path": str(path),
        "entry_count": len(entries),
        "generated_by": generated_by,
        "created": created,
    }
    if existing is not None:
        diff = diff_baseline(existing, entries)
        payload["added"] = len(diff.added)
        payload["pruned"] = len(diff.stale)
    _emit_document(options, payload=payload, text_lines=_baseline_update_text(payload))
    return 0


def _baseline_update_text(payload: BaselineUpdatePayload) -> list[str]:
    lines = [
        f"Baseline: {payload['path']}",
        f"Entries: {payload['entry_count']}",
        f"Generated by: {payload['generated_by']}",
        f"Created: {payload['created']}",
    ]
    if "added" in payload and "pruned" in payload:
        lines.append(f"Added: {payload['added']}  Pruned: {payload['pruned']}")
    else:
        lines.append("Created a new baseline.")
    return lines


def command_baseline_diff(args: argparse.Namespace) -> int:
    """Report how a stored run differs from the baseline without writing."""
    options = _output_options(args)
    record, project_path, root, path = _resolve_baseline_run(args)
    _drain_quiet_warnings(options)
    baseline = _load_baseline_for_cli(path)
    diff = diff_baseline(baseline, _baseline_entries(flat_findings(record), root))
    payload: BaselineDiffPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "baseline diff",
        "path": str(path),
        "run": run_payload(record, project_path=project_path),
        "baseline": _baseline_block(path, diff),
    }
    _emit_document(options, payload=payload, text_lines=_baseline_diff_text(payload))
    return 0


def _baseline_diff_text(payload: BaselineDiffPayload) -> list[str]:
    block = payload["baseline"]
    lines = [_baseline_counts_text(block)]
    for entry in block["entries"]:
        location = format_source_location(
            file=entry["file"],
            line=entry["line"],
            column=None,
            end_line=None,
        )
        prefix = f"{location}  " if location else ""
        lines.append(
            f"[{entry['status']}] [{entry['severity']}] {prefix}{entry['module'] or '(unknown)'}: "
            f"{kind_human_label(entry['kind'])} - {entry['message']}"
        )
    return lines


def _run_summary_payload(summary: RunSummary) -> _RunSummaryPayload:
    return {
        "run_id": summary.run_id,
        "started_at": summary.started_at,
        "finished_at": summary.finished_at,
        "project_tag": summary.project_tag,
        "project_path": summary.project_path,
        "target_count": summary.target_count,
        "analyzer_count": summary.analyzer_count,
        "finding_count": summary.issue_count,
        "failure_count": summary.failure_count,
        "status": summary.status,
    }


def _skipped_run_payload(skipped: SkippedRun) -> _SkippedRunPayload:
    return {"run_id": skipped.run_id, "reason": skipped.reason, "detail": skipped.detail}


def _skip_reason_label(reason: str) -> str:
    return _SKIP_REASON_LABELS.get(reason, reason)


def _run_analyzer_payload(target_name: str, analyzer: RunAnalyzerRecord) -> _RunAnalyzerPayload:
    return {
        "target": target_name,
        "key": analyzer.key,
        "name": analyzer.name,
        "status": analyzer.status,
        "finding_count": len(analyzer.findings),
        "issue_count": analyzer.issue_count,
        "duration_ms": analyzer.duration_ms,
        "summary": analyzer.summary,
        "skip_reason": analyzer.skip_reason,
    }


def _run_analyzer_payloads(record: RunRecord) -> list[_RunAnalyzerPayload]:
    payloads = [
        _run_analyzer_payload(target.target_name, analyzer)
        for target in record.targets
        for analyzer in target.analyzers
    ]
    payloads.extend(_run_analyzer_payload("", analyzer) for analyzer in record.project_analyzers)
    return payloads


def _run_failure_payload(failure: RunFailure) -> _RunFailurePayload:
    return {
        "kind": failure.kind,
        "target": failure.target,
        "analyzer": failure.analyzer,
        "message": failure.message,
        "path": failure.path,
        "line": failure.line,
        "column": failure.column,
    }


def command_runs_list(args: argparse.Namespace) -> int:
    """List stored runs, newest first, scoped to the queried project."""
    options = _output_options(args)
    _drain_quiet_warnings(options)
    scope = _scoped_project_path(args.project)
    scan = scan_runs()
    summaries = [summary for summary in scan.summaries if _in_project_scope(summary.project_path, scope)]
    # A skipped record with no readable project path cannot be attributed, so it
    # stays visible in every scope: it is a store-health warning, not a run.
    skipped = [
        entry
        for entry in scan.skipped
        if scope is None or not entry.project_path or _same_project_path(entry.project_path, scope)
    ]
    limit = args.limit
    if limit is not None:
        summaries = summaries[:limit]
    payload: RunsListPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "runs list",
        "project": scope or "",
        "runs": [_run_summary_payload(summary) for summary in summaries],
        "skipped": [_skipped_run_payload(entry) for entry in skipped],
        "skipped_count": len(skipped),
    }
    _emit_document(options, payload=payload, text_lines=_runs_list_text(payload))
    return 0


def _runs_list_text(payload: RunsListPayload) -> list[str]:
    scope = payload["project"] or "(all projects)"
    lines = [f"Runs: {len(payload['runs'])}  Project: {scope}"]
    if payload["runs"]:
        lines.append(f"  {'Run ID':<30}  {'Started':<24}  {'Targets':>7}  {'Findings':>8}  Status    Project")
        for run in payload["runs"]:
            project = run["project_path"] or run["project_tag"] or "(unknown)"
            lines.append(
                f"  {run['run_id']:<30}  {run['started_at']:<24}  {run['target_count']:>7}  "
                f"{run['finding_count']:>8}  {run['status']:<8}  {project}"
            )
    else:
        lines.append("  No stored runs match this scope.")
    if payload["skipped"]:
        lines.append("")
        lines.append(f"Skipped: {payload['skipped_count']} record(s) this build cannot read.")
        for skipped in payload["skipped"]:
            detail = f" ({skipped['detail']})" if skipped["detail"] else ""
            lines.append(f"  - {skipped['run_id']}: {_skip_reason_label(skipped['reason'])}{detail}")
        lines.append("Run 'sattlint runs prune' to remove them.")
    return lines


def command_runs_show(args: argparse.Namespace) -> int:
    """Show one stored run, including its analyzer and failure detail."""
    options = _output_options(args)
    selector = str(args.run_id or "").strip()
    if not selector:
        raise CliError(
            "Run selector is empty. Use 'latest', a run id, or a unique run-id prefix.",
            code="run_invalid",
            exit_code=2,
        )
    selector, project_path = _selector_scope(selector, args.project)
    _drain_quiet_warnings(options)
    record = _resolve_query_run(selector, project_path, allow_failed=True)
    payload: RunShowPayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "runs show",
        "run": _run_summary_payload(RunSummary.from_record(record)),
        "cancelled": record.cancelled,
        "selected_analyzers": list(record.selected_analyzers),
        "truncated": record.truncated,
        "truncation_note": record.truncation_note or "",
        "failure_message": record.failure_message or "",
        "failure_reason": "" if record.effective_status == RUN_STATUS_OK else _run_failure_reason(record),
        "analyzers": _run_analyzer_payloads(record),
        "failures": [_run_failure_payload(failure) for failure in record.failures],
        "output_line_count": len(record.output_lines),
    }
    _emit_document(options, payload=payload, text_lines=_runs_show_text(payload))
    return 0


def _runs_show_text(payload: RunShowPayload) -> list[str]:
    run = payload["run"]
    project = run["project_path"] or run["project_tag"] or "(unknown)"
    lines = [
        f"Run:       {run['run_id']}",
        f"Started:   {run['started_at']}",
        f"Finished:  {run['finished_at']}",
        f"Status:    {run['status']}",
        f"Project:   {project}",
        f"Targets:   {run['target_count']}",
        f"Findings:  {run['finding_count']}",
        f"Analyzers: {run['analyzer_count']}",
    ]
    if run["status"] != RUN_STATUS_OK:
        lines.append(f"Reason:    {payload['failure_reason']}")
    if payload["cancelled"]:
        lines.append("Cancelled: yes")
    if payload["truncated"]:
        lines.append(f"Record:    truncated ({payload['truncation_note']})")
    if payload["failures"]:
        lines.append(f"Failures ({len(payload['failures'])}):")
        lines.extend(_run_failure_text(failure) for failure in payload["failures"])
    if payload["analyzers"]:
        lines.append("Analyzers:")
        lines.extend(_run_analyzer_text(analyzer) for analyzer in payload["analyzers"])
    return lines


def _run_failure_text(failure: _RunFailurePayload) -> str:
    subject = failure["target"] or "(project)"
    if failure["analyzer"]:
        subject = f"{subject}/{failure['analyzer']}"
    location = format_source_location(
        file=failure["path"],
        line=failure["line"],
        column=failure["column"],
        end_line=None,
    )
    where = f"  {location}" if location else ""
    return f"  - [{failure['kind']}] {subject}: {failure['message']}{where}"


def _run_analyzer_text(analyzer: _RunAnalyzerPayload) -> str:
    target = analyzer["target"] or "(project)"
    line = (
        f"  {target}  {analyzer['key']} ({analyzer['name']}): {analyzer['status']}, "
        f"{analyzer['finding_count']} finding(s)"
    )
    if analyzer["skip_reason"]:
        line = f"{line}, skipped: {analyzer['skip_reason']}"
    if analyzer["status"] == "failed" and analyzer["summary"]:
        line = f"{line} - {analyzer['summary']}"
    return line


def command_runs_prune(args: argparse.Namespace) -> int:
    """Remove run records this build cannot read, and optionally old readable ones."""
    options = _output_options(args)
    _drain_quiet_warnings(options)
    report: PruneReport = prune_unreadable_runs(keep=args.keep)
    payload: RunsPrunePayload = {
        "schema_version": SCHEMA_VERSION,
        "command": "runs prune",
        "removed": report.removed,
        "unreadable": report.unreadable,
        "over_limit": report.over_limit,
        "kept": report.kept,
        "removed_run_ids": list(report.removed_run_ids),
    }
    _emit_document(options, payload=payload, text_lines=_runs_prune_text(payload))
    return 0


def _runs_prune_text(payload: RunsPrunePayload) -> list[str]:
    lines = [
        f"Removed: {payload['removed']} run record(s)",
        f"  unreadable: {payload['unreadable']}",
        f"Kept: {payload['kept']} readable run record(s)",
    ]
    if payload["over_limit"]:
        lines.insert(2, f"  older than the requested keep count: {payload['over_limit']}")
    return lines


__all__ = [
    "RunShowPayload",
    "RunsListPayload",
    "RunsPrunePayload",
    "command_analyze",
    "command_analyzers_list",
    "command_baseline_diff",
    "command_baseline_update",
    "command_findings",
    "command_project_check",
    "command_project_init",
    "command_project_show",
    "command_project_targets",
    "command_runs_list",
    "command_runs_prune",
    "command_runs_show",
    "command_show",
]
