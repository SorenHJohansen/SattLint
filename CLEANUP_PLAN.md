# Post-Pruning Cleanup Plan — Dead Code, Stale Docs, and Coverage Gaps

Status: **partially executed** — CI smoke steps fixed on the `analyzer_cleaning`
branch (2026-09-16). Remaining items are the removal, doc-sync, and coverage work
below.

Context: `TUI_PRUNING_PLAN.md` removed ~31k lines (analyzers, CLI commands, LSP/editor
API, semantic aggregate, legacy menu infra). This plan chases what that pass left
behind: modules nothing imports, docs that still promise removed CLI commands,
stale metadata referencing deleted files, and reachable features with thin tests.

Decision rule: **if a module is not reachable from the Textual UI and nothing
imports it, delete it.** The repo's own beliefs (#23 dead code removal, #11 docs
rot is tech debt, #15 tests are executable proof) are the standing authority.

---

## 1. DONE — CI workflows no longer call removed CLI commands

The package smoke step in both workflows ran `sattlint --version`, `--help`, and
`syntax-check`, which now exit `2` (all subcommands removed). Replaced with
wheel-install probes that assert what the package still guarantees.

- `.github/workflows/ci.yml` — Linux + Windows `Package smoke` steps
- `.github/workflows/publish.yml` — `Clean-wheel smoke` step

Each now runs:
- `import sattlint; assert sattlint.__version__`
- `import sattlint.ui`
- `from sattlint.cli.startup import cli` (entry point still reachable)

**Verification:** `python -m pytest tests/app/test_cli.py -q --tb=short`.

---

## 2. Delete orphaned modules (nothing imports them)

Confirmed by import graph + 0% coverage. All safe to remove with `trash-put`.

| File | Lines | Note |
|---|---|---|
| `src/sattlint/analyzers/_wave2_support.py` | 124 | nothing imports it |
| `src/sattlint/analyzers/_wave2_node_traversal.py` | 305 | imported only by `_wave2_support` (also dead) |
| `src/sattlint/analyzers/shared/_report_defaults.py` | 21 | `empty_issue_list`/`empty_*_summary_data` imported nowhere |
| `src/sattlint/core/tracing.py` | 116 | `detect_transform_invariant_violations` / `detect_unreachable_sequence_logic` never called; `AnalysisTraceRecorder` only referenced as a type annotation, never constructed |
| `src/sattlint/analyzers/_modules_debug.py` | 78 | `debug_module_structure` imported into `modules.py` but never called; remove the import too |
| `src/sattlint/analyzers/variable_usage_reporting.py` | 466 | production file imported only by tests; either move to `tests/helpers/` or delete and update the four test importers |
| `src/sattlint/ui/app_textual.py` | 28 | redundant re-export of `_app_textual_app`/`_app_textual_shared`; only the CI smoke import kept it alive (now removed) |
| `src/sattlint/transformer/sl_transformer.py` + `__init__.py` | 12 | compat wrapper imported only by `tests/conftest.py:20`; update conftest to use `sattline_parser` directly, then delete |

Notes / cleanup after each deletion:
- `src/sattlint/analyzers/modules.py:17` drop the `_modules_debug` import (and its
  `__all__` re-export if present).
- Tests referencing `variable_usage_reporting`:
  `tests/helpers/analyzers_suites_support.py:64`, `tests/helpers/app_analysis_support.py:22`,
  `tests/analyzers/test_module_localvar_strict.py:21`, `tests/analyzers/test_variable_usage_reporting.py:17`.
- `tests/conftest.py:20` `SLTransformer = import_module("sattlint.transformer.sl_transformer")`.

**Guard:** after each removal run
`python -m ruff check src/sattlint tests && python -m pyright src/sattlint tests && python -m pytest -q --tb=short`.

---

## 3. Sync docs that still promise removed CLI commands

The CLI is now a single no-arg TUI launch (see `CLI_COMMANDS.md`). These files
reference `sattlint init`, `--project`, `--version`, `--help`, `syntax-check`, or
`analyze`, none of which exist.

| File | Lines | Fix |
|---|---|---|
| `AGENTS.md` | 33-34, 58 | Rewrite the `.slproj` bullets for the TUI (Setup → New configuration); replace the `syntax-check` invariant with the retained parser-test route |
| `AGENTS_REFERENCE.md` | 13, 100, 222 | Point parser validation at the pytest route; drop `syntax-check` references |
| `ARCHITECTURE.md` | 99 | "Entry: `sattlint analyze`" → "Entry: the Textual Analyze view" |
| `README.md` | 117 | Remove the `sattlint --project PATH <command>` bullet |
| `CONTRIBUTING.md` | 14, 222, 272-274 | Drop `--version`/`--help`/`syntax-check` checklist items; version checks go through `python -c "import sattlint; print(sattlint.__version__)"` |
| `.github/instructions/parser-analysis.instructions.md` | 11, 15 | Replace `syntax-check` route with the targeted parser pytest |
| `.github/instructions/sattline-invariants.instructions.md` | 25-26, 37, 43 | Rewrite the strictness invariant in terms of the parser-test route |
| `.github/instructions/cli-app.instructions.md` | 9 | Verify the text still matches the real entry (`sattlint.cli.startup:cli`, no subcommands) |
| `.github/instructions/repo-map.instructions.md` | 11-12 | Check the surface descriptions still hold post-pruning |
| `.github/ISSUE_TEMPLATE/bug_report.md` | 13, 22 | Drop `syntax-check`/`analyze`/`init`/`--version` examples; use the TUI views + `sattlint.__version__` |

`CHANGELOG.md:129` is a historical entry — leave it; add a new entry documenting
the CLI removal + this cleanup.

**Guard:** `python -m ruff check . && python -m pytest tests/app/test_cli.py -q --tb=short`.

---

## 4. Remove stale metadata referencing deleted files

| File | Lines | Issue |
|---|---|---|
| `src/sattlint/analyzers/registry/_registry_delivery_data.py` | 7-15 | `_ANALYZER_SUITE_ACCEPTANCE_TESTS` points at `tests/test_analyzers_suites_part1..6.py` (deleted); `_APP_ACCEPTANCE_TESTS` points at `tests/test_app_cli_commands.py` (deleted); `tests/test_analyzers_version_drift.py` (deleted). Point them at the surviving suite files under `tests/analyzers/suites/` or empty them |
| `tests/fixtures/corpus/README.md` | 13, 74, 89 | References removed `sattlint.devtools.corpus`, `sattlint-corpus-runner`, `sattlint-repo-audit`; rewrite for the `tests/test_corpus_analyzers.py` harness |
| `src/sattlint/analyzers/registry/__init__.py` | 51 | `DEFAULT_CORPUS_MANIFEST_DIR` exported, no consumers; remove or keep only if the corpus runner returns |
| `src/sattlint/analyzers/registry/__init__.py` | 168 | `get_correctness_analyzer_keys()` exported, no consumers; remove with its `__all__` entry |

**Guard:** `python -m pytest tests/analyzers/test_analyzer_architecture.py tests/test_corpus_analyzers.py -q --tb=short`.

---

## 5. Rename retained tests that no longer test their namesake

- `tests/analyzers/suites/test_naming_alarm_integrity.py` → only tests `alarm-integrity` (naming analyzer was deleted). Rename to `test_alarm_integrity_suite.py` or fold into `test_alarm_integrity.py`.
- `tests/analyzers/suites/test_safety_taint_mms_usage.py` → tests version-drift opt-in registry + variable-usage reporting only (safety/taint/mms analyzers deleted). Rename to match actual content (e.g. `test_versiondrift_optin_variable_usage.py`).

**Guard:** `python -m pytest tests/analyzers/suites/ -q --tb=short`.

---

## 6. Close coverage gaps on reachable features

Current aggregate 80.22% (CI floor is 80). These are reachable production
modules with thin tests — not dead code.

| Module | Coverage | Gap |
|---|---|---|
| `analyzers/dataflow/_dataflow_conditions.py` | 28% | condition-eval engine: always-true/false, self-compare, logical shortcuts, ternary `_assume`; `test_dataflow_*` barely touches it |
| `core/workspace_discovery.py` | 27% | source-discovery path helpers (public `WorkspaceSourceDiscovery`) |
| `validation/expression.py` | 40% | builtin call arity/type semantics |
| `core/syntax.py` | 43% | code/dependency extension routing |
| `console.py` | 42% | print/output helpers used across the CLI |
| `core/_semantic_helpers.py` | 43% | module/typedef label formatting |
| `analyzers/cyclomatic_complexity.py` | 50% | registered opt-in analyzer — only clean/high fixtures in corpus |
| `analyzers/sfc/_sfc_guard_logic.py` | 50% | transition-guard normalization |
| `analyzers/dataflow/_dataflow_non_state_sites.py` | 65% | newer `non_state_multi_site` finding — no corpus manifest |

Prioritized work:
1. `_dataflow_conditions.py` — add focused tests per finding kind
   (`condition_always_true/false`, `self_compare_condition`, `unreachable_branch`,
   ternary `_assume`) alongside `tests/analyzers/test_dataflow_conflicting_constants.py`.
2. Add corpus manifests for `dataflow` `non_state_multi_site` and a `same-cycle`
   clean case (currently only `parallel-read-write` exists).
3. `validation/expression.py` + `core/workspace_discovery.py` — table-drive the
   public helpers.

**Guard:** `python -m pytest -q --tb=short --cov=sattlint --cov-fail-under=80`.

---

## 7. TUI key-binding cleanup

Three TUI shell bindings no longer match the intended surface.

### 7.1 Remove the `/` filter

The `slash` binding is the Analyze-view analyzer filter. It is redundant with
the built-in `Ctrl+F`-style list filtering and the intended shell has no
filter surface.

- `src/sattlint/ui/_app_textual_shared.py:20` — drop
  `("slash", "prompt_view_filter", "Filter")` from `APP_SHELL_BINDINGS`.
- `src/sattlint/ui/_app_textual_actions.py:444` — delete
  `action_prompt_view_filter` (and any internal `_prompt_*_filter` helpers it
  is the only caller of).
- `src/sattlint/ui/_app_textual_setup_display.py:228-234` — remove the
  `filter_suffix` text that tells users to "Press / to filter the analyzers".

### 7.2 Remove `Ctrl+S` save

Configurations save automatically, so the explicit save binding is dead weight.

- `src/sattlint/ui/_app_textual_shared.py:27` — drop
  `("ctrl+s", "save_config", "Save Config")` from `APP_SHELL_BINDINGS`.
- `src/sattlint/ui/_app_textual_actions.py:520` — delete `action_save_config`
  (and the `save_config_fn` plumbing if nothing else calls it).
- `src/sattlint/ui/_app_textual_settings.py:70-74` — drop "Press Ctrl+S to save
  app settings" from the settings note.

### 7.3 Fix the `Ctrl+1..4` view order

The nav-tab display order in `src/sattlint/ui/_app_textual_app.py:159-162` is
**Analyze, Results, Configuration Settings, App Settings**, but `APP_SHELL_BINDINGS`
maps `ctrl+2` to App Settings, `ctrl+3` to Results, and `ctrl+4` to Setup. The
number keys must follow the on-screen tab order:

| Key | Action (current) | Action (correct) |
|---|---|---|
| `ctrl+1` | `show_analyze` | `show_analyze` |
| `ctrl+2` | `show_settings` | `show_results` |
| `ctrl+3` | `show_results` | `show_setup` |
| `ctrl+4` | `show_setup` | `show_settings` |

- `src/sattlint/ui/_app_textual_shared.py:16-19` — reorder the four bindings to
  match the nav-tab order; update the binding descriptions accordingly.
- Check the welcome text in `src/sattlint/ui/_app_textual_app.py:376-385`
  (`Ctrl+1` Analyze, `Ctrl+4` Setup) still holds after the swap.

**Guard:** `python -m pytest tests/app/test_app_textual.py tests/app/test_app_textual_results.py tests/app/test_app_textual_change_review.py -q --tb=short`.

---

## 8. Execution order

1. §2 deletions (largest dead-code removal, reruns guards after each).
2. §4 metadata cleanup (depends on nothing).
3. §3 doc sync (references the removed CLI — do after confirming removals).
4. §5 test renames.
5. §6 coverage (independent, can run in parallel with §3).
6. §7 TUI key-binding cleanup (independent of §2-§6).

Each section is independently mergeable; keep them in separate commits per the
repo's change-isolation belief (#18).
