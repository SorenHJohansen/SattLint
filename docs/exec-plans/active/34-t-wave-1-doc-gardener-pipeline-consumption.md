# T-Wave-1 Doc-Gardener Pipeline Consumption

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan closes T-006. After this work lands, `sattlint.devtools.doc_gardener` will be able to consume the machine-readable pipeline outputs that SattLint already writes under `artifacts/analysis/` and use them to update `docs/quality-score.md` and related tracking files with real pipeline facts instead of scan-only append behavior. The observable proof is that running the pipeline and then doc-gardener updates the quality score using `summary.json` and `status.json`, while existing scan-only behavior still works when artifacts are missing.

## Progress

- [x] (2026-05-13) Create the ExecPlan and confirm `src/sattlint/devtools/pipeline.py` already writes `status.json`, `summary.json`, and registry-backed artifacts, while `src/sattlint/devtools/doc_gardener.py` still ignores those outputs and `docs/quality-score.md` has no `## Trend` section, so the current `update_quality_score` path mostly no-ops.
- [ ] Add a small pipeline-artifact reader to `src/sattlint/devtools/doc_gardener.py` and expose an optional output-dir override.
- [ ] Update `docs/quality-score.md` from real pipeline summaries while preserving current scan-log updates.
- [ ] Add focused tests and run narrow pytest plus touched-file quality gates.

## Surprises & Discoveries

Observation: the shared pipeline already emits the exact machine-readable data this debt item needs.
Evidence: `src/sattlint/devtools/pipeline.py` writes `status.json`, `summary.json`, and a registry-backed artifact manifest through `write_json_artifact` and `write_pipeline_artifacts`.

Observation: the current quality-score updater is structurally incomplete.
Evidence: `src/sattlint/devtools/doc_gardener.py` only edits `docs/quality-score.md` when it finds a `## Trend` section, but the current file contains `## Domain Scores`, `## Layer Scores`, and `## Grading Scale` only.

Observation: the repository already has stable doc-gardener path-patching tests.
Evidence: `tests/_repo_audit_test_support.py` and `tests/test_repo_audit_doc_gardener.py` already patch doc-gardener paths for temp-repo tests.

## Decision Log

Decision: extend `src/sattlint/devtools/doc_gardener.py` instead of adding a second documentation-update tool.
Rationale: the repository already treats doc-gardener as the owning surface for `quality-score.md` and `tech-debt-tracker.md`, so adding parallel update logic would create drift immediately.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: read existing pipeline artifacts rather than inventing a new artifact format for documentation updates.
Rationale: the pipeline already emits stable JSON contracts, and repo-audit instructions explicitly prefer extending existing devtools seams.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: make the pipeline output directory configurable, with `artifacts/analysis` as the default.
Rationale: CI and developers already use different output directories at times, and doc-gardener should be able to consume either without rewriting files by hand.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Planning baseline only. The current repository already has the pipeline data this debt item needs, but doc-gardener still behaves like an isolated markdown scanner rather than a consumer of the broader devtools artifact set.

## Context and Orientation

The controlling documentation updater is `src/sattlint/devtools/doc_gardener.py`. `run_scan` gathers markdown findings. `update_quality_score` and `update_tech_debt_scan_log` mutate the two tracked docs when doc-gardener runs outside `--check-only` mode. The CLI entry point is `main(argv)` in the same file.

The controlling artifact producers are in `src/sattlint/devtools/pipeline.py` and `src/sattlint/devtools/pipeline_artifacts.py`. The pipeline writes `status.json`, `summary.json`, and registry-backed artifacts under its output directory, which defaults to `artifacts/analysis`. This debt item is about consuming those existing outputs, not about adding a new artifact family.

The nearest tests are `tests/test_repo_audit_doc_gardener.py`, `tests/_repo_audit_part5.py`, and `tests/test_artifact_contracts.py`. Those files already cover doc-gardener path patching and artifact-shape expectations, so they are the right place to extend before adding broader pipeline coverage.

## Plan of Work

Start by adding a small loader in `src/sattlint/devtools/doc_gardener.py` that reads `summary.json`, `status.json`, and any other already-registered pipeline artifact needed for score updates. The loader should return a small internal snapshot object or dictionary, and it must treat missing files as a non-fatal condition so doc-gardener still works in scan-only mode.

Next, update `update_quality_score` so it can create a `## Trend` section when one is missing and append a new dated row using pipeline facts instead of only the raw markdown-finding count. Keep the existing `## Domain Scores` and `## Layer Scores` layout unless the file truly needs a minimal additive section. The first slice should prefer stable, high-signal values such as overall pipeline status, findings count, and coverage summary that already exist in the pipeline output.

Then extend `main(argv)` with an optional `--pipeline-output-dir` argument that defaults to `artifacts/analysis`. When doc-gardener runs without `--check-only`, it should load the pipeline snapshot first, update the quality score from that snapshot, and then update the tech-debt scan log as it does today.

## Concrete Steps

Run all commands from the repository root.

Inspect the current updater and artifact seams before editing code:

    rg -n "update_quality_score|update_tech_debt_scan_log|run_scan|main" src/sattlint/devtools/doc_gardener.py
    rg -n "status.json|summary.json|write_pipeline_artifacts|artifact_registry" src/sattlint/devtools/pipeline.py src/sattlint/devtools/pipeline_artifacts.py

After implementing the pipeline snapshot reader and the quality-score updater, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_repo_audit_doc_gardener.py tests/test_artifact_contracts.py -x -q --tb=short

Exercise the user-facing command once the tests pass:

    python scripts/run_repo_python.py -m sattlint.devtools.pipeline --profile quick --output-dir artifacts/analysis
    python scripts/run_repo_python.py -m sattlint.devtools.doc_gardener --pipeline-output-dir artifacts/analysis

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/devtools/doc_gardener.py tests/test_repo_audit_doc_gardener.py
    python scripts/run_repo_python.py -m pyright src/sattlint/devtools/doc_gardener.py

## Validation and Acceptance

Acceptance requires more than a new helper. After the change, doc-gardener must read real pipeline outputs from a chosen output directory, update `docs/quality-score.md` deterministically even when `## Trend` is initially missing, and keep working in scan-only mode when no pipeline artifacts are present. Existing doc-gardener scan-log updates and repo-audit integrations must continue to pass.

## Idempotence and Recovery

This plan is safe to run repeatedly. Reading pipeline JSON is side-effect free, and updating the same quality-score sections should be written to be idempotent. If the pipeline snapshot is missing or malformed, doc-gardener should skip the pipeline-derived quality update, print a clear message, and continue with the existing markdown-finding workflow instead of failing halfway through.

## Artifacts and Notes

Record one short before-and-after excerpt from `docs/quality-score.md`, plus the exact `summary.json` fields that drove the update. The important proof is that doc-gardener consumed real pipeline data, not that it reformatted the entire document.

## Interfaces and Dependencies

The implementation surface is `src/sattlint/devtools/doc_gardener.py`, with read-only reuse of `src/sattlint/devtools/pipeline.py` and `src/sattlint/devtools/pipeline_artifacts.py`. Do not introduce a new artifact format. Continue to consume the repository’s existing machine-readable JSON outputs.
