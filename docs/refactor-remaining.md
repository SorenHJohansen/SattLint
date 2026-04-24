# Refactor Plan

Items #2, #4, #5, #8, #9, #33, and #45 are closed (done or no action needed).
The remaining 9 open items are sequenced below.

---

## Planned waves

| Wave | Item(s) | Focus | Dependency |
|------|---------|-------|------------|
| ~~1~~ | ~~#5~~ | ~~Import consolidation~~ | Done - 3 sites updated to `sattline_parser.models.ast_model` |
| ~~2~~ | ~~#45, #9~~ | ~~Debug comment cleanup; devtools import direction~~ | Done - no debug comments found; import direction already correct |
| 1 | #27, #36 | Dataclass audit; `Optional` triage | Audit-only pass - no code changes yet |
| 2 | #22, #23 | Module boundary ordering; LSP input validation | #22 needs validation-first test coverage first |
| ~~3~~ | ~~#8~~ | ~~Test file splitting~~ | Done - 5 files split into 10; 521 tests pass |
| ~~3~~ | ~~#7~~ | ~~`app.py` monolith split~~ | Partially done - CLI expanded, constants added, `repo_audit_module` proxy. Full file split deferred: see Wave 3b. |
| 3b | #7 | `app.py` test-patch refactor (prerequisite for split) | Must do before splitting |
| 3c | #7 | `app.py` file split into `app/` package | Depends on 3b |
| 4 | #20, #44 | Print-to-logging; logging levels | After wave 3 so `app.py` is stable |
| 5 | #21 | Return type consistency | After waves 3-4; fix per-module alongside those changes |

---

## Wave notes

**Wave 1 - Audit passes (#27, #36)**

- `#27`: List all dataclasses with `Select-String -Path src/**/*.py -Pattern "@dataclass"`. Categorise by whether
  they are mutated after construction. Only mark `frozen=True` on provably immutable
  ones. No code changes in this wave - produce an audit table as output.
- `#36`: List functions typed `-> Optional[X]` or `-> X | None` and triage which are
  genuinely nullable vs. which use `None` as a sentinel. Output an audit list for the
  next fix wave.

---

**Wave 2 - Boundary and validation (#22, #23)**

- `#22`: Add tests for the validation-before-load path in `engine.py`. Then enforce
  that `validation.py` runs before `engine.py` dependency loading when `syntax_check`
  is `True`.
- `#23`: Add boundary validation for LSP request params in `server.py` (highest-value
  target). Use `isinstance` guards or a small `_validate_params` helper per handler.
  Do not add validation at internal Python-to-Python call paths.

---

**~~Wave 3 - `app.py` CLI and constants (#7)~~** (Done)

Expanded `build_cli_parser()` with `--version`, `--config`, `--no-cache`, `--quiet`
flags and `validate-config`, `analyze`, `docgen`, `repo-audit` subcommands.
Added `EXIT_SUCCESS`/`EXIT_USAGE_ERROR` constants and lazy `repo_audit_module` proxy
to break the circular import via `structural_reports`. 521 tests pass.

---

**Wave 3b - Refactor `app.py` test patches (prerequisite for file split)**

The file split is blocked by 62+ `monkeypatch.setattr(app, 'X', mock)` calls across
three test files. When `X` moves to a submodule, patching `app.X` no longer intercepts
the call inside the submodule — the test passes but tests nothing real.

Before splitting, update every `monkeypatch.setattr(app, 'X', mock)` to patch the
submodule that will own `X` after the split. Mapping:

| Attribute patched | Target submodule after split |
|---|---|
| `clear_screen`, `pause`, `confirm`, `prompt`, `quit_app` | `app._base` |
| `_clear_windows_console` | `app._base` |
| `load_config`, `save_config`, `apply_debug`, `self_check` | `app._base` |
| `target_exists`, `load_project`, `ensure_ast_cache`, `force_refresh_ast` | `app._base` |
| `ASTCache`, `get_cache_dir` | `app._base` |
| `_iter_loaded_projects`, `_get_enabled_analyzers`, `_run_checks` | `app._analysis` |
| `run_variable_analysis`, `run_debug_variable_usage` | `app._analysis` |
| `run_mms_interface_analysis`, `run_icf_validation` | `app._analysis` |
| `run_comment_code_analysis`, `run_module_tree_debug` | `app._analysis` |
| `run_advanced_datatype_analysis` | `app._analysis` |
| `analysis_menu`, `variable_usage_submenu`, `module_analysis_submenu` | `app._analysis` |
| `analyze_variables`, `analyze_shadowing` | `app._analysis` (these are imported names) |
| `get_graphics_rules_path`, `load_graphics_rules` | `app._base` |
| `graphics_rules_menu` | `app._graphics` |
| `_discover_graphics_rule_selector_options` | `app._graphics` |
| `classify_documentation_structure` | `app._docs` |
| `documentation_menu` | `app._docs` |
| `_get_documentation_unit_selection`, `_set_documentation_unit_selection` | `app._docs` |
| `dump_menu`, `config_menu`, `tools_menu`, `show_help`, `show_config` | `app._menus` |
| `load_config` in `run_cli` tests | `app._base` |
| `run_syntax_check_command` | `app._base` |
| `repo_audit_module` | `app` (proxy; stays at top level) |

Steps:
1. Do the file split (wave 3c) first in a branch.
2. Run `pytest` — expect many failures.
3. For each `monkeypatch.setattr(app, 'X', mock)` failure, change to
   `monkeypatch.setattr(app._submodule, 'X', mock)` where `_submodule` is from the
   table above.
4. Re-run until all 521 tests pass.

---

**Wave 3c - `app.py` file split into `app/` package**

Depends on Wave 3b being done first. Do as a mechanical move, not a rewrite.
Keep all public names importable from `sattlint.app` via `__init__.py` re-exports
so all external callers continue to work unchanged.

Proposed submodule boundaries (line numbers in current `app.py`, ~2850 lines):

| File | Lines | Contents |
|---|---|---|
| `app/_base.py` | L1–L731 | Imports, constants, shared UI helpers, config I/O, CLI dispatch stubs |
| `app/_graphics.py` | L732–L1387 | Graphics rule helpers, `graphics_rules_menu`, `run_graphics_rules_validation` |
| `app/_docs.py` | L1388–L1578 | Documentation helpers, `documentation_menu` |
| `app/_analysis.py` | L1579–L2493 | Project loading, variable analysis, all analysis menus |
| `app/_menus.py` | L2494–end | `dump_menu`, `config_menu`, `tools_menu`, `main`, `cli` |
| `app/__init__.py` | — | Re-exports everything from the above submodules |

Import DAG (no cycles):
```
_graphics  → _base
_docs      → _base
_analysis  → _base, _graphics, _docs
_menus     → _base, _graphics, _analysis
__init__   → all
```

`repo_audit_module` stays as a lazy proxy on `app` (already in `_base`) to keep the
existing circular-import break.

---

**Wave 4 - Print-to-logging (#20, #44)**

`console.print()` wrapper is already in place (`console.py`). Remaining work: replace
bare `print()` calls in `app.py` (and modules split out in wave 3) with
`console.print_status()` or `console.print_info()`. Do not convert informational output
to invisible `logging.debug` - keep it user-visible via the console wrapper. Fix
logging levels (#44) in the same pass.

---

**Wave 5 - Return type consistency (#21)**

Work through the audit list from wave 1. Fix per module as each module is touched.
Prefer raising a typed exception over returning `None` / `[]` / `{}` at internal
boundaries. At external (LSP / CLI) boundaries, keep safe fallback returns and annotate
with `# LSP handler` or `# CLI boundary` comments.

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
