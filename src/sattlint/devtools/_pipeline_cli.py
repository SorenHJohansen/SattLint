"""Pipeline CLI and recommendation helpers."""

from __future__ import annotations

import shlex
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sattlint.path_sanitizer import sanitize_path_for_report


def build_pipeline_check_catalog(
    *,
    profile: str,
    output_dir: Path | None,
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module
    from sattlint.devtools import pipeline_checks

    return pipeline_checks.build_pipeline_check_catalog(
        profile=profile,
        output_dir=output_dir or pipeline_module.DEFAULT_OUTPUT_DIR,
        repo_root=pipeline_module.REPO_ROOT,
        validate_profile=pipeline_module._profile_settings,
    )


def _shell_command(command: list[str]) -> str:
    return shlex.join(command)


def _changed_file_flag_args(changed_files: Iterable[str]) -> list[str]:
    from sattlint.devtools import pipeline as pipeline_module

    args: list[str] = []
    for path_text in pipeline_module.normalize_changed_files(changed_files):
        args.extend(["--changed-file", path_text])
    return args


def _focused_python_files(changed_files: Iterable[str]) -> list[str]:
    from sattlint.devtools import pipeline as pipeline_module

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


def _mutation_guidance(changed_files: Iterable[str]) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    matched_surfaces: list[str] = []
    suggested_commands: list[str] = []
    rules = (
        (
            "parser",
            ("src/sattline_parser/", "tests/test_parser", "src/sattlint/grammar/"),
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_core.py tests/test_parser_validation.py -x -q --tb=short',
        ),
        (
            "validation",
            ("src/sattlint/validation.py", "src/sattlint/_validation", "tests/test_parser_validation.py"),
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_parser_validation.py -x -q --tb=short',
        ),
        (
            "routing",
            (
                "src/sattlint/devtools/pipeline.py",
                "src/sattlint/devtools/pipeline_checks.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/repo_audit_cli.py",
                "src/sattlint/devtools/repo_audit_entrypoints.py",
                "src/sattlint/devtools/ai_work_map.py",
                "tests/test_recommendation_routing.py",
            ),
            '& ".venv/Scripts/python.exe" -m pytest --no-cov tests/test_pipeline_run.py tests/test_repo_audit.py tests/test_recommendation_routing.py -x -q --tb=short',
        ),
    )
    for surface_name, prefixes, command in rules:
        if not any(path_text.startswith(prefix) for prefix in prefixes for path_text in normalized_changed_files):
            continue
        matched_surfaces.append(surface_name)
        if command not in suggested_commands:
            suggested_commands.append(command)

    if not matched_surfaces:
        return {
            "status": "not-applicable",
            "critical_surfaces": [],
            "suggested_commands": [],
            "suggestion": None,
        }
    return {
        "status": "advisory",
        "critical_surfaces": matched_surfaces,
        "suggested_commands": suggested_commands,
        "suggestion": (
            "Prefer mutation-style or property-style assertions for parser, validation, and routing seams before "
            "treating the repo-wide coverage percentage as sufficient proof."
        ),
    }


def build_change_proof_requirements(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    owner_test_targets = _owner_test_targets_for_checks(recommended_checks)
    touched_python_files = _focused_python_files(normalized_changed_files)
    touched_source_files = _changed_source_python_files(normalized_changed_files)
    focused_behavior_required = bool(touched_python_files)
    focused_behavior_status = "satisfied" if (not focused_behavior_required or owner_test_targets) else "missing"
    return {
        "focused_behavior_test": {
            "required": focused_behavior_required,
            "status": focused_behavior_status,
            "owner_test_targets": owner_test_targets,
            "reason": (
                "Code changes require at least one focused owner pytest target."
                if focused_behavior_required
                else "No changed Python files require a focused owner pytest target."
            ),
        },
        "coverage": {
            "required": bool(touched_source_files),
            "preferred_mode": "changed-lines" if touched_source_files else None,
            "fallback_mode": "touched-files" if touched_source_files else None,
            "touched_source_files": touched_source_files,
            "reason": (
                "Touched source files should be proven by focused changed-line coverage when executable diff lines "
                "exist, or touched-file coverage otherwise."
                if touched_source_files
                else "No changed source files require focused coverage proof."
            ),
        },
        "mutation_guidance": _mutation_guidance(normalized_changed_files),
    }


def _build_owner_pytest_step(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    python_command: list[str],
    coverage_output_path: Path,
) -> dict[str, Any] | None:
    owner_test_targets = _owner_test_targets_for_checks(recommended_checks)
    if not owner_test_targets:
        return None
    touched_source_files = _changed_source_python_files(changed_files)
    if touched_source_files:
        pytest_argv = [*python_command, "-m", "pytest", *owner_test_targets, "-x", "-q", "--tb=short"]
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
    pytest_argv = [*python_command, "-m", "pytest", "--no-cov", *owner_test_targets, "-x", "-q", "--tb=short"]
    return {
        "id": "owner-pytest",
        "label": "Run owner pytest targets for the recommended checks",
        "command": _shell_command(pytest_argv),
        "argv": pytest_argv,
    }


def evaluate_change_scoped_coverage_proof(
    *,
    repo_root: Path,
    coverage_output_path: Path,
    changed_files: Iterable[str],
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module

    report = pipeline_module.build_coverage_summary_report(
        repo_root,
        coverage_path=coverage_output_path,
        changed_files=changed_files,
    )
    change_scoped = dict(report["change_scoped"])
    change_scoped["coverage_path"] = (
        sanitize_path_for_report(coverage_output_path.resolve(), repo_root=repo_root)
        or coverage_output_path.resolve().as_posix()
    )
    return change_scoped


def _build_finish_gate_commands(
    *,
    profile: str,
    output_dir: Path,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    ruff_command: list[str],
    pyright_command: list[str],
    python_command: list[str],
) -> list[dict[str, Any]]:
    from sattlint.devtools import pipeline as pipeline_module

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
    )
    if owner_pytest_step is not None:
        commands.append(owner_pytest_step)
    return commands


def _build_recommendation_why_this_gate(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    skipped_checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module
    from sattlint.devtools import pipeline_checks

    normalized_changed_files = pipeline_module.normalize_changed_files(changed_files)
    matched_routes: list[dict[str, Any]] = []
    for entry in recommended_checks:
        matched_files = pipeline_checks.matching_changed_files(normalized_changed_files, entry["path_globs"])
        matched_routes.append(
            {
                "check_id": entry["id"],
                "owner_surface": entry["owner_surface"],
                "matched_files": matched_files,
                "path_globs": entry["path_globs"],
                "reason": entry["reason"],
            }
        )
    return {
        "changed_files": normalized_changed_files,
        "matched_routes": matched_routes,
        "skipped_checks": list(skipped_checks),
    }


def _build_recommendation_drift_report(
    *,
    profile: str,
    changed_files: Iterable[str],
    recommended_check_ids: Iterable[str],
    tool_statuses: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module

    recommended_ids = list(dict.fromkeys(recommended_check_ids))
    observed_nonpassing_check_ids = [
        check_id
        for check_id in pipeline_module.PIPELINE_CHECK_IDS
        if tool_statuses.get(check_id, {}).get("status") in {"fail", "pass_with_notes"}
    ]
    omitted_nonpassing_check_ids = [
        check_id for check_id in observed_nonpassing_check_ids if check_id not in recommended_ids
    ]
    return {
        "kind": "sattlint.pipeline.recommendation_drift",
        "schema_version": 1,
        "profile": profile,
        "changed_files": pipeline_module.normalize_changed_files(changed_files),
        "recommended_check_ids": recommended_ids,
        "observed_nonpassing_check_ids": observed_nonpassing_check_ids,
        "omitted_nonpassing_check_ids": omitted_nonpassing_check_ids,
        "status": "drift" if omitted_nonpassing_check_ids else "consistent",
    }


def build_pipeline_check_recommendations(
    *,
    profile: str,
    output_dir: Path | None,
    changed_files: Iterable[str] | None,
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module
    from sattlint.devtools import pipeline_checks

    resolved_output_dir = (output_dir or pipeline_module.DEFAULT_OUTPUT_DIR).resolve()
    resolved_changed_files = pipeline_module.normalize_changed_files(
        pipeline_module._detect_changed_files(repo_root=pipeline_module.REPO_ROOT)
        if changed_files is None
        else changed_files
    )
    catalog = build_pipeline_check_catalog(
        profile=profile,
        output_dir=resolved_output_dir,
    )
    fallback_required = False
    fallback_reason: str | None = None
    recommendation_reasons: dict[str, str] = {}

    if not resolved_changed_files:
        fallback_required = True
        fallback_reason = (
            "No changed files were provided or detected, so the full supported pipeline slice is recommended."
        )
    elif pipeline_checks.matching_changed_files(
        resolved_changed_files, pipeline_checks.PIPELINE_RECOMMENDATION_FALLBACK_GLOBS
    ):
        fallback_required = True
        fallback_reason = (
            "Changed files touch the pipeline control surface, so the full supported pipeline slice is recommended."
        )

    if fallback_required and fallback_reason is not None:
        for entry in catalog["checks"]:
            recommendation_reasons[entry["id"]] = fallback_reason
    else:
        for entry in catalog["checks"]:
            matched_files = pipeline_checks.matching_changed_files(resolved_changed_files, entry["path_globs"])
            if not matched_files:
                continue
            recommendation_reasons[entry["id"]] = f"Matched {matched_files[0]} against the {entry['id']} routing globs."
        if not recommendation_reasons:
            fallback_required = True
            fallback_reason = "No pipeline routing globs matched the changed files, so the full supported pipeline slice is recommended."
            for entry in catalog["checks"]:
                recommendation_reasons[entry["id"]] = fallback_reason

    recommended_checks: list[dict[str, Any]] = []
    skipped_checks: list[dict[str, Any]] = []
    for entry in catalog["checks"]:
        reason = recommendation_reasons.get(entry["id"])
        if reason is None:
            skipped_checks.append(
                {
                    "id": entry["id"],
                    "label": entry["label"],
                    "reason": "No changed-file route matched this check.",
                }
            )
            continue
        recommended_checks.append({**entry, "reason": reason})

    suggested_finish_gate_commands = _build_finish_gate_commands(
        profile=profile,
        output_dir=resolved_output_dir,
        changed_files=resolved_changed_files,
        recommended_checks=recommended_checks,
        ruff_command=["ruff"],
        pyright_command=["pyright"],
        python_command=["python"],
    )

    return {
        "kind": "sattlint.pipeline.check_recommendations",
        "schema_version": 1,
        "profile": profile,
        "changed_files": resolved_changed_files,
        "fallback_required": fallback_required,
        "fallback_reason": fallback_reason,
        "recommended_check_ids": [entry["id"] for entry in recommended_checks],
        "suggested_check_commands": [entry["command"] for entry in recommended_checks],
        "suggested_finish_gate_commands": [entry["command"] for entry in suggested_finish_gate_commands],
        "recommended_checks": recommended_checks,
        "skipped_checks": skipped_checks,
        "proof_requirements": build_change_proof_requirements(
            changed_files=resolved_changed_files,
            recommended_checks=recommended_checks,
        ),
        "why_this_gate": _build_recommendation_why_this_gate(
            changed_files=resolved_changed_files,
            recommended_checks=recommended_checks,
            skipped_checks=skipped_checks,
        ),
    }


def run_recommended_pipeline_finish_gate(
    output_dir: Path,
    *,
    trace_target: Path | None,
    profile: str,
    include_vulture: bool | None,
    include_bandit: bool | None,
    baseline_findings: Path | None,
    corpus_manifest_dir: Path | None,
    changed_files: Iterable[str] | None,
    slow_phase_threshold_ms: float,
    phase_budget_ms: float,
    total_budget_ms: float,
    fail_on_drift: bool,
    fail_on_budget: bool,
) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module

    recommendation = pipeline_module.build_pipeline_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        changed_files=changed_files,
    )
    proof_requirements = recommendation.get("proof_requirements") or pipeline_module.build_change_proof_requirements(
        changed_files=recommendation.get("changed_files", []),
        recommended_checks=recommendation.get("recommended_checks", []),
    )
    summary = pipeline_module._run_pipeline(
        output_dir,
        trace_target=trace_target,
        profile=profile,
        include_vulture=include_vulture,
        include_bandit=include_bandit,
        baseline_findings=baseline_findings,
        corpus_manifest_dir=corpus_manifest_dir,
        changed_files=pipeline_module.normalize_changed_files(changed_files),
        slow_phase_threshold_ms=slow_phase_threshold_ms,
        phase_budget_ms=phase_budget_ms,
        total_budget_ms=total_budget_ms,
        fail_on_drift=fail_on_drift,
        fail_on_budget=fail_on_budget,
        selected_checks=recommendation["recommended_check_ids"],
    )
    finish_gate_steps = _build_finish_gate_commands(
        profile=profile,
        output_dir=output_dir,
        changed_files=recommendation["changed_files"],
        recommended_checks=recommendation["recommended_checks"],
        ruff_command=[pipeline_module._resolve_venv_tool("ruff") or "ruff"],
        pyright_command=[pipeline_module._resolve_venv_tool("pyright") or "pyright"],
        python_command=[pipeline_module._resolve_python_executable()],
    )[1:]
    step_reports: list[dict[str, Any]] = []
    finish_gate_status = "pass"
    coverage_proof: dict[str, Any] = {
        "status": "not-required",
        "mode": "skipped",
        "coverage_path": None,
    }
    for step in finish_gate_steps:
        result = pipeline_module._run_command(step["id"], step["argv"])
        step_status = "pass" if result.exit_code == 0 else "fail"
        if step_status == "fail":
            finish_gate_status = "fail"
        step_reports.append(
            {
                "id": step["id"],
                "label": step["label"],
                "command": step["command"],
                "exit_code": result.exit_code,
                "duration_seconds": result.duration_seconds,
                "status": step_status,
            }
        )
    if proof_requirements["focused_behavior_test"]["status"] == "missing":
        finish_gate_status = "fail"
        step_reports.append(
            {
                "id": "focused-behavior-test",
                "label": "Require focused owner pytest for changed code",
                "command": "",
                "exit_code": None,
                "duration_seconds": 0.0,
                "status": "fail",
                "detail": proof_requirements["focused_behavior_test"]["reason"],
            }
        )
    coverage_step = next((step for step in finish_gate_steps if step["id"] == "owner-pytest-coverage"), None)
    if coverage_step is not None:
        coverage_proof = pipeline_module.evaluate_change_scoped_coverage_proof(
            repo_root=pipeline_module.REPO_ROOT,
            coverage_output_path=Path(coverage_step["coverage_output_path"]),
            changed_files=recommendation["changed_files"],
        )
        if coverage_proof["status"] == "fail":
            finish_gate_status = "fail"
    elif proof_requirements["coverage"]["required"]:
        coverage_proof = {
            "status": "fail",
            "mode": "skipped",
            "coverage_path": None,
            "reason": "Focused coverage proof is required for changed source files but no owner pytest coverage step was available.",
        }
        finish_gate_status = "fail"
    finish_gate_report = {
        "kind": "sattlint.pipeline.finish_gate",
        "schema_version": 1,
        "status": finish_gate_status,
        "commands": step_reports,
        "changed_files": recommendation["changed_files"],
        "owner_test_targets": _owner_test_targets_for_checks(recommendation["recommended_checks"]),
        "proof_requirements": proof_requirements,
        "coverage_proof": coverage_proof,
    }
    pipeline_module.write_json_artifact(output_dir / "finish_gate.json", finish_gate_report)
    return {
        "recommendation": recommendation,
        "pipeline_summary": summary,
        "finish_gate": finish_gate_report,
        "overall_status": "fail"
        if summary["status"]["overall_status"] == "fail" or finish_gate_status == "fail"
        else "pass",
    }


__all__ = [
    "_build_finish_gate_commands",
    "_build_owner_pytest_step",
    "_build_recommendation_drift_report",
    "_build_recommendation_why_this_gate",
    "_changed_file_flag_args",
    "_focused_python_files",
    "_owner_test_targets_for_checks",
    "_shell_command",
    "build_change_proof_requirements",
    "build_pipeline_check_catalog",
    "build_pipeline_check_recommendations",
    "evaluate_change_scoped_coverage_proof",
    "run_recommended_pipeline_finish_gate",
]
