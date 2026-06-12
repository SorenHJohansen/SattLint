"""Finish-gate and proof helpers for the pipeline CLI."""

from __future__ import annotations

import shlex
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sattlint.devtools.json_helpers import json_mapping as _json_mapping
from sattlint.path_sanitizer import sanitize_path_for_report

from ._pipeline_change_proof import (
    build_change_proof_requirements,
    evaluate_change_scoped_coverage_proof,
)

FINISH_GATE_MAX_WORKERS = 2
_PIPELINE_REUSED_FINISH_GATE_STEP_IDS = {
    "ruff-touched-python": "ruff",
    "pyright-touched-python": "pyright",
}


def _shell_command(command: list[str]) -> str:
    return shlex.join(command)


def _changed_file_flag_args(changed_files: Iterable[str]) -> list[str]:
    from sattlint.devtools import pipeline as pipeline_module  # noqa: PLC0415

    args: list[str] = []
    for path_text in pipeline_module.normalize_changed_files(changed_files):
        args.extend(["--changed-file", path_text])
    return args


def _pytest_worker_args(pytest_workers: str | None) -> list[str]:
    if pytest_workers is None:
        return []
    normalized = str(pytest_workers).strip()
    if not normalized:
        return []
    return ["-n", normalized]


def _focused_python_files(changed_files: Iterable[str]) -> list[str]:
    from sattlint.devtools import pipeline as pipeline_module  # noqa: PLC0415

    focused_files: list[str] = []
    for path_text in pipeline_module.normalize_changed_files(changed_files):
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


def _changed_source_python_files(changed_files: Iterable[str]) -> list[str]:
    return [path_text for path_text in _focused_python_files(changed_files) if path_text.startswith("src/")]


def _finish_gate_pipeline_check_ids(
    *,
    recommended_check_ids: Iterable[str],
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    pytest_workers: str | None = None,
) -> list[str]:
    selected_checks = list(dict.fromkeys(str(check_id) for check_id in recommended_check_ids if str(check_id).strip()))
    owner_pytest_step = _build_owner_pytest_step(
        changed_files=changed_files,
        recommended_checks=recommended_checks,
        python_command=["python"],
        coverage_output_path=Path("coverage_proof.xml"),
        pytest_workers=pytest_workers,
    )
    if owner_pytest_step is None or "pytest" not in selected_checks:
        return selected_checks
    return [check_id for check_id in selected_checks if check_id != "pytest"]


def _build_owner_pytest_step(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    python_command: list[str],
    coverage_output_path: Path,
    pytest_workers: str | None = None,
) -> dict[str, Any] | None:
    owner_test_targets = _owner_test_targets_for_checks(recommended_checks)
    if not owner_test_targets:
        return None
    touched_source_files = _changed_source_python_files(changed_files)
    if touched_source_files:
        pytest_argv = [
            *python_command,
            "-m",
            "pytest",
            *_pytest_worker_args(pytest_workers),
            *owner_test_targets,
            "-x",
            "-q",
            "--tb=short",
        ]
        pytest_argv.extend(f"--cov={path_text}" for path_text in touched_source_files)
        pytest_argv.extend(
            [
                "--cov-report=term-missing",
                f"--cov-report=xml:{coverage_output_path.resolve()}",
                "--cov-fail-under=0",
            ]
        )
        return {
            "id": "owner-pytest-coverage",
            "label": "Run owner pytest targets with focused coverage for touched source files",
            "command": _shell_command(pytest_argv),
            "argv": pytest_argv,
            "coverage_output_path": str(coverage_output_path.resolve()),
        }
    pytest_argv = [
        *python_command,
        "-m",
        "pytest",
        *_pytest_worker_args(pytest_workers),
        "--no-cov",
        *owner_test_targets,
        "-x",
        "-q",
        "--tb=short",
    ]
    return {
        "id": "owner-pytest",
        "label": "Run owner pytest targets for the recommended checks",
        "command": _shell_command(pytest_argv),
        "argv": pytest_argv,
    }


def _build_finish_gate_commands(
    *,
    profile: str,
    output_dir: Path,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    ruff_command: list[str],
    pyright_command: list[str],
    python_command: list[str],
    pytest_workers: str | None = None,
) -> list[dict[str, Any]]:
    from sattlint.devtools import pipeline as pipeline_module  # noqa: PLC0415

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    commands: list[dict[str, Any]] = []
    coverage_output_path = output_dir / "coverage_proof.xml"
    recommended_slice_command = [
        "sattlint-analysis-pipeline",
        "--profile",
        profile,
        "--run-recommended-slice",
        *_changed_file_flag_args(normalized_changed_files),
        "--output-dir",
        (
            sanitize_path_for_report(output_dir.resolve(), repo_root=pipeline_module.REPO_ROOT)
            or output_dir.resolve().as_posix()
        ),
    ]
    if pytest_workers is not None and str(pytest_workers).strip():
        recommended_slice_command.extend(["--pytest-workers", str(pytest_workers).strip()])
    commands.append(
        {
            "id": "recommended-slice",
            "label": "Run the recommended pipeline slice",
            "command": _shell_command(recommended_slice_command),
            "argv": recommended_slice_command,
        }
    )
    touched_python_files = _focused_python_files(normalized_changed_files)
    if touched_python_files:
        ruff_argv = [*ruff_command, "check", *touched_python_files]
        pyright_argv = [*pyright_command, *touched_python_files]
        commands.append(
            {
                "id": "ruff-touched-python",
                "label": "Run Ruff on touched Python files",
                "command": _shell_command(ruff_argv),
                "argv": ruff_argv,
            }
        )
        commands.append(
            {
                "id": "pyright-touched-python",
                "label": "Run Pyright on touched Python files",
                "command": _shell_command(pyright_argv),
                "argv": pyright_argv,
            }
        )
    owner_pytest_step = _build_owner_pytest_step(
        changed_files=normalized_changed_files,
        recommended_checks=recommended_checks,
        python_command=python_command,
        coverage_output_path=coverage_output_path,
        pytest_workers=pytest_workers,
    )
    if owner_pytest_step is not None:
        commands.append(owner_pytest_step)
    return commands


def _step_status_from_exit_code(exit_code: int | None) -> str:
    return "pass" if exit_code in (None, 0) else "fail"


def _pipeline_duration_seconds(pipeline_summary: dict[str, Any], pipeline_check_id: str) -> float:
    timing = _json_mapping(pipeline_summary.get("timing")) or {}
    duration_map = _json_mapping(timing.get("check_durations_seconds")) or {}
    try:
        return float(duration_map.get(pipeline_check_id) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _pipeline_reused_finish_gate_step(
    *,
    step: dict[str, Any],
    pipeline_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if pipeline_summary is None:
        return None
    pipeline_check_id = _PIPELINE_REUSED_FINISH_GATE_STEP_IDS.get(str(step.get("id", "")))
    if pipeline_check_id is None:
        return None
    status_payload = _json_mapping(pipeline_summary.get("status"))
    tool_statuses = _json_mapping(status_payload.get("tool_statuses")) if status_payload is not None else None
    tool_status = _json_mapping(tool_statuses.get(pipeline_check_id)) if tool_statuses is not None else None
    if tool_status is None or tool_status.get("status") == "skipped":
        return None
    exit_code_raw = tool_status.get("normalized_exit_code")
    exit_code = exit_code_raw if isinstance(exit_code_raw, int) else None
    return {
        "id": step["id"],
        "label": step["label"],
        "command": step["command"],
        "exit_code": exit_code,
        "duration_seconds": _pipeline_duration_seconds(pipeline_summary, pipeline_check_id),
        "status": _step_status_from_exit_code(exit_code),
        "reused_from_pipeline": True,
        "reused_check_id": pipeline_check_id,
        "detail": "Reused the recommended pipeline slice result for this broader proof step.",
    }


def _finish_gate_step_report_from_result(step: dict[str, Any], result: Any) -> dict[str, Any]:
    return {
        "id": step["id"],
        "label": step["label"],
        "command": step["command"],
        "exit_code": result.exit_code,
        "duration_seconds": result.duration_seconds,
        "status": _step_status_from_exit_code(result.exit_code),
    }


def _is_serial_finish_gate_step(step: dict[str, Any]) -> bool:
    return str(step.get("id", "")).startswith("owner-pytest")


def execute_finish_gate_steps(
    *,
    steps: list[dict[str, Any]],
    run_command: Callable[[str, list[str]], Any],
    pipeline_summary: dict[str, Any] | None = None,
    max_workers: int = FINISH_GATE_MAX_WORKERS,
) -> list[dict[str, Any]]:
    step_reports: list[dict[str, Any] | None] = [None] * len(steps)
    parallel_steps: list[tuple[int, dict[str, Any]]] = []
    serial_steps: list[tuple[int, dict[str, Any]]] = []

    for index, step in enumerate(steps):
        reused_step = _pipeline_reused_finish_gate_step(step=step, pipeline_summary=pipeline_summary)
        if reused_step is not None:
            step_reports[index] = reused_step
            continue
        if _is_serial_finish_gate_step(step):
            serial_steps.append((index, step))
        else:
            parallel_steps.append((index, step))

    if parallel_steps:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_command, step["id"], step["argv"]): (index, step) for index, step in parallel_steps
            }
            for future, (index, step) in futures.items():
                step_reports[index] = _finish_gate_step_report_from_result(step, future.result())

    for index, step in serial_steps:
        step_reports[index] = _finish_gate_step_report_from_result(step, run_command(step["id"], step["argv"]))

    return [report for report in step_reports if report is not None]


def summarize_finish_gate_timing(step_reports: Iterable[dict[str, Any]]) -> dict[str, Any]:
    ordered_reports = [dict(report) for report in step_reports]
    per_check = {
        str(report.get("id", "")): round(float(report.get("duration_seconds") or 0.0), 3) for report in ordered_reports
    }
    reused_duration_seconds = round(
        sum(
            float(report.get("duration_seconds") or 0.0)
            for report in ordered_reports
            if report.get("reused_from_pipeline")
        ),
        3,
    )
    serial_duration_seconds = round(
        sum(
            float(report.get("duration_seconds") or 0.0)
            for report in ordered_reports
            if _is_serial_finish_gate_step(report)
        ),
        3,
    )
    parallel_durations = [
        float(report.get("duration_seconds") or 0.0)
        for report in ordered_reports
        if not report.get("reused_from_pipeline") and not _is_serial_finish_gate_step(report)
    ]
    parallelizable_duration_seconds = round(sum(parallel_durations), 3)
    critical_path_duration_seconds = round((max(parallel_durations, default=0.0) + serial_duration_seconds), 3)
    total_duration_seconds = round(sum(float(report.get("duration_seconds") or 0.0) for report in ordered_reports), 3)
    return {
        "check_durations_seconds": per_check,
        "parallel_worker_count": FINISH_GATE_MAX_WORKERS,
        "parallelizable_duration_seconds": parallelizable_duration_seconds,
        "serial_duration_seconds": serial_duration_seconds,
        "reused_duration_seconds": reused_duration_seconds,
        "critical_path_duration_seconds": critical_path_duration_seconds,
        "total_duration_seconds": total_duration_seconds,
    }


__all__ = [
    "_build_finish_gate_commands",
    "_build_owner_pytest_step",
    "_changed_file_flag_args",
    "_finish_gate_pipeline_check_ids",
    "_focused_python_files",
    "_owner_test_targets_for_checks",
    "_shell_command",
    "build_change_proof_requirements",
    "evaluate_change_scoped_coverage_proof",
    "execute_finish_gate_steps",
    "summarize_finish_gate_timing",
]
