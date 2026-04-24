# TODO GUI

## Goal

Build a desktop GUI for SattLint that reuses existing CLI and analysis logic, starts fast, and stays isolated from current CLI and LSP behavior.

## Guardrails

- Keep CLI behavior unchanged. GUI code lives under `src/sattlint_gui/`.
- Reuse `sattlint.app` logic through a binding layer. GUI modules should not call `print()`-driven CLI functions directly.
- Treat `binding.py` as the only place allowed to touch private CLI helpers such as `_get_enabled_analyzers`.
- Ship vertical slices. Each phase should leave `sattlint-gui` launchable.
- Prefer editable, testable adapters over large Tk callback methods.

## Package Structure

```text
src/sattlint_gui/
├── __init__.py
├── __main__.py
├── main.py
├── theme.py
├── window.py
├── binding.py
├── frames/
│   ├── __init__.py
│   ├── sidebar.py
│   ├── analyze_frame.py
│   ├── config_frame.py
│   ├── docs_frame.py
│   ├── tools_frame.py
│   └── results_frame.py
└── widgets/
    ├── __init__.py
    ├── console.py
    ├── target_list.py
    ├── report_view.py
    └── styled_widgets.py
```

## Architecture Notes

### Main Window

- Root class: `SattLintWindow(tk.Tk)`.
- Default size: `1280x800`.
- Layout: horizontal `tk.PanedWindow` with fixed-width sidebar and resizable content area.
- Sidebar width target: `200px`.
- Content area uses stacked frames, one per top-level view.

### Theme

`theme.py` keeps immutable defaults for:

- `bg_main`
- `bg_panel`
- `btn_bg`
- `btn_active`
- `accent`
- `input_bg`
- `text`
- `console_bg`
- `console_text`

### Binding Layer

`binding.py` owns:

- Config load and save wrappers around `load_config`, `save_config`, and `CONFIG_PATH`
- Tool wrappers around `ensure_ast_cache` and `self_check`
- Analysis wrappers around `run_variable_analysis`
- Discovery wrappers around `_get_enabled_analyzers`
- Output capture so GUI gets strings and structured results instead of raw terminal printing

### Config Strategy

Phase 1 uses a raw JSON editor backed by current config dict shape.

Phase 2 replaces that editor with form controls aligned to CLI config menu options 1-12 in `src/sattlint/app.py`.

### Entry Point

Console script should be:

```toml
sattlint-gui = "sattlint_gui.main:gui"
```

The original `sattlint_gui:main:gui` form is not valid setuptools entry-point syntax.

## Delivery Plan

### Phase 1: Launchable shell

- Add package scaffold
- Add theme and ttk styling helpers
- Add main window, sidebar, and placeholder content frames
- Add minimal binding for config load/save, self-check, AST cache, analyzer listing
- Add `sattlint-gui` console script
- Add narrow tests for import and launch wiring

### Phase 2: First usable workflow

- Analyze view shows configured targets
- Self-check and AST cache actions stream output into a console widget
- Config view supports reload and save from JSON editor
- Tools view shows enabled analyzers and common diagnostics

### Phase 3: CLI parity work

- Replace raw config JSON with explicit form fields
- Mirror CLI config menu behavior for target add/remove, mode toggle, scan toggles, and path pickers
- Add unsaved-change prompts and close guard

### Phase 4: Analysis and reports

- Add analyzer selection UI
- Run variable analysis and check bundles from GUI
- Render summaries in `report_view.py`
- Keep long-running tasks off the Tk event loop

### Phase 5: Docs and polish

- Wire doc-generation actions
- Add progress feedback and status bar updates
- Add higher-level GUI tests where practical
- Document install and launch flow in README if feature stabilizes

## Immediate Implementation Slice

1. Create launchable GUI shell with themed sidebar and stacked views.
2. Add binding wrappers for config load/save, self-check, AST cache, and analyzer listing.
3. Add a basic Analyze view and Config view that exercise those wrappers.
4. Validate with focused pytest coverage and direct `gui()` launch wiring.
