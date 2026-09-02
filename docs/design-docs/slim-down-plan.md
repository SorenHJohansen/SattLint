# SattLint Slim-Down Plan

**Goal:** Reduce SattLint to a focused static analysis tool: load project → build semantic model → run high-confidence checks → present diagnostics. Everything that does not directly serve this mission is deleted.

**Current state:** ~72,800 lines of Python.  
**Target state:** ~57,000 lines (~16,000 removed, ~22% reduction).

---

## What stays (the core mission)

| Layer | What | Why |
|-------|------|-----|
| Project | `.slproj` loading, dependency resolution, `ProjectGraph` | Entry point for everything |
| Engine | Parser, transformer, AST cache | Produces the semantic model |
| Semantic model | `SemanticSnapshot`, symbol table, type graph, scope, access graph | Drives all analysis |
| Registry analyzers | All 30+ registry-backed checks (variables, MMS, SFC, ICF validation, etc.) | The actual defect detection |
| ICF validation | `analyzers/icf/` — parsing + validation against AST | Explicitly requested to keep |
| CLI | `init`, `analyze`, `syntax-check`, `validate-config`, `cache-prune` | Non-interactive surface |
| Config | `ConfigDict`, `.slproj`, `config.toml` | Needed for project setup |

## What gets deleted

| Category | Files | Lines removed |
|----------|-------|--------------|
| Graphics subsystem | 11 `*graphics*` files + `structural/` | ~3,800 |
| Picture display paths | `picture_display_paths.py`, `_picture_display_path_runtime*.py` | ~1,500 |
| Investigation/debug tools | `run_datatype_usage_analysis`, `run_debug_variable_usage`, `run_module_localvar_analysis`, `run_module_duplicates_analysis`, `run_module_find_by_name`, `run_module_tree_debug` | ~400 |
| `format-icf` command | CLI command + handler + formatter wiring | ~150 |
| Classic text-mode menus | `cli/menus.py` (729 lines), `_app_analysis_menus.py` (622 lines) | ~1,350 |
| Catalog investigation section | `investigation.*`, `structure.*` entries in `_app_analysis_catalog_data.py` | ~200 |
| `app_analysis.py` run_* explosion | `run_datatype_usage_analysis`, `run_debug_variable_usage`, `run_module_localvar_analysis`, `run_module_duplicates_analysis`, `run_module_find_by_name`, `run_module_tree_debug`, `run_advanced_datatype_analysis`, `run_icf_formatter`, `run_mms_interface_analysis` (standalone) | ~400 |
| `application/analyze.py` thin wrappers | All per-function wrappers except `run_checks` and `run_variable_analysis` | ~100 |
| `app.py` re-exports | Graphics + investigation + menu re-exports | ~100 |
| Graphics fuzzer | `graphics_fuzzer.py` | ~20 |
| Devtools empty dirs | `devtools/` `__pycache__` dirs | ~0 |

**Total: ~8,000 lines hard-deleted.** The remaining ~10,000 reduction comes from simplifying `app_analysis.py`, `_app_analysis_catalog_data.py`, `application/analyze.py`, `app.py`, and the TUI shell from 4 views to 2.

---

## Phase 1: Delete graphics subsystem

The most self-contained chunk. No analysis check depends on it.

### Delete these files:
```
src/sattlint/graphics_validation.py              (350 lines)
src/sattlint/graphics_rules.py                   (422 lines)
src/sattlint/_graphics_validation_bindings.py    (296 lines)
src/sattlint/_app_graphics_menus.py              (598 lines)
src/sattlint/app_graphics.py                     (397 lines)
src/sattlint/_app_graphics_reports.py            (235 lines)
src/sattlint/_app_startup_docs_graphics.py       (144 lines)
src/sattlint/_engine_graphics_helpers.py         (275 lines)
src/sattlint/_engine_graphics_context_helpers.py (118 lines)
src/sattlint/graphics_fuzzer.py                  (18 lines)
src/sattlint/picture_display_paths.py            (491 lines)
src/sattlint/_picture_display_path_runtime.py    (516 lines)
src/sattlint/structural/__init__.py              (10 lines)
src/sattlint/structural/_structural_report_graphics.py (471 lines)
```

### Remove imports from:
- `app.py` — delete all `app_graphics` imports, `get_graphics_rules_path`, `load_graphics_rules`, `save_graphics_rules`, `_graphics_rule_label`, `_graphics_rule_config_line`, `_print_graphics_rules_summary`, `_discover_graphics_rule_selector_options`, `_pick_or_prompt_graphics_rule_selector_value`, `_prompt_graphics_rule_definition_with_config`, `_collect_graphics_layout_entries_for_target`, `run_graphics_rules_validation`, `graphics_rules_menu`, `GraphicsRulesConfig`, `GraphicsRulesLoadResult`
- `cli/startup.py` — remove `discover_graphics_rule_selector_options`, `pick_or_prompt_graphics_rule_selector_value`, `graphics_rules_menu`, `prompt_graphics_rule_definition_with_config`, `collect_graphics_layout_entries_for_target`, `run_graphics_rules_validation`
- `app_support.py` — remove `save_graphics_rules` if present
- `cli/menus.py` — remove "Edit graphics rules" from config_menu (line ~311)

### Registry cleanup:
- Remove `picture-display-paths` from `DEFAULT_CLI_ANALYZER_KEYS` in `analyzers/registry/__init__.py`
- Remove the `picture-display-paths` analyzer spec from `build_default_analyzers()`
- Remove `picture_display_paths.py` from the registry imports
- Keep `picture_display_paths.py` module only if the registry analyzer `picture-display-paths` is the sole user — if so, delete it too

### Config cleanup:
- No `ConfigDict` fields reference graphics, so nothing to change in `config_types.py`

### Test cleanup:
- Find and delete tests for graphics validation, graphics rules, picture display paths
- Search `tests/` for `graphics`, `picture_display`, `structural_report`

### Verification:
- `sattlint analyze --check variables` still works
- `sattlint syntax-check` still works
- Import `sattlint` succeeds without graphics modules

---

## Phase 2: Delete investigation/debug tools and `format-icf`

### Delete from `app_analysis.py`:
- `run_datatype_usage_analysis()`
- `run_debug_variable_usage()`
- `run_module_localvar_analysis()`
- `run_module_duplicates_analysis()`
- `run_module_find_by_name()`
- `run_module_tree_debug()`
- `run_advanced_datatype_analysis()`
- `run_mms_interface_analysis()` (standalone, not the registry analyzer)
- `run_icf_formatter()`

### Delete from `application/analyze.py`:
- `run_datatype_usage_analysis()`
- `run_module_duplicates_analysis()`
- `run_module_find_by_name()`
- `run_module_tree_debug()`
- `run_module_localvar_analysis()`
- `run_mms_interface_analysis()`
- `run_debug_variable_usage()`
- `run_comment_code_analysis()`
- `run_advanced_datatype_analysis()`
- `run_icf_validation()` (standalone handler — ICF validation stays as a registry analyzer, not a standalone `run_*` handler)

### Delete from `_app_analysis_catalog_data.py`:
- Remove `ENTRY_DATATYPE_USAGE` entry
- Remove `ENTRY_VARIABLE_USAGE_TRACE` entry
- Remove `ENTRY_MODULE_LOCAL_VARIABLES` entry
- Remove `structure.compare-module-variants` entry
- Remove `structure.find-module-instances` entry
- Remove `structure.inspect-module-tree` entry
- Remove `structure.validate-graphics-rules` entry
- Remove `interfaces.format-icf-files` entry
- Remove `code-quality.commented-out-code` entry (keep `comment-code` as a registry analyzer)
- Remove `interfaces.mms-interface-variables` standalone entry (keep the registry analyzer)
- Remove `interfaces.validate-icf-paths` standalone entry (keep ICF validation as a registry analyzer)
- Remove the `SECTION_INVESTIGATION`, `SECTION_STRUCTURE_ACTIONS`, `SECTION_CODE_QUALITY_ACTIONS` section specs
- Remove the `FAMILY_INVESTIGATION`, `FAMILY_STRUCTURE_MODULES`, `FAMILY_CODE_QUALITY` top-level families
- Simplify `TOP_LEVEL_ANALYSIS_FAMILIES` to only `FAMILY_ANALYZE_SUITE`, `FAMILY_VARIABLE_ISSUES`, and `FAMILY_ANALYZER_CATALOG`

### Delete from `_app_analysis_catalog_shared.py`:
- Remove constants for the deleted entries (`ENTRY_DATATYPE_USAGE`, `ENTRY_VARIABLE_USAGE_TRACE`, `ENTRY_MODULE_LOCAL_VARIABLES`, etc.)

### Delete from `app.py`:
- Remove all the `run_*` re-exports for deleted handlers
- Remove `run_format_icf_command`, `run_icf_formatter`
- Remove `_configured_icf_files`
- Remove `run_graphics_rules_validation`
- Keep: `run_checks`, `run_variable_analysis`, `run_analyze_command`, `run_syntax_check_command`, `run_validate_config_command`, `run_cache_prune_command`

### Delete `cli/menus.py` entirely (729 lines):
- The classic text-mode menu system is replaced by the TUI
- Remove the `menus` import from `app.py`
- Remove `tools_menu`, `dump_menu`, `config_menu`, `analysis_menu`, `variable_analysis_menu` etc. from the `startup.py` re-exports

### Delete `_app_analysis_menus.py` entirely (622 lines):
- The catalog-driven interactive menu system is no longer needed
- Analysis selection goes through the TUI's Analyze planner or the CLI's `--check` flags

### CLI changes:
- Remove `format-icf` subcommand from `cli/entry.py`
- Remove `format_icf` from `CommandHandlers` TypedDict
- Remove `run_format_icf_command` and `run_icf_formatter` from `cli/app_commands.py`

### Verification:
- `sattlint analyze --list-checks` still lists registry analyzers
- `sattlint analyze --check variables` still works
- `sattlint analyze --check mms-interface` still works (registry analyzer, not standalone)
- `sattlint analyze --check icf-validation` still works (if ICF validation is in the registry)

---

## Phase 3: Simplify `app_analysis.py` and `application/analyze.py`

After phases 1–2, `app_analysis.py` should only contain:
- `run_checks()` — the registry dispatch entry point
- `run_variable_analysis()` — variable issue analysis
- `analyze_variables()` — the core variable analysis engine
- `VARIABLE_ANALYSES` / `HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS` / `LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS`
- `validate_icf_entries_against_program()` — ICF validation (if kept as standalone)

### Simplify `application/analyze.py` to:
```python
def run_checks(cfg, selected_keys, *, selected_issue_kinds=None):
    """Run the registry analyzer suite."""

def run_variable_analysis(cfg, kinds):
    """Run variable issue analysis."""
```

Two functions. No more `run_datatype_usage_analysis`, `run_mms_interface_analysis`, etc.

### Simplify `app.py` re-exports:
- Remove the `GraphicsRulesConfig`, `GraphicsRulesLoadResult` type aliases
- Remove the `_COMPATIBILITY_HELPERS` tuple (graphics references)
- Remove `_menu_option`, `_print_menu`, `_summarize_targets` (menu helpers)
- Remove `run_analysis_menu`, `analysis_menu`, `config_menu`, `tools_menu`, `dump_menu`, `variable_analysis_menu`, `variable_usage_submenu`, `module_analysis_submenu`, `interface_communication_submenu`, `code_quality_submenu`, `analyzer_catalog_menu`, `advanced_analysis_menu`, `run_checks_menu`
- Keep the lean core: `load_config`, `save_config`, `validate_effective_config`, `build_cli_parser`, `run_cli`, `run_syntax_check_command`, `run_analyze_command`, `run_cache_prune_command`, `main`, `cli`

---

## Phase 4: Clean up `_app_analysis_catalog_data.py`

After phases 1–3, the catalog should only have:

### Top-level families (3):
1. **Full analyzer suite** → runs all enabled registry analyzers
2. **Variable issues** → the 27 variable issue kinds (high-confidence + heuristic)
3. **Analyzer catalog** → individual registry analyzer selection

### Remove:
- `SECTION_INVESTIGATION` (500) — deleted in phase 2
- `SECTION_STRUCTURE_ACTIONS` (600) — deleted in phase 2
- `SECTION_CODE_QUALITY_ACTIONS` (800) — deleted in phase 2
- `FAMILY_INVESTIGATION`, `FAMILY_STRUCTURE_MODULES`, `FAMILY_CODE_QUALITY` families
- All `investigation.*`, `structure.*`, `interfaces.mms-interface-variables`, `interfaces.validate-icf-paths`, `interfaces.format-icf-files`, `code-quality.commented-out-code` entries

### Keep:
- `SECTION_TOP_LEVEL` (100)
- `SECTION_VARIABLE_SUITE` (200)
- `SECTION_VARIABLE_HIGH_CONFIDENCE` (300)
- `SECTION_VARIABLE_LOW_CONFIDENCE` (400)
- `SECTION_CATALOG_SUITE` (900)
- `SECTION_CATALOG_ISSUE_CHECKS` (950)
- `SECTION_CATALOG_ANALYZERS` (1000)
- `FAMILY_ANALYZE_SUITE`, `FAMILY_VARIABLE_ISSUES`, `FAMILY_ANALYZER_CATALOG`

---

## Phase 5: Config simplification

Your config comment was cut off, but based on the current `ConfigDict`:

### Remove (if present):
- `graphics_rules` or any graphics-related config keys (none currently in `ConfigDict` — they live in a separate JSON file, already deleted in phase 1)

### Keep:
- `analyzed_programs_and_libraries`
- `include_reverse_library_consumers`
- `mode`
- `debug`
- `program_dir`, `ABB_lib_dir`, `icf_dir`, `other_lib_dirs`
- `telemetry`
- `analysis.sfc`, `analysis.naming`, `analysis.rule_profiles`

### The `.slproj` project file stays as-is — it has no graphics fields.

---

## Execution order

| Phase | Risk | Estimated lines removed | Dependencies |
|-------|------|------------------------|--------------|
| 1. Delete graphics | Low — self-contained | ~4,800 | None |
| 2. Delete investigation tools + format-icf | Medium — need to verify ICF validation lives in registry | ~1,800 | Phase 1 |
| 3. Simplify app_analysis.py + application/analyze.py + app.py | Medium — re-exports have callers | ~600 | Phase 2 |
| 4. Clean up catalog data | Low — after phase 2, entries are already gone | ~200 | Phase 2 |
| 5. Config cleanup | Low | ~50 | Phase 1 |

### After each phase:
1. `python -m sattlint analyze --list-checks` — registry still intact
2. `python -m sattlint analyze --check variables` — variable analysis works
3. `python -m sattlint syntax-check <test-file>` — parser works
4. `python -c "import sattlint"` — no import errors
5. Run the existing test suite: `pytest tests/`
6. Run `ruff check src/` and `pyright src/` for lint/type compliance

---

## What the result looks like

```
sattlint init          → scaffold .slproj
sattlint analyze       → run all enabled analyzers, print diagnostics
  --check KEY          → run specific analyzer
  --list-checks        → show available analyzers
  --format json        → machine-readable output
sattlint syntax-check  → validate a single file
sattlint validate-config → check config.toml
sattlint cache-prune   → clean stale cache
```

Just analysis. No graphics. No investigation tools. No format-icf. No classic menus.
