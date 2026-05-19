# T-Wave-7 App And Config Strict Typing Promotion

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan makes the remaining app and config control-surface files ready for full strict coverage. After this work lands, the startup helpers, analysis or graphics menu helpers, config support files, and shared app-side type surface will be strict-clean, and the existing strict-listed blocker in `src/sattlint/config.py` will be resolved.

The observable proof is that the app and config owner tests remain green, the owned files pass touched-file `pyright`, and the same change updates `pyproject.toml` plus a matching approval record so the slice stops blocking full strict coverage.

## Progress

- [x] (2026-05-18 15:10Z) Create the ExecPlan and capture the live baseline: eleven app-side files are uncovered, and the current repo `pyright` gate already fails in `src/sattlint/config.py` with `reportPrivateUsage` errors.
- [x] (2026-05-18 15:10Z) Capture the strict-mode error pattern for the uncovered startup helpers: the full-strict audit reports repeated `reportUnnecessaryCast` diagnostics in `src/sattlint/_app_startup.py` and `src/sattlint/_app_startup_docs_graphics.py`.
- [x] (2026-05-18 15:45Z) Resolve the existing strict-listed blocker in `src/sattlint/config.py` without changing config behavior by replacing private helper reach-through with public compatibility aliases and tightening config-shape narrowing in `config_validation.py` and `config_io.py`.
- [x] (2026-05-18 15:45Z) Make the eleven uncovered app and config files strict-clean by removing redundant startup-helper casts and tightening config helper typing until the app/config strict temp `pyright` project reported zero errors.
- [x] (2026-05-18 15:45Z) Repair the focused owner-test regression uncovered during validation: `src/sattlint/app_analysis.py` now uses the public `engine.is_within_directory` helper instead of the removed private `_is_within_directory` name.
- [x] (2026-05-18 15:45Z) Add the newly clean uncovered files to `tool.pyright.strict` in `pyproject.toml` and update the matching approval record in `.github/approvals/ratchet-rebaseline-2026-05-18.md`.
- [x] (2026-05-18 15:45Z) Run focused app and config validation, touched-file Ruff, touched-file Pyright, and the protected-path ratchet-policy tests for the slice.

## Surprises & Discoveries

- Observation: this slice contains both uncovered inventory and an already strict-listed blocker.
  Evidence: `src/sattlint/config.py` already fails the repo `pyright` gate, while the app-side helper files are missing from the strict list entirely.
- Observation: the startup helpers are likely blocked more by redundant narrowing than by missing types.
  Evidence: the full-strict audit reports repeated `reportUnnecessaryCast` diagnostics in `_app_startup.py` and `_app_startup_docs_graphics.py`.
- Observation: config validation reaches into private helpers today.
  Evidence: the repo `pyright` gate currently reports `reportPrivateUsage` on `_configured_targets`, `_normalize_documentation_rule_keys`, and `_validation_errors_by_key`.
- Observation: the focused app/config owner suite also exposed a stale compatibility seam outside the original strict list.
  Evidence: `tests/test_app_analysis.py::test_run_variable_analysis_runs_all_analyzed_targets` failed with `AttributeError: module 'sattlint.engine' has no attribute '_is_within_directory'` until `src/sattlint/app_analysis.py` switched to the existing public `engine.is_within_directory` helper.

## Decision Log

- Decision: keep app or menu helpers and config cleanup in one slice.
  Rationale: the startup and menu surfaces consume the config helpers directly, so strict typing across this boundary is easier to resolve together than in separate overlapping plans.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: resolve the existing `config.py` strict failure before promoting uncovered app files.
  Rationale: the app-side strict-promotion work is incomplete if the currently strict-listed config module still fails.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: keep interactive behavior stable and avoid menu redesign.
  Rationale: this is a typing-promotion slice, not a UX rewrite.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)
- Decision: repair the focused pytest regression in `src/sattlint/app_analysis.py` inside this slice instead of restoring another private engine alias.
  Rationale: the owner test failure was on the app-analysis seam itself, and the public replacement helper already existed in `src/sattlint/engine.py`, so the smallest durable fix was to repoint the caller.
  Date/Author: 2026-05-18 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This slice is complete. `src/sattlint/config.py` no longer fails strict `pyright`, the eleven uncovered app/config files now sit in `tool.pyright.strict`, and the focused owner tests, touched-file `pyright`, touched-file Ruff, and protected-path ratchet tests all pass.

The work stayed behavior-preserving. Config validation now exposes public compatibility helpers instead of reaching through private names, config I/O and validation narrow raw config objects explicitly for strict mode, the startup/doc or graphics wrappers dropped redundant casts, and the focused owner-test regression in `src/sattlint/app_analysis.py` was resolved by switching to the public engine helper that already replaced the removed private name.

## Context and Orientation

The owned files are:

- `src/sattlint/config.py`
- `src/sattlint/_app_analysis_loading.py`
- `src/sattlint/_app_analysis_menus.py`
- `src/sattlint/_app_graphics_menus.py`
- `src/sattlint/_app_graphics_reports.py`
- `src/sattlint/_app_startup.py`
- `src/sattlint/_app_startup_docs_graphics.py`
- `src/sattlint/_app_startup_from_app.py`
- `src/sattlint/_config_self_check.py`
- `src/sattlint/config_io.py`
- `src/sattlint/config_validation.py`
- `src/sattlint/types.py`

`src/sattlint/config.py` is already in `tool.pyright.strict` and currently fails the repo `pyright` gate. The remaining eleven files are inside the strict roots but are not yet represented in `tool.pyright.strict` or the debt allowlist.

The main owner tests for this slice are:

- `tests/test_app_analysis.py`
- `tests/test_app_analysis_project_cache.py`
- `tests/test_app_menus.py`
- `tests/test_app_menu_helpers.py`
- `tests/test_app_graphics_prompts.py`
- `tests/test_app_config_validation.py`
- `tests/test_app_support_helpers.py`
- `tests/test_app_cli_commands.py`
- `tests/test_app_docgen.py`

This plan ends with a protected-path edit in `pyproject.toml`, which requires a matching approval record under `.github/approvals/ratchet-rebaseline-*.md`.

## Plan of Work

Start with `src/sattlint/config.py`, `src/sattlint/_config_self_check.py`, `src/sattlint/config_io.py`, `src/sattlint/config_validation.py`, and `src/sattlint/types.py`. Clean up private-helper exposure and any config-shape typing issues first so the app helpers consume a stable typed config boundary.

Then move to the startup, analysis, and graphics helpers. Remove unnecessary casts, add precise local annotations where the intent is already obvious, and avoid changing prompts, menu numbering, or startup behavior.

Once the files are locally strict-clean, update `pyproject.toml` to add the uncovered files to `tool.pyright.strict`, add the approval record, and rerun the focused app or config tests plus touched-file lint and type checks.

## Concrete Steps

Run all commands from the repository root.

Inspect the slice before editing:

    rg -n "cast\(|_configured_targets|_normalize_documentation_rule_keys|_validation_errors_by_key|def |class " src/sattlint/config.py src/sattlint/_config_self_check.py src/sattlint/config_io.py src/sattlint/config_validation.py src/sattlint/types.py src/sattlint/_app_analysis_loading.py src/sattlint/_app_analysis_menus.py src/sattlint/_app_graphics_menus.py src/sattlint/_app_graphics_reports.py src/sattlint/_app_startup.py src/sattlint/_app_startup_docs_graphics.py src/sattlint/_app_startup_from_app.py

First focused proof after the first substantive edit:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_app_config_validation.py tests/test_app_analysis.py tests/test_app_analysis_project_cache.py tests/test_app_menus.py tests/test_app_menu_helpers.py tests/test_app_graphics_prompts.py tests/test_app_support_helpers.py tests/test_app_cli_commands.py tests/test_app_docgen.py -x -q --tb=short

Touched-file type and lint proof:

    bash scripts/run_repo_python.sh -m pyright src/sattlint/config.py src/sattlint/_config_self_check.py src/sattlint/config_io.py src/sattlint/config_validation.py src/sattlint/types.py src/sattlint/_app_analysis_loading.py src/sattlint/_app_analysis_menus.py src/sattlint/_app_graphics_menus.py src/sattlint/_app_graphics_reports.py src/sattlint/_app_startup.py src/sattlint/_app_startup_docs_graphics.py src/sattlint/_app_startup_from_app.py
    bash scripts/run_repo_python.sh -m ruff check src/sattlint/config.py src/sattlint/_config_self_check.py src/sattlint/config_io.py src/sattlint/config_validation.py src/sattlint/types.py src/sattlint/_app_analysis_loading.py src/sattlint/_app_analysis_menus.py src/sattlint/_app_graphics_menus.py src/sattlint/_app_graphics_reports.py src/sattlint/_app_startup.py src/sattlint/_app_startup_docs_graphics.py src/sattlint/_app_startup_from_app.py

Protected-path closeout proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short

## Validation and Acceptance

This plan is complete only when the existing `config.py` strict failure is resolved, the eleven uncovered app or config files are strict-clean and added to `tool.pyright.strict`, the focused app and config tests pass, and the approval record exists in the same change as the `pyproject.toml` update.

Acceptance is behavior-focused. Startup flow, menu behavior, graphics prompts, analysis loading, and config validation behavior must stay stable from the test perspective after the typing cleanup.

## Idempotence and Recovery

The cleanup is safe to repeat. If one cast removal or helper exposure change changes behavior, revert that local adjustment and retry with narrower typing rather than a larger API rewrite.

Do not touch `pyproject.toml` until every owned file is already strict-clean locally. The protected-path step should be the bookkeeping closeout, not part of debugging the code.

## Artifacts and Notes

- Original strict blocker: narrow `pyright` on `src/sattlint/config.py` and `src/sattlint/config_validation.py` reported `reportPrivateUsage` on `_configured_targets`, `_normalize_documentation_rule_keys`, and `_validation_errors_by_key` in `src/sattlint/config.py`.
- Focused owner-suite summary: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_app_config_validation.py tests/test_app_analysis.py tests/test_app_analysis_project_cache.py tests/test_app_menus.py tests/test_app_menu_helpers.py tests/test_app_graphics_prompts.py tests/test_app_support_helpers.py tests/test_app_cli_commands.py tests/test_app_docgen.py -x -q --tb=short` passed with `173 passed` after the app-analysis helper fix.
- Final touched-file `pyright` output: `bash scripts/run_repo_python.sh -m pyright src/sattlint/config.py src/sattlint/_config_self_check.py src/sattlint/config_io.py src/sattlint/config_validation.py src/sattlint/types.py src/sattlint/_app_analysis_loading.py src/sattlint/_app_analysis_menus.py src/sattlint/_app_graphics_menus.py src/sattlint/_app_graphics_reports.py src/sattlint/_app_startup.py src/sattlint/_app_startup_docs_graphics.py src/sattlint/_app_startup_from_app.py src/sattlint/app_analysis.py` reported `0 errors, 0 warnings, 0 informations`.
- Protected-path proof: `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_ratchet_policy.py tests/test_ratchet_policy_typing.py -x -q --tb=short` passed with `23 passed`.
- Approval record path used for the strict-list update: `.github/approvals/ratchet-rebaseline-2026-05-18.md`.

## Interfaces and Dependencies

This slice depends on the existing app and config entry surfaces in `src/sattlint/`. Preserve CLI and menu behavior, prompt flow, and config parsing semantics. The goal is strict-safe typing of the existing control surface, not a behavior rewrite.

The only protected-path dependency is `pyproject.toml` plus the matching approval record. No new debt entries are allowed.
