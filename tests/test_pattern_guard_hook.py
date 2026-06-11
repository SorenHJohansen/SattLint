from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PATTERN_GUARD_PATH = REPO_ROOT / ".github" / "hooks" / "scripts" / "pattern_guard.py"


def _load_pattern_guard_module():
    spec = importlib.util.spec_from_file_location("sattlint_pattern_guard", PATTERN_GUARD_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pattern_guard_reports_unallowlisted_matches(tmp_path, monkeypatch, capsys) -> None:
    pattern_guard = _load_pattern_guard_module()
    monkeypatch.setattr(pattern_guard, "REPO_ROOT", tmp_path)
    source = tmp_path / "src" / "demo.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("value = cast(Any, raw)\n", encoding="utf-8")

    exit_code = pattern_guard.main(
        [
            "--pattern",
            r"cast\(Any[,\s]",
            "--label",
            "cast(Any,...)",
            "src/demo.py",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "src/demo.py:1: forbidden cast(Any,...)" in captured.out


def test_pattern_guard_ignores_missing_files(tmp_path, monkeypatch, capsys) -> None:
    pattern_guard = _load_pattern_guard_module()
    monkeypatch.setattr(pattern_guard, "REPO_ROOT", tmp_path)

    exit_code = pattern_guard.main(
        [
            "--pattern",
            r"cast\(Any[,\s]",
            "--label",
            "cast(Any,...)",
            "src/demo.py",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
