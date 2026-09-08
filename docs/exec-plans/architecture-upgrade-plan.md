# SattLint Architecture Upgrade Plan

> Status: Active (Phase 1 of the unified plan complete)
> This plan is the single authority. It replaces and merges
> `application-layer-plan.md` and `architecture-reliability-refactor.md`.
>
> **Deferred:** Phases 6, 9, 10, 17 are deferred pending the analyzer
> performance optimization branch. See `analyzer-execution-refactor.md`.

## Goal

Simplify SattLint's internal architecture: dissolve the flat `_app_*`/`app_*`
modules into layered packages, make the application layer a real thin
orchestration service, remove compatibility/reflection glue, and strengthen the
test system with explicit dependency boundaries.

The desired architecture:

```text
CLI / TUI / LSP
       │
       ▼
Application layer
       │
  ┌────┴────┐
  ▼         ▼
Project   Analysis (AnalyzerRegistry)
  │         │
  ▼         ▼
ProjectGraph  SemanticSnapshot
  │         │
  └────┬─────┘
      ▼
sattline-parser
```

Core architectural rule:

> Analyzers depend on SattLint's semantic model, not on project-loading
> mechanics, CLI/UI code, parser construction, or registry implementation
> details.

Do not preserve old internal APIs merely to avoid changing callers. Prefer
changing callers and deleting obsolete compatibility layers.

---

## Current state & sizing

`src/sattlint` is ~65,900 lines: analyzers 34,418 (~52%), Textual TUI 4,060
(~6%), everything else ~27,500. Sizing by subsystem (vital vs non-vital):

| Subsystem | Lines | Vital? | Note |
|-----------|------|--------|------|
| Semantic core + resolution + string_inference | ~10,000 | Vital | The model engine; every analyzer consumes it |
| Analysis app layer (non-TUI glue) | ~4,000 | Vital | `app_analysis.py`, loading, `_run_checks` dispatch |
| Validation subsystem | ~2,940 | Borderline | Wired into load path; engine has a no-op injection — **decide scope in Phase 15** |
| Graphics + picture displays | ~2,780 | Non-vital | Kept by decision; must stay isolated in its own domain module |
| Reporting | ~1,440 | Vital | Imported directly by 5+ analyzers; needs a defined boundary (Phase 14) |
| CLI | ~1,100 | Vital | Entry point |
| Config | ~1,100 | Vital | `config_validation.py` (473) unowned (Phase 16) |
| Cache | ~1,050 | Non-vital | Has `--no-cache`; pure performance |
| Utils | ~800 | Vital | Feeds engine + `comment-code` analyzer |
| Project | ~640 | Vital | `.slproj`, `ProjectGraph` |
| Models | ~630 | Vital | `ProjectGraph`, variable-issue models |
| Application | ~430 | Vital | Thin wrapper layer (target of Phases 1–5) |

---

## Target layout

```
src/sattlint/
├── application/          # thin orchestration (services only)
│   ├── analyze.py        # analyze_project(project, options) -> AnalysisResult
│   └── project.py        # orchestration only — loading lives below
├── analyzers/            # analyzer implementation + registry
├── core/                 # semantic model, diagnostics, shared core
├── project/              # project loading service
├── resolution/           # dependency resolution (below project)
├── reporting/            # diagnostics rendering shared by analyzers
├── validation/           # structural/expression validation (per Phase 15)
├── graphics/             # graphics + picture-display domain (isolated)
├── cache/                # persistence (perf-only)
├── config/               # ConfigDict, .slproj, config.toml
├── ui/                   # Textual/rich terminal widgets
├── cli/                  # parsing, commands, startup, rendering
└── __main__.py
```

## Normative rules

### Classification test

For every function that would land in `application/`, ask:

> "Could a Python API consumer invoke this without caring that SattLint has a
> CLI?"

- **Yes** → `application/` layer.
- Knows about `argparse`, Textual, menus, stdout/stderr, keyboard input, exit
  codes → `cli/` / `ui/`.
- Knows about SattLine files, parser, project graph, semantic index →
  `project/` / `core/` / `resolution/`.

### Ownership table

Normative for every move — a function is classified by what it is, not by the
module it currently lives in:

| Responsibility | Destination |
|----------------|-------------|
| Analyze project (orchestration) | `application/analyze.py` |
| Load project (orchestration) | `application/project.py` |
| Project loading implementation | `project/` |
| Dependency graph | `project/` |
| Dependency resolution | `resolution/` (below `project/`) |
| Semantic model | `core/` |
| Analyzer implementation + registry/catalog | `analyzers/` |
| Diagnostics model | `core/` |
| Diagnostics rendering | `reporting/` |
| Structural/expression validation | `validation/` |
| Graphics + picture displays | `graphics/` |
| Cache implementation | `cache/` |
| Config parsing | `config/` |
| Text output / rendering / menus / terminal input | `cli/` / `ui/` |

### Dependency direction

```
cli / ui
    ↓
application
    ↓
project / core / analyzers
    ↓
resolution / parser / persistence
```

Rules (enforced by tests, not grep):

1. Lower layers must not import `application`.
2. Domain/core code must not import CLI/UI.
3. Analyzers must not depend on CLI/UI.
4. Analyzers depend on semantic abstractions, not project-loading details.
5. Project loaders must not depend on `engine`.
6. Production code must not depend on `tests/`.
7. Analyzer execution must not depend on reflection when a typed callable works.
8. Internal analyzer keys are canonical.
9. Compatibility code exists only for intentional public compatibility.
10. Non-vital subsystems (cache, graphics) stay isolated behind their domain
    boundary.

---

## Completed work (from the application-layer plan, Phases 1–5)

All gates green at completion (pyright strict 0 errors, ruff check + format
clean, full pytest green):

- **Phase 1** — engine alias surface decoupled.
- **Phase 2** — `application/` package created.
- **Phase 3** — CLI wiring made `app_module`-free; `app.py::main`/`cli` delegate
  to `cli/startup`.
- **Phase 4** — Textual shell binds direct handler functions; interaction state
  owned by `application/_interaction.py`.
- **Phase 5** — deleted the 7 legacy facade/from-app modules; `app.py` is a thin
  re-export entry point.
- Slim-down work (prior): investigation/debug tools, `format-icf`, classic
  menus, catalog/planner deleted; TUI Analyze rebuilt on the registry; dead
  modules/functions removed.

---

## Unified phases

### Unified-plan completions

- **Phase 1 (of this plan) — Move CLI concerns fully out of `application/`**:
  CLI interaction (`_interaction.py`, `interaction.py`) moved from `application/`
  to `cli/`; `require_targets_for_menu_action` relocated from `application/project.py`
  to `cli/startup.py`; removed hardcoded `pause`/`print_output` defaults from
  `application/analyze.py` and `application/project.py`; `app.py` re-exports
  re-pointed; tests updated. All gates green.

### Part A — Layering

#### Phase 1 — Move CLI concerns fully out of `application/` ✅ COMPLETE

`application/` must contain service-style operations only.

- Confirm `cli/` owns all command implementations (`run_cli`,
  `run_validate_config_command`, `run_analyze_command`, `run_cache_prune_command`,
  `show_config`) and the interactive startup/menu code (`cli/startup.py`).
- Keep `application/project.py` thin — orchestration only; no loading details.
- `application/` keeps only operations that pass the classification test.
- `app.py` re-exports re-pointed; tests retargeted.

Acceptance: every function in `application/` passes the classification test.

#### Phase 2 — Dissolve the flat `_app_*`/`app_*` implementation modules

> **Phase 2 progress (substages 2a–2h ✅ COMPLETE).**
>
> - **2a ✅** Created `src/sattlint/ui/` — moved `app_textual.py`, `_app_textual_*`
>   (10 modules) and `app_textual.tcss` into it; `ui/__init__.py` is the facade;
>   `app.py` and `cli/startup.py` re-pointed; `tests/test_app_textual.py` retargeted
>   to `sattlint.ui`; root `_app_textual_*`/`app_textual.py`/`app_textual.tcss` trashed.
> - **2b ✅** `_app_debug.py` → `core/debug.py`; `_app_analysis_variable_analyses.py`
>   → `analyzers/variable_analyses.py`; consumers (`_app_analysis_loading*`,
>   `app_analysis.py`, `tests/test_app_debug.py`) retargeted; root files trashed.
> - **2c ✅** `analysis_catalog.py` → `analyzers/catalog.py`; `analysis_dispatch.py`
>   → `analyzers/dispatch.py`; consumers (`app.py`, `app_analysis.py`,
>   `application/analyze.py`, `semantic_analysis.py`, `cli/entry.py`,
>   `tests/test_full_analysis_crash_sweep.py`) retargeted; root files trashed.
>   `test_analyzer_architecture.py` boundary rule still green.
> - **2d ✅** `_app_analysis_loading.py` → `project/loading.py`; the
>   `_app_analysis_loading_support.py` helpers → `project/loading_support.py`;
>   `app_analysis.py` and `tests/test_app_analysis_part3.py` retargeted; root files
>   trashed.
> - **2e ✅** Reporting helpers split to `reporting/target_report.py` and
>   `project/cache.py` (AST/report cache moved under `project/`); consumers
>   (`app_analysis.py`, `_app_analysis_checks.py`, `_app_analysis_commands.py`,
>   `application/`) retargeted; root reporting shims removed.
> - **2f ✅** `app_base.py` dissolved into `core/terminal.py`, `core/logging.py`,
>   `core/interaction.py`, `cli/syntax_check.py`, `cli/config.py` with consumer
>   retargets (`app.py`, `cli/startup.py`, `cli/_interaction.py`,
>   `cli/app_commands.py`, `cli/command_handlers.py`, `tests/test_app_base.py`,
>   `tests/test_cli.py`, `tests/test_app_textual.py`); `app_base.py` trashed.
>   `app_support.py` dissolved into `project/support.py` (canonical target/ICF/csv
>   queries, warning helpers, `TargetLoadError`) and `cli/menu.py` (menu/help
>   presentation); consumer retargets (`app.py`, `app_analysis.py`,
>   `cli/startup.py`, `cli/_interaction.py`, `cli/rich_output.py`,
>   `application/project.py`, `application/analyze.py`,
>   `_app_analysis_commands.py`, `tests/test_app_support_helpers.py`,
>   `tests/test_app_analysis_part3.py`); the `app_support` DI seams in
>   `project/loading*.py` removed (dead duplicates deleted); `app_support.py`
>   trashed. `application/project.py` now binds `project/support.py` directly.
> - **2g ✅** `app_analysis.py`, `_app_analysis_checks.py`, `_app_analysis_commands.py`
>   dissolved into `application/` (project loading orchestration and cache wrappers
>   in `application/project.py`, checks/run orchestration in `application/checks.py`,
>   per-command implementations in `application/commands.py`, output glue in
>   `application/output.py`, `flush_stdout()` in `core/terminal.py`); all src
>   consumers (`app.py` facade aliases, `application/analyze.py`,
>   `cli/startup.py`, `cli/app_commands.py`) and tests (`test_app_analysis_part1–4`,
>   `test_app_analysis_project_cache.py`, `test_app_config_validation.py`,
>   `_app_analysis_test_support.py`) retargeted; `app.py` public surface kept
>   (`DEFAULT_CONFIG`, `EXIT_*`, `VARIABLE_ANALYSES`, `analyze_variables`,
>   `validate_icf_entries_against_program`, `app_analysis_checks`/
>   `app_analysis_commands` aliases); call-time vs def-time monkeypatch semantics
>   preserved (module-global reads for `analyze_variables`/`analyze_shadowing`/
>   `AnalysisReportCache`/`get_cache_dir`/`compute_analysis_report_cache_key`/
>   `emit_output`/`ASTCache`/`parse_icf_file`/`validate_icf_entries_against_program`);
>   the three flat modules trashed; all gates green (1069 passing, pyright strict,
>   ruff, `ruff format --check`).
>
> - **2h ✅** `_app_startup.py` and `_app_interactive_menus.py` dissolved into
>   `cli/startup.py` (merged `main` keeps the full module-function DI defaults;
>   `run_interactive_session` now defaulted via `run_main_loop_fn` so `app.main`
>   still injects `app.run_interactive_session`) and `cli/app_commands.py`
>   (`run_validate_config_command`, `run_analyze_command`,
>   `run_cache_prune_command`, `show_config` inline with
>   `emit_output_fn=console_module.print_output`); `InteractiveCliOverrides`/
>   `resolve_interactive_cli_overrides` moved to `cli/startup.py`; `show_config`
>   duplicate removed from `cli/startup.py`; the two flat modules trashed; tests
>   retargeted (`tests/test_cli.py` — 8 `startup_application.main(` call sites plus
>   menu-helper delegation rewrites; `tests/test_app_cli_commands.py` — command
>   delegation rewrites patching `cli/` owners); new
>   `tests/test_dependency_guard.py` AST/import-graph guard covering
>   `application`→`app`/`app_*`/`_app_*`, `core`/`project`→`application`+`cli`,
>   `resolution`→`application`+`project`, `analyzers`→`application` and the
>   reporting-internals rule; all gates green (1072 passing).
>
> All gates green (1072 passing) after each substage; Phase 2 complete.

Replace flat root modules with layered packages so `application/` depends only
on `project/core/analyzers/resolution/reporting/validation`.

**Classify function-by-function, never file-by-file.** The ownership table is
the authority, not the current module layout.

- `app_analysis.py` mixes analyzer execution, definitions, report formatting,
  configuration, and orchestration — split by concept.
- `app_base.py` → `core/` (CLI-independent primitives).
- `app_support.py` → `project/` + `core/` by content.
- `app_textual.py`, `_app_textual_*` → `ui/`.
- `_app_analysis_*.py`, `_app_startup.py`, `_app_interactive_menus.py` →
  `ui/`/`cli/`/`core/` by content, not origin.
- `analysis_catalog.py` stays the registry surface (or moves under
  `analyzers/`).
- Update imports; delete now-unused legacy modules.

Acceptance: no mixed-concept flat module survives; the dependency-guard test
(mechanical enforcement below) is green.

#### Phase 3 — Simplify `engine.py` to orchestration

> **Phase 3 progress (substages 3a–3f).**
>
> - **3a ✅** Cache implementation moved under `cache/`: `cache.py` → `cache/__init__.py`
>   (facade, `__all__`), `_cache_classes.py` → `cache/classes.py`,
>   `_cache_manager.py` → `cache/manager.py`; internal/computed-mode imports
>   retargeted (`from .. import cache as cache_module`,
>   `from .._config_defaults import PROJECT_CACHE_CONFIG_KEYS`);
>   `tests/test_cache_classes.py` retargeted to `sattlint.cache.classes`; root
>   `cache.py`, `_cache_classes.py`, `_cache_manager.py` trashed. All gates green.
> - **3b ✅** Graphics handling moved under `graphics/`: `graphics_validation.py` →
>   `graphics/validation.py`, `_graphics_validation_bindings.py` →
>   `graphics/validation_bindings.py`, `picture_display_paths.py` →
>   `graphics/picture_display_paths.py`, `_picture_display_path_runtime*.py` →
>   `graphics/picture_display_runtime*.py`, `_engine_graphics_helpers.py` →
>   `graphics/graphics_helpers.py`, `_engine_graphics_context_helpers.py` →
>   `graphics/graphics_context_helpers.py`; consumers (`_engine_syntax_helpers.py`,
>   `engine.py`, `_engine_project_loader.py`, `analyzers/picture_display_paths.py`,
>   `analyzers/variables/_variables_picture_display_support.py`) and 6 test files
>   retargeted; 7 root graphics modules trashed. All gates green.
> - **3c ✅** Validation subsystem moved under `validation/`:
>   `validation.py` → `validation/__init__.py` (facade, keeps `__all__`),
>   `_validation_shared.py` → `validation/shared.py`, `_validation_expression.py` →
>   `validation/expression.py`, `_validation_sequences.py` → `validation/sequences.py`,
>   `_validation_structure_core.py` → `validation/structure_core.py`,
>   `_validation_structure_modules.py` → `validation/structure_modules.py`,
>   `_validation_type_helpers.py` → `validation/type_helpers.py`; subtree relative
>   imports deepened (`.grammar`/`.resolution.type_graph`/`.types` → `..*`);
>   consumers of `_validation_shared`/`_validation_type_helpers` retargeted
>   (`engine.py`, `_engine_syntax_helpers.py`, `_engine_loader_base.py`,
>   `_engine_project_loader.py`, `graphics/graphics_helpers.py`,
>   `graphics/graphics_context_helpers.py`, `string_inference.py`,
>   `analyzers/shared/_validators.py`, `analyzers/variables/_variables_contracts.py`,
>   `analyzers/variables/_variables_string_overflow.py`); 7 root validation modules
>   trashed. All gates green (1072 passing).
> - **3d ✅** Parsing/validation-surface split of `_engine_syntax_helpers.py`:
>   `core/syntax.py` (parsing + syntax validation surface),
>   `core/libraries.py` (`expected_unavailable_library_reason`/
>   `is_expected_unavailable_library`; removed later by
>   `library-resolution-and-config-cleanup.md` P1), `project/loading.py`
>   (`record_project_failure`/`record_project_warning`/`format_debug_*`/
>   `is_within_directory`); consumers retargeted (`_engine_loader_base.py`,
>   `_engine_loader_config.py`, `_engine_project_loader.py`, `engine.py`,
>   `graphics/graphics_helpers.py`, `graphics/graphics_context_helpers.py`,
>   `core/_semantic_helpers.py`, `project/support.py`); original
>   `_engine_syntax_helpers.py` trashed. All gates green.
> - **3e ✅** Loader relocated under `project/`: `_engine_loader_base/config/lookup` →
>   `project/loader_base.py`/`project/loader_config.py`/`project/loader_lookup.py`,
>   `_engine_project_loader.py` → `project/loader.py`;
>   `_engine_dependency_helpers.py` → `resolution/dependency_versions.py`;
>   `merge_project_basepicture` moved to `models/project_graph.py` (engine still
>   re-exports it for the DI seam); `core/semantic.py` retargeted off `engine`
>   (`core.syntax.CodeMode`, `project.loader*`, `models.project_graph.merge_*`),
>   breaking the `core → engine` cycle; all 5 `_engine_loader*`/
>   `_engine_dependency_helpers` originals trashed; no `core`/`project`/
>   `resolution` module imports `engine` anymore. All gates green (1072 passing).
> - **3f ✅** `engine.py` slimmed to orchestration: duplicate local
>   `merge_project_basepicture` body replaced by a re-export wrapper over
>   `models.project_graph`; dead `dump_parse_tree`/`dump_ast`/
>   `dump_dependency_graph`/`_get_dump_dir` removed (no callers in src/tests);
>   `__all__` narrowed accordingly; `tests/test_dependency_guard.py` extended with
>   `test_engine_is_not_imported_below_the_top_layers` (only `application`/`cli`/
>   root facade may import `sattlint.engine`). All gates green (1073 passing).
>
> **Phase 3 ✅ COMPLETE** — `engine.py` is composition/orchestration only; every
> `_engine_*` helper module has been dissolved into its owning package
> (`cache/`, `graphics/`, `validation/`, `core/`, `project/`, `resolution/`,
> `models/`); lower modules never import `engine`; public engine APIs stay typed.
>

Reduce `engine.py` to composition, not a service locator / export hub. Move
implementation to the owning package:

- parsing → parser-related module
- project loading → `project/`
- dependency resolution → `resolution/`
- validation → `validation/`
- graphics handling → `graphics/`
- cache implementation → `cache/`

Avoid replacing the current `_engine_*` split with an even larger number of
helper modules — merge modules that do not represent real boundaries.

Acceptance: `engine.py` has a narrow responsibility; lower modules never import
it; public engine APIs stay typed.

#### Phase 4 — Fix loader dependency direction

> **Phase 4 ✅ COMPLETE.** Removed the `engine_module: Any` service-locator
> injection from the project-loading layer:
> - `project/loading.py` now imports the loader directly
>   (`build_project_loader_from_type(SattLineProjectLoader, ...)` from
>   `.loader`/`.loader_config`) and resolves the graph itself instead of calling
>   `engine_module.load_project_graph` / `engine_module.build_project_loader`;
>   `validate_loader_config`, `merge_project_basepicture`, and
>   `resolve_graphics_companion_path` are imported from their owners
>   (`.loader_config`, `..models.project_graph`, `..graphics.graphics_context_helpers`).
> - `record_project_failure`/`record_project_warning`/`format_debug_list`/
>   `format_debug_missing_entries` moved from `project/loading.py` to
>   `project/loading_support.py` (broke a `loading ↔ loader` import cycle and
>   placed graph-mutation/debug helpers beside the loader that uses them).
> - `_include_reverse_library_consumers` takes a typed
>   `is_within_directory_fn: Callable[[Path, Path], bool]` instead of `engine_module`.
> - `application/project.py` and `application/commands.py` no longer import
>   `engine`; `app.py`'s dead `engine_module` attribute removed; test
>   monkeypatch targets retargeted to `project.loading`/`application.commands`.
> - Only `cli/syntax_check.py` (top layer) still imports the public `engine`
>   facade; no project-loader module imports `sattlint.engine`, no dynamic
>   `engine` import remains. All gates green (1073 passing).

Remove `ProjectLoader → engine`. The loader must not dynamically import
`sattlint.engine` for parser factories or helpers. Instead move shared
functionality to its owner or inject dependencies; `engine` wires them.

```text
engine/application
    │
    ▼
ProjectLoader
    │
    ▼
lower-level services
```

Prefer explicit typed dependencies over `importlib` lookups.

Acceptance: no project-loader module imports `sattlint.engine`; no dynamic
`engine` import for normal operation; loader unit-testable with injected
services.

#### Phase 5 — Establish the application service contract (mandatory)

> **Phase 5 progress (additive typed service).**
>
> - **5a ✅** Added `application/service.py`: the typed service API.
>   - `Project` — deliberate domain handle (frozen dataclass): `name`,
>     `base_picture`, `graph`, `config`, `entry_file`, `workspace_root`. Callers
>     no longer juggle raw `(BasePicture, ProjectGraph)` tuples.
>   - `AnalysisOptions` — typed application options (frozen dataclass):
>     `selected_analyzer_keys`, `selected_issue_kinds`,
>     `collect_variable_diagnostics`, `debug`; deliberately decoupled from the
>     full `ConfigDict`/CLI/UI configuration.
>   - `load_project_handle(cfg, target_name, ...) -> Project` — thin wrapper
>     over the existing load flow that returns a typed `Project`.
>   - `analyze_project(project, options) -> ProjectAnalysisResult` — owns the
>     `Project → SemanticSnapshot → Analyzer execution → AnalysisResult`
>     pipeline: builds the `SemanticSnapshot` via
>     `core.semantic.build_snapshot_from_loaded_project`, dispatches the selected
>     analyzers through the registry, and returns `ProjectAnalysisResult`
>     (`project`, `snapshot`, `analyzer_reports`, `selected_analyzer_keys`).
>   - Exported through `application/__init__.py`.
> - **5b ✅** `tests/test_app_service.py` exercises the contract: snapshot
>   construction + default analyzer run, selected-analyzer filtering, issue-kind
>   propagation, and `load_project_handle` typing. All gates green (1077
>   passing).
> - Additive by design: existing `run_*`/`collect_run_checks_result` terminal
>   surfaces are untouched; terminal-facing flows can migrate to
>   `analyze_project` incrementally.

Reshape application operations into typed orchestration decoupled from
`ConfigDict` and the terminal:

```python
analyze_project(project: Project, options: AnalysisOptions) -> AnalysisResult
```

- `project` is a deliberate domain object, not an ambiguous
  `ProjectGraph`/AST/path.
- The caller does not build a `SemanticSnapshot`; the application layer does:

  ```text
  Project → SemanticSnapshot → Analyzer execution → AnalysisResult
  ```

- Introduce `AnalysisOptions` instead of passing `config` directly. Deliberately
  separate application options, project configuration, CLI configuration, and
  UI configuration.
- `application/project.py` exposes a minimal `load_project(...) -> Project`;
  resolution stays hidden behind `project/` → `resolution/`.

Acceptance: `application/` has a well-defined typed service API; it is the
final completion criterion for Part A.

### Part B — Registry

#### Phase 7 — Validate analyzer dependency graphs at construction

> **Phase 7 ✅ COMPLETE.** Construction-time analyzer dependency validation in
> `analyzers/registry/__init__.py`:
> - `validate_analyzer_dependencies(specs)` rejects duplicate keys, colliding
>   canonical keys (via `canonicalize_analyzer_key`), unknown required
>   analyzers, self-dependencies, and dependency cycles, raising
>   `AnalyzerDependencyGraphError` (a `ValueError`) with all conditions reported
>   together. Validation happens once at catalog construction, not via recursive
>   runtime behavior.
> - `deterministic_dependency_order(specs)` returns a stable dependency-first
>   order (dependencies precede dependents; unrelated analyzers keep input
>   order).
> - `get_default_analyzer_catalog()` now validates and orders specs before
>   building metadata.
> - `tests/test_analyzers_registry_dependency_graph.py` covers every invalid
>   condition plus valid deterministic ordering. All gates green (1085 passing).

Reject invalid graphs when the registry is constructed: duplicate keys, unknown
required analyzers, self-dependencies, cycles, colliding canonical keys.
Validate once, not via recursive runtime behavior.

Acceptance: tests exist for each invalid condition; a valid registry yields a
deterministic dependency order.

#### Phase 8 — Canonicalize analyzer keys

> **Phase 8 ✅ COMPLETE.** Canonical key handling unified on the registry
> canonicalizer:
> - `analyzers/_registry_dispatch.py` replaced its casefold-only `_canonical_key`
>   with `registry_module.canonicalize_analyzer_key` (alias-aware); selection,
>   spec lookup, LSP projection, and requirement satisfaction all normalize via
>   the canonical boundary function instead of ad hoc `.casefold()`.
> - `analyzers/registry/get_default_cli_analyzers` keys its enabled-analyzer map
>   by canonical keys.
> - Internal maps (`reports_by_analyzer_key`, requirement checks) hold canonical
>   keys; `requires` values in templates are already canonical.
> - Legacy aliases retained only in `LEGACY_ANALYZER_KEY_ALIASES` as documented
>   user-facing compatibility (`config_drift` → `config-drift`, etc.).
> - `tests/test_analyzers_registry_canonical_keys.py` covers alias mapping,
>   canonical internal keys, backward-compatible lookup (aliases + case
>   variants), and unknown-key rejection. All gates green (1092 passing).

Invariant: all analyzer keys are canonical internally; canonicalization happens
at the boundary. Remove repeated `.casefold()`/normalization; drop duplicate key
representations; retain aliases only as documented user-facing compatibility.

Acceptance: internal maps hold canonical keys; dependency checks use them;
lookup stays backward-compatible where required.

### Part C — Domain structure & boundaries

#### Phase 11 — Introduce a typed `SemanticIndex` result object

> **Phase 11 ✅ COMPLETE.** `SemanticIndex` frozen dataclass
> (`symbol_table`, `type_graph`, `definitions`, `definitions_by_key`,
> `moduletype_index`, `references_by_file`, `references_by_definition_key`,
> `call_signatures`) replaces the 8-element tuple from
> `SemanticIndexBuilder.build()`. `core/semantic.py` consumes named attributes;
> `tests/test_semantic_analysis.py` retargeted; no `result[0]` indexing remains.
> Behavior-preserving.

Replace the multi-value/8-element tuple returned by semantic-index construction
with a typed object (`symbol_table`, `type_graph`, `definitions`,
`definitions_by_key`, `moduletype_index`, `references_by_file`,
`references_by_definition_key`, `call_signatures`). Update callers to named
attributes; no `result[0]` indexing remains. Behavior-preserving.

#### Phase 12 — Reconsider `SemanticSnapshot` structure

> **Phase 12 ✅ COMPLETE.** `_semantic_snapshot_types.py` merged into
> `_semantic_snapshot.py` — the types/base-dataclass split existed only to keep
> the heavy query facade separate; it had a single consumer (the facade) and no
> import cycle, so it was a pure cycle-avoidance split. The merged module now
> holds model types + factories + `SemanticSnapshot` query methods as one
> cohesive snapshot model. `semantic.py`, `_semantic_helpers.py`,
> `_semantic_index.py`, `_semantic_index_reference_support.py` retain real
> domain boundaries. No behavior change; originals trashed.

Review `_semantic_snapshot.py`, `_semantic_snapshot_types.py`, `semantic.py`,
`_semantic_helpers.py`, `_semantic_index.py`,
`_semantic_index_reference_support.py`. Merge splits that exist only to avoid
historical import cycles; keep real domain boundaries. No behavior change.

#### Phase 13 — `string_inference.py` structure review

`string_inference.py` is 1,716 lines — the largest single non-analyzer file and
vital (feeds `variables` string-overflow). Apply the same merge/split discipline
as Phase 12: split or reorganize by real concepts (cursor-aware builtin
handling, exact string inference). No behavior change.

#### Phase 14 — Define the reporting boundary

> **Phase 14 ✅ COMPLETE.** `reporting/__init__.py` documents the stable
> boundary: analyzers emit structured results (model types such as `IssueKind`,
> `VariableIssue`, `ICFEntry`, `MMSInterfaceHit`); `reporting/` owns public
> model types and rendering; rendering helpers stay private
> (`_variables_report_rendering`). Verified: no analyzer imports
> `reporting._*` (dependency-guard `test_analyzers_use_only_the_public_reporting_surface`
> covers all analyzer files via `rglob`), and no analyzer touches renderers.
> `reporting/` is not a compatibility facade.

`reporting/` (~1,440) is imported directly by 5+ analyzers. Make it a stable,
documented boundary: analyzers emit structured results; `reporting/` renders
them. Remove any analyzer→reporting renderer coupling that is accidental, and
keep reporting out of the compatibility/facade pattern. Add a dependency-guard
rule so analyzers depend on reporting's public surface only.

#### Phase 15 — Decide the validation subsystem scope

> **Phase 15 ✅ COMPLETE.** **Decision: Option A — core infrastructure.**
> The validation subsystem is load-path-mandatory: `project/loader.py` calls
> `validate_single_file_syntax`/`validate_transformed_basepicture*` directly and
> raises `StructuralValidationError` on failure; `syntax-check` uses the same
> typed public API. It already lives under `validation/` (Phase 3c) with a typed
> public API. The remaining `engine.parse_source_file` no-op injection is an
> explicit, documented raw-parse helper for analyzer unit tests (unvalidated
> ASTs by design); validation stays mandatory on the load path. Rationale
> recorded in the module docstring.

The validation subsystem (~2,940) is wired into the load path
(`validate_transformed_basepicture*` in `_engine_project_loader.py`) and
`syntax-check`, but the engine exposes a no-op injection
(`validate_transformed_basepicture_fn=lambda _bp: None`). Decide explicitly:

- **Option A — core infrastructure:** keep it load-path-mandatory; move under
  `validation/` with a typed public API.
- **Option B — gated feature:** make it an opt-in validation layer invoked by
  `syntax-check` and explicit checks, off the mandatory analysis path.

Record the decision and its rationale; then place the code in the chosen layer.
This is the largest unowned chunk and the main open architectural question.

#### Phase 16 — Config ownership

> **Phase 16 ✅ COMPLETE.** Config consolidated under `config/`:
> `config.py` → `config/__init__.py` facade; `config_types.py` →
> `config/types.py`; `config_validation.py` → `config/validation.py`;
> `config_io.py` → `config/io.py`; `_config_defaults.py` →
> `config/defaults.py`; `_config_display.py` → `config/display.py`;
> `_config_paths.py` → `config/paths.py`; `_config_self_check.py` →
> `config/_self_check.py` (renamed to avoid submodule shadowing the facade
> `self_check` function). The `ConfigDict`/`TOP_LEVEL_CONFIG_FIELDS` contract
> assertion remains the single source of truth
> (`config/defaults.py::_assert_top_level_config_contract`). ~25 src/test
> importers retargeted; root originals trashed; facade preserves the public
> surface (`config_module.*`). All gates green (1092 passing).

`config_validation.py` (473) plus types/io/defaults/display/self-check (~1,100)
have no owning phase. Consolidate config under `config/`, split
`config_validation.py` by concept if needed, and keep the
`ConfigDict`/`TOP_LEVEL_CONFIG_FIELDS` contract assertion as the single source
of truth.

### Part D — Reliability & tests

#### Phase 18 — Semantic invariants

> **Phase 18 ✅ COMPLETE.** `tests/test_semantic_invariants.py` covers repeated
> build equivalence, unique canonical identities, definition-by-key indexing,
> reference identity/location validity, source-location validity, deterministic
> queries, and required definition fields. Independent of individual analyzers.

Tests for: references resolve to a definition or an explicit unresolved state;
canonical identities unique; definitions/references deterministic; source
locations valid; type relationships internally consistent; repeated builds
equivalent. Independent of individual analyzers.

#### Phase 19 — Project graph invariants

> **Phase 19 ✅ COMPLETE.** `tests/test_project_graph_invariants.py` covers
> unique node/origin recording, deterministic re-indexing, deterministic
> `merge_project_basepicture`, strict vs non-strict missing-library behavior,
> expected-unavailable vs missing distinction, and casefolded deterministic
> dependency edges.

Tests for: unique nodes; deterministic dependency edges; circular-dependency
detection; consistent missing dependencies; external/proprietary dependencies
distinguishable from missing files; intentional strict/non-strict behavior;
repeated loads produce equivalent graphs.

#### Phase 20 — Corpus regression exactness

> **Phase 20 ✅ COMPLETE.** `tests/test_corpus_regression_exactness.py` runs 54
> semantic-layer corpus manifests through `analyze_sattline_semantics` and
> asserts exact expectations: expected finding IDs present, forbidden finding
> IDs absent, scoped `finding_count`, and per-rule counts. One stale manifest
> (`analyzer-fault-handling.json`) was corrected to match the verified analyzer
> output (an exactness harness catching drift). A second test asserts production
> code never imports `tests`/corpus modules. Non-semantic per-analyzer manifests
> remain covered by existing fixture-integration tests.

Canonical corpus cases support exact expectations: total finding count, rule
counts, finding identity/location where stable, no unexpected findings. Keep
corpus metadata out of production runtime — an installed wheel must behave
correctly without `tests/`.

#### Phase 21 — Corpus differential reporting

> **Phase 21 ✅ COMPLETE.** `src/sattlint/corpus_diff.py` provides
> `diff_corpus_findings(baseline, current) -> CorpusDiff` (added, removed,
> count changes keyed by stable finding id). `tests/test_corpus_differential_reporting.py`
> covers identical/empty diffs, added/removed findings, count changes, and
> stable identity.

Make corpus runs reviewable as before/after diffs: added findings, removed
findings, changed counts, changed rules, based on stable finding identity.

#### Phase 22 — Parser compatibility testing

> **Phase 22 ✅ COMPLETE.** `tests/test_parser_compatibility.py` documents the
> declared `sattline-parser` policy (`>=2026.8.1,<2027` from `pyproject.toml`),
> asserts the installed version is within range and the requirement is pinned,
> verifies the core parser API surface (`parse_source_text`,
> `read_text_with_fallback`, `describe_parse_error`, `is_compressed`,
> `preprocess_sl_text`, `SLTransformer`), and parses representative fixtures
> (`EnableExpr.s`, `MiscIssues.s`, `PowerUp.s`, `TestOverFlow.s`).

Define the supported `sattline-parser` version policy explicitly; CI tests the
minimum and current/latest supported versions; use representative fixtures for
all features relying on parser behavior.

#### Phase 23 — Coverage non-regression

> **Phase 23 ⏸ DEFERRED — SUPERSEDED by `enforcement-gaps.md` Phase 4.** An
> aggregate coverage floor (`--cov-fail-under=80`) is now enforced in `ci.yml`
> (single combined run, the "lighter approach" noted below). The floor only
> ratchets up; it is never lowered. Optional per-module floors for the vital
> core (`core/`, `project/`, `analyzers/`) remain a later ratchet step.
> A `test_coverage_non_regression.py` measuring core-module coverage floors was
> drafted but requires running the full analyzer suite recursively (heavy + slow);
> the CI `--cov` floor supersedes it.

Keep coverage as a signal, not a vanity number. After the baseline is
established: prevent decrease, ensure core/project/analyzer execution paths are
covered, keep corpus tests mandatory. A modest non-regression threshold is
preferable to an arbitrary high number.

### Root-package cleanup (post Part D)

Cleaned the `src/sattlint/` root surface: loose modules were relocated to their
owning packages so the root holds only entry/facade files plus the fuzzers.

- `semantic_analysis.py`, `call_signatures.py`, `tracing.py` → `core/`
- `casefolding.py`, `repo_paths.py` → `utils/`
- `cli_output.py`, `_exit_codes.py` → `cli/`
- `string_inference.py` → `analyzers/`
- `corpus_diff.py` → `reporting/`
- `console.py` **kept at root** — it is a cross-cutting terminal-output
  primitive imported by `config/`, `application/`, `cli/`, and `app.py`;
  moving it into `core/` introduced an import cycle
  (`config.io → core.console → core/__init__ → core.semantic → … →
  core.telemetry → config.io`), so it stays as a root leaf alongside
  `types.py`.
- Empty `contracts/` directory deleted.
- All src/test importers retargeted; root originals trashed. All gates green
  (1174 passing).

Root now holds: `app.py`, `console.py`, `engine.py`, `__init__.py`,
`__main__.py`, `__version__.py`, `types.py`, and the three fuzzers
(`engine_fuzzer.py`, `icf_fuzzer.py`, `syntax_fuzzer.py`).

---

## Mechanical enforcement

The ownership rules must be enforced by a **test**, not grep. Add an
AST/import-graph dependency-guard test covering the forbidden imports:

```text
application → app_*
application → _app_*
core        → application
project     → application
resolution  → application
analyzers   → application
core        → cli
project     → cli
resolution  → project
analyzers   → reporting internals (only the public reporting surface)
```

A violation fails CI.

---

## Definition of Done

This plan:
- Canonical corpus cases enforce exact expected behavior.
- Production code has no dependency on `tests/fixtures/corpus`.
- Project loader no longer imports/dynamically loads `engine`.
- Semantic index uses a typed `SemanticIndex` object.
- Analyzer dependency graphs are validated; internal keys are canonical.
- `engine.py` is orchestration, not a service locator.
- `application/` is a thin typed service layer (`analyze_project`).
- Reporting and validation have defined boundaries (Phases 14–15).
- Semantic and project invariants are tested.
- Corpus differential reporting is available.
- Supported parser versions are explicitly tested.
- Coverage cannot silently regress.
- Architecture dependency rules are enforced by tests.
- Gates: `pyright src/sattlint` 0 errors, `ruff check` clean, `ruff format --check` clean, full pytest green.
- Installed-package behavior works without repository test files.
- No functionality or diagnostic behavior changes unintentionally.

Deferred to `analyzer-execution-refactor.md`:
- Analyzer execution uses typed callable definitions (Phase R1).
- Obsolete compatibility/monkeypatch/facade mechanisms are removed (Phase R3).
- Analyzers are independent except for explicit dependencies (Phase R4).

---

## Implementation principles

- Make one phase at a time; keep the repository green between phases.
- Prefer deleting indirection over relocating it.
- Move responsibilities by domain, not by historical filename.
- Do not add abstractions unless they remove real coupling.
- Preserve behavior unless the phase explicitly changes test/architecture
  behavior.
- When removing compatibility code, update callers/tests rather than adding
  another wrapper.
- After each phase, inspect imports and dependency direction, not just test
  results.
- Non-vital subsystems (cache, graphics) stay isolated; do not let them
  entangle with the core path while relocating them.
