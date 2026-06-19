# pyright: reportArgumentType=false
from __future__ import annotations

from pathlib import Path

import pytest

from sattlint import app_support


class _FormatResult:
    def __init__(self, *, changed: bool) -> None:
        self.changed = changed


def test_target_load_error_categorizes_other_entries_and_warnings() -> None:
    error = app_support.TargetLoadError(
        "Root",
        resolved=["Root", "DepA"],
        missing=[
            "Root parse/transform error: bad syntax",
            "Missing code file for 'DepA'",
            "unstructured failure",
        ],
        warnings=[
            "Root: root warning",
            "DepA: direct warning",
            "mystery warning",
        ],
        direct_dependencies=["DepA"],
    )

    message = str(error)

    assert "Root target validation errors (1):" in message
    assert "Failed direct dependencies (1):" in message
    assert "Other missing/failed entries (1):" in message
    assert "Root target warnings (1):" in message
    assert "Direct dependency warnings (1):" in message
    assert "Other warnings (1):" in message


def test_target_load_error_reports_missing_none_when_no_failures() -> None:
    error = app_support.TargetLoadError("Root", resolved=[], missing=[], warnings=[])

    assert "Resolved targets: none" in str(error)
    assert "Missing/failed targets: none" in str(error)


def test_print_validation_warnings_and_target_helpers_cover_edge_cases(tmp_path: Path) -> None:
    printed: list[str] = []
    app_support.print_validation_warnings([], print_fn=printed.append)
    app_support.print_validation_warnings([f"warn-{index}" for index in range(13)], print_fn=printed.append)
    app_support.print_validation_warnings(
        [
            "TargetA: PictureDisplay in module 'Root.L1' path '+MissingPanel' could not be resolved: "
            "module 'MissingPanel' was not found under 'Root.L1'"
        ],
        print_fn=printed.append,
    )

    assert printed[0] == "Validation warnings (13):"
    assert printed[14] == "Validation warnings (1):"
    assert printed[15] == "  - [Root.L1] '+MissingPanel'"
    assert printed[16] == "    module 'MissingPanel' was not found under 'Root.L1'"
    assert app_support.extract_warning_name("plain warning") is None
    assert not app_support.is_expected_unavailable_warning(
        "TargetA: dependency 'ControlLib' unavailable: unexpected reason"
    )
    assert app_support.get_analyzed_targets({"analyzed_programs_and_libraries": "bad"}) == []
    assert (
        app_support.summarize_targets({"analyzed_programs_and_libraries": ["A", "B", "C", "D"]})
        == "4 targets configured: A, B, C, ..."
    )
    with pytest.raises(RuntimeError):
        app_support.require_analyzed_targets({"analyzed_programs_and_libraries": []})

    paused: list[str] = []
    app_support.show_help(
        {"analyzed_programs_and_libraries": ["A"]},
        clear_screen_fn=lambda: printed.append("clear"),
        get_analyzed_targets_fn=lambda cfg: ["A"],
        summarize_targets_fn=lambda cfg: "1 target configured: A",
        print_fn=printed.append,
        pause_fn=lambda: paused.append("pause"),
    )
    assert "Current target status: 1 target configured: A" in printed
    assert paused == ["pause"]


def test_configured_icf_files_and_run_format_icf_command_cover_error_paths(tmp_path: Path) -> None:
    assert app_support.configured_icf_files({"icf_dir": ""}) == (None, [])

    printed: list[str] = []
    assert (
        app_support.run_format_icf_command(
            {"icf_dir": ""},
            check=False,
            print_fn=printed.append,
            exit_success=0,
            exit_usage_error=2,
        )
        == 2
    )
    assert any("icf_dir is not set" in line for line in printed)

    missing_dir = tmp_path / "missing"
    icf_dir, icf_files = app_support.configured_icf_files({"icf_dir": str(missing_dir)})
    assert icf_dir == missing_dir
    assert icf_files == []

    printed.clear()
    assert (
        app_support.run_format_icf_command(
            {"icf_dir": str(missing_dir)},
            check=False,
            print_fn=printed.append,
            exit_success=0,
            exit_usage_error=2,
        )
        == 2
    )
    assert any("does not exist" in line for line in printed)

    real_dir = tmp_path / "icf"
    real_dir.mkdir()
    printed.clear()
    assert (
        app_support.run_format_icf_command(
            {"icf_dir": str(real_dir)},
            check=False,
            print_fn=printed.append,
            exit_success=0,
            exit_usage_error=2,
        )
        == 2
    )

    changed_file = real_dir / "a.icf"
    unchanged_file = real_dir / "b.icf"
    changed_file.write_text("x", encoding="utf-8")
    unchanged_file.write_text("y", encoding="utf-8")

    def fake_format_icf_file(path: Path, check: bool) -> _FormatResult:
        del check
        return _FormatResult(changed=path.name == "a.icf")

    original = app_support.format_icf_file
    app_support.format_icf_file = fake_format_icf_file
    try:
        printed.clear()
        exit_code = app_support.run_format_icf_command(
            {"icf_dir": str(real_dir)},
            check=True,
            print_fn=printed.append,
            exit_success=0,
            exit_usage_error=2,
        )
    finally:
        app_support.format_icf_file = original

    assert exit_code == 1
    assert any("Would change: 1" in line for line in printed)
    assert any("Unchanged: 1" in line for line in printed)
