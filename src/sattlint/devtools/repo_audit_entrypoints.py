"""Selected-check helpers for the repository audit."""

from __future__ import annotations

import json
import subprocess  # nosec
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from sattlint.contracts import FindingCollection
from sattlint.devtools import pipeline as pipeline_module
from sattlint.devtools.artifact_registry import AUDIT_ARTIFACTS, artifact_reports_map
from sattlint.devtools.pipeline_artifacts import write_json_artifact
from sattlint.devtools.pipeline_checks import matching_changed_files, normalize_changed_files, verify_check_catalog
from sattlint.devtools.progress_reporting import ProgressReporter
from sattlint.path_sanitizer import sanitize_path_for_report

REPO_AUDIT_FINDING_CHECK_IDS = (
    "text-scan",
    "documented-commands",
    "unused-config-keys",
    "architecture",
    "structural-report",
    "cli",
    "logging",
    "ai-gc",
    "ignored-repo-paths",
    "coverage",
    "public-readiness",
    "verify-recommendations",
)
REPO_AUDIT_SPECIAL_CHECK_IDS = ("cli-consistency",)
REPO_AUDIT_INDIVIDUAL_CHECK_IDS = REPO_AUDIT_FINDING_CHECK_IDS + REPO_AUDIT_SPECIAL_CHECK_IDS
REPO_AUDIT_RECOMMENDATION_FALLBACK_GLOBS = (
    "pyproject.toml",
    "src/sattlint/devtools/pipeline.py",
    "src/sattlint/devtools/pipeline_checks.py",
    "src/sattlint/devtools/repo_audit.py",
    "src/sattlint/devtools/repo_audit_cli.py",
    "src/sattlint/devtools/repo_audit_entrypoints.py",
)
AI_FEEDBACK_FILENAME = "ai_feedback.json"


def _repo_audit_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module

    return repo_audit_module


def _repo_audit_finding_check_definitions() -> tuple[dict[str, Any], ...]:
    repo_audit = _repo_audit_module()
    return (
        {
            "id": "text-scan",
            "label": "Scan repository text for leaks and local paths",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_text_scan_check,
            "owner_surface": "text-scan",
            "estimated_cost": "low",
            "path_globs": (
                "README.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "docs/**",
                ".github/**",
                "src/**/*.py",
                "tests/**/*.py",
                "scripts/**/*.py",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "documented-commands",
            "label": "Check documented commands against implemented CLI surfaces",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_documented_commands_check,
            "owner_surface": "cli-docs",
            "estimated_cost": "low",
            "path_globs": (
                "README.md",
                "CONTRIBUTING.md",
                "docs/references/cli-commands.md",
                "docs/references/ai-agent-reference.md",
                "pyproject.toml",
                "src/sattlint/cli/**",
                "src/sattlint/app*.py",
                "src/sattlint/devtools/repo_audit_cli.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "unused-config-keys",
            "label": "Report declared but unused config keys",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_unused_config_keys_check,
            "owner_surface": "config",
            "estimated_cost": "low",
            "path_globs": (
                "pyproject.toml",
                "src/sattlint/config.py",
                "src/sattlint/**/*.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "architecture",
            "label": "Run repository architecture checks",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_architecture_check,
            "owner_surface": "architecture",
            "estimated_cost": "medium",
            "path_globs": (
                "src/**",
                "tests/**",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "structural-report",
            "label": "Translate structural report findings into repo-audit findings",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_structural_report_check,
            "owner_surface": "structural",
            "estimated_cost": "medium",
            "path_globs": (
                "src/**",
                "tests/**",
                "artifacts/analysis/structural_budget_ratchet.json",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "cli",
            "label": "Validate CLI descriptions and subcommand help",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_cli_check,
            "owner_surface": "cli",
            "estimated_cost": "low",
            "path_globs": (
                "pyproject.toml",
                "src/sattlint/cli/**",
                "src/sattlint/app*.py",
                "src/sattlint/devtools/repo_audit_cli.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "logging",
            "label": "Check library modules for unexpected print calls",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_logging_check,
            "owner_surface": "logging",
            "estimated_cost": "low",
            "path_globs": ("src/**/*.py",),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "ai-gc",
            "label": "Report stale AI-generated artifacts and oversized local coordination state",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_ai_gc_check,
            "owner_surface": "ai-hygiene",
            "estimated_cost": "low",
            "path_globs": (
                "artifacts/**",
                "docs/generated/**",
                ".github/coordination/current-work.template.md",
                "src/sattlint/devtools/ai_gc.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/repo_audit_cli.py",
                "src/sattlint/devtools/repo_audit_entrypoints.py",
                "tests/test_repo_audit.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "ignored-repo-paths",
            "label": "Detect references to ignored repo-local paths",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_ignored_repo_paths_check,
            "owner_surface": "path-safety",
            "estimated_cost": "low",
            "path_globs": (
                "src/**/*.py",
                "tests/**/*.py",
                "scripts/**/*.py",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "coverage",
            "label": "Translate low-coverage modules into audit findings",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_coverage_check,
            "owner_surface": "coverage",
            "estimated_cost": "low",
            "path_globs": (
                "tests/**",
                "coverage.xml",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "public-readiness",
            "label": "Check public-repository readiness files and metadata",
            "profiles": ("quick", "full"),
            "runner": repo_audit._run_public_readiness_check,
            "owner_surface": "public-readiness",
            "estimated_cost": "low",
            "path_globs": (
                "README.md",
                "CONTRIBUTING.md",
                "SECURITY.md",
                "LICENSE",
                ".github/**",
                "docs/**",
                "pyproject.toml",
            ),
            "owner_test_targets": ("tests/test_repo_audit.py",),
        },
        {
            "id": "verify-recommendations",
            "label": "Verify recommendation metadata and routing catalog coverage",
            "profiles": ("quick", "full"),
            "runner": _run_verify_recommendations_check,
            "owner_surface": "recommendations",
            "estimated_cost": "low",
            "path_globs": (
                "src/sattlint/devtools/pipeline.py",
                "src/sattlint/devtools/pipeline_checks.py",
                "src/sattlint/devtools/repo_audit.py",
                "src/sattlint/devtools/repo_audit_cli.py",
                "src/sattlint/devtools/repo_audit_entrypoints.py",
                "tests/test_pipeline_run.py",
                "tests/test_repo_audit.py",
                "tests/test_recommendation_routing.py",
                "docs/references/cli-commands.md",
                "docs/references/ai-agent-reference.md",
            ),
            "owner_test_targets": (
                "tests/test_pipeline_run.py",
                "tests/test_repo_audit.py",
                "tests/test_recommendation_routing.py",
            ),
        },
    )


def _run_verify_recommendations_check(_context: Any) -> list[Any]:
    repo_audit = _repo_audit_module()
    output_dir = repo_audit.DEFAULT_OUTPUT_DIR
    pipeline_catalog = pipeline_module.build_pipeline_check_catalog(
        profile="full", output_dir=output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME
    )
    repo_catalog = build_repo_audit_check_catalog(profile="full", output_dir=output_dir, fail_on="high")
    reports = (
        verify_check_catalog(pipeline_catalog, repo_root=repo_audit.REPO_ROOT),
        verify_check_catalog(repo_catalog, repo_root=repo_audit.REPO_ROOT),
    )
    findings: list[Any] = []
    for report in reports:
        for issue in report["issues"]:
            findings.append(
                repo_audit.Finding(
                    id=f"recommendation-{issue['issue_id']}-{issue['check_id']}",
                    category="feature-wiring",
                    severity="high",
                    confidence="high",
                    message=issue["message"],
                    detail=json.dumps(issue, sort_keys=True),
                    source="verify-recommendations",
                )
            )
    return findings


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
) -> list[dict[str, Any]]:
    normalized_changed_files = normalize_changed_files(changed_files)
    commands: list[dict[str, Any]] = []
    finish_gate_argv = [
        "sattlint-repo-audit",
        "--profile",
        profile,
        "--run-recommended-finish-gate",
        *_changed_file_flag_args(normalized_changed_files),
        "--fail-on",
        fail_on,
        "--output-dir",
        (
            sanitize_path_for_report(output_dir.resolve(), repo_root=_repo_audit_module().REPO_ROOT)
            or output_dir.resolve().as_posix()
        ),
    ]
    commands.append(
        {
            "id": "recommended-finish-gate",
            "label": "Run the recommended repo-audit finish gate",
            "command": _shell_command(finish_gate_argv),
            "argv": finish_gate_argv,
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
    owner_test_targets = _owner_test_targets_for_checks(recommended_checks)
    if owner_test_targets:
        pytest_argv = [*python_command, "-m", "pytest", "--no-cov", *owner_test_targets, "-x", "-q", "--tb=short"]
        commands.append(
            {
                "id": "owner-pytest",
                "label": "Run owner pytest targets for the recommended checks",
                "command": _shell_command(pytest_argv),
                "argv": pytest_argv,
            }
        )
    return commands


def _build_recommendation_why_this_gate(
    *,
    changed_files: Iterable[str],
    recommended_checks: Iterable[dict[str, Any]],
    skipped_checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    normalized_changed_files = normalize_changed_files(changed_files)
    matched_routes: list[dict[str, Any]] = []
    for entry in recommended_checks:
        matched_routes.append(
            {
                "check_id": entry["id"],
                "source": entry["source"],
                "owner_surface": entry["owner_surface"],
                "matched_files": matching_changed_files(normalized_changed_files, entry["path_globs"]),
                "path_globs": entry["path_globs"],
                "reason": entry["reason"],
            }
        )
    return {
        "changed_files": normalized_changed_files,
        "matched_routes": matched_routes,
        "skipped_checks": list(skipped_checks),
    }


def _normalize_repo_audit_finding_checks(selected_checks: Iterable[str] | None) -> tuple[str, ...] | None:
    if selected_checks is None:
        return None
    supported = set(REPO_AUDIT_FINDING_CHECK_IDS)
    normalized: list[str] = []
    for raw_check in selected_checks:
        check_id = raw_check.strip()
        if not check_id:
            continue
        if check_id not in supported:
            supported_text = ", ".join(sorted(supported))
            raise ValueError(f"Unsupported repo-audit finding check: {check_id}. Supported: {supported_text}")
        if check_id not in normalized:
            normalized.append(check_id)
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
    repo_audit = _repo_audit_module()
    if profile not in repo_audit.AUDIT_PROFILE_CHOICES:
        raise ValueError(f"Unsupported audit profile: {profile}")
    resolved_output_dir = (output_dir or repo_audit.DEFAULT_OUTPUT_DIR).resolve()
    sanitized_output_dir = (
        sanitize_path_for_report(resolved_output_dir, repo_root=repo_audit.REPO_ROOT) or resolved_output_dir.as_posix()
    )
    pipeline_catalog = pipeline_module.build_pipeline_check_catalog(
        profile=profile,
        output_dir=resolved_output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME,
    )
    checks: list[dict[str, Any]] = []
    for entry in pipeline_catalog["checks"]:
        checks.append(
            {
                "id": entry["id"],
                "label": entry["label"],
                "profiles": entry["profiles"],
                "artifact_ids": entry["artifact_ids"],
                "source": "pipeline",
                "owner_surface": entry["owner_surface"],
                "estimated_cost": entry["estimated_cost"],
                "path_globs": entry["path_globs"],
                "owner_test_targets": entry["owner_test_targets"],
                "command": entry["command"],
            }
        )
    for definition in _repo_audit_finding_check_definitions():
        if profile not in tuple(definition["profiles"]):
            continue
        checks.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "profiles": list(definition["profiles"]),
                "artifact_ids": [
                    "progress",
                    "status",
                    "summary",
                    "findings",
                    "summary_markdown",
                    "run_history",
                    *(["ai_gc"] if definition["id"] == "ai-gc" else []),
                ],
                "source": "repo-audit",
                "owner_surface": definition["owner_surface"],
                "estimated_cost": definition["estimated_cost"],
                "path_globs": list(definition["path_globs"]),
                "owner_test_targets": list(definition["owner_test_targets"]),
                "command": (
                    f"sattlint-repo-audit --profile {profile} --check {definition['id']} --skip-pipeline "
                    f"--fail-on {fail_on} --output-dir {sanitized_output_dir}"
                ),
            }
        )
    if profile == "full":
        checks.append(
            {
                "id": "cli-consistency",
                "label": "Build the full CLI consistency report",
                "profiles": ["full"],
                "artifact_ids": [
                    "progress",
                    "status",
                    "summary",
                    "findings",
                    "summary_markdown",
                    "run_history",
                    "cli_consistency",
                ],
                "source": "repo-audit",
                "owner_surface": "cli-docs",
                "estimated_cost": "low",
                "path_globs": [
                    "README.md",
                    "CONTRIBUTING.md",
                    "docs/references/cli-commands.md",
                    "docs/references/ai-agent-reference.md",
                    "pyproject.toml",
                    "src/sattlint/cli/**",
                    "src/sattlint/app*.py",
                    "src/sattlint/devtools/repo_audit_cli.py",
                ],
                "owner_test_targets": ["tests/test_repo_audit.py"],
                "command": (
                    f"sattlint-repo-audit --profile full --check cli-consistency --skip-pipeline "
                    f"--fail-on {fail_on} --output-dir {sanitized_output_dir}"
                ),
            }
        )
    return {
        "kind": "sattlint.repo_audit.check_catalog",
        "schema_version": 1,
        "profile": profile,
        "fail_on": fail_on,
        "checks": checks,
    }


def build_repo_audit_check_recommendations(
    *,
    profile: str = "full",
    output_dir: Path | None = None,
    fail_on: str = "high",
    changed_files: Iterable[str] | None = None,
) -> dict[str, Any]:
    repo_audit = _repo_audit_module()
    resolved_output_dir = (output_dir or repo_audit.DEFAULT_OUTPUT_DIR).resolve()
    changed_file_list = normalize_changed_files(
        pipeline_module._detect_changed_files(repo_root=repo_audit.REPO_ROOT)
        if changed_files is None
        else changed_files
    )
    catalog = build_repo_audit_check_catalog(
        profile=profile,
        output_dir=resolved_output_dir,
        fail_on=fail_on,
    )
    fallback_required = False
    fallback_reason: str | None = None
    recommendation_reasons: dict[str, str] = {}

    if not changed_file_list:
        fallback_required = True
        fallback_reason = (
            "No changed files were provided or detected, so the full supported repo-audit profile is recommended."
        )
    elif matching_changed_files(changed_file_list, REPO_AUDIT_RECOMMENDATION_FALLBACK_GLOBS):
        fallback_required = True
        fallback_reason = "Changed files touch the repo-audit control surface, so the full supported repo-audit profile is recommended."

    if fallback_required and fallback_reason is not None:
        for entry in catalog["checks"]:
            recommendation_reasons[entry["id"]] = fallback_reason
    else:
        for entry in catalog["checks"]:
            matched_files = matching_changed_files(changed_file_list, entry["path_globs"])
            if not matched_files:
                continue
            recommendation_reasons[entry["id"]] = f"Matched {matched_files[0]} against the {entry['id']} routing globs."
        if not recommendation_reasons:
            fallback_required = True
            fallback_reason = "No audit routing globs matched the changed files, so the full supported repo-audit profile is recommended."
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

    suggested_finish_gate_commands = _build_repo_audit_finish_gate_commands(
        profile=profile,
        output_dir=resolved_output_dir,
        fail_on=fail_on,
        changed_files=changed_file_list,
        recommended_checks=recommended_checks,
        ruff_command=["ruff"],
        pyright_command=["pyright"],
        python_command=["python"],
    )

    return {
        "kind": "sattlint.repo_audit.check_recommendations",
        "schema_version": 1,
        "profile": profile,
        "fail_on": fail_on,
        "changed_files": list(changed_file_list),
        "fallback_required": fallback_required,
        "fallback_reason": fallback_reason,
        "recommended_check_ids": [entry["id"] for entry in recommended_checks],
        "recommended_pipeline_check_ids": [
            entry["id"] for entry in recommended_checks if entry["source"] == "pipeline"
        ],
        "recommended_repo_audit_check_ids": [
            entry["id"] for entry in recommended_checks if entry["source"] == "repo-audit"
        ],
        "suggested_check_commands": [entry["command"] for entry in recommended_checks],
        "suggested_finish_gate_commands": [entry["command"] for entry in suggested_finish_gate_commands],
        "recommended_checks": recommended_checks,
        "skipped_checks": skipped_checks,
        "why_this_gate": _build_recommendation_why_this_gate(
            changed_files=changed_file_list,
            recommended_checks=recommended_checks,
            skipped_checks=skipped_checks,
        ),
    }


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
    repo_audit = _repo_audit_module()
    output_dir.mkdir(parents=True, exist_ok=True)
    ai_gc_report = None
    sanitized_output_dir = sanitize_path_for_report(output_dir, repo_root=repo_audit.REPO_ROOT) or output_dir.as_posix()
    sanitized_latest_output_dir = (
        None
        if latest_output_dir is None
        else sanitize_path_for_report(latest_output_dir, repo_root=repo_audit.REPO_ROOT) or latest_output_dir.as_posix()
    )
    selected_checks = list(dict.fromkeys(check_ids))
    progress = ProgressReporter(
        kind="sattlint.repo_audit.progress",
        title="Repository audit",
        output_dir=output_dir,
        write_json=write_json_artifact,
        stages=[
            ("custom_scan", "Run repository-specific checks"),
            ("write_reports", "Write audit reports"),
        ],
        canonical_command=(
            "sattlint-repo-audit "
            f"--profile {profile} "
            f"{' '.join(f'--check {check_id}' for check_id in selected_checks)} "
            f"--skip-pipeline --fail-on {fail_on} --output-dir {sanitized_output_dir}"
        ),
    )
    progress.start_stage("custom_scan")
    findings = collect_custom_findings(
        repo_audit.REPO_ROOT,
        include_generated=include_generated,
        tracked_only=True,
        suspicious_identifiers=suspicious_identifiers,
        selected_checks=selected_checks,
    )
    progress.complete_stage("custom_scan", detail=f"{len(findings)} findings")
    blocking_count = _blocking_finding_count(findings, fail_on)
    enabled_audit_artifact_ids = {"progress", "status", "summary", "findings", "summary_markdown", "run_history"}
    if "ai-gc" in selected_checks:
        ai_gc_report = repo_audit.build_ai_gc_report(repo_audit.REPO_ROOT)
        enabled_audit_artifact_ids.add("ai_gc")
    reports = artifact_reports_map(
        AUDIT_ARTIFACTS,
        profile=profile,
        enabled_artifact_ids=enabled_audit_artifact_ids,
    )
    reports["pipeline_status"] = None
    reports["pipeline_summary"] = None
    finding_collection = FindingCollection(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if blocking_count else "pass"
    summary = {
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "output_dir": sanitized_output_dir,
        "profile": profile,
        "entry_report": "status.json",
        "canonical_command": progress.to_dict()["canonical_command"],
        "pipeline_ran": False,
        "pipeline_summary": None,
        "reports": reports,
        "finding_count": len(findings),
        "severity_counts": _severity_counts(findings),
        "category_counts": _category_counts(findings),
        "max_severity": _max_severity(findings),
        "findings_schema": finding_collection.schema_metadata,
        "history_cleanup_findings": [finding.to_dict() for finding in findings if finding.history_cleanup_recommended],
        "findings": [finding.to_dict() for finding in findings],
        "selected_checks": selected_checks,
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "profile": profile,
        "fail_on": fail_on,
        "overall_status": overall_status_value,
        "canonical_command": summary["canonical_command"],
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
        "progress_report": f"{sanitized_output_dir}/progress.json",
        "finding_count": summary["finding_count"],
        "blocking_finding_count": blocking_count,
        "max_severity": summary["max_severity"],
        "severity_counts": summary["severity_counts"],
        "category_counts": summary["category_counts"],
        "findings_schema": summary["findings_schema"],
        "pipeline_status_report": None,
        "latest_status_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/status.json",
        "latest_summary_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/summary.json",
        "top_findings": [
            {
                "id": finding.id,
                "severity": finding.severity,
                "path": finding.path,
                "line": finding.line,
                "message": finding.message,
            }
            for finding in findings[:5]
        ],
        "selected_checks": selected_checks,
    }
    progress.start_stage("write_reports")
    write_json_artifact(output_dir / "status.json", status_report)
    write_json_artifact(output_dir / "summary.json", summary)
    write_json_artifact(output_dir / "findings.json", finding_collection.to_dict())
    if ai_gc_report is not None:
        write_json_artifact(output_dir / "ai_gc.json", ai_gc_report)
    repo_audit._write_markdown(output_dir / "summary.md", findings, summary)
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit_selected_check",
        primary_payload=summary,
        status_payload=status_report,
        summary_payload=summary,
    )
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    return summary


def _run_repo_audit_cli_consistency_check(
    output_dir: Path,
    *,
    fail_on: str,
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    repo_audit = _repo_audit_module()
    output_dir.mkdir(parents=True, exist_ok=True)
    sanitized_output_dir = sanitize_path_for_report(output_dir, repo_root=repo_audit.REPO_ROOT) or output_dir.as_posix()
    sanitized_latest_output_dir = (
        None
        if latest_output_dir is None
        else sanitize_path_for_report(latest_output_dir, repo_root=repo_audit.REPO_ROOT) or latest_output_dir.as_posix()
    )
    progress = ProgressReporter(
        kind="sattlint.repo_audit.progress",
        title="Repository audit",
        output_dir=output_dir,
        write_json=write_json_artifact,
        stages=[
            ("custom_scan", "Build CLI consistency report"),
            ("write_reports", "Write audit reports"),
        ],
        canonical_command=(
            f"sattlint-repo-audit --profile full --check cli-consistency --skip-pipeline "
            f"--fail-on {fail_on} --output-dir {sanitized_output_dir}"
        ),
    )
    progress.start_stage("custom_scan")
    cli_consistency_report = repo_audit.build_cli_consistency_report(root=repo_audit.REPO_ROOT)
    findings = _cli_consistency_findings(cli_consistency_report)
    progress.complete_stage("custom_scan", detail=f"{len(findings)} findings")
    blocking_count = _blocking_finding_count(findings, fail_on)
    enabled_audit_artifact_ids = {
        "progress",
        "status",
        "summary",
        "findings",
        "summary_markdown",
        "run_history",
        "cli_consistency",
    }
    reports = artifact_reports_map(
        AUDIT_ARTIFACTS,
        profile="full",
        enabled_artifact_ids=enabled_audit_artifact_ids,
    )
    reports["pipeline_status"] = None
    reports["pipeline_summary"] = None
    finding_collection = FindingCollection(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if cli_consistency_report.get("status") == "fail" else "pass"
    summary = {
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "output_dir": sanitized_output_dir,
        "profile": "full",
        "entry_report": "status.json",
        "canonical_command": progress.to_dict()["canonical_command"],
        "pipeline_ran": False,
        "pipeline_summary": None,
        "reports": reports,
        "finding_count": len(findings),
        "severity_counts": _severity_counts(findings),
        "category_counts": _category_counts(findings),
        "max_severity": _max_severity(findings),
        "findings_schema": finding_collection.schema_metadata,
        "history_cleanup_findings": [],
        "findings": [finding.to_dict() for finding in findings],
        "selected_checks": ["cli-consistency"],
        "cli_consistency_status": cli_consistency_report.get("status"),
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "profile": "full",
        "fail_on": fail_on,
        "overall_status": overall_status_value,
        "canonical_command": summary["canonical_command"],
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
        "progress_report": f"{sanitized_output_dir}/progress.json",
        "finding_count": summary["finding_count"],
        "blocking_finding_count": blocking_count,
        "max_severity": summary["max_severity"],
        "severity_counts": summary["severity_counts"],
        "category_counts": summary["category_counts"],
        "findings_schema": summary["findings_schema"],
        "pipeline_status_report": None,
        "latest_status_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/status.json",
        "latest_summary_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/summary.json",
        "top_findings": [
            {
                "id": finding.id,
                "severity": finding.severity,
                "path": finding.path,
                "line": finding.line,
                "message": finding.message,
            }
            for finding in findings[:5]
        ],
        "selected_checks": ["cli-consistency"],
        "cli_consistency_status": cli_consistency_report.get("status"),
    }
    progress.start_stage("write_reports")
    write_json_artifact(output_dir / "status.json", status_report)
    write_json_artifact(output_dir / "summary.json", summary)
    write_json_artifact(output_dir / "findings.json", finding_collection.to_dict())
    write_json_artifact(output_dir / "cli_consistency.json", cli_consistency_report)
    repo_audit._write_markdown(output_dir / "summary.md", findings, summary)
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit_cli_consistency",
        primary_payload=summary,
        status_payload=status_report,
        summary_payload=summary,
    )
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    return summary


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
    latest_output_dir: Path | None = None,
    record_history: bool = True,
) -> dict[str, Any]:
    repo_audit = _repo_audit_module()
    output_dir.mkdir(parents=True, exist_ok=True)
    ai_gc_report = None
    resolved_changed_files = normalize_changed_files(
        pipeline_module._detect_changed_files(repo_root=repo_audit.REPO_ROOT)
        if changed_files is None
        else changed_files
    )
    recommendation = build_repo_audit_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=resolved_changed_files,
    )
    pipeline_check_ids = recommendation["recommended_pipeline_check_ids"]
    repo_check_ids = recommendation["recommended_repo_audit_check_ids"]
    repo_finding_check_ids = [check_id for check_id in repo_check_ids if check_id in REPO_AUDIT_FINDING_CHECK_IDS]
    sanitized_output_dir = sanitize_path_for_report(output_dir, repo_root=repo_audit.REPO_ROOT) or output_dir.as_posix()
    sanitized_latest_output_dir = (
        None
        if latest_output_dir is None
        else sanitize_path_for_report(latest_output_dir, repo_root=repo_audit.REPO_ROOT) or latest_output_dir.as_posix()
    )
    progress = ProgressReporter(
        kind="sattlint.repo_audit.progress",
        title="Repository audit",
        output_dir=output_dir,
        write_json=write_json_artifact,
        stages=[
            ("pipeline", "Run recommended pipeline checks"),
            ("custom_scan", "Run recommended repository-specific checks"),
            ("merge_findings", "Merge and normalize findings"),
            ("write_reports", "Write audit reports"),
        ],
        canonical_command=(
            f"sattlint-repo-audit --profile {profile} --run-recommended-slice --fail-on {fail_on} "
            f"--output-dir {sanitized_output_dir}"
        ),
    )
    pipeline_summary: dict[str, Any] | None = None
    pipeline_findings: list[Any] = []
    if pipeline_check_ids:
        pipeline_output_dir = output_dir / repo_audit.PIPELINE_OUTPUT_DIRNAME
        progress.start_stage("pipeline")
        pipeline_summary = pipeline_module._run_pipeline(
            pipeline_output_dir,
            trace_target=(
                pipeline_module.DEFAULT_TRACE_TARGET if pipeline_module.DEFAULT_TRACE_TARGET.exists() else None
            ),
            profile=profile,
            include_vulture=False if skip_vulture else None,
            include_bandit=False if skip_bandit else None,
            corpus_manifest_dir=_default_corpus_manifest_dir(),
            changed_files=list(resolved_changed_files),
            selected_checks=pipeline_check_ids,
        )
        pipeline_findings = repo_audit._find_pipeline_findings(pipeline_output_dir)
        progress.complete_stage("pipeline", detail=f"{len(pipeline_findings)} pipeline findings")
    else:
        progress.skip_stage("pipeline", detail="no pipeline checks recommended")

    progress.start_stage("custom_scan")
    custom_findings: list[Any] = []
    cli_consistency_report = None
    if repo_finding_check_ids:
        custom_findings.extend(
            collect_custom_findings(
                repo_audit.REPO_ROOT,
                include_generated=include_generated,
                tracked_only=True,
                suspicious_identifiers=suspicious_identifiers,
                selected_checks=repo_finding_check_ids,
            )
        )
    if "ai-gc" in repo_check_ids:
        ai_gc_report = repo_audit.build_ai_gc_report(repo_audit.REPO_ROOT)
    if "cli-consistency" in repo_check_ids:
        cli_consistency_report = repo_audit.build_cli_consistency_report(root=repo_audit.REPO_ROOT)
        custom_findings.extend(_cli_consistency_findings(cli_consistency_report))
    progress.complete_stage("custom_scan", detail=f"{len(custom_findings)} custom findings")

    progress.start_stage("merge_findings")
    findings = repo_audit._dedupe_findings([*pipeline_findings, *custom_findings])
    findings = sorted(
        findings,
        key=lambda item: (
            -repo_audit.SEVERITY_RANK[item.severity],
            item.category,
            item.path or "",
            item.line or 0,
            item.id,
        ),
    )
    blocking_count = _blocking_finding_count(findings, fail_on)
    enabled_audit_artifact_ids = {"progress", "status", "summary", "findings", "summary_markdown", "run_history"}
    if cli_consistency_report is not None:
        enabled_audit_artifact_ids.add("cli_consistency")
    if ai_gc_report is not None:
        enabled_audit_artifact_ids.add("ai_gc")
    reports = artifact_reports_map(
        AUDIT_ARTIFACTS,
        profile=profile,
        enabled_artifact_ids=enabled_audit_artifact_ids,
    )
    progress.complete_stage("merge_findings", detail=f"{len(findings)} total findings")
    reports["pipeline_status"] = (
        None if pipeline_summary is None else f"{repo_audit.PIPELINE_OUTPUT_DIRNAME}/status.json"
    )
    reports["pipeline_summary"] = (
        None if pipeline_summary is None else f"{repo_audit.PIPELINE_OUTPUT_DIRNAME}/summary.json"
    )
    finding_collection = FindingCollection(tuple(finding.to_record() for finding in findings))
    overall_status_value = "fail" if blocking_count else "pass"
    if cli_consistency_report is not None and cli_consistency_report.get("status") == "fail":
        overall_status_value = "fail"
    summary = {
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "output_dir": sanitized_output_dir,
        "profile": profile,
        "entry_report": "status.json",
        "canonical_command": progress.to_dict()["canonical_command"],
        "pipeline_ran": bool(pipeline_check_ids),
        "pipeline_summary": pipeline_summary,
        "reports": reports,
        "finding_count": len(findings),
        "severity_counts": _severity_counts(findings),
        "category_counts": _category_counts(findings),
        "max_severity": _max_severity(findings),
        "findings_schema": finding_collection.schema_metadata,
        "history_cleanup_findings": [finding.to_dict() for finding in findings if finding.history_cleanup_recommended],
        "findings": [finding.to_dict() for finding in findings],
        "selected_checks": recommendation["recommended_check_ids"],
        "selected_pipeline_checks": pipeline_check_ids,
        "selected_repo_audit_checks": repo_check_ids,
        "recommendation": recommendation,
        "cli_consistency_status": None if cli_consistency_report is None else cli_consistency_report.get("status"),
    }
    status_report = {
        "kind": "sattlint.repo_audit.status",
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "profile": profile,
        "fail_on": fail_on,
        "overall_status": overall_status_value,
        "canonical_command": summary["canonical_command"],
        "status_report": f"{sanitized_output_dir}/status.json",
        "summary_report": f"{sanitized_output_dir}/summary.json",
        "progress_report": f"{sanitized_output_dir}/progress.json",
        "finding_count": summary["finding_count"],
        "blocking_finding_count": blocking_count,
        "max_severity": summary["max_severity"],
        "severity_counts": summary["severity_counts"],
        "category_counts": summary["category_counts"],
        "findings_schema": summary["findings_schema"],
        "pipeline_status_report": None
        if pipeline_summary is None
        else f"{sanitized_output_dir}/{repo_audit.PIPELINE_OUTPUT_DIRNAME}/status.json",
        "latest_status_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/status.json",
        "latest_summary_report": None
        if sanitized_latest_output_dir is None
        else f"{sanitized_latest_output_dir}/summary.json",
        "top_findings": [
            {
                "id": finding.id,
                "severity": finding.severity,
                "path": finding.path,
                "line": finding.line,
                "message": finding.message,
            }
            for finding in findings[:5]
        ],
        "selected_checks": recommendation["recommended_check_ids"],
        "selected_pipeline_checks": pipeline_check_ids,
        "selected_repo_audit_checks": repo_check_ids,
        "cli_consistency_status": None if cli_consistency_report is None else cli_consistency_report.get("status"),
    }
    progress.start_stage("write_reports")
    write_json_artifact(output_dir / "status.json", status_report)
    write_json_artifact(output_dir / "summary.json", summary)
    write_json_artifact(output_dir / "findings.json", finding_collection.to_dict())
    if ai_gc_report is not None:
        write_json_artifact(output_dir / "ai_gc.json", ai_gc_report)
    repo_audit._write_markdown(output_dir / "summary.md", findings, summary)
    if cli_consistency_report is not None:
        write_json_artifact(output_dir / "cli_consistency.json", cli_consistency_report)
    if record_history:
        repo_audit._write_audit_run_history(
            output_dir,
            latest_output_dir=latest_output_dir,
            report_kind="repo_audit_recommended_slice",
            primary_payload=summary,
            status_payload=status_report,
            summary_payload=summary,
        )
    repo_audit._mirror_latest_reports(output_dir, latest_output_dir)
    progress.complete_stage("write_reports")
    progress.finalize(overall_status=overall_status_value)
    return summary


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
    latest_output_dir: Path | None = None,
) -> dict[str, Any]:
    recommendation = build_repo_audit_check_recommendations(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
    )
    summary = run_recommended_repo_audit_slice(
        output_dir,
        profile=profile,
        fail_on=fail_on,
        include_generated=include_generated,
        suspicious_identifiers=suspicious_identifiers,
        skip_vulture=skip_vulture,
        skip_bandit=skip_bandit,
        changed_files=changed_files,
        latest_output_dir=latest_output_dir,
        record_history=False,
    )
    finish_gate_steps = _build_repo_audit_finish_gate_commands(
        profile=profile,
        output_dir=output_dir,
        fail_on=fail_on,
        changed_files=recommendation["changed_files"],
        recommended_checks=recommendation["recommended_checks"],
        ruff_command=[pipeline_module._resolve_venv_tool("ruff") or "ruff"],
        pyright_command=[pipeline_module._resolve_venv_tool("pyright") or "pyright"],
        python_command=[pipeline_module._resolve_python_executable()],
    )[1:]
    step_reports: list[dict[str, Any]] = []
    finish_gate_status = "pass"
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
    finish_gate_report = {
        "kind": "sattlint.repo_audit.finish_gate",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "status": finish_gate_status,
        "commands": step_reports,
        "changed_files": recommendation["changed_files"],
        "owner_test_targets": _owner_test_targets_for_checks(recommendation["recommended_checks"]),
    }
    write_json_artifact(output_dir / "finish_gate.json", finish_gate_report)
    summary["finish_gate"] = finish_gate_report
    summary["overall_status"] = (
        "fail" if summary.get("overall_status") == "fail" or finish_gate_status == "fail" else "pass"
    )
    repo_audit = _repo_audit_module()
    repo_audit._write_audit_run_history(
        output_dir,
        latest_output_dir=latest_output_dir,
        report_kind="repo_audit_finish_gate",
        primary_payload=summary,
        status_payload=None,
        summary_payload=summary,
    )
    return summary


def _selected_surface_and_reason(recommendation: dict[str, Any]) -> tuple[str, str]:
    selected_surface = "repo-audit" if recommendation["recommended_repo_audit_check_ids"] else "pipeline"
    if selected_surface == "pipeline":
        return (
            selected_surface,
            "No repo-audit-specific checks were recommended, so the shared pipeline finish gate is sufficient.",
        )
    return (
        selected_surface,
        "Repo-audit-specific checks were recommended, so the combined repo-audit finish gate is required.",
    )


def build_check_my_changes_planning_report(
    *,
    profile: str = "full",
    output_dir: Path | None = None,
    fail_on: str = "high",
    changed_files: Iterable[str] | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import ai_work_map as ai_work_map_module

    repo_audit = _repo_audit_module()
    resolved_output_dir = (output_dir or repo_audit.DEFAULT_OUTPUT_DIR).resolve()
    sanitized_output_dir = (
        sanitize_path_for_report(resolved_output_dir, repo_root=repo_audit.REPO_ROOT) or resolved_output_dir.as_posix()
    )
    recommendation = build_repo_audit_check_recommendations(
        profile=profile,
        output_dir=resolved_output_dir,
        fail_on=fail_on,
        changed_files=changed_files,
    )
    selected_surface, selected_reason = _selected_surface_and_reason(recommendation)
    planning_context = ai_work_map_module.build_planning_context(
        changed_files=recommendation["changed_files"],
        recommended_check_ids=recommendation["recommended_check_ids"],
        selected_surface=selected_surface,
    )
    return {
        "kind": "sattlint.planning_context",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "profile": profile,
        "fail_on": fail_on,
        "output_dir": sanitized_output_dir,
        "changed_files": recommendation["changed_files"],
        "selected_surface": selected_surface,
        "selected_reason": selected_reason,
        "planning_context": planning_context,
        "recommendation": {
            "fallback_required": recommendation["fallback_required"],
            "fallback_reason": recommendation["fallback_reason"],
            "recommended_check_ids": recommendation["recommended_check_ids"],
            "recommended_pipeline_check_ids": recommendation["recommended_pipeline_check_ids"],
            "recommended_repo_audit_check_ids": recommendation["recommended_repo_audit_check_ids"],
        },
    }


def _first_failed_finish_gate_step(finish_gate_report: dict[str, Any]) -> dict[str, Any] | None:
    for step in finish_gate_report.get("commands", []):
        if not isinstance(step, dict) or step.get("status") != "fail":
            continue
        return {
            "id": str(step.get("id", "")),
            "label": str(step.get("label", "")),
            "command": str(step.get("command", "")),
            "exit_code": step.get("exit_code"),
        }
    return None


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
    instruction_names = [
        str(item.get("name", ""))
        for item in planning_context.get("instruction_files", [])
        if isinstance(item, dict) and item.get("name")
    ]
    first_validation_commands = [
        str(command) for command in planning_context.get("first_validation_commands", []) if str(command).strip()
    ]
    first_failed_step = _first_failed_finish_gate_step(selected_result.get("finish_gate", {}))
    suggested_next_command = (
        str(first_failed_step.get("command", ""))
        if first_failed_step is not None and str(first_failed_step.get("command", "")).strip()
        else (first_validation_commands[0] if first_validation_commands else selected_command)
    )
    return {
        "kind": "sattlint.ai_feedback",
        "schema_version": 1,
        "generated_by": "sattlint.devtools.repo_audit_entrypoints",
        "changed_files": changed_files,
        "selected_surface": selected_surface,
        "selected_reason": selected_reason,
        "selected_command": selected_command,
        "overall_status": overall_status,
        "finish_gate_status": finish_gate_status,
        "primary_agent": planning_context.get("primary_agent"),
        "instruction_names": instruction_names[:3],
        "owner_test_targets": list(planning_context.get("owner_test_targets", []))[:3],
        "first_validation_commands": first_validation_commands[:3],
        "recommended_check_ids": list(recommendation.get("recommended_check_ids", [])),
        "recommended_pipeline_check_ids": list(recommendation.get("recommended_pipeline_check_ids", [])),
        "recommended_repo_audit_check_ids": list(recommendation.get("recommended_repo_audit_check_ids", [])),
        "first_failed_step": first_failed_step,
        "suggested_next_command": suggested_next_command,
        "reports": reports,
    }


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
        selected_result = run_recommended_repo_audit_finish_gate(
            output_dir,
            profile=profile,
            fail_on=fail_on,
            include_generated=include_generated,
            suspicious_identifiers=suspicious_identifiers,
            skip_vulture=skip_vulture,
            skip_bandit=skip_bandit,
            changed_files=resolved_changed_files,
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
