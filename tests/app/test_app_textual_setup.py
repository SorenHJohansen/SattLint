# pyright: reportPrivateUsage=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
"""Setup view, target selection, and project opening."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint import ui as app_textual
from sattlint.config.string_capacities import STRING_CAPACITY_KEYS
from sattlint.project.io import init_project, load_project
from sattlint.ui import _app_textual_actions as app_textual_actions_module
from sattlint.ui import _app_textual_shared as app_textual_shared_module
from sattlint.ui import _app_textual_widgets as app_textual_widgets_module
from tests.helpers.app_textual_support import (
    attach_test_project,
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
    query_any_screen,
)

# Re-export the autouse fixtures so pytest registers them for this module.
__all__ = [
    "isolate_app_config_path",
    "isolate_textual_projects",
]


def test_textual_setup_browser_gains_config_mode_class_when_dirty() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+4")
            await pilot.pause()

            setup_browser = app_instance.query_one("#setup-browser")
            assert setup_browser.has_class("config-mode") is False

            app_instance._dirty = True
            app_instance._refresh_view()
            await pilot.pause()
            assert setup_browser.has_class("config-mode") is True

    asyncio.run(_run())


def test_textual_setup_view_shows_selected_target_preview(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        program_dir = tmp_path / "programs"
        abb_dir = tmp_path / "abb"
        program_dir.mkdir()
        abb_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")
        (program_dir / "TargetA.l").write_text("deps")
        (abb_dir / "TargetA.x").write_text("official")

        cfg: dict[str, object] = {
            "analyzed_programs_and_libraries": [],
            "program_dir": str(program_dir),
            "ABB_lib_dir": str(abb_dir),
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
        attach_test_project(app_instance)

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+3")
            await pilot.pause()

            workspace_host = app_instance.query_one("#workspace-host")
            view_title = app_instance.query_one("#view-title")
            output_pane = app_instance.query_one("#output-pane")
            browse_button = app_instance.query_one("#setup-target-browse")
            remove_button = app_instance.query_one("#setup-target-remove")
            program_button = app_instance.query_one("#setup-edit-program-dir")
            targets_col = app_instance.query_one("#setup-targets-col")
            settings_col = app_instance.query_one("#setup-settings-col")
            assert app_instance._active_view == "setup"
            assert workspace_host.has_class("no-output")
            assert str(view_title.renderable) == "Configuration Settings"
            assert output_pane.has_class("is-hidden") is True
            assert app_instance.query_one("#setup-browser").has_class("is-hidden") is False
            assert str(getattr(browse_button, "label", "")) == "Add"
            assert str(getattr(program_button, "label", "")) == "Change folder"
            assert targets_col is not None
            assert settings_col is not None
            assert str(app_instance.query_one("#setup-label-program-dir").renderable) == (
                f"{program_dir.name}\n{program_dir}"
            )
            assert str(app_instance.query_one("#setup-label-abb-dir").renderable) == f"{abb_dir.name}\n{abb_dir}"
            assert str(app_instance.query_one("#setup-label-other-dirs").renderable) == "No extra libraries"
            assert str(app_instance.query_one("#setup-label-icf-dir").renderable) == "Not configured"
            assert str(app_instance.query_one("#setup-label-mode").renderable) == "Draft mode\n.s and .l files"

            targets_section = app_instance.query_one("#setup-targets-section")
            settings_section = app_instance.query_one("#setup-settings-section")
            assert targets_section.region.x < settings_section.region.x
            assert targets_col.region.width > 0
            assert settings_col.region.width > 0
            assert browse_button.region.x >= targets_col.region.x
            assert browse_button.region.x < settings_col.region.x
            # Remove is disabled when nothing is selected
            assert getattr(remove_button, "disabled", False) is True

    asyncio.run(_run())


def test_textual_setup_target_list_keeps_its_highlight_across_a_rebuild() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app(
            cfg={"analyzed_programs_and_libraries": ["TargetA", "TargetB"]},
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+3")
            await pilot.pause()

            app_instance._selected_configured_target = "TargetB"
            app_instance._refresh_setup_target_list()
            await pilot.pause()

            list_view = app_instance.query_one("#setup-target-listview")
            assert list_view.index == 1

            # Adding a target rebuilds the list; the selection must survive it.
            app_instance._cfg["analyzed_programs_and_libraries"] = ["TargetA", "TargetB", "TargetC"]
            app_instance._refresh_setup_target_list()
            for _ in range(10):
                await pilot.pause()
                if list_view.index == 1:
                    break

            assert app_instance._selected_configured_target == "TargetB"
            assert list_view.index == 1
            assert app_instance.query_one("#setup-target-remove").disabled is False

    asyncio.run(_run())


def test_textual_project_picker_selects_the_first_project_after_mount(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    for name in ("Alpha", "Beta"):
        (tmp_path / f"{name}.slproj").write_text("{}", encoding="utf-8")

    async def _run() -> None:
        app_instance = make_textual_app(project=False)
        screen = app_textual_widgets_module._ProjectPickerScreen(projects_dir=tmp_path)

        async with app_instance.run_test() as pilot:
            app_instance.push_screen(screen)
            await pilot.pause()
            await pilot.pause()

            assert screen._selected_path == tmp_path / "Alpha.slproj"
            assert screen.query_one("#project-picker-open").disabled is False
            assert screen.query_one("#project-picker-delete").disabled is False
            assert screen.query_one("#project-picker-list").index == 0

    asyncio.run(_run())


def test_textual_project_picker_opens_a_path_outside_the_config_directory(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    project_path = tmp_path / "checked-in" / "app.slproj"
    project_path.parent.mkdir()
    init_project(project_path)

    async def _run() -> None:
        app_instance = make_textual_app(project=False)

        async with app_instance.run_test() as pilot:
            app_instance._open_project_browser()
            await pilot.pause()

            screen = app_instance.screen
            screen.query_one("#project-picker-path").value = str(project_path)
            await pilot.pause()
            assert screen.query_one("#project-picker-open").disabled is False

            await pilot.click("#project-picker-open")
            await pilot.pause()

        assert app_instance._project_path == project_path

    asyncio.run(_run())


def test_textual_setup_shows_empty_dirs_when_no_configuration_is_open() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        cfg = {
            "analyzed_programs_and_libraries": [],
            "program_dir": "/some/program/dir",
            "ABB_lib_dir": "/some/abb",
            "other_lib_dirs": ["/some/lib1"],
            "icf_dir": "/some/icf",
            "mode": "official",
        }
        app_instance = app_textual.SattLintTextualApp(
            cfg=cfg,
            summarize_targets_fn=lambda _cfg: "targets",
            save_config_fn=lambda _path, _cfg: None,
            config_path=None,
            quit_app_error=RuntimeError,
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()

            assert app_instance._project_loaded() is False
            for label_id in (
                "setup-label-program-dir",
                "setup-label-abb-dir",
                "setup-label-other-dirs",
                "setup-label-icf-dir",
            ):
                assert str(app_instance.query_one(f"#{label_id}").renderable) == ""

    asyncio.run(_run())


def test_textual_setup_browse_filters_targets_by_mode_without_extensions(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        program_dir = tmp_path / "programs"
        abb_dir = tmp_path / "abb"
        program_dir.mkdir()
        abb_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")
        (program_dir / "TargetA.l").write_text("deps")
        (abb_dir / "TargetA.x").write_text("official")
        (abb_dir / "Other.z").write_text("other")

        app_instance = make_textual_app(
            cfg={
                "analyzed_programs_and_libraries": [],
                "program_dir": str(program_dir),
                "ABB_lib_dir": str(abb_dir),
                "other_lib_dirs": [],
                "mode": "draft",
            }
        )

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+3")
            await pilot.pause()

            browse_button = app_instance.query_one("#setup-target-browse")
            app_instance.on_button_pressed(SimpleNamespace(button=browse_button))
            await pilot.pause()

            assert query_any_screen(app_instance, "#file-browser-dialog") is not None
            tree = query_any_screen(app_instance, "#file-browser-tree")
            assert tree is not None

            await pilot.pause(0.5)
            labels = [str(getattr(child, "label", "")) for child in tree.root.children]

            # Draft mode shows .s/.l targets as stems only, never the .x/.z files.
            assert "TargetA" in labels
            assert "TargetA.s" not in labels and "TargetA.l" not in labels
            assert "Other" not in labels

    asyncio.run(_run())


def test_textual_setup_target_button_click_adds_and_removes_target(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        program_dir = tmp_path / "programs"
        program_dir.mkdir()
        (program_dir / "TargetA.s").write_text("draft")

        cfg: dict[str, object] = {
            "analyzed_programs_and_libraries": [],
            "program_dir": str(program_dir),
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

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+4")
            await pilot.pause()

            # Add target programmatically (file browser not testable in headless mode)
            app_instance._add_selected_setup_target("TargetA")
            await pilot.pause()

            assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]

            # Select target via _selected_configured_target (simulating ListView highlight)
            app_instance._selected_configured_target = "TargetA"
            await pilot.pause()

            assert app_instance._selected_configured_target == "TargetA"

            # Click remove to remove the selected target
            remove_button = app_instance.query_one("#setup-target-remove")
            app_instance.on_button_pressed(SimpleNamespace(button=remove_button))
            await pilot.pause()

            assert cfg["analyzed_programs_and_libraries"] == []
            assert app_instance._selected_configured_target is None

    asyncio.run(_run())


def test_textual_setup_add_selected_target_marks_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")

    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": str(program_dir),
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

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    app_instance._active_view = "setup"
    original_targets = cfg["analyzed_programs_and_libraries"]

    app_instance._add_selected_setup_target()

    assert cfg["analyzed_programs_and_libraries"] == ["TargetA"]
    assert cfg["analyzed_programs_and_libraries"] is not original_targets
    assert app_instance._dirty is True
    assert messages == ["Added analysis target 'TargetA' from the Setup view."]


def test_textual_setup_remove_selected_target_marks_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    program_dir = tmp_path / "programs"
    program_dir.mkdir()
    (program_dir / "TargetA.s").write_text("draft")

    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": ["TargetA"],
        "program_dir": str(program_dir),
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

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    app_instance._active_view = "setup"
    original_targets = cfg["analyzed_programs_and_libraries"]

    app_instance._remove_selected_setup_target()

    assert cfg["analyzed_programs_and_libraries"] == []
    assert cfg["analyzed_programs_and_libraries"] is not original_targets
    assert app_instance._dirty is True
    assert messages == ["Removed analysis target 'TargetA' from the Setup view."]


def test_textual_new_project_creates_project_at_the_entered_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_dir = tmp_path / "new-project-root"
    projects_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "sattlint.config.paths.get_projects_dir",
        lambda: projects_dir,
    )
    monkeypatch.chdir(tmp_path)

    app_instance = make_textual_app(project=False)
    captured: dict[str, object] = {}
    messages: list[str] = []
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))

    def _capture_request(
        request: app_textual_shared_module.InteractionRequest, on_response_fn: object | None = None
    ) -> None:
        captured["request"] = request
        captured["callback"] = on_response_fn

    monkeypatch.setattr(app_instance, "present_request", _capture_request)

    app_instance._new_project()

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert request.default == str(tmp_path / "project.slproj")
    assert "current directory" in (request.note or "")

    callback = captured["callback"]
    assert callable(callback)
    callback("My Demo Project")

    project_file = tmp_path / "My Demo Project.slproj"
    assert project_file.is_file()
    assert not projects_dir.exists() or not list(projects_dir.iterdir())
    scaffolded = load_project(project_file)
    assert scaffolded.data["slproj_version"] == 2
    assert scaffolded.data["string_capacities"] == {
        "identstring": 15,
        "tagstring": 30,
        "string": 40,
        "linestring": 80,
        "maxstring": 140,
    }
    assert app_instance._project is not None
    assert app_instance._project_loaded() is True
    assert app_instance._project_path == project_file
    assert "Created configuration" in messages[0]
    assert str(project_file) in messages[0]

    # Reject an existing project path.
    callback(None)
    callback("My Demo Project")
    assert any("already exists" in message for message in messages)


def test_textual_setup_change_autosaves_to_slproj(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    project_path = app_instance._project.path

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda text: None)
    app_instance._active_view = "setup"

    app_instance._cfg["program_dir"] = "/some/program/dir"
    app_instance._mark_setup_changed("updated")

    assert app_instance._dirty is False
    saved = load_project(project_path)
    assert saved.data["program_dir"] == "/some/program/dir"
    assert saved.data["allow_external_roots"] is True
    assert saved.data["slproj_version"] == 2
    assert saved.data["string_capacities"] == {
        "identstring": 15,
        "tagstring": 30,
        "string": 40,
        "linestring": 80,
        "maxstring": 140,
    }
    assert saved.data["analyzers"] == []


def test_textual_setup_shows_the_five_string_capacities() -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    async def _run() -> None:
        app_instance = make_textual_app()

        async with app_instance.run_test() as pilot:
            await pilot.press("ctrl+3")
            await pilot.pause()

            assert app_instance.query_one("#setup-group-capacities") is not None
            labels = {
                key: str(app_instance.query_one(f"#setup-label-capacity-{key}").renderable)
                for key in STRING_CAPACITY_KEYS
            }
            assert labels == {
                "identstring": "15",
                "tagstring": "30",
                "string": "40",
                "linestring": "80",
                "maxstring": "140",
            }
            assert app_instance.query_one("#setup-edit-capacity-string").disabled is False

    asyncio.run(_run())


def test_textual_setup_string_capacity_button_opens_a_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        app_instance,
        "present_request",
        lambda request, on_response_fn=None: captured.update(request=request, callback=on_response_fn),
    )

    app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="setup-edit-capacity-linestring")))

    request = captured["request"]
    assert isinstance(request, app_textual_shared_module.InteractionRequest)
    assert request.kind == "prompt"
    assert request.default == "80"
    assert request.message is not None
    assert "positive integer" in request.message


def test_textual_setup_string_capacity_edit_saves_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    project_path = app_instance._project.path
    captured: dict[str, Any] = {}
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        app_instance,
        "present_request",
        lambda request, on_response_fn=None: captured.update(request=request, callback=on_response_fn),
    )
    monkeypatch.setattr(app_instance, "_report_error", lambda title, message: errors.append((title, message)))
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda _text: None)

    app_instance._prompt_string_capacity("string", label="string capacity")
    captured["callback"]("25")

    assert errors == []
    saved = load_project(project_path)
    assert saved.data["string_capacities"] == {
        "identstring": 15,
        "tagstring": 30,
        "string": 25,
        "linestring": 80,
        "maxstring": 140,
    }


def test_textual_setup_string_capacity_edit_rejects_non_positive_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_instance = make_textual_app()
    project_path = app_instance._project.path
    captured: dict[str, Any] = {}
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        app_instance,
        "present_request",
        lambda request, on_response_fn=None: captured.update(request=request, callback=on_response_fn),
    )
    monkeypatch.setattr(app_instance, "_report_error", lambda title, message: errors.append((title, message)))

    app_instance._prompt_string_capacity("string", label="string capacity")
    for raw_value in ("0", "-4", "not a number", ""):
        captured["callback"](raw_value)

    assert errors == [("Invalid value", "string capacity must be a positive integer.")] * 4
    saved = load_project(project_path)
    assert saved.data["string_capacities"]["string"] == 40


def test_textual_persist_project_keeps_capacities_and_analyzers() -> None:
    app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["TargetA"]})
    assert "string_capacities" not in app_instance._cfg
    app_instance._project.data["analyzers"] = ["variables", "sfc"]

    assert app_instance._persist_project() is True

    saved = load_project(app_instance._project.path)
    assert saved.data["slproj_version"] == 2
    assert saved.data["analyzers"] == ["variables", "sfc"]
    assert saved.data["string_capacities"] == {
        "identstring": 15,
        "tagstring": 30,
        "string": 40,
        "linestring": 80,
        "maxstring": 140,
    }


def test_textual_setup_save_failure_keeps_the_dirty_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    app_instance = make_textual_app()
    errors: list[str] = []

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda _text: None)
    monkeypatch.setattr(app_instance, "_report_error", lambda title, message: errors.append(f"{title}: {message}"))
    monkeypatch.setattr(
        app_textual_actions_module,
        "_save_slproj",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("read-only configuration")),
    )
    app_instance._active_view = "setup"

    app_instance._cfg["program_dir"] = "/some/program/dir"
    app_instance._mark_setup_changed("updated")

    assert app_instance._dirty is True
    assert errors == ["Failed to save configuration: Failed to save configuration: read-only configuration"]


def test_textual_open_project_loads_and_unlocks_views(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app_instance = make_textual_app(project=False)
    assert app_instance._project_loaded() is False

    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)

    project_dir = tmp_path / "opened-project"
    project = init_project(project_dir / ".slproj")
    project.data["analyzed_programs_and_libraries"] = ["TargetA"]

    app_instance._load_project_object(project)

    assert app_instance._project_loaded() is True
    assert app_instance._project_path == project.path
    assert app_instance._cfg["analyzed_programs_and_libraries"] == ["TargetA"]


def test_textual_open_project_refreshes_ast_cache_before_interaction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    refreshed_cfgs: list[object] = []
    app_instance = make_textual_app(
        project=False,
        ensure_ast_cache_fn=lambda _cfg, *, emit_output_fn=None: (
            refreshed_cfgs.append(_cfg),
            emit_output_fn("Checking AST cache for Demo") if emit_output_fn is not None else None,
            True,
        )[2],
    )

    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda _text: None)
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    project_dir = tmp_path / "opened-project"
    project = init_project(project_dir / ".slproj")
    project.data["analyzed_programs_and_libraries"] = ["TargetA"]

    app_instance._load_project_object(project)

    assert app_instance._ast_refresh_pending is True
    assert len(pushed) == 1
    screen, callback = pushed[0]
    assert isinstance(screen, app_textual_widgets_module._AstRefreshModalScreen)
    assert callable(callback)

    screen._refresh_fn(lambda _message: None)

    assert refreshed_cfgs == [app_instance._cfg]

    result = app_textual_widgets_module._AstRefreshModalResult(ok=True, output="Checking AST cache for Demo")
    callback(result)

    assert app_instance._ast_refresh_pending is False
    assert app_instance._interaction_locked() is False


def test_textual_open_project_without_targets_skips_ast_refresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_instance = make_textual_app(
        project=False,
        ensure_ast_cache_fn=lambda _cfg, *, emit_output_fn=None: True,
    )
    monkeypatch.setattr(app_instance, "_clear_session_output", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    pushed: list[tuple[Any, Any]] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append((screen, callback)))

    project_dir = tmp_path / "opened-project"
    project = init_project(project_dir / ".slproj")

    app_instance._load_project_object(project)

    assert pushed == []
    assert app_instance._ast_refresh_pending is False
    assert app_instance._interaction_locked() is False


def test_sanitize_project_name_preserves_spaces_and_strips_path_separators() -> None:
    assert app_textual_actions_module._sanitize_project_name("OG batchrapporter") == "OG batchrapporter"
    assert app_textual_actions_module._sanitize_project_name("  My   Project  ") == "My   Project"
    assert app_textual_actions_module._sanitize_project_name("a/b\\c") == "a-b-c"
    assert app_textual_actions_module._sanitize_project_name("  ") == "project"


def test_textual_make_project_relative_keeps_empty_paths_empty(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    elsewhere = tmp_path / "elsewhere"
    assert app_textual_actions_module._make_project_relative("", project_dir) == ""
    assert app_textual_actions_module._make_project_relative("   ", project_dir) == ""
    assert app_textual_actions_module._make_project_relative("relative/dir", project_dir) == "relative/dir"
    assert app_textual_actions_module._make_project_relative(str(project_dir / "icf"), project_dir) == "icf"
    assert app_textual_actions_module._make_project_relative(str(elsewhere), project_dir) == elsewhere.as_posix()


def test_textual_add_target_from_path_does_not_reannounce_an_unchanged_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": [], "program_dir": str(library_dir)})
    marked: list[str] = []
    messages: list[str] = []
    monkeypatch.setattr(app_instance, "_mark_setup_changed", lambda message, **kwargs: marked.append(message))
    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(str(text)))

    app_instance._add_target_from_path(library_dir)

    assert marked == []
    assert messages == [f"'{library_dir}' is already one of the configured folders."]


def test_textual_setup_prompt_rejects_a_folder_that_does_not_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg: dict[str, Any] = {"analyzed_programs_and_libraries": [], "program_dir": ""}
    app_instance = make_textual_app(cfg=cfg, project=False)
    captured: dict[str, Any] = {}
    errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        app_instance,
        "present_request",
        lambda request, on_response_fn=None: captured.update(request=request, callback=on_response_fn),
    )
    monkeypatch.setattr(app_instance, "_report_error", lambda title, message: errors.append((title, message)))

    app_instance._prompt_setup_value("program_dir", label="program_dir")
    captured["callback"]("/definitely/missing/folder")

    assert cfg["program_dir"] == ""
    assert errors == [("Invalid folder", "'/definitely/missing/folder' is not an existing folder.")]


def test_textual_open_configuration_menu_pushes_project_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_instance = make_textual_app()
    pushed: list[object] = []
    monkeypatch.setattr(app_instance, "push_screen", lambda screen, callback=None: pushed.append(screen))

    app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="menu-file-open-project")))
    assert len(pushed) == 1
    assert type(pushed[0]).__name__ == "_ProjectPickerScreenImpl"
