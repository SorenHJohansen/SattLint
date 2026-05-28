"""Pipeline CLI and recommendation helpers."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from sattlint.devtools._pipeline_finish_gate import (
    _build_finish_gate_commands,
    _build_owner_pytest_step,
    _changed_file_flag_args,
    _finish_gate_pipeline_check_ids,
    _focused_python_files,
    _owner_test_targets_for_checks,
    _shell_command,
    build_change_proof_requirements,
    evaluate_change_scoped_coverage_proof,
    execute_finish_gate_steps,
    summarize_finish_gate_timing,
)


def build_pipeline_check_catalog(*, profile: str, output_dir: Path | None) -> dict[str, Any]:
    from sattlint.devtools import pipeline as pipeline_module
    from sattlint.devtools import pipeline_checks

    return pipeline_checks.build_pipeline_check_catalog(
        profile=profile,
        output_dir=output_dir or pipeline_module.DEFAULT_OUTPUT_DIR,
        repo_root=pipeline_module.REPO_ROOT,
        validate_profile=pipeline_module.profile_settings,
    )


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
    from sattlint.devtools import _pipeline_recommendations as helper

    return helper.build_pipeline_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        changed_files=changed_files,
    )


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
    pytest_workers: str | None = None,
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
    selected_pipeline_checks = _finish_gate_pipeline_check_ids(
        recommended_check_ids=recommendation["recommended_check_ids"],
        changed_files=recommendation["changed_files"],
        recommended_checks=recommendation["recommended_checks"],
        pytest_workers=pytest_workers,
    )
    summary = pipeline_module.run_pipeline(
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
        selected_checks=selected_pipeline_checks,
        pytest_workers=pytest_workers,
    )
    finish_gate_steps = _build_finish_gate_commands(
        profile=profile,
        output_dir=output_dir,
        changed_files=recommendation["changed_files"],
        recommended_checks=recommendation["recommended_checks"],
        ruff_command=[pipeline_module.resolve_venv_tool("ruff") or "ruff"],
        pyright_command=[pipeline_module.resolve_venv_tool("pyright") or "pyright"],
        python_command=[pipeline_module.resolve_python_executable()],
        pytest_workers=pytest_workers,
    )[1:]
    step_reports = execute_finish_gate_steps(
        steps=finish_gate_steps,
        run_command=pipeline_module.run_command,
        pipeline_summary=summary,
    )
    finish_gate_status = "pass"
    coverage_proof: dict[str, Any] = {
        "status": "not-required",
        "mode": "skipped",
        "coverage_path": None,
    }
    for step_report in step_reports:
        step_status = str(step_report.get("status", "pass"))
        if step_status == "fail":
            finish_gate_status = "fail"
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
        "selected_pipeline_checks": selected_pipeline_checks,
        "owner_test_targets": _owner_test_targets_for_checks(recommendation["recommended_checks"]),
        "proof_requirements": proof_requirements,
        "coverage_proof": coverage_proof,
        "timing": summarize_finish_gate_timing(step_reports),
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


def build_pipeline_parser(
    *,
    default_output_dir: Path,
    default_trace_target: Path,
    profile_choices: Iterable[str],
    default_profile: str,
    check_ids: Iterable[str],
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the SattLint analysis pipeline and emit JSON reports.")
    parser.add_argument(
        "--output-dir",
        default=str(default_output_dir),
        help="Directory where JSON reports will be written",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(profile_choices),
        default=default_profile,
        help="Run the fast quick profile or the complete full profile",
    )
    parser.add_argument(
        "--trace-target",
        default=str(default_trace_target) if default_trace_target.exists() else "",
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
        choices=tuple(check_ids),
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
        help="Exit with code 1 if the baseline comparison finds new or resolved findings. Requires --baseline-findings.",
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
    return parser


def _build_cli_summary_payload(summary: dict[str, Any], *, overall_status: str | None = None) -> dict[str, Any]:
    resolved_overall_status = summary["status"]["overall_status"] if overall_status is None else overall_status
    return {
        "profile": summary["profile"],
        "overall_status": resolved_overall_status,
        "tool_statuses": summary["status"]["tool_statuses"],
        "findings_schema": summary.get("findings_schema"),
        "status_report": f"{summary['output_dir']}/status.json",
        "summary_report": f"{summary['output_dir']}/summary.json",
        "corpus_results_report": (
            None if summary["reports"].get("corpus_results") is None else f"{summary['output_dir']}/corpus_results.json"
        ),
        "analysis_diff_report": (
            None if summary["reports"].get("analysis_diff") is None else f"{summary['output_dir']}/analysis_diff.json"
        ),
        "analysis_diff_summary": {
            "new_count": summary["counts"]["baseline_new_findings"],
            "resolved_count": summary["counts"]["baseline_resolved_findings"],
            "changed_count": summary["counts"]["baseline_changed_findings"],
            "unchanged_count": summary["counts"]["baseline_unchanged_findings"],
        },
    }


def execute_pipeline_cli(
    args: Any,
    *,
    build_pipeline_check_catalog_fn: Callable[..., dict[str, Any]],
    build_pipeline_check_recommendations_fn: Callable[..., dict[str, Any]],
    run_recommended_pipeline_finish_gate_fn: Callable[..., dict[str, Any]],
    run_pipeline_fn: Callable[..., dict[str, Any]],
    print_cli_summary_fn: Callable[[dict[str, Any]], None],
) -> int:
    output_dir = Path(args.output_dir).resolve()
    if args.list_checks:
        print(
            json.dumps(
                build_pipeline_check_catalog_fn(
                    profile=args.profile,
                    output_dir=output_dir,
                ),
                indent=2,
            )
        )
        return 0
    if args.recommend_checks:
        print(
            json.dumps(
                build_pipeline_check_recommendations_fn(
                    profile=args.profile,
                    output_dir=output_dir,
                    changed_files=args.changed_file,
                ),
                indent=2,
            )
        )
        return 0
    try:
        if args.run_recommended_finish_gate:
            finish_gate = run_recommended_pipeline_finish_gate_fn(
                output_dir,
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
            print_cli_summary_fn(_build_cli_summary_payload(summary, overall_status=finish_gate["overall_status"]))
            return 1 if finish_gate["overall_status"] == "fail" else 0

        trace_target = Path(args.trace_target).resolve() if args.trace_target else None
        mutation_target = Path(args.mutation_target).resolve() if args.mutation_target else None
        baseline_findings = Path(args.baseline_findings).resolve() if args.baseline_findings else None
        corpus_manifest_dir = Path(args.corpus_manifest_dir).resolve() if args.corpus_manifest_dir else None
        save_baseline = Path(args.save_baseline).resolve() if args.save_baseline else None
        selected_checks = args.check
        if args.run_recommended_slice:
            selected_checks = build_pipeline_check_recommendations_fn(
                profile=args.profile,
                output_dir=output_dir,
                changed_files=args.changed_file,
            )["recommended_check_ids"]
        summary = run_pipeline_fn(
            output_dir,
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
            findings_src = output_dir / "findings.json"
            if findings_src.exists():
                save_baseline.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(findings_src, save_baseline)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1

    print_cli_summary_fn(_build_cli_summary_payload(summary))
    return 1 if summary["status"]["overall_status"] == "fail" else 0


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
    "build_pipeline_parser",
    "evaluate_change_scoped_coverage_proof",
    "execute_pipeline_cli",
]
