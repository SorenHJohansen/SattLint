from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from sattlint import app_menus

from ._app_menus_support import make_input


class _QuitSignalError(Exception):
    pass


def _option(key: str, label: str, description: str):
    return type("Option", (), {"key": key, "label": label, "description": description})()


def _capture_output(store: list[str]):
    def _emit(message: str, *args, **kwargs) -> None:
        store.append(message)

    return _emit


def test_analysis_target_helpers_cover_rejection_paths() -> None:
    cfg = {"analyzed_programs_and_libraries": ["Demo"]}
    pauses: list[str] = []
    outputs: list[str] = []
    original_emit = app_menus.emit_output
    app_menus.emit_output = _capture_output(outputs)
    try:
        assert (
            app_menus._add_analysis_target(
                cfg,
                prompt_fn=lambda *_: "Missing",
                target_exists_fn=lambda *_: False,
                confirm_fn=lambda *_: True,
                pause_fn=lambda: pauses.append("pause"),
            )
            is False
        )
        assert (
            app_menus._add_analysis_target(
                cfg,
                prompt_fn=lambda *_: "Demo",
                target_exists_fn=lambda *_: True,
                confirm_fn=lambda *_: True,
                pause_fn=lambda: pauses.append("pause"),
            )
            is False
        )
        assert (
            app_menus._add_analysis_target(
                cfg,
                prompt_fn=lambda *_: "NewTarget",
                target_exists_fn=lambda *_: True,
                confirm_fn=lambda *_: False,
                pause_fn=lambda: pauses.append("pause"),
            )
            is False
        )

        empty_cfg = {"analyzed_programs_and_libraries": []}
        assert (
            app_menus._remove_analysis_target(
                empty_cfg,
                prompt_fn=lambda *_: "1",
                confirm_fn=lambda *_: True,
                pause_fn=lambda: pauses.append("pause"),
            )
            is False
        )
        assert (
            app_menus._remove_analysis_target(
                cfg,
                prompt_fn=lambda *_: "bad",
                confirm_fn=lambda *_: True,
                pause_fn=lambda: pauses.append("pause"),
            )
            is False
        )
        assert (
            app_menus._remove_analysis_target(
                cfg,
                prompt_fn=lambda *_: "1",
                confirm_fn=lambda *_: False,
                pause_fn=lambda: pauses.append("pause"),
            )
            is False
        )
    finally:
        app_menus.emit_output = original_emit

    assert len(pauses) >= 3
    assert any("Target not found" in line for line in outputs)
    assert any("Target already listed" in line for line in outputs)
    assert any("No analyzed targets configured" in line for line in outputs)
    assert any("Invalid index" in line for line in outputs)


def test_config_value_helpers_cover_false_and_remove_paths(tmp_path: Path) -> None:
    cfg = {
        "scan_root_only": False,
        "program_dir": "old",
        "other_lib_dirs": ["/one", "/two"],
    }

    assert (
        app_menus._toggle_config_value(cfg, "scan_root_only", confirm_message="x", confirm_fn=lambda *_: False) is False
    )
    assert cfg["scan_root_only"] is False
    assert (
        app_menus._update_config_value(
            cfg,
            "program_dir",
            prompt_message="prompt",
            confirm_message="confirm",
            prompt_fn=lambda *_: "new",
            confirm_fn=lambda *_: False,
        )
        is False
    )
    assert cfg["program_dir"] == "old"
    assert (
        app_menus._edit_other_lib_dirs(
            cfg,
            prompt_fn=lambda *_: "2",
            confirm_fn=lambda message: message == "Remove entry?",
        )
        is True
    )
    assert cfg["other_lib_dirs"] == ["/one"]

    saved: list[tuple[Path, dict[str, object]]] = []
    assert (
        app_menus._save_configuration(
            cfg,
            dirty=True,
            config_path=tmp_path / "cfg.json",
            save_config_fn=lambda path, data: saved.append((path, dict(data))),
            confirm_fn=lambda *_: False,
        )
        is True
    )
    assert saved == []


def test_menu_remove_and_other_lib_dir_success_and_invalid_remove_paths() -> None:
    cfg = {
        "analyzed_programs_and_libraries": ["Demo"],
        "other_lib_dirs": ["/one"],
    }

    assert (
        app_menus._remove_analysis_target(
            cfg,
            prompt_fn=lambda *_: "1",
            confirm_fn=lambda *_: True,
            pause_fn=lambda: None,
        )
        is True
    )
    assert cfg["analyzed_programs_and_libraries"] == []

    confirms = iter([False, True])
    assert (
        app_menus._edit_other_lib_dirs(
            cfg,
            prompt_fn=lambda *_: "9",
            confirm_fn=lambda *_: next(confirms),
        )
        is False
    )
    assert cfg["other_lib_dirs"] == ["/one"]


def test_save_configuration_keeps_dirty_on_save_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = {"analyzed_programs_and_libraries": ["Demo"], "other_lib_dirs": []}
    config_path = tmp_path / "config.json"

    dirty = app_menus._save_configuration(
        cfg,
        dirty=True,
        config_path=config_path,
        save_config_fn=lambda *_: (_ for _ in ()).throw(PermissionError("read-only filesystem")),
        confirm_fn=lambda *_: True,
    )

    out = capsys.readouterr().out
    assert dirty is True
    assert f"Failed to save config to {config_path}" in out
    assert "read-only filesystem" in out


def test_handle_config_menu_exit_stays_open_on_save_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = {"analyzed_programs_and_libraries": ["Demo"], "other_lib_dirs": []}
    config_path = tmp_path / "config.json"
    quit_calls: list[str] = []

    app_menus._handle_config_menu_exit(
        cfg,
        dirty=True,
        config_path=config_path,
        save_config_fn=lambda *_: (_ for _ in ()).throw(PermissionError("read-only filesystem")),
        confirm_fn=lambda *_: True,
        quit_app_fn=lambda: quit_calls.append("quit"),
    )

    out = capsys.readouterr().out
    assert quit_calls == []
    assert f"Failed to save config to {config_path}" in out
    assert "read-only filesystem" in out


def test_dump_menu_tools_menu_and_main_loop_cover_invalid_and_quit_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builtins, "input", make_input(["x", "q"]))
    outputs: list[str] = []
    original_emit = app_menus.emit_output
    app_menus.emit_output = _capture_output(outputs)
    try:
        with pytest.raises(_QuitSignalError):
            app_menus.dump_menu(
                {"debug": False},
                clear_screen_fn=lambda: None,
                print_menu_fn=lambda *args, **kwargs: None,
                menu_option_factory=_option,
                quit_app_fn=lambda: (_ for _ in ()).throw(_QuitSignalError()),
                confirm_fn=lambda *_: False,
                iter_loaded_projects_fn=lambda *_: iter(()),
                analyze_variables_fn=lambda *_args, **_kwargs: None,
            )
    finally:
        app_menus.emit_output = original_emit

    assert outputs == ["Invalid choice."]

    monkeypatch.setattr(builtins, "input", make_input(["12", "6", "new-dir", "y", "2", "1", "n", "q", "y"]))
    saves: list[tuple[Path, dict[str, object]]] = []
    graphics_calls: list[dict[str, object]] = []
    with pytest.raises(SystemExit):
        app_menus.config_menu(
            {
                "analyzed_programs_and_libraries": ["Demo"],
                "mode": "official",
                "scan_root_only": False,
                "fast_cache_validation": False,
                "program_dir": "old-dir",
                "ABB_lib_dir": "abb",
                "other_lib_dirs": [],
                "icf_dir": "icf",
                "debug": False,
            },
            config_path=Path("config.json"),
            clear_screen_fn=lambda: None,
            show_config_fn=lambda *_: None,
            print_menu_fn=lambda *args, **kwargs: None,
            menu_option_factory=_option,
            prompt_fn=lambda prompt, default=None: builtins.input(prompt),
            pause_fn=lambda: None,
            confirm_fn=lambda *_: builtins.input("confirm") == "y",
            target_exists_fn=lambda *_: True,
            save_config_fn=lambda path, cfg: saves.append((path, dict(cfg))),
            apply_debug_fn=lambda *_: None,
            graphics_rules_menu_fn=lambda cfg: graphics_calls.append(dict(cfg)),
            quit_app_fn=lambda: None,
        )
    assert graphics_calls
    assert saves and saves[0][0] == Path("config.json")

    monkeypatch.setattr(builtins, "input", make_input(["x", "q"]))
    outputs = []
    original_emit = app_menus.emit_output
    app_menus.emit_output = _capture_output(outputs)
    try:
        with pytest.raises(_QuitSignalError):
            app_menus.tools_menu(
                {},
                clear_screen_fn=lambda: None,
                print_menu_fn=lambda *args, **kwargs: None,
                menu_option_factory=_option,
                quit_app_fn=lambda: (_ for _ in ()).throw(_QuitSignalError()),
                self_check_fn=lambda *_: True,
                pause_fn=lambda: outputs.append("pause"),
                require_targets_for_menu_action_fn=lambda *_: False,
                dump_menu_fn=lambda *_: None,
                run_source_diff_report_fn=lambda *_: None,
                confirm_fn=lambda *_: False,
                force_refresh_ast_fn=lambda *_: None,
            )
    finally:
        app_menus.emit_output = original_emit
    assert outputs[:2] == ["Invalid choice.", "pause"]

    monkeypatch.setattr(builtins, "input", make_input(["x", "q"]))
    outputs = []
    original_emit = app_menus.emit_output
    app_menus.emit_output = _capture_output(outputs)
    try:
        with pytest.raises(_QuitSignalError):
            app_menus.run_main_loop(
                {},
                clear_screen_fn=lambda: None,
                print_menu_fn=lambda *args, **kwargs: None,
                menu_option_factory=_option,
                summarize_targets_fn=lambda *_: "summary",
                require_targets_for_menu_action_fn=lambda *_: False,
                analysis_menu_fn=lambda *_: None,
                documentation_menu_fn=lambda *_: False,
                config_menu_fn=lambda *_: False,
                tools_menu_fn=lambda *_: None,
                show_help_fn=lambda *_: None,
                pause_fn=lambda: outputs.append("pause"),
                confirm_fn=lambda *_: False,
                save_config_fn=lambda *_: None,
                config_path=Path("config.json"),
                quit_app_fn=lambda: (_ for _ in ()).throw(_QuitSignalError()),
            )
    finally:
        app_menus.emit_output = original_emit
    assert outputs == ["Invalid choice."]


def test_menu_helpers_handle_keyboard_interrupt_and_return_to_current_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs: list[str] = []
    original_emit = app_menus.emit_output
    app_menus.emit_output = _capture_output(outputs)
    try:
        monkeypatch.setattr(builtins, "input", make_input(["1", "b"]))
        app_menus.tools_menu(
            {"analyzed_programs_and_libraries": ["TargetA"]},
            clear_screen_fn=lambda: None,
            print_menu_fn=lambda *args, **kwargs: None,
            menu_option_factory=_option,
            quit_app_fn=lambda: (_ for _ in ()).throw(_QuitSignalError()),
            self_check_fn=lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()),
            pause_fn=lambda: outputs.append("pause"),
            require_targets_for_menu_action_fn=lambda *_: True,
            dump_menu_fn=lambda *_: None,
            run_source_diff_report_fn=lambda *_: None,
            confirm_fn=lambda *_: True,
            force_refresh_ast_fn=lambda *_: None,
        )
    finally:
        app_menus.emit_output = original_emit

    assert any("Operation canceled. Returning to the menu." in line for line in outputs)
    assert outputs.count("pause") == 1
