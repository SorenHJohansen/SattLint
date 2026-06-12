from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from scripts._repo_paths import repo_root_from
except ModuleNotFoundError:  # pragma: no cover - direct script execution resolves from scripts/
    from _repo_paths import repo_root_from

REPO_ROOT = repo_root_from(Path(__file__))


def _windows_path_to_wsl(path: Path) -> str:
    posix_path = path.resolve().as_posix()
    if len(posix_path) >= 2 and posix_path[1] == ":":
        drive = posix_path[0].lower()
        return f"/mnt/{drive}{posix_path[2:]}"
    return posix_path


def _normalize_wsl_args(tool_args: list[str]) -> list[str]:
    return [arg.replace("\\", "/") if not arg.startswith("-") else arg for arg in tool_args]


def _wsl_has_command(command_name: str) -> bool:
    return (
        subprocess.run(
            [
                "wsl",
                "--cd",
                _windows_path_to_wsl(REPO_ROOT),
                "sh",
                "-lc",
                f"command -v {shlex.quote(command_name)} >/dev/null 2>&1",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def _find_actionlint() -> str | None:
    if shutil.which("actionlint"):
        return "actionlint"

    candidates = [
        Path.home() / ".local" / "bin" / "actionlint",
        Path("/usr/local/bin/actionlint"),
        Path("/opt/homebrew/bin/actionlint"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    return None


def _resolve_command(tool_args: list[str]) -> tuple[list[str], Path | None]:
    command_args = ["-color", *tool_args]

    executable = _find_actionlint()
    if executable:
        return [executable, *command_args], REPO_ROOT

    if sys.platform == "win32" and shutil.which("wsl") and _wsl_has_command("actionlint"):
        return ["wsl", "--cd", _windows_path_to_wsl(REPO_ROOT), "actionlint", *_normalize_wsl_args(command_args)], None

    print(
        "actionlint requires `actionlint` on PATH or WSL with `actionlint` installed.",
        file=sys.stderr,
    )
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
