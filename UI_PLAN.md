# UI Surface Gaps — What Is in the App but Not in the UI

> Status: Draft — decisions applied 2026-09-07
> Decision rule: everything should be reachable from the UI (or a documented CLI
> command), or be removed — unless there is a good reason not to.
> Scope: capabilities implemented in `src/sattlint` that are not reachable from
> the interactive Textual UI or the CLI, plus dead code and stale UI text.

## How to read this document

"UI" means the Textual shell (`src/sattlint/ui/`). The CLI (`sattlint ...`) is a
separate surface; an interactive session always launches Textual
(`cli/startup.py:run_interactive_session`).

Every item explains **what it is**, **how it works / why it exists**, **how it is
reached today**, then gives a verdict with the reason grounded in the mechanism.
Section 9 lists what each removal breaks.

Verdicts: **ADD** (expose in UI/CLI), **REMOVE** (superseded/dead/unwanted),
**KEEP CLI-ONLY** (good reason: automation/CI, scaffolding),
**KEEP INTERNAL** (building block / library API, not a UI feature).

---

## 1. Hidden application commands

These live in `analysis_handler_fns()` (`cli/startup.py:200`) but **no UI control
invokes them**, and none has a CLI subcommand.

### 1.1–1.3 `run_variable_analysis`, `run_comment_code_analysis`, `run_mms_interface_analysis`

- **What they are.** The pre-registry, per-feature analysis commands
  (`application/commands.py:71/287/314`).
- **Why obsolete.** The registered analyzers (`variables` + `shadowing`,
  `comment-code`, `mms-interface`) provide the same checks and are reachable in
  the Analyze planner and via `analyze --check KEY`. Two parallel implementations
  have already diverged: the legacy `run_variable_analysis` auto-sets
  `include_reverse_library_consumers` from the requested kinds
  (`commands.py:139-145`), the registry pipeline does not (§5.1).
- **Verdict: REMOVE.**

### 1.4 `run_icf_validation`

- **What it is.** The only user-facing entry to ICF-config validation
  (`application/commands.py:349`): validates every `*.icf` entry against the
  loaded program (program match, resolvable paths, field/datatype, group-key
  suffixes, journal fields, unit drift, value-prefix consistency).
- **Why it must exist in the UI.** It is the only feature whose whole purpose is
  checking `.icf` files, and nothing calls it. The `mms-interface` analyzer uses
  the same validator for tag resolution but never surfaces its findings.
- **Verdict: ADD** as a registered `icf` analyzer (see
  `analyzer-reference-and-rework.md` Part C, phases I1–I4).

  > **Status (2026-09-08):** Done. `icf` is registered, selectable, in
  > `DEFAULT_CLI_ANALYZER_KEYS`, and runs once per session across the whole
  > `icf_dir`. See Part C implementation notes.

### 1.5 `run_checks_menu` / `_run_analyze_checks`

- Dead helper; its only UI caller (`_app_textual_setup_actions.py:36`) is never
  bound. The planner runs checks via `run_checks_result`.
- **Verdict: REMOVE.**

---

## 2. Implemented capabilities with no UI or CLI entrypoint

### 2.1 ICF file formatting (`format_icf_file`, `format_icf_text`) — **REMOVE**

- **What it is.** Normalizes `.icf` file formatting with a `check=True` CI mode
  (`analyzers/icf/_icf_file_io.py:58/102`).
- **Decision.** Formatting is not needed. Remove the functions and the tests that
  exercise them (`tests/analyzers/test_icf_validation.py`,
  `test_icf_helpers.py`, `test_icf_helpers_grouping.py`).
- **Follow-up.** Fix the CLI description (`cli/entry.py:111`) that still promises
  "formatting commands".

### 2.2 Self-check diagnostics (`self_check`) — **AUTOMATIC ONLY**

- **What it does.** Pre-flight config checks: required keys present; directories
  exist; targets configured; analysis-namespace shape valid
  (`config/_self_check.py:79`).
- **Decision.** No user-facing action. Run it automatically as part of the
  analysis pre-flight (before the checks pipeline starts) and surface failures in
  the existing output path. If it fails, analysis stops with a clear message
  instead of failing later with a confusing error.

### 2.3 Config summary display (`show_config`) — **REMOVE**

- **What it is.** Prints the effective resolved config
  (`config/display.py:57`). Nothing calls it.
- **Decision.** Remove `show_config`, the `config/display.py` module, its wrapper
  (`cli/app_commands.py:148`) and the `app.py` re-export. The UI already renders
  config in Setup / App Settings; a CLI dump is not wanted.

### 2.4 Full cache clear-and-rebuild (`refresh_analysis_caches`, `force_refresh_ast`) — **CLI FLAG ONLY**

- **What they do.** `force_refresh_ast` reloads a target AST bypassing the cache;
  `refresh_analysis_caches` clears and rebuilds all caches
  (`application/project.py:183/225`).
- **Decision.** The user should never have to think about caches, and no UI
  control should exist. Expose a CLI flag (e.g. `--refresh-caches`) on `analyze`
  that forces a rebuild for that run. Automatic startup pruning of stale entries
  (`cache/classes.py:37/145`) already keeps caches healthy; nothing else is
  needed.

### 2.5 `load_program_ast` — **KEEP INTERNAL**

- Building block; becomes a dependency of the `icf` analyzer (1.4).

### 2.6 Typed service API (`application/service.py`) — **KEEP as library API**

- Deliberate public Python API for embedding/automation; needs docs, not a UI
  surface.

### 2.7 `parse_index_selection` — **REMOVE**

- Menu-index parser (`commands.py:47`); only tests use it.

---

## 3. CLI subcommands

### 3.1 `syntax-check` — **REMOVE**

- Single-file validation with exit codes. Decision: remove the subcommand, the
  `cli/syntax_check.py` module, the `app.py` import, and its tests. The UI
  planner is the supported analysis surface.

### 3.2 `validate-config` — **REMOVE (validation stays automatic)**

- **Key fact:** config validation already runs automatically — `load_config`
  validates and prints warnings on every load (`config/io.py:31-63`), and
  `save_config` refuses invalid configs (`config/io.py:72-74`). The standalone
  subcommand only adds an explicit, user-facing step for something that already
  happens.
- **Decision.** Remove the `validate-config` subcommand and
  `run_validate_config_command`; keep the automatic load-time validation. The
  user never has to think about config.

### 3.3 `cache-prune` — **KEEP CLI-ONLY**

- Stale entries are already pruned automatically at cache open
  (`cache/classes.py:37/145`); the subcommand is an explicit maintenance/reporting
  pass. Do not add a UI button.

### 3.4 `init` — **REMOVE**

- Remove the CLI `init` subcommand and its dispatch (`cli/entry.py:132,289`).
  The `init_project` function stays — the UI's New Configuration uses it
  (`ui/_app_textual_actions.py:26,862`). Project creation is an in-app action.

### 3.5 `analyze --check / --list-checks / --issue-kind / --list-issue-kinds`, `--output-format json` — **KEEP CLI-ONLY**

- Non-interactive automation / CI is the entire point of the CLI.

### 3.6 Global flags (`--config`, `--project`, `--no-cache`, `--quiet`, `--debug`, `--ui`, `--version`) — **KEEP CLI-ONLY**

- Standard CLI surface. `--refresh-caches` (2.4) joins these.

---

## 4. Analyzer planner gaps

The planner shows the **29** analyzers in `DEFAULT_CLI_ANALYZER_KEYS`
(`registry/__init__.py:58`); CLI `--list-checks` shows the **33** selectable;
**34** are registered today (a new `datatype-fields` analyzer from 5.1 adds one
more).

| # | Analyzer | Decision | Reason |
|---|---|---|---|
| 4.1 | `naming-consistency` | **REMOVE the analyzer** | Not wanted. Remove the analyzer, its registry entry, and the `analysis.naming` config (5.4) and the naming rule in rule profiles |
| 4.2 | `cyclomatic-complexity` | **ADD to planner** | Registered, selectable, CLI-runnable; users should pick it in the UI |
| 4.3 | `parameter-drift` | **ADD to planner** | Same |
| 4.4 | `version-drift` | **ADD to planner** | Same |
| 4.5 | `sattline-semantics` | **REMOVE from consideration; no Select-all** | The aggregate layer stays as the LSP-facing surface only; do not add a redundant "run everything" checkbox |
| 4.6 | `datatype-fields` (new) | **ADD to planner** | Split from `variables` (5.1); always loads dependent files, so it is expensive and must be an explicit opt-in |

Root cause to fix for 4.2–4.4: the planner sources `DEFAULT_CLI_ANALYZER_KEYS`
while `--list-checks` sources `get_selectable_analyzers()`; unify the planner on
the selectable set.

---

## 5. Config options not editable in the UI

### 5.1 `include_reverse_library_consumers` — **REMOVE the flag; split datatype-field analysis into its own analyzer**

- **What it controls.** When the target is a **library**, whether the loader also
  loads the configured programs/libraries that depend on it
  (`project/loading_support.py:218`). Needed for correctness of the datatype-field
  kinds (`unused_datatype_field`, `field_read_only`, `field_never_read`): a
  library field is only "unused" if no consumer uses it. Off by default because
  loading consumers is expensive.
- **Decision.** Two parts:
  1. **Always correct.** Whenever datatype-field analysis runs, it **always**
     scans the files that depend on the file where the datatype is declared —
     reverse consumers are loaded unconditionally, never gated by a config flag.
  2. **Split into its own analyzer.** Move the three datatype-field kinds out of
     the `variables` analyzer into a dedicated **`datatype-fields`** analyzer,
     exposed in the Analyze planner. Because it loads dependent programs, it is
     expensive, so users opt into it explicitly in the UI instead of it being
     silently bundled into every `variables` run.
- **Result.** The `include_reverse_library_consumers` config flag is removed from
  the user-facing contract; the loader behavior is driven solely by whether the
  `datatype-fields` analyzer is selected. The `variables` analyzer keeps the rest
  of its kinds (lifecycle, names, parameters, layout) and no longer triggers
  reverse-consumer loads.

### 5.2 `analysis.sfc.mutually_exclusive_steps` — **REMOVE (with the finding)**

- Removes the config key, the `sfc_illegal_state_combination` finding in the
  `sfc` analyzer, and its semantic rule. Note: there is no separate analyzer —
  it is one finding inside `sfc`.

### 5.3 `analysis.sfc.step_contracts` — **REMOVE (with the findings)**

- Removes the config key and the three `sfc` contract findings
  (`sfc_missing_step_enter_contract`, `sfc_missing_step_exit_contract`,
  `sfc_step_state_leakage`) plus their rules.

### 5.4 `analysis.naming.*` — **REMOVE**

- Removes the naming-style/allowlist config (its analyzer is removed in 4.1).

### 5.5 `analysis.rule_profiles` — **REMOVE (everything is always the same)**

- Removes rule profiles entirely: the config schema/validation, `rule_profiles.py`,
  `apply_rule_profile_to_report` in the checks pipeline (`application/checks.py:422`),
  the `--profile` flag, and `get_default_rule_profile_report` in the registry
  catalog. Findings are never disabled or re-weighted per user.

---

## 6. Stale / misleading UI text

| # | Location | Fix |
|---|---|---|
| 6.1 | `cli/menu.py` `_HELP_TEXT` (Documentation modal) | Remove the "Tools: self-check, dumps, source diff reports ... AST cache refresh" promises; self-check is now automatic (2.2) |
| 6.2 | `_app_textual_app.py:54` results-view note | Implement the raw-output toggle or fix the note |
| 6.3 | Analyze planner stale "queue"/"Execution order" notes | Remove or implement |
| 6.4 | CLI top description (`cli/entry.py:111`) | Remove "formatting commands" (2.1) and "validation" wording now that `validate-config` is gone (3.2) |

---

## 7. Decision summary

| Verdict | Items | One-line reason |
|---|---|---|
| **ADD to UI** | 1.4 (ICF), 4.2–4.4 (cyclomatic-complexity, parameter-drift, version-drift), 4.6 (`datatype-fields`) | Real, currently invisible capabilities |
| **ADD to CLI** | 2.4 (`--refresh-caches`) | Cache handling is a flag, never a UI concern |
| **AUTOMATIC** | 2.2 (self-check) | Runs in the pre-flight; no user action |
| **SPLIT + ALWAYS-ON** | 5.1 (datatype-field kinds → new `datatype-fields` analyzer; reverse consumers always loaded) | Correctness is unconditional; the cost is made visible by an explicit opt-in analyzer |
| **REMOVE** | 1.1–1.3, 1.5, 2.1 (format-icf), 2.3 (show-config), 2.7, 3.1 (syntax-check), 3.2 (validate-config), 3.4 (init), 4.1 (naming-consistency), 4.5 (no select-all), 5.1 (flag), 5.2–5.5 (sfc contracts, naming config, rule profiles) | Superseded, dead, or unwanted; everything should be in the UI or gone |
| **KEEP CLI-ONLY** | 3.3 (cache-prune), 3.5, 3.6 | Automation/CI or already-automatic (pruning) |
| **KEEP INTERNAL / API** | 2.5 (`load_program_ast`), 2.6 (`service.py`) | Building block / deliberate library API |
| **Fix text** | 6.1–6.4 | Text must match the shipped surface |

## 8. Recommended follow-up plan (ordered)

1. **Remove the superseded hidden commands** (1.1–1.3, 1.5, 2.7) and the dead
   `show_config` module (2.3).
2. **Remove the CLI subcommands**: `syntax-check` (3.1), `validate-config` (3.2),
   `init` (3.4); add `--refresh-caches` to `analyze` (2.4); fix the CLI
   description (6.4).
3. **Remove ICF formatting** (2.1) and its tests.
4. **Split datatype-field analysis into a dedicated `datatype-fields` analyzer**
   (5.1): move `unused_datatype_field`, `field_read_only`, and `field_never_read`
   out of `variables`; make reverse-consumer loading unconditional whenever it
   runs; drop the `include_reverse_library_consumers` flag. Add it to the planner
   (4.6).
5. **Register the ICF check as an analyzer** (1.4) —
   `analyzer-reference-and-rework.md` Part C. *(Done 2026-09-08; see Part C
   implementation notes.)*
6. **Unify the planner on the selectable analyzer set** (4.2–4.4); remove
   `naming-consistency` (4.1) and leave `sattline-semantics` LSP-only (4.5).
7. **Remove the SFC contract config + findings** (5.2, 5.3), the naming config
   (5.4), and rule profiles (5.5) from the config schema, sfc analyzer, registry,
   checks pipeline, and `--profile`.
8. **Wire self-check into the analysis pre-flight** (2.2).
9. **Fix stale UI text** (6.1–6.3) and decide the results raw-output toggle
   (6.2).

---

## 9. Impact — what these decisions break

Everything below is test/doc/code coupling that must be removed or updated in the
same change as the feature removal. None of the removals are one-line deletions.

### 9.1 Tests that break directly

| Removal | Tests that assert on it |
|---|---|
| 2.1 format-icf | `tests/analyzers/test_icf_validation.py` (`test_format_icf_text_*`, `test_format_icf_file_*`), `test_icf_helpers.py:70`, `test_icf_helpers_grouping.py:135` |
| 2.3 show-config | `tests/app/test_cli.py::test_show_config_command_reaches_config_display_owner` |
| 3.1 syntax-check | `tests/app/test_cli.py::test_build_cli_parser_has_descriptions` (asserts `"syntax-check" in choices`), `test_build_cli_parser_syntax_check_includes_output_format`, `test_run_syntax_check_command_*` (≈6), the handler-required test |
| 3.2 validate-config | `test_build_cli_parser_has_descriptions` (asserts `"validate-config"`), `test_build_cli_parser_validate_config_includes_output_format`, `test_run_cli_validate_config_*` |
| 3.4 init | any test exercising the `init` subcommand; the shared `init_project` function itself stays |
| 4.1 naming-consistency | `tests/analyzers/test_naming.py` (5+), `test_analyzer_guardrails.py`, `tests/analyzers/suites/test_versiondrift_initialvalues_registry.py`, `tests/helpers/analyzers_suites_support.py` (imports + analyzer list) |
| 5.2/5.3 sfc contracts | `tests/app/test_app_config_validation.py` (sfc config validation), `tests/analyzers/test_sfc.py`, `tests/analyzers/state_integrity/test_sfc_contract_and_global_coupling.py`, `test_implicit_latch_and_sfc_contract.py`, `test_sattline_semantics.py`, `test_sattline_semantics_regressions.py`, suites tests |
| 5.5 rule profiles | `tests/analyzers/test_rule_profiles.py`, config-validation tests, catalog/report tests that include `rule_profiles` |

### 9.2 Code coupling that must be removed together

- **CLI subcommands** (`3.1/3.2/3.4`): `cli/entry.py` (parsers + dispatch), the
  `command_handlers` wiring, `cli/app_commands.py` (`run_validate_config_command`,
  `run_syntax_check_command` import), `app.py` re-exports, `cli/syntax_check.py`.
  The `analyze`-only subcommand set survives.
- **naming-consistency** (`4.1`): `analyzers/naming.py`, the registry template
  (`_registry_spec_templates.py:290`), delivery metadata for `naming-consistency`,
  the `rules` context provider, the `rule_profiles.py` naming rule, config
  `analysis.naming.*` (schema, defaults, validation).
- **SFC contracts** (`5.2/5.3`): `config/types.py`, `config/defaults.py`,
  `config/validation.py` (`_SECTION_SFC_KEYS`), `project/models.py`,
  `sfc/__init__.py` (findings + config consumption), the sfc semantic rules in
  `_sattline_semantic_rules_more_data.py`, and the `_registry_specs.py` context
  providers `mutually_exclusive_steps` / `step_contracts`.
- **rule profiles** (`5.5`): `config/types.py`, `config/defaults.py`,
  `config/validation.py`, `project/models.py`, `analyzers/rule_profiles.py`,
  `application/checks.py:422` (`apply_rule_profile_to_report`), `--profile`
  (`cli/entry.py:217`), `get_default_rule_profile_report` in the registry
  catalog and its report output.
- **datatype-fields split** (`5.1`): the three kinds in the `variables` package
  (issue-kind catalog in `models/_variable_issues.py`, field-kind emission in
  `_variable_module_issue_scan.py` / `_variables_execution.py`), a new
  `datatype-fields` registry template and delivery entry, the `variables` spec
  dropping the field kinds, the loader flag consumption
  (`project/loading.py:269`, `project/loading_support.py:218`), and the
  `include_reverse_library_consumers` key in `config/types.py` /
  `config/defaults.py`.
- **self-check automatic** (`2.2`): wire into the analyze pre-flight; the
  function already exists and is covered by `tests/app/test_app_base.py`.
- **cache flag** (`2.4`): `force_refresh_ast` / `refresh_analysis_caches` are
  implemented and safe; only a flag wiring + tests are needed.

### 9.3 What does NOT break

- **`init` removal** does not touch project creation: the UI New Configuration
  uses the same `init_project` (`ui/_app_textual_actions.py:862`), so the
  function stays and the UI path is unaffected.
- **`validate-config` removal** is safe because config validation already runs on
  every load (`config/io.py`) and refuses invalid saves; no validation behavior
  is lost.
- **`cache-prune`** stays CLI-only; automatic startup pruning is unchanged.
- **`sattline-semantics`** (4.5) is already LSP-facing and batch-excluded; no
  code change needed — just don't add a Select-all.
- **`5.1` datatype-fields split** is a behavior change, not a break: the three
  field kinds move from `variables` to a new opt-in `datatype-fields` analyzer,
  and library targets that select it always load reverse consumers. Watch for
  load-time cost and any test that asserts the current
  `variables`-owns-field-kinds or manual-flag behavior in `tests/`
  (project-loading and variable-analysis suites).
