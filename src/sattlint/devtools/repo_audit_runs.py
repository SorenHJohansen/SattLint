"""Stage repo-audit runs in a temporary directory and publish only complete results."""

from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sattlint.devtools import repo_audit_cli
from sattlint.devtools.artifact_readiness import ReadinessError, assert_artifact_dir_ready


@dataclass(frozen=True, slots=True)
class RepoAuditRunResult:
    final_output_dir: Path
    staged_output_dir: Path
    archived_output_dir: Path | None
    readiness_report: dict[str, object]
    audit_exit_code: int


UNSUPPORTED_FORWARD_FLAGS = (
    "--apply-ai-gc",
    "--check",
    "--check-my-changes",
    "--list-checks",
    "--planning-context",
    "--recommend-checks",
    "--run-recommended-finish-gate",
    "--run-recommended-slice",
)


def _contains_flag(arguments: list[str], flag: str) -> bool:
    return any(argument == flag or argument.startswith(f"{flag}=") for argument in arguments)


def _timestamp_label() -> str:
    return time.strftime("%Y%m%dT%H%M%S", time.gmtime())


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    counter = 1
    while True:
        candidate = path.with_name(f"{path.name}-{counter}")
        if not candidate.exists():
            return candidate
        counter += 1


def build_staging_output_dir(final_output_dir: Path) -> Path:
    parent = final_output_dir.resolve().parent
    parent.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{final_output_dir.name}.tmp-", dir=parent))


def _archive_existing_output(final_output_dir: Path, keep_history_dir: Path | None) -> tuple[Path | None, bool]:
    if not final_output_dir.exists():
        return None, False
    timestamp = _timestamp_label()
    if keep_history_dir is not None:
        keep_history_dir.mkdir(parents=True, exist_ok=True)
        archived_path = _unique_path(keep_history_dir / f"{final_output_dir.name}-{timestamp}")
        final_output_dir.rename(archived_path)
        return archived_path, True
    backup_path = _unique_path(final_output_dir.with_name(f"{final_output_dir.name}.previous-{timestamp}"))
    final_output_dir.rename(backup_path)
    return backup_path, True


def publish_completed_run(
    staged_output_dir: Path,
    final_output_dir: Path,
    *,
    keep_history_dir: Path | None = None,
) -> Path | None:
    archived_output_dir, restore_available = _archive_existing_output(final_output_dir, keep_history_dir)
    try:
        staged_output_dir.rename(final_output_dir)
    except BaseException:
        if restore_available and archived_output_dir is not None and not final_output_dir.exists():
            archived_output_dir.rename(final_output_dir)
        raise
    if keep_history_dir is None and archived_output_dir is not None:
        try:
            shutil.rmtree(archived_output_dir)
        except OSError:
            return archived_output_dir
        return None
    return archived_output_dir


def _forwarded_repo_audit_args(forwarded_args: list[str], staged_output_dir: Path) -> list[str]:
    if _contains_flag(forwarded_args, "--output-dir"):
        raise ValueError("repo_audit_runs controls --output-dir; use --final-output-dir instead.")
    for flag in UNSUPPORTED_FORWARD_FLAGS:
        if _contains_flag(forwarded_args, flag):
            raise ValueError(f"repo_audit_runs does not support forwarding {flag}.")
    return [*forwarded_args, "--output-dir", str(staged_output_dir)]


def run_staged_repo_audit(
    *,
    final_output_dir: Path,
    forwarded_args: list[str],
    keep_history_dir: Path | None = None,
    audit_main: Callable[[list[str] | None], int] = repo_audit_cli.main,
    readiness_check: Callable[[Path], dict[str, object]] = assert_artifact_dir_ready,
) -> RepoAuditRunResult:
    staged_output_dir = build_staging_output_dir(final_output_dir)
    audit_exit_code = audit_main(_forwarded_repo_audit_args(forwarded_args, staged_output_dir))
    readiness_report = readiness_check(staged_output_dir)
    archived_output_dir = publish_completed_run(
        staged_output_dir,
        final_output_dir.resolve(),
        keep_history_dir=None if keep_history_dir is None else keep_history_dir.resolve(),
    )
    return RepoAuditRunResult(
        final_output_dir=final_output_dir.resolve(),
        staged_output_dir=staged_output_dir,
        archived_output_dir=archived_output_dir,
        readiness_report=readiness_report,
        audit_exit_code=audit_exit_code,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run repo-audit in a temporary sibling directory and publish only complete results."
    )
    parser.add_argument("--final-output-dir", required=True, help="Final published audit directory")
    parser.add_argument(
        "--keep-history",
        default=None,
        help="Optional directory where the previous published audit directory will be archived before replacement.",
    )
    args, forwarded_args = parser.parse_known_args(argv)
    final_output_dir = Path(args.final_output_dir)
    keep_history_dir = None if args.keep_history is None else Path(args.keep_history)
    try:
        result = run_staged_repo_audit(
            final_output_dir=final_output_dir,
            forwarded_args=forwarded_args,
            keep_history_dir=keep_history_dir,
        )
    except (ReadinessError, ValueError) as error:
        print(str(error))
        return 1
    print(f"Published completed audit to {result.final_output_dir.as_posix()}")
    if result.archived_output_dir is not None:
        print(f"Archived previous audit at {result.archived_output_dir.as_posix()}")
    return result.audit_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
