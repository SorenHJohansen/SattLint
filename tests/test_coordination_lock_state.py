from __future__ import annotations

from sattlint.devtools import coordination_lock_state


def test_hold_lock_leaves_replaced_lock_file_in_place(tmp_path):
    lock_path = coordination_lock_state.shared_coordination_dir(tmp_path) / coordination_lock_state.LOCKFILE_NAME

    with coordination_lock_state._hold_lock(tmp_path):
        lock_path.write_text("999999", encoding="utf-8")

    assert lock_path.read_text(encoding="utf-8") == "999999"
