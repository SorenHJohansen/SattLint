import json
import sqlite3
from pathlib import Path
from typing import Any

from sattlint.devtools import ai_chat_observability


def test_ai_chat_observability_writes_fixture_artifacts(tmp_path):
    fixture_root = Path(__file__).resolve().parent / "fixtures" / "ai_chat" / "sample_workspace" / "GitHub.copilot-chat"
    output_dir = tmp_path / "artifacts"
    session_db = _write_degraded_session_store(tmp_path / "session-store.sqlite3")

    exit_code = ai_chat_observability.main(
        [
            "--transcripts-dir",
            str(fixture_root / "transcripts"),
            "--output-dir",
            str(output_dir),
            "--session-db",
            str(session_db),
        ]
    )

    assert exit_code == 0
    status = _load_json(output_dir / "status.json")
    summary = _load_json(output_dir / "summary.json")
    sessions = _load_json(output_dir / "sessions.json")
    findings = _load_json(output_dir / "findings.json")

    assert status["overall_status"] == "degraded"
    assert summary["transcript_corpus"]["session_count"] == 2
    assert summary["transcript_corpus"]["status"] == "degraded"
    assert summary["session_store"]["status"] == "degraded"
    assert summary["health_summary"]["highest_churn_bucket"] == "implement-this-plan"
    assert sessions["session_count"] == 2
    assert sessions["malformed_line_count"] == 1

    finding_ids = {entry["id"] for entry in findings["findings"]}
    assert {
        "session-store-empty",
        "high-empty-assistant-output-rate",
        "high-discovery-before-action",
        "codegraph-tool-failures",
        "repeated-tool-retries",
        "malformed-transcript-line",
    } <= finding_ids

    implement_session = next(entry for entry in sessions["sessions"] if entry["session_id"] == "fixture-implement-plan")
    assert implement_session["prompt_bucket"] == "implement-this-plan"
    assert implement_session["first_action_tool"] == "apply_patch"
    assert implement_session["discovery_before_action_count"] == 8
    assert implement_session["codegraph_failure_count"] == 2
    assert implement_session["same_tool_retry_count"] == 1


def test_ai_chat_observability_resolves_workspace_storage_root(tmp_path):
    fixture_root = Path(__file__).resolve().parent / "fixtures" / "ai_chat" / "sample_workspace" / "GitHub.copilot-chat"
    output_dir = tmp_path / "artifacts"

    exit_code = ai_chat_observability.main(
        [
            "--workspace-storage",
            str(fixture_root),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    status = _load_json(output_dir / "status.json")
    assert status["transcript_source"]["input_kind"] == "workspace-storage"
    assert status["transcript_source"]["transcripts_dir"].endswith(
        "tests/fixtures/ai_chat/sample_workspace/GitHub.copilot-chat/transcripts"
    )


def test_ai_chat_observability_requires_transcripts_child_dir(tmp_path, capsys):
    workspace_storage = tmp_path / "GitHub.copilot-chat"
    workspace_storage.mkdir()

    exit_code = ai_chat_observability.main(
        [
            "--workspace-storage",
            str(workspace_storage),
            "--output-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    assert exit_code == 2
    assert "transcripts child directory" in capsys.readouterr().err


def _write_degraded_session_store(path: Path) -> Path:
    connection = sqlite3.connect(path)
    with connection:
        connection.execute(
            "CREATE TABLE sessions (id INTEGER PRIMARY KEY, repo TEXT, cwd TEXT, branch TEXT, agent TEXT)"
        )
        connection.execute("CREATE TABLE turns (id INTEGER PRIMARY KEY, session_id INTEGER, role TEXT)")
        connection.execute("CREATE TABLE session_files (id INTEGER PRIMARY KEY, session_id INTEGER, path TEXT)")
        connection.executemany(
            "INSERT INTO sessions (repo, cwd, branch, agent) VALUES (?, ?, ?, ?)",
            [
                ("", "", "", ""),
                (None, None, None, None),
            ],
        )
    connection.close()
    return path


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
