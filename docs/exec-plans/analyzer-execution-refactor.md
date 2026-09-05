# SattLint Analyzer Execution Refactor

> Status: Deferred — waiting on analyzer performance optimization branch
> Depends on: architecture-upgrade-plan.md Parts A and C complete
> Replaces: Phases 6, 9, 10, 17 of the architecture upgrade plan

## Goal

Redesign the analyzer execution model for speed and correctness: eliminate
reflection, simplify the registry-to-execution chain, enforce dependency
invariants, and verify analyzer isolation.

## Context

These phases were deferred from the architecture upgrade plan because an
in-progress analyzer performance optimization branch changes how analyzers run.
Merging the registry refactors in parallel would cause significant conflicts.
The optimization branch should land first; then these phases adapt the new
execution model to the clean architecture.

## Phases

### Phase R1 — Replace registry reflection with typed definitions

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

### Phase R2 — Simplify registry/catalog/dispatch

Review `registry`, `catalog`, `dispatch`, `specs`, `delivery` as a whole. Remove
layers that only forward calls or exist because of past refactors. Target:

```text
AnalyzerSpec → AnalyzerRegistry → Analyzer execution
```

Keep separate modules only for meaningful domain boundaries; optimize for
minimum conceptual indirection, not minimum file count.

Acceptance: the execution path is traceable without traversing facade modules.

### Phase R3 — Remove remaining compatibility architecture

Delete historical compatibility mechanisms (`_COMPATIBILITY_HELPERS`,
`_REGISTRY_MONKEYPATCH_SURFACE`, any remaining `_app_*_from_app`,
`_app_facade_*`). Do not move them elsewhere. Replace monkeypatch-only
production APIs with injection or typed test seams. Keep only documented public
compatibility.

Acceptance: no compatibility helper exists solely for old internal callers; no
monkeypatch-only production API; legacy aliases removed or justified; full suite
green.

### Phase R4 — Analyzer isolation and ordering tests

- **Isolation:** each analyzer run alone produces the same result as in the
  full suite, except for explicitly declared dependencies.
- **Order independence:** run analyzers in different valid orders and verify
  equivalent results. Undeclared ordering dependencies fail tests.

Acceptance: all analyzers pass isolation and order-independence tests on the
final execution model.

## Dependency order

R1 → R2 → R3 → R4 (sequential; each builds on the previous)

R1 should be adapted to the state of the analyzer optimization branch at merge
time — the new execution model may already eliminate some reflection.

## Definition of Done

- Analyzer execution uses typed callable definitions (no `getattr()` dispatch).
- The registry-to-execution path has no forwarding/facade indirection.
- Compatibility helpers and monkeypatch surfaces are removed.
- Each analyzer is isolated and order-independent.

## Gates

Same as the architecture upgrade plan: pyright strict 0 errors, ruff check +
format clean, full pytest green.
