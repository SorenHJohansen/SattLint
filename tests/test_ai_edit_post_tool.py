from __future__ import annotations

import importlib.util
import io
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / ".github" / "hooks" / "scripts" / "ai_edit_gate_post_tool.py"


def _load_post_tool_module():
    spec = importlib.util.spec_from_file_location("sattlint_ai_edit_gate_post_tool", HOOK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_ignores_non_edit_tools(monkeypatch, tmp_path):
    hook = _load_post_tool_module()
    payload = {
        "hookEventName": "PostToolUse",
        "cwd": str(tmp_path),
        "tool_name": "functions.read_file",
        "tool_input": {"filePath": str(tmp_path / "README.md")},
    }
    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(json.dumps(payload)))

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook.main() == 0
    assert calls == []


def test_main_runs_ai_edit_gate_for_apply_patch(monkeypatch, tmp_path):
    hook = _load_post_tool_module()
    target = tmp_path / "src" / "demo.py"
    payload = {
        "hookEventName": "PostToolUse",
        "cwd": str(tmp_path),
        "tool_name": "functions.apply_patch",
        "tool_input": {
            "input": "\n".join(
                [
                    "*** Begin Patch",
                    f"*** Update File: {target}",
                    "@@",
                    "-value = 1",
                    "+value = 2",
                    "*** End Patch",
                ]
            )
        },
    }
    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(hook, "_resolve_python", lambda _repo_root: Path("python"))

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook.main() == 0
    assert calls == [["python", "scripts/run_ai_edit_gate.py", "src/demo.py"]]


def test_main_blocks_when_ai_edit_gate_fails(monkeypatch, tmp_path, capsys):
    hook = _load_post_tool_module()
    payload = {
        "hookEventName": "PostToolUse",
        "cwd": str(tmp_path),
        "tool_name": "functions.create_file",
        "tool_input": {"filePath": str(tmp_path / "docs" / "repo-map.md"), "content": "# Repo Map\n"},
    }
    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(hook, "_resolve_python", lambda _repo_root: Path("python"))
    monkeypatch.setattr(
        hook.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1, stdout="", stderr="boom"),
    )

    assert hook.main() == 1
    assert "AI edit gate blocked: boom" in capsys.readouterr().err


def test_main_fails_open_when_hook_runtime_raises(monkeypatch, tmp_path, capsys):
    hook = _load_post_tool_module()
    payload = {
        "hookEventName": "PostToolUse",
        "cwd": str(tmp_path),
        "tool_name": "functions.create_file",
        "tool_input": {"filePath": str(tmp_path / "docs" / "repo-map.md"), "content": "# Repo Map\n"},
    }
    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(hook, "_resolve_python", lambda _repo_root: Path("python"))

    def raise_runtime(_command, **_kwargs):
        raise RuntimeError("subprocess unavailable")

    monkeypatch.setattr(hook.subprocess, "run", raise_runtime)

    assert hook.main() == 0
    warning_payload = json.loads(capsys.readouterr().out)

    assert warning_payload["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "hook failed open" in warning_payload["systemMessage"]
