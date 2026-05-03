from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OPTIONS_WITH_VALUE = {"--config", "--configPointer"}


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


def _has_explicit_targets(tool_args: list[str]) -> bool:
    skip_next = False
    for arg in tool_args:
        if skip_next:
            skip_next = False
            continue
        if arg in OPTIONS_WITH_VALUE:
            skip_next = True
            continue
        if arg.startswith("--"):
            continue
        return True
    return False


def _build_tool_args(tool_args: list[str]) -> list[str]:
    if "--no-globs" in tool_args or not _has_explicit_targets(tool_args):
        return tool_args

    built_args: list[str] = []
    index = 0
    while index < len(tool_args):
        arg = tool_args[index]
        if arg in OPTIONS_WITH_VALUE:
            built_args.extend(tool_args[index : index + 2])
            index += 2
            continue
        if arg.startswith("--"):
            built_args.append(arg)
            index += 1
            continue
        built_args.append("--no-globs")
        built_args.extend(tool_args[index:])
        return built_args

    return built_args


def main(argv: list[str] | None = None) -> int:
    tool_args = _build_tool_args(argv if argv is not None else sys.argv[1:])
    command, cwd = _resolve_command(tool_args)
    if not command:
        return 2

    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
