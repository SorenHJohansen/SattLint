from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path
from typing import Any, cast


def _load_guard_module():
    module_path = Path(__file__).resolve().parents[1] / ".github" / "hooks" / "scripts" / "claimed_files_guard.py"
    spec = importlib.util.spec_from_file_location("sattlint_claimed_files_guard", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


claimed_files_guard = _load_guard_module()


def _write_lock_state(tmp_path: Path, *, workstream_id: str, claimed_paths: list[str], status: str = "active") -> Path:
    state_path = claimed_files_guard.coordination_lock_state.lock_state_path(tmp_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "workstreams": [
                    {
                        "workstream_id": workstream_id,
                        "owner": "Copilot",
                        "status": status,
                        "claimed_paths": claimed_paths,
                        "updated_at": claimed_files_guard.coordination_lock_state.utc_now_timestamp(),
                        "first_validation": "pytest tests/test_claimed_files_guard.py -x -q --tb=short",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return state_path


def _run_guard(payload: dict[str, object]) -> dict[str, Any] | None:
    stdin = io.StringIO(json.dumps(payload))
    stdout = io.StringIO()
    previous_stdin = sys.stdin
    previous_stdout = sys.stdout
    sys.stdin = stdin
    sys.stdout = stdout
    try:
        exit_code = claimed_files_guard.main()
    finally:
        sys.stdin = previous_stdin
        sys.stdout = previous_stdout
    assert exit_code == 0
    output = stdout.getvalue().strip()
    if not output:
        return None
    return cast(dict[str, Any], json.loads(output))


def test_claimed_files_guard_reads_json_lock_state_before_markdown_ledger(tmp_path):
    target_path = tmp_path / "src" / "demo.py"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("value = 1\n", encoding="utf-8")

    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True, exist_ok=True)
    markdown_ledger = coordination_dir / "current-work.md"
    markdown_ledger.write_text(
        "\n".join(
            [
                "# Active Work Ledger",
                "",
                "## Active Workstreams",
                "",
                "### Workstream stale-ledger-entry",
                "",
                "- Owner: Other",
                "- Status: active",
                "- Claims: `src/other.py`",
                "- First validation: pytest old",
                "- Updated: 2026-05-03T23:59:00Z",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_lock_state(tmp_path, workstream_id="json-lock-entry", claimed_paths=["src/demo.py"])

    payload = {
        "hookEventName": "PreToolUse",
        "cwd": str(tmp_path),
        "tool_name": "apply_patch",
        "tool_input": {
            "input": "\n".join(
                [
                    "*** Begin Patch",
                    f"*** Update File: {target_path.as_posix()}",
                    "@@",
                    "-value = 1",
                    "+value = 2",
                    "*** End Patch",
                ]
            )
        },
    }

    response = _run_guard(payload)

    assert response is not None
    assert response["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "json-lock-entry" in response["systemMessage"]
    assert "stale-ledger-entry" not in response["systemMessage"]


def test_claimed_files_guard_ignores_markdown_when_lock_state_is_missing(tmp_path):
    target_path = tmp_path / "src" / "demo.py"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("value = 1\n", encoding="utf-8")

    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True, exist_ok=True)
    markdown_ledger = coordination_dir / "current-work.md"
    markdown_ledger.write_text(
        "\n".join(
            [
                "# Active Work Ledger",
                "",
                "## Active Workstreams",
                "",
                "### Workstream migrated-entry",
                "",
                "- Owner: Copilot",
                "- Status: active",
                "- Claims: `src/demo.py`",
                "- First validation: pytest tests/test_claimed_files_guard.py -x -q --tb=short",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = {
        "hookEventName": "PreToolUse",
        "cwd": str(tmp_path),
        "tool_name": "apply_patch",
        "tool_input": {
            "input": "\n".join(
                [
                    "*** Begin Patch",
                    f"*** Update File: {target_path.as_posix()}",
                    "@@",
                    "-value = 1",
                    "+value = 2",
                    "*** End Patch",
                ]
            )
        },
    }

    response = _run_guard(payload)

    lock_state_path = claimed_files_guard.coordination_lock_state.lock_state_path(tmp_path)
    assert response is None
    assert not lock_state_path.exists()
    assert markdown_ledger.exists()
