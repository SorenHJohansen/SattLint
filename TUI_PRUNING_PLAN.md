# TUI-First Pruning Plan — Remove Everything Not Reachable From the Textual UI

Status: proposal
Scope: the whole `sattlint` package
Decision rule: **if a capability is not reachable from the Textual UI, remove it —
unless there is a very good, written reason to keep it.**
Related: [`UI_PLAN.md`](UI_PLAN.md) (earlier UI-surface pass), [`ANALYZER_PIPELINE_PLAN.md`](ANALYZER_PIPELINE_PLAN.md)

---

## 1. The decision rule

Default verdict is **REMOVE**.

An item may stay only under one of these named exceptions, and the reason must be
recorded next to it:

| Exception | Meaning | Examples |
|---|---|---|
| **KEEP CLI-ONLY** | Non-interactive automation/CI needs it. The CLI is a supported surface (`PYTHON_API.md` stability table). | `analyze --check`, `--list-checks`, `--output-format json`, `cache-prune` |
| **KEEP INTERNAL** | A building block used by a TUI feature. Not a user-facing surface; not independently invokable. | project loader, AST cache, `SemanticSnapshot` used by Change Review |
| **KEEP LIBRARY-API** | A documented public API with a real external consumer. | *(none currently proven — see §8)* |

Everything else goes. "It might be useful later", "it was here before", and
"someone could import it" are **not** good reasons.

### What "in the TUI" means (the reachable surface)

The Textual shell (`src/sattlint/ui/`) exposes exactly:

- **Views** (Ctrl+1..4): Analyze, App Settings, Results, Configuration Settings (Setup).
- **Help** (Ctrl+H / `?`).
- **File actions**: Open Configuration, New Configuration, Save.
- **Analyze view actions**: analyzer list + `/` filter, *Run selected analyses*,
  *Generate Change Review*, *Cancel running*, *Clear selection*, *Clear output*.
- **Results view**: browse persisted runs, results tree, expand/collapse.
- **Setup view**: manage analysis targets and project paths.

A capability is "in the TUI" only if one of those controls invokes it.

---

## 2. Headline removals

### 2.1 The semantic aggregate ("semantic check") — **REMOVE**

`sattline-semantics` is the aggregate analyzer whose own description says *"You
normally do not run this analyzer yourself. It is the surface used by the LSP
server."* It is not in the Analyze list, not a CLI `--check` key, and not
reachable from the TUI. Remove it and its whole supporting rule engine.

| Remove | Where |
|---|---|
| `sattline-semantics` registry template | `analyzers/_registry_spec_templates.py:31-58` |
| Aggregate entry point + report | `analyzers/sattline_semantics.py` |
| Semantic rule engine | `analyzers/_sattline_semantic_models.py`, `_sattline_semantic_rules*.py`, `_sattline_semantic_rules_more_data.py`, `_sattline_semantic_rules_data.py`, `_sattline_semantic_contracts.py`, `_sattline_semantic_issue_mapping.py`, `_sattline_semantic_issue_metadata.py` |
| LSP projection dispatch | `collect_lsp_report_issues`, `get_lsp_projection_analyzers`, `get_semantic_contributor_specs` in `analyzers/_registry_dispatch.py`; `analyzers/dispatch.py` re-exports |
| LSP analyzer-key helpers | `get_actual_lsp_analyzer_keys`, `get_declared_lsp_analyzer_keys` in `analyzers/registry/__init__.py` + `analyzers/catalog.py` |
| `SEMANTIC_LAYER_ANALYZER_KEY` and every `_is_batch_dispatch_analyzer` / semantic-layer branch | `analyzers/registry/__init__.py` |
| `lsp_exposed` / `exposed_via` delivery fields and their data | `analyzers/registry/_registry_delivery*.py` |
| Semantic contributor metadata | `semantic_mapping_kind` / `semantic_rule_source` on `AnalyzerSpec` and every spec template |

This also removes the entire reason `ANALYZER_PIPELINE_PLAN.md` had to special-case
`_order_analyzers_for_batch` and `_is_batch_dispatch_analyzer`.

### 2.2 The editor/LSP public API — **REMOVE**

The package root exposes workspace-snapshot loading that only an editor/LSP client
uses. Change Review (in the TUI) does **not** use these; it uses
`build_source_snapshot_from_basepicture` directly via `change_review/loader.py`.

| Remove | Where |
|---|---|
| `discover_workspace_sources`, `load_workspace_snapshot`, `build_variable_semantic_artifacts` | `sattlint/__init__.py` |
| Completion surface: `CompletionItem`, `SemanticSnapshot.completions()` | `core/_semantic_snapshot.py`, `core/semantic.py` |
| Editor diagnostics projection (only the LSP collects diagnostics; Change Review loads *without* diagnostics) | `core/diagnostics.py`, `core/semantic_analysis.py` (`collect_variable_diagnostics`, `project_variable_issues`, `SemanticDiagnostic` emission) |
| Workspace source discovery used only by the LSP | `WorkspaceSourceDiscovery` + `discover_workspace_sources` in `core/semantic.py` |
| Docs | `PYTHON_API.md` (`sattlint.core` table, workspace snapshot rows) |

**Keep** the subset Change Review needs (see §3): `SemanticSnapshot`,
`SymbolDefinition`/`SymbolReference`, `CallSignatureOccurrence`, `CodeModel`, the
`build_snapshot_from_loaded_project` seam.

### 2.3 Stale `run_icf_validation` handler — **REMOVE**

`analysis_handler_fns()` (`cli/startup.py:200`) still registers `run_icf_validation`,
but the TUI runs ICF through the registered `icf` analyzer via `run_checks_result`.
Nothing in the TUI invokes `run_icf_validation`, and there is no CLI subcommand for
it.

| Remove | Where |
|---|---|
| Handler entry | `cli/startup.py:203` |
| Application wrapper | `application/analyze.py:40` (`run_icf_validation`) |
| Menu command implementation | `application/menu_commands.py` (`run_icf_validation` + helpers used only by it) |

Keep `project.support.configured_icf_files` and the `icf` analyzer; only the
menu-command path goes.

### 2.4 Legacy variable-analysis menu catalog — **REMOVE**

`analyzers/variable_analyses.py` maps numbered terminal-menu keys (`"1"`..`"25"`) to
`IssueKind` sets. The terminal menu is gone; the TUI selects analyzers, not issue
kinds. No non-test consumer was found.

- Remove `analyzers/variable_analyses.py` (`VARIABLE_ANALYSES`,
  `HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS`, `LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS`).
- This is the only catalog behind `analyze --issue-kind` / `--list-issue-kinds`
  (see §4.2).

---

## 3. Change Review — what to keep and why

Change Review **is** in the TUI (`Generate Change Review` button), so its dependency
chain is KEEP INTERNAL even though it is "semantic" in name. The pruning above must
not touch:

- `change_review/` (loader, review, semantic_diff, impact, context, serializers,
  settings).
- `core/semantic.py` snapshot loading (`build_source_snapshot_from_basepicture`,
  `build_snapshot_from_loaded_project`).
- `core/_semantic_snapshot.py` `SemanticSnapshot`, `_semantic_index*.py`,
  `_semantic_helpers.py`.
- `core/call_signatures.py` (`CallSignatureOccurrence` is consumed by
  `change_review/semantic_diff.py`).
- `core/document.py` **only if** Change Review or snapshot code uses `LineIndex` /
  `utf16_index_to_codepoint_offset`; verify before deleting.

Verification gate for §2.2: after removing the editor-only pieces, `pyright` and the
`change_review` tests must still pass. Anything that only the removed code imported
goes too.

---

## 4. CLI flag review

Global flags (`--config`, `--project`, `--no-cache`, `--quiet`, `--debug`,
`--version`) and `--ui` stay: standard automation surface.

| Flag | Verdict | Reason |
|---|---|---|
| `analyze --check KEY` | KEEP CLI-ONLY | The core CI entry point; the TUI is interactive-only |
| `analyze --list-checks` | KEEP CLI-ONLY | Discovery for CI scripts |
| `analyze --output-format json` | KEEP CLI-ONLY | Machine-readable CI output |
| `analyze --refresh-caches` | KEEP CLI-ONLY | Cache maintenance; deliberately no TUI button (UI_PLAN 2.4) |
| `cache-prune` | KEEP CLI-ONLY | Maintenance/reporting pass; auto-pruned at startup already |
| `--ui textual` | **REMOVE** | Interactive is Textual-only; the flag can only accept `textual` and `resolve_interactive_ui_mode` already rejects anything else. Keep the `SATTLINT_UI` validation or drop it too. |
| `analyze --profile` | **OPEN** (recommend KEEP CLI-ONLY) | Developer performance diagnostics (`SATTLINT_PROFILE`, JSONL under the cache dir). No TUI counterpart; keep only if performance debugging is still wanted. |
| `analyze --issue-kind` / `--list-issue-kinds` | **REMOVE** (recommended) | Only consumer of the removed `variable_analyses` catalog; the TUI already selects analyzers. Removes `selected_issue_kinds` plumbing across `checks.py`, `AnalysisContext`, and the variables analyzer. See §5. |
| `analyze --format` alias for list commands | KEEP CLI-ONLY | Same as `--output-format` |

---

## 5. `selected_issue_kinds` cross-cutting plumbing — **REMOVE**

If §4 drops `--issue-kind`, the whole issue-kind filter chain goes with it:

- `application/checks.py`: `normalize_selected_issue_kind_values`,
  `format_selected_issue_kind_values`, `selected_issue_kind_tuple`,
  `_filter_report_for_selected_issue_kinds`, the `spec.key == "variables"` /
  `supports_selected_issue_kinds` branches, and the `VariablesReport` special case.
- `framework.AnalyzerSpec.supports_selected_issue_kinds`; `AnalysisContext.selected_issue_kinds`.
- `_registry_specs.py` `"selected_issue_kinds"` context provider and the `variables`
  template's `context_kwargs` entry.
- `VariablesAnalyzer`'s issue-kind selection API (keep only the internal
  `datatype-fields` fixed subset if that analyzer survives the analyzer-pipeline plan).

This is the same cleanup as Phase 7 of `ANALYZER_PIPELINE_PLAN.md`; do it here if this
plan lands first.

---

## 6. Profiling and run diagnostics

`core/profiling.py` + `--profile` + `SATTLINT_PROFILE` + `_shared_artifact_profile_text`
+ `analyzer_phase_timings` / bottleneck payloads in `application/checks.py`.

- Not in the TUI.
- Used to emit JSONL performance events and extra output lines when profiling is on.
- **Verdict: OPEN.** Recommend KEEP CLI-ONLY (developer diagnostics) because it has a
  concrete, written purpose and zero TUI surface. If maximum pruning is wanted,
  REMOVE it and the timing/bottleneck plumbing it feeds.

---

## 7. Legacy non-Textual menu infrastructure

Interactive startup is Textual-only (`resolve_interactive_ui_mode` raises if Textual
is missing; `run_interactive_session` always launches the shell). Some
`cli/menu.py` helpers remain reachable through the TUI (Help modal), others are
leftovers from the removed terminal menu.

| Item | Verdict | Reason |
|---|---|---|
| `cli/menu.py: get_help_text`, `summarize_targets` | KEEP INTERNAL | Used by the TUI Help modal (`startup.get_help_text`) |
| `cli/menu.py: print_menu`, `_HELP_TEXT`, `choose_menu_option` paths | REMOVE after verification | No TUI caller; only the removed terminal menu used them |
| `cli/startup.py`: `print_menu`, `_choose_menu_option`, `menu_option`, `build_menu_interaction`, `show_help` print path | REMOVE after verification | Only used by the deleted terminal loop |
| `cli/_interaction.py` non-textual interaction helpers | REMOVE after verification | Textual bridge is the only live path |
| `application/menu_commands.py` | REMOVE | Replaced by the `icf` analyzer (§2.3) |

Verification: trace every symbol with a search before deleting; keep anything the
Textual Help/Setup paths actually call.

---

## 8. Library API and `application/service.py`

`application/service.py` is a "typed service API" for embedding. It is not reachable
from the TUI.

- **Verdict: OPEN — default REMOVE** under this plan's rule.
- Keep only if there is a proven external consumer. "We documented it" is not a
  consumer; `PYTHON_API.md` itself marks Python APIs as *Preview* and the CLI as the
  stable contract.
- If kept, it must be reclassified **KEEP LIBRARY-API** with the consumer named.

---

## 9. Ordered migration

Each step must leave `ruff`, `pyright`, and the focused tests green.

1. **Fix the Change Review boundary first.** Confirm (search) exactly which
   `core/semantic*`, `core/call_signatures`, and `core/document` symbols
   `change_review/` imports. Write that list down; it is the keep-set.
2. **Remove the semantic aggregate** (§2.1). Start with `_registry_dispatch` +
   `dispatch` + registry helpers, then delete the `sattline_semantics` module tree and
   the spec template. Update `ARCHITECTURE.md` (the "sattline-semantics" special case).
3. **Remove the editor/LSP public API** (§2.2) down to the Change Review keep-set.
   Update `PYTHON_API.md`.
4. **Remove stale handlers and menu commands** (§2.3, §7). Fix `analysis_handler_fns`.
5. **Decide the CLI flags** (§4): remove `--ui`, and `--issue-kind` /
   `--list-issue-kinds` if the decision is to drop issue-kind selection. If dropped,
   do §5 in the same change.
6. **Remove the legacy variable-analysis catalog** (§2.4).
7. **Decide profiling** (§6) and the service API (§8).
8. **Dead-code sweep**: search for every symbol removed here; delete tests, docs, and
   delivery metadata that referenced it.

---

## 10. Tests and docs to update

Likely removals/rewrites (confirm by search, do not bulk-delete):

- `tests/analyzers/test_sattline_semantics*.py`, semantic rule/contract tests.
- LSP projection tests (`collect_lsp_report_issues`, `get_lsp_projection_analyzers`,
  `get_actual_lsp_analyzer_keys`).
- `tests/core/test_semantic_analysis.py` (variable diagnostic projection) — keep only
  what Change Review covers.
- `tests/analyzers/test_icf_validation.py` menu-command cases (the analyzer cases stay).
- Any test importing `variable_analyses`.
- `tests/app/test_cli.py` cases for `--issue-kind` / `--list-issue-kinds` / `--ui`.
- `PYTHON_API.md`, `ARCHITECTURE.md`, `FEATURE_GUIDE.md`, `CLI_COMMANDS.md`,
  `SUPPORT.md` references to removed surfaces.

---

## 11. Validation

```
python -m pytest tests/change_review -q
python -m pytest tests/analyzers -q
python -m pytest tests/app -q
ruff check
ruff format --check
pyright
python -m pytest -q
```

Behavioral smoke:

```
sattlint                      # TUI opens, Analyze/Setup/Results/Help work
sattlint analyze --check variables --list-checks
```

Change Review must still generate from the TUI after the semantic core is trimmed.

---

## 12. Risks and open questions

**Risks**

- The Change Review keep-set is the whole risk of §2.2. If any editor-only symbol is
  actually used by Change Review, the build breaks; hence step 1 is a search/verify
  pass, not a guess.
- Removing the semantic rule engine removes the `SemanticRule`/`RuleMetadata`
  catalog that the registry's `to_report` emits. Confirm no TUI/tooling consumer of
  that report before deleting (the TUI does not read it).

**Open questions (need a decision before the matching phase)**

1. `analyze --profile` and `core/profiling.py`: keep as CLI-only developer
   diagnostics, or remove?
2. `analyze --issue-kind` / `--list-issue-kinds`: remove (recommended) or keep
   CLI-only? This decides §5.
3. `application/service.py`: is there a real external consumer, or does it go?
4. `--ui textual`: remove the flag outright, or keep it as an explicit
   "interactive is Textual-only" guard?
5. Is the `AnalyzerCatalog.to_report` / delivery-metadata surface (buckets,
   `lsp_exposed`, acceptance-test lists, corpus links) used by anything outside
   tests? If not, it is a candidate for the same sweep.
