from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_python(repo_root: Path) -> Path:
    windows_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if windows_python.exists():
        return windows_python

    posix_python = repo_root / ".venv" / "bin" / "python"
    if posix_python.exists():
        return posix_python

    return Path(sys.executable)


def _command_path(path: Path, python_executable: Path) -> str:
    if python_executable.suffix.casefold() != ".exe":
        return str(path)

    completed = subprocess.run(
        ["wslpath", "-w", str(path)],
        check=False,
        text=True,
        capture_output=True,
    )
    converted = completed.stdout.strip()
    if completed.returncode == 0 and converted:
        return converted
    return str(path)


def main() -> int:
    if len(sys.argv) < 2:
        return 2

    script_path = Path(sys.argv[1])
    if not script_path.is_absolute():
        script_path = REPO_ROOT / script_path

    python_executable = _resolve_python(REPO_ROOT)
    command = [str(python_executable), _command_path(script_path, python_executable), *sys.argv[2:]]
    completed = subprocess.run(command, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
