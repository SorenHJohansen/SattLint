import json
import sqlite3
from pathlib import Path
from typing import Any

from sattlint.devtools import _ai_chat_grounding as ai_chat_grounding
from sattlint.devtools import _ai_chat_transcripts as ai_chat_transcripts
from sattlint.devtools import ai_chat_observability
from sattlint.devtools._semble_adapter import SembleMatch, SembleSearchResponse


def test_ai_chat_observability_writes_fixture_artifacts(tmp_path, monkeypatch):
    fixture_root = Path(__file__).resolve().parent / "fixtures" / "ai_chat" / "sample_workspace" / "GitHub.copilot-chat"
    output_dir = tmp_path / "artifacts"
    session_db = _write_degraded_session_store(tmp_path / "session-store.sqlite3")
    monkeypatch.setattr(
        ai_chat_observability,
        "build_semantic_grounding_report",
        lambda *, transcript_report, repo_root: {
            "status": "ok",
            "backend": "python-library",
            "queryable_session_count": 2,
            "searchable_session_count": 2,
            "grounded_session_count": 1,
            "grounding_match_rate": 0.5,
            "average_candidate_match_ratio": 0.25,
            "ungrounded_session_ids": ["fixture-review"],
            "explanation": "grounded",
            "sessions": [
                {
                    "session_id": "fixture-implement-plan",
                    "status": "ok",
                    "query": "Implement this plan",
                    "candidate_file_paths": ["src/sattlint/devtools/ai_chat_observability.py"],
                    "matched_file_paths": ["src/sattlint/devtools/ai_chat_observability.py"],
                    "match_ratio": 1.0,
                    "explanation": "grounded",
                },
                {
                    "session_id": "fixture-review",
                    "status": "ungrounded",
                    "query": "Review this slice",
                    "candidate_file_paths": ["tests/test_repo_audit.py"],
                    "matched_file_paths": [],
                    "match_ratio": 0.0,
                    "explanation": "ungrounded",
                },
            ],
        },
    )

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
    assert summary["semantic_grounding"]["status"] == "ok"
    assert summary["semantic_grounding"]["grounding_match_rate"] == 0.5
    assert summary["health_summary"]["highest_churn_bucket"] == "implement-this-plan"
    assert summary["health_summary"]["semantic_grounding_health"] == "ok"
    assert sessions["session_count"] == 2
    assert sessions["malformed_line_count"] == 1

    finding_ids = {entry["id"] for entry in findings["findings"]}
    assert {
        "session-store-empty",
        "high-empty-assistant-output-rate",
        "high-discovery-before-action",
        "repeated-tool-retries",
        "malformed-transcript-line",
    } <= finding_ids

    implement_session = next(entry for entry in sessions["sessions"] if entry["session_id"] == "fixture-implement-plan")
    assert implement_session["prompt_bucket"] == "implement-this-plan"
    assert implement_session["first_action_tool"] == "apply_patch"
    assert implement_session["discovery_before_action_count"] == 8
    assert implement_session["same_tool_retry_count"] == 1
    assert implement_session["semantic_grounding"]["status"] == "ok"


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


def test_ai_chat_observability_returns_failure_when_output_write_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        ai_chat_observability,
        "build_ai_chat_observability_report",
        lambda **_kwargs: {
            "status": {"overall_status": "ok", "output_dir": str((tmp_path / "artifacts").resolve())},
            "summary": {
                "transcript_corpus": {"transcript_count": 1},
                "session_store": {"status": "ok"},
            },
            "sessions": {"session_count": 1},
            "findings": {"finding_count": 0, "findings": []},
        },
    )
    monkeypatch.setattr(
        ai_chat_observability,
        "write_ai_chat_observability_artifacts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("locked")),
    )

    exit_code = ai_chat_observability.main(
        [
            "--transcripts-dir",
            str(tmp_path / "transcripts"),
            "--output-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == {
        "finding_count": 0,
        "output_dir": str((tmp_path / "artifacts").resolve()),
        "overall_status": "ok",
        "session_store_status": "ok",
        "transcript_count": 1,
    }
    assert "ai chat observability output error: locked" in captured.err


def test_load_transcript_corpus_tolerates_unreadable_transcript(monkeypatch, tmp_path):
    transcripts_dir = tmp_path / "transcripts"
    transcripts_dir.mkdir()
    readable = transcripts_dir / "readable.jsonl"
    unreadable = transcripts_dir / "unreadable.jsonl"
    readable.write_text('{"type":"user.message","data":{"content":"hello"}}\n', encoding="utf-8")
    unreadable.write_text('{"type":"user.message","data":{"content":"secret"}}\n', encoding="utf-8")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == unreadable:
            raise PermissionError("permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    report = ai_chat_transcripts.load_transcript_corpus(
        resolved_input={
            "input_kind": "transcripts-dir",
            "input_path": "transcripts",
            "transcripts_dir": "transcripts",
            "resolved_transcripts_dir": transcripts_dir,
            "wrong_log_seam_risk": False,
        },
        repo_root=tmp_path,
    )

    assert report["transcript_count"] == 2
    assert len(report["sessions"]) == 2
    unreadable_session = next(session for session in report["sessions"] if session["session_id"] == "unreadable")
    assert unreadable_session["event_count"] == 0
    assert unreadable_session["malformed_line_count"] == 1
    assert report["parse_failures"][0]["transcript_path"].endswith("transcripts/unreadable.jsonl")
    assert report["parse_failures"][0]["line_number"] == 0


def test_build_semantic_grounding_report_uses_prompt_and_file_overlap(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ai_chat_grounding,
        "search_local_repo",
        lambda query, *, repo_root, top_k: SembleSearchResponse(
            available=True,
            backend="python-library",
            query=query,
            repo_path=repo_root.as_posix(),
            top_k=top_k,
            results=(
                SembleMatch(
                    file_path="src/sattlint/devtools/ai_chat_observability.py",
                    start_line=1,
                    end_line=20,
                    content="def build_ai_chat_observability_report(...)",
                    score=0.77,
                ),
                SembleMatch(
                    file_path="tests/test_repo_audit.py",
                    start_line=1,
                    end_line=20,
                    content="def test_repo_audit(...)",
                    score=0.61,
                ),
            ),
            explanation="ok",
        ),
    )

    report = ai_chat_grounding.build_semantic_grounding_report(
        transcript_report={
            "sessions": [
                {
                    "session_id": "session-1",
                    "prompt_preview": "update ai chat observability",
                    "file_reference_paths": ["src/sattlint/devtools/ai_chat_observability.py"],
                },
                {
                    "session_id": "session-2",
                    "prompt_preview": "review repo audit",
                    "file_reference_paths": ["src/sattlint/devtools/repo_audit.py"],
                },
            ]
        },
        repo_root=tmp_path,
    )

    assert report["status"] == "ok"
    assert report["queryable_session_count"] == 2
    assert report["searchable_session_count"] == 2
    assert report["grounded_session_count"] == 1
    assert report["grounding_match_rate"] == 0.5
    assert report["sessions"][0]["matched_file_paths"] == ["src/sattlint/devtools/ai_chat_observability.py"]
    assert report["sessions"][1]["status"] == "ungrounded"


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
