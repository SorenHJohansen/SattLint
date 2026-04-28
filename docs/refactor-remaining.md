# Refactor Roadmap (Open Items)

This roadmap tracks only refactor work that is still open.

References:

- Wave 1 static audit data: `docs/refactor-wave1-audit.md`
- Current work ledger: `.github/coordination/current-work.md`

## Remaining refactor backlog

1. Split remaining large hotspot modules.
	- `src/sattlint/validation.py`
	- `src/sattlint/analyzers/sfc.py`
	- `src/sattlint_lsp/server.py`
2. Finalize `sattlint.app` facade boundary.
	- Keep `sattlint.app` as stable public entry.
	- Remove or isolate remaining lazy `repo_audit_module` coupling.
	- Keep ownership in `app_*` owners and `cli/entry.py`.
3. Normalize long parameter bundles in high-churn APIs.
	- Replace long argument lists with context objects or dataclasses where stable.
	- Migrate incrementally at subsystem boundaries.
4. Complete strict expression and assignment semantics.
	- Reject remaining unsupported string arithmetic paths.
	- Enforce coercion policy (`INT -> REAL`) consistently.
	- Decide and enforce policy for assignment to `:OLD` under compatibility constraints.
5. Complete CONST and STATE semantics.
	- Finish CONST init and modifier enforcement.
	- Finish STATE read/write timing and persistence constraints.
6. Complete SFC execution semantics backlog.
	- Active-step cardinality contracts.
	- Transition correctness and ordering guarantees.
	- Reset/hold behavior.
	- Step auto-variable typing.
	- One-transition-per-cycle rule.
7. Tighten dependency and type-resolution strictness.
	- Missing-library diagnostics policy.
	- Circular dependency checks.
	- Version compatibility checks.
	- External datatype-resolution strictness policy.
8. Decide and enforce compatibility-wrapper strategy.
	- Keep wrappers only where public compatibility requires them.
	- Remove internal indirection where direct imports are safe.
	- Document retained wrappers and rationale.
9. Remove residual duplicate traversal and access helper patterns.
	- Consolidate duplicate traversal helpers.
	- Replace repeated `.code` probing and list-index branches with shared helpers where it reduces call-site branching.

## Open waves and exit conditions

| Wave | Focus | Exit condition |
|---|---|---|
| R1 | Ownership hardening and hotspot splits | Hotspot modules split into stable owner seams with behavior preserved |
| R2 | Strict-validation completion | Remaining semantic backlog implemented with focused regression coverage |
| R3 | Boundary and API cleanup | Compatibility boundaries are explicit and import/cycle pressure is reduced |

## Validation routing by wave

### R1

1. Focused module tests for each split surface.
2. Targeted pytest slices for moved owners.
3. No CLI or LSP behavior drift in compatibility checks.

### R2

1. `sattlint syntax-check` regressions first.
2. Focused parser and validation pytest modules.
3. Broader semantic and LSP suites only after focused checks pass.

### R3

1. Focused parser and analyzer import or behavior tests.
2. Static import and type checks for touched boundaries.

## Cross-wave guardrails

- Preserve strict `syntax-check` versus workspace/LSP behavior separation.
- Keep `sattlint.app` stable while internal ownership moves.
- Prefer narrow, reviewable slices over broad rewrites.

## Definition of done

- Each remaining item is completed or explicitly deferred with reason.
- Every completed slice has focused validation evidence.
- Public CLI and editor-facing behavior remains stable unless intentionally changed and documented.
