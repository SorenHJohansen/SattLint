# D-Wave-2 Devtools Follow-Ons

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan replaces the remaining Program D roadmap placeholders for D-039, D-040, and D-042 with one active execution surface. D-038 is already shipped, and D-041 is already closed in its own completed plan, so this file focuses only on the missing D-Wave-2 devtools: performance profiling, automated refactoring, and a metrics dashboard. After this work lands, users will be able to inspect performance hot spots, preview safe refactorings, and generate code-quality metrics without relying on broad pipeline runs or ad hoc scripts.

## Progress

- [x] (2026-05-13 09:12Z) Create the ExecPlan and confirm that `src/sattlint/devtools/profiler.py`, `src/sattlint/devtools/refactoring.py`, and `src/sattlint/devtools/metrics_dashboard.py` do not exist, while D-038 is already implemented and D-041 is already closed in `docs/exec-plans/completed/22-d-041-impact-analysis-tool.md`.
- [x] (2026-05-13T11:10Z) Define the user-facing module and command contracts for profiling, refactoring, and metrics reporting as direct `python -m sattlint.devtools.*` entry points with stable JSON output, optional text summaries, and explicit `--workspace-root` routing.
- [x] (2026-05-13T11:10Z) Implement `src/sattlint/devtools/profiler.py` for D-039 with deterministic phase and analyzer timing payloads plus bottleneck summaries.
- [x] (2026-05-13T11:10Z) Implement `src/sattlint/devtools/refactoring.py` for D-040 with a preview-first workflow, a scoped `normalize-layout` transformation, and semantic safety checks before any write.
- [x] (2026-05-13T11:10Z) Implement `src/sattlint/devtools/metrics_dashboard.py` for D-042 with stable JSON aggregation, text summaries, and reuse of cyclomatic-complexity and version-drift analyzer results.
- [x] (2026-05-13T11:10Z) Add focused tests for the new devtools and pass narrow pytest, Ruff, Pyright, and direct-command smoke validation for the shipped slices.

## Surprises & Discoveries

- Observation: Program D already has adjacent read-only reporting seams that should be reused instead of replaced.
  Evidence: `src/sattlint/devtools/impact_analyzer.py`, `src/sattlint/devtools/structural_reports.py`, `src/sattlint/devtools/accuracy_metrics.py`, and `src/sattlint/devtools/coverage_reports.py` already provide direct command and report-building patterns.
- Observation: the metrics feature can reuse analyzer results that are already present in the tree.
  Evidence: `src/sattlint/analyzers/cyclomatic_complexity.py` and `src/sattlint/analyzers/modules.py` already compute complexity and module-structure facts that should feed D-042 rather than being recomputed.
- Observation: refactoring is the only mutating feature in this wave, so it needs a stricter safety contract than profiling or metrics.
  Evidence: the other two features only read workspace state, while D-040 proposes code transformations and therefore must support a dry-run or preview path before any write is allowed.
- Observation: the private AST normalizer in `src/sattlint/analyzers/modules.py` is too strict to serve as the first safety gate for whitespace-only rewrites.
  Evidence: the initial `normalize-layout` implementation preserved parseability and semantic snapshot signatures, but `_normalize_ast_value` still reported non-semantic differences. The shipped safety model instead compares `collect_ast_summary(...)` plus the semantic snapshot signature.
- Observation: the profiler already exposes a useful hotspot ordering on real repo inputs without adding new analyzer wiring.
  Evidence: the smoke run written to `artifacts/tmp/plan32-profiler/profiler_report.json` showed `sattline-semantics` as the slowest analyzer on the sampled entry, followed by `scan_concurrency`, `taint-paths`, and `safety-paths`.

## Decision Log

- Decision: group D-039, D-040, and D-042 in one active plan while leaving D-041 in its existing dedicated file.
  Rationale: these three items share devtools conventions, direct-module command patterns, and validation surfaces, but D-041 already has a separately owned implementation slice.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: implement the read-only tools before the mutating refactoring tool.
  Rationale: profiling and metrics can establish the reporting contract and reusable output helpers first, while refactoring should come last because it carries the highest correctness risk.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: require a preview-first contract for D-040.
  Rationale: this repository avoids destructive defaults. A refactoring tool that writes immediately would violate that expectation and would be harder to validate safely.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)
- Decision: scope the first writable refactoring to `normalize-layout` and prove safety with structural-summary plus semantic-signature equality before any apply step.
  Rationale: layout normalization is deterministic, easy to preview as a unified diff, and can be guarded by parser plus semantic checks without claiming a broader source-to-source rewrite model than the repo currently has.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Implemented. Program D now has direct-command surfaces for profiling, metrics reporting, and preview-first refactoring in `src/sattlint/devtools/profiler.py`, `src/sattlint/devtools/metrics_dashboard.py`, and `src/sattlint/devtools/refactoring.py`, each backed by focused tests under `tests/devtools/`. The profiler emits deterministic phase and analyzer timing payloads plus bottleneck rankings. The metrics dashboard reuses existing analyzer facts instead of recomputing them. The refactoring tool stays opt-in for writes and requires semantic safety checks before applying even the first layout-normalization transform.

Validation passed with `python scripts/run_repo_python.py -m pytest --no-cov tests/devtools/test_profiler.py tests/devtools/test_metrics_dashboard.py tests/devtools/test_refactoring.py -x -q --tb=short`, touched-file Ruff, touched-file Pyright, and smoke invocations that wrote artifacts to `artifacts/tmp/plan32-profiler/`, `artifacts/tmp/plan32-metrics/`, and `artifacts/tmp/plan32-refactor/`.

## Context and Orientation

The nearest current devtools patterns are `src/sattlint/devtools/impact_analyzer.py` and `src/sattlint/devtools/structural_reports.py`. Those files already show how a direct command module can load workspace data, build a report, and emit stable JSON without routing through the full pipeline. They are the correct pattern to copy for D-039 and D-042.

For metrics, the best reusable sources are already in the analyzer layer. `src/sattlint/analyzers/cyclomatic_complexity.py` and `src/sattlint/analyzers/modules.py` compute facts that should feed a dashboard rather than be duplicated. For profiling, the nearest data-loading seam is `src/sattlint/core/semantic.py`, and the nearest parser-loading seam remains the standard parser entrypoint. For refactoring, the existing resolver and analyzer seams should be reused so any transformation can explain why it is safe.

There is no current owner surface for these three features. No `profiler.py`, `refactoring.py`, or `metrics_dashboard.py` file exists under `src/sattlint/devtools/`, and there are no focused tests for them. This plan exists to create those surfaces explicitly.

## Plan of Work

Implement D-039 first in `src/sattlint/devtools/profiler.py`. The first slice should measure parsing, loading, and analysis steps using committed workspace fixtures or small local inputs, then report bottlenecks in a stable, scriptable format. Keep the initial profiler deterministic and repository-local. Do not add ambient background sampling or system-dependent measurements in the first milestone.

Implement D-042 second in `src/sattlint/devtools/metrics_dashboard.py`. Reuse complexity and module-analysis facts from the existing analyzers and package them into a stable summary that can be rendered as JSON and a compact table. The dashboard should stay read-only and should be able to run on one workspace snapshot at a time.

Implement D-040 last in `src/sattlint/devtools/refactoring.py`. Start with a small set of explicitly safe transformations, each with a dry-run or preview mode that shows the intended change before anything is written. Any file-writing mode must remain opt-in and must produce deterministic output that tests can compare directly.

## Concrete Steps

Run all commands from the repository root.

Inspect the current direct-command and reporting seams before editing code:

    rg -n "def main|generated_by|output_dir|workspace-root" src/sattlint/devtools/impact_analyzer.py src/sattlint/devtools/structural_reports.py src/sattlint/devtools/coverage_reports.py src/sattlint/devtools/accuracy_metrics.py
    rg -n "cyclomatic|module" src/sattlint/analyzers/cyclomatic_complexity.py src/sattlint/analyzers/modules.py

After implementing the devtools and their focused tests, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/devtools/test_profiler.py tests/devtools/test_refactoring.py tests/devtools/test_metrics_dashboard.py -x -q --tb=short

Exercise the direct command surfaces once the tests pass:

    python scripts/run_repo_python.py -m sattlint.devtools.profiler --workspace-root .
    python scripts/run_repo_python.py -m sattlint.devtools.metrics_dashboard --workspace-root . --format json
    python scripts/run_repo_python.py -m sattlint.devtools.refactoring --workspace-root . --dry-run

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/devtools/profiler.py src/sattlint/devtools/refactoring.py src/sattlint/devtools/metrics_dashboard.py tests/devtools/test_profiler.py tests/devtools/test_refactoring.py tests/devtools/test_metrics_dashboard.py
    python scripts/run_repo_python.py -m pyright src/sattlint/devtools/profiler.py src/sattlint/devtools/refactoring.py src/sattlint/devtools/metrics_dashboard.py

## Validation and Acceptance

Acceptance requires a first-class tool for each roadmap feature. The profiler must produce deterministic timing or bottleneck summaries on committed inputs. The metrics dashboard must produce stable machine-readable output and a human-readable summary. The refactoring tool must support a preview or dry-run path and must prove at least one safe transformation with focused tests that fail before implementation and pass after it. No feature in this plan is complete if it exists only as an internal helper.

## Idempotence and Recovery

This plan is safe to execute incrementally. Land the read-only tools first, validate them independently, and only then add the mutating refactoring surface. If the refactoring tool cannot satisfy a preview-first contract, stop and keep it read-only until the transformation safety model is explicit. If profiling output depends on local machine noise, narrow the measurement scope until the tests become deterministic.

## Artifacts and Notes

Record one passing pytest summary per tool, one direct-command invocation that demonstrates the user-facing contract, and one sample output artifact. For refactoring, keep both a dry-run example and a before-and-after diff excerpt so the safety contract stays explicit.

## Interfaces and Dependencies

The implementation surface for this plan is centered on `src/sattlint/devtools/impact_analyzer.py`, `src/sattlint/devtools/structural_reports.py`, `src/sattlint/devtools/accuracy_metrics.py`, `src/sattlint/devtools/coverage_reports.py`, `src/sattlint/analyzers/cyclomatic_complexity.py`, and `src/sattlint/analyzers/modules.py`. New public devtool entry points must live in `src/sattlint/devtools/profiler.py`, `src/sattlint/devtools/refactoring.py`, and `src/sattlint/devtools/metrics_dashboard.py`. Focused regression proof belongs in new test files under `tests/devtools/`.
