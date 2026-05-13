# D-041 Impact Analysis Tool

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan promotes impact analysis from a structural-pipeline artifact into a first-class user tool. After this change, a user will be able to point SattLint at a workspace and a set of changed libraries, modules, or entry files and receive an explicit impact report that answers "what depends on this change directly, what depends on it transitively, and which entry files are affected?". The observable outcome is a dedicated command with stable JSON output and focused tests, built on top of the structural report logic that already exists in the repository.

## Progress

- [x] (2026-05-04) Create the ExecPlan and confirm that reverse-dependency aggregation already exists in the structural report layer.
- [x] (2026-05-05) Create a dedicated impact-analysis devtool command module that wraps the existing collectors.
- [x] (2026-05-05) Define the input contract for selecting changed nodes, entry files, or libraries and filtering the full workspace report down to actionable results.
- [x] (2026-05-05) Add focused command-level tests for the standalone command module.
- [x] (2026-05-13 09:26Z) Validate the new tool with narrow pytest, Ruff, and Pyright checks, capture a real JSON artifact, and archive this plan under `docs/exec-plans/completed/`.

## Surprises & Discoveries

- Observation: the core impact-analysis aggregation already exists and is tested, but it is only reachable today as part of broader structural reporting and pipeline output.
  Evidence: `src/sattlint/devtools/structural_reports.py:collect_impact_analysis_report()` already computes reverse dependents, and `tests/test_pipeline_collection.py` already asserts direct and transitive library and module impacts.
- Observation: the pipeline and artifact registry already treat impact analysis as a named artifact.
  Evidence: `src/sattlint/devtools/pipeline.py`, `src/sattlint/devtools/pipeline_artifacts.py`, and `src/sattlint/devtools/artifact_registry.py` all contain an `impact_analysis` artifact shape.
- Observation: scanning the full repository workspace can take long enough that the direct command appears hung unless it emits progress before snapshot loading completes.
  Evidence: a direct `python -m sattlint.devtools.impact_analyzer` run against the repo remained in the `loading workspace graph inputs` stage beyond a short timeout until stderr progress output was added in `src/sattlint/devtools/impact_analyzer.py`.
- Observation: the repository-wide closeout artifact is more deterministic when driven from a known fixture entry file than from a guessed library id.
  Evidence: `python scripts/run_repo_python.py -m sattlint.devtools.impact_analyzer --workspace-root . --entry-file tests/fixtures/corpus/semantic/ParallelWriteRace.s --format json --output-dir artifacts/impact-analysis` resolved the requested target cleanly to library `semantic` and module `BasePicture`, while also preserving unrelated `snapshot_failures` from invalid and edge-case fixtures.

## Decision Log

- Decision: build the first user-facing tool as a thin wrapper around `collect_impact_analysis_report()` rather than reimplementing graph traversal in a new module.
  Rationale: the repository already has working reverse-dependency logic and tests; duplicating it would create drift immediately.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: ship the first milestone as a dedicated devtool module that can run with `python -m`, with an optional console-script alias only after the core behavior is stable.
  Rationale: this keeps the first implementation small and avoids unnecessary packaging churn while the CLI contract settles.
  Date/Author: 2026-05-04 / Copilot (GPT-5.4)
- Decision: use a committed fixture entry file for the closeout artifact instead of relying on a repository-wide library selector.
  Rationale: the direct tool already supports entry-file expansion, and the fixture-based selector yields a deterministic artifact without assuming that a particular library id exists across the whole repo workspace.
  Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Implementation complete. The repo now has a direct, scriptable impact-analysis command in `src/sattlint/devtools/impact_analyzer.py` with explicit `--library`, `--module`, and `--entry-file` selectors, deterministic JSON output, and focused command tests in `tests/devtools/test_impact_analyzer.py`. The command emits progress to stderr so long repository scans no longer appear idle while stdout stays machine-readable.

Closeout validation passed without requiring any follow-on code changes. The focused pytest route passed at `141 passed in 1.71s`, the touched-file Ruff check passed with `All checks passed!`, and the touched-file Pyright check passed with `0 errors, 0 warnings, 0 informations`. The direct command wrote `artifacts/impact-analysis/impact_analysis.json`, and that artifact proved that requested target expansion, selected impacts, and `snapshot_failures` all remain visible in the final JSON payload.

No helper extraction from `src/sattlint/devtools/structural_reports.py` was needed to finish the first milestone. The thin wrapper design held, so this plan now moves to `docs/exec-plans/completed/`.

## Context and Orientation

The controlling code path already lives in `src/sattlint/devtools/structural_reports.py`. `collect_dependency_graph_report()` builds the library-level dependency graph. `collect_call_graph_report()` builds the module-level access graph. `collect_impact_analysis_report()` combines those two reports and emits direct and transitive dependents, entry files, read and write counts, and symbol summaries. The structural pipeline in `src/sattlint/devtools/pipeline.py` and the artifact registry in `src/sattlint/devtools/artifact_registry.py` already know how to include the resulting `impact_analysis` artifact in broader runs.

Before this work landed, what did not exist was a narrow user-facing tool. The resulting wrapper now lives in `src/sattlint/devtools/impact_analyzer.py`, and the dedicated direct-command coverage lives in `tests/devtools/test_impact_analyzer.py`.

For this plan, "impact analysis" means reverse dependency reporting: starting from something the user plans to change, show what libraries, modules, and entry files would be affected. It does not mean speculative runtime risk scoring, automatic prioritization, or diff parsing from Git history in the first milestone.

## Plan of Work

Create `src/sattlint/devtools/impact_analyzer.py` as a thin command module. It should load or accept graph inputs, call the existing dependency and impact collectors, and then filter the full report down to the user's requested starting points. Support at least three selectors in the first milestone: library IDs, module IDs, and entry-file paths. Keep the selectors explicit and additive; do not infer them from unstaged Git changes in the first slice.

Define a stable JSON output contract that preserves the existing collector payloads but adds a top-level `requested_targets` section and a filtered `selected_impacts` section. The full report can still be written when requested, but the default console experience should be concise and should tell the user exactly which direct and transitive dependents were found.

Keep the graph-building logic in `src/sattlint/devtools/structural_reports.py`. If the existing collector needs a small refactor to expose reusable helpers, make that refactor there and extend the existing tests in `tests/test_pipeline_collection.py`. Command parsing, output filtering, and file writing belong in the new devtool module, with its own direct tests in `tests/devtools/test_impact_analyzer.py`.

If the packaging surface needs an alias later, add it only after the module works with `python -m sattlint.devtools.impact_analyzer`. The first milestone should optimize for correctness and scriptability rather than for extra entrypoint names.

## Concrete Steps

Run all commands from the repository root.

Inspect the existing collectors and pipeline artifact plumbing:

    rg -n "def collect_dependency_graph_report|def collect_impact_analysis_report|impact_analysis" src/sattlint/devtools/structural_reports.py src/sattlint/devtools/pipeline.py src/sattlint/devtools/pipeline_artifacts.py src/sattlint/devtools/artifact_registry.py tests/test_pipeline_collection.py tests/test_pipeline_run.py

After implementing the wrapper and its tests, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/devtools/test_impact_analyzer.py tests/test_pipeline_collection.py tests/test_pipeline_run.py -x -q --tb=short

Exercise the tool directly on the repository workspace with a committed fixture selector:

    python scripts/run_repo_python.py -m sattlint.devtools.impact_analyzer --workspace-root . --entry-file tests/fixtures/corpus/semantic/ParallelWriteRace.s --format json --output-dir artifacts/impact-analysis

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/devtools/impact_analyzer.py src/sattlint/devtools/structural_reports.py tests/devtools/test_impact_analyzer.py tests/test_pipeline_collection.py tests/test_pipeline_run.py
    python scripts/run_repo_python.py -m pyright src/sattlint/devtools/impact_analyzer.py src/sattlint/devtools/structural_reports.py

Expected success signal: the direct command exits with code `0`, writes a stable JSON file when requested, and the filtered report clearly lists direct and transitive dependents for the requested selectors.

## Validation and Acceptance

Acceptance requires a first-class user tool. A developer must be able to run the new module directly without invoking the full pipeline, supply one or more explicit selectors, and receive a deterministic report of impacted libraries, modules, and entry files. The new tool tests must fail before implementation and pass after it. Existing pipeline collection tests must continue to pass, proving the shared collector behavior did not regress.

The tool must fail clearly when a requested selector does not exist in the collected graphs. It must not silently emit an empty success payload that hides typos. The JSON contract must remain stable and machine-readable. If a workspace snapshot fails, that failure must appear in the output rather than being discarded.

## Idempotence and Recovery

This plan is safe to execute incrementally because the first milestone is additive. The wrapper module can be built and tested without changing the broader pipeline contract. If a refactor in `structural_reports.py` causes pipeline regressions, stop and restore collector compatibility before continuing with command-level features. If selector design becomes contentious, keep the command scoped to explicit selectors and postpone convenience aliases until after the core report shape is stable.

## Artifacts and Notes

Recorded closeout artifacts:

- Focused validation: `python scripts/run_repo_python.py -m pytest --no-cov tests/devtools/test_impact_analyzer.py tests/test_pipeline_collection.py tests/test_pipeline_run.py -x -q --tb=short` -> `141 passed in 1.71s`
- Touched-file lint: `python scripts/run_repo_python.py -m ruff check src/sattlint/devtools/impact_analyzer.py src/sattlint/devtools/structural_reports.py tests/devtools/test_impact_analyzer.py tests/test_pipeline_collection.py tests/test_pipeline_run.py` -> `All checks passed!`
- Touched-file typing: `python scripts/run_repo_python.py -m pyright src/sattlint/devtools/impact_analyzer.py src/sattlint/devtools/structural_reports.py` -> `0 errors, 0 warnings, 0 informations`
- Real tool artifact: `python scripts/run_repo_python.py -m sattlint.devtools.impact_analyzer --workspace-root . --entry-file tests/fixtures/corpus/semantic/ParallelWriteRace.s --format json --output-dir artifacts/impact-analysis` -> exit `0`, writes `artifacts/impact-analysis/impact_analysis.json`, resolves the requested fixture to library `semantic` and module `BasePicture`, and preserves `snapshot_failures` for other workspace files that fail snapshot loading.
- Structural helper note: no reusable helper extraction from `src/sattlint/devtools/structural_reports.py` was required to close the first milestone.

Useful JSON excerpt from the recorded artifact:

    {
      "requested_targets": {
        "entry_files": [
          "tests/fixtures/corpus/semantic/ParallelWriteRace.s"
        ],
        "libraries": [],
        "modules": []
      },
      "resolved_targets": {
        "libraries": ["semantic"],
        "modules": ["BasePicture"]
      },
      "selected_impacts": {
        "libraries": [ ... ],
        "modules": [ ... ]
      }
    }

## Interfaces and Dependencies

The core dependency is `src/sattlint/devtools/structural_reports.py`, especially `collect_dependency_graph_report()` and `collect_impact_analysis_report()`. The new user-facing wrapper belongs in `src/sattlint/devtools/impact_analyzer.py`. Existing shared behavior is already exercised in `tests/test_pipeline_collection.py` and `tests/test_pipeline_run.py`, and the new direct-command coverage belongs in `tests/devtools/test_impact_analyzer.py`. The broader artifact vocabulary is defined in `src/sattlint/devtools/pipeline_artifacts.py` and `src/sattlint/devtools/artifact_registry.py`, and any new file-writing behavior should remain compatible with those existing payload shapes.
