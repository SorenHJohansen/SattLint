# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportArgumentType=false
from __future__ import annotations

import json

from sattlint.devtools import coordination_lock_state


def test_hold_lock_leaves_replaced_lock_file_in_place(tmp_path):
    lock_path = coordination_lock_state.shared_coordination_dir(tmp_path) / coordination_lock_state.LOCKFILE_NAME

    with coordination_lock_state._hold_lock(tmp_path):
        lock_path.write_text("999999", encoding="utf-8")

    assert lock_path.read_text(encoding="utf-8") == "999999"


def test_parse_markdown_ledger_normalizes_entries_and_drops_done_rows(tmp_path):
    entries, dropped_done = coordination_lock_state.parse_markdown_ledger(
        """
### Workstream WS-1
- Owner: Alice
- Status: active
- Claims: `src/sattlint/devtools/coordination_lock_state.py`
- Updated: 2026-06-11T12:00:00Z
- First Validation: pytest tests/test_coordination_lock_state.py -q

### Workstream WS-2
- Owner: Bob
- Status: done
- Claims: `src/sattlint/devtools/ledger.py`
""",
        repo_root=tmp_path,
        default_updated_at="2026-06-11T00:00:00Z",
    )

    assert dropped_done == 1
    assert entries == [
        {
            "workstream_id": "WS-1",
            "owner": "Alice",
            "status": "active",
            "claimed_paths": ["src/sattlint/devtools/coordination_lock_state.py"],
            "updated_at": "2026-06-11T12:00:00Z",
            "first_validation": "pytest tests/test_coordination_lock_state.py -q",
        }
    ]


def test_write_load_and_upsert_workstream_round_trip(tmp_path):
    updated_at = coordination_lock_state.utc_now_timestamp()
    entries = [
        {
            "workstream_id": "WS-1",
            "owner": "Alice",
            "status": "active",
            "claimed_paths": ["src/sattlint/devtools/coordination_lock_state.py"],
            "updated_at": updated_at,
            "first_validation": "pytest tests/test_coordination_lock_state.py -q",
        }
    ]

    written = coordination_lock_state.write_lock_state(tmp_path, entries)
    loaded = coordination_lock_state.load_lock_state(tmp_path)
    updated = coordination_lock_state.upsert_workstream(
        tmp_path,
        workstream_id="WS-1",
        owner="Alice",
        status="blocked",
        claimed_paths=["src/sattlint/devtools/coordination_lock.py"],
        first_validation="pytest tests/test_coordination_lock_state.py -q -k round_trip",
    )

    assert written == entries
    assert loaded == entries
    assert updated["status"] == "blocked"
    assert updated["claimed_paths"] == ["src/sattlint/devtools/coordination_lock.py"]
    assert coordination_lock_state.load_lock_state(tmp_path) == [updated]


def test_claimed_file_debt_entries_match_directory_claims_and_oversized_structural_debt(tmp_path):
    ratchet_path = tmp_path / coordination_lock_state.FILE_DEBT_RATCHET_PATH
    ratchet_path.parent.mkdir(parents=True, exist_ok=True)
    ratchet_path.write_text(
        json.dumps(
            {
                "files": {
                    "src/sattlint/devtools/coordination_lock_state.py": {
                        "structural": {
                            "current_baseline": 580,
                            "target": 400,
                            "touch_rule": "must_not_grow",
                            "reason": "oversized module",
                        },
                        "coverage": {
                            "touch_rule": "must_not_drop",
                            "reason": "keep behavior covered",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    entries = coordination_lock_state.claimed_file_debt_entries(
        tmp_path,
        ["src/sattlint/devtools/"],
    )
    oversized = coordination_lock_state.claimed_oversized_structural_debt_entries(
        tmp_path,
        ["src/sattlint/devtools/"],
    )

    assert entries == [
        {
            "path": "src/sattlint/devtools/coordination_lock_state.py",
            "dimensions": ["coverage", "structural"],
            "touch_rules": {"coverage": "must_not_drop", "structural": "must_shrink"},
            "structural_current_baseline": 580,
            "structural_target": 400,
            "structural_touch_rule": "must_shrink",
            "reasons": ["oversized module", "keep behavior covered"],
        }
    ]
    assert oversized == entries


def test_migrate_current_work_ledger_writes_lock_state_and_removes_source(tmp_path):
    ledger_path = coordination_lock_state.ledger_path(tmp_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        """
### Workstream WS-1
- Owner: Alice
- Status: active
- Claims: `src/sattlint/devtools/coordination_lock_state.py`

### Workstream WS-2
- Owner: Bob
- Status: done
- Claims: `src/sattlint/devtools/ledger.py`
""",
        encoding="utf-8",
    )

    migration = coordination_lock_state.migrate_current_work_ledger(tmp_path)
    lock_state_file = coordination_lock_state.lock_state_path(tmp_path)
    loaded = coordination_lock_state.load_lock_state(tmp_path)

    assert migration["source"] == coordination_lock_state.ledger_path(tmp_path).relative_to(tmp_path).as_posix()
    assert migration["active_workstream_count"] == 1
    assert migration["dropped_done_workstream_count"] == 1
    assert ledger_path.exists() is False
    assert json.loads(lock_state_file.read_text(encoding="utf-8")) == {"workstreams": loaded}
