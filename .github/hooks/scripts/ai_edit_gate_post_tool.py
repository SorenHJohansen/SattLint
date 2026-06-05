from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hook_path_compat import normalize_payload_path_text, resolve_payload_cwd  # noqa: E402

EDIT_TOOL_NAMES = {
    "apply_patch",
    "create_file",
    "edit_notebook_file",
    "multi_replace_string_in_file",
    "replace_string_in_file",
    "vscode_renamesymbol",
    "mcp_pylance_mcp_s_pylanceinvokerefactoring",
}


def _load_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _normalize_tool_name(tool_name: str) -> str:
    return tool_name.rsplit(".", 1)[-1].casefold()


def _normalize_relative(raw_path: str) -> str:
    cleaned = normalize_payload_path_text(raw_path)
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.rstrip("/")


def _resolve_workspace_path(raw_path: str, cwd: Path) -> Path:
    path = Path(_normalize_relative(raw_path))
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def _extract_patch_paths(patch_text: str) -> list[str]:
    lines = patch_text.splitlines()
    prefix = "*** "
    paths: list[str] = []
    for line in lines:
        if not line.startswith(prefix) or " File: " not in line:
            continue
        path_text = line.split(" File: ", 1)[1].split(" -> ", 1)[0].strip()
        if path_text:
            paths.append(path_text)
    return paths


def _extract_tool_paths(tool_name: str, tool_input: object, cwd: Path) -> list[Path]:
    normalized_tool_name = _normalize_tool_name(tool_name)
    if normalized_tool_name not in EDIT_TOOL_NAMES:
        return []

    seen: dict[str, Path] = {}

    def add_raw(raw_path: str) -> None:
        relative = _normalize_relative(raw_path)
        if not relative:
            return
        seen[relative.casefold()] = _resolve_workspace_path(relative, cwd)

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                lowered = key.casefold()
                if lowered in {"filepath", "path", "old_path", "new_path"} and isinstance(nested, str):
                    add_raw(nested)
                    continue
                if lowered in {"filepaths", "files", "paths"} and isinstance(nested, list):
                    for item in nested:
                        if isinstance(item, str):
                            add_raw(item)
                    continue
                if lowered == "input" and isinstance(nested, str) and normalized_tool_name == "apply_patch":
                    for item in _extract_patch_paths(nested):
                        add_raw(item)
                    continue
                walk(nested)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(tool_input)
    return list(seen.values())


def _resolve_python(repo_root: Path) -> Path:
    windows_python = repo_root / ".venv" / "Scripts" / "python.exe"
    if windows_python.exists():
        return windows_python

    posix_python = repo_root / ".venv" / "bin" / "python"
    if posix_python.exists():
        return posix_python

    return Path(sys.executable)


def _relative_targets(targets: list[Path], cwd: Path) -> list[str]:
    rel_paths: list[str] = []
    seen: set[str] = set()
    for target in targets:
        try:
            relative = target.resolve().relative_to(cwd.resolve()).as_posix()
        except ValueError:
            continue
        if relative in seen:
            continue
        seen.add(relative)
        rel_paths.append(relative)
    return rel_paths


def _warning_payload(message: str) -> dict[str, object]:
    return {
        "systemMessage": message,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        },
    }


def main() -> int:
    try:
        payload = _load_payload()
        if payload.get("hookEventName") != "PostToolUse":
            return 0

        cwd = resolve_payload_cwd(str(payload.get("cwd") or "."))
        tool_name = str(payload.get("tool_name") or "")
        targets = _extract_tool_paths(tool_name, payload.get("tool_input"), cwd)
        rel_paths = _relative_targets(targets, cwd)
        if not rel_paths:
            return 0

        python_executable = _resolve_python(cwd)
        completed = subprocess.run(
            [str(python_executable), "scripts/run_ai_edit_gate.py", *rel_paths],
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0:
            return 0

        detail = (
            completed.stderr.strip() or completed.stdout.strip() or "run_ai_edit_gate.py returned a non-zero exit code."
        )
        print(f"AI edit gate blocked: {detail}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - hook failures should not block edits
        message = f"AI edit gate hook warning: hook failed open with {type(exc).__name__}: {exc}"
        sys.stdout.write(json.dumps(_warning_payload(message)))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
