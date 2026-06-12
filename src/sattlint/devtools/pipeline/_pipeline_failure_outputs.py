"""Pipeline failure artifact helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from sattlint.contracts import FindingCollection
from sattlint.devtools.artifact_registry import PIPELINE_ARTIFACTS, artifact_reports_map
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.devtools.shared.pipeline_artifacts import write_json_artifact
from sattlint.devtools.status_reports import build_pipeline_status_report, build_pipeline_summary_report


def _progress_active_stage_key(progress: ProgressReporter) -> str | None:
    progress_payload = progress.to_dict()
    active_stage = cast(dict[str, Any] | None, progress_payload.get("active_stage"))
    if not isinstance(active_stage, dict):
        return None
    key = active_stage.get("key")
    return key if isinstance(key, str) and key else None


def _exception_detail(error: BaseException) -> str:
    message = str(error).strip()
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def build_failure_tool_statuses(
    progress: ProgressReporter,
    *,
    failing_stage_key: str | None,
    make_tool_status: Callable[..., dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    progress_payload = progress.to_dict()
    progress_stages: dict[str, dict[str, Any]] = {}
    for raw_stage in cast(list[Any], progress_payload.get("stages", [])):
        if not isinstance(raw_stage, dict):
            continue
        stage = cast(dict[str, Any], raw_stage)
        stage_key = stage.get("key")
        if isinstance(stage_key, str) and stage_key:
            progress_stages[stage_key] = stage
    stage_to_tool = {
        "ruff": "ruff",
        "pyright": "pyright",
        "pytest": "pytest",
        "vulture": "vulture",
        "bandit": "bandit",
        "corpus": "corpus",
    }
    tool_statuses: dict[str, dict[str, Any]] = {}
    for stage_key, tool_name in stage_to_tool.items():
        stage = progress_stages.get(stage_key, {})
        stage_status = stage.get("status")
        stage_detail = stage.get("detail")
        if stage_status == "completed":
            tool_statuses[tool_name] = make_tool_status(
                status="pass",
                report=None,
                raw_exit_code=0,
                normalized_exit_code=0,
                detail=None if not isinstance(stage_detail, str) else stage_detail,
            )
            continue
        if stage_key == failing_stage_key or stage_status == "failed":
            tool_statuses[tool_name] = make_tool_status(
                status="fail",
                report=None,
                raw_exit_code=1,
                normalized_exit_code=1,
                detail=(
                    stage_detail
                    if isinstance(stage_detail, str) and stage_detail
                    else "failed before report generation"
                ),
            )
            continue
        tool_statuses[tool_name] = make_tool_status(
            status="skipped",
            report=None,
            raw_exit_code=None,
            normalized_exit_code=None,
            detail="not reached due earlier failure",
        )

    for tool_name in ("rule_metadata", "baseline_drift", "performance_budget"):
        tool_statuses[tool_name] = make_tool_status(
            status="skipped",
            report=None,
            raw_exit_code=None,
            normalized_exit_code=None,
            detail="not reached due earlier failure",
        )
    return tool_statuses


def write_pipeline_failure_artifacts(
    context: dict[str, Any],
    error: BaseException,
    *,
    make_tool_status: Callable[..., dict[str, Any]],
) -> None:
    progress = cast(ProgressReporter, context["progress"])
    failing_stage_key = _progress_active_stage_key(progress)
    if failing_stage_key is not None:
        progress.fail_stage(failing_stage_key, detail=_exception_detail(error))
    progress.finalize(overall_status="failed")

    tool_statuses = build_failure_tool_statuses(
        progress,
        failing_stage_key=failing_stage_key,
        make_tool_status=make_tool_status,
    )
    failing_tools = [name for name, payload in tool_statuses.items() if payload["status"] == "fail"]
    findings = FindingCollection(())
    reports = artifact_reports_map(
        PIPELINE_ARTIFACTS,
        profile=context["profile"],
        enabled_artifact_ids=context["enabled_artifacts"],
    )
    for report_key in list(reports):
        if report_key not in {"artifact_registry", "findings", "status", "summary", "progress"}:
            reports[report_key] = None
    status_report = build_pipeline_status_report(
        profile=context["profile"],
        sanitized_output_dir=context["sanitized_output_dir"],
        overall_status_value="fail",
        tool_statuses=tool_statuses,
        failing_tools=failing_tools,
        non_blocking_tools=[],
        progress_report=f"{context['sanitized_output_dir']}/progress.json",
        findings_schema=findings.schema_metadata,
    )
    error_payload = {
        "type": type(error).__name__,
        "message": str(error),
        "stage": failing_stage_key,
    }
    status_report["error"] = error_payload
    summary = build_pipeline_summary_report(
        profile=context["profile"],
        sanitized_output_dir=context["sanitized_output_dir"],
        reports=reports,
        overall_status_value="fail",
        tool_statuses=tool_statuses,
        failing_tools=failing_tools,
        non_blocking_tools=[],
        tool_exit_codes={name: payload.get("normalized_exit_code") for name, payload in tool_statuses.items()},
        artifact_registry_report=context["artifact_registry_report"],
        counts={},
        progress_report=f"{context['sanitized_output_dir']}/progress.json",
        findings_schema=findings.schema_metadata,
    )
    summary["error"] = error_payload
    if context["selected_checks"] is not None:
        selected_checks = list(context["selected_checks"])
        status_report["selected_checks"] = selected_checks
        summary["selected_checks"] = selected_checks
    if "artifact_registry" in context["enabled_artifacts"]:
        write_json_artifact(context["output_dir"] / "artifact_registry.json", context["artifact_registry_report"])
    write_json_artifact(context["output_dir"] / "findings.json", findings.to_dict())
    write_json_artifact(context["output_dir"] / "status.json", status_report)
    write_json_artifact(context["output_dir"] / "summary.json", summary)


__all__ = [
    "build_failure_tool_statuses",
    "write_pipeline_failure_artifacts",
]
