import importlib.util
import json
from pathlib import Path

from sattlint.devtools import ai_work_map

REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_CONTEXT_PATH = REPO_ROOT / ".github" / "hooks" / "scripts" / "session_context.py"


def _load_session_context_module():
    spec = importlib.util.spec_from_file_location("sattlint_session_context", SESSION_CONTEXT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_planning_context_payload_uses_compact_session_map(monkeypatch, tmp_path):
    session_context = _load_session_context_module()
    app_path = tmp_path / "src" / "sattlint" / "app.py"
    app_path.parent.mkdir(parents=True)
    app_path.write_text("", encoding="utf-8")
    session_map = {"kind": "sattlint.ai_session_context_map"}
    calls: dict[str, object] = {}

    monkeypatch.setattr(ai_work_map, "load_session_context_map", lambda: session_map)

    def fake_build_planning_context(*, changed_files, recommended_check_ids, selected_surface, work_map=None):
        calls["changed_files"] = changed_files
        calls["recommended_check_ids"] = recommended_check_ids
        calls["selected_surface"] = selected_surface
        calls["work_map"] = work_map
        return {
            "primary_agent": "CLI App Menu",
            "instruction_files": [{"name": "CLI App Instructions"}],
            "nearest_owner_suites": [{"tests": ["tests/test_app.py"]}],
            "first_validation_commands": ["pytest tests/test_app.py -x -q --tb=short"],
        }

    monkeypatch.setattr(ai_work_map, "build_planning_context", fake_build_planning_context)

    payload = session_context._build_planning_context_payload(
        {"paths": [app_path], "keywords": set(), "text": ""},
        tmp_path,
    )

    assert payload == {
        "changed_files": ["src/sattlint/app.py"],
        "selected_surface": "session-start",
        "primary_agent": "CLI App Menu",
        "instruction_names": ["CLI App Instructions"],
        "owner_test_targets": ["tests/test_app.py"],
        "first_validation_commands": ["pytest tests/test_app.py -x -q --tb=short"],
    }
    assert calls["recommended_check_ids"] is None
    assert calls["selected_surface"] == "session-start"
    assert calls["work_map"] is session_map


def test_format_context_uses_compact_summary_language_and_first_validation():
    session_context = _load_session_context_module()
    ranked = [
        {
            "entry": {
                "id": "ai-context-feedback-tightening-2026-05-01",
                "owner": "Copilot",
                "goal": "Tighten AI session context and feedback.",
                "status": "active",
            },
            "matched_claims": ["src/sattlint/app.py"],
            "matched_keywords": ["context"],
            "score": 80,
        }
    ]
    planning = {
        "changed_files": ["src/sattlint/app.py"],
        "selected_surface": "session-start",
        "primary_agent": "CLI App Menu",
        "instruction_names": ["CLI App Instructions"],
        "owner_test_targets": ["tests/test_app.py"],
        "first_validation_commands": ["pytest tests/test_app.py -x -q --tb=short"],
    }

    context = session_context._format_context(ranked, planning)

    assert context is not None
    assert "Relevant SattLint workstreams:" in context
    assert "current-work.md" not in context
    assert "first-validation=pytest tests/test_app.py -x -q --tb=short" in context
    assert "Use the compact session summary first." in context
    assert "JSON lock state" in context


def test_write_summary_records_first_validation_commands(tmp_path):
    session_context = _load_session_context_module()
    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True)
    planning = {
        "changed_files": ["src/sattlint/app.py"],
        "selected_surface": "session-start",
        "primary_agent": "CLI App Menu",
        "instruction_names": ["CLI App Instructions"],
        "owner_test_targets": ["tests/test_app.py"],
        "first_validation_commands": ["pytest tests/test_app.py -x -q --tb=short"],
    }

    session_context._write_summary(
        tmp_path,
        {"paths": [], "keywords": set(), "text": ""},
        [],
        0,
        tmp_path,
        planning,
    )

    summary_path = coordination_dir / "current_work_summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert payload["planning"]["first_validation_commands"] == ["pytest tests/test_app.py -x -q --tb=short"]
