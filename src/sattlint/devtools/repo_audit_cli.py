"""CLI parser and main entrypoint for the repository audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol

from sattlint.devtools.repo_audit_cli_reporting import (
    build_check_my_changes_stdout_report as _build_check_my_changes_stdout_report,
)
from sattlint.devtools.repo_audit_cli_reporting import (
    build_planning_context_stdout_report as _build_planning_context_stdout_report,
)
from sattlint.devtools.repo_audit_cli_reporting import (
    build_recommend_checks_stdout_report as _build_recommend_checks_stdout_report,
)
from sattlint.devtools.repo_audit_cli_reporting import (
    latest_report_links as _reporting_latest_report_links,
)


class _ErrorCapableParser(Protocol):
    def error(self, message: str, /) -> None: ...


def _repo_audit_cli_module() -> Any:
    from sattlint.devtools import repo_audit as repo_audit_module  # noqa: PLC0415

    return repo_audit_module


def _repo_audit_loader() -> Any:
    repo_audit_module_loader = globals().get("_repo_audit_module")
    if callable(repo_audit_module_loader):
        return repo_audit_module_loader()
    return _repo_audit_cli_module()


def __getattr__(name: str) -> Any:
    if name == "_repo_audit_module":
        return _repo_audit_cli_module
    raise AttributeError(name)


def _latest_report_links(current_output_dir: Path) -> tuple[str | None, str | None]:
    repo_audit = _repo_audit_loader()
    return _reporting_latest_report_links(
        current_output_dir,
        default_output_dir=repo_audit.DEFAULT_OUTPUT_DIR.resolve(),
        repo_root=repo_audit.REPO_ROOT,
    )


def build_cli_parser(*, prog: str | None = None, add_help: bool = True) -> argparse.ArgumentParser:
    repo_audit = _repo_audit_loader()
    parser = argparse.ArgumentParser(
        prog=prog,
        add_help=add_help,
        description="Run repository audit checks for portability, security, wiring, architecture, and public-readiness.",
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


def _summary_findings(summary: dict[str, Any]):
    repo_audit = _repo_audit_loader()
    return (repo_audit.Finding(**finding) for finding in summary["findings"])


def _terminal_findings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return list(summary.get("findings", []))


def _selected_check_exit_code(summary: dict[str, Any], fail_on: str) -> tuple[int, dict[str, Any]]:
    repo_audit = _repo_audit_loader()
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
    repo_audit = _repo_audit_loader()
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
    repo_audit = _repo_audit_loader()
    parser = build_cli_parser()
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
