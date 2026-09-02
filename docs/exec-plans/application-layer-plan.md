# Application-Layer Refactor Plan

> Status: Active (Phases 1–5 complete; Phases 6–8 defined, not started)
> Branch context: `refactor/remove-app-facade`

## Goal

Make the application layer a real, thin orchestration package instead of another
collection of `_app_*`/`app_*` facade modules. The layer answers one question:

> "What does SattLint do as an application?"

It orchestrates lower-level services but does **not** implement them.

## Target Layout

```
src/sattlint/
├── application/          # thin orchestration (services only)
│   ├── __init__.py
│   ├── analyze.py        # analyze_project(project, options) -> AnalysisResult
│   └── project.py        # orchestration only — project loading lives below
├── analyzers/            # analyzer implementation + registry
├── core/                 # semantic model construction, diagnostics, shared core
├── project/              # project loading service
├── resolution/           # dependency resolution (below project)
├── ui/                   # terminal widgets (Textual/rich)
├── cli/                  # CLI: parsing, commands, startup, rendering
└── __main__.py
```

## Dependency Direction

```
cli ───────────────┐
ui ────────────────┤
lsp ───────────────┤
                   ▼
             application
                   │
          ┌────────┼────────┐
          ▼        ▼        ▼
       project    core   analyzers
          │
          ▼
      resolution
```

`application` sits **above** those components; nothing below it depends on it.

Two refinements to the base picture:

- **`resolution` lives below `project`.** If `resolution/` is purely
  dependency-resolution machinery, `application` should not know about it
  directly. The resolution mechanism is hidden behind the project service:

  ```
  application
      ↓
  project service
      ↓
  resolution
  ```

- **The legacy `_app_*`/`app_*` flat modules at `src/sattlint/` root are the
  current impediment to this direction** and must be dissolved into the layered
  packages.

## The Classification Test

For every function currently in `app.py` (and its application/ ports), ask:

> "Could a Python API consumer invoke this without caring that SattLint has a
> CLI?"

- **Yes** → `application/` layer.
- Knows about `argparse`, Textual, terminal menus, stdout/stderr, keyboard
  input, CLI exit codes → **`cli/` / `ui/` layer**.
- Knows about SattLine files, parser, project graph, semantic index →
  **`project/` / `core/` / `resolution/` layer**.

## Separation: Application Services vs. Application Commands

- `application/analyze.py`, `application/project.py` → reusable application
  operations (orchestration).
- `cli/commands.py` → turns those operations into CLI behavior (argparse,
  exit codes, output formats, rendering).

```
CLI command:  sattlint check foo
    │
    ▼
application:  analyze_project(...)
    │
    ▼
domain/core:  semantic analysis
    │
    ▼
result
    │
    ▼
CLI:  render diagnostics
```

## Completed (Phases 1–5)

Phases 1–5 removed the mechanical facade layer. All gates green
(pyright strict 0 errors, ruff check + format clean, 1134 tests pass).

- **Phase 1** — engine alias surface decoupled.
- **Phase 2** — `application/` package created (`analyze.py`, `project.py`,
  `commands.py`, `startup.py`, `_interaction.py`, `__init__.py`).
- **Phase 3** — CLI wiring (`cli/command_handlers.py`) made `app_module`-free;
  `app.py::main`/`cli` delegate to `application/startup`.
- **Phase 4** — full app non-binding pass: Textual shell binds direct handler
  functions; interaction state owned by `application/_interaction.py`.
- **Phase 5** — deleted the 7 legacy facade/from-app modules and unified
  `MenuOption`; `app.py` is now a thin re-export entry point:
  - `_app_facade_analysis.py` → `application/analyze.py`
  - `_app_facade_project.py` → `application/project.py`
  - `_app_startup_from_app.py` → `application/startup.py`
  - `_app_facade_commands.py` → `application/commands.py`
  - `_app_analysis_from_app.py`, `_app_graphics_from_app.py`,
    `_app_menus_from_app.py`, `tests/_app_live_adapters_support.py` → deleted

## Not Yet Done (gap vs. target)

1. **Application layer is still command-shaped, not orchestration.**
   `application/analyze.py` is a pass-through over `app_analysis`:
   `run_variable_analysis(cfg)`, `run_checks(cfg, ...)`, `run_icf_validation(cfg)`.
   No `analyze_project(project, options) -> AnalysisResult`, no
   `AnalyzerRegistry`, no `SemanticSnapshot` orchestration. Functions still take
   `ConfigDict` and are bound to the app-level config/terminal concepts.

2. **Dependency direction is still inverted.** `application/` depends on the
   legacy flat modules:
   - `startup.py` → `_app_analysis_menus`, `_app_interactive_menus`,
     `_app_startup`, `app_analysis`, `app_graphics`, `app_menus`,
     `app_support`, `console`
   - `analyze.py` → `app_analysis`, `app_base`, `analysis_catalog`
   - `project.py` → `app_analysis`, `app_support`, `cache`, `console`
   - `commands.py` → `_app_startup`, `_app_analysis_checks`,
     `app_cli_commands`, `cli.entry`
   These `_app_*`/`app_*` modules are the real implementation; `application/`
   is a thin facade over them rather than a layer above reorganized
   `project/core/analyzers`.

3. **Services vs. commands not separated.** `application/commands.py` holds
   CLI concerns (`run_cli`, `run_validate_config_command`,
   `run_cache_prune_command`, exit codes, `cli.entry`). `application/startup.py`
   is the terminal-menu loop (`clear_screen`, `pause`, `confirm`, `prompt`,
   `print_menu`, `dump_menu`, `config_menu`, `tools_menu`,
   `graphics_rules_menu`, `build_menu_interaction`). Per the classification
   test, these belong in `cli/`, not `application/`.

4. **Directory layout not realized.** Domain implementation still lives in flat
   `app_analysis.py`, `app_base.py`, `app_menus.py`, `app_graphics.py`,
   `app_support.py`, `app_interaction.py`, `app_cli_commands.py` at the package
   root, not organized into the layered packages.

## Phase 6½ — Ownership Table (define before moving)

Before moving any legacy code, record the responsibility→destination mapping so
later phases make no arbitrary mid-flight decisions.

| Responsibility                     | Destination                                            |
| ---------------------------------- | ------------------------------------------------------ |
| Analyze project (orchestration)    | `application/analyze.py`                               |
| Load project (orchestration)       | `application/project.py`                               |
| Project loading implementation     | `project/`                                             |
| Dependency graph                  | `project/`                                             |
| Dependency resolution              | `resolution/` (below `project/`)                       |
| Semantic model                     | `core/`                                                |
| Analyzer implementation            | `analyzers/`                                           |
| Analyzer registry / catalog        | `analyzers/`                                           |
| Diagnostics                        | `core/`                                                |
| Text output / rendering            | `cli/` / `ui/`                                         |
| Interactive menus / terminal input | `cli/` / `ui/`                                         |
| Config parsing                     | `config/`                                              |
| Cache implementation               | the domain that owns persistence                        |

This table is normative: a function must be classified by what it is, not by
which `_app_*`/`app_*` module it currently lives in.

## Remaining Phases

### Phase 6 — Move CLI concerns out of `application/`

Move command implementations and the interactive menu loop into the CLI layer,
leaving `application/` with service-style operations only.

- `application/commands.py` → `cli/commands.py` (`run_cli`,
  `run_validate_config_command`, `run_analyze_command`,
  `run_cache_prune_command`, `run_format_icf_command`, `run_icf_formatter`,
  `show_config`, `configured_icf_files`). These exist only to serve CLI
  behavior, so the move is correct.
- `application/startup.py` terminal/menu code → `cli/startup.py`
  (menu_option factory, clear_screen/pause/confirm/prompt, print_menu,
  build_menu_interaction, dump_menu, config_menu, tools_menu,
  graphics_rules_menu, analysis menus, resolve_interactive_ui_mode, main/cli).
- **Keep `application/project.py` thin — orchestration only.** Do not let it
  accumulate project-loading details; project loading implementation belongs in
  `project/` (Phase 7).
- `application/` keeps only operations that pass the classification test.
- `app.py` re-exports re-pointed accordingly; tests retargeted.

### Phase 7 — Dissolve the flat `_app_*`/`app_*` implementation modules

Replace the flat root modules with properly layered packages so `application/`
depends only on `project/core/analyzers/resolution`.

**Classify function-by-function, never file-by-file.**

> Do not preserve module boundaries merely because they existed in `app_*`.
> Move each responsibility to the package that owns the concept.

`app_analysis.py` alone mixes several concepts (analyzer execution, analyzer
definitions, report formatting, configuration, application orchestration); each
must be separated to its owning package. The ownership table (Phase 6½) is the
authority, not the current module layout.

- `app_analysis.py` → `analyzers/` + `core/` by concept.
- `app_base.py` → `core/` (shared CLI-independent primitives).
- `app_support.py` → `project/` (targets, analyzed-target bookkeeping) + `core/`.
- `app_graphics.py`, `app_menus.py`, `app_interaction.py`,
  `app_cli_commands.py`, `app_rich.py`, `app_textual.py` → `ui/` / `cli/`.
- `_app_analysis_menus.py`, `_app_interactive_menus.py`, `_app_startup.py`,
  `_app_analysis_checks.py`, remaining `_app_*` → `ui/` / `cli/` / `core/` by
  content, not by origin.
- Update `application/*` imports; delete now-unused legacy modules.

### Phase 8 — Establish the application service contract (mandatory)

**Not optional.** The exact shape of the service API can evolve, but the
architectural objective — a well-defined `application/` responsibility — is the
final completion criterion. Without it, Phase 7 could finish with
`application/` still holding arbitrary orchestration wrappers.

Reshape application operations into typed orchestration decoupled from
`ConfigDict` and the terminal:

```
analyze_project(
    project: Project,
    options: AnalysisOptions,
) -> AnalysisResult
```

- `project` is a deliberate **domain object** (`Project`), not an ambiguous
  parameter that could be a `ProjectGraph`, a list of loaded source files, an
  AST collection, a `SemanticSnapshot`, or a path.
- The caller does **not** construct a `SemanticSnapshot`; the application layer
  builds it:

  ```
  Project
      ↓
  SemanticSnapshot
      ↓
  Analyzer execution
      ↓
  AnalysisResult
  ```

- **Introduce `AnalysisOptions`** instead of passing `config` directly.
  Otherwise `ConfigDict` becomes the dumping ground for everything
  (analyzer selection, output format, strictness, project paths, cache
  settings, UI settings, ICF settings) and application functions end up
  coupled to the global configuration structure. Deliberately separate:

  - **Application options** (`AnalysisOptions`)
  - **Project configuration**
  - **CLI configuration**
  - **UI configuration**

- `application/project.py` exposes a minimal project service (e.g.
  `load_project(...) -> Project`); the resolution mechanism stays hidden behind
  it in `project/` → `resolution/`.

## Mechanical Enforcement

The ownership rules must be enforced by a **test**, not just a grep command.
Lower layers must never import higher layers.

Dependency-guard test matrix (forbidden imports):

```
application → app_*
application → _app_*
core        → application
project     → application
resolution  → application
analyzers   → application
core        → cli
project     → cli
resolution  → project      # resolution sits below project
```

A simple AST/import-graph guard test in the suite makes violations fail CI.

## Definition of Done (Phase 6–8)

- The classification test passes for every function that remains in
  `application/`.
- The ownership table (Phase 6½) is fully realized; no legacy `_app_*`/`app_*`
  module survives as a mixed-concept module.
- The dependency-guard test passes (the matrix above is green).
- All gates green: `pyright src/sattlint` (strict) 0 errors,
  `ruff check` + `ruff format --check` clean, full `pytest` suite passes.
- `app.py` contains **only entry-point delegation**, e.g.:

  ```python
  # app.py
  from sattlint.cli.startup import main

  __all__ = ["main"]
  ```

  No blanket compatibility re-export layer, unless a specific re-export is
  intentionally part of SattLint's public Python API. Once compatibility is no
  longer needed, `app.py` may be eliminated entirely.