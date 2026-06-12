# Structural Reports Extractor Seams

Status: Proposed
Owner: Devtools structural reports

## Problem

`src/sattlint/devtools/structural/structural_reports.py` reaches directly into multiple core packages to assemble report data. That coupling makes the module expensive to test, vulnerable to unrelated core-package churn, and hard to evolve without import-boundary regressions.

Current direct dependencies called out in review:

- analyzer registry surfaces
- core semantic workspace loading
- reporting variables rendering
- resolution helpers
- semantic analysis helpers

## Goal

Move `structural_reports.py` onto report-specific extractor interfaces so the orchestration layer depends on stable data contracts instead of core implementation details.

## Design Task

1. Introduce a shared extractor module under `src/sattlint/devtools/structural/` with typed contracts for each report family that currently reaches into core packages.
2. Add adapter modules next to the owning core surfaces to implement those extractor contracts without moving business logic into devtools.
3. Update `structural_reports.py` to depend only on the extractor contracts and adapter entrypoints.
4. Add focused tests that can replace the adapters with fakes, proving `structural_reports.py` no longer needs the full analyzer and resolution machinery for unit coverage.

## Acceptance Criteria

- `structural_reports.py` no longer imports core implementation modules directly beyond the approved extractor seam.
- Structural report orchestration tests can run with fake extractor implementations.
- The extractor contracts are typed and documented well enough to make new report adapters predictable.
- Existing JSON artifact shapes remain unchanged unless a separate artifact-contract change is approved.

## Non-Goals

- Rewriting existing analyzers or semantic loaders.
- Changing artifact schemas as part of the seam extraction.
- Bundling unrelated structural-report cleanup into the same refactor.
