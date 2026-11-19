# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnusedImport=false
"""Program directory, library directories, and directory pickers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from sattlint import ui as app_textual
from sattlint.ui import _app_textual_shared as app_textual_shared_module
from sattlint.ui import _app_textual_widgets as app_textual_widgets_module
from tests.helpers.app_textual_support import (  # noqa: F401  (autouse fixtures)
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
    typed_cfg,
)


def test_textual_setup_remove_other_lib_dir_presents_menu(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": ["/libs/one", "/libs/two", "/libs/three"],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._remove_other_lib_dir()

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "menu"
    assert [option.label for option in request.options] == ["/libs/one", "/libs/two", "/libs/three"]

    callback = captured["callback"]
    assert callable(callback)
    callback("2")

    assert cfg["other_lib_dirs"] == ["/libs/one", "/libs/three"]
    assert app_instance._dirty is True
    assert messages == ["Removed extra library folder '/libs/two' from the Setup view."]


def test_textual_setup_remove_other_lib_dir_ignores_invalid_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": ["/libs/one", "/libs/two"],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._remove_other_lib_dir()
    callback = captured["callback"]
    assert callable(callback)
    callback("9")
    callback("abc")
    callback(None)

    assert cfg["other_lib_dirs"] == ["/libs/one", "/libs/two"]
    assert messages == []


def test_textual_setup_remove_other_lib_dir_empty_writes_message(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "present_request", lambda *args, **kwargs: captured.setdefault("called", True))

    app_instance._remove_other_lib_dir()

    assert "called" not in captured
    assert messages == ["No extra library folders are configured to remove."]


def test_textual_setup_remove_other_lib_dir_button_state() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={
                "analyzed_programs_and_libraries": [],
                "program_dir": "",
                "ABB_lib_dir": "",
                "other_lib_dirs": [],
                "mode": "draft",
            }
        )
        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()
            assert getattr(app_instance.query_one("#setup-edit-other-lib-dirs-remove"), "disabled", False) is True

    asyncio.run(_run())


def test_textual_setup_remove_other_lib_dir_button_enabled_with_entries() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={
                "analyzed_programs_and_libraries": [],
                "program_dir": "",
                "ABB_lib_dir": "",
                "other_lib_dirs": ["/libs/one"],
                "mode": "draft",
            }
        )
        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+3")
            await pilot.pause()
            assert getattr(app_instance.query_one("#setup-edit-other-lib-dirs-remove"), "disabled", False) is False

    asyncio.run(_run())


def test_textual_setup_prompt_updates_program_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    new_program_dir = tmp_path / "new-programs"
    new_program_dir.mkdir()
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "/old/programs",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._prompt_setup_value("program_dir", label="program_dir")

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert request.default == "/old/programs"

    callback = captured["callback"]
    assert callable(callback)
    callback(str(new_program_dir))

    assert cfg["program_dir"] == str(new_program_dir)
    assert app_instance._dirty is True
    assert messages == ["Updated program_dir from the Setup view."]


def test_textual_setup_prompt_replaces_whole_other_lib_dirs_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_lib_a = tmp_path / "new-lib-a"
    new_lib_b = tmp_path / "new-lib-b"
    new_lib_a.mkdir()
    new_lib_b.mkdir()
    original_other_dirs = ["/old/lib-a", "/old/lib-b"]
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "/old/programs",
        "ABB_lib_dir": "",
        "other_lib_dirs": original_other_dirs,
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    captured: dict[str, object] = {}
    messages: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._prompt_setup_value("other_lib_dirs", label="other_lib_dirs", is_list=True)

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert request.message == "Enter one folder per line for other_lib_dirs. Leave blank to clear the list."
    assert request.default == "/old/lib-a\n/old/lib-b"

    callback = captured["callback"]
    assert callable(callback)
    callback(f"{new_lib_a}\n{new_lib_b}")

    assert cfg["other_lib_dirs"] == [str(new_lib_a), str(new_lib_b)]
    assert cfg["other_lib_dirs"] is not original_other_dirs
    assert app_instance._dirty is True
    assert messages == ["Updated other_lib_dirs from the Setup view."]


def test_textual_setup_dir_picker_pushes_browser_and_applies_program_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []
    pushed: list[tuple[Any, Any]] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance._open_dir_picker("program_dir", label="program_dir")

    assert len(pushed) == 1
    screen, callback = pushed[0]
    assert isinstance(screen, app_textual_widgets_module._FileBrowserScreen)
    assert screen._directory_only is True
    assert callable(callback)

    callback(program_dir)
    assert cfg["program_dir"] == str(program_dir)
    assert app_instance._dirty is True
    assert messages == ["Updated program_dir from the Setup view."]


def test_textual_setup_dir_picker_ignores_non_path_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "/existing",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance._open_dir_picker("program_dir", label="program_dir")
    _, callback = pushed[0]
    callback("not-a-path")
    assert cfg["program_dir"] == "/existing"


def test_textual_setup_dir_picker_appends_to_other_lib_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")
    extra_dir = tmp_path / "extra"
    extra_dir.mkdir()
    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": ["/old/lib"],
        "mode": "draft",
    }
    app_instance = app_textual.SattLintTextualApp(
        cfg=cfg,
        summarize_targets_fn=lambda _cfg: "targets",
        save_config_fn=lambda _path, _cfg: None,
        config_path=None,
        quit_app_error=RuntimeError,
    )
    messages: list[str] = []
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    app_instance._open_dir_picker("other_lib_dirs", label="other_lib_dirs", is_list=True)
    _, callback = pushed[0]
    callback(extra_dir)
    assert cfg["other_lib_dirs"] == ["/old/lib", str(extra_dir)]
    assert messages == ["Updated other_lib_dirs from the Setup view."]


def test_discover_setup_target_candidates_collects_preview_files(tmp_path: Path) -> None:
    program_dir = tmp_path / "programs"
    abb_dir = tmp_path / "abb"
    program_dir.mkdir()
    abb_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")
    (program_dir / "TargetA.l").write_text("deps")
    (abb_dir / "TargetA.x").write_text("official")
    (abb_dir / "TargetB.s").write_text("draft-only")

    candidates = app_textual.discover_setup_target_candidates(
        typed_cfg(
            {
                "program_dir": str(program_dir),
                "ABB_lib_dir": str(abb_dir),
                "other_lib_dirs": [],
                "mode": "official",
            }
        )
    )

    assert [candidate.name for candidate in candidates] == ["TargetA", "TargetB"]
    assert [path.name for path in candidates[0].files] == ["TargetA.l", "TargetA.s", "TargetA.x"]
    assert candidates[0].available is True
    assert candidates[1].available is False
