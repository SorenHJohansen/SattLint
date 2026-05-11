"""CLI parser and main entrypoint for the repository audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol, TypeGuard, cast

from sattlint.path_sanitizer import sanitize_path_for_report

_MAX_STDOUT_CHANGED_FILE_PREVIEW = 12
_MAX_STDOUT_ITEM_PREVIEW = 8
_MAX_STDOUT_COMMAND_LENGTH = 220
_STDOUT_COMMAND_HEAD_LENGTH = 160
_STDOUT_COMMAND_TAIL_LENGTH = 40


class _ErrorCapableParser(Protocol):
    def error(self, message: str, /) -> None: ...


def _is_string_object_mapping(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def _repo_audit_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module

    return repo_audit_module


def _build_cli_parser() -> argparse.ArgumentParser:
    repo_audit = _repo_audit_module()
    parser = argparse.ArgumentParser(
        description="Run repository audit checks for portability, security, wiring, architecture, and public-readiness."
    )
    parser.add_argument(
        "--output-dir",
        default=str(repo_audit.DEFAULT_OUTPUT_DIR),
        help="Directory where audit reports will be written",
    )
    parser.add_argument(
        "--profile",
        choices=repo_audit.AUDIT_PROFILE_CHOICES,
        default="full",
        help="Run the fast quick profile or the complete full profile",
    )
    parser.add_argument(
        "--fail-on",
        choices=("critical", "high", "medium", "low"),
        default=None,
        help="Exit non-zero when findings at or above this severity exist",
    )
    parser.add_argument(
        "--leaks-only",
        action="store_true",
        help="Only report repository leak findings such as hardcoded paths, identifiers, emails, and tracked generated artifacts",
    )
    parser.add_argument(
        "--suspicious-identifier",
        action="append",
        default=[],
        help="Additional username, hostname, or developer-specific token to flag",
    )
    parser.add_argument(
        "--include-generated",
        action="store_true",
        help="Include generated artifacts such as artifacts/analysis in custom scans",
    )
    parser.add_argument(
        "--check",
        action="append",
        choices=repo_audit.REPO_AUDIT_INDIVIDUAL_CHECK_IDS,
        default=None,
        help="Run only the named repo-audit-specific check. Repeatable for finding-backed checks.",
    )
    parser.add_argument(
        "--list-checks",
        action="store_true",
        help="Print the individually runnable full repo-audit checks as JSON and exit.",
    )
    parser.add_argument(
        "--changed-file",
        action="append",
        default=None,
        help="Repo-relative changed file path used for recommendation and slice routing. Repeatable.",
    )
    parser.add_argument(
        "--pytest-workers",
        default=None,
        help="Optional pytest-xdist worker setting forwarded as '-n <value>' to recommended pipeline and finish-gate pytest runs.",
    )
    parser.add_argument(
        "--recommend-checks",
        action="store_true",
        help="Print machine-readable recommended repo-audit checks for the changed files and exit.",
    )
    parser.add_argument(
        "--run-recommended-slice",
        action="store_true",
        help="Run the recommended repo-audit slice for the changed files instead of the full selected profile.",
    )
    parser.add_argument(
        "--run-recommended-finish-gate",
        action="store_true",
        help="Run the recommended repo-audit slice plus focused touched-file Ruff, Pyright, and owner pytest commands.",
    )
    parser.add_argument(
        "--check-my-changes",
        action="store_true",
        help="Auto-select the right finish gate for the current change set and print one machine-readable result.",
    )
    parser.add_argument(
        "--planning-context",
        action="store_true",
        help="Print the full machine-readable planning report for the current or explicit changed files and exit.",
    )
    parser.add_argument(
        "--apply-ai-gc",
        action="store_true",
        help="Delete safe stale AI-generated artifacts and compact the local coordination ledger, then write ai_gc.json.",
    )
    parser.add_argument(
        "--skip-pipeline", action="store_true", help="Skip the existing lint/type/test/security pipeline"
    )
    parser.add_argument("--skip-vulture", action="store_true", help="Skip Vulture inside the shared pipeline")
    parser.add_argument("--skip-bandit", action="store_true", help="Skip Bandit inside the shared pipeline")
    return parser


def _check_mode_conflicts(args: argparse.Namespace, parser: _ErrorCapableParser) -> None:
    if args.check and (args.recommend_checks or args.run_recommended_slice or args.run_recommended_finish_gate):
        parser.error("--check cannot be combined with --recommend-checks or --run-recommended-slice.")
    if args.leaks_only and (args.recommend_checks or args.run_recommended_slice or args.run_recommended_finish_gate):
        parser.error("--leaks-only cannot be combined with --recommend-checks or --run-recommended-slice.")
    if args.check_my_changes and (
        args.check
        or args.list_checks
        or args.recommend_checks
        or args.run_recommended_slice
        or args.run_recommended_finish_gate
        or args.leaks_only
    ):
        parser.error("--check-my-changes must be run on its own.")
    if args.planning_context and (
        args.check
        or args.list_checks
        or args.recommend_checks
        or args.run_recommended_slice
        or args.run_recommended_finish_gate
        or args.check_my_changes
        or args.leaks_only
        or args.apply_ai_gc
    ):
        parser.error("--planning-context must be run on its own.")
    if args.apply_ai_gc and (
        args.check
        or args.list_checks
        or args.recommend_checks
        or args.run_recommended_slice
        or args.run_recommended_finish_gate
        or args.check_my_changes
    ):
        parser.error("--apply-ai-gc must be run on its own.")


def _latest_report_links(current_output_dir: Path) -> tuple[str | None, str | None]:
    repo_audit = _repo_audit_module()
    default_output_dir = repo_audit.DEFAULT_OUTPUT_DIR.resolve()
    if current_output_dir == default_output_dir:
        return None, None
    sanitized = (
        sanitize_path_for_report(default_output_dir, repo_root=repo_audit.REPO_ROOT) or default_output_dir.as_posix()
    )
    return f"{sanitized}/status.json", f"{sanitized}/summary.json"


def _compact_command(command: object) -> tuple[str | None, bool]:
    text = str(command or "").strip()
    if not text:
        return None, False
    if len(text) <= _MAX_STDOUT_COMMAND_LENGTH:
        return text, False
    head = text[:_STDOUT_COMMAND_HEAD_LENGTH].rstrip()
    tail = text[-_STDOUT_COMMAND_TAIL_LENGTH:].lstrip()
    return f"{head} ... {tail}", True


def _changed_file_preview(changed_files: object) -> dict[str, Any]:
    paths = [str(item) for item in cast(list[object], changed_files)] if isinstance(changed_files, list) else []
    preview = paths[:_MAX_STDOUT_CHANGED_FILE_PREVIEW]
    return {
        "preview": preview,
        "count": len(paths),
        "truncated": len(paths) > len(preview),
        "overflow_count": max(0, len(paths) - len(preview)),
    }


def _string_list_preview(items: object, *, max_items: int = _MAX_STDOUT_ITEM_PREVIEW) -> dict[str, Any]:
    values = [str(item) for item in cast(list[object], items)] if isinstance(items, list) else []
    preview = values[:max_items]
    return {
        "preview": preview,
        "count": len(values),
        "truncated": len(values) > len(preview),
        "overflow_count": max(0, len(values) - len(preview)),
    }


def _compact_command_list(commands: object, *, max_items: int = _MAX_STDOUT_ITEM_PREVIEW) -> dict[str, Any]:
    values = cast(list[object], commands) if isinstance(commands, list) else []
    preview: list[str] = []
    truncated_command_count = 0
    for command in values[:max_items]:
        compacted, was_truncated = _compact_command(command)
        if compacted is None:
            continue
        preview.append(compacted)
        if was_truncated:
            truncated_command_count += 1
    return {
        "preview": preview,
        "count": len(values),
        "truncated": len(values) > len(preview),
        "overflow_count": max(0, len(values) - len(preview)),
        "truncated_command_count": truncated_command_count,
    }


def _apply_preview_fields(payload: dict[str, Any], key: str, preview: dict[str, Any]) -> None:
    payload[key] = preview["preview"]
    payload[f"{key[:-1]}_count" if key.endswith("s") else f"{key}_count"] = preview["count"]
    if preview["truncated"]:
        payload[f"{key}_truncated"] = True
        payload[f"{key}_overflow_count"] = preview["overflow_count"]


def _compact_instruction_names(planning_context: dict[str, Any]) -> list[str]:
    instruction_files = planning_context.get("instruction_files")
    if not isinstance(instruction_files, list):
        return []
    instruction_file_items = list(cast(list[object], instruction_files))
    names: list[str] = []
    for item in instruction_file_items:
        if not _is_string_object_mapping(item):
            continue
        name = item.get("name")
        if name is not None:
            names.append(str(name))
    return names


def _compact_blocking_invariants(planning_context: dict[str, Any]) -> list[dict[str, str]]:
    invariants = planning_context.get("blocking_invariants")
    if not isinstance(invariants, list):
        return []
    invariant_items = list(cast(list[object], invariants))
    compacted: list[dict[str, str]] = []
    for item in invariant_items[:_MAX_STDOUT_ITEM_PREVIEW]:
        if not _is_string_object_mapping(item):
            continue
        entry: dict[str, str] = {}
        for key in ("id", "summary"):
            value = item.get(key)
            if value is not None:
                entry[key] = str(value)
        if entry:
            compacted.append(entry)
    return compacted


def _compact_finish_gate(finish_gate: object) -> dict[str, Any] | None:
    if not isinstance(finish_gate, dict):
        return None
    finish_gate_dict = cast(dict[str, object], finish_gate)
    payload: dict[str, Any] = {}
    for key in ("selected_surface", "output_dir", "description"):
        value = finish_gate_dict.get(key)
        if value is not None:
            payload[key] = value
    command, command_truncated = _compact_command(finish_gate_dict.get("command"))
    if command is not None:
        payload["command"] = command
    if command_truncated:
        payload["command_truncated"] = True
    for key in ("commands", "owner_test_targets", "recommended_check_ids", "includes"):
        preview = (
            _compact_command_list(finish_gate_dict.get(key))
            if key == "commands"
            else _string_list_preview(finish_gate_dict.get(key))
        )
        if preview["count"] == 0 and not preview["preview"]:
            continue
        _apply_preview_fields(payload, key, preview)
        if key == "commands" and preview["truncated_command_count"]:
            payload["commands_with_truncated_text"] = preview["truncated_command_count"]
    return payload


def _compact_proof_requirements(proof_requirements: object) -> dict[str, Any] | None:
    if not isinstance(proof_requirements, dict):
        return None
    requirements = cast(dict[str, object], proof_requirements)
    payload: dict[str, Any] = {}
    for section_name in ("focused_behavior_test", "coverage", "mutation_guidance"):
        section = requirements.get(section_name)
        if not isinstance(section, dict):
            continue
        section_dict = cast(dict[str, object], section)
        compacted: dict[str, Any] = {}
        for key in ("required", "status", "reason", "preferred_mode", "fallback_mode", "suggestion"):
            value = section_dict.get(key)
            if value is not None:
                compacted[key] = value
        for key in ("owner_test_targets", "critical_surfaces", "suggested_commands", "touched_source_files"):
            if key not in section_dict:
                continue
            preview = (
                _compact_command_list(section_dict.get(key))
                if key == "suggested_commands"
                else _string_list_preview(section_dict.get(key))
            )
            if preview["count"] == 0 and not preview["preview"]:
                continue
            _apply_preview_fields(compacted, key, preview)
            if key == "suggested_commands" and preview["truncated_command_count"]:
                compacted["suggested_commands_with_truncated_text"] = preview["truncated_command_count"]
        if compacted:
            payload[section_name] = compacted
    return payload


def _build_recommend_checks_stdout_report(report: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "kind",
        "schema_version",
        "profile",
        "fail_on",
        "fallback_required",
        "fallback_reason",
        "recommended_check_ids",
        "recommended_pipeline_check_ids",
        "recommended_repo_audit_check_ids",
    ):
        value = report.get(key)
        if value is not None:
            payload[key] = value

    if "changed_files" in report:
        _apply_preview_fields(payload, "changed_files", _changed_file_preview(report.get("changed_files")))

    for key in ("suggested_check_commands", "suggested_finish_gate_commands"):
        if key not in report:
            continue
        preview = _compact_command_list(report.get(key))
        if preview["count"] == 0 and not preview["preview"]:
            continue
        _apply_preview_fields(payload, key, preview)
        if preview["truncated_command_count"]:
            payload[f"{key}_with_truncated_text"] = preview["truncated_command_count"]

    proof_requirements = _compact_proof_requirements(report.get("proof_requirements"))
    if proof_requirements is not None:
        payload["proof_requirements"] = proof_requirements

    return payload


def _build_planning_context_stdout_report(report: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "kind",
        "schema_version",
        "generated_by",
        "default_entrypoint",
        "profile",
        "fail_on",
        "output_dir",
        "owning_surface",
        "selected_surface",
        "selected_reason",
    ):
        value = report.get(key)
        if value is not None:
            payload[key] = value

    if "changed_files" in report:
        _apply_preview_fields(payload, "changed_files", _changed_file_preview(report.get("changed_files")))

    recommendation = report.get("recommendation") if isinstance(report.get("recommendation"), dict) else None
    if recommendation is not None:
        compacted_recommendation: dict[str, Any] = {}
        for key in (
            "fallback_required",
            "fallback_reason",
            "recommended_check_ids",
            "recommended_pipeline_check_ids",
            "recommended_repo_audit_check_ids",
        ):
            value = recommendation.get(key)
            if value is not None:
                compacted_recommendation[key] = value
        if compacted_recommendation:
            payload["recommendation"] = compacted_recommendation

    proof_requirements = _compact_proof_requirements(report.get("proof_requirements"))
    if proof_requirements is not None:
        payload["proof_requirements"] = proof_requirements

    planning_context = report.get("planning_context") if isinstance(report.get("planning_context"), dict) else None
    if planning_context is not None:
        compacted_context: dict[str, Any] = {}
        for key in ("primary_agent",):
            value = planning_context.get(key)
            if value is not None:
                compacted_context[key] = value
        for key in ("owner_surfaces", "owner_test_targets", "first_validation_commands"):
            if key not in planning_context:
                continue
            preview = (
                _compact_command_list(planning_context.get(key))
                if key == "first_validation_commands"
                else _string_list_preview(planning_context.get(key))
            )
            if preview["count"] == 0 and not preview["preview"]:
                continue
            _apply_preview_fields(compacted_context, key, preview)
            if key == "first_validation_commands" and preview["truncated_command_count"]:
                compacted_context["first_validation_commands_with_truncated_text"] = preview["truncated_command_count"]

        instruction_names = _compact_instruction_names(planning_context)
        if instruction_names:
            _apply_preview_fields(compacted_context, "instruction_names", _string_list_preview(instruction_names))

        blocking_invariants = _compact_blocking_invariants(planning_context)
        if blocking_invariants:
            compacted_context["blocking_invariants"] = blocking_invariants
            if isinstance(planning_context.get("blocking_invariants"), list) and len(
                planning_context["blocking_invariants"]
            ) > len(blocking_invariants):
                compacted_context["blocking_invariants_truncated"] = True

        finish_gate = _compact_finish_gate(planning_context.get("finish_gate"))
        if finish_gate is not None:
            compacted_context["finish_gate"] = finish_gate

        if compacted_context:
            payload["planning_context"] = compacted_context

    finish_gate = _compact_finish_gate(report.get("finish_gate"))
    if finish_gate is not None:
        payload["finish_gate"] = finish_gate

    return payload


def _compact_failed_step(step: object) -> dict[str, Any] | None:
    if not isinstance(step, dict):
        return None
    step_dict = cast(dict[str, object], step)
    payload: dict[str, object] = {
        "id": step_dict.get("id"),
        "label": step_dict.get("label"),
        "exit_code": step_dict.get("exit_code"),
    }
    command, truncated = _compact_command(step_dict.get("command"))
    if command is not None:
        payload["command"] = command
    if truncated:
        payload["command_truncated"] = True
    return payload


def _build_check_my_changes_stdout_report(report: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in (
        "kind",
        "schema_version",
        "generated_by",
        "profile",
        "fail_on",
        "output_dir",
        "report_path",
        "selected_surface",
        "selected_reason",
        "overall_status",
        "finish_gate_status",
        "reports",
    ):
        value = report.get(key)
        if value is not None:
            payload[key] = value

    if "changed_files" in report:
        changed_files = _changed_file_preview(report.get("changed_files"))
        payload["changed_files"] = changed_files["preview"]
        payload["changed_file_count"] = changed_files["count"]
        if changed_files["truncated"]:
            payload["changed_files_truncated"] = True
            payload["changed_file_overflow_count"] = changed_files["overflow_count"]

    selected_command, selected_command_truncated = _compact_command(report.get("selected_command"))
    if selected_command is not None:
        payload["selected_command"] = selected_command
    if selected_command_truncated:
        payload["selected_command_truncated"] = True

    recommendation = report.get("recommendation") if isinstance(report.get("recommendation"), dict) else None
    if recommendation is not None:
        recommended_check_ids = recommendation.get("recommended_check_ids")
        if isinstance(recommended_check_ids, list):
            payload["recommended_check_ids"] = recommended_check_ids

    ai_feedback = report.get("ai_feedback") if isinstance(report.get("ai_feedback"), dict) else None
    if ai_feedback is not None:
        first_failed_step = _compact_failed_step(ai_feedback.get("first_failed_step"))
        if first_failed_step is not None:
            payload["first_failed_step"] = first_failed_step

        suggested_next_command, suggested_next_command_truncated = _compact_command(
            ai_feedback.get("suggested_next_command")
        )
        if suggested_next_command is not None:
            payload["suggested_next_command"] = suggested_next_command
        if suggested_next_command_truncated:
            payload["suggested_next_command_truncated"] = True

    return payload


def _summary_findings(summary: dict[str, Any]):
    repo_audit = _repo_audit_module()
    return (repo_audit.Finding(**finding) for finding in summary["findings"])


def _terminal_findings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return list(summary.get("findings", []))


def _selected_check_exit_code(summary: dict[str, Any], fail_on: str) -> tuple[int, dict[str, Any]]:
    repo_audit = _repo_audit_module()
    selected_findings = _summary_findings(summary)
    selected_status = (
        "fail"
        if summary.get("cli_consistency_status") == "fail" or repo_audit._should_fail(selected_findings, fail_on)
        else "pass"
    )
    output_dir = Path(summary["output_dir"]).resolve()
    latest_status_report, latest_summary_report = _latest_report_links(output_dir)
    status_report = {
        "profile": summary["profile"],
        "overall_status": selected_status,
        "findings_schema": summary.get("findings_schema"),
        "finding_count": summary["finding_count"],
        "findings": _terminal_findings(summary),
        "blocking_finding_count": repo_audit._blocking_finding_count(_summary_findings(summary), fail_on),
        "fail_on": fail_on,
        "status_report": f"{summary['output_dir']}/status.json",
        "summary_report": f"{summary['output_dir']}/summary.json",
        "latest_status_report": latest_status_report,
        "latest_summary_report": latest_summary_report,
    }
    return (1 if selected_status == "fail" else 0), status_report


def _run_selected_checks(args: argparse.Namespace, fail_on: str) -> tuple[int, dict[str, Any]]:
    repo_audit = _repo_audit_module()
    selected_checks = tuple(dict.fromkeys(args.check))
    output_dir = Path(args.output_dir).resolve()
    latest_output_dir = repo_audit.DEFAULT_OUTPUT_DIR.resolve()
    if "cli-consistency" in selected_checks:
        if len(selected_checks) != 1:
            raise ValueError("cli-consistency must be run alone.")
        summary = repo_audit._run_repo_audit_cli_consistency_check(
            output_dir,
            fail_on=fail_on,
            latest_output_dir=latest_output_dir,
        )
    else:
        summary = repo_audit._run_repo_audit_findings_checks(
            output_dir,
            profile=args.profile,
            check_ids=selected_checks,
            fail_on=fail_on,
            include_generated=args.include_generated,
            suspicious_identifiers=list(args.suspicious_identifier),
            latest_output_dir=latest_output_dir,
        )
    return _selected_check_exit_code(summary, fail_on)


def main(argv: list[str] | None = None) -> int:
    repo_audit = _repo_audit_module()
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    _check_mode_conflicts(args, parser)
    fail_on = args.fail_on or ("medium" if args.leaks_only else "high")
    if args.list_checks:
        print(
            json.dumps(
                repo_audit.build_repo_audit_check_catalog(
                    profile=args.profile,
                    output_dir=Path(args.output_dir).resolve(),
                    fail_on=fail_on,
                ),
                indent=2,
            )
        )
        return 0
    if args.recommend_checks:
        report = repo_audit.build_repo_audit_check_recommendations(
            profile=args.profile,
            output_dir=Path(args.output_dir).resolve(),
            fail_on=fail_on,
            changed_files=args.changed_file,
        )
        print(json.dumps(_build_recommend_checks_stdout_report(report), indent=2))
        return 0
    if args.apply_ai_gc:
        report = repo_audit.apply_ai_gc(
            output_dir=Path(args.output_dir).resolve(),
        )
        print(json.dumps(report, indent=2))
        return 1 if report["summary"]["failure_count"] else 0
    if args.planning_context:
        report = repo_audit._repo_audit_entrypoints.build_check_my_changes_planning_report(
            profile=args.profile,
            output_dir=Path(args.output_dir).resolve(),
            fail_on=fail_on,
            changed_files=args.changed_file,
        )
        print(json.dumps(_build_planning_context_stdout_report(report), indent=2))
        return 0
    if args.check_my_changes:
        report = repo_audit.run_check_my_changes(
            Path(args.output_dir).resolve(),
            profile=args.profile,
            fail_on=fail_on,
            include_generated=args.include_generated,
            suspicious_identifiers=list(args.suspicious_identifier),
            skip_vulture=args.skip_vulture,
            skip_bandit=args.skip_bandit,
            changed_files=args.changed_file,
            pytest_workers=args.pytest_workers,
            latest_output_dir=repo_audit.DEFAULT_OUTPUT_DIR.resolve(),
        )
        print(json.dumps(_build_check_my_changes_stdout_report(report), indent=2))
        return 1 if report["overall_status"] == "fail" else 0
    if args.check:
        exit_code, status_report = _run_selected_checks(args, fail_on)
        repo_audit._print_cli_summary(status_report)
        return exit_code
    if args.run_recommended_slice:
        summary = repo_audit.run_recommended_repo_audit_slice(
            Path(args.output_dir).resolve(),
            profile=args.profile,
            fail_on=fail_on,
            include_generated=args.include_generated,
            suspicious_identifiers=list(args.suspicious_identifier),
            skip_vulture=args.skip_vulture,
            skip_bandit=args.skip_bandit,
            changed_files=args.changed_file,
            pytest_workers=args.pytest_workers,
            latest_output_dir=repo_audit.DEFAULT_OUTPUT_DIR.resolve(),
        )
        exit_code, status_report = _selected_check_exit_code(summary, fail_on)
        repo_audit._print_cli_summary(status_report)
        return exit_code
    if args.run_recommended_finish_gate:
        summary = repo_audit.run_recommended_repo_audit_finish_gate(
            Path(args.output_dir).resolve(),
            profile=args.profile,
            fail_on=fail_on,
            include_generated=args.include_generated,
            suspicious_identifiers=list(args.suspicious_identifier),
            skip_vulture=args.skip_vulture,
            skip_bandit=args.skip_bandit,
            changed_files=args.changed_file,
            pytest_workers=args.pytest_workers,
            latest_output_dir=repo_audit.DEFAULT_OUTPUT_DIR.resolve(),
        )
        exit_code, status_report = _selected_check_exit_code(summary, fail_on)
        if summary.get("finish_gate", {}).get("status") == "fail":
            exit_code = 1
            status_report["overall_status"] = "fail"
        repo_audit._print_cli_summary(status_report)
        return exit_code
    summary = repo_audit.audit_repository(
        Path(args.output_dir).resolve(),
        profile=args.profile,
        fail_on=fail_on,
        include_generated=args.include_generated,
        leaks_only=args.leaks_only,
        suspicious_identifiers=list(args.suspicious_identifier),
        skip_pipeline=args.skip_pipeline,
        skip_vulture=args.skip_vulture,
        skip_bandit=args.skip_bandit,
        latest_output_dir=repo_audit.DEFAULT_OUTPUT_DIR.resolve(),
    )
    latest_status_report, latest_summary_report = _latest_report_links(Path(args.output_dir).resolve())
    repo_audit._print_cli_summary(
        {
            "profile": summary["profile"],
            "overall_status": "fail" if repo_audit._should_fail(_summary_findings(summary), fail_on) else "pass",
            "findings_schema": summary.get("findings_schema"),
            "finding_count": summary["finding_count"],
            "findings": _terminal_findings(summary),
            "blocking_finding_count": repo_audit._blocking_finding_count(_summary_findings(summary), fail_on),
            "fail_on": fail_on,
            "status_report": f"{summary['output_dir']}/status.json",
            "summary_report": f"{summary['output_dir']}/summary.json",
            "latest_status_report": latest_status_report,
            "latest_summary_report": latest_summary_report,
        }
    )
    return 1 if repo_audit._should_fail(_summary_findings(summary), fail_on) else 0


__all__ = ["main"]
