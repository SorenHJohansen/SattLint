from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _resolve_python(repo_root: Path) -> Path:
    windows_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if windows_python.exists():
        return windows_python

    posix_python = repo_root / ".venv" / "bin" / "python"
    if posix_python.exists():
        return posix_python

    return Path(sys.executable)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if len(sys.argv) == 1:
        print("usage: run_repo_python.py <python-args>", file=sys.stderr)
        return 2

    python_executable = _resolve_python(repo_root)
    completed = subprocess.run(
        [str(python_executable), *sys.argv[1:]],
        cwd=repo_root,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
