from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Mapping
from copy import deepcopy
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, TypedDict, cast

from ..binding import SattLintBinding
from ..theme import resolve_theme


class EditableConfig(TypedDict):
    analyzed_programs_and_libraries: list[str]
    mode: str
    scan_root_only: bool
    fast_cache_validation: bool
    debug: bool
    program_dir: str
    ABB_lib_dir: str
    icf_dir: str
    other_lib_dirs: list[str]


def _list_config_value(cfg: dict[str, Any], key: str) -> list[str]:
    value = cfg.get(key)
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    return [item_str for item in items if (item_str := str(item).strip())]


def _string_config_value(cfg: dict[str, Any], key: str, default: str = "") -> str:
    return str(cfg.get(key) or default)


def extract_editable_config(cfg: dict[str, Any]) -> EditableConfig:
    return {
        "analyzed_programs_and_libraries": _list_config_value(cfg, "analyzed_programs_and_libraries"),
        "mode": _string_config_value(cfg, "mode", "official"),
        "scan_root_only": bool(cfg.get("scan_root_only")),
        "fast_cache_validation": bool(cfg.get("fast_cache_validation", True)),
        "debug": bool(cfg.get("debug")),
        "program_dir": _string_config_value(cfg, "program_dir"),
        "ABB_lib_dir": _string_config_value(cfg, "ABB_lib_dir"),
        "icf_dir": _string_config_value(cfg, "icf_dir"),
        "other_lib_dirs": _list_config_value(cfg, "other_lib_dirs"),
    }


def apply_editable_config(base_cfg: dict[str, Any], editable_cfg: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base_cfg)
    normalized = extract_editable_config(dict(editable_cfg))
    for key, value in normalized.items():
        merged[key] = value
    return merged


def _get_string_var(variable: tk.StringVar) -> str:
    return variable.get()


def _get_bool_var(variable: tk.BooleanVar) -> bool:
    return variable.get()


def _listbox_selection(listbox: tk.Listbox) -> tuple[int, ...]:
    curselection = cast(Callable[[], tuple[int, ...]], cast(Any, listbox).curselection)
    return curselection()


def _listbox_item(listbox: tk.Listbox, index: int) -> str:
    getter = cast(Callable[[int], object], cast(Any, listbox).get)
    return str(getter(index)).strip()


class ConfigFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc, *, binding: SattLintBinding) -> None:
        super().__init__(parent, style="Content.TFrame")
        self.binding = binding
        theme = resolve_theme(parent)
        self._loading = False
        self._dirty = False
        self._full_config: dict[str, Any] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self.mode_var = tk.StringVar(value="official")
        self.scan_root_only_var = tk.BooleanVar(value=False)
        self.fast_cache_validation_var = tk.BooleanVar(value=True)
        self.debug_var = tk.BooleanVar(value=False)
        self.program_dir_var = tk.StringVar(value="")
        self.abb_lib_dir_var = tk.StringVar(value="")
        self.icf_dir_var = tk.StringVar(value="")
        self.graphics_rules_path_var = tk.StringVar(value="")

        for variable in (
            self.mode_var,
            self.scan_root_only_var,
            self.fast_cache_validation_var,
            self.debug_var,
            self.program_dir_var,
            self.abb_lib_dir_var,
            self.icf_dir_var,
        ):
            variable.trace_add("write", self._on_field_changed)

        toolbar = ttk.Frame(self, style="Content.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(toolbar, text="Reload", style="Accent.TButton", command=self.reload_config).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Save", command=self.save_config).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(toolbar, text="Use Workspace HA Paths", command=self.apply_workspace_ha_paths).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        body = ttk.Frame(self, style="Content.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        general_panel = ttk.Frame(body, style="Panel.TFrame", padding=12)
        general_panel.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        general_panel.columnconfigure(1, weight=1)

        ttk.Label(general_panel, text="Setup", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(general_panel, text="Mode").grid(row=1, column=0, sticky="w", pady=(10, 0))
        mode_combo = ttk.Combobox(
            general_panel,
            textvariable=self.mode_var,
            values=("official", "draft"),
            state="readonly",
            width=18,
        )
        mode_combo.grid(row=1, column=1, sticky="w", pady=(10, 0))

        toggles = ttk.Frame(general_panel, style="Panel.TFrame")
        toggles.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(toggles, text="Scan root only", variable=self.scan_root_only_var).pack(side=tk.LEFT)
        ttk.Checkbutton(toggles, text="Fast cache validation", variable=self.fast_cache_validation_var).pack(
            side=tk.LEFT, padx=(12, 0)
        )
        ttk.Checkbutton(toggles, text="Debug logging", variable=self.debug_var).pack(side=tk.LEFT, padx=(12, 0))

        self._build_path_row(general_panel, 3, "Program dir", self.program_dir_var, self._browse_program_dir)
        self._build_path_row(general_panel, 4, "ABB lib dir", self.abb_lib_dir_var, self._browse_abb_lib_dir)
        self._build_path_row(general_panel, 5, "ICF dir", self.icf_dir_var, self._browse_icf_dir)

        ttk.Label(general_panel, text="Graphics rules").grid(row=6, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(general_panel, textvariable=self.graphics_rules_path_var, state="readonly").grid(
            row=6, column=1, sticky="ew", pady=(10, 0)
        )
        ttk.Button(general_panel, text="Show Path", command=self._show_graphics_rules_path).grid(
            row=6, column=2, sticky="e", padx=(8, 0), pady=(10, 0)
        )

        targets_panel = ttk.Frame(body, style="Panel.TFrame", padding=12)
        targets_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        targets_panel.columnconfigure(0, weight=1)
        targets_panel.rowconfigure(1, weight=1)
        ttk.Label(targets_panel, text="Analyzed Targets", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.targets_list: tk.Listbox = tk.Listbox(
            targets_panel,
            relief=tk.FLAT,
            bg=theme.input_bg,
            fg=theme.text,
            selectbackground=theme.btn_active,
            selectforeground=theme.console_text,
            exportselection=False,
        )
        self.targets_list.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        self.targets_list.bind("<<ListboxSelect>>", lambda _event: self._refresh_status())
        target_buttons = ttk.Frame(targets_panel, style="Panel.TFrame")
        target_buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(target_buttons, text="Add Target", command=self._add_target).pack(side=tk.LEFT)
        ttk.Button(target_buttons, text="Remove Selected", command=self._remove_target).pack(side=tk.LEFT, padx=(8, 0))

        libs_panel = ttk.Frame(body, style="Panel.TFrame", padding=12)
        libs_panel.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        libs_panel.columnconfigure(0, weight=1)
        libs_panel.rowconfigure(1, weight=1)
        ttk.Label(libs_panel, text="Other Library Dirs", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.other_libs_list: tk.Listbox = tk.Listbox(
            libs_panel,
            relief=tk.FLAT,
            bg=theme.input_bg,
            fg=theme.text,
            selectbackground=theme.btn_active,
            selectforeground=theme.console_text,
            exportselection=False,
        )
        self.other_libs_list.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        self.other_libs_list.bind("<<ListboxSelect>>", lambda _event: self._refresh_status())
        lib_buttons = ttk.Frame(libs_panel, style="Panel.TFrame")
        lib_buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(lib_buttons, text="Add Folder", command=self._add_other_lib_dir).pack(side=tk.LEFT)
        ttk.Button(lib_buttons, text="Remove Selected", command=self._remove_other_lib_dir).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        self.status = ttk.Label(self, text="", style="Muted.TLabel")
        self.status.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.reload_config()

    def _build_path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse_command: Callable[[], None],
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=(10, 0))
        ttk.Button(parent, text="Browse", command=browse_command).grid(
            row=row, column=2, sticky="e", padx=(8, 0), pady=(10, 0)
        )

    def _string_var_value(self, variable: tk.StringVar) -> str:
        return _get_string_var(variable).strip()

    def _bool_var_value(self, variable: tk.BooleanVar) -> bool:
        return _get_bool_var(variable)

    def _on_field_changed(self, *_args: object) -> None:
        if self._loading:
            return
        self._set_dirty(True)

    def _set_dirty(self, value: bool) -> None:
        self._dirty = value
        self._refresh_status()

    def _refresh_status(self, text: str | None = None) -> None:
        if text is not None:
            self.status.configure(text=text)
            return
        suffix = "Unsaved changes" if self._dirty else "Saved"
        self.status.configure(text=f"Config: {self.binding.config_path} | {suffix}")

    def _set_listbox_items(self, listbox: tk.Listbox, values: list[str]) -> None:
        listbox.delete(0, tk.END)
        for value in values:
            listbox.insert(tk.END, value)

    def _get_listbox_items(self, listbox: tk.Listbox) -> list[str]:
        return [value for index in range(listbox.size()) if (value := _listbox_item(listbox, index))]

    def _current_editable_config(self) -> EditableConfig:
        return {
            "analyzed_programs_and_libraries": self._get_listbox_items(self.targets_list),
            "mode": _get_string_var(self.mode_var).strip() or "official",
            "scan_root_only": _get_bool_var(self.scan_root_only_var),
            "fast_cache_validation": _get_bool_var(self.fast_cache_validation_var),
            "debug": _get_bool_var(self.debug_var),
            "program_dir": _get_string_var(self.program_dir_var).strip(),
            "ABB_lib_dir": _get_string_var(self.abb_lib_dir_var).strip(),
            "icf_dir": _get_string_var(self.icf_dir_var).strip(),
            "other_lib_dirs": self._get_listbox_items(self.other_libs_list),
        }

    def _preview_full_config(self) -> dict[str, Any]:
        return apply_editable_config(self._full_config, self._current_editable_config())

    def _browse_directory(self, variable: tk.StringVar) -> None:
        directory = filedialog.askdirectory(parent=self, initialdir=_get_string_var(variable).strip() or None)
        if not directory:
            return
        variable.set(directory)

    def _browse_program_dir(self) -> None:
        self._browse_directory(self.program_dir_var)

    def _browse_abb_lib_dir(self) -> None:
        self._browse_directory(self.abb_lib_dir_var)

    def _browse_icf_dir(self) -> None:
        self._browse_directory(self.icf_dir_var)

    def _show_graphics_rules_path(self) -> None:
        messagebox.showinfo("Graphics Rules", _get_string_var(self.graphics_rules_path_var).strip(), parent=self)

    def _add_target(self) -> None:
        target_name = simpledialog.askstring("Add Target", "Program or library name", parent=self)
        if not target_name:
            return
        target_name = target_name.strip()
        existing = {item.casefold() for item in self._get_listbox_items(self.targets_list)}
        if target_name.casefold() in existing:
            messagebox.showwarning("Duplicate Target", "Target already listed.", parent=self)
            return
        preview_cfg = self._preview_full_config()
        if not self.binding.target_exists(target_name, preview_cfg):
            messagebox.showerror("Unknown Target", "Target not found in configured directories.", parent=self)
            return
        self.targets_list.insert(tk.END, target_name)
        self._set_dirty(True)

    def _remove_target(self) -> None:
        selection = _listbox_selection(self.targets_list)
        if not selection:
            return
        self.targets_list.delete(selection[0])
        self._set_dirty(True)

    def _add_other_lib_dir(self) -> None:
        directory = filedialog.askdirectory(parent=self)
        if not directory:
            return
        existing = {item.casefold() for item in self._get_listbox_items(self.other_libs_list)}
        if directory.casefold() in existing:
            messagebox.showwarning("Duplicate Folder", "Folder already listed.", parent=self)
            return
        self.other_libs_list.insert(tk.END, directory)
        self._set_dirty(True)

    def _remove_other_lib_dir(self) -> None:
        selection = _listbox_selection(self.other_libs_list)
        if not selection:
            return
        self.other_libs_list.delete(selection[0])
        self._set_dirty(True)

    def reload_config(self) -> None:
        if self._dirty and not messagebox.askyesno(
            "Discard Changes",
            "Discard unsaved configuration changes and reload from disk?",
            parent=self,
        ):
            return

        self._loading = True
        try:
            self._full_config = self.binding.load_config()
            editable = extract_editable_config(self._full_config)
            self.mode_var.set(editable["mode"])
            self.scan_root_only_var.set(editable["scan_root_only"])
            self.fast_cache_validation_var.set(editable["fast_cache_validation"])
            self.debug_var.set(editable["debug"])
            self.program_dir_var.set(editable["program_dir"])
            self.abb_lib_dir_var.set(editable["ABB_lib_dir"])
            self.icf_dir_var.set(editable["icf_dir"])
            self.graphics_rules_path_var.set(str(self.binding.graphics_rules_path))
            self._set_listbox_items(self.targets_list, editable["analyzed_programs_and_libraries"])
            self._set_listbox_items(self.other_libs_list, editable["other_lib_dirs"])
            self._dirty = False
        finally:
            self._loading = False
        self._refresh_status(f"Loaded {self.binding.config_path}")

    def apply_workspace_ha_paths(self) -> None:
        suggested = self.binding.load_config()
        editable = extract_editable_config(suggested)
        self._loading = True
        try:
            self.program_dir_var.set(editable["program_dir"])
            self.abb_lib_dir_var.set(editable["ABB_lib_dir"])
            self.icf_dir_var.set(editable["icf_dir"])
            self._set_listbox_items(self.other_libs_list, editable["other_lib_dirs"])
        finally:
            self._loading = False
        self._set_dirty(True)
        self._refresh_status("Applied workspace HA path suggestions")

    def save_config(self) -> None:
        cfg = self._preview_full_config()
        result = self.binding.save_config(cfg)
        if result.ok:
            self._full_config = cfg
            self._set_dirty(False)
            self._refresh_status(result.output)
        else:
            messagebox.showerror("Save Failed", result.output, parent=self)

    def can_close(self) -> bool:
        if not self._dirty:
            return True
        response = messagebox.askyesnocancel(
            "Unsaved Changes",
            "Save configuration changes before closing?",
            parent=self,
        )
        if response is None:
            return False
        if response:
            self.save_config()
            return not self._dirty
        return True


__all__ = ["ConfigFrame", "apply_editable_config", "extract_editable_config"]
