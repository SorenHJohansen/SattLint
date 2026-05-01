from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _windows_path_to_wsl(path: Path) -> str:
    posix_path = path.resolve().as_posix()
    if len(posix_path) >= 2 and posix_path[1] == ":":
        drive = posix_path[0].lower()
        return f"/mnt/{drive}{posix_path[2:]}"
    return posix_path


def _resolve_command(tool_args: list[str]) -> tuple[list[str], Path | None]:
    if sys.platform == "win32" and shutil.which("wsl"):
        return ["wsl", "--cd", _windows_path_to_wsl(REPO_ROOT), "npx", "--yes", "markdownlint-cli2", *tool_args], None

    if shutil.which("npx"):
        return ["npx", "--yes", "markdownlint-cli2", *tool_args], REPO_ROOT

    print("markdownlint requires `npx`, or WSL with `npx` available.", file=sys.stderr)
    return [], None


def main(argv: list[str] | None = None) -> int:
    tool_args = argv if argv is not None else sys.argv[1:]
    command, cwd = _resolve_command(tool_args)
    if not command:
        return 2

    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
