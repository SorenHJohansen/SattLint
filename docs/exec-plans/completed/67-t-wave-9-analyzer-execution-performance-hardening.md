# T-Wave-9 Analyzer Execution Performance Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan reduces repeated analyzer work in the main SattLint analysis path. Today, running the default analyzer batch on one loaded target repeatedly rebuilds analyzer-local state, repeatedly walks the same `BasePicture` tree, and in the semantic layer can rerun analyzers whose findings were already computed moments earlier. After this work lands, a maintainer should be able to run the normal analysis flow and see the same findings with less duplicate in-process work, plus explicit proof that the hot analyzer families reuse shared per-target artifacts instead of rebuilding them for each analyzer.

The observable proof is partly behavioral and partly performance-oriented. Behavioral proof means the existing analyzer reports, semantic findings, and CLI output stay stable. Performance proof means focused regression tests and profiling counters show that one target-level analysis batch reuses shared artifacts, avoids semantic double execution, and does not rebuild the variable-analysis hot path independently for both `variables` and `sfc` when both run in the same batch.

## Progress

- [x] (2026-06-01 06:55Z) Created this ExecPlan and captured the current hot paths: `src/sattlint/app_analysis.py` runs analyzers in a strict target-by-analyzer loop, `src/sattlint/analyzers/sattline_semantics.py` reruns semantic-mapped analyzers directly, and `src/sattlint/analyzers/_sfc_collectors.py` subclasses `VariablesAnalyzer`.
- [x] (2026-06-01 09:10Z) Confirmed that the previous active `62` path conflicted with an already completed `62` plan, so this analyzer-execution follow-on now uses a new active identifier.
- [x] (2026-06-01 11:20Z) Added low-noise profiling and reuse counters through `AnalysisSharedArtifacts`, plus opt-in `SATTLINT_PROFILE_ANALYZERS=1` summary output from `src/sattlint/app_analysis.py`.
- [x] (2026-06-01 11:20Z) Added a per-target shared analysis-artifact seam on `AnalysisContext` via `src/sattlint/analyzers/_shared_analysis.py` and threaded it through `_run_checks(...)`.
- [x] (2026-06-01 11:20Z) Eliminated semantic-layer double execution for already-produced same-target reports by teaching `src/sattlint/analyzers/sattline_semantics.py` to reuse `reports_by_analyzer_key` and only fall back to reruns when a mapped analyzer report is missing.
- [x] (2026-06-01 11:20Z) Extracted and reused variable-analysis hot artifacts for `variables`, `sfc`, and the nearby reset or implicit-latch path without changing report contents.
- [x] (2026-06-01 10:10Z) Measured the remaining standalone subsystems on real HA inputs. `graphics_validation` stayed tiny (13.2 ms cold, 1.7 ms warm on `KaHAMPCSøjleLib.g`), `layout_geometry` stayed modest (147.1 ms median on `KaHAMPCSøjleLib`), and ICF stayed modest (`2.2 ms` parse, `0.8 ms` moduletype-index build, `273.3 ms` validation on `KaHAOPS2Z4.icf`). `graphics_rules` validation itself also stayed moderate (`549.3 ms` median for a synthetic 32-rule sample), but the real layout-entry collection path was material at `25.2 s` median for `31,537` entries, so that cost is recorded as a separate follow-on candidate instead of widening this milestone.
- [x] (2026-06-01 09:57Z) Re-ran the representative profiling smoke against `KaHAMPCSøjleLib` and captured a successful reuse-profile line: `shared-artifact-holders=1, variable-foundation-builds=1, semantic-precomputed-reports=0, semantic-reruns=0, local-env-builds=3`.
- [x] (2026-06-01 11:28Z) Focused regression tests passed for `tests/analyzers/test_sattline_semantics.py`, `tests/analyzers/test_sfc.py`, `tests/analyzers/test_reset_contamination.py`, and `tests/_app_analysis_part2.py`, and touched production-file Pyright passed for the edited analyzer and app-analysis modules.

## Surprises & Discoveries

- Observation: the main performance problem is not repeated project loading; it is repeated in-process analyzer work after the `BasePicture` is already loaded.
  Evidence: `src/sattlint/app_analysis.py` creates one `AnalysisContext` per target inside `_run_checks(...)` and then calls `spec.run(context)` for each analyzer in sequence. Nothing in that loop shares analyzer-local traversal state.
- Observation: the repository already has a disk-backed report cache, but it does not solve in-process duplication inside a single uncached batch.
  Evidence: `_run_with_analysis_report_cache(...)` in `src/sattlint/app_analysis.py` caches final reports by project cache key and analyzer key. It does not carry shared objects such as `TypeGraph`, scope data, or per-module traversal state from one analyzer to the next.
- Observation: `sattline_semantics` currently duplicates analyzer work instead of aggregating already-computed reports.
  Evidence: `src/sattlint/analyzers/sattline_semantics.py` iterates `registry_module.get_default_analyzer_catalog().analyzers`, rebuilds analyzer arguments, and invokes analyzer functions again for any enabled analyzer that exposes `semantic_mapping_kind`.
- Observation: `sfc` sits on the same expensive variable-analysis foundation as `variables`.
  Evidence: `_SfcAccessCollector` in `src/sattlint/analyzers/_sfc_collectors.py` subclasses `VariablesAnalyzer`, so both analyzers currently pay the `VariablesAnalyzer` initialization cost and related AST walking in the same batch.
- Observation: same-batch semantic reuse also required analyzer ordering, not just a shared report map.
  Evidence: `sattline-semantics` appears before many analyzers in the full catalog order, so `_run_checks(...)` had to move the semantic layer to the end of the selected batch order for already-produced reports to exist when semantic aggregation runs.
- Observation: the previous active `62` path conflicted with an existing completed `62` plan and also contained two separate plan bodies.
  Evidence: `docs/exec-plans/completed/62-t-wave-8-performance-and-scalability-hardening.md` already exists, while the former `docs/exec-plans/active/62-t-wave-8-performance-and-scalability-hardening.md` held both analyzer-execution and loader-pipeline follow-on content.
- Observation: after the external HA dependency fix, the representative `KaHAMPCSøjleLib` smoke now runs through analyzer execution and emits the reuse counters needed for this milestone.
  Evidence: `artifacts/tmp/profile-kahampcsoejlelib_measure.json` records `Analyzer reuse profile for KaHAMPCSøjleLib: shared-artifact-holders=1, variable-foundation-builds=1, semantic-precomputed-reports=0, semantic-reruns=0, local-env-builds=3`.
- Observation: `graphics_validation` already benefits from an effective parser-factory cache and is not a material standalone hotspot on the representative graphics file.
  Evidence: `artifacts/tmp/plan67_standalone_subsystem_measurements.json` records `13.2 ms` cold and `1.7 ms` warm medians for `src/sattlint/graphics_validation.py` on the representative `KaHAMPCSøjleLib.g` graphics file.
- Observation: `graphics_rules` cost is dominated by layout-entry collection, not by rule matching or mismatch comparison.
  Evidence: `artifacts/tmp/plan67_standalone_subsystem_measurements.json` records `25.2 s` median for `app_graphics.collect_graphics_layout_entries_for_target(...)` over `31,537` entries, versus `8.9 ms` with the current empty `graphics_rules.json` and `549.3 ms` for a synthetic 32-rule validation sample.
- Observation: `layout_geometry` and ICF validation are real but comparatively modest on representative inputs and do not justify widening this plan.
  Evidence: `artifacts/tmp/plan67_standalone_subsystem_measurements.json` records `147.1 ms` median for `collect_layout_overlap_issues(...)` on `KaHAMPCSøjleLib`, plus `273.3 ms` median ICF validation after `2.2 ms` parse and `0.8 ms` moduletype-index build on `KaHAOPS2Z4.icf`.

## Decision Log

- Decision: treat analyzer execution reuse as the first performance follow-on milestone instead of bundling every performance topic named in prior review notes into one edit.
  Rationale: the current evidence is strongest around duplicate analyzer work in `app_analysis`, `sattline_semantics`, and the variable-family analyzers. Starting there gives a measurable win without entangling loader caches, LSP refresh behavior, pipeline scans, and graphics subsystems in the same slice.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)
- Decision: assign this follow-on a new active identifier rather than reusing `62`.
  Rationale: `62` already belongs to a completed plan, so keeping an active plan under the same id would make tracker routing ambiguous.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)
- Decision: add reusable per-target artifacts to `AnalysisContext` rather than building a new global singleton cache.
  Rationale: the duplication being addressed happens inside one target analysis batch. A target-scoped artifact store is easier to invalidate, easier to test, and avoids cross-target contamination.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)
- Decision: require explicit counters or call-count proof in tests instead of accepting a wall-clock speedup claim alone.
  Rationale: wall-clock timing is noisy in CI and on shared developer machines. Call-count assertions on hot constructors and mapping functions are more stable and directly prove the intended reuse.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)
- Decision: leave `graphics_validation`, `graphics_rules`, `layout_geometry`, and `icf` out of the first implementation milestone.
  Rationale: those are related to performance, but they do not flow through the same analyzer-registry hot loop. They should be measured after the registry-path work lands, not used to widen the initial change.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)
- Decision: close plan 67 after measurement rather than widening it to optimize graphics-layout collection.
  Rationale: the only remaining material standalone cost sits in `src/sattlint/app_graphics.py` and `src/sattlint/devtools/structural_reports.py` during layout-entry collection for graphics rules, which is outside the analyzer-registry reuse seam this plan owns. The other measured standalone subsystems were small enough on representative inputs to avoid a new milestone here.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This implementation landed the target-scoped reuse seam described above. `src/sattlint/analyzers/framework.py` now carries `AnalysisSharedArtifacts` on `AnalysisContext`; `src/sattlint/app_analysis.py` creates one holder per target, stores same-batch reports on it, emits opt-in reuse counters, and schedules `sattline-semantics` after the analyzers it can aggregate. `src/sattlint/analyzers/sattline_semantics.py` now reuses precomputed mapped-analyzer reports when present and only reruns missing analyzers in standalone or partial-report cases.

The variable-family hot path now reuses a shared `VariableAnalysisArtifacts` foundation across `variables` and `sfc`, while `_reset_contamination.py` reuses cached local env maps across the reset-contamination and implicit-latch scans. Focused proof landed in the owner suites: `tests/_app_analysis_part2.py`, `tests/analyzers/test_sattline_semantics.py`, `tests/analyzers/test_sfc.py`, and `tests/analyzers/test_reset_contamination.py`. Focused pytest passed, and touched production-file Pyright passed.

Standalone measurement is now complete. `graphics_validation`, `layout_geometry`, and ICF validation all stayed comparatively modest on representative real inputs, so they do not need another optimization pass inside this milestone. `graphics_rules` itself also stayed moderate once entries existed, but the layout-entry collection path used by `app_graphics.collect_graphics_layout_entries_for_target(...)` was materially expensive and should be handled as a separate follow-on on the graphics or structural-reporting surface rather than reopening this analyzer-execution plan.

With those measurements captured and the representative profiling smoke complete, plan 67 is complete and can move to `docs/exec-plans/completed/`.

## Context and Orientation

The main CLI analysis batch lives in `src/sattlint/app_analysis.py`. In this repository, an `analyzer` is one registered rule bundle that consumes an `AnalysisContext` and returns a report. The default CLI batch is a short list of analyzers defined in `src/sattlint/analyzers/registry.py`, but the full analyzer catalog is larger and also feeds the semantic layer.

`AnalysisContext` lives in `src/sattlint/analyzers/framework.py`. It is the per-target object that already carries the loaded `BasePicture`, the project graph, debug flags, and target metadata. A `BasePicture` is the root parsed SattLine program tree for one analyzed target. If this plan refers to a `shared artifact`, it means a reusable object derived from one `BasePicture` during one batch run, such as a type graph, an index of module paths, or a memoized mapping from module path to scope information.

The hottest reusable analyzer family is centered on `src/sattlint/analyzers/variables.py`. `VariablesAnalyzer` constructs a `TypeGraph`, a canonical symbol table, a context builder, several indexes over typedefs and variables, and caches for module-path-to-scope resolution during its initializer. `src/sattlint/analyzers/_sfc_collectors.py` inherits from `VariablesAnalyzer`, which means the `sfc` analyzer currently rebuilds much of the same foundation independently of the normal `variables` analyzer. `src/sattlint/analyzers/reset_contamination.py` is separate code, but it also performs its own tree walk over many of the same modules.

The semantic layer lives in `src/sattlint/analyzers/sattline_semantics.py`. It maps analyzer findings to higher-level semantic rules. Right now it does that by invoking semantic-mapped analyzers again, not by reusing reports that were already computed in `app_analysis`. That is the clearest duplicate-execution seam in the current design.

There are also standalone performance-adjacent subsystems. `src/sattlint/graphics_validation.py` parses graphics files and already caches its parser factory. `src/sattlint/graphics_rules.py` validates layout-rule JSON data. `src/sattlint/analyzers/layout_geometry.py` walks module placement geometry. `src/sattlint/analyzers/icf.py` validates ICF entries. They matter to total runtime, but they do not share the same registry execution seam and should not block the first milestone.

The main owner tests for this work are `tests/test_app_analysis.py`, `tests/analyzers/test_sattline_semantics.py`, `tests/test_analyzers_variables.py`, `tests/analyzers/test_sfc.py`, and `tests/analyzers/test_reset_contamination.py`. The plan may add a small dedicated performance-regression test module if that keeps call-count assertions simpler than bolting them onto broad existing suites.

## Plan of Work

Begin in `src/sattlint/analyzers/framework.py` by extending `AnalysisContext` with a target-scoped shared-artifact holder. Keep the context itself safe to pass around. The artifact holder can be mutable internally, but it must be created fresh per target and must not survive beyond one `_run_checks(...)` batch. Use a narrow, explicit type such as `AnalysisSharedArtifacts` rather than a free-form dictionary so later steps have stable names to program against.

Then update `src/sattlint/app_analysis.py` so `_run_checks(...)` creates one shared-artifact holder for each target and passes it through the existing `AnalysisContext`. At the same seam, add low-noise instrumentation hooks that count artifact builds and analyzer reruns when performance tracing is enabled. The initial instrumentation must stay off by default and should be readable in tests without requiring wall-clock measurements.

Once the shared holder exists, eliminate the most obvious duplicate execution in `src/sattlint/analyzers/sattline_semantics.py`. Introduce a report-reuse path that accepts already-computed analyzer reports for the current target and maps them to semantic issues without calling the analyzer functions again. The plan does not require changing the public `analyze_sattline_semantics(...)` contract for standalone use. If the function is called directly without precomputed reports, it should keep its current fallback behavior.

After semantic reuse is in place, extract the variable-family hot artifacts. The first extraction target is not every field inside `VariablesAnalyzer`; it is the clearly shareable foundation that is expensive and stable for one target, especially `TypeGraph` and the indexes that depend only on the `BasePicture`. Create a narrow helper or artifact dataclass in the analyzer package that builds those once and lets `VariablesAnalyzer` and `_SfcAccessCollector` consume them without rebuilding. Do not share per-report mutable issue lists or trackers.

With that foundation extracted, teach `variables` and `sfc` to use the shared artifacts when they run inside the same batch. If `sfc` still needs a specialized collector, keep it, but construct it from the already-built target artifacts rather than from a cold `VariablesAnalyzer` initialization path. Then measure whether `reset_contamination` can reuse any of the same module-path or environment indexes without forcing a broad rewrite. If the reuse is small and safe, include it here. If it needs a second extraction step, record that in the plan and leave it for the next checkpoint.

Finally, assess the standalone performance-adjacent subsystems after the registry-path work is green. `graphics_validation` should be checked for avoidable per-call transformer allocation, and `layout_geometry` plus `icf` should be measured for actual runtime weight before any refactor is scheduled. Record those results in this plan's `Surprises & Discoveries` or split them into a follow-on plan only if they materially change priority.

## Concrete Steps

Run all commands from the repository root.

Capture the current execution seams before editing:

    rg -n "def _run_checks|spec.run\(context\)|report_cache" src/sattlint/app_analysis.py
    rg -n "class AnalysisContext" src/sattlint/analyzers/framework.py
    rg -n "TypeGraph.from_basepicture|class VariablesAnalyzer" src/sattlint/analyzers/variables.py
    rg -n "class _SfcAccessCollector" src/sattlint/analyzers/_sfc_collectors.py
    rg -n "semantic_mapping_kind|get_default_analyzer_catalog|analyzer_fn" src/sattlint/analyzers/sattline_semantics.py

Implement the shared-artifact seam and the semantic-report reuse path first. After that code is in place, add focused tests that prove reuse without relying on elapsed time. Add or extend tests with names close to these behaviors:

    tests/test_app_analysis.py::test_run_checks_reuses_target_shared_artifacts
    tests/analyzers/test_sattline_semantics.py::test_sattline_semantics_reuses_precomputed_reports
    tests/analyzers/test_sfc.py::test_analyze_sfc_reuses_variable_artifacts_when_available
    tests/analyzers/test_reset_contamination.py::test_reset_contamination_can_consume_shared_indexes

Run the narrow proof after the first implementation milestone:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_app_analysis.py tests/analyzers/test_sattline_semantics.py tests/analyzers/test_sfc.py tests/analyzers/test_reset_contamination.py tests/test_analyzers_variables.py -x -q --tb=short

If a separate small regression module is created for call-count assertions, run it in the same slice:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/analyzers/test_analysis_performance_reuse.py -x -q --tb=short

After the focused tests pass, run touched-file type checking. Adjust the path list to match the actual edited files, but it should stay close to this set:

    bash scripts/run_repo_python.sh -m pyright src/sattlint/app_analysis.py src/sattlint/analyzers/framework.py src/sattlint/analyzers/sattline_semantics.py src/sattlint/analyzers/variables.py src/sattlint/analyzers/_sfc_collectors.py src/sattlint/analyzers/reset_contamination.py tests/test_app_analysis.py tests/analyzers/test_sattline_semantics.py tests/analyzers/test_sfc.py tests/analyzers/test_reset_contamination.py tests/test_analyzers_variables.py

Then run one profiling smoke with tracing enabled on a representative target. The exact command may vary with the local fixture chosen during implementation, but it must remain a direct repository-root command and must print counters that show artifact builds and semantic reruns. One acceptable shape is:

    SATTLINT_PROFILE_ANALYZERS=1 bash scripts/run_repo_python.sh -m sattlint.app --config custom.toml

Expected observable profiling behavior after implementation:

    - one shared-artifact build summary per loaded target, not one per analyzer
    - no semantic rerun count for analyzers whose reports were already available in the same batch
    - one variable-foundation build for a target even when both `variables` and `sfc` run in that batch

## Validation and Acceptance

Acceptance is based on preserved findings plus reduced duplicate work. A maintainer must be able to run the normal analyzer batch and receive the same user-facing reports for the covered analyzers while focused regression tests prove that shared artifacts are reused and semantic reruns are skipped when prior reports already exist.

The work is not complete if it only adds a cache object that nothing consumes. The tests must prove at least these behaviors: `_run_checks(...)` creates one target-scoped shared-artifact holder per target; `analyze_sattline_semantics(...)` can reuse precomputed analyzer reports instead of calling the analyzers again; `variables` and `sfc` do not both rebuild the same target-wide variable foundation during one batch; and the nearby reset-contamination path either reuses extracted indexes or is explicitly documented as deferred with measured evidence.

Performance acceptance must not rely only on raw timing numbers. The plan requires stable counters, call counts, or equivalent deterministic proof that duplicate construction decreased. Wall-clock profiling is useful as supporting evidence, but the main gate is reproducible structural proof.

## Idempotence and Recovery

This plan is safe to execute incrementally. The shared-artifact holder is per target and in memory only, so rerunning the analyzer batch should not persist stale state between commands. If a reuse change leaks findings or changes output ordering, back out the last reuse hook and rerun the nearest focused tests before attempting a broader fix.

If semantic-report reuse complicates the public standalone `analyze_sattline_semantics(...)` function, keep the standalone fallback path and make reuse optional rather than forcing every caller to provide precomputed reports. If extracting the variable foundation exposes too much mutable state, narrow the extraction to immutable indexes first and leave deeper sharing for a follow-on checkpoint.

Do not add a cross-process cache or on-disk artifact format in this milestone. The repository already has a report cache and AST cache story. This plan is about in-process reuse during one analysis batch.

## Artifacts and Notes

Baseline facts captured when this plan was created:

    - `src/sattlint/app_analysis.py` runs analyzers in a strict `for target ... for spec ... spec.run(context)` loop.
    - `src/sattlint/app_analysis.py` already has a disk-backed report cache, but it stores finished reports rather than reusable in-memory analysis artifacts.
    - `src/sattlint/analyzers/sattline_semantics.py` reruns semantic-mapped analyzers directly.
    - `src/sattlint/analyzers/_sfc_collectors.py` subclasses `VariablesAnalyzer`.
    - `src/sattlint/analyzers/reset_contamination.py` independently walks module trees.
    - `src/sattlint/graphics_validation.py`, `src/sattlint/graphics_rules.py`, `src/sattlint/analyzers/layout_geometry.py`, and `src/sattlint/analyzers/icf.py` are related performance surfaces but not the first implementation seam.

Target evidence to capture during implementation:

    - a short profiling transcript showing shared-artifact build counts and semantic rerun counts before and after the change
    - one or more focused tests that monkeypatch hot constructors or builder functions and assert reduced call counts
    - a narrow diff or notes section showing which analyzer families now consume shared artifacts
    - `artifacts/tmp/plan67_standalone_subsystem_measurements.json` and `artifacts/tmp/plan67_standalone_subsystem_measurements.txt`, which record the representative standalone-subsystem timings used to close out this plan

## Interfaces and Dependencies

The main owner seam is `src/sattlint/analyzers/framework.py`, where `AnalysisContext` should gain a stable target-scoped shared-artifact field. If extracting the artifact logic into its own helper keeps the design clearer, create a small private module in `src/sattlint/analyzers/` such as `src/sattlint/analyzers/_shared_analysis.py`. Keep names explicit. Prefer `AnalysisSharedArtifacts` or `VariableAnalysisArtifacts` over generic names like `Cache`.

`src/sattlint/app_analysis.py` must remain the owner of per-target batch orchestration. It should create the shared-artifact holder and pass it through the existing context rather than introducing a second orchestration path.

`src/sattlint/analyzers/sattline_semantics.py` must support two modes at the end of this milestone: standalone execution that computes what it needs itself, and batch reuse that consumes already-computed reports for the current target. The output type must remain `SattLineSemanticsReport`.

`src/sattlint/analyzers/variables.py` and `src/sattlint/analyzers/_sfc_collectors.py` should consume a shared variable foundation that is immutable or effectively immutable for the life of one target batch. Do not share mutable issue lists, mutable usage trackers, or per-report warning collections between analyzers.

Focused regression proof belongs in the existing owner suites when practical. If those suites become too broad for call-count assertions, add a small dedicated module such as `tests/analyzers/test_analysis_performance_reuse.py` and keep it limited to deterministic reuse contracts rather than large end-to-end timing benchmarks.
