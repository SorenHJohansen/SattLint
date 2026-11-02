"""Headless CLI commands for agents and automation."""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from ..analyzers.catalog import (
    canonicalize_analyzer_keys,
    get_actual_cli_analyzer_keys,
    get_default_analyzer_catalog,
)
from ..application.analyze import collect_checks_result
from ..application.checks import build_run_record
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
    CliError,
    base_payload,
    emit_json,
    emit_ndjson,
    emit_text,
    output_path,
)
from ._project import (
    effective_project_config,
    project_payload,
    resolve_project_file,
    validate_project,
)


def command_project_show(args: Any) -> int:
    project = resolve_project_file(args.project)
    payload = base_payload(command="project show", project=project_payload(project))
    output = output_path(args.output)
    if args.format == "json":
        emit_json(payload, output=output)
    else:
        _emit_project_text(project_payload(project), output=output)
    return 0


def _emit_project_text(project: dict[str, Any], *, output: Path | None) -> None:
    paths = cast(dict[str, object], project["paths"])
    lines = [
        f"Project: {project['path']}",
        f"Root:    {project['root']}",
        f"Mode:    {project['mode']}",
        f"Targets: {', '.join(cast(list[str], project['targets'])) or '(none)'}",
        f"program_dir: {paths['program_dir']}",
        f"ABB_lib_dir: {paths['ABB_lib_dir']}",
        f"icf_dir: {paths['icf_dir']}",
        f"other_lib_dirs: {', '.join(cast(list[str], paths['other_lib_dirs'])) or '(none)'}",
        f"Runs:    {project['runs_dir']}",
        f"Review:  {project['review_output_dir']}",
    ]
    emit_text(lines, output=output)


def command_project_validate(args: Any) -> int:
    project = resolve_project_file(args.project)
    validation = validate_project(project)
    payload = base_payload(command="project validate", **validation)
    output = output_path(args.output)
    if args.format == "json":
        emit_json(payload, output=output)
    else:
        emit_text(_validation_text(validation), output=output)
    return 0 if validation["ok"] else 2


def _validation_text(validation: dict[str, Any]) -> list[str]:
    project_path = validation["project_path"]
    if validation["ok"]:
        return [f"Project is valid: {project_path}"]
    lines = [f"Project is invalid: {project_path}"]
    for error in cast(list[dict[str, str]], validation["errors"]):
        lines.append(f"- [{error['key_path']}] {error['message']}")
    return lines


def command_analyzers_list(args: Any) -> int:
    catalog = get_default_analyzer_catalog()
    default_keys = set(catalog_default_keys())
    analyzers: list[dict[str, object]] = []
    for metadata in catalog.analyzers:
        entry: dict[str, object] = metadata.to_dict()
        entry["default"] = metadata.spec.key in default_keys
        analyzers.append(entry)
    payload = base_payload(command="analyzers list", analyzers=analyzers)
    output = output_path(args.output)
    if args.format == "json":
        emit_json(payload, output=output)
    else:
        lines: list[str] = []
        for entry in analyzers:
            marker = "*" if entry["default"] else " "
            lines.append(f"{marker} {entry['key']:<24} {entry['category']:<12} {entry['name']}")
        emit_text(lines, output=output)
    return 0


def catalog_default_keys() -> tuple[str, ...]:
    return get_actual_cli_analyzer_keys()


def _resolve_analyzer_keys(requested: list[str]) -> list[str] | None:
    if not requested:
        return None
    canonical = list(canonicalize_analyzer_keys(requested))
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


def _apply_target_filter(cfg: ConfigDict, requested: list[str]) -> ConfigDict:
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


def _capture_run(cfg: ConfigDict, keys: list[str] | None, *, use_cache: bool, persist_run: bool) -> tuple[Any, str]:
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            result = collect_checks_result(cfg, keys, use_cache=use_cache, persist_run=persist_run)
    except TargetLoadError as exc:
        raise CliError(str(exc), code="target_load_failed", exit_code=2) from exc
    return result, buffer.getvalue()


def _result_record(result: Any, cfg: ConfigDict) -> RunRecord:
    record = build_run_record(result, cfg)
    if result.run_id:
        record = replace(record, run_id=result.run_id)
    return record


def command_analyze(args: Any) -> int:
    project = resolve_project_file(args.project)
    cfg = _apply_target_filter(effective_project_config(project), args.target)
    keys = _resolve_analyzer_keys(args.analyzer)
    result, captured = _capture_run(cfg, keys, use_cache=not args.no_cache, persist_run=not args.no_save)
    if captured and not args.quiet:
        sys.stderr.write(captured)
        sys.stderr.flush()
    if result.cancelled:
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
    record = _result_record(result, cfg)
    all_findings = flat_findings(record)
    filters = FindingFilters(modules=tuple(args.module))
    findings = filter_findings(all_findings, filters)
    summary = finding_summary(findings)
    summary["total_findings"] = len(all_findings)
    summary["targets"] = len(result.targets)
    summary["analyzers"] = len(result.selected_analyzers)
    payload = base_payload(
        command="analyze",
        run_id=result.run_id,
        cancelled=result.cancelled,
        project={
            "path": str(project.path),
            "targets": list(cfg.get("analyzed_programs_and_libraries", [])),
        },
        selected_analyzers=list(result.selected_analyzers),
        summary=summary,
        findings=[finding_payload(finding) for finding in findings],
    )
    _emit_analyze(args, payload, findings)
    if args.fail_on == "any" and findings:
        return 1
    return 0


def _emit_analyze(args: Any, payload: dict[str, Any], findings: list[FlatFinding]) -> None:
    output = output_path(args.output)
    if args.format == "json":
        emit_json(payload, output=output)
    elif args.format == "ndjson":
        emit_ndjson((finding_payload(finding) for finding in findings), output=output)
    else:
        emit_text(_analyze_text(payload), output=output)


def _analyze_text(payload: dict[str, Any]) -> list[str]:
    summary = cast(dict[str, object], payload["summary"])
    lines = [
        f"Run: {payload['run_id'] or '(not saved)'}",
        f"Targets: {summary['targets']}  Analyzers: {summary['analyzers']}  Findings: {summary['findings']}",
    ]
    for finding in cast(list[dict[str, Any]], payload["findings"]):
        lines.append(_finding_line(finding))
    return lines


def _finding_line(finding: dict[str, Any]) -> str:
    module = finding["module"] or "(unknown)"
    rule = f" [{finding['rule_id']}]" if finding["rule_id"] else ""
    return f"{module}: {finding['kind']}{rule} - {finding['message']} ({finding['analyzer']})"


def command_findings(args: Any) -> int:
    record = resolve_run(args.run)
    findings = filter_findings(
        flat_findings(record),
        FindingFilters(
            targets=tuple(args.target),
            analyzers=tuple(args.analyzer),
            modules=tuple(args.module),
            exact_module=args.exact_module,
            kinds=tuple(args.kind),
            rules=tuple(args.rule),
        ),
    )
    matched = len(findings)
    if args.limit is not None:
        findings = findings[: args.limit]
    groups = group_findings(findings, args.group_by)
    summary = finding_summary(findings)
    summary["matched"] = matched
    payload = base_payload(
        command="findings",
        run=run_payload(record),
        filters={
            "target": list(args.target),
            "analyzer": list(args.analyzer),
            "module": list(args.module),
            "exact_module": args.exact_module,
            "kind": list(args.kind),
            "rule": list(args.rule),
            "group_by": args.group_by,
            "limit": args.limit,
        },
        summary=summary,
        groups=groups,
        findings=[finding_payload(finding) for finding in findings],
    )
    output = output_path(args.output)
    if args.format == "json":
        emit_json(payload, output=output)
    elif args.format == "ndjson":
        emit_ndjson((finding_payload(finding) for finding in findings), output=output)
    else:
        emit_text(_findings_text(payload), output=output)
    return 0


def _findings_text(payload: dict[str, Any]) -> list[str]:
    run = cast(dict[str, object], payload["run"])
    summary = cast(dict[str, object], payload["summary"])
    lines = [
        f"Run: {run['run_id']}  Findings: {summary['findings']} (matched {summary['matched']})",
    ]
    groups = cast(list[dict[str, Any]], payload["groups"])
    if groups:
        for group in groups:
            lines.append(f"{group['key']} ({group['count']})")
        return lines
    for finding in cast(list[dict[str, Any]], payload["findings"]):
        lines.append(_finding_line(finding))
    return lines


def command_show(args: Any) -> int:
    record = resolve_run(args.run)
    findings = flat_findings(record)
    match = next((finding for finding in findings if finding.id == args.finding_id), None)
    if match is None:
        raise CliError(
            f"Finding {args.finding_id!r} was not found in run {record.run_id}.",
            code="finding_not_found",
            exit_code=2,
            details={"run_id": record.run_id},
        )
    payload = base_payload(
        command="show",
        run=run_payload(record),
        finding=finding_payload(match),
    )
    output = output_path(args.output)
    if args.format == "json":
        emit_json(payload, output=output)
    elif args.format == "markdown":
        emit_text(_finding_markdown(payload), output=output)
    else:
        emit_text(_finding_text(payload), output=output)
    return 0


def _finding_text(payload: dict[str, Any]) -> list[str]:
    finding = cast(dict[str, Any], payload["finding"])
    lines = [
        f"Finding: {finding['id']}",
        f"Module:  {finding['module'] or '(unknown)'}",
        f"Kind:    {finding['kind']}",
    ]
    if finding["rule_id"]:
        lines.append(f"Rule:    {finding['rule_id']}")
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


def _finding_markdown(payload: dict[str, Any]) -> list[str]:
    finding = cast(dict[str, Any], payload["finding"])
    run = cast(dict[str, object], payload["run"])
    lines = [
        f"# {finding['kind']}: {finding['module'] or '(unknown)'}",
        "",
        f"- **Finding:** `{finding['id']}`",
        f"- **Run:** `{run['run_id']}`",
        f"- **Analyzer:** `{finding['analyzer']}`",
        f"- **Target:** `{finding['target']}`",
    ]
    if finding["rule_id"]:
        lines.append(f"- **Rule:** `{finding['rule_id']}`")
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
    "command_project_validate",
    "command_show",
]
