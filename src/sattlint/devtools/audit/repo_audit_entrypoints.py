"""Selected-check helpers for the repository audit."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import shlex
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from sattlint.devtools import pipeline as pipeline_module
from sattlint.devtools.shared import pipeline_checks as pipeline_checks_module
from sattlint.devtools.shared.pipeline_checks import matching_changed_files, normalize_changed_files

from . import _repo_audit_check_catalog as repo_audit_check_catalog_helpers
from . import _repo_audit_entrypoint_helpers as repo_audit_entrypoint_helpers
from . import _repo_audit_planning_helpers as repo_audit_planning_helpers

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


def _planning_string_list(value: object) -> list[str]:
    return repo_audit_planning_helpers.string_list(value)


def _repo_audit_entrypoints_module() -> Any:
    from . import repo_audit as repo_audit_module  # noqa: PLC0415

    return repo_audit_module


def _repo_audit_finding_check_definitions() -> tuple[dict[str, Any], ...]:
    return repo_audit_check_catalog_helpers.build_repo_audit_finding_check_definitions(
        verify_recommendations_runner=_run_verify_recommendations_check,
    )


def _run_verify_recommendations_check(_context: Any) -> list[Any]:
    from . import _repo_audit_check_specs as helper  # noqa: PLC0415

    return helper._run_verify_recommendations_check(_context)


def _shell_command(command: list[str]) -> str:
    return shlex.join(command)


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
        repo_root=_repo_audit_entrypoints_module().REPO_ROOT,
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
    return repo_audit_entrypoint_helpers._normalize_repo_audit_finding_checks(
        selected_checks,
        supported_check_ids=REPO_AUDIT_FINDING_CHECK_IDS,
    )


_cli_consistency_findings = repo_audit_entrypoint_helpers._cli_consistency_findings


def build_repo_audit_check_catalog(
    *,
    profile: str = "full",
    output_dir: Path | None = None,
    fail_on: str = "high",
) -> dict[str, Any]:
    from . import _repo_audit_check_specs as helper  # noqa: PLC0415

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
    from . import _repo_audit_check_specs as helper  # noqa: PLC0415

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
    repo_audit = _repo_audit_entrypoints_module()
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
    from . import _repo_audit_full_run as helper  # noqa: PLC0415

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
    from . import _repo_audit_full_run as helper  # noqa: PLC0415

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
    from . import _repo_audit_entrypoint_runs as helper  # noqa: PLC0415

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
    from . import _repo_audit_entrypoint_runs as helper  # noqa: PLC0415

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
        repo_audit=_repo_audit_entrypoints_module(),
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
    from sattlint.devtools.ai import ai_work_map as ai_work_map_module  # noqa: PLC0415

    return repo_audit_planning_helpers.build_check_my_changes_planning_report(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
        repo_audit=_repo_audit_entrypoints_module(),
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
    from . import _repo_audit_entrypoint_runs as helper  # noqa: PLC0415

    return helper.run_check_my_changes(
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


_severity_counts = repo_audit_entrypoint_helpers._severity_counts
_category_counts = repo_audit_entrypoint_helpers._category_counts
_max_severity = repo_audit_entrypoint_helpers._max_severity
_should_fail = repo_audit_entrypoint_helpers._should_fail
_blocking_finding_count = repo_audit_entrypoint_helpers._blocking_finding_count
_recommended_command = repo_audit_entrypoint_helpers._recommended_command
_format_terminal_finding_path = repo_audit_entrypoint_helpers._format_terminal_finding_path
_print_cli_summary = repo_audit_entrypoint_helpers._print_cli_summary
_default_corpus_manifest_dir = repo_audit_entrypoint_helpers._default_corpus_manifest_dir


__all__ = [
    "REPO_AUDIT_FINDING_CHECK_IDS",
    "REPO_AUDIT_INDIVIDUAL_CHECK_IDS",
    "REPO_AUDIT_SPECIAL_CHECK_IDS",
    "_blocking_finding_count",
    "_category_counts",
    "_default_corpus_manifest_dir",
    "_format_terminal_finding_path",
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
    "matching_changed_files",
    "run_check_my_changes",
    "run_recommended_repo_audit_finish_gate",
    "run_recommended_repo_audit_slice",
]


def __getattr__(name: str) -> Any:
    if name == "_repo_audit_module":
        return _repo_audit_entrypoints_module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
