# SattLint Architecture & Reliability Refactor Plan

> Status: Active (plan defined; no phases started)

## Goal

Simplify SattLint's internal architecture, remove compatibility/reflection glue,
strengthen the test system, and establish clear dependency boundaries.

The desired architecture is:

```text
                         CLI / TUI / LSP
                                │
                                ▼
                        Application layer
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
         Project loading                    Analysis
                │                               │
                ▼                               ▼
        ProjectGraph                     AnalyzerRegistry
                │                               │
                ▼                               ▼
          BasePicture                    SemanticSnapshot
                │                               │
                └───────────────┬───────────────┘
                                ▼
                         sattline-parser
```

More concretely:

```text
sattline-parser
       │
       ▼
ProjectLoader
       │
       ▼
ProjectGraph
       │
       ▼
SemanticIndex
       │
       ▼
SemanticSnapshot
       │
       ├── Analyzer A
       ├── Analyzer B
       ├── Analyzer C
       └── ...
       │
       ▼
DiagnosticReport
       │
       ├── CLI
       ├── TUI
       └── LSP
```

Core architectural rule:

> Analyzers depend on SattLint's semantic model, not on project-loading
> mechanics, CLI/UI code, parser construction, or registry implementation
> details.

Do not preserve old internal APIs merely to avoid changing callers. Prefer
changing callers and deleting obsolete compatibility layers.

---

# Phase 1 — Strengthen corpus regression guarantees

## 1. Make canonical corpus expectations exact

The existing real-world corpus is an important regression suite. Keep it and
strengthen it rather than creating a second test system.

For selected canonical regression cases, support exact expectations:

* exact total finding count
* exact rule counts
* ideally exact finding identity/location where stable
* no unexpected additional findings

Subset/fragment matching can remain available where deliberately useful, but
canonical regression cases should be strict.

Add tests proving that unexpected findings fail the corpus test.

## 2. Keep corpus metadata out of production runtime

Production SattLint code must not depend on:

```text
tests/fixtures/corpus
```

or import test-only modules to construct runtime analyzer metadata.

Corpus discovery/reporting belongs in test/dev tooling.

Verify that an installed wheel behaves correctly without the repository's
`tests/` directory.

## Acceptance criteria

* Canonical corpus cases fail when unexpected findings are introduced.
* Clean cases still require zero findings.
* Production package imports/runs without `tests/`.
* Corpus-specific helpers are clearly test/dev code.

---

# Phase 2 — Fix loader dependency direction

Remove the architectural dependency:

```text
ProjectLoader → engine
```

The loader must not dynamically import `sattlint.engine` to obtain parser
factories, helpers, or other implementation details.

Instead:

* move shared functionality to the package that owns it, or
* inject dependencies into the loader
* make `engine` construct/wire those dependencies

Desired direction:

```text
engine/application
        │
        ▼
   ProjectLoader
        │
        ▼
 lower-level services
```

Never:

```text
ProjectLoader → engine → ProjectLoader
```

Prefer explicit typed dependencies over `importlib` lookups.

## Acceptance criteria

* No project-loader module imports `sattlint.engine`.
* No dynamic import of `engine` is required for normal operation.
* Existing loader tests continue to pass.
* Loader can be unit-tested with injected parser/transformer/services.

---

# Phase 3 — Replace registry reflection with typed definitions

Replace string/reflection-based execution such as:

```text
attribute name
    ↓
getattr(...)
    ↓
callable
```

with typed analyzer definitions containing the callable itself.

For example:

```python
AnalyzerSpec(
    key="powerup",
    run=analyze_powerup,
    requires=(...),
)
```

The exact types should follow the existing architecture and avoid unnecessary
abstraction.

Goals:

* eliminate avoidable `Any`
* eliminate runtime `getattr()` for analyzer execution
* reduce dynamic imports
* make analyzer execution directly type-checkable
* keep registry lookup simple

Do not reintroduce plugin complexity unless it is genuinely required.

## Acceptance criteria

* Analyzer execution no longer depends on string-based `getattr()` lookup.
* Analyzer callables are statically typed.
* Pyright remains clean in strict mode.
* Existing analyzer outputs remain unchanged.

---

# Phase 4 — Introduce a real SemanticIndex result object

Replace the current multi-value/8-element tuple returned by semantic-index
construction with a typed result object.

Create a `SemanticIndex` dataclass/class containing the existing fields, for
example:

```python
SemanticIndex(
    symbol_table=...,
    type_graph=...,
    definitions=...,
    definitions_by_key=...,
    moduletype_index=...,
    references_by_file=...,
    references_by_definition_key=...,
    call_signatures=...,
)
```

Update callers to use named attributes rather than numeric tuple positions.

Preserve behavior; this is an API/maintainability improvement, not a semantic
change.

## Acceptance criteria

* No indexing like `result[0]`, `result[1]`, etc. remains for semantic-index
  results.
* Semantic index data has one typed representation.
* Existing semantic tests pass unchanged in behavior.

---

# Phase 5 — Make analyzer dependency validation explicit

When the analyzer registry is constructed/validated, reject invalid dependency
graphs:

* duplicate analyzer keys
* unknown required analyzers
* self-dependencies
* dependency cycles
* invalid/colliding canonical keys

Validate once when the registry/catalog is created rather than relying on
recursive runtime behavior to discover problems.

## Acceptance criteria

Tests exist for each invalid graph condition.

A valid registry produces a deterministic dependency order.

---

# Phase 6 — Canonicalize analyzer keys

Establish one invariant:

> All analyzer keys are canonical internally.

Canonicalization should happen at the boundary.

After that:

* internal structures use canonical keys only
* remove repeated `.casefold()`/normalization logic
* remove duplicate key representations where possible
* retain aliases only when they are intentionally part of a documented
  user-facing compatibility API

Avoid passing arbitrary user-form keys deep into the analysis system.

## Acceptance criteria

* Internal analyzer maps contain canonical keys only.
* Dependency checks use canonical keys.
* Analyzer lookup behavior remains backward-compatible where required.
* No unnecessary repeated canonicalization remains.

---

# Phase 7 — Remove remaining compatibility architecture

Once the previous phases are working, remove historical compatibility
mechanisms.

Delete or simplify:

```text
_COMPATIBILITY_HELPERS
_REGISTRY_MONKEYPATCH_SURFACE
_app_*_from_app
_app_facade_*
```

Do not merely move these mechanisms elsewhere.

For tests that currently monkeypatch internal modules, replace that behavior
with explicit dependency injection or typed test seams.

For compatibility aliases, determine whether they are actually public API. Keep
only documented user-facing compatibility requirements.

## Acceptance criteria

* No compatibility helper exists solely for old internal tests/callers.
* No monkeypatch-only production API exists.
* Legacy internal aliases are removed or justified as public compatibility.
* Full test suite remains green.

---

# Phase 8 — Simplify registry/catalog/dispatch

Review the current:

```text
registry
catalog
dispatch
specs
delivery
```

layers as a whole.

Remove layers that only forward calls or exist because of previous refactoring.

Aim for a small conceptual model:

```text
AnalyzerSpec
    ↓
AnalyzerRegistry
    ↓
Analyzer execution
```

Keep separate modules only when they represent meaningful domain boundaries.

Do not optimize for minimum file count; optimize for minimum conceptual
indirection.

## Acceptance criteria

The analyzer execution path can be followed without traversing multiple
compatibility/facade modules.

---

# Phase 9 — Simplify engine architecture

Reduce `engine.py` to high-level orchestration/composition rather than a
service locator or compatibility export hub.

Move implementation to the package that owns the responsibility:

* parsing → parser-related module
* project loading → project
* dependency resolution → resolution/project
* validation → appropriate domain/core module
* graphics handling → graphics/domain module
* cache implementation → appropriate persistence/service module

`engine.py` should primarily compose these pieces.

Avoid replacing the current `_engine_*` decomposition with an even larger number
of helper modules. Merge modules when they don't represent real boundaries.

## Acceptance criteria

* `engine.py` has a clear, narrow responsibility.
* Lower-level modules do not import `engine.py`.
* Public engine APIs remain intentional and typed.

---

# Phase 10 — Reconsider SemanticSnapshot structure

Review:

```text
_semantic_snapshot.py
_semantic_snapshot_types.py
semantic.py
_semantic_helpers.py
_semantic_index.py
_semantic_index_reference_support.py
```

Determine which splits represent real concepts and which exist only to avoid
previous import cycles.

Where appropriate, merge implementation/type/helper modules into clearer
semantic-domain modules.

Do not change behavior as part of this phase.

## Acceptance criteria

Semantic code has clear ownership and fewer historical/refactoring-driven
boundaries.

---

# Phase 11 — Analyzer isolation and ordering tests

Add tests proving that analyzer execution is deterministic and correctly
isolated.

For every analyzer where applicable:

### Isolation

Run the analyzer alone and verify that it produces the same result as when run
in the full suite, except for explicitly declared dependencies.

### Order independence

Run analyzers in different valid orders:

```text
A B C
B C A
C A B
```

and verify equivalent results.

Explicit analyzer dependencies may determine required ordering, but undeclared
ordering dependencies must fail tests.

## Acceptance criteria

* No analyzer relies accidentally on another analyzer having run first.
* Results are deterministic.
* Shared artifacts are correctly declared.

---

# Phase 12 — Semantic invariants

Add tests for core semantic-model invariants, including where applicable:

* every reference resolves to a valid definition or an explicitly represented
  unresolved state
* canonical identities are unique
* definitions are deterministic
* references are deterministic
* source locations are valid
* type relationships are internally consistent
* repeated semantic builds produce equivalent results

These tests should test the semantic layer independently of individual
analyzers.

---

# Phase 13 — Project graph invariants

Add tests for project/dependency loading:

* nodes are unique
* dependency edges are deterministic
* circular dependencies are detected
* missing dependencies are represented consistently
* unavailable external/proprietary dependencies are distinguishable from
  missing expected files
* strict/non-strict behavior is intentional and tested
* repeated project loading produces equivalent graphs

---

# Phase 14 — Corpus differential reporting

Improve the existing corpus tooling so changes can be reviewed as a
before/after diff.

For a corpus run, make it possible to see:

```text
Added findings
Removed findings
Changed counts
Changed rules
```

This is particularly useful when intentionally changing analyzer behavior.

The differential output should be based on stable finding identity wherever
possible.

---

# Phase 15 — Parser compatibility testing

SattLint depends heavily on `sattline-parser`.

Define the supported parser-version policy explicitly.

Then ensure CI tests the intended compatibility range, for example:

```text
minimum supported parser
current/latest supported parser
```

Use representative parser fixtures for all SattLint features that rely on
parser behavior.

Do not rely solely on the parser project's own tests.

---

# Phase 16 — Coverage non-regression

Keep coverage as a quality signal, but focus on important code paths rather
than blindly maximizing the global percentage.

Once the current baseline is established:

* prevent coverage from decreasing
* ensure core/project/analyzer execution paths are covered
* ensure corpus tests remain mandatory

A modest non-regression threshold is preferable to an arbitrary high number
that encourages meaningless tests.

---

# Final architecture rules

Enforce these rules mechanically where practical:

```text
CLI/UI/LSP
    ↓
application
    ↓
project / core / analyzers
    ↓
resolution / parser / persistence
```

Rules:

1. Lower layers must not import `application`.
2. Domain/core code must not import CLI/UI.
3. Analyzers must not depend on CLI/UI.
4. Analyzers should depend on semantic abstractions rather than project-loading
   details.
5. Project loaders must not depend on `engine`.
6. Production code must not depend on `tests/`.
7. Analyzer execution must not depend on reflection when a typed callable can
   be used.
8. Internal analyzer keys are canonical.
9. Compatibility code is retained only for intentional public compatibility.

Add architecture tests so these rules cannot silently regress.

---

# Definition of Done

The refactor is complete when:

* canonical corpus cases enforce exact expected behavior
* production code has no dependency on `tests/fixtures/corpus`
* project loader no longer imports/dynamically loads `engine`
* analyzer execution uses typed callable definitions
* semantic index uses a typed `SemanticIndex` object
* analyzer dependency graphs are validated
* internal analyzer keys are canonical
* obsolete compatibility/monkeypatch/facade mechanisms are removed
* `engine.py` is orchestration rather than a service locator
* analyzers are independent except for explicit dependencies
* semantic and project invariants are tested
* corpus differential reporting is available
* supported parser versions are explicitly tested
* coverage cannot silently regress
* architecture dependency rules are enforced by tests
* `pyright src/sattlint` passes with zero errors
* `ruff check` passes
* `ruff format --check` passes
* the full pytest suite passes
* installed-package behavior works without repository test files
* no functionality or diagnostic behavior changes unintentionally

---

# Implementation principles

* Make one phase at a time and keep the repository green between phases.
* Prefer deleting indirection over relocating it.
* Move responsibilities by domain, not by historical filename.
* Do not add abstractions unless they remove real coupling.
* Preserve behavior unless the phase explicitly changes test/architecture
  behavior.
* When removing compatibility code, update callers/tests rather than adding
  another wrapper.
* After each phase, inspect imports and dependency direction rather than
  relying only on passing tests.