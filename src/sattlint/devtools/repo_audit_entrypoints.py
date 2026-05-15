"""Selected-check helpers for the repository audit."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import subprocess  # nosec
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from sattlint.devtools import _repo_audit_check_catalog as repo_audit_check_catalog_helpers
from sattlint.devtools import _repo_audit_planning_helpers as repo_audit_planning_helpers
from sattlint.devtools import pipeline as pipeline_module
from sattlint.devtools import pipeline_checks as pipeline_checks_module
from sattlint.devtools.pipeline_artifacts import write_json_artifact
from sattlint.devtools.pipeline_checks import normalize_changed_files
from sattlint.path_sanitizer import sanitize_path_for_report

verify_check_catalog = pipeline_checks_module.verify_check_catalog

REPO_AUDIT_FINDING_CHECK_IDS = repo_audit_check_catalog_helpers.REPO_AUDIT_FINDING_CHECK_IDS
REPO_AUDIT_SPECIAL_CHECK_IDS = repo_audit_check_catalog_helpers.REPO_AUDIT_SPECIAL_CHECK_IDS
REPO_AUDIT_INDIVIDUAL_CHECK_IDS = repo_audit_check_catalog_helpers.REPO_AUDIT_INDIVIDUAL_CHECK_IDS
REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_GLOBS = (
    repo_audit_check_catalog_helpers.REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_GLOBS
)
REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_CHECK_IDS = (
    repo_audit_check_catalog_helpers.REPO_AUDIT_RECOMMENDATION_CONTROL_SURFACE_CHECK_IDS
)
REPO_AUDIT_RECOMMENDATION_FALLBACK_GLOBS = repo_audit_check_catalog_helpers.REPO_AUDIT_RECOMMENDATION_FALLBACK_GLOBS
AI_FEEDBACK_FILENAME = repo_audit_check_catalog_helpers.AI_FEEDBACK_FILENAME


def _mapping_of(value: object) -> dict[str, Any]:
    return repo_audit_planning_helpers.mapping_of(value)


def _string_list(value: object) -> list[str]:
    return repo_audit_planning_helpers.string_list(value)


def _repo_audit_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module

    return repo_audit_module


def _repo_audit_finding_check_definitions() -> tuple[dict[str, Any], ...]:
    return repo_audit_check_catalog_helpers.build_repo_audit_finding_check_definitions(
        repo_audit=_repo_audit_module(),
        verify_recommendations_runner=_run_verify_recommendations_check,
    )


def _run_verify_recommendations_check(_context: Any) -> list[Any]:
    from sattlint.devtools import _repo_audit_check_specs as helper

    return helper._run_verify_recommendations_check(_context)


def _shell_command(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def _changed_file_flag_args(changed_files: Iterable[str]) -> list[str]:
    args: list[str] = []
    for path_text in normalize_changed_files(changed_files):
        args.extend(["--changed-file", path_text])
    return args


def _focused_python_files(changed_files: Iterable[str]) -> list[str]:
    focused_files: list[str] = []
    for path_text in normalize_changed_files(changed_files):
        if not path_text.endswith(".py"):
            continue
        if not path_text.startswith(("src/", "tests/", "scripts/")):
            continue
        if path_text in focused_files:
            continue
        focused_files.append(path_text)
    return focused_files


def _owner_test_targets_for_checks(recommended_checks: Iterable[dict[str, Any]]) -> list[str]:
    targets: list[str] = []
    for entry in recommended_checks:
        for target in entry.get("owner_test_targets", []):
            target_text = str(target).strip()
            if not target_text or target_text in targets:
                continue
            targets.append(target_text)
    return targets


def _build_repo_audit_finish_gate_commands(
    *,
    profile: str,
    output_dir: Path,
    fail_on: str,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    ruff_command: list[str],
    pyright_command: list[str],
    python_command: list[str],
    pytest_workers: str | None = None,
) -> list[dict[str, Any]]:
    return repo_audit_check_catalog_helpers.build_repo_audit_finish_gate_commands(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
        recommended_checks=recommended_checks,
        ruff_command=ruff_command,
        pyright_command=pyright_command,
        python_command=python_command,
        repo_root=_repo_audit_module().REPO_ROOT,
        changed_file_flag_args=_changed_file_flag_args,
        focused_python_files=_focused_python_files,
        build_owner_pytest_step=pipeline_module._build_owner_pytest_step,
        shell_command=_shell_command,
        pytest_workers=pytest_workers,
    )


def _build_recommendation_why_this_gate(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    skipped_checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    return repo_audit_check_catalog_helpers.build_recommendation_why_this_gate(
        changed_files=changed_files,
        recommended_checks=recommended_checks,
        skipped_checks=skipped_checks,
    )


def _normalize_repo_audit_finding_checks(selected_checks: Iterable[str] | None) -> tuple[str, ...] | None:
    if selected_checks is None:
        return None
    supported = set(REPO_AUDIT_FINDING_CHECK_IDS)
    normalized: list[str] = []
    seen: set[str] = set()
    for check_id in selected_checks:
        normalized_id = str(check_id).strip()
        if not normalized_id:
            raise ValueError("At least one non-empty repo-audit finding check is required when selecting checks.")
        if normalized_id not in supported:
            supported_text = ", ".join(sorted(supported))
            raise ValueError(
                f"Unsupported repo-audit finding check '{normalized_id}'. Supported checks: {supported_text}."
            )
        if normalized_id in seen:
            continue
        seen.add(normalized_id)
        normalized.append(normalized_id)
    if not normalized:
        raise ValueError("At least one non-empty repo-audit finding check is required when selecting checks.")
    return tuple(normalized)


def _cli_consistency_findings(report: dict[str, Any]) -> list[Any]:
    repo_audit = _repo_audit_module()
    findings: list[Any] = []
    for entry in report.get("gaps", {}).get("undeclared_subcommands", []):
        findings.append(
            repo_audit.Finding(
                id="cli-consistency-undeclared-subcommand",
                category="feature-wiring",
                severity="medium",
                confidence="high",
                message=f"Documented CLI subcommand '{entry.get('subcommand')}' is not declared.",
                path=entry.get("referenced_in"),
                line=entry.get("line"),
                source="cli-consistency",
            )
        )
    for entry in report.get("gaps", {}).get("undeclared_scripts", []):
        findings.append(
            repo_audit.Finding(
                id="cli-consistency-undeclared-script",
                category="feature-wiring",
                severity="medium",
                confidence="high",
                message=f"Documented CLI script '{entry.get('script')}' is not declared.",
                path=entry.get("referenced_in"),
                line=entry.get("line"),
                source="cli-consistency",
            )
        )
    return findings


def build_repo_audit_check_catalog(
    *,
    profile: str = "full",
    output_dir: Path | None = None,
    fail_on: str = "high",
) -> dict[str, Any]:
    from sattlint.devtools import _repo_audit_check_specs as helper

    return helper.build_repo_audit_check_catalog(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
    )


def build_repo_audit_check_recommendations(
    *,
    profile: str = "full",
    output_dir: Path | None = None,
    fail_on: str = "high",
    changed_files: Iterable[str] | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import _repo_audit_check_specs as helper

    return helper.build_repo_audit_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
    )


def collect_custom_findings(
    root: Path | None = None,
    *,
    include_generated: bool = False,
    tracked_only: bool = False,
    suspicious_identifiers: Iterable[str] = (),
    selected_checks: Iterable[str] | None = None,
) -> list[Any]:
    repo_audit = _repo_audit_module()
    resolved_root = repo_audit.REPO_ROOT if root is None else root
    findings: list[Any] = []
    selected_check_ids = _normalize_repo_audit_finding_checks(selected_checks)
    selected_check_set = None if selected_check_ids is None else set(selected_check_ids)
    context = repo_audit._build_repo_audit_scan_context(
        resolved_root,
        include_generated=include_generated,
        tracked_only=tracked_only,
        suspicious_identifiers=suspicious_identifiers,
    )
    if selected_check_set is None or {"text-scan", "local-ci-parity"} & selected_check_set:
        context = repo_audit._with_shared_text_line_findings(context)
    for definition in repo_audit._repo_audit_finding_check_definitions():
        if selected_check_set is not None and definition["id"] not in selected_check_set:
            continue
        findings.extend(definition["runner"](context))
    return repo_audit._dedupe_findings(findings)


def _run_repo_audit_findings_checks(
    output_dir: Path,
    *,
    profile: str,
    check_ids: Sequence[str],
    fail_on: str,
    include_generated: bool,
    suspicious_identifiers: Iterable[str],
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import _repo_audit_full_run as helper

    return helper._run_repo_audit_findings_checks(
        output_dir,
        profile=profile,
        check_ids=check_ids,
        fail_on=fail_on,
        include_generated=include_generated,
        suspicious_identifiers=suspicious_identifiers,
        latest_output_dir=latest_output_dir,
    )


def _run_repo_audit_cli_consistency_check(
    output_dir: Path,
    *,
    fail_on: str,
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import _repo_audit_full_run as helper

    return helper._run_repo_audit_cli_consistency_check(
        output_dir,
        fail_on=fail_on,
        latest_output_dir=latest_output_dir,
    )


def run_recommended_repo_audit_slice(
    output_dir: Path,
    *,
    profile: str,
    fail_on: str,
    include_generated: bool,
    suspicious_identifiers: Iterable[str],
    skip_vulture: bool,
    skip_bandit: bool,
    changed_files: Iterable[str] | None,
    pytest_workers: str | None = None,
    latest_output_dir: Path | None = None,
    record_history: bool = True,
) -> dict[str, Any]:
    from sattlint.devtools import _repo_audit_entrypoint_runs as helper

    return helper.run_recommended_repo_audit_slice(
        output_dir,
        profile=profile,
        fail_on=fail_on,
        include_generated=include_generated,
        suspicious_identifiers=suspicious_identifiers,
        skip_vulture=skip_vulture,
        skip_bandit=skip_bandit,
        changed_files=changed_files,
        pytest_workers=pytest_workers,
        latest_output_dir=latest_output_dir,
        record_history=record_history,
    )


def run_recommended_repo_audit_finish_gate(
    output_dir: Path,
    *,
    profile: str,
    fail_on: str,
    include_generated: bool,
    suspicious_identifiers: Iterable[str],
    skip_vulture: bool,
    skip_bandit: bool,
    changed_files: Iterable[str] | None,
    pytest_workers: str | None = None,
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import _repo_audit_entrypoint_runs as helper

    return helper.run_recommended_repo_audit_finish_gate(
        output_dir,
        profile=profile,
        fail_on=fail_on,
        include_generated=include_generated,
        suspicious_identifiers=suspicious_identifiers,
        skip_vulture=skip_vulture,
        skip_bandit=skip_bandit,
        changed_files=changed_files,
        pytest_workers=pytest_workers,
        latest_output_dir=latest_output_dir,
    )


def _selected_surface_and_reason(recommendation: dict[str, Any]) -> tuple[str, str]:
    return repo_audit_planning_helpers.selected_surface_and_reason(recommendation)


def _build_selected_finish_gate_plan(
    *,
    profile: str,
    output_dir: Path,
    fail_on: str,
    selected_surface: str,
    changed_files: Iterable[str],
    planning_context: dict[str, Any],
    recommendation: dict[str, Any],
) -> dict[str, Any]:
    return repo_audit_planning_helpers.build_selected_finish_gate_plan(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        selected_surface=selected_surface,
        changed_files=changed_files,
        planning_context=planning_context,
        recommendation=recommendation,
        repo_audit=_repo_audit_module(),
        pipeline_module=pipeline_module,
        normalize_changed_files=normalize_changed_files,
    )


def build_check_my_changes_planning_report(
    *,
    profile: str = "full",
    output_dir: Path | None = None,
    fail_on: str = "high",
    changed_files: Iterable[str] | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import ai_work_map as ai_work_map_module

    return repo_audit_planning_helpers.build_check_my_changes_planning_report(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
        repo_audit=_repo_audit_module(),
        build_repo_audit_check_recommendations=build_repo_audit_check_recommendations,
        build_change_proof_requirements=pipeline_module.build_change_proof_requirements,
        build_planning_context=ai_work_map_module.build_planning_context,
        build_selected_finish_gate_plan_fn=_build_selected_finish_gate_plan,
    )


def _first_failed_finish_gate_step(finish_gate_report: dict[str, Any]) -> dict[str, Any] | None:
    return repo_audit_planning_helpers.first_failed_finish_gate_step(finish_gate_report)


def _build_ai_feedback_report(
    *,
    changed_files: list[str],
    selected_surface: str,
    selected_reason: str,
    selected_command: str,
    overall_status: str,
    finish_gate_status: str,
    reports: dict[str, str],
    planning_context: dict[str, Any],
    recommendation: dict[str, Any],
    selected_result: dict[str, Any],
) -> dict[str, Any]:
    return repo_audit_planning_helpers.build_ai_feedback_report(
        changed_files=changed_files,
        selected_surface=selected_surface,
        selected_reason=selected_reason,
        selected_command=selected_command,
        overall_status=overall_status,
        finish_gate_status=finish_gate_status,
        reports=reports,
        planning_context=planning_context,
        recommendation=recommendation,
        selected_result=selected_result,
    )


def run_check_my_changes(
    output_dir: Path,
    *,
    profile: str,
    fail_on: str,
    include_generated: bool,
    suspicious_identifiers: Iterable[str],
    skip_vulture: bool,
    skip_bandit: bool,
    changed_files: Iterable[str] | None,
    pytest_workers: str | None = None,
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    repo_audit = _repo_audit_module()
    output_dir.mkdir(parents=True, exist_ok=True)
    planning_report = build_check_my_changes_planning_report(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
    )
    recommendation = planning_report["recommendation"]
    resolved_changed_files = planning_report["changed_files"]
    selected_surface = planning_report["selected_surface"]
    selected_reason = planning_report["selected_reason"]
    planning_context = planning_report["planning_context"]
    sanitized_output_dir = (
        sanitize_path_for_report(output_dir.resolve(), repo_root=repo_audit.REPO_ROOT)
        or output_dir.resolve().as_posix()
    )

    if selected_surface == "pipeline":
        selected_output_dir = output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME
        selected_output_dir.mkdir(parents=True, exist_ok=True)
        sanitized_selected_output_dir = (
            sanitize_path_for_report(selected_output_dir.resolve(), repo_root=repo_audit.REPO_ROOT)
            or selected_output_dir.resolve().as_posix()
        )
        selected_command_argv = [
            "sattlint-analysis-pipeline",
            "--profile",
            profile,
            "--run-recommended-finish-gate",
            *_changed_file_flag_args(resolved_changed_files),
            "--output-dir",
            sanitized_selected_output_dir,
        ]
        if pytest_workers is not None and str(pytest_workers).strip():
            selected_command_argv.extend(["--pytest-workers", str(pytest_workers).strip()])
        selected_result = pipeline_module.run_recommended_pipeline_finish_gate(
            selected_output_dir,
            trace_target=(
                pipeline_module.DEFAULT_TRACE_TARGET if pipeline_module.DEFAULT_TRACE_TARGET.exists() else None
            ),
            profile=profile,
            include_vulture=False if skip_vulture else None,
            include_bandit=False if skip_bandit else None,
            baseline_findings=None,
            corpus_manifest_dir=_default_corpus_manifest_dir(),
            changed_files=resolved_changed_files,
            slow_phase_threshold_ms=25.0,
            phase_budget_ms=50.0,
            total_budget_ms=250.0,
            fail_on_drift=False,
            fail_on_budget=False,
            pytest_workers=pytest_workers,
        )
        overall_status = selected_result["overall_status"]
        finish_gate_status = selected_result["finish_gate"]["status"]
        selected_reports = {
            "status": f"{sanitized_selected_output_dir}/status.json",
            "summary": f"{sanitized_selected_output_dir}/summary.json",
            "finish_gate": f"{sanitized_selected_output_dir}/finish_gate.json",
        }
    else:
        sanitized_selected_output_dir = sanitized_output_dir
        selected_command_argv = [
            "sattlint-repo-audit",
            "--profile",
            profile,
            "--run-recommended-finish-gate",
            *_changed_file_flag_args(resolved_changed_files),
            "--fail-on",
            fail_on,
            "--output-dir",
            sanitized_selected_output_dir,
        ]
        if pytest_workers is not None and str(pytest_workers).strip():
            selected_command_argv.extend(["--pytest-workers", str(pytest_workers).strip()])
        selected_result = run_recommended_repo_audit_finish_gate(
            output_dir,
            profile=profile,
            fail_on=fail_on,
            include_generated=include_generated,
            suspicious_identifiers=suspicious_identifiers,
            skip_vulture=skip_vulture,
            skip_bandit=skip_bandit,
            changed_files=resolved_changed_files,
            pytest_workers=pytest_workers,
            latest_output_dir=latest_output_dir,
        )
        overall_status = selected_result["overall_status"]
        finish_gate_status = selected_result["finish_gate"]["status"]
        selected_reports = {
            "status": f"{sanitized_selected_output_dir}/status.json",
            "summary": f"{sanitized_selected_output_dir}/summary.json",
            "finish_gate": f"{sanitized_selected_output_dir}/finish_gate.json",
        }

    report_path = f"{sanitized_output_dir}/check_my_changes.json"
    reports = {
        **selected_reports,
        "check_my_changes": report_path,
        "ai_feedback": f"{sanitized_output_dir}/{AI_FEEDBACK_FILENAME}",
    }
    ai_feedback = _build_ai_feedback_report(
        changed_files=resolved_changed_files,
        selected_surface=selected_surface,
        selected_reason=selected_reason,
        selected_command=_shell_command(selected_command_argv),
        overall_status=overall_status,
        finish_gate_status=finish_gate_status,
        reports=reports,
        planning_context=planning_context,
        recommendation=recommendation,
        selected_result=selected_result,
    )
    write_json_artifact(output_dir / AI_FEEDBACK_FILENAME, ai_feedback)
    report = {
        "kind": "sattlint.check_my_changes",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "profile": profile,
        "fail_on": fail_on,
        "output_dir": sanitized_output_dir,
        "report_path": report_path,
        "changed_files": resolved_changed_files,
        "selected_surface": selected_surface,
        "selected_reason": selected_reason,
        "selected_command": _shell_command(selected_command_argv),
        "overall_status": overall_status,
        "finish_gate_status": finish_gate_status,
        "reports": reports,
        "timing": {
            "selected_run": (
                dict(_mapping_of(_mapping_of(selected_result.get("pipeline_summary")).get("timing")))
                if selected_surface == "pipeline"
                else dict(_mapping_of(selected_result.get("timing")))
            ),
            "finish_gate": dict(_mapping_of(_mapping_of(selected_result.get("finish_gate")).get("timing"))),
        },
        "proof_requirements": planning_report.get("proof_requirements", {}),
        "planning_context": planning_context,
        "ai_feedback": ai_feedback,
        "recommendation": {
            "fallback_required": recommendation["fallback_required"],
            "fallback_reason": recommendation["fallback_reason"],
            "recommended_check_ids": recommendation["recommended_check_ids"],
            "recommended_pipeline_check_ids": recommendation["recommended_pipeline_check_ids"],
            "recommended_repo_audit_check_ids": recommendation["recommended_repo_audit_check_ids"],
        },
    }
    write_json_artifact(output_dir / "check_my_changes.json", report)
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="check_my_changes",
        primary_payload=report,
        status_payload=None,
        summary_payload=None,
    )
    return report


def _severity_counts(findings: Iterable[Any]) -> dict[str, int]:
    counts = Counter(finding.severity for finding in findings)
    return {severity: counts.get(severity, 0) for severity in ("critical", "high", "medium", "low")}


def _category_counts(findings: Iterable[Any]) -> dict[str, int]:
    counts = Counter(finding.category for finding in findings)
    return dict(sorted(counts.items()))


def _max_severity(findings: Iterable[Any]) -> str | None:
    repo_audit = _repo_audit_module()
    max_finding = max(findings, key=lambda item: repo_audit.SEVERITY_RANK[item.severity], default=None)
    return None if max_finding is None else max_finding.severity


def _should_fail(findings: Iterable[Any], threshold: str) -> bool:
    repo_audit = _repo_audit_module()
    minimum_rank = repo_audit.SEVERITY_RANK[threshold]
    return any(repo_audit.SEVERITY_RANK[finding.severity] >= minimum_rank for finding in findings)


def _blocking_finding_count(findings: Iterable[Any], threshold: str) -> int:
    repo_audit = _repo_audit_module()
    minimum_rank = repo_audit.SEVERITY_RANK[threshold]
    return sum(1 for finding in findings if repo_audit.SEVERITY_RANK[finding.severity] >= minimum_rank)


def _recommended_command(*, output_dir: str, profile: str, fail_on: str, leaks_only: bool) -> str:
    parts = ["sattlint-repo-audit"]
    if leaks_only:
        parts.append("--leaks-only")
    else:
        parts.extend(["--profile", profile])
    parts.extend(["--fail-on", fail_on, "--output-dir", output_dir])
    return " ".join(parts)


def _format_terminal_finding_path(path: str | None, line: int | None) -> str:
    if path is None:
        return ""
    if line is None:
        return f" [{path}]"
    return f" [{path}:{line}]"


def _print_terminal_findings(findings: Iterable[dict[str, Any]]) -> None:
    finding_list = list(findings)
    if not finding_list:
        return
    print("Detailed findings:")
    for finding in finding_list:
        path_suffix = _format_terminal_finding_path(finding.get("path"), finding.get("line"))
        print(
            f"- {finding['severity'].upper()} {finding['category']} {finding['id']}{path_suffix}: {finding['message']}"
        )
        detail = finding.get("detail")
        if detail:
            print(f"  detail: {detail}")
        suggestion = finding.get("suggestion")
        if suggestion:
            print(f"  suggestion: {suggestion}")


def _print_cli_summary(status_report: dict[str, Any]) -> None:
    print(f"Audit profile: {status_report['profile']}")
    print(f"Overall status: {status_report['overall_status']}")
    findings_schema = status_report.get("findings_schema")
    if findings_schema:
        print(
            f"Findings schema: {findings_schema.get('kind', 'unknown')} v{findings_schema.get('schema_version', '?')}"
        )
    print(
        "Findings: "
        f"{status_report['finding_count']} total, "
        f"{status_report['blocking_finding_count']} blocking at fail-on {status_report['fail_on']}"
    )
    print(f"Status report: {status_report['status_report']}")
    print(f"Summary report: {status_report['summary_report']}")
    latest_status_report = status_report.get("latest_status_report")
    latest_summary_report = status_report.get("latest_summary_report")
    if latest_status_report and latest_summary_report:
        print(f"Latest status report: {latest_status_report}")
        print(f"Latest summary report: {latest_summary_report}")
    _print_terminal_findings(status_report.get("findings", ()))


def _default_corpus_manifest_dir() -> Path | None:
    manifest_dir = pipeline_module.DEFAULT_CORPUS_MANIFEST_DIR.resolve()
    if not manifest_dir.exists():
        return None
    if not any(manifest_dir.rglob("*.json")):
        return None
    return manifest_dir


__all__ = [
    "REPO_AUDIT_FINDING_CHECK_IDS",
    "REPO_AUDIT_INDIVIDUAL_CHECK_IDS",
    "REPO_AUDIT_SPECIAL_CHECK_IDS",
    "_blocking_finding_count",
    "_category_counts",
    "_default_corpus_manifest_dir",
    "_max_severity",
    "_print_cli_summary",
    "_recommended_command",
    "_repo_audit_finding_check_definitions",
    "_run_repo_audit_cli_consistency_check",
    "_run_repo_audit_findings_checks",
    "_severity_counts",
    "_should_fail",
    "build_check_my_changes_planning_report",
    "build_repo_audit_check_catalog",
    "build_repo_audit_check_recommendations",
    "collect_custom_findings",
    "run_check_my_changes",
    "run_recommended_repo_audit_finish_gate",
    "run_recommended_repo_audit_slice",
]
