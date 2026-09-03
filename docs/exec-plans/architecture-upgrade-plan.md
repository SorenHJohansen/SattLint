# SattLint Architecture Upgrade Plan

> Status: Active (no phases of the unified plan started)
> This plan is the single authority. It replaces and merges
> `application-layer-plan.md` and `architecture-reliability-refactor.md`.

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

### Part A — Layering

#### Phase 1 — Move CLI concerns fully out of `application/`

`application/` must contain service-style operations only.

- Confirm `cli/` owns all command implementations (`run_cli`,
  `run_validate_config_command`, `run_analyze_command`, `run_cache_prune_command`,
  `show_config`) and the interactive startup/menu code (`cli/startup.py`).
- Keep `application/project.py` thin — orchestration only; no loading details.
- `application/` keeps only operations that pass the classification test.
- `app.py` re-exports re-pointed; tests retargeted.

Acceptance: every function in `application/` passes the classification test.

#### Phase 2 — Dissolve the flat `_app_*`/`app_*` implementation modules

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

#### Phase 6 — Replace registry reflection with typed definitions

Replace string/reflection execution (`getattr` by attribute name) with typed
analyzer definitions containing the callable:

```python
AnalyzerSpec(key="powerup", run=analyze_powerup, requires=(...))
```

Goals: eliminate avoidable `Any`, eliminate runtime `getattr()` for execution,
reduce dynamic imports, make execution directly type-checkable, keep lookup
simple. Do not reintroduce plugin complexity.

Acceptance: analyzer execution has no string-based `getattr()`; callables are
statically typed; pyright clean; outputs unchanged.

#### Phase 7 — Validate analyzer dependency graphs at construction

Reject invalid graphs when the registry is constructed: duplicate keys, unknown
required analyzers, self-dependencies, cycles, colliding canonical keys.
Validate once, not via recursive runtime behavior.

Acceptance: tests exist for each invalid condition; a valid registry yields a
deterministic dependency order.

#### Phase 8 — Canonicalize analyzer keys

Invariant: all analyzer keys are canonical internally; canonicalization happens
at the boundary. Remove repeated `.casefold()`/normalization; drop duplicate key
representations; retain aliases only as documented user-facing compatibility.

Acceptance: internal maps hold canonical keys; dependency checks use them;
lookup stays backward-compatible where required.

#### Phase 9 — Simplify registry/catalog/dispatch

Review `registry`, `catalog`, `dispatch`, `specs`, `delivery` as a whole. Remove
layers that only forward calls or exist because of past refactors. Target:

```text
AnalyzerSpec → AnalyzerRegistry → Analyzer execution
```

Keep separate modules only for meaningful domain boundaries; optimize for
minimum conceptual indirection, not minimum file count.

Acceptance: the execution path is traceable without traversing facade modules.

#### Phase 10 — Remove remaining compatibility architecture

Once Parts A–B are working, delete historical compatibility mechanisms
(`_COMPATIBILITY_HELPERS`, `_REGISTRY_MONKEYPATCH_SURFACE`, any remaining
`_app_*_from_app`, `_app_facade_*`). Do not move them elsewhere. Replace
monkeypatch-only production APIs with injection or typed test seams. Keep only
documented public compatibility.

Acceptance: no compatibility helper exists solely for old internal callers; no
monkeypatch-only production API; legacy aliases removed or justified; full suite
green.

### Part C — Domain structure & boundaries

#### Phase 11 — Introduce a typed `SemanticIndex` result object

Replace the multi-value/8-element tuple returned by semantic-index construction
with a typed object (`symbol_table`, `type_graph`, `definitions`,
`definitions_by_key`, `moduletype_index`, `references_by_file`,
`references_by_definition_key`, `call_signatures`). Update callers to named
attributes; no `result[0]` indexing remains. Behavior-preserving.

#### Phase 12 — Reconsider `SemanticSnapshot` structure

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

`reporting/` (~1,440) is imported directly by 5+ analyzers. Make it a stable,
documented boundary: analyzers emit structured results; `reporting/` renders
them. Remove any analyzer→reporting renderer coupling that is accidental, and
keep reporting out of the compatibility/facade pattern. Add a dependency-guard
rule so analyzers depend on reporting's public surface only.

#### Phase 15 — Decide the validation subsystem scope

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

`config_validation.py` (473) plus types/io/defaults/display/self-check (~1,100)
have no owning phase. Consolidate config under `config/`, split
`config_validation.py` by concept if needed, and keep the
`ConfigDict`/`TOP_LEVEL_CONFIG_FIELDS` contract assertion as the single source
of truth.

### Part D — Reliability & tests

#### Phase 17 — Analyzer isolation and ordering tests

- **Isolation:** each analyzer run alone produces the same result as in the
  full suite, except for explicitly declared dependencies.
- **Order independence:** run analyzers in different valid orders and verify
  equivalent results. Undeclared ordering dependencies fail tests.

#### Phase 18 — Semantic invariants

Tests for: references resolve to a definition or an explicit unresolved state;
canonical identities unique; definitions/references deterministic; source
locations valid; type relationships internally consistent; repeated builds
equivalent. Independent of individual analyzers.

#### Phase 19 — Project graph invariants

Tests for: unique nodes; deterministic dependency edges; circular-dependency
detection; consistent missing dependencies; external/proprietary dependencies
distinguishable from missing files; intentional strict/non-strict behavior;
repeated loads produce equivalent graphs.

#### Phase 20 — Corpus regression exactness

Canonical corpus cases support exact expectations: total finding count, rule
counts, finding identity/location where stable, no unexpected findings. Keep
corpus metadata out of production runtime — an installed wheel must behave
correctly without `tests/`.

#### Phase 21 — Corpus differential reporting

Make corpus runs reviewable as before/after diffs: added findings, removed
findings, changed counts, changed rules, based on stable finding identity.

#### Phase 22 — Parser compatibility testing

Define the supported `sattline-parser` version policy explicitly; CI tests the
minimum and current/latest supported versions; use representative fixtures for
all features relying on parser behavior.

#### Phase 23 — Coverage non-regression

Keep coverage as a signal, not a vanity number. After the baseline is
established: prevent decrease, ensure core/project/analyzer execution paths are
covered, keep corpus tests mandatory. A modest non-regression threshold is
preferable to an arbitrary high number.

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

- Canonical corpus cases enforce exact expected behavior.
- Production code has no dependency on `tests/fixtures/corpus`.
- Project loader no longer imports/dynamically loads `engine`.
- Analyzer execution uses typed callable definitions.
- Semantic index uses a typed `SemanticIndex` object.
- Analyzer dependency graphs are validated; internal keys are canonical.
- Obsolete compatibility/monkeypatch/facade mechanisms are removed.
- `engine.py` is orchestration, not a service locator.
- `application/` is a thin typed service layer (`analyze_project`).
- Reporting and validation have defined boundaries (Phases 14–15).
- Analyzers are independent except for explicit dependencies.
- Semantic and project invariants are tested.
- Corpus differential reporting is available.
- Supported parser versions are explicitly tested.
- Coverage cannot silently regress.
- Architecture dependency rules are enforced by tests.
- Gates: `pyright src/sattlint` 0 errors, `ruff check` clean, `ruff format --check` clean, full pytest green.
- Installed-package behavior works without repository test files.
- No functionality or diagnostic behavior changes unintentionally.

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