from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_repo_health() -> int:
    completed = subprocess.run(  # nosec B603 - fixed Python executable and controlled arguments
        [
            sys.executable,
            "scripts/repo_health.py",
            "--audit-dir",
            "artifacts/audit",
            "--json-output",
            "artifacts/health/repo-health.json",
            "--markdown-output",
            "docs/generated/repo-health.md",
            "--html-output",
            "artifacts/health/repo-health.html",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    return _run_repo_health()


if __name__ == "__main__":
    raise SystemExit(main())
