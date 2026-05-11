import importlib.util
import json
import subprocess
import sys
import textwrap
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


def test_write_summary_creates_coordination_directory(tmp_path):
    session_context = _load_session_context_module()

    session_context._write_summary(
        tmp_path,
        {"paths": [], "keywords": set(), "text": ""},
        [],
        0,
        tmp_path,
        None,
    )

    assert (tmp_path / ".github" / "coordination" / "current_work_summary.json").exists()


def test_rank_workstreams_handles_claim_patterns_without_raw_metadata(monkeypatch, tmp_path):
    session_context = _load_session_context_module()
    claimed_path = tmp_path / "src" / "sattlint" / "app.py"
    claimed_path.parent.mkdir(parents=True)
    claimed_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        session_context.coordination_lock_state,
        "load_lock_state",
        lambda repo_root: [
            {
                "workstream_id": "session-start-hook-compat",
                "owner": "Copilot",
                "status": "active",
                "claimed_paths": ["src/sattlint/app.py"],
                "updated_at": "2026-05-08T00:00:00Z",
                "first_validation": "pytest tests/test_session_context.py -x -q --tb=short",
            }
        ],
    )
    monkeypatch.setattr(
        session_context.coordination_lock_state,
        "resolve_claim_patterns",
        lambda claimed_paths, cwd: [{"path": claimed_path, "is_directory": False}],
    )

    entries = session_context._load_active_workstreams(tmp_path, tmp_path)
    ranked = session_context._rank_workstreams(
        entries,
        {"paths": [claimed_path], "keywords": set(), "text": ""},
    )

    assert entries[0]["claim_paths"] == [{"raw": "src/sattlint/app.py", "path": claimed_path, "is_directory": False}]
    assert ranked[0]["matched_claims"] == ["src/sattlint/app.py"]


def test_build_planning_context_payload_does_not_require_lark_import():
    script = textwrap.dedent(
        f"""
        import builtins
        import importlib.util
        import json
        from pathlib import Path

        repo_root = Path({str(REPO_ROOT)!r})
        original_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'lark' or name.startswith('lark.'):
                raise ModuleNotFoundError("No module named 'lark'")
            return original_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarded_import
        module_path = repo_root / '.github' / 'hooks' / 'scripts' / 'session_context.py'
        spec = importlib.util.spec_from_file_location('sattlint_session_context_subprocess', module_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        payload = module._build_planning_context_payload(
            {{'paths': [repo_root / 'src' / 'sattlint' / 'app.py'], 'keywords': set(), 'text': ''}},
            repo_root,
        )
        print(json.dumps(payload))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["changed_files"] == ["src/sattlint/app.py"]
    assert payload["selected_surface"] == "session-start"
    assert payload["primary_agent"] == "CLI App Menu"
