"""Repeatable static-analysis pipeline that emits machine-readable JSON reports."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import argparse
import contextlib
import json
import os
import platform
import re
import shutil
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, cast

from sattlint.contracts import FindingCollection
from sattlint.devtools import _pipeline_cli as pipeline_cli_helpers
from sattlint.devtools import _pipeline_execution as pipeline_execution_helpers
from sattlint.devtools import _pipeline_finish_gate as pipeline_finish_gate_helpers
from sattlint.devtools import _pipeline_optional_reports_helpers as pipeline_optional_report_helpers
from sattlint.devtools import _pipeline_parsing_helpers as pipeline_parsing_helpers
from sattlint.devtools.artifact_registry import (
    PIPELINE_ARTIFACTS,
    artifact_reports_map,
    build_artifact_registry_report,
)
from sattlint.devtools.corpus import CORPUS_RESULTS_FILENAME, run_corpus_suite
from sattlint.devtools.coverage_reports import build_coverage_summary_report
from sattlint.devtools.pipeline_artifacts import (
    PipelineArtifactContext,
    write_json_artifact,
    write_pipeline_artifacts,
)
from sattlint.devtools.pipeline_checks import (
    PIPELINE_CHECK_IDS,
    normalize_changed_files,
    normalize_selected_checks,
    skipped_stage_report,
)
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.devtools.status_reports import (
    build_pipeline_status_report,
    build_pipeline_summary_report,
    build_tool_status,
    overall_status,
)
from sattlint.devtools.structural_reports import (
    StructuralReportsBundle,
    WorkspaceGraphInputs,
)
from sattlint.devtools.structural_reports import (
    collect_analyzer_registry_report as build_analyzer_registry_report,
)
from sattlint.devtools.structural_reports import (
    collect_architecture_report as build_architecture_report,
)
from sattlint.devtools.structural_reports import (
    collect_call_graph_report as build_call_graph_report,
)
from sattlint.devtools.structural_reports import (
    collect_dependency_graph_report as build_dependency_graph_report,
)
from sattlint.devtools.structural_reports import (
    collect_graphics_layout_report as build_graphics_layout_report,
)
from sattlint.devtools.structural_reports import (
    collect_impact_analysis_report as build_impact_analysis_report,
)
from sattlint.devtools.structural_reports import (
    collect_phase2_rule_metadata_gate as build_phase2_rule_metadata_gate,
)
from sattlint.devtools.structural_reports import (
    collect_structural_reports as build_structural_reports,
)
from sattlint.devtools.structural_reports import (
    collect_workspace_graph_inputs as build_workspace_graph_inputs,
)
from sattlint.devtools.tool_reports import build_command_report
from sattlint.devtools.trace_reports import collect_trace_report as build_trace_report
from sattlint.path_sanitizer import sanitize_path_for_report

REPO_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "artifacts" / "analysis"
DEFAULT_TRACE_TARGET = REPO_ROOT / "tests" / "fixtures" / "sample_sattline_files" / "LinterTestProgram.s"
DEFAULT_CORPUS_MANIFEST_DIR = REPO_ROOT / "tests" / "fixtures" / "corpus" / "manifests"
PIPELINE_PROFILE_CHOICES = ("quick", "full")
DEFAULT_PIPELINE_PROFILE = "full"
DEFAULT_QUICK_PYTEST_TARGETS = ("tests/test_pipeline.py", "tests/test_repo_audit.py", "tests/parser/test_corpus.py")
_VULTURE_LINE_RE = re.compile(r"^(?P<file>.*?):(?P<line>\d+): (?P<message>.*) \((?P<confidence>\d+)% confidence\)$")

CommandResult = pipeline_execution_helpers.CommandResult


def _read_pyproject() -> dict[str, Any]:
    return pipeline_parsing_helpers.read_pyproject(PYPROJECT_PATH)


def _tool_version(package_name: str) -> str | None:
    return pipeline_parsing_helpers.tool_version(package_name)


def _resolve_python_executable() -> str:
    return pipeline_execution_helpers._resolve_python_executable()


def _resolve_venv_tool(tool_name: str) -> str | None:
    return pipeline_execution_helpers._resolve_venv_tool(tool_name)


def _run_command(name: str, command: list[str], *, cwd: Path = REPO_ROOT) -> CommandResult:
    return pipeline_execution_helpers._run_command(name, command, cwd=cwd)


def _detect_changed_files(*, repo_root: Path = REPO_ROOT) -> list[str]:
    return pipeline_execution_helpers._detect_changed_files(repo_root=repo_root)


def _profile_settings(profile: str) -> dict[str, Any]:
    if profile == "quick":
        return {
            "include_vulture": False,
            "include_bandit": False,
            "include_structural_reports": False,
            "include_trace": False,
            "pytest_addopts_override": "--strict-markers --strict-config",
        }
    if profile == "full":
        return {
            "include_vulture": True,
            "include_bandit": True,
            "include_structural_reports": True,
            "include_trace": True,
            "pytest_addopts_override": None,
        }
    raise ValueError(f"Unsupported pipeline profile: {profile}")


build_pipeline_check_catalog = pipeline_cli_helpers.build_pipeline_check_catalog
_shell_command = pipeline_cli_helpers._shell_command
_changed_file_flag_args = pipeline_cli_helpers._changed_file_flag_args
_focused_python_files = pipeline_cli_helpers._focused_python_files
_owner_test_targets_for_checks = pipeline_cli_helpers._owner_test_targets_for_checks
build_change_proof_requirements = pipeline_cli_helpers.build_change_proof_requirements
_build_owner_pytest_step = pipeline_cli_helpers._build_owner_pytest_step
evaluate_change_scoped_coverage_proof = pipeline_cli_helpers.evaluate_change_scoped_coverage_proof
_build_finish_gate_commands = pipeline_cli_helpers._build_finish_gate_commands
_build_recommendation_why_this_gate = pipeline_cli_helpers._build_recommendation_why_this_gate
_build_recommendation_drift_report = pipeline_cli_helpers._build_recommendation_drift_report
build_pipeline_check_recommendations = pipeline_cli_helpers.build_pipeline_check_recommendations
run_recommended_pipeline_finish_gate = pipeline_cli_helpers.run_recommended_pipeline_finish_gate
_pytest_worker_args = pipeline_finish_gate_helpers._pytest_worker_args


def _normalize_pytest_workers(pytest_workers: str | None) -> str | None:
    if pytest_workers is None:
        return None
    normalized = str(pytest_workers).strip()
    return normalized or None


def _build_pytest_command(
    python_cmd: list[str],
    junit_path: Path,
    *,
    profile: str,
    pytest_workers: str | None = None,
) -> list[str]:
    settings = _profile_settings(profile)
    command = [*python_cmd, "-m", "pytest", *_pytest_worker_args(pytest_workers), "-q"]
    addopts_override = settings.get("pytest_addopts_override")
    if addopts_override:
        command.extend(["-o", f"addopts={addopts_override}"])
    if profile == "quick":
        command.extend(DEFAULT_QUICK_PYTEST_TARGETS)
    command.append(f"--junitxml={junit_path}")
    return command


def _build_pipeline_timing_summary(
    *,
    progress: ProgressReporter,
    tool_statuses: dict[str, dict[str, Any]],
    pytest_workers: str | None,
) -> dict[str, Any]:
    stage_durations: dict[str, float] = {}
    for stage in progress.to_dict().get("stages", []):
        stage_key = str(stage.get("key", "")).strip()
        if not stage_key:
            continue
        try:
            stage_durations[stage_key] = round(float(stage.get("duration_seconds") or 0.0), 3)
        except (TypeError, ValueError):
            stage_durations[stage_key] = 0.0
    check_stage_map = {
        "ruff": "ruff",
        "pyright": "pyright",
        "pytest": "pytest",
        "vulture": "vulture",
        "bandit": "bandit",
        "structural-reports": "structural_reports",
        "trace": "trace",
        "corpus": "corpus",
    }
    check_durations = {
        check_id: stage_durations.get(stage_key, 0.0)
        for check_id, stage_key in check_stage_map.items()
        if tool_statuses.get(check_id, {}).get("status") != "skipped"
    }
    timing_summary: dict[str, Any] = {
        "stage_durations_seconds": stage_durations,
        "check_durations_seconds": check_durations,
        "total_duration_seconds": round(sum(stage_durations.values()), 3),
    }
    normalized_workers = _normalize_pytest_workers(pytest_workers)
    if normalized_workers is not None:
        timing_summary["pytest_workers"] = normalized_workers
    return timing_summary


def _make_tool_status(
    *,
    status: str,
    report: str | None,
    raw_exit_code: int | None,
    normalized_exit_code: int | None,
    finding_count: int = 0,
    note_count: int = 0,
    detail: str | None = None,
) -> dict[str, Any]:
    return build_tool_status(
        status=status,
        report=report,
        raw_exit_code=raw_exit_code,
        normalized_exit_code=normalized_exit_code,
        finding_count=finding_count,
        note_count=note_count,
        detail=detail,
    )


def _collect_phase2_rule_metadata_gate(
    architecture_report: dict[str, Any],
) -> dict[str, Any]:
    return build_phase2_rule_metadata_gate(architecture_report)


def _overall_status(tool_statuses: dict[str, dict[str, Any]]) -> str:
    return overall_status(tool_statuses)


def _print_cli_summary(status_report: dict[str, Any]) -> None:
    print(f"Pipeline profile: {status_report['profile']}")
    print(f"Overall status: {status_report['overall_status']}")
    findings_schema = status_report.get("findings_schema")
    if findings_schema:
        print(
            f"Findings schema: {findings_schema.get('kind', 'unknown')} v{findings_schema.get('schema_version', '?')}"
        )
    for tool_name in ("ruff", "pyright", "pytest", "vulture", "bandit", "corpus"):
        tool_status = status_report["tool_statuses"].get(tool_name)
        if tool_status is None:
            continue
        detail = tool_status.get("detail")
        line = f"- {tool_name}: {tool_status['status']}"
        if detail:
            line = f"{line} ({detail})"
        print(line)
    analysis_diff_summary = cast(dict[str, Any], status_report.get("analysis_diff_summary") or {})
    analysis_diff_report = status_report.get("analysis_diff_report")
    if analysis_diff_report:
        print(
            "Analysis diff: "
            f"{analysis_diff_summary.get('new_count', 0)} new, "
            f"{analysis_diff_summary.get('changed_count', 0)} changed, "
            f"{analysis_diff_summary.get('resolved_count', 0)} resolved, "
            f"{analysis_diff_summary.get('unchanged_count', 0)} unchanged"
        )
        print(f"Analysis diff report: {analysis_diff_report}")
    corpus_results_report = status_report.get("corpus_results_report")
    if corpus_results_report:
        print(f"Corpus results report: {corpus_results_report}")
    print(f"Status report: {status_report['status_report']}")
    print(f"Summary report: {status_report['summary_report']}")


def _command_payload(result: CommandResult, **extra: Any) -> dict[str, Any]:
    return build_command_report(result, repo_root=REPO_ROOT, **extra)


def _parse_json_lines(raw_output: str) -> list[dict[str, Any]]:
    return pipeline_parsing_helpers.parse_json_lines(raw_output)


def _parse_vulture_output(raw_output: str) -> list[dict[str, Any]]:
    return pipeline_parsing_helpers.parse_vulture_output(raw_output, _VULTURE_LINE_RE)


def _parse_pytest_junit(xml_path: Path) -> dict[str, Any]:
    return pipeline_parsing_helpers.parse_pytest_junit(xml_path)


def _collect_environment_report() -> dict[str, Any]:
    pyproject = _read_pyproject()
    project = pyproject.get("project", {})
    optional_deps = project.get("optional-dependencies", {})
    python_executable = _resolve_python_executable()
    return {
        "project_name": project.get("name"),
        "project_version": project.get("version"),
        "requires_python": project.get("requires-python"),
        "platform": platform.platform(),
        "python": {
            "executable": sanitize_path_for_report(python_executable, repo_root=REPO_ROOT),
            "version": platform.python_version(),
        },
        "dependencies": {
            "runtime": project.get("dependencies", []),
            "optional": optional_deps,
        },
        "installed_tool_versions": {
            name: _tool_version(name) for name in ("ruff", "pyright", "pytest", "bandit", "vulture", "types-openpyxl")
        },
    }


def _collect_architecture_report() -> dict[str, Any]:
    return build_architecture_report()


def _collect_analyzer_registry_report() -> dict[str, Any]:
    return build_analyzer_registry_report()


def _collect_workspace_graph_inputs(
    workspace_root: Path = REPO_ROOT,
) -> WorkspaceGraphInputs:
    return build_workspace_graph_inputs(workspace_root)


def _collect_dependency_graph_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if graph_inputs is None:
        graph_inputs = _collect_workspace_graph_inputs(workspace_root)
    return build_dependency_graph_report(workspace_root, graph_inputs=graph_inputs)


def _collect_call_graph_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if graph_inputs is None:
        graph_inputs = _collect_workspace_graph_inputs(workspace_root)
    return build_call_graph_report(workspace_root, graph_inputs=graph_inputs)


def _collect_impact_analysis_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
    dependency_graph_report: dict[str, Any] | None = None,
    call_graph_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if graph_inputs is None:
        graph_inputs = _collect_workspace_graph_inputs(workspace_root)
    return build_impact_analysis_report(
        workspace_root,
        graph_inputs=graph_inputs,
        dependency_graph_report=dependency_graph_report,
        call_graph_report=call_graph_report,
    )


def _collect_graphics_layout_report(
    workspace_root: Path = REPO_ROOT,
    *,
    graph_inputs: WorkspaceGraphInputs | tuple[Any, list[Any], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    if graph_inputs is None:
        graph_inputs = _collect_workspace_graph_inputs(workspace_root)
    return build_graphics_layout_report(workspace_root, graph_inputs=graph_inputs)


def _collect_structural_report_bundle(
    workspace_root: Path = REPO_ROOT,
    *,
    progress_callback: Callable[[str], None] | None = None,
) -> StructuralReportsBundle:
    return build_structural_reports(workspace_root, progress_callback=progress_callback)


def _collect_trace_report(trace_target: Path) -> dict[str, Any]:
    return build_trace_report(trace_target)


def _run_environment_stage(progress: ProgressReporter) -> dict[str, Any]:
    progress.start_stage("environment")
    environment_report = _collect_environment_report()
    progress.complete_stage("environment")
    return environment_report


def _run_ruff_stage(
    progress: ProgressReporter, *, python_cmd: list[str]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    progress.start_stage("ruff")
    ruff_binary = _resolve_venv_tool("ruff")
    if ruff_binary:
        ruff_result = _run_command(
            "ruff",
            [ruff_binary, "check", "src", "tests", "--output-format", "json"],
        )
    else:
        ruff_result = _run_command(
            "ruff",
            [*python_cmd, "-m", "ruff", "check", "src", "tests", "--output-format", "json"],
        )
    ruff_findings = json.loads(ruff_result.stdout or "[]")
    ruff_report = _command_payload(ruff_result, finding_count=len(ruff_findings), findings=ruff_findings)
    progress.complete_stage("ruff", detail=f"{len(ruff_findings)} findings")
    return ruff_report, ruff_findings


def _run_pyright_stage(
    progress: ProgressReporter,
    *,
    python_cmd: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    progress.start_stage("pyright")
    pyright_binary = _resolve_venv_tool("pyright")
    if pyright_binary:
        pyright_result = _run_command(
            "pyright",
            [pyright_binary, "--outputjson", "src", "tests"],
        )
    else:
        pyright_result = _run_command(
            "pyright",
            [*python_cmd, "-m", "pyright", "--outputjson", "src", "tests"],
        )
    pyright_data = json.loads(pyright_result.stdout or "{}")
    pyright_findings = pyright_data.get("generalDiagnostics", [])
    pyright_summary = pyright_data.get("summary", {})
    pyright_error_count = pyright_summary.get("errorCount", 0)
    pyright_warning_count = pyright_summary.get("warningCount", 0)
    pyright_report = _command_payload(
        pyright_result,
        finding_count=len(pyright_findings),
        error_count=pyright_error_count,
        warning_count=pyright_warning_count,
        effective_exit_code=0 if pyright_error_count == 0 else pyright_result.exit_code,
        findings=pyright_findings,
    )
    progress.complete_stage(
        "pyright",
        detail=f"{pyright_error_count} errors, {pyright_warning_count} warnings",
    )
    return pyright_report, pyright_findings


def _run_pytest_stage(
    progress: ProgressReporter,
    *,
    output_dir: Path,
    python_cmd: list[str],
    profile: str,
    pytest_workers: str | None = None,
) -> dict[str, Any]:
    junit_path = output_dir / "pytest.junit.xml"
    coverage_data_path = output_dir / ".coverage.pytest"
    progress.start_stage("pytest")
    with contextlib.suppress(FileNotFoundError):
        coverage_data_path.unlink()

    previous_coverage_file = os.environ.get("COVERAGE_FILE")
    os.environ["COVERAGE_FILE"] = str(coverage_data_path)
    try:
        pytest_result = _run_command(
            "pytest",
            _build_pytest_command(python_cmd, junit_path, profile=profile, pytest_workers=pytest_workers),
        )
    finally:
        if previous_coverage_file is None:
            os.environ.pop("COVERAGE_FILE", None)
        else:
            os.environ["COVERAGE_FILE"] = previous_coverage_file
    try:
        pytest_parsed = _parse_pytest_junit(junit_path)
    except FileNotFoundError:
        pytest_parsed = {
            "testcases": [],
            "summary": {"tests": 0, "failures": 0, "errors": 1, "skipped": 0},
            "errors": [{"message": f"JUnit XML not generated: {pytest_result.stderr}"}],
        }
    pytest_report = _command_payload(pytest_result, **pytest_parsed)
    progress.complete_stage(
        "pytest",
        detail=(
            f"{pytest_report['summary']['tests']} tests, "
            f"{pytest_report['summary']['failures']} failures, "
            f"{pytest_report['summary']['errors']} errors"
        ),
    )
    return pytest_report


def _prepare_pipeline_run(
    output_dir: Path,
    *,
    trace_target: Path | None,
    mutation_target: Path | None,
    profile: str,
    include_vulture: bool | None,
    include_bandit: bool | None,
    baseline_findings: Path | None,
    corpus_manifest_dir: Path | None,
    changed_files: list[str] | None,
    selected_checks: Iterable[str] | None,
    run_mutation_analysis: bool,
    pytest_workers: str | None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if baseline_findings is not None and not baseline_findings.exists():
        raise FileNotFoundError(f"Baseline findings file does not exist: {baseline_findings}")

    python_cmd = [_resolve_python_executable()]
    settings = _profile_settings(profile)
    normalized_selected_checks = normalize_selected_checks(profile, selected_checks, validate_profile=_profile_settings)

    def wants(check_id: str) -> bool:
        return normalized_selected_checks is None or check_id in normalized_selected_checks

    run_vulture = wants("vulture") and (settings["include_vulture"] if include_vulture is None else include_vulture)
    run_bandit = wants("bandit") and (settings["include_bandit"] if include_bandit is None else include_bandit)
    run_structural_reports = wants("structural-reports") and settings["include_structural_reports"]
    run_trace = wants("trace") and settings["include_trace"] and trace_target is not None and trace_target.exists()
    resolved_mutation_target = mutation_target.resolve() if mutation_target is not None else trace_target
    run_mutation = bool(
        run_mutation_analysis and resolved_mutation_target is not None and resolved_mutation_target.exists()
    )
    resolved_corpus_manifest_dir = corpus_manifest_dir.resolve() if corpus_manifest_dir is not None else None
    run_corpus = wants("corpus") and bool(resolved_corpus_manifest_dir and resolved_corpus_manifest_dir.exists())
    run_coverage_summary = run_structural_reports and (REPO_ROOT / "coverage.xml").exists()
    resolved_changed_files = (
        list(changed_files) if changed_files is not None else _detect_changed_files(repo_root=REPO_ROOT)
    )
    sanitized_output_dir = sanitize_path_for_report(output_dir, repo_root=REPO_ROOT) or output_dir.as_posix()
    canonical_command = f"sattlint-analysis-pipeline --profile {profile} --output-dir {sanitized_output_dir}"
    if normalized_selected_checks is not None:
        canonical_command = f"{canonical_command} " + " ".join(
            f"--check {check_id}" for check_id in normalized_selected_checks
        )
    normalized_pytest_workers = _normalize_pytest_workers(pytest_workers)
    if normalized_pytest_workers is not None:
        canonical_command = f"{canonical_command} --pytest-workers {normalized_pytest_workers}"
    progress = ProgressReporter(
        kind="sattlint.pipeline.progress",
        title="Pipeline",
        output_dir=output_dir,
        write_json=write_json_artifact,
        stages=[
            ("environment", "Collect environment"),
            ("ruff", "Run Ruff"),
            ("pyright", "Run pyright"),
            ("pytest", "Run pytest"),
            ("vulture", "Run Vulture"),
            ("bandit", "Run Bandit"),
            ("structural_reports", "Collect structural reports"),
            ("trace", "Collect trace report"),
            ("corpus", "Run corpus suite"),
            ("findings", "Normalize findings"),
            ("write_artifacts", "Write artifacts"),
        ],
        canonical_command=canonical_command,
    )

    enabled_artifacts: set[str] = {
        "progress",
        "status",
        "summary",
        "findings",
        "artifact_registry",
    }
    if profile == "full" and normalized_selected_checks is None:
        enabled_artifacts.add("recommendation_drift")
    if wants("ruff"):
        enabled_artifacts.add("ruff")
    if wants("pyright"):
        enabled_artifacts.add("pyright")
    if wants("pytest"):
        enabled_artifacts.add("pytest")
    if baseline_findings is not None:
        enabled_artifacts.add("analysis_diff")
        if profile == "full":
            enabled_artifacts.add("differential")
    if run_corpus:
        enabled_artifacts.add("corpus_results")
    if run_vulture:
        enabled_artifacts.add("vulture")
    if run_bandit:
        enabled_artifacts.add("bandit")
    if run_structural_reports:
        enabled_artifacts.update(
            {
                "architecture",
                "analyzer_registry",
                "dependency_graph",
                "call_graph",
                "current_debt_snapshot",
                "graphics_layout",
                "impact_analysis",
                "sattline_semantic",
                "rule_metrics",
            }
        )
    if run_trace:
        enabled_artifacts.update({"trace", "profiling_summary", "performance_budget"})
    if run_mutation:
        enabled_artifacts.add("mutation_results")
    enabled_artifacts.add("incremental_analysis")
    if run_coverage_summary:
        enabled_artifacts.add("coverage_summary")

    artifact_registry_report = build_artifact_registry_report(
        PIPELINE_ARTIFACTS,
        generated_by="sattlint.devtools.pipeline",
        profile=profile,
        enabled_artifact_ids=enabled_artifacts,
    )

    return {
        "artifact_registry_report": artifact_registry_report,
        "changed_files": normalize_changed_files(resolved_changed_files),
        "enabled_artifacts": enabled_artifacts,
        "output_dir": output_dir,
        "profile": profile,
        "progress": progress,
        "pytest_workers": normalized_pytest_workers,
        "python_cmd": python_cmd,
        "resolved_changed_files": resolved_changed_files,
        "resolved_corpus_manifest_dir": resolved_corpus_manifest_dir,
        "mutation_target": resolved_mutation_target,
        "run_bandit": run_bandit,
        "run_corpus": run_corpus,
        "run_coverage_summary": run_coverage_summary,
        "run_mutation_analysis": run_mutation,
        "run_structural_reports": run_structural_reports,
        "run_trace": run_trace,
        "run_vulture": run_vulture,
        "sanitized_output_dir": sanitized_output_dir,
        "selected_checks": normalized_selected_checks,
    }


def _run_vulture_stage(
    progress: ProgressReporter,
    *,
    python_cmd: list[str],
    run_vulture: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if run_vulture:
        progress.start_stage("vulture")
        vulture_result = _run_command(
            "vulture",
            [*python_cmd, "-m", "vulture", "src", "--min-confidence", "80"],
        )
        vulture_findings = _parse_vulture_output(vulture_result.stdout)
        vulture_report = _command_payload(
            vulture_result,
            finding_count=len(vulture_findings),
            findings=vulture_findings,
        )
        progress.complete_stage("vulture", detail=f"{len(vulture_findings)} findings")
        return vulture_report, vulture_findings

    progress.skip_stage("vulture", detail="skipped by profile")
    return {"tool": "vulture", "skipped": True}, []


def _run_bandit_stage(
    progress: ProgressReporter,
    *,
    python_cmd: list[str],
    run_bandit: bool,
) -> dict[str, Any]:
    if run_bandit:
        progress.start_stage("bandit")
        bandit_result = _run_command(
            "bandit",
            [*python_cmd, "-m", "bandit", "-r", "src", "-f", "json", "-q"],
        )
        bandit_findings = json.loads(bandit_result.stdout or "{}")
        bandit_report = _command_payload(
            bandit_result,
            metrics=bandit_findings.get("metrics", {}),
            findings=bandit_findings.get("results", []),
            errors=bandit_findings.get("errors", []),
        )
        progress.complete_stage(
            "bandit",
            detail=f"{len(bandit_report.get('findings', []))} findings",
        )
        return bandit_report

    progress.skip_stage("bandit", detail="skipped by profile")
    return {"tool": "bandit", "skipped": True}


def _collect_optional_reports(
    context: dict[str, Any],
    *,
    trace_target: Path | None,
) -> dict[str, Any]:
    return pipeline_optional_report_helpers.collect_optional_reports(
        context,
        trace_target=trace_target,
        repo_root=REPO_ROOT,
        collect_structural_report_bundle=_collect_structural_report_bundle,
        collect_trace_report=_collect_trace_report,
        run_corpus_suite_fn=run_corpus_suite,
    )


def _build_derived_reports(
    context: dict[str, Any],
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    *,
    baseline_findings: Path | None,
    slow_phase_threshold_ms: float,
    phase_budget_ms: float,
    total_budget_ms: float,
) -> dict[str, Any]:
    return pipeline_optional_report_helpers.build_derived_reports(
        context,
        stage_reports,
        optional_reports,
        baseline_findings=baseline_findings,
        slow_phase_threshold_ms=slow_phase_threshold_ms,
        phase_budget_ms=phase_budget_ms,
        total_budget_ms=total_budget_ms,
        repo_root=REPO_ROOT,
        default_trace_target=DEFAULT_TRACE_TARGET,
        build_coverage_summary_report_fn=build_coverage_summary_report,
    )


def _build_static_tool_statuses(stage_reports: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "ruff": _make_tool_status(
            status=(
                "skipped"
                if stage_reports["ruff_report"].get("skipped")
                else "fail"
                if stage_reports["ruff_report"]["exit_code"] != 0
                else "pass"
            ),
            report=None if stage_reports["ruff_report"].get("skipped") else "ruff.json",
            raw_exit_code=None
            if stage_reports["ruff_report"].get("skipped")
            else stage_reports["ruff_report"]["exit_code"],
            normalized_exit_code=(
                None if stage_reports["ruff_report"].get("skipped") else stage_reports["ruff_report"]["exit_code"]
            ),
            finding_count=stage_reports["ruff_report"].get("finding_count", 0),
            detail=(
                stage_reports["ruff_report"].get("detail", "skipped by check selection")
                if stage_reports["ruff_report"].get("skipped")
                else f"{stage_reports['ruff_report'].get('finding_count', 0)} findings"
            ),
        ),
        "pyright": _make_tool_status(
            status=(
                "skipped"
                if stage_reports["pyright_report"].get("skipped")
                else "fail"
                if stage_reports["pyright_report"].get("error_count", 0) > 0
                else "pass_with_warnings"
                if stage_reports["pyright_report"].get("warning_count", 0) > 0
                else "pass"
            ),
            report=None if stage_reports["pyright_report"].get("skipped") else "pyright.json",
            raw_exit_code=(
                None if stage_reports["pyright_report"].get("skipped") else stage_reports["pyright_report"]["exit_code"]
            ),
            normalized_exit_code=(
                None
                if stage_reports["pyright_report"].get("skipped")
                else stage_reports["pyright_report"]["effective_exit_code"]
            ),
            finding_count=stage_reports["pyright_report"].get("error_count", 0),
            note_count=stage_reports["pyright_report"].get("warning_count", 0),
            detail=(
                stage_reports["pyright_report"].get("detail", "skipped by check selection")
                if stage_reports["pyright_report"].get("skipped")
                else (
                    f"{stage_reports['pyright_report'].get('error_count', 0)} errors, "
                    f"{stage_reports['pyright_report'].get('warning_count', 0)} warnings"
                )
            ),
        ),
        "pytest": _make_tool_status(
            status=(
                "skipped"
                if stage_reports["pytest_report"].get("skipped")
                else "fail"
                if stage_reports["pytest_report"]["summary"]["failures"]
                or stage_reports["pytest_report"]["summary"]["errors"]
                else "pass"
            ),
            report=None if stage_reports["pytest_report"].get("skipped") else "pytest.json",
            raw_exit_code=(
                None if stage_reports["pytest_report"].get("skipped") else stage_reports["pytest_report"]["exit_code"]
            ),
            normalized_exit_code=(
                None if stage_reports["pytest_report"].get("skipped") else stage_reports["pytest_report"]["exit_code"]
            ),
            finding_count=(
                stage_reports["pytest_report"]["summary"]["failures"]
                + stage_reports["pytest_report"]["summary"]["errors"]
            ),
            detail=(
                stage_reports["pytest_report"].get("detail", "skipped by check selection")
                if stage_reports["pytest_report"].get("skipped")
                else (
                    f"{stage_reports['pytest_report']['summary']['tests']} tests, "
                    f"{stage_reports['pytest_report']['summary']['failures']} failures, "
                    f"{stage_reports['pytest_report']['summary']['errors']} errors"
                )
            ),
        ),
        "vulture": _make_tool_status(
            status=(
                "skipped"
                if stage_reports["vulture_report"].get("skipped")
                else "fail"
                if stage_reports["vulture_report"].get("finding_count", 0)
                or stage_reports["vulture_report"].get("exit_code", 0) != 0
                else "pass"
            ),
            report=None if stage_reports["vulture_report"].get("skipped") else "vulture.json",
            raw_exit_code=stage_reports["vulture_report"].get("exit_code"),
            normalized_exit_code=(
                0
                if stage_reports["vulture_report"].get("skipped")
                else stage_reports["vulture_report"].get("exit_code")
            ),
            finding_count=stage_reports["vulture_report"].get("finding_count", 0),
            detail=(
                "skipped by profile"
                if stage_reports["vulture_report"].get("skipped")
                else f"{stage_reports['vulture_report'].get('finding_count', 0)} findings"
            ),
        ),
        "bandit": _make_tool_status(
            status=(
                "skipped"
                if stage_reports["bandit_report"].get("skipped")
                else "fail"
                if stage_reports["bandit_report"].get("findings")
                or stage_reports["bandit_report"].get("errors")
                or stage_reports["bandit_report"].get("exit_code", 0) != 0
                else "pass"
            ),
            report=None if stage_reports["bandit_report"].get("skipped") else "bandit.json",
            raw_exit_code=stage_reports["bandit_report"].get("exit_code"),
            normalized_exit_code=(
                0 if stage_reports["bandit_report"].get("skipped") else stage_reports["bandit_report"].get("exit_code")
            ),
            finding_count=len(stage_reports["bandit_report"].get("findings", [])),
            detail=(
                "skipped by profile"
                if stage_reports["bandit_report"].get("skipped")
                else f"{len(stage_reports['bandit_report'].get('findings', []))} findings"
            ),
        ),
    }


def _build_extended_tool_statuses(
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    return {
        "corpus": _make_tool_status(
            status=(
                "skipped"
                if optional_reports["corpus_results_report"] is None
                else "fail"
                if optional_reports["corpus_results_report"]["summary"]["failed_count"] > 0
                else "pass"
            ),
            report=None if optional_reports["corpus_results_report"] is None else CORPUS_RESULTS_FILENAME,
            raw_exit_code=None,
            normalized_exit_code=(
                None
                if optional_reports["corpus_results_report"] is None
                else 1
                if optional_reports["corpus_results_report"]["summary"]["failed_count"] > 0
                else 0
            ),
            finding_count=(
                0
                if optional_reports["corpus_results_report"] is None
                else optional_reports["corpus_results_report"]["summary"]["failed_count"]
            ),
            detail=(
                "skipped because no manifest directory was provided"
                if optional_reports["corpus_results_report"] is None
                else (
                    f"{optional_reports['corpus_results_report']['summary']['case_count']} cases, "
                    f"{optional_reports['corpus_results_report']['summary']['failed_count']} failed"
                )
            ),
        ),
        "rule_metadata": _make_tool_status(
            status=(
                "skipped"
                if not context["run_structural_reports"]
                else "fail"
                if derived_reports["phase2_rule_metadata_gate"]["status"] == "fail"
                else "pass"
            ),
            report=None if not context["run_structural_reports"] else "architecture.json",
            raw_exit_code=None,
            normalized_exit_code=(
                None
                if not context["run_structural_reports"]
                else 1
                if derived_reports["phase2_rule_metadata_gate"]["status"] == "fail"
                else 0
            ),
            finding_count=len(derived_reports["phase2_rule_metadata_gate"]["blocking_rule_ids"]),
            detail=(
                "skipped by profile"
                if not context["run_structural_reports"]
                else (
                    f"{len(derived_reports['phase2_rule_metadata_gate']['blocking_rule_ids'])} "
                    "rules missing enforced metadata"
                    if derived_reports["phase2_rule_metadata_gate"]["status"] == "fail"
                    else None
                )
            ),
        ),
    }


def _build_core_tool_statuses(
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    tool_statuses = _build_static_tool_statuses(stage_reports)
    tool_statuses.update(_build_extended_tool_statuses(optional_reports, derived_reports, context))
    return tool_statuses


def _build_policy_tool_statuses(
    derived_reports: dict[str, Any],
    *,
    fail_on_drift: bool,
    fail_on_budget: bool,
) -> dict[str, dict[str, Any]]:
    return {
        "baseline_drift": _make_tool_status(
            status=(
                "skipped"
                if derived_reports["analysis_diff_report"] is None
                else "fail"
                if fail_on_drift
                and (
                    derived_reports["analysis_diff_report"]["summary"]["new_count"] > 0
                    or derived_reports["analysis_diff_report"]["summary"]["resolved_count"] > 0
                )
                else "pass"
            ),
            report=None if derived_reports["analysis_diff_report"] is None else "analysis_diff.json",
            raw_exit_code=None,
            normalized_exit_code=(
                None
                if derived_reports["analysis_diff_report"] is None
                else 1
                if fail_on_drift
                and (
                    derived_reports["analysis_diff_report"]["summary"]["new_count"] > 0
                    or derived_reports["analysis_diff_report"]["summary"]["resolved_count"] > 0
                )
                else 0
            ),
            finding_count=(
                0
                if derived_reports["analysis_diff_report"] is None
                else derived_reports["analysis_diff_report"]["summary"]["new_count"]
                + derived_reports["analysis_diff_report"]["summary"]["resolved_count"]
            ),
            detail=(
                "skipped: no baseline supplied"
                if derived_reports["analysis_diff_report"] is None
                else (
                    f"{derived_reports['analysis_diff_report']['summary']['new_count']} new, "
                    f"{derived_reports['analysis_diff_report']['summary']['resolved_count']} resolved, "
                    f"{derived_reports['analysis_diff_report']['summary']['changed_count']} changed"
                )
            ),
        ),
        "performance_budget": _make_tool_status(
            status=(
                "skipped"
                if derived_reports["performance_budget_report"] is None
                else "fail"
                if fail_on_budget and derived_reports["performance_budget_report"]["status"] == "fail"
                else "pass_with_notes"
                if derived_reports["performance_budget_report"]["status"] == "fail"
                else "pass"
            ),
            report=None if derived_reports["performance_budget_report"] is None else "performance_budget.json",
            raw_exit_code=None,
            normalized_exit_code=(
                None
                if derived_reports["performance_budget_report"] is None
                else 1
                if fail_on_budget and derived_reports["performance_budget_report"]["status"] == "fail"
                else 0
            ),
            finding_count=(
                0
                if derived_reports["performance_budget_report"] is None
                else derived_reports["performance_budget_report"]["violation_count"]
            ),
            detail=(
                "skipped because trace profiling is unavailable"
                if derived_reports["performance_budget_report"] is None
                else f"{derived_reports['performance_budget_report']['violation_count']} budget violations"
            ),
        ),
    }


def _build_pipeline_tool_exit_codes(
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    context: dict[str, Any],
    *,
    fail_on_drift: bool,
    fail_on_budget: bool,
) -> dict[str, int | None]:
    return {
        "ruff": None if stage_reports["ruff_report"].get("skipped") else stage_reports["ruff_report"]["exit_code"],
        "pyright": (
            None
            if stage_reports["pyright_report"].get("skipped")
            else stage_reports["pyright_report"]["effective_exit_code"]
        ),
        "pytest": None
        if stage_reports["pytest_report"].get("skipped")
        else stage_reports["pytest_report"]["exit_code"],
        "vulture": stage_reports["vulture_report"].get("exit_code"),
        "bandit": stage_reports["bandit_report"].get("exit_code"),
        "corpus": (
            None
            if optional_reports["corpus_results_report"] is None
            else 1
            if optional_reports["corpus_results_report"]["summary"]["failed_count"] > 0
            else 0
        ),
        "rule_metadata": (
            None
            if not context["run_structural_reports"]
            else 1
            if derived_reports["phase2_rule_metadata_gate"]["status"] == "fail"
            else 0
        ),
        "baseline_drift": (
            None
            if derived_reports["analysis_diff_report"] is None
            else 1
            if fail_on_drift
            and (
                derived_reports["analysis_diff_report"]["summary"]["new_count"] > 0
                or derived_reports["analysis_diff_report"]["summary"]["resolved_count"] > 0
            )
            else 0
        ),
        "performance_budget": (
            None
            if derived_reports["performance_budget_report"] is None
            else 1
            if fail_on_budget and derived_reports["performance_budget_report"]["status"] == "fail"
            else 0
        ),
    }


def _build_pipeline_counts(
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, int | float]:
    incremental_analysis_report = derived_reports["incremental_analysis_report"]
    profiling_summary_report = derived_reports["profiling_summary_report"]
    performance_budget_report = derived_reports["performance_budget_report"]
    pytest_summary = stage_reports["pytest_report"].get(
        "summary", {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    )
    return {
        "baseline_new_findings": 0
        if derived_reports["analysis_diff_report"] is None
        else derived_reports["analysis_diff_report"]["summary"]["new_count"],
        "baseline_resolved_findings": 0
        if derived_reports["analysis_diff_report"] is None
        else derived_reports["analysis_diff_report"]["summary"]["resolved_count"],
        "baseline_changed_findings": 0
        if derived_reports["analysis_diff_report"] is None
        else derived_reports["analysis_diff_report"]["summary"]["changed_count"],
        "baseline_unchanged_findings": 0
        if derived_reports["analysis_diff_report"] is None
        else derived_reports["analysis_diff_report"]["summary"]["unchanged_count"],
        "incremental_changed_file_count": 0
        if incremental_analysis_report is None
        else incremental_analysis_report["summary"]["changed_file_count"],
        "incremental_candidate_analyzer_count": 0
        if incremental_analysis_report is None
        else incremental_analysis_report["summary"]["impacted_analyzer_count"],
        "incremental_blocking_analyzer_count": 0
        if incremental_analysis_report is None
        else incremental_analysis_report["summary"]["fallback_analyzer_count"],
        "normalized_findings": len(derived_reports["finding_collection"].findings),
        "corpus_case_count": 0
        if optional_reports["corpus_results_report"] is None
        else optional_reports["corpus_results_report"]["summary"]["case_count"],
        "corpus_passed_case_count": 0
        if optional_reports["corpus_results_report"] is None
        else optional_reports["corpus_results_report"]["summary"]["passed_count"],
        "corpus_failed_case_count": 0
        if optional_reports["corpus_results_report"] is None
        else optional_reports["corpus_results_report"]["summary"]["failed_count"],
        "corpus_execution_error_count": 0
        if optional_reports["corpus_results_report"] is None
        else optional_reports["corpus_results_report"]["summary"]["execution_error_count"],
        "ruff_findings": stage_reports["ruff_report"].get("finding_count", 0),
        "pyright_errors": stage_reports["pyright_report"].get("error_count", 0),
        "pyright_warnings": stage_reports["pyright_report"].get("warning_count", 0),
        "pytest_failures": pytest_summary["failures"],
        "pytest_errors": pytest_summary["errors"],
        "vulture_findings": stage_reports["vulture_report"].get("finding_count", 0),
        "bandit_findings": len(stage_reports["bandit_report"].get("findings", [])),
        "architecture_findings": len(optional_reports["architecture_report"]["findings"]),
        "semantic_rule_count": len(optional_reports["analyzer_registry_report"]["rules"]),
        "phase2_rule_metadata_blocking_gaps": len(derived_reports["phase2_rule_metadata_gate"]["blocking_rule_ids"]),
        "phase2_rule_metadata_advisory_gaps": len(derived_reports["phase2_rule_metadata_gate"]["advisory_rule_ids"]),
        "dependency_graph_edges": len(optional_reports["dependency_graph_report"]["edges"]),
        "call_graph_edges": len(optional_reports["call_graph_report"]["edges"]),
        "graphics_layout_entries": len(optional_reports["graphics_layout_report"]["entries"]),
        "graphics_layout_groups": len(optional_reports["graphics_layout_report"]["groups"]),
        "graphics_layout_findings": len(optional_reports["graphics_layout_report"]["findings"]),
        "impact_analysis_library_nodes": len(optional_reports["impact_analysis_report"]["library_impacts"]),
        "impact_analysis_module_nodes": len(optional_reports["impact_analysis_report"]["module_impacts"]),
        "workspace_graph_snapshot_failures": 0
        if optional_reports["workspace_graph_inputs"] is None
        else len(optional_reports["workspace_graph_inputs"].snapshot_failures),
        "trace_dataflow_issues": 0
        if optional_reports["trace_report"] is None
        else optional_reports["trace_report"].get("dataflow_analysis", {}).get("issue_count", 0),
        "trace_unreachable_logic": 0
        if optional_reports["trace_report"] is None
        else len(optional_reports["trace_report"].get("heuristics", {}).get("unreachable_logic", [])),
        "trace_transform_violations": 0
        if optional_reports["trace_report"] is None
        else len(optional_reports["trace_report"].get("heuristics", {}).get("transform_invariant_violations", [])),
        "profiling_total_duration_ms": 0.0
        if profiling_summary_report is None
        else profiling_summary_report["total_duration_ms"],
        "profiling_phase_count": 0
        if profiling_summary_report is None
        else profiling_summary_report["summary"]["phase_count"],
        "profiling_slow_phase_count": 0
        if profiling_summary_report is None
        else profiling_summary_report["summary"]["slow_phase_count"],
        "performance_budget_violation_count": 0
        if performance_budget_report is None
        else performance_budget_report["violation_count"],
    }


def _check_core_invariants(
    derived_reports: dict[str, Any],
    context: dict[str, Any],
) -> list[str]:
    """Hard-fail enforcement: verify core invariants before emitting artifacts."""
    violations: list[str] = []
    finding_collection = derived_reports.get("finding_collection")
    if finding_collection is None:
        return violations

    findings = finding_collection.findings
    # Invariant: no duplicate finding fingerprints across the collection
    seen_fingerprints: set[str] = set()
    for f in findings:
        fingerprint = getattr(f, "fingerprint", None) or getattr(f, "id", None)
        if fingerprint and fingerprint in seen_fingerprints:
            violations.append(f"Duplicate finding fingerprint: {fingerprint}")
        if fingerprint:
            seen_fingerprints.add(fingerprint)

    # Invariant: transform-invariant violations must be reported
    trace_report = cast(dict[str, Any], derived_reports.get("trace_report") or {})
    heuristics = cast(dict[str, Any], trace_report.get("heuristics") or {})
    transform_violations = cast(list[Any], heuristics.get("transform_invariant_violations") or [])
    if transform_violations:
        violations.append(f"Transform invariant violations: {len(transform_violations)}")

    return violations


def _finalize_pipeline_outputs(
    context: dict[str, Any],
    stage_reports: dict[str, Any],
    optional_reports: dict[str, Any],
    derived_reports: dict[str, Any],
    *,
    fail_on_drift: bool,
    fail_on_budget: bool,
) -> dict[str, Any]:
    tool_statuses = _build_core_tool_statuses(stage_reports, optional_reports, derived_reports, context)
    tool_statuses.update(
        _build_policy_tool_statuses(
            derived_reports,
            fail_on_drift=fail_on_drift,
            fail_on_budget=fail_on_budget,
        )
    )
    overall_status_value = _overall_status(tool_statuses)
    failing_tools = [name for name, payload in tool_statuses.items() if payload["status"] == "fail"]
    non_blocking_tools = [name for name, payload in tool_statuses.items() if payload["status"] == "pass_with_notes"]
    reports = artifact_reports_map(
        PIPELINE_ARTIFACTS,
        profile=context["profile"],
        enabled_artifact_ids=context["enabled_artifacts"],
    )

    status_report = build_pipeline_status_report(
        profile=context["profile"],
        sanitized_output_dir=context["sanitized_output_dir"],
        overall_status_value=overall_status_value,
        tool_statuses=tool_statuses,
        failing_tools=failing_tools,
        non_blocking_tools=non_blocking_tools,
        progress_report=f"{context['sanitized_output_dir']}/progress.json",
        findings_schema=derived_reports["findings_schema"],
    )
    summary = build_pipeline_summary_report(
        profile=context["profile"],
        sanitized_output_dir=context["sanitized_output_dir"],
        reports=reports,
        overall_status_value=overall_status_value,
        tool_statuses=tool_statuses,
        failing_tools=failing_tools,
        non_blocking_tools=non_blocking_tools,
        tool_exit_codes=_build_pipeline_tool_exit_codes(
            stage_reports,
            optional_reports,
            derived_reports,
            context,
            fail_on_drift=fail_on_drift,
            fail_on_budget=fail_on_budget,
        ),
        artifact_registry_report=context["artifact_registry_report"],
        progress_report=f"{context['sanitized_output_dir']}/progress.json",
        findings_schema=derived_reports["findings_schema"],
        counts=_build_pipeline_counts(stage_reports, optional_reports, derived_reports, context),
    )
    recommendation_drift: dict[str, Any] | None = None
    if context["selected_checks"] is None:
        recommendation_drift = _build_recommendation_drift_report(
            profile=context["profile"],
            changed_files=context["changed_files"],
            recommended_check_ids=build_pipeline_check_recommendations(
                profile=context["profile"],
                output_dir=context["output_dir"],
                changed_files=context["changed_files"],
            )["recommended_check_ids"],
            tool_statuses=tool_statuses,
        )
        summary["recommendation_drift"] = recommendation_drift
        status_report["recommendation_drift"] = {
            "status": recommendation_drift["status"],
            "omitted_nonpassing_check_ids": recommendation_drift["omitted_nonpassing_check_ids"],
        }
    if context["selected_checks"] is not None:
        selected_checks = list(context["selected_checks"])
        status_report["selected_checks"] = selected_checks
        summary["selected_checks"] = selected_checks

    artifact_context = PipelineArtifactContext(
        payloads={
            "progress": context["progress"].to_dict(),
            "artifact_registry": context["artifact_registry_report"],
            "environment": stage_reports["environment_report"]
            if "environment" in context["enabled_artifacts"]
            else None,
            "ruff": stage_reports["ruff_report"] if "ruff" in context["enabled_artifacts"] else None,
            "pyright": stage_reports["pyright_report"] if "pyright" in context["enabled_artifacts"] else None,
            "pytest": stage_reports["pytest_report"] if "pytest" in context["enabled_artifacts"] else None,
            "vulture": None if stage_reports["vulture_report"].get("skipped") else stage_reports["vulture_report"],
            "bandit": None if stage_reports["bandit_report"].get("skipped") else stage_reports["bandit_report"],
            "architecture": None
            if optional_reports["architecture_report"].get("skipped")
            else optional_reports["architecture_report"],
            "analyzer_registry": None
            if optional_reports["analyzer_registry_report"].get("skipped")
            else optional_reports["analyzer_registry_report"],
            "dependency_graph": None
            if optional_reports["dependency_graph_report"].get("skipped")
            else optional_reports["dependency_graph_report"],
            "call_graph": None
            if optional_reports["call_graph_report"].get("skipped")
            else optional_reports["call_graph_report"],
            "graphics_layout": None
            if optional_reports["graphics_layout_report"].get("skipped")
            else optional_reports["graphics_layout_report"],
            "impact_analysis": None
            if optional_reports["impact_analysis_report"].get("skipped")
            else optional_reports["impact_analysis_report"],
            "trace": optional_reports["trace_report"],
            "incremental_analysis": derived_reports["incremental_analysis_report"],
            "findings": derived_reports["finding_collection"].to_dict(),
            "analysis_diff": derived_reports["analysis_diff_report"],
            "recommendation_drift": recommendation_drift,
            "corpus_results": optional_reports["corpus_results_report"],
            "coverage_summary": derived_reports["coverage_summary_report"],
            "current_debt_snapshot": derived_reports["current_debt_snapshot_report"],
            "sattline_semantic": derived_reports["sattline_semantic_report"],
            "rule_metrics": derived_reports["rule_metrics_report"],
            "profiling_summary": derived_reports["profiling_summary_report"],
            "performance_budget": derived_reports["performance_budget_report"],
            "mutation_results": derived_reports["mutation_results"],
            "differential": derived_reports["differential_report"],
            "status": status_report,
            "summary": summary,
        }
    )
    context["progress"].start_stage("write_artifacts")
    write_pipeline_artifacts(
        context["output_dir"],
        artifacts=PIPELINE_ARTIFACTS,
        profile=context["profile"],
        enabled_artifact_ids=context["enabled_artifacts"],
        context=artifact_context,
        write_json=write_json_artifact,
    )
    context["progress"].complete_stage("write_artifacts")
    context["progress"].finalize(overall_status=overall_status_value)
    timing_summary = _build_pipeline_timing_summary(
        progress=context["progress"],
        tool_statuses=tool_statuses,
        pytest_workers=context.get("pytest_workers"),
    )
    status_report["timing"] = timing_summary
    summary["timing"] = timing_summary
    write_json_artifact(context["output_dir"] / "status.json", status_report)
    write_json_artifact(context["output_dir"] / "summary.json", summary)
    return summary


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


def _build_failure_tool_statuses(
    progress: ProgressReporter,
    *,
    failing_stage_key: str | None,
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
            tool_statuses[tool_name] = _make_tool_status(
                status="pass",
                report=None,
                raw_exit_code=0,
                normalized_exit_code=0,
                detail=None if not isinstance(stage_detail, str) else stage_detail,
            )
            continue
        if stage_key == failing_stage_key or stage_status == "failed":
            tool_statuses[tool_name] = _make_tool_status(
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
        tool_statuses[tool_name] = _make_tool_status(
            status="skipped",
            report=None,
            raw_exit_code=None,
            normalized_exit_code=None,
            detail="not reached due earlier failure",
        )

    for tool_name in ("rule_metadata", "baseline_drift", "performance_budget"):
        tool_statuses[tool_name] = _make_tool_status(
            status="skipped",
            report=None,
            raw_exit_code=None,
            normalized_exit_code=None,
            detail="not reached due earlier failure",
        )
    return tool_statuses


def _write_pipeline_failure_artifacts(
    context: dict[str, Any],
    error: BaseException,
) -> None:
    progress = cast(ProgressReporter, context["progress"])
    failing_stage_key = _progress_active_stage_key(progress)
    if failing_stage_key is not None:
        progress.fail_stage(failing_stage_key, detail=_exception_detail(error))
    progress.finalize(overall_status="failed")

    tool_statuses = _build_failure_tool_statuses(progress, failing_stage_key=failing_stage_key)
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


def _run_pipeline(
    output_dir: Path,
    *,
    trace_target: Path | None,
    mutation_target: Path | None = None,
    profile: str = DEFAULT_PIPELINE_PROFILE,
    include_vulture: bool | None = None,
    include_bandit: bool | None = None,
    baseline_findings: Path | None = None,
    corpus_manifest_dir: Path | None = None,
    changed_files: list[str] | None = None,
    slow_phase_threshold_ms: float = 25.0,
    phase_budget_ms: float = 50.0,
    total_budget_ms: float = 250.0,
    fail_on_drift: bool = False,
    fail_on_budget: bool = False,
    selected_checks: Iterable[str] | None = None,
    run_mutation_analysis: bool = False,
    pytest_workers: str | None = None,
) -> dict[str, Any]:
    context = _prepare_pipeline_run(
        output_dir,
        trace_target=trace_target,
        mutation_target=mutation_target,
        profile=profile,
        include_vulture=include_vulture,
        include_bandit=include_bandit,
        baseline_findings=baseline_findings,
        corpus_manifest_dir=corpus_manifest_dir,
        changed_files=changed_files,
        selected_checks=selected_checks,
        run_mutation_analysis=run_mutation_analysis,
        pytest_workers=pytest_workers,
    )
    try:
        progress = context["progress"]
        selected_checks = context.get("selected_checks")
        selected_check_set = None if selected_checks is None else set(selected_checks)

        def wants(check_id: str) -> bool:
            return selected_check_set is None or check_id in selected_check_set

        environment_report = skipped_stage_report("environment")
        if wants("ruff") or wants("pyright") or wants("pytest"):
            environment_report = _run_environment_stage(progress)

        if wants("ruff"):
            ruff_report, ruff_findings = _run_ruff_stage(progress, python_cmd=context["python_cmd"])
        else:
            ruff_report, ruff_findings = skipped_stage_report("ruff"), []

        if wants("pyright"):
            pyright_report, pyright_findings = _run_pyright_stage(progress, python_cmd=context["python_cmd"])
        else:
            pyright_report, pyright_findings = skipped_stage_report("pyright"), []

        if wants("pytest"):
            pytest_report = _run_pytest_stage(
                progress,
                output_dir=context["output_dir"],
                python_cmd=context["python_cmd"],
                profile=context["profile"],
                pytest_workers=context.get("pytest_workers"),
            )
        else:
            pytest_report = skipped_stage_report("pytest")

        if wants("vulture"):
            vulture_report, _vulture_findings = _run_vulture_stage(
                progress,
                python_cmd=context["python_cmd"],
                run_vulture=context["run_vulture"],
            )
        else:
            vulture_report, _vulture_findings = (
                {"tool": "vulture", "skipped": True, "detail": "skipped by check selection"},
                [],
            )

        if wants("bandit"):
            bandit_report = _run_bandit_stage(
                progress,
                python_cmd=context["python_cmd"],
                run_bandit=context["run_bandit"],
            )
        else:
            bandit_report = {"tool": "bandit", "skipped": True, "detail": "skipped by check selection"}
        stage_reports = {
            "bandit_report": bandit_report,
            "environment_report": environment_report,
            "pyright_findings": pyright_findings,
            "pyright_report": pyright_report,
            "pytest_report": pytest_report,
            "ruff_findings": ruff_findings,
            "ruff_report": ruff_report,
            "vulture_report": vulture_report,
        }
        optional_reports = _collect_optional_reports(context, trace_target=trace_target)
        derived_reports = _build_derived_reports(
            context,
            stage_reports,
            optional_reports,
            baseline_findings=baseline_findings,
            slow_phase_threshold_ms=slow_phase_threshold_ms,
            phase_budget_ms=phase_budget_ms,
            total_budget_ms=total_budget_ms,
        )
        # Hard-fail invariant enforcement (ID 23: Core invariant checks)
        invariant_violations = _check_core_invariants(derived_reports, context)
        if invariant_violations:
            for v in invariant_violations:
                print(f"INVARIANT VIOLATION: {v}")
        return _finalize_pipeline_outputs(
            context,
            stage_reports,
            optional_reports,
            derived_reports,
            fail_on_drift=fail_on_drift,
            fail_on_budget=fail_on_budget,
        )
    except BaseException as error:
        _write_pipeline_failure_artifacts(context, error)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the SattLint analysis pipeline and emit JSON reports.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where JSON reports will be written",
    )
    parser.add_argument(
        "--profile",
        choices=PIPELINE_PROFILE_CHOICES,
        default=DEFAULT_PIPELINE_PROFILE,
        help="Run the fast quick profile or the complete full profile",
    )
    parser.add_argument(
        "--trace-target",
        default=str(DEFAULT_TRACE_TARGET) if DEFAULT_TRACE_TARGET.exists() else "",
        help="Optional SattLine source fixture to trace into trace.json",
    )
    parser.add_argument(
        "--mutation-target",
        default="",
        help="Optional SattLine source fixture to mutate into mutation_results.json",
    )
    parser.add_argument(
        "--run-mutation-analysis",
        action="store_true",
        help="Emit mutation_results.json for the selected mutation target or trace target.",
    )
    parser.add_argument(
        "--baseline-findings",
        default="",
        help="Optional normalized findings.json file used to emit analysis_diff.json",
    )
    parser.add_argument(
        "--corpus-manifest-dir",
        default="",
        help="Optional directory of corpus manifests used to emit corpus_results.json",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=None,
        help="Repo-relative path to include in incremental_analysis.json. Repeatable.",
    )
    parser.add_argument(
        "--slow-phase-threshold-ms",
        type=float,
        default=25.0,
        help="Minimum phase duration included in profiling_summary.json slow_phases.",
    )
    parser.add_argument(
        "--phase-budget-ms",
        type=float,
        default=50.0,
        help="Per-phase duration budget used by performance_budget.json.",
    )
    parser.add_argument(
        "--total-budget-ms",
        type=float,
        default=250.0,
        help="Total trace duration budget used by performance_budget.json.",
    )
    parser.add_argument(
        "--check",
        action="append",
        choices=PIPELINE_CHECK_IDS,
        default=None,
        help="Run only the named pipeline check. Repeatable.",
    )
    parser.add_argument(
        "--pytest-workers",
        default=None,
        help="Optional pytest-xdist worker setting forwarded as '-n <value>' to pipeline and finish-gate pytest runs.",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="Print the individually runnable pipeline checks for the selected profile as JSON and exit.",
    )
    parser.add_argument(
        "--recommend-checks",
        action="store_true",
        help="Print machine-readable recommended pipeline checks for the changed files and exit.",
    )
    parser.add_argument(
        "--run-recommended-slice",
        action="store_true",
        help="Run the recommended pipeline checks for the changed files instead of the full selected profile.",
    )
    parser.add_argument(
        "--run-recommended-finish-gate",
        action="store_true",
        help="Run the recommended pipeline slice plus focused touched-file Ruff, Pyright, and owner pytest commands.",
    )
    parser.add_argument("--skip-vulture", action="store_true", help="Skip the Vulture dead-code scan")
    parser.add_argument("--skip-bandit", action="store_true", help="Skip the Bandit security scan")
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help=(
            "Exit with code 1 if the baseline comparison finds new or resolved findings. Requires --baseline-findings."
        ),
    )
    parser.add_argument(
        "--fail-on-budget",
        action="store_true",
        help="Exit with code 1 when performance_budget.json reports budget violations.",
    )
    parser.add_argument(
        "--save-baseline",
        default="",
        help="Copy the emitted findings.json to this path after a successful run (approve-or-refresh workflow).",
    )
    args = parser.parse_args(argv)

    if args.check and (args.recommend_checks or args.run_recommended_slice or args.run_recommended_finish_gate):
        parser.error("--check cannot be combined with recommendation modes.")

    if args.list_checks:
        print(
            json.dumps(
                build_pipeline_check_catalog(
                    profile=args.profile,
                    output_dir=Path(args.output_dir).resolve(),
                ),
                indent=2,
            )
        )
        return 0
    if args.recommend_checks:
        print(
            json.dumps(
                build_pipeline_check_recommendations(
                    profile=args.profile,
                    output_dir=Path(args.output_dir).resolve(),
                    changed_files=args.changed_file,
                ),
                indent=2,
            )
        )
        return 0
    if args.run_recommended_finish_gate:
        finish_gate = run_recommended_pipeline_finish_gate(
            Path(args.output_dir).resolve(),
            trace_target=Path(args.trace_target).resolve() if args.trace_target else None,
            profile=args.profile,
            include_vulture=False if args.skip_vulture else None,
            include_bandit=False if args.skip_bandit else None,
            baseline_findings=Path(args.baseline_findings).resolve() if args.baseline_findings else None,
            corpus_manifest_dir=Path(args.corpus_manifest_dir).resolve() if args.corpus_manifest_dir else None,
            changed_files=args.changed_file,
            slow_phase_threshold_ms=args.slow_phase_threshold_ms,
            phase_budget_ms=args.phase_budget_ms,
            total_budget_ms=args.total_budget_ms,
            fail_on_drift=args.fail_on_drift,
            fail_on_budget=args.fail_on_budget,
            pytest_workers=args.pytest_workers,
        )
        summary = finish_gate["pipeline_summary"]
        _print_cli_summary(
            {
                "profile": summary["profile"],
                "overall_status": finish_gate["overall_status"],
                "tool_statuses": summary["status"]["tool_statuses"],
                "findings_schema": summary.get("findings_schema"),
                "status_report": f"{summary['output_dir']}/status.json",
                "summary_report": f"{summary['output_dir']}/summary.json",
                "corpus_results_report": (
                    None
                    if summary["reports"].get("corpus_results") is None
                    else f"{summary['output_dir']}/corpus_results.json"
                ),
                "analysis_diff_report": (
                    None
                    if summary["reports"].get("analysis_diff") is None
                    else f"{summary['output_dir']}/analysis_diff.json"
                ),
                "analysis_diff_summary": {
                    "new_count": summary["counts"]["baseline_new_findings"],
                    "resolved_count": summary["counts"]["baseline_resolved_findings"],
                    "changed_count": summary["counts"]["baseline_changed_findings"],
                    "unchanged_count": summary["counts"]["baseline_unchanged_findings"],
                },
            }
        )
        return 1 if finish_gate["overall_status"] == "fail" else 0

    trace_target = Path(args.trace_target).resolve() if args.trace_target else None
    mutation_target = Path(args.mutation_target).resolve() if args.mutation_target else None
    baseline_findings = Path(args.baseline_findings).resolve() if args.baseline_findings else None
    corpus_manifest_dir = Path(args.corpus_manifest_dir).resolve() if args.corpus_manifest_dir else None
    save_baseline = Path(args.save_baseline).resolve() if args.save_baseline else None
    selected_checks = args.check
    if args.run_recommended_slice:
        selected_checks = build_pipeline_check_recommendations(
            profile=args.profile,
            output_dir=Path(args.output_dir).resolve(),
            changed_files=args.changed_file,
        )["recommended_check_ids"]
    summary = _run_pipeline(
        Path(args.output_dir).resolve(),
        trace_target=trace_target,
        mutation_target=mutation_target,
        profile=args.profile,
        include_vulture=False if args.skip_vulture else None,
        include_bandit=False if args.skip_bandit else None,
        baseline_findings=baseline_findings,
        corpus_manifest_dir=corpus_manifest_dir,
        changed_files=args.changed_file,
        slow_phase_threshold_ms=args.slow_phase_threshold_ms,
        phase_budget_ms=args.phase_budget_ms,
        total_budget_ms=args.total_budget_ms,
        fail_on_drift=args.fail_on_drift,
        fail_on_budget=args.fail_on_budget,
        selected_checks=selected_checks,
        run_mutation_analysis=(args.run_mutation_analysis or bool(args.mutation_target)),
        pytest_workers=args.pytest_workers,
    )
    if save_baseline is not None:
        findings_src = Path(args.output_dir).resolve() / "findings.json"
        if findings_src.exists():
            save_baseline.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(findings_src, save_baseline)
    _print_cli_summary(
        {
            "profile": summary["profile"],
            "overall_status": summary["status"]["overall_status"],
            "tool_statuses": summary["status"]["tool_statuses"],
            "findings_schema": summary.get("findings_schema"),
            "status_report": f"{summary['output_dir']}/status.json",
            "summary_report": f"{summary['output_dir']}/summary.json",
            "corpus_results_report": (
                None
                if summary["reports"].get("corpus_results") is None
                else f"{summary['output_dir']}/corpus_results.json"
            ),
            "analysis_diff_report": (
                None
                if summary["reports"].get("analysis_diff") is None
                else f"{summary['output_dir']}/analysis_diff.json"
            ),
            "analysis_diff_summary": {
                "new_count": summary["counts"]["baseline_new_findings"],
                "resolved_count": summary["counts"]["baseline_resolved_findings"],
                "changed_count": summary["counts"]["baseline_changed_findings"],
                "unchanged_count": summary["counts"]["baseline_unchanged_findings"],
            },
        }
    )
    return 1 if summary["status"]["overall_status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
