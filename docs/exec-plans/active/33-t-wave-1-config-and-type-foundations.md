# T-Wave-1 Config And Type Foundations

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan closes T-005 and T-008 together. After this work lands, SattLint will surface unresolved `analyzed_programs_and_libraries` entries as structured validation errors before analysis or documentation begins, and the repository will have one central semantic-type module so high-signal interfaces stop using ambiguous bare `str` annotations for project paths, target names, and variable identities. The observable proof is that `validate-config` returns a nonzero exit for missing configured targets, interactive startup shows the same validation messages before AST cache warmup, and Pyright accepts the new alias-bearing interfaces without runtime behavior changes.

## Progress

- [x] (2026-05-13) Create the ExecPlan and confirm `src/sattlint/config.py` already validates raw TOML shape and already has `_self_check_targets`, but missing-target checks are still outside `ConfigValidationResult`, `src/sattlint/app.py` still treats them as interactive console output only, and `src/sattlint/types.py` does not exist.
- [ ] Add `src/sattlint/types.py` with a small, documented alias set and migrate a narrow set of central interfaces.
- [ ] Promote analyzed-target existence checks into merged-config validation that reuses existing `target_exists` logic.
- [ ] Reuse the shared validation in `validate-config` and the interactive startup flow before AST cache or analysis work begins.
- [ ] Add focused tests and run narrow pytest, Ruff, and Pyright proof.

## Surprises & Discoveries

Observation: the repo already performs an interactive target existence check, but only as console output.
Evidence: `src/sattlint/config.py` has `_self_check_targets`, and `src/sattlint/app.py` already calls `self_check(cfg)` before the menu loop.

Observation: raw `validate_config` cannot safely check target existence because it runs before defaults are merged.
Evidence: `src/sattlint/config.py` calls `validate_config(cfg)` on the raw TOML payload inside `load_config`, but `target_exists` depends on merged `program_dir`, `ABB_lib_dir`, `other_lib_dirs`, and `mode` values.

Observation: a repo-wide `NewType` migration would create unnecessary churn.
Evidence: there is no existing semantic alias module, and the current debt is discoverability-oriented rather than a runtime correctness problem.

## Decision Log

Decision: keep T-005 and T-008 in one plan.
Rationale: both items are foundation work inside `src/sattlint/`, and both benefit from touching the same small set of config and user-facing interface files in one slice.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: introduce semantic aliases incrementally instead of rewriting every `str` annotation in the repository.
Rationale: the goal is discoverability, not a mass refactor. A small alias module plus a narrow set of public or diagnostic-facing consumers gives immediate value without unnecessary churn.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

Decision: formalize target existence checks as a second validation phase that runs on merged config.
Rationale: path and target existence depend on defaults and normalized directories, so that logic should not live in the raw TOML-shape validator.
Date/Author: 2026-05-13 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Planning baseline only. The current repository already has informal self-check output, but it does not yet produce structured validation errors for missing analyzed targets, and it still lacks a semantic alias module.

## Context and Orientation

The controlling config code lives in `src/sattlint/config.py`. `validate_config` currently returns `ConfigValidationResult` for key-shape and mode errors only. `load_config` merges defaults after that validation. `target_exists` and `_self_check_targets` already know how to resolve configured program and library names across `program_dir`, `ABB_lib_dir`, and `other_lib_dirs`, but they surface their result only through console printing.

The user-visible entry points live in `src/sattlint/app.py` and `src/sattlint/app_cli_commands.py`. `app.main` calls `self_check(cfg)` before the interactive menu loop and asks whether to continue on failure. `run_validate_config_command` returns a process exit code based on the boolean result from `self_check`. That makes T-005 a refactor of validation ownership, not a feature from scratch.

T-008 has no current owner file. `src/sattlint/types.py` does not exist, so the first step is to create it. Keep the alias set deliberately small and tied to current user-facing seams. `ProjectPath`, `TargetName`, and `VariableId` are enough for the first slice. Consume them only in files that already own config or variable-diagnostic behavior, such as `src/sattlint/config.py`, `src/sattlint/app.py`, `src/sattlint/app_cli_commands.py`, and one variable-facing surface such as `src/sattlint/core/diagnostics.py`.

## Plan of Work

Start by adding `src/sattlint/types.py`. Define `ProjectPath`, `TargetName`, and `VariableId` as `typing.NewType` wrappers over `str`, and give each alias a short docstring that explains what concept it names in this repository. Do not add aliases for every primitive in the codebase.

Next, refactor config validation into two phases inside `src/sattlint/config.py`. Keep `validate_config` responsible for raw TOML shape and top-level key validation. Add a second helper that runs after defaults are merged and reports missing configured directories or unresolved `analyzed_programs_and_libraries` entries using the same structured error shape. Reuse existing `target_exists` logic instead of duplicating path resolution.

Then update `src/sattlint/app_cli_commands.py` and `src/sattlint/app.py` to use the shared validation result instead of ad hoc printing only. The validate-config command must return a nonzero exit when configured targets cannot be resolved. Interactive startup should keep its current graceful behavior: show the same validation messages before AST cache warmup or analysis, but continue to allow the user to stay in the menu if they explicitly confirm.

After the validation path is stable, apply the new aliases to the touched config surfaces and one variable-facing diagnostic surface. The first slice does not need a repo-wide alias migration. The acceptance bar is that the aliases are real, documented, imported from one central module, and used in the highest-signal interfaces touched by this plan.

## Concrete Steps

Run all commands from the repository root.

Inspect the current config-validation and startup seams before editing code:

    rg -n "validate_config|load_config|target_exists|_self_check_targets|self_check" src/sattlint/config.py src/sattlint/app.py src/sattlint/app_cli_commands.py

After implementing the shared merged-config validation and the first semantic aliases, run the narrow validation first:

    python scripts/run_repo_python.py -m pytest --no-cov tests/test_app_config_validation.py tests/test_app_cli_commands.py -x -q --tb=short

Run touched-file quality gates after the focused tests pass:

    python scripts/run_repo_python.py -m ruff check src/sattlint/types.py src/sattlint/config.py src/sattlint/app.py src/sattlint/app_cli_commands.py src/sattlint/core/diagnostics.py
    python scripts/run_repo_python.py -m pyright src/sattlint/types.py src/sattlint/config.py src/sattlint/app.py src/sattlint/app_cli_commands.py src/sattlint/core/diagnostics.py

## Validation and Acceptance

Acceptance requires two user-visible outcomes. First, missing configured targets must appear in the validate-config path and in the interactive startup self-check before analysis or documentation work begins. Second, the repository must have one central alias module and a small set of real consumers so `ProjectPath`, `TargetName`, and `VariableId` are discoverable in code instead of existing only as an unused types file.

## Idempotence and Recovery

This plan is safe to execute incrementally. Add the alias module first, then land the merged-config validation helper, then wire the CLI and startup surfaces. If the stricter validation causes noisy startup behavior, keep the menu prompt behavior and only block the validate-config command until the interaction is refined. Do not delete the existing `self_check` flow until the new structured path is proven by tests.

## Artifacts and Notes

Record one failing and then passing validate-config example with a missing target name, plus one Pyright excerpt that shows the alias-bearing signatures type-check cleanly. Keep the artifact short; the important proof is the changed exit behavior and the existence of one central alias module.

## Interfaces and Dependencies

The implementation surface is `src/sattlint/config.py`, `src/sattlint/app.py`, `src/sattlint/app_cli_commands.py`, and the new `src/sattlint/types.py`. The validation result format should stay compatible with the existing `ConfigValidationResult` structure so callers and tests do not need a parallel error format. Use standard-library `typing.NewType`; do not add a new dependency for semantic aliases.
