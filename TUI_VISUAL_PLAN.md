# TUI Visual Layout Plan

> Design review of the Textual shell, produced from textual-capture frames.
> Goal: keep the current color palette exactly as-is and improve layout, hierarchy,
> and button grouping. Capture artifacts: `/tmp/opencode/shots/*.svg` (transient).

## Current state (from textual-capture)

Frames captured at 110x44 with a real project loaded (`NNEDemo.slproj`):

- `01-analyze-no-project.svg`, `10-analyze-project.svg`, `11-analyze-selected.svg`
- `02-setup.svg`, `12-setup-project.svg`, `03-settings.svg`, `04-results.svg`

### Findings

1. **Analyze toolbar** (`#analyze-actions-primary`) has 5 buttons in one flat row:
   `Run selected analyses | Generate Change Review | Cancel running | Clear selection | Clear output`.
   - Mixes three different concerns with equal visual weight.
   - At 80 cols, `Clear selection` truncates to `Clear` and `Clear output` is cut off
     (horizontal scroll; already visible in a live capture).
   - No `Select all` — bulk-selecting 11+ analyzers is manual.
2. **Generate Change Review** sits beside `Run selected analyses` with identical styling
   though it is a whole-project artifact generator, not a selection action.
3. **Nav tabs** are `Static` widgets padded with literal spaces
   (`  Analyze  `, `  Configuration Settings  `) — inconsistent padding and a different
   visual language than the menubar buttons. Active tab (`#f4efde`) is flush with the
   content background; there is no seam/connection to the panel.
4. **Config lifecycle** is split: `Open Configuration` + `New Configuration` in the menubar
   (`MENU_DEFINITIONS`), `Delete Configuration` (`#setup-delete-project`) buried at the
   bottom of the Setup view.
5. **Capture-found defects:**
   - `Remove...` (`#setup-edit-other-lib-dirs-remove`, `.setup-row-button-compact` width 11)
     wraps to `Remov / e...`.
   - Settings view shows "App Settings" twice (view title + `#settings-config-title`).
   - Analyze browser and Setup targets/config columns stretch to large empty heights.
   - Results `Expand all` / `Collapse all` are classed `.results-tab-button` (misnomer).

## Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | Add buttons? | Yes — add `Select all`, paired with `Clear selection`. |
| 2 | Move buttons? | Yes — split the Analyze toolbar into run zone (left) and selection/utility zone (right). |
| 3 | Move Generate Change Review? | Yes — relocate to the Results header, next to Expand/Collapse. |
| 4 | New tab? | No — the 4 existing tabs cover the content; revisit only if Results crowds. |
| 5 | "Select all"? | Yes — see #1. |
| 6 | Selection buttons away from run buttons? | Yes — group them on the right. |
| 7 | Tabs look similar? | Yes — real CSS padding (no literal spaces), equal sizing, active tab connects into the panel; unify menubar + tab strip. |
| 8 | Open/New/Delete config? | Yes — consolidate all three in the menubar; Delete uses the danger accent. |

## Implementation

### 1. Analyze toolbar zones

Files: `src/sattlint/ui/_app_textual_app.py`, `src/sattlint/ui/_app_textual_actions.py`,
`src/sattlint/ui/_app_textual_analyze.py`, `src/sattlint/ui/app_textual.tcss`.

- Add a `Select all` button in `compose()` (in `_app_textual_app.py:174` block):
  `id="analyze-select-all"`, classes `raised-button toolbar-button`.
- Wrap the existing buttons in two horizontal containers inside `#analyze-actions-primary`:
  - run zone: `Run selected analyses`, `Cancel running`
  - selection zone (right-aligned): `Select all`, `Clear selection`, `Clear output`
- Wire `analyze-select-all` in `on_button_pressed` (`_app_textual_actions.py:1091`).
- Add `_select_all_analyzers` next to `_clear_selected_analyzers`
  (`_app_textual_analyze.py:397`): set `_analyze_selected_entry_ids` to all filtered
  entry ids, then `_refresh_view()` + `_refresh_shell_state()` + write output.
- Update `_refresh_shell_state` (`_app_textual_actions.py:973`) to enable/disable
  `analyze-select-all` like the clear-selection logic (disabled when nothing selectable).
- CSS: give `#analyze-actions-primary` a `layout: horizontal` with the two zones, and
  `align: left middle` / `align: right middle`; remove `overflow-x: auto` once the zones
  wrap sensibly at 80 cols.

### 2. Move Generate Change Review to Results

- Remove the button from `compose()` (`_app_textual_app.py:180`).
- Add it to the `#results-tabs` row (`_app_textual_app.py:344`):
  `id="results-generate-change-review"`, classes `raised-button results-tab-button`.
- Wire it in `on_button_pressed` to `_run_generate_change_review`.
- Update `_refresh_shell_state` to gate it on `results_view` instead of `analyze_view`.
- Rename `.results-tab-button` → `.results-header-button` (both CSS + compose) while here.

### 3. Tabs + menubar unification

File: `src/sattlint/ui/app_textual.tcss`.

- Remove literal spaces from tab labels in `compose()` (`_app_textual_app.py:159-162`).
- Add consistent `padding: 0 2` via `.nav-tab`, equal `height: 3`, and give the strip a
  single shared `background`.
- Active tab: `background: #f4efde`, `color: #001ba3`, plus a `border-top` accent in
  `#0077b3` (or a bottom edge on the inactive tabs) so the active tab visually connects
  to the panel below.
- Match menubar button hover/typography to the tab strip (same `height`, `text-style`,
  hover `background`) so the two rows read as one chrome region.

### 4. Config lifecycle in the menubar

Files: `src/sattlint/ui/_app_textual_shared.py`, `src/sattlint/ui/_app_textual_actions.py`,
`src/sattlint/ui/_app_textual_app.py`.

- Add `("Delete Configuration", "menu-file-delete-project")` to `MENU_DEFINITIONS`
  (`_app_textual_shared.py:151`) after `New Configuration`.
- Wire `menu-file-delete-project` in `on_button_pressed` → `_delete_project`
  (`_app_textual_actions.py:895`).
- Remove the `#setup-delete-project` button from Setup compose
  (`_app_textual_app.py:277-282`) and its wiring.
- Style `Button.menubar-button` for destructive action in the danger accent
  (`#8a3b12`) via a class or `#menu-file-delete-project` selector.

### 5. Capture-found fixes

- Widen `.setup-row-button-compact` from `11` to `16` (or relabel `Remove...` →
  `Remove lib`) so it no longer wraps.
- Remove the duplicate App Settings heading: hide `#settings-config-title` when the
  view title is visible (or drop it and keep only the view title).
- Cap dead vertical space: give `#analyze-browser-left`, `#setup-targets-col`, and
  `#setup-settings-col` a sensible `max-height` / `height: 1fr` with `overflow-y: auto`
  so the panels do not stretch to huge empty heights.

### 6. Deeper findings (round 2 — dead/missing UI)

These came from tracing code paths the captures hinted at; none are layout opinions,
they are confirmed dead or invisible behavior.

| # | Finding | Evidence | Fix |
|---|---------|----------|-----|
| A | **Project summary is computed but never displayed.** `_refresh_summary()` is called ~10× and builds `_summary_text()` (configured target names, or the summarize-targets output) but no `#summary` widget exists in `compose()`, so it silently no-ops. | `_app_textual_actions.py:243`, `_app_textual_app.py:155-359` | Mount a `#summary` Static (view header or a status strip) and update it in `_refresh_summary`. |
| B | **Unsaved-changes indicator is invisible.** `setup_browser.set_class(self._dirty, "config-mode")` toggles `.config-mode`, which has no CSS rule. The dirty flag only surfaces via the quit-confirm dialog. | `_app_textual_actions.py:749`; no `.config-mode` in `app_textual.tcss` | Add a `.config-mode` rule (e.g. warning-tinted border `#8a5a00` or a `•` label) so unsaved edits are visible. |
| C | **No indicator of which configuration is open.** The chrome shows no project name anywhere. | captures; `_project_loaded()` state | Show the open project name (or "No configuration") in the menubar/title area. |
| D | **`view-primary-action` launch button is vestigial.** Clicking it prints "…available directly in the view" / "not available as a standalone action". It is an enabled-looking button that does nothing useful. | `_launch_active_view` `_app_textual_actions.py:959`; `launch_label` registry `_app_textual_shared.py:172` | Remove the button + `launch_label` plumbing, or repurpose per view (Analyze → run, Settings → save, etc.). |
| E | **`_ShellBanner` is dead code.** Defined/exported, never mounted. | `_app_textual_widgets.py:42` | Either mount it (app title/subtitle row) or delete it. |
| F | **First-run welcome modal is dead.** `_welcome_shown` is never read; `_show_welcome` is never called (`on_mount` prints the welcome to the output pane instead). | `_app_textual_app.py:148,376` | Wire it or drop the dead path. |
| G | **View-title treatment is inconsistent.** Setup/Results hide the title; Settings shows it plus a duplicate "App Settings" section header. | `_refresh_view` `_app_textual_actions.py:736-738` | Always show a uniform view title; drop `#settings-config-title`. |
| H | **Nothing is focused on startup.** Keyboard-first users land nowhere. | `on_mount` `_app_textual_app.py:361` | Focus the analyzer `SelectionList` (or first control) on mount. |
| I | **Footer is crowded.** `APP_SHELL_BINDINGS` + Textual's default `^p palette` fill the bar. | captures L43 | Trim rarely used bindings (`^o`, `^c`, `^s`) or hide `palette`. |
| J | **Filter state is invisible.** After `/`, the list shrinks with no indication of the active filter. | `_set_analyze_filter_text` | Show "Filter: <text>" + a clear action in the section header. |

### 7. Settings area redesign (round 3)

From `03-settings.svg` (110 cols): the three Settings cards are squeezed side-by-side
into ~31 columns each, which causes all the wrapping below. This is a layout problem,
not a styling problem.

Observed defects:
- Duplicate "App Settings" heading (view title `#view-title` L6 + section header
  `#settings-config-title` L8).
- `.setup-row-button` fixed `width: 15` wraps labels: "Save run history" →
  `Save run`/`history`; "Session output retention" → 3 lines.
- Value boxes (`.setup-row-label`, `border: round`, `#b9d9df`) are ~30 cols wide, so
  descriptions wrap 5-7 lines ("Enabled: Completed runs are saved" → 7 lines).
- Cards are `height: auto` + `align: center top` → ~4 empty rows of dead space at the
  bottom of the panel.

Proposal (keep palette; do not touch `.setup-group-box` used by Setup):
1. Stack the three cards **vertically** in `#settings-settings-col` (full-width rows).
   Each row becomes `Button (auto width) | value box (1fr)` so labels fit on one line.
2. Card headers reuse the app's dialog-title style (`#0077b3` bg, `#fbfbee` bold,
   `height: 3`) — same as `#help-dialog-title` / `#file-browser-title` — for cohesion.
3. Drop `#settings-config-title`; keep only the view title.
4. `align: center middle` on the column with `padding`, eliminating the dead space.
5. Add `settings-group-box` / `settings-row-button` classes in `app_textual.tcss`
   (mirroring the existing group/row rules, minus the fixed button width).

Widgets involved: `settings-toggle-run-history`, `settings-edit-run-history-limit`,
`settings-toggle-debug`, `settings-edit-output-retention`,
`settings-edit-review-output-dir` (`_app_textual_app.py:283-337`).

## Validation

1. Re-run the capture driver:
   `.venv/bin/python /tmp/opencode/sattlint_capture.py` and
   `.venv/bin/python /tmp/opencode/sattlint_capture2.py`
2. Confirm at 110x44 and 80x44 that the Analyze toolbar no longer truncates and the
   two zones are visually distinct.
3. `pytest tests/ui/...` (focused), then `ruff check src tests`, `pyright`,
   `ruff format --check` (per AGENTS.md workflow).
4. Confirm colors are byte-identical to the current palette (`#f4efde`, `#b9d9df`,
   `#0077b3`, `#001ba3`, `#58787e`, `#e6decb`, `#d5cdb8`).
5. Round-2 checks: `#summary` visible and populated; `.config-mode` styles the Setup
   browser when dirty; open project name shown; `view-primary-action` removed or
   repurposed; initial focus lands on the analyzer list.
