# pyright: reportArgumentType=false
from __future__ import annotations

from pathlib import Path

import pytest

from sattlint.cli import menu as menu_module
from sattlint.project import support as support_module


def test_target_load_error_categorizes_other_entries_and_warnings() -> None:
    error = support_module.TargetLoadError(
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
    error = support_module.TargetLoadError("Root", resolved=[], missing=[], warnings=[])

    assert "Resolved targets: none" in str(error)
    assert "Missing/failed targets: none" in str(error)


def test_print_validation_warnings_and_target_helpers_cover_edge_cases(tmp_path: Path) -> None:
    printed: list[str] = []
    support_module.print_validation_warnings([], print_fn=printed.append)
    support_module.print_validation_warnings([f"warn-{index}" for index in range(13)], print_fn=printed.append)
    support_module.print_validation_warnings(
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
    assert support_module.extract_warning_name("plain warning") is None
    assert not support_module.is_expected_unavailable_warning(
        "TargetA: dependency 'ControlLib' unavailable: unexpected reason"
    )
    assert support_module.get_analyzed_targets({"analyzed_programs_and_libraries": "bad"}) == []
    assert (
        menu_module.summarize_targets({"analyzed_programs_and_libraries": ["A", "B", "C", "D"]})
        == "4 targets configured: A, B, C, ..."
    )
    with pytest.raises(RuntimeError):
        support_module.require_analyzed_targets({"analyzed_programs_and_libraries": []})

    paused: list[str] = []
    menu_module.show_help(
        {"analyzed_programs_and_libraries": ["A"]},
        clear_screen_fn=lambda: printed.append("clear"),
        get_analyzed_targets_fn=lambda cfg: ["A"],
        summarize_targets_fn=lambda cfg: "1 target configured: A",
        print_fn=printed.append,
        pause_fn=lambda: paused.append("pause"),
    )
    assert "Current target status: 1 target configured: A" in printed
    assert paused == ["pause"]


def test_configured_icf_files_cover_error_paths(tmp_path: Path) -> None:
    assert support_module.configured_icf_files({"icf_dir": ""}) == (None, [])

    missing_dir = tmp_path / "missing"
    icf_dir, icf_files = support_module.configured_icf_files({"icf_dir": str(missing_dir)})
    assert icf_dir == missing_dir
    assert icf_files == []
