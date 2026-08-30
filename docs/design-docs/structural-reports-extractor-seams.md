# Structural Reports Extractor Seams

Status: Partially implemented
Owner: Devtools structural reports

## Problem

`src/sattlint/devtools/structural/structural_reports.py` reaches directly into multiple core packages to assemble report data. That coupling makes the module expensive to test, vulnerable to unrelated core-package churn, and hard to evolve without import-boundary regressions.

Current direct dependencies called out in review:

- analyzer registry surfaces (`analysis_catalog`)
- core semantic workspace loading (`core/semantic`)
- reporting variables rendering (`reporting/variables_report`)
- resolution helpers (`resolution/common`)
- semantic analysis helpers (`semantic_analysis`)

Current submodule structure after partial extraction:

- `_structural_report_architecture` — architecture report builder
- `_structural_report_budget` — structural budget report builder
- `_structural_report_graphics` — graphics report builder
- `_structural_report_graphs` — graph report builder
- `_structural_report_impact` — impact analysis report builder
- `_structural_budget_inventory` — budget line/markdown/python counting helpers

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

## Current State

Report-family submodules have been extracted into dedicated files under `src/sattlint/devtools/structural/`. The main orchestrator still imports directly from `core/semantic`, `resolution/common`, and `semantic_analysis` for workspace loading and variable artifact construction. The remaining work is to replace those direct imports with typed extractor contracts.

## Non-Goals

- Rewriting existing analyzers or semantic loaders.
- Changing artifact schemas as part of the seam extraction.
- Bundling unrelated structural-report cleanup into the same refactor.
