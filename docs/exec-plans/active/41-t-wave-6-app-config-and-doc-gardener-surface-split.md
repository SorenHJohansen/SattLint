# T-Wave-6 App, Config, and Doc-Gardener Surface Split

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan covers the next control-surface debt cluster from the 2026-05-15 architecture review. `src/sattlint/app_analysis.py`, `src/sattlint/app.py`, `src/sattlint/app_graphics.py`, `src/sattlint/config.py`, and `src/sattlint/devtools/doc_gardener.py` each mix pure helpers, file-system input or output, and user-facing menu or reporting behavior in one owner file. After this work lands, those surfaces will still expose the same menu commands, config loading behavior, and doc-gardener updates, but the logic will be separated into smaller modules with clearer ownership.

Two additional files — `src/sattlint/validation.py` (1,270 lines) and `src/sattlint/engine.py` (1,152 lines) — are not yet in `file_debt_ratchet.json`. This plan adds their ratchet baseline entries as a precondition step so they cannot regress further while waiting for a dedicated decomposition plan.

The observable proof is that the app analysis menus still run, config validation still returns the same errors for bad settings, and doc-gardener still updates the quality and debt-tracker docs when asked, while the large owner files shrink instead of regressing further.

## Progress

- [x] (2026-05-15) Create the ExecPlan and confirm `src/sattlint/app_analysis.py` is 1300 lines, `src/sattlint/config.py` is 626 lines, and `src/sattlint/devtools/doc_gardener.py` is 849 lines. The architecture review also flags fresh structural regression in `config.py` and `doc_gardener.py`.
- [x] (2026-05-15) Gap review adds `src/sattlint/app.py` (1033 lines, ratcheted must_shrink target 500), `src/sattlint/app_graphics.py` (924 lines, ratcheted must_shrink target 500), and the precondition ratchet entries for `src/sattlint/validation.py` (1270 lines) and `src/sattlint/engine.py` (1152 lines) to this plan.
- [ ] Add baseline ratchet entries for `validation.py` and `engine.py` in `artifacts/analysis/file_debt_ratchet.json` so both files cannot grow further while they await decomposition.
- [ ] Fix stale path references in `docs/exec-plans/tech-debt-tracker.md` that still point to `active/` for T-003 through T-026 plans that now live in `completed/`.
- [ ] Split `app_analysis.py` into project-loading or cache helpers, analysis runners, and menu or CLI handlers, leaving the owner file as a thin facade and dispatch surface.
- [ ] Split `app.py` by extracting interactive menu routing and startup orchestration into dedicated helpers while keeping the public `main` entry point and `self_check` behavior stable.
- [ ] Split `app_graphics.py` by moving graphics-rule menu flows and report rendering into dedicated helpers while keeping the public graphics app behavior stable.
- [ ] Move config normalization, validation, and IO into dedicated helper modules while keeping the public `load_config`, `validate_config`, `validate_loaded_config`, `validate_effective_config`, and `save_config` names stable.
- [ ] Move doc-gardener scan families and mutation steps into smaller helpers, keeping the CLI behavior and `docs/quality-score.md` or `docs/exec-plans/tech-debt-tracker.md` update flow stable.
- [ ] Add or split focused tests for app menus, config validation, and doc-gardener behavior, then rerun narrow pytest plus touched-file Ruff and Pyright.

## Surprises & Discoveries

Observation: `app_analysis.py` already has natural split points.
Evidence: the file contains distinct clusters for project loading, analysis execution, menu rendering, and check execution, and the test suite is already partitioned into `tests/_app_analysis_part*.py` plus focused top-level app tests.

Observation: `config.py` is doing three different jobs.
Evidence: the file owns legacy-key normalization, config validation, filesystem existence checks, and TOML load/save behavior, even though those concerns change at different rates.

Observation: `doc_gardener.py` still mixes scanning and mutation.
Evidence: the same file owns scan functions such as `scan_dead_links` and `scan_stale_docs`, pipeline snapshot loading, quality-score updates, and optional pull-request side effects.

Observation: `src/sattlint/console.py` is also coverage-ratcheted low.
Evidence: the 2026-05-15 repo-health snapshot lists `src/sattlint/console.py` at 63.29% line coverage, so any refactor that touches console output should add focused tests instead of treating that file as a free dependency.

Observation: `app.py` and `app_graphics.py` are ratcheted must_shrink owners with no active plan.
Evidence: `artifacts/analysis/file_debt_ratchet.json` marks `app.py` at 891-line baseline (target 500) and `app_graphics.py` at 907-line baseline (target 500), while neither appears in any exec plan created at review time. They belong in this plan because they are part of the same interactive app control surface as `app_analysis.py`.

Observation: `validation.py` and `engine.py` are large but have no ratchet entries.
Evidence: `src/sattlint/validation.py` is 1270 lines and `src/sattlint/engine.py` is 1152 lines, but neither has an entry in `file_debt_ratchet.json`. Without a baseline entry they can grow silently while waiting for a decomposition plan.

Observation: tech-debt-tracker.md has stale path references.
Evidence: the tracker still lists T-003 through T-026 coverage under `docs/exec-plans/active/`, but all those plans now live in `completed/`.

## Decision Log

Decision: separate pure validation from filesystem IO in the config surface.
Rationale: validation can be tested cheaply and deterministically, while path existence and TOML persistence need different tests and should not force edits through one monolithic owner.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: keep `app_analysis.py` as the public app-analysis facade while moving internal seams out.
Rationale: menu and CLI callers already import from that file, so the safest structural change is extraction behind a stable facade rather than a broad rename.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: preserve doc-gardener CLI behavior and tracked-document formats while shrinking the owner file.
Rationale: the debt is structural. Changing the quality-score or tech-debt-tracker formats during the split would make validation harder and widen scope.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

At creation time, no code has landed yet. The current outcome is a scoped plan that treats app analysis, config, and doc-gardener as one control-surface cluster because they are all orchestration-heavy, user-facing, and already backed by focused tests.

## Context and Orientation

`src/sattlint/app_analysis.py` is the interactive analysis app owner. It loads projects, resolves cache entries, runs analyzers, and renders menu flows such as variable analysis, module analysis, interface communication, advanced analysis, and check execution. In this repository, a "facade" is a thin public module that keeps the existing import path while delegating the actual work to smaller internal helpers.

`src/sattlint/app.py` is the top-level interactive app owner. It owns `main`, `self_check`, the top-level menu loop, and startup orchestration. It is ratcheted must_shrink with a 500-line target.

`src/sattlint/app_graphics.py` is the interactive graphics app owner. It owns graphics-rule menu flows, validation, and rendering. It is ratcheted must_shrink with a 500-line target.

`src/sattlint/config.py` is the configuration owner. It defines default config values, normalizes legacy documentation keys, validates the shape and filesystem readiness of settings, and loads or saves TOML config files.

`src/sattlint/devtools/doc_gardener.py` is the documentation maintenance tool. It scans markdown and debt-tracker content for stale information and can update tracked docs such as `docs/quality-score.md` and `docs/exec-plans/tech-debt-tracker.md`.

The nearest tests are `tests/test_app_analysis.py`, `tests/test_app_analysis_project_cache.py`, `tests/test_app_menus.py`, `tests/test_app_menu_helpers.py`, `tests/test_app_cli_commands.py`, `tests/test_app_support_helpers.py`, `tests/test_app_config_validation.py`, and `tests/test_repo_audit_doc_gardener.py`.

## Plan of Work

Start with the precondition steps. Add baseline ratchet entries for `src/sattlint/validation.py` and `src/sattlint/engine.py` in `artifacts/analysis/file_debt_ratchet.json` using their current line counts as the `current_baseline` and `must_shrink` as the `touch_rule`. Fix the stale path references in `docs/exec-plans/tech-debt-tracker.md` by replacing every `active/33-` through `active/39-` reference with `completed/33-` through `completed/39-`.

Then split `src/sattlint/app_analysis.py`. Move the project-loading and cache helpers into `src/sattlint/_app_analysis_loading.py`, and move menu-specific rendering and selection parsing into `src/sattlint/_app_analysis_menus.py`. Keep the public functions in `app_analysis.py` as stable wrappers or small dispatch points.

Next, split `src/sattlint/app.py` by extracting startup orchestration and menu-loop helpers into `src/sattlint/_app_startup.py`, keeping `main`, `self_check`, and the top-level menu registration in the owner file as a thin dispatch surface.

Then split `src/sattlint/app_graphics.py` by moving graphics-rule menu flows into `src/sattlint/_app_graphics_menus.py` and report rendering helpers into `src/sattlint/_app_graphics_reports.py`, keeping the public entry points in the owner file.

Then split `src/sattlint/config.py` by concern. Put pure config-shape validation into `src/sattlint/config_validation.py`, keep path-existence or readability checks in that validation surface or a small adjacent helper, and isolate TOML load or save behavior in `src/sattlint/config_io.py` so later changes do not require editing the same file as the rule tables.

Finally, split `src/sattlint/devtools/doc_gardener.py` into scanning helpers and tracked-document mutation helpers. Put scan-only behavior in `src/sattlint/devtools/_doc_gardener_scan.py`, put tracked-document updates in `src/sattlint/devtools/_doc_gardener_updates.py`, and keep the optional pull-request side effects isolated so the scan functions remain side-effect free.

## Concrete Steps

Run all commands from the repository root.

Inspect the current owner surfaces before editing code:

    wc -l src/sattlint/app.py src/sattlint/app_analysis.py src/sattlint/app_graphics.py src/sattlint/config.py src/sattlint/devtools/doc_gardener.py src/sattlint/validation.py src/sattlint/engine.py
    rg -n "load_project|analysis_menu|run_checks|validate_config|load_config|save_config|run_scan|update_quality_score|update_tech_debt_scan_log|open_fixup_pr" src/sattlint/app_analysis.py src/sattlint/config.py src/sattlint/devtools/doc_gardener.py

After the extraction work lands, run the narrow validation first:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_app.py tests/test_app_analysis.py tests/test_app_analysis_project_cache.py tests/test_app_menus.py tests/test_app_menu_helpers.py tests/test_app_cli_commands.py tests/test_app_support_helpers.py tests/test_app_config_validation.py tests/test_repo_audit_doc_gardener.py -x -q --tb=short

Run touched-file quality gates after the focused tests pass:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint/app.py src/sattlint/_app_startup.py src/sattlint/app_analysis.py src/sattlint/_app_analysis_loading.py src/sattlint/_app_analysis_menus.py src/sattlint/app_graphics.py src/sattlint/_app_graphics_menus.py src/sattlint/_app_graphics_reports.py src/sattlint/config.py src/sattlint/config_validation.py src/sattlint/config_io.py src/sattlint/devtools/doc_gardener.py src/sattlint/devtools/_doc_gardener_scan.py src/sattlint/devtools/_doc_gardener_updates.py tests/test_app.py tests/test_app_analysis.py tests/test_app_menus.py tests/test_app_config_validation.py tests/test_repo_audit_doc_gardener.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint/app.py src/sattlint/_app_startup.py src/sattlint/app_analysis.py src/sattlint/_app_analysis_loading.py src/sattlint/_app_analysis_menus.py src/sattlint/app_graphics.py src/sattlint/_app_graphics_menus.py src/sattlint/_app_graphics_reports.py src/sattlint/config.py src/sattlint/config_validation.py src/sattlint/config_io.py src/sattlint/devtools/doc_gardener.py src/sattlint/devtools/_doc_gardener_scan.py src/sattlint/devtools/_doc_gardener_updates.py

If the split changes user-facing app menus or doc-gardener output flow, run one smoke command after the tests pass:

    bash scripts/run_repo_python.sh -m sattlint.devtools.doc_gardener --check-only

## Validation and Acceptance

Acceptance requires stable behavior across all three surfaces. App-analysis menu flows must still open and run the same analysis paths. Config validation must still reject the same invalid keys, modes, naming styles, and broken filesystem paths. Doc-gardener must still scan tracked docs and update the quality-score and debt-tracker files through the same CLI surface. The owner files must shrink, and no new helper file should replace one monolith with another equally large one.

## Idempotence and Recovery

This plan is safe to execute in three small slices. Split `app_analysis.py` first and validate it. Then move config validation or IO. Then shrink doc-gardener. Leave stable wrapper functions in the original owner files if imports or tests still depend on them. If a split changes menu numbering or doc output unexpectedly, restore the old wrapper behavior before moving on.

## Artifacts and Notes

Current owner sizes at plan creation time:

    1033 src/sattlint/app.py
    1300 src/sattlint/app_analysis.py
    924 src/sattlint/app_graphics.py
    626 src/sattlint/config.py
    849 src/sattlint/devtools/doc_gardener.py

Added by gap review (2026-05-15):

    1270 src/sattlint/validation.py  (no ratchet entry yet — add baseline as precondition)
    1152 src/sattlint/engine.py       (no ratchet entry yet — add baseline as precondition)

Current fresh structural regressions called out by the architecture review:

    src/sattlint/config.py
    src/sattlint/devtools/doc_gardener.py

## Interfaces and Dependencies

The implementation surface is `src/sattlint/app.py`, `src/sattlint/app_analysis.py`, `src/sattlint/app_graphics.py`, `src/sattlint/config.py`, and `src/sattlint/devtools/doc_gardener.py`. Preserve the current app menu and CLI entry behavior, the existing config load and save contract, and the current doc-gardener update targets in `docs/quality-score.md` and `docs/exec-plans/tech-debt-tracker.md`. `src/sattlint/validation.py` and `src/sattlint/engine.py` are in scope only for ratchet-entry precondition work; their decomposition is deferred to a later plan.
