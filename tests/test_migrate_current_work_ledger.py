from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "migrate_current_work_ledger.py"


def _load_migration_script():
    spec = importlib.util.spec_from_file_location("sattlint_migrate_current_work_ledger", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migrate_current_work_ledger = _load_migration_script()


def test_migration_script_writes_lock_state_and_removes_legacy_markdown(tmp_path, capsys):
    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True)
    ledger_path = coordination_dir / "current-work.md"
    ledger_path.write_text(
        "\n".join(
            [
                "# Active Work Ledger",
                "",
                "## Active Workstreams",
                "",
                "### Workstream keep-me",
                "",
                "- Owner: Copilot",
                "- Status: active",
                "- Claims: `src/demo.py`, `.github/coordination/current-work.md`",
                "- Goal: keep this active",
                "- Notes: this should not survive in the compact view",
                "- First validation: pytest tests/test_migrate_current_work_ledger.py -x -q --tb=short",
                "",
                "### Workstream drop-me",
                "",
                "- Owner: Copilot",
                "- Status: done",
                "- Claims: `src/old.py`",
                "- First validation: pytest old",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = migrate_current_work_ledger.main(["--repo-root", str(tmp_path)])

    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "source": ".github/coordination/current-work.md",
        "lock_state": ".git/sattlint-ai-coordination/current_work_lock.json",
        "active_workstream_count": 1,
        "dropped_done_workstream_count": 1,
    }

    lock_state = json.loads(
        migrate_current_work_ledger.coordination_lock_state.lock_state_path(tmp_path).read_text(encoding="utf-8")
    )
    assert lock_state["workstreams"][0]["workstream_id"] == "keep-me"
    assert lock_state["workstreams"][0]["claimed_paths"] == [
        "src/demo.py",
        ".github/coordination/current-work.md",
    ]
    assert not ledger_path.exists()


def test_migration_script_returns_failure_when_lock_write_fails(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        migrate_current_work_ledger.coordination_lock_state,
        "migrate_current_work_ledger",
        lambda _repo_root: (_ for _ in ()).throw(PermissionError("read-only filesystem")),
    )

    exit_code = migrate_current_work_ledger.main(["--repo-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "migrate-current-work-ledger: read-only filesystem" in captured.err
