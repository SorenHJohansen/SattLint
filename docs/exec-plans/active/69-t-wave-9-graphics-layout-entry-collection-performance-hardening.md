# T-Wave-9 Graphics Layout Entry Collection Performance Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan reduces the time spent collecting graphics layout entries for graphics-rules validation and related structural-report consumers. Today, the representative `KaHAMPCSøjleLib` measurement shows that `app_graphics.collect_graphics_layout_entries_for_target(...)` dominates the standalone graphics follow-on cost even when the active graphics rules file is empty. After this work lands, a maintainer should be able to run the same representative measurement and see materially less time spent in layout-entry collection while the emitted graphics layout entries and downstream graphics-rules output stay behaviorally stable.

The user-visible proof is that graphics-rules validation and any tooling that depends on the graphics layout report stop spending most of their runtime inside structural entry collection. Engineering proof means stage timings show the expensive part of `collect_graphics_layout_entries_for_target(...)` shrank without changing entry counts, grouping behavior, or rule-matching results on representative inputs.

## Progress

- [x] (2026-06-01 10:20Z) Opened this follow-on plan from the completed analyzer-execution slice after the standalone subsystem measurement isolated graphics layout-entry collection as the only remaining material cost.
- [ ] Split the current `collect_graphics_layout_entries_for_target(...)` timing into stage-level measurements for `collect_graphics_layout_report(...)`, per-snapshot accumulation, report building, and structure-path annotation on the representative HA target.
- [ ] Identify the dominant repeated work in `src/sattlint/devtools/_structural_report_graphics.py` and `src/sattlint/app_graphics.py`, then land the smallest safe reuse or batching change that preserves output shape.
- [ ] Add focused regression proof that the optimized path preserves layout-entry payloads, group counts, and rule-matching behavior for representative sample entries.
- [ ] Validate the change with focused pytest, touched-file Pyright, and an updated representative timing artifact that shows lower layout-entry collection cost than the current `25,206.55 ms` median baseline.

## Surprises & Discoveries

- Observation: the expensive graphics follow-on cost is in layout-entry collection, not in graphics expression parsing, rule normalization, or rule mismatch comparison.
  Evidence: `artifacts/tmp/plan67_standalone_subsystem_measurements.json` records `25,206.55 ms` median for `app_graphics.collect_graphics_layout_entries_for_target(...)` over `31,537` entries, while `graphics_validation` warms to `1.706 ms`, empty-rules validation takes `8.938 ms`, and a synthetic 32-rule comparison takes `549.327 ms`.
- Observation: the current app-level collection path is a wrapper around the structural reports graphics pipeline plus a second structure-path annotation step.
  Evidence: `src/sattlint/app_graphics.py` calls `src/sattlint/devtools/structural_reports.py::collect_graphics_layout_report(...)` and then `annotate_graphics_entries_with_structure_paths(...)` before returning entries.
- Observation: the structural graphics report path currently walks all snapshots and accumulates entries before building the report payload.
  Evidence: `src/sattlint/devtools/_structural_report_graphics.py::collect_graphics_layout_report(...)` loops through `resolved_inputs.snapshots`, calls `accumulate_graphics_layout_snapshot(...)`, and only then calls `build_graphics_layout_report(...)`.

## Decision Log

- Decision: scope this follow-on to graphics layout-entry collection instead of reopening the broader analyzer-execution performance plan.
  Rationale: the completed plan 67 measurements isolated one remaining material cost on the graphics or structural-reporting surface. Reopening the analyzer-reuse slice would blur ownership and dilute validation.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)
- Decision: treat `src/sattlint/app_graphics.py`, `src/sattlint/devtools/structural_reports.py`, and `src/sattlint/devtools/_structural_report_graphics.py` as the primary owner surfaces.
  Rationale: the measured hotspot is the wrapper plus structural-report collection pipeline, not `src/sattlint/graphics_rules.py` rule matching or `src/sattlint/graphics_validation.py` parsing.
  Date/Author: 2026-06-01 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This plan is newly opened. No code changes have landed yet. The current baseline is that representative layout-entry collection for `KaHAMPCSøjleLib` takes `25,206.55 ms` median for `31,537` entries, while the downstream rule-checking path stays comparatively small. The main success criterion is to lower that collection cost without changing emitted entry payloads or downstream graphics-rules behavior.

## Context and Orientation

The public app-level owner seam is `src/sattlint/app_graphics.py::collect_graphics_layout_entries_for_target(...)`. That function creates a synthetic snapshot wrapper for one loaded target, calls `src/sattlint/devtools/structural_reports.py::collect_graphics_layout_report(...)`, and then runs `annotate_graphics_entries_with_structure_paths(...)` on the returned `entries` payload before handing it to graphics-rules validation.

`src/sattlint/devtools/structural_reports.py` is the stable facade for structural graph and layout reporting. Its graphics path delegates to `src/sattlint/devtools/_structural_report_graphics.py`, which is where the raw entry accumulation, grouping, sorting, and report construction live. In this plan, a `layout entry` means one serialized module or moduletype graphics-layout payload in the structural graphics report, not a graphics rule and not a parsed `.g` binding.

The current performance evidence comes from `artifacts/tmp/plan67_standalone_subsystem_measurements.json`, which used representative HA inputs. That artifact shows the graphics-rules comparator itself is not the hotspot. The expensive path is the production collection seam that materializes layout entries before any rules are applied.

The main owner tests are likely to sit near `tests/test_structural_reports_graphics.py`, `tests/graphics/test_graphics_rules.py`, and any app-graphics tests that cover `collect_graphics_layout_entries_for_target(...)` or structure-path annotation. If the optimization introduces reusable helpers or cached intermediate forms, those helpers should get narrow deterministic tests rather than broad timing assertions.

## Plan of Work

Start by adding stage-level instrumentation or a dedicated probe around the existing graphics layout-entry path without changing behavior. The first goal is to split the current end-to-end `collect_graphics_layout_entries_for_target(...)` median into at least these components: snapshot accumulation, report building, and structure-path annotation. Keep this measurement helper local to the performance slice and write the artifact under `artifacts/tmp/` so it can be compared against the plan 67 baseline.

Once the dominant stage is confirmed, optimize the nearest owner seam rather than rewriting the whole pipeline. If entry accumulation is dominant, inspect the repeated work inside `accumulate_graphics_layout_snapshot(...)` and its child walkers for redundant serialization, repeated normalization, or avoidable repeated sorting or casefolding. If report building or annotation is dominant, target the specific grouping or path-resolution helper responsible for the repeated work. Prefer extraction or memoization at the smallest stable helper boundary over a broad architectural change.

After the local optimization lands, add regression proof that emitted entries remain stable for representative sample snapshots. The proof should compare deterministic facts such as entry counts, selected key fields, grouping counts, or normalized payload fragments rather than relying only on raw timing numbers. Then rerun the representative timing helper to confirm the end-to-end collection median moved materially downward from the current baseline.

## Concrete Steps

Run all commands from the repository root.

Capture the current owner seams before editing:

    rg -n "collect_graphics_layout_entries_for_target|annotate_graphics_entries_with_structure_paths" src/sattlint/app_graphics.py
    rg -n "collect_graphics_layout_report|accumulate_graphics_layout_snapshot|build_graphics_layout_report" src/sattlint/devtools/structural_reports.py src/sattlint/devtools/_structural_report_graphics.py
    rg -n "collect_graphics_layout_entries_for_target|validate_graphics_layout_entries" tests/graphics tests/test_structural_reports_graphics.py tests/test_app_graphics_prompts.py

Establish or refresh the stage-timing baseline with the representative helper:

    bash scripts/run_repo_python.sh artifacts/tmp/measure_plan67_standalone_subsystems.py

Expected baseline excerpt:

    graphics_rules layout collection median: 25206.55 ms
    graphics_rules synthetic validation median: 549.327 ms

After adding a dedicated stage-timing helper for this plan, rerun it and capture a stage breakdown for the representative target.

Validate the optimized slice with focused owner tests. Adjust the exact list to match the touched files, but it should stay close to:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_structural_reports_graphics.py tests/graphics/test_graphics_rules.py tests/test_app_graphics_prompts.py -x -q --tb=short

Then run touched-file type checking for the touched production files and any new helper or test module:

    bash scripts/run_repo_python.sh -m pyright src/sattlint/app_graphics.py src/sattlint/devtools/structural_reports.py src/sattlint/devtools/_structural_report_graphics.py tests/test_structural_reports_graphics.py tests/graphics/test_graphics_rules.py tests/test_app_graphics_prompts.py

Finally, rerun the representative timing helper and record the new median beside the baseline in this plan.

## Validation and Acceptance

Acceptance requires both behavioral stability and lower representative collection cost. Behavioral stability means the collected graphics layout entries still support the same graphics-rules outcomes, structure-path annotation, and structural grouping behavior on the covered tests and representative probe. Performance proof must show that the end-to-end `collect_graphics_layout_entries_for_target(...)` median is lower than the current `25,206.55 ms` baseline on the representative target, with stage timings that explain where the reduction came from.

The work is not complete if it only moves time between substeps without lowering the end-to-end collection median, or if it improves timing by dropping fields, entries, or path annotations. The acceptance artifact should make it easy to compare pre-change and post-change medians and to confirm that entry counts remain stable.

## Idempotence and Recovery

This plan is safe to execute incrementally. The first stage should be a measurement-only helper or local instrumentation that exposes the dominant graphics layout-entry cost without changing output. If an optimization changes the emitted entry shape or grouping order unexpectedly, revert the local helper or memoization hook, rerun the focused graphics tests, and return to the last known-good stage measurement before trying a different seam.

Avoid introducing cross-run caches or workspace-global mutable state unless the measured hotspot clearly demands it and the invalidation contract is obvious. Prefer per-call memoization or reuse scoped to one collection run. If the owner seam turns out to be too entangled inside `structural_reports`, split the work into a narrower extraction first and keep the timing helper so the next checkpoint still has a stable baseline.

## Artifacts and Notes

Baseline artifacts captured before this plan opened:

    - `artifacts/tmp/plan67_standalone_subsystem_measurements.json` records `25,206.55 ms` median for graphics layout-entry collection over `31,537` entries on `KaHAMPCSøjleLib`.
    - `/home/sqhj/.config/sattlint/graphics_rules.json` currently contains zero rules, so the live graphics-rules runtime is dominated by entry collection rather than rule comparison.
    - `src/sattlint/app_graphics.py` wraps the structural graphics report path and then annotates entries with structure paths.
    - `src/sattlint/devtools/_structural_report_graphics.py` owns snapshot accumulation and graphics layout report building.

Target evidence to capture during implementation:

    - a dedicated stage-timing artifact for the graphics layout-entry collection path
    - a before-or-after comparison of representative collection medians
    - focused regression proof that entry counts and representative payload fragments remain stable

## Interfaces and Dependencies

`src/sattlint/app_graphics.py` owns the app-facing collection API used by graphics-rules validation. Keep its public behavior unchanged unless a broader app contract change is explicitly required.

`src/sattlint/devtools/structural_reports.py` is the stable facade for structural reporting. If implementation needs new low-level helpers or staged entrypoints, prefer keeping them private in `src/sattlint/devtools/_structural_report_graphics.py` and preserving the facade contract.

`src/sattlint/devtools/_structural_report_graphics.py` is the likely optimization owner. Keep any new memoization or helper extraction tightly scoped to one report collection run, and avoid leaking graphics-specific complexity into unrelated structural report modules.

`src/sattlint/graphics_rules.py` is downstream validation, not the primary owner of this hotspot. It should only change if the optimization needs a narrower entry shape contract or extra regression proof for rule matching.
