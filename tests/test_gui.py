from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("tkinter", exc_type=ImportError)

from sattlint_gui.frames.config_frame import ConfigFrame, apply_editable_config, extract_editable_config
from tests._gui_test_support import _FakeLabel, _FakeListbox, _FakeVar


def _make_config_frame_double(*, binding_obj: Any | None = None, full_config: dict | None = None) -> Any:
    fake_binding = binding_obj or SimpleNamespace(
        config_path="config.toml",
        graphics_rules_path=Path("graphics-rules.toml"),
        load_config=lambda: {},
        save_config=lambda _cfg: SimpleNamespace(ok=True, output="saved"),
        target_exists=lambda _target, _cfg: True,
    )
    frame = SimpleNamespace(
        binding=fake_binding,
        _loading=False,
        _dirty=False,
        _full_config=full_config or {},
        status=_FakeLabel(),
        targets_list=_FakeListbox(),
        other_libs_list=_FakeListbox(),
        mode_var=_FakeVar("official"),
        scan_root_only_var=_FakeVar(False),
        fast_cache_validation_var=_FakeVar(True),
        debug_var=_FakeVar(False),
        program_dir_var=_FakeVar(""),
        abb_lib_dir_var=_FakeVar(""),
        icf_dir_var=_FakeVar(""),
        graphics_rules_path_var=_FakeVar(""),
    )
    frame_any = cast(Any, frame)
    frame._refresh_status = lambda text=None: ConfigFrame._refresh_status(frame_any, text)
    frame._set_dirty = lambda value: ConfigFrame._set_dirty(frame_any, value)
    frame._set_listbox_items = lambda listbox, values: ConfigFrame._set_listbox_items(frame_any, listbox, values)
    frame._get_listbox_items = lambda listbox: ConfigFrame._get_listbox_items(frame_any, listbox)
    frame._current_editable_config = lambda: ConfigFrame._current_editable_config(frame_any)
    frame._preview_full_config = lambda: ConfigFrame._preview_full_config(frame_any)
    return frame


def test_extract_editable_config_normalizes_defaults():
    extracted = extract_editable_config({"mode": "draft", "program_dir": None, "other_lib_dirs": None})

    assert extracted["mode"] == "draft"
    assert extracted["program_dir"] == ""
    assert extracted["other_lib_dirs"] == []
    assert extracted["analyzed_programs_and_libraries"] == []


def test_apply_editable_config_preserves_nested_sections():
    base_cfg = {
        "mode": "official",
        "program_dir": "old-program",
        "analysis": {"keep": True},
        "documentation": {"classifications": {"em": {"name_contains": ["Equip"]}}},
    }
    editable_cfg = {
        "mode": "draft",
        "program_dir": "new-program",
        "ABB_lib_dir": "abb",
        "icf_dir": "icf",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "analyzed_programs_and_libraries": ["TargetA"],
        "other_lib_dirs": ["lib-a", "lib-b"],
    }

    merged = apply_editable_config(base_cfg, editable_cfg)

    assert merged["mode"] == "draft"
    assert merged["program_dir"] == "new-program"
    assert merged["analysis"] == {"keep": True}
    assert merged["documentation"] == {"classifications": {"em": {"name_contains": ["Equip"]}}}
    assert merged["analyzed_programs_and_libraries"] == ["TargetA"]
    assert merged["other_lib_dirs"] == ["lib-a", "lib-b"]


def test_config_frame_listbox_helpers_and_preview_config_without_tk_widgets():
    frame = _make_config_frame_double(full_config={"analysis": {"keep": True}})

    ConfigFrame._set_listbox_items(frame, frame.targets_list, [" TargetA ", "TargetB"])
    ConfigFrame._set_listbox_items(frame, frame.other_libs_list, [" lib-a ", "lib-b"])
    frame.mode_var.set("draft")
    frame.scan_root_only_var.set(True)
    frame.fast_cache_validation_var.set(False)
    frame.debug_var.set(True)
    frame.program_dir_var.set(" programs ")
    frame.abb_lib_dir_var.set(" abb ")
    frame.icf_dir_var.set(" icf ")

    current = ConfigFrame._current_editable_config(frame)
    preview = ConfigFrame._preview_full_config(frame)

    assert current == {
        "analyzed_programs_and_libraries": ["TargetA", "TargetB"],
        "mode": "draft",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "program_dir": "programs",
        "ABB_lib_dir": "abb",
        "icf_dir": "icf",
        "other_lib_dirs": ["lib-a", "lib-b"],
    }
    assert preview["analysis"] == {"keep": True}
    assert preview["program_dir"] == "programs"
    assert preview["other_lib_dirs"] == ["lib-a", "lib-b"]


def test_config_frame_browse_directory_and_target_addition_without_tk_widgets(monkeypatch):
    warnings: list[str] = []
    errors: list[str] = []
    binding_obj = SimpleNamespace(
        config_path="config.toml",
        graphics_rules_path=Path("graphics-rules.toml"),
        load_config=lambda: {},
        save_config=lambda _cfg: SimpleNamespace(ok=True, output="saved"),
        target_exists=lambda target, _cfg: target == "TargetC",
    )
    frame = _make_config_frame_double(binding_obj=binding_obj)
    frame.targets_list.items = ["TargetA"]
    variable = _FakeVar("")

    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "")
    ConfigFrame._browse_directory(frame, cast(Any, variable))
    assert variable.get() == ""

    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "Programs")
    ConfigFrame._browse_directory(frame, cast(Any, variable))
    assert variable.get() == "Programs"

    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.messagebox.showwarning", lambda _title, msg, **_k: warnings.append(msg)
    )
    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.messagebox.showerror", lambda _title, msg, **_k: errors.append(msg)
    )

    monkeypatch.setattr("sattlint_gui.frames.config_frame.simpledialog.askstring", lambda *_a, **_k: " targeta ")
    ConfigFrame._add_target(frame)
    assert warnings == ["Target already listed."]

    monkeypatch.setattr("sattlint_gui.frames.config_frame.simpledialog.askstring", lambda *_a, **_k: "TargetB")
    ConfigFrame._add_target(frame)
    assert errors == ["Target not found in configured directories."]

    monkeypatch.setattr("sattlint_gui.frames.config_frame.simpledialog.askstring", lambda *_a, **_k: "TargetC")
    ConfigFrame._add_target(frame)
    assert frame.targets_list.items == ["TargetA", "TargetC"]
    assert frame._dirty is True


def test_config_frame_remove_and_other_library_workflows_without_tk_widgets(monkeypatch):
    warnings: list[str] = []
    frame = _make_config_frame_double()
    frame.targets_list.items = ["TargetA", "TargetB"]
    frame.other_libs_list.items = ["lib-a"]

    ConfigFrame._remove_target(frame)
    assert frame.targets_list.items == ["TargetA", "TargetB"]

    frame.targets_list._selection = (0,)
    ConfigFrame._remove_target(frame)
    assert frame.targets_list.items == ["TargetB"]
    assert frame._dirty is True

    monkeypatch.setattr(
        "sattlint_gui.frames.config_frame.messagebox.showwarning", lambda _title, msg, **_k: warnings.append(msg)
    )
    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "lib-a")
    ConfigFrame._add_other_lib_dir(frame)
    assert warnings == ["Folder already listed."]

    monkeypatch.setattr("sattlint_gui.frames.config_frame.filedialog.askdirectory", lambda **_kwargs: "lib-b")
    ConfigFrame._add_other_lib_dir(frame)
    assert frame.other_libs_list.items == ["lib-a", "lib-b"]

    frame.other_libs_list._selection = (1,)
    ConfigFrame._remove_other_lib_dir(frame)
    assert frame.other_libs_list.items == ["lib-a"]


def test_config_frame_reload_apply_workspace_paths_and_save_without_tk_widgets():
    loaded_cfg = {
        "mode": "draft",
        "scan_root_only": True,
        "fast_cache_validation": False,
        "debug": True,
        "program_dir": "programs",
        "ABB_lib_dir": "abb",
        "icf_dir": "icf",
        "analyzed_programs_and_libraries": ["TargetA"],
        "other_lib_dirs": ["lib-a"],
    }
    saved: list[dict[str, Any]] = []
    binding_obj = SimpleNamespace(
        config_path="config.toml",
        graphics_rules_path=Path("graphics-rules.toml"),
        load_config=lambda: loaded_cfg,
        save_config=lambda cfg: saved.append(cfg) or SimpleNamespace(ok=True, output="Saved config"),
        target_exists=lambda _target, _cfg: True,
    )
    frame = _make_config_frame_double(binding_obj=binding_obj)

    ConfigFrame.reload_config(frame)

    assert frame.mode_var.get() == "draft"
    assert frame.scan_root_only_var.get() is True
    assert frame.fast_cache_validation_var.get() is False
    assert frame.debug_var.get() is True
    assert frame.targets_list.items == ["TargetA"]
    assert frame.other_libs_list.items == ["lib-a"]
    assert frame.graphics_rules_path_var.get().endswith("graphics-rules.toml")
    assert frame.status.text == "Loaded config.toml"

    binding_obj.load_config = lambda: {
        **loaded_cfg,
        "program_dir": "workspace-programs",
        "ABB_lib_dir": "workspace-abb",
        "icf_dir": "workspace-icf",
        "other_lib_dirs": ["workspace-lib"],
    }
    ConfigFrame.apply_workspace_ha_paths(frame)
    assert frame.program_dir_var.get() == "workspace-programs"
    assert frame.abb_lib_dir_var.get() == "workspace-abb"
    assert frame.icf_dir_var.get() == "workspace-icf"
    assert frame.other_libs_list.items == ["workspace-lib"]
    assert frame.status.text == "Applied workspace HA path suggestions"
    assert frame._dirty is True

    frame.mode_var.set("official")
    ConfigFrame.save_config(frame)
    assert saved[-1]["mode"] == "official"
    assert frame._dirty is False
    assert frame.status.text == "Saved config"


def test_config_frame_can_close_handles_cancel_save_and_discard(monkeypatch):
    frame = _make_config_frame_double()

    assert ConfigFrame.can_close(frame) is True

    frame._dirty = True
    monkeypatch.setattr("sattlint_gui.frames.config_frame.messagebox.askyesnocancel", lambda *_a, **_k: None)
    assert ConfigFrame.can_close(frame) is False

    monkeypatch.setattr("sattlint_gui.frames.config_frame.messagebox.askyesnocancel", lambda *_a, **_k: False)
    assert ConfigFrame.can_close(frame) is True

    monkeypatch.setattr("sattlint_gui.frames.config_frame.messagebox.askyesnocancel", lambda *_a, **_k: True)
    frame.save_config = lambda: frame._set_dirty(False)
    frame._dirty = True
    assert ConfigFrame.can_close(frame) is True
    assert frame._dirty is False
