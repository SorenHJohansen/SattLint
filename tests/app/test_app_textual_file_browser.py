# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnusedImport=false
"""Directory browser widget behavior."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sattlint import ui as app_textual
from sattlint.ui import _app_textual_shared as app_textual_shared_module
from sattlint.ui import _app_textual_widgets as app_textual_widgets_module
from tests.helpers.app_textual_support import (  # noqa: F401  (autouse fixtures)
    isolate_app_config_path,
    isolate_textual_projects,
    make_textual_app,
)


def test_textual_file_browser_selection_raises_when_required_widgets_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(
        start_paths=[Path(".")],
        candidates=(("demo", ("demo.x",)),),
    )

    def _raise_missing(*_args: Any, **_kwargs: Any) -> object:
        raise LookupError("missing file browser widget")

    monkeypatch.setattr(browser, "query_exactly_one", _raise_missing, raising=False)
    monkeypatch.setattr(browser, "query_one", _raise_missing)

    with pytest.raises(LookupError, match="missing file browser widget"):
        browser._set_candidate_selection(None)


def test_textual_file_browser_select_labels_folder_when_filtering_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], file_suffix=".slproj")
    select_button = SimpleNamespace(label="Select", disabled=True)
    widgets: dict[str, object] = {
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": select_button,
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )

    browser._update_selection(tmp_path)

    assert select_button.label == "Open folder"
    assert select_button.disabled is False


def test_textual_file_browser_select_navigates_into_folder_when_filtering_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    folder = tmp_path / "OG-batchrapporter"
    folder.mkdir()
    (folder / ".slproj").write_text("slproj_version = 1\n")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], file_suffix=".slproj")
    dismissed: list[object] = []
    tree = SimpleNamespace(path=None)
    widgets: dict[str, object] = {
        "#file-browser-tree": tree,
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": SimpleNamespace(label="Select", disabled=True),
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )
    browser.dismiss = lambda result: dismissed.append(result)

    browser._current_path = folder
    browser.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="file-browser-select")))

    assert dismissed == []
    assert tree.path == folder
    assert browser._current_path is None


def test_textual_file_browser_select_dismisses_file_when_filtering_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    project_file = tmp_path / "demo.slproj"
    project_file.write_text("slproj_version = 1\n")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], file_suffix=".slproj")
    dismissed: list[object] = []
    widgets: dict[str, object] = {
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": SimpleNamespace(label="Select", disabled=True),
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )
    browser.dismiss = lambda result: dismissed.append(result)

    browser._current_path = project_file
    browser.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="file-browser-select")))

    assert dismissed == [project_file]


def test_textual_file_browser_directory_only_disables_select_for_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], directory_only=True)
    file_path = tmp_path / "Program.s"
    file_path.write_text("draft")
    select_button = SimpleNamespace(label="Select", disabled=True)
    widgets: dict[str, object] = {
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": select_button,
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )

    browser._update_selection(file_path)
    assert select_button.disabled is True

    browser._update_selection(tmp_path)
    assert select_button.label == "Select folder"
    assert select_button.disabled is False


def test_textual_file_browser_directory_only_ignores_file_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[tmp_path], directory_only=True)
    file_path = tmp_path / "Program.s"
    file_path.write_text("draft")
    dismissed: list[object] = []
    browser.dismiss = lambda result: dismissed.append(result)

    browser.on_directory_tree_file_selected(SimpleNamespace(path=file_path))
    assert dismissed == []

    browser.on_directory_tree_file_selected(SimpleNamespace(path=tmp_path))
    assert dismissed == [tmp_path]


def test_textual_file_browser_directory_only_tree_hides_files(tmp_path: Path) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    subdir = tmp_path / "sub"
    subdir.mkdir()
    file_path = tmp_path / "Program.s"
    file_path.write_text("draft")

    class _TreeHost(app_textual_shared_module._TEXTUAL_APP):
        def compose(self) -> Any:
            yield app_textual_widgets_module._FilteredDirectoryTree(
                str(tmp_path), directory_only=True, id="file-browser-tree"
            )

    async def _run() -> None:
        async with _TreeHost().run_test() as pilot:
            await pilot.pause()
            tree = pilot.app.query_one("#file-browser-tree")
            result = list(tree.filter_paths([subdir, file_path]))
            assert result == [subdir]

    asyncio.run(_run())


def test_textual_file_browser_directory_only_go_up_navigates_to_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    start_path = tmp_path / "start"
    start_path.mkdir()
    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[start_path], directory_only=True)
    tree = SimpleNamespace(path=str(start_path))
    select_button = SimpleNamespace(label="Select folder", disabled=True)
    up_button = SimpleNamespace(disabled=True)
    widgets: dict[str, object] = {
        "#file-browser-tree": tree,
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": select_button,
        "#file-browser-up": up_button,
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )

    browser.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="file-browser-up")))

    assert Path(tree.path) == tmp_path
    assert browser._current_path == tmp_path
    assert select_button.label == "Select folder"
    assert select_button.disabled is False
    assert up_button.disabled is False


def test_textual_file_browser_directory_only_up_button_disabled_at_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    filesystem_root = Path(tmp_path.anchor)
    browser = app_textual_widgets_module._FileBrowserScreen(start_paths=[filesystem_root], directory_only=True)
    tree = SimpleNamespace(path=str(filesystem_root))
    up_button = SimpleNamespace(disabled=False)
    widgets: dict[str, object] = {
        "#file-browser-tree": tree,
        "#file-browser-selection": SimpleNamespace(update=lambda text: None),
        "#file-browser-select": SimpleNamespace(label="Select folder", disabled=True),
        "#file-browser-up": up_button,
    }
    monkeypatch.setattr(
        app_textual_widgets_module,
        "_query_required",
        lambda _owner, selector, _expected_type=None: widgets[selector],
    )

    browser._refresh_up_button(filesystem_root)
    assert up_button.disabled is True

    browser.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id="file-browser-up")))
    assert tree.path == str(filesystem_root)
    assert browser._current_path is None


@pytest.mark.parametrize(
    "button_id, field_key, is_list",
    [
        ("setup-edit-program-dir", "program_dir", False),
        ("setup-edit-abb-dir", "ABB_lib_dir", False),
        ("setup-edit-other-lib-dirs", "other_lib_dirs", True),
        ("setup-edit-icf-dir", "icf_dir", False),
    ],
)
def test_textual_setup_dir_buttons_push_directory_only_picker(
    monkeypatch: pytest.MonkeyPatch, button_id: str, field_key: str, is_list: bool
) -> None:
    if not app_textual.has_textual():
        pytest.skip("Textual not installed")

    cfg: dict[str, Any] = {
        "analyzed_programs_and_libraries": [],
        "program_dir": "",
        "ABB_lib_dir": "",
        "other_lib_dirs": [],
        "icf_dir": "",
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

    app_instance.on_button_pressed(SimpleNamespace(button=SimpleNamespace(id=button_id)))

    assert len(pushed) == 1
    screen, _callback = pushed[0]
    assert isinstance(screen, app_textual_widgets_module._FileBrowserScreen)
    assert screen._directory_only is True


def test_textual_file_browser_duplicate_target_leaves_other_lib_dirs_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": ["DemoTarget"]})
    messages: list[str] = []
    replacements: list[object] = []
    target_file = tmp_path / "DemoTarget.s"
    target_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(app_instance, "_write_output", lambda text: messages.append(text))
    monkeypatch.setattr(
        app_instance,
        "_replace_setup_list_value",
        lambda *args, **_kwargs: replacements.append(args),
    )

    app_instance._add_target_from_path(target_file)

    assert not app_instance._cfg.get("other_lib_dirs")
    assert replacements == []
    assert messages == ["Target 'DemoTarget' is already configured."]


def test_textual_file_browser_add_records_target_and_containing_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app_instance = make_textual_app(cfg={"analyzed_programs_and_libraries": []})
    target_file = tmp_path / "NewTarget.s"
    target_file.write_text("", encoding="utf-8")

    monkeypatch.setattr(app_instance, "_refresh_summary", lambda: None)
    monkeypatch.setattr(app_instance, "_refresh_view", lambda: None)
    monkeypatch.setattr(app_instance, "_set_active_action", lambda _action_id: None)
    monkeypatch.setattr(app_instance, "_refresh_shell_state", lambda: None)
    monkeypatch.setattr(app_instance, "_write_output", lambda _text: None)

    app_instance._add_target_from_path(target_file)

    assert app_instance._cfg["other_lib_dirs"] == [str(tmp_path)]
    assert app_instance._cfg["analyzed_programs_and_libraries"] == ["NewTarget"]
    assert app_instance._dirty is False
