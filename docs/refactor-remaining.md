# Refactor Plan

This document tracks only remaining refactor work. Completed items have been removed. Wave 1 audit output lives in `docs/refactor-wave1-audit.md` and feeds Wave 5.

---

## Planned waves

| Wave | Item(s) | Focus | Exit condition |
|------|---------|-------|----------------|
| 3 | #7 | Split `src/sattlint/app.py` behind stable `sattlint.app` facade | `app.py` becomes thin facade plus CLI entry points with no behavior drift |
| 4 | #20, #44 | User-visible console output routing; logging levels | App-facing output stops using ad hoc `print()` paths except intentional console wrappers |
| 5 | #21 | Return type consistency | Sentinel-return sites are triaged and fixed module-by-module |

---

## Wave notes

---

**Wave 3 - Bulletproof `app.py` split (#7)**

Current facts to preserve:

- `src/sattlint/app.py` is still the public import and still owns CLI dispatch, menu routing, project loading, and analysis workflows.
- `src/sattlint/app_graphics.py` already owns most graphics helpers and is called from `app.py` through wrappers. Treat it as an existing leaf seam; do not re-split graphics first.
- `tests/test_app.py`, `tests/test_app_menus.py`, and `tests/test_app_analysis.py` still contain many `monkeypatch.setattr(app, ...)` seams. Moving code without retargeting those seams will create false-green tests.
- `repo_audit_module` must stay lazy to preserve the current circular-import break with `structural_reports`.

Principles for the split:

- Keep `sattlint.app` as the only public import path during the entire refactor.
- Extract one slice at a time and retarget only the tests that cover that slice in the same change.
- Prefer sibling modules first (`app_base.py`, `app_docs.py`, `app_analysis.py`, `app_menus.py`) over an immediate `app/` package rename. Converting the facade file into a package can be a final cleanup step after behavior is stable, not part of the risky move.
- `app.py` should remain a thin facade that re-exports moved callables and keeps `main()` / `cli()` stable.
- No slice is considered moved until its focused pytest target passes with patches aimed at the owning module instead of the facade.

Recommended sequence:

1. Stabilize test ownership before moving code.
  - Pick one authoritative test file per surface: analysis behavior in `tests/test_app_analysis.py`, menu and CLI behavior in `tests/test_app_menus.py`.
  - Remove or merge duplicated coverage from `tests/test_app.py` only after equivalent split-file coverage is confirmed. Right now the legacy file still mirrors menu/config and analysis seams, which inflates patch churn and can hide missing coverage.
  - Add shared helper fixtures only where they reduce repeated patch setup without obscuring what module is actually being patched.

2. Extract a base seam into `src/sattlint/app_base.py` while keeping `src/sattlint/app.py` as facade.
  - Move constants, config I/O wrappers, prompt and screen helpers, logging setup, CLI parser, `run_cli()`, `run_syntax_check_command()`, cache helpers, and the lazy `repo_audit_module` support.
  - In `app.py`, re-export those names from `app_base.py` so external callers and the console entry point do not move.
  - Retarget only menu and CLI tests that patch these names.

3. Extract documentation flow into `src/sattlint/app_docs.py`.
  - Move documentation scope state, unit-selection helpers, and `documentation_menu()`.
  - Keep `classify_documentation_structure` and related imported names patched at the docs module once this slice moves.
  - Validate with the documentation and main-menu tests only.

4. Extract analysis flow into `src/sattlint/app_analysis.py`.
  - Move project-loading helpers that are analysis-only, `_iter_loaded_projects()`, analyzer catalog helpers, variable-analysis submenus, module-analysis flows, ICF/MMS/comment-code actions, and datatype or debug utilities.
  - Move imported aliases used only by this slice with it, including `analyze_variables`, `analyze_shadowing`, `validate_icf_entries_against_program`, and analysis-specific helper imports.
  - Retarget analysis tests slice-by-slice instead of doing a repo-wide monkeypatch rewrite.

5. Extract top-level menu orchestration into `src/sattlint/app_menus.py`.
  - Move `dump_menu()`, `config_menu()`, `tools_menu()`, interactive `main()` loop helpers, and any remaining menu-only glue.
  - Keep `app.py` with thin `main()` / `cli()` entry points that delegate into `app_menus.py` until the last cleanup step.

6. Shrink `src/sattlint/app.py` to explicit facade exports.
  - After all moved slices have green focused tests, reduce `app.py` to imports plus explicit re-exports.
  - Only if this is still valuable, replace the facade file with an `app/` package in a final mechanical rename. That rename should be zero-behavior and zero-test-logic.

Patch-target map for the split:

| Patched name today | Owning module after split |
|---|---|
| `clear_screen`, `pause`, `confirm`, `prompt`, `quit_app`, `_clear_windows_console` | `app_base` |
| `load_config`, `save_config`, `apply_debug`, `self_check`, `target_exists` | `app_base` |
| `ensure_ast_cache`, `force_refresh_ast`, `ASTCache`, `get_cache_dir` | `app_base` |
| `build_cli_parser`, `run_cli`, `run_syntax_check_command`, `show_config`, `show_help` | `app_base` |
| `repo_audit_module` | `app` facade |
| `graphics_rules_menu`, `run_graphics_rules_validation`, `get_graphics_rules_path`, `load_graphics_rules` | existing `app_graphics` seam or thin `app.py` wrappers over it |
| `documentation_menu`, `_get_documentation_unit_selection`, `_set_documentation_unit_selection`, `classify_documentation_structure` | `app_docs` |
| `load_project`, `load_program_ast`, `_iter_loaded_projects`, `_get_enabled_analyzers`, `_run_checks` | `app_analysis` |
| `run_variable_analysis`, `run_datatype_usage_analysis`, `run_debug_variable_usage`, `run_advanced_datatype_analysis` | `app_analysis` |
| `run_module_localvar_analysis`, `run_module_duplicates_analysis`, `run_module_find_by_name`, `run_module_tree_debug` | `app_analysis` |
| `run_mms_interface_analysis`, `run_icf_validation`, `validate_icf_entries_against_program`, `run_comment_code_analysis` | `app_analysis` |
| `analysis_menu`, `variable_usage_submenu`, `module_analysis_submenu`, `analyze_variables`, `analyze_shadowing` | `app_analysis` |
| `dump_menu`, `config_menu`, `tools_menu`, `main` interactive routing | `app_menus` |

Focused validation order for Wave 3:

1. Run only the pytest module that covers the slice you just moved.
2. Retarget its monkeypatch sites from `sattlint.app` to the owning module in that same change.
3. Re-run the same focused pytest module before moving the next slice.
4. Only after all slices are green, run the combined app-facing suite.

Abort conditions for the split:

- If a move requires widespread cross-imports back into `app.py`, stop and re-cut the seam smaller.
- If a test starts passing only when patching both `sattlint.app` and the new module, the facade boundary is still wrong.
- If the final step is only a rename from facade file to package layout, defer it unless there is a concrete maintenance win.

---

**Wave 4 - Print-to-logging (#20, #44)**

- `console.py` already provides output wrappers. After Wave 3 settles ownership, replace remaining ad hoc user-facing `print()` calls in the app surfaces with the correct console wrapper while keeping the output visible.
- Fix logging levels in the same pass so debug-only detail stays behind debug mode and normal status output remains user-facing.

---

**Wave 5 - Return type consistency (#21)**

- Use `docs/refactor-wave1-audit.md` to fix return contracts module-by-module.
- Prefer raising typed exceptions at internal boundaries over returning `None`, `[]`, or `{}` sentinels.
- Keep safe fallbacks only at explicit CLI or LSP boundaries, and label those boundaries clearly in code when needed.

---

## Validation gaps to add

These are confirmed missing checks to be implemented in future validation waves.

### Expression and type rules

- Missing operator type enforcement:
  - Arithmetic operators (`+`, `-`, `*`, `/`) are not enforced as numeric-only.
  - Logical operators (`AND`, `OR`, `NOT`) are not enforced as boolean-only.
  - Comparison operators (`<`, `>`, `<=`, `>=`) are not enforced as numeric-only.
- Missing string arithmetic guard:
  - No explicit error when `STRING` values participate in arithmetic expressions.
- Missing division safety:
  - Division-by-zero checks are not enforced.
- Missing IF-expression branch compatibility:
  - IF-expression branch type compatibility is not validated.
- Coercion is too permissive:
  - `INT -> REAL` coercion is over-applied and not spec-accurate.

### Assignment semantics

- Missing: assignment to `:OLD` is not rejected.
- Clarification: assignment to variable name without `:NEW` is treated as assignment to `:NEW`.

### CONST and STATE semantics

- CONST missing:
  - Mandatory initialization not enforced.
  - Invalid `:OLD` / `:NEW` usage not enforced.
  - `OpSave` / `Secure` / `RECORD` interaction not validated.
  - Auto-update semantics not modeled.
- STATE missing entirely:
  - No STATE-specific initialization requirements.
  - No `:OLD` write protection checks.
  - No same-scan read/write semantic checks.
  - No parameter / out-parameter restrictions.
  - No persistence semantic checks.

### SFC execution semantics

- Missing validation for:
  - Multiple simultaneously active steps (without explicit contract config).
  - Transition correctness.
  - Execution ordering and avalanche rule behavior.
  - Reset/hold behavior.
  - Step auto-variable typing.
  - Single-transition-per-cycle rule.

### Libraries and dependencies

- Missing validation for:
  - Missing libraries.
  - Circular dependencies.
  - Version compatibility.
  - External datatype resolution (currently unresolved types can be tolerated).
