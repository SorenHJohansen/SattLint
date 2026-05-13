from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR_PARTS = ("artifacts", "audit")
REPO_HEALTH_JSON_PARTS = ("artifacts", "health", "repo-health.json")
REPO_HEALTH_HTML_PARTS = ("artifacts", "health", "repo-health.html")
REPO_HEALTH_MARKDOWN_PARTS = ("docs", "generated", "repo-health.md")


def _repo_relative_text(*parts: str) -> str:
    return Path(*parts).as_posix()


def _run_repo_health() -> int:
    completed = subprocess.run(  # nosec B603 - fixed Python executable and controlled arguments
        [
            sys.executable,
            "scripts/repo_health.py",
            "--audit-dir",
            _repo_relative_text(*AUDIT_DIR_PARTS),
            "--json-output",
            _repo_relative_text(*REPO_HEALTH_JSON_PARTS),
            "--markdown-output",
            _repo_relative_text(*REPO_HEALTH_MARKDOWN_PARTS),
            "--html-output",
            _repo_relative_text(*REPO_HEALTH_HTML_PARTS),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    return int(completed.returncode)


def main() -> int:
    return _run_repo_health()


if __name__ == "__main__":
    raise SystemExit(main())
