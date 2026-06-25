# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_PATH = REPO_ROOT / ".github" / "hooks" / "scripts" / "switch_agent_plan_guard.py"


def _load_hook_module():
    spec = importlib.util.spec_from_file_location("sattlint_switch_agent_plan_guard", HOOK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_denies_switch_agent_to_plan(monkeypatch, capsys):
    hook = _load_hook_module()
    payload = {
        "hookEventName": "PreToolUse",
        "tool_name": "functions.switch_agent",
        "tool_input": {"agentName": "Plan"},
    }
    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(json.dumps(payload)))

    assert hook.main() == 0
    response = json.loads(capsys.readouterr().out)

    assert response["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "plan mode" in response["hookSpecificOutput"]["permissionDecisionReason"].casefold()
    assert "switch_agent" in response["systemMessage"]


def test_main_ignores_other_tools(monkeypatch, capsys):
    hook = _load_hook_module()
    payload = {
        "hookEventName": "PreToolUse",
        "tool_name": "functions.read_file",
        "tool_input": {"filePath": "/tmp/demo.txt"},
    }
    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(json.dumps(payload)))

    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_main_fails_open_when_payload_loading_raises(monkeypatch, capsys):
    hook = _load_hook_module()
    monkeypatch.setattr(hook, "_load_payload", lambda: (_ for _ in ()).throw(ValueError("bad payload")))

    assert hook.main() == 0
    response = json.loads(capsys.readouterr().out)

    assert response["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert response["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "hook failed open" in response["systemMessage"]
