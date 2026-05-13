from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR_PARTS = ("artifacts", "audit")


def _repo_relative_text(*parts: str) -> str:
    return Path(*parts).as_posix()


def _run_pre_push_audit() -> int:
    completed = subprocess.run(  # nosec B603 - fixed Python executable and controlled arguments
        [
            sys.executable,
            "-m",
            "sattlint.devtools.repo_audit",
            "--profile",
            "full",
            "--check-my-changes",
            "--output-dir",
            _repo_relative_text(*AUDIT_DIR_PARTS),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    return int(completed.returncode)


def _refresh_dashboard() -> int:
    completed = subprocess.run(  # nosec B603 - fixed Python executable and controlled arguments
        [sys.executable, "scripts/refresh_repo_health_dashboard.py"],
        cwd=REPO_ROOT,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    audit_exit_code = _run_pre_push_audit()
    dashboard_exit_code = _refresh_dashboard()
    if dashboard_exit_code != 0:
        return dashboard_exit_code
    return audit_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
