# T-Wave-9 Analyzer Architecture Drift Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns a one-off architecture-drift review into a repo-owned execution path that prevents the analyzer package from continuing to fragment. After this work lands, maintainers should be able to add or extend analyzers without guessing about naming, registration, import style, or helper reuse. The visible proof is concrete: the analyzer package will reject new naming drift through focused architecture tests, registry-facing analyzer keys will follow one canonical kebab-case style, helper-only modules will be marked private, and the highest-value duplicated traversal and origin helpers will move to shared seams instead of being copied again.

The result must be observable from the repository root. A maintainer should be able to run focused pytest coverage for analyzer architecture, see that new drift is rejected automatically, and then run the existing analyzer suites without discovering that registry names, import paths, or helper ownership changed silently. This is not a motivational cleanup plan. It is a structural hardening plan whose acceptance is that the next AI or human edit has less room to fork conventions by accident.

## Progress

- [x] (2026-06-01) Created this ExecPlan from the 2026-06-01 analyzer-architecture drift review and captured the initial baseline in the plan itself.
- [x] (2026-06-01) Verified the main owner surfaces: `src/sattlint/analyzers/_registry_spec_templates.py` contains mixed kebab-case and snake_case analyzer keys, `src/sattlint/analyzers/registry.py` mixes absolute and relative imports, and `src/sattlint/analyzers/variable_usage_reporting.py` exposes two public `analyze_*` helpers that are not registry-backed analyzers.
- [x] (2026-06-01) Verified that the proposed private-module rename is repo-wide rather than purely internal: `src/sattlint/analyzers/variables.py`, `src/sattlint/analyzers/_variables_execution.py`, and multiple tests import `reset_contamination`, `validators`, `usage_tracker`, `variable_traversal`, or `variable_issue_collection` directly.
- [x] (2026-06-01) Verified that the current test baseline already encodes legacy underscore analyzer keys in `tests/_analyzers_suites_part3.py`, so naming enforcement must be staged instead of introduced as an immediate all-or-nothing break.
- [x] (2026-06-01) Added analyzer-specific drift-prevention guidance in `.github/instructions/analyzer-architecture.instructions.md` and kept `AGENTS.md` to one short routing pointer.
- [x] (2026-06-01) Added `tests/test_analyzer_architecture.py` to ratchet registry key style, non-registry `analyze_*` exceptions, and analyzer-package import-style consistency.
- [x] (2026-06-01) Normalized the canonical registry-facing analyzer keys to kebab-case, kept legacy underscore spellings selectable through centralized alias normalization, and renamed the app-facing reporting helpers to `report_*` names.
- [x] (2026-06-01) Renamed the clearly internal variable helper modules to underscore-prefixed paths and updated source plus test imports in one mechanical slice.
- [x] (2026-06-01) Added `src/sattlint/analyzers/_walk_utils.py` and expanded `src/sattlint/analyzers/variable_utils.py` with `matches_root_origin(...)`, then migrated the first low-risk traversal and origin callers to those shared seams.
- [x] (2026-06-01) Reassessed `symbolic_lite`, `_REGISTRY_MONKEYPATCH_SURFACE`, and the `_report_defaults` overlap after the structural slices stabilized; no deletion was warranted because each seam still has active registry, artifact, or helper-report callers.
- [x] (2026-06-01) Finished with focused pytest proof for each slice plus touched-file Ruff and source-slice Pyright.

## Surprises & Discoveries

Observation: the two public `analyze_*` functions in `src/sattlint/analyzers/variable_usage_reporting.py` are not dead registry omissions; they are app-facing reporting helpers used directly by `src/sattlint/app_analysis.py`.
Evidence: `src/sattlint/app_analysis.py` calls `analyze_datatype_usage(...)` and imports `analyze_module_localvar_fields(...)` directly, while `src/sattlint/analyzers/registry.py` does not register either function.

Observation: the private-module rename cannot be treated as an internal-only cleanup because tests import some of those helper modules directly.
Evidence: `tests/test_reset_contamination_ratchet.py`, `tests/test_reset_contamination_ratchet_helpers.py`, `tests/test_variables_helper_coverage.py`, and `tests/_analyzers_variables_test_support.py` import `reset_contamination` or `variable_issue_collection` as modules rather than only through public wrappers.

Observation: the strongest first guardrail is not a blanket kebab-case test by itself, because the current suite still expects legacy underscore keys.
Evidence: `tests/_analyzers_suites_part3.py` currently monkeypatches and asserts keys such as `interface_contracts`, `signal_lifecycle`, `loop_stability`, `fault_handling`, `numeric_constraints`, `data_dependency`, `config_drift`, `resource_usage`, `scan_concurrency`, and `state_inference`.

Observation: `symbolic_lite` is orphaned in the analyzer pipeline but not absent from the repository.
Evidence: `src/sattlint/analyzers/_registry_delivery_data.py` includes a `symbolic_lite` delivery template, `src/sattlint/analyzers/symbolic_lite.py` defines exported helpers, `src/sattlint/devtools/artifact_registry.py` still names `sattlint.symbolic_lite`, and earlier completed plans plus tests already exercise helper behavior.

Observation: a shared root-origin helper already exists, but some analyzer paths still bypass it or wrap it inconsistently.
Evidence: `src/sattlint/analyzers/variable_utils.py` exports `same_origin_file_stem(...)`, and some analyzer modules use it directly, while other code paths still define their own `is_from_root_origin(...)` or `_same_origin_file_stem(...)` logic.

Observation: the first safe traversal extraction was smaller than the original duplication inventory because only a subset of walkers could share a read-only path-yielding contract without dragging along analyzer-owned env state.
Evidence: `src/sattlint/analyzers/variable_usage_reporting.py` and `src/sattlint/analyzers/_sfc_module_walk.py` migrated cleanly to `src/sattlint/analyzers/_walk_utils.py`, while env-carrying walkers such as `src/sattlint/analyzers/_wave2_support.py` still need a different seam if they are consolidated later.

## Decision Log

Decision: stage enforcement before larger refactors.
Rationale: if naming, import-style, and entry-point drift are not enforced first, any cleanup can regress immediately in a later AI-generated edit. The first slice must make future drift fail fast.
Date/Author: 2026-06-01 / Copilot (GPT-5.4)

Decision: treat the two `variable_usage_reporting.py` public `analyze_*` functions as reporting helpers, not missing analyzers.
Rationale: they return formatted strings for app workflows rather than analyzer `Issue` collections, and they are invoked directly by `src/sattlint/app_analysis.py` instead of through the shared analyzer registry. Renaming them to `report_*` or `debug_*` makes the registry-completeness rule meaningful.
Date/Author: 2026-06-01 / Copilot (GPT-5.4)

Decision: use compatibility aliases when migrating legacy underscore analyzer keys to kebab-case.
Rationale: the current registry tests, CLI-facing expectations, and likely user configs already know the underscore spellings. The migration should ratchet toward kebab-case without forcing one large break across config, tests, and registry wiring in the same step.
Date/Author: 2026-06-01 / Copilot (GPT-5.4)

Decision: keep analyzer-specific pattern guidance in a scoped instruction file and only add a short routing pointer to `AGENTS.md`.
Rationale: repository guidance already says AGENTS should stay small and scoped instructions should hold subsystem detail. This plan needs discoverability, not another oversized global rule block.
Date/Author: 2026-06-01 / Copilot (GPT-5.4)

Decision: defer repo-wide `.casefold()` and empty-list helper consolidation until analyzer ownership and traversal seams are stable.
Rationale: those cleanups are real, but they are broader than the analyzer package and would widen the slice before the highest-signal architecture drift is contained.
Date/Author: 2026-06-01 / Copilot (GPT-5.4)

Decision: remove apparently dead analyzer metadata only after proving that no active helper tests, artifact registry surfaces, or preserved compatibility hooks still depend on it.
Rationale: the initial drift report correctly identified orphan-like seams, but `symbolic_lite` and `_REGISTRY_MONKEYPATCH_SURFACE` already have repository-local test or compatibility history. Premature deletion would turn an architecture cleanup into a behavioral break.
Date/Author: 2026-06-01 / Copilot (GPT-5.4)

Decision: stop the first traversal extraction at the read-only walkers that already agree on a node-plus-path contract.
Rationale: reworking env-carrying walkers in the same slice would have turned a structural hardening plan into a broader behavior refactor. `variable_usage_reporting` and `_sfc_module_walk` were enough to establish the shared seam without forcing unrelated analyzers through an unproven abstraction.
Date/Author: 2026-06-01 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The analyzer package now enforces its own high-signal structure instead of relying on convention memory. The canonical registry-facing analyzer keys are kebab-case, legacy underscore spellings still resolve through one centralized alias seam, reporting-only variable usage helpers no longer look like registry analyzers, and the internal variable helper modules now advertise their private status directly through underscore-prefixed filenames.

The architectural ratchet is observable from the repository root. `tests/test_analyzer_architecture.py` now fails on new underscore registry keys, on new non-registry `analyze_*` functions unless they are explicitly exempted, and on mixed absolute/relative analyzer-package imports. The first shared traversal seam lives in `src/sattlint/analyzers/_walk_utils.py`, and the first shared analyzer-owned origin seam now lives in `src/sattlint/analyzers/variable_utils.py` as `matches_root_origin(...)`.

The deferred cleanup review did not justify deletion. `symbolic_lite` still has delivery metadata and artifact-registry references, `_REGISTRY_MONKEYPATCH_SURFACE` still protects test and helper monkeypatch seams, and `_report_defaults` still has active analyzer callers. The main lesson from execution was scope control: the plan succeeded because it hardened structure first and only extracted the smallest shared seams that could be validated with existing owner suites.

## Context and Orientation

The analyzer package lives under `src/sattlint/analyzers/`. In this repository, an `analyzer` is a callable exposed through the shared registry so CLI or reporting surfaces can select it by key. The registry owner file is `src/sattlint/analyzers/registry.py`. It imports public analyzer entry points, exposes default analyzer subsets, and builds analyzer metadata from `src/sattlint/analyzers/_registry_specs.py`. The spec-template source of truth is `src/sattlint/analyzers/_registry_spec_templates.py`, where each `AnalyzerSpecTemplate` row defines the analyzer key, description, and registry attribute name. A `registry key` is the string a user or internal caller selects, such as `variables` or `picture-display-paths`.

The variables analyzer has grown into a particularly important owner surface for this plan. `src/sattlint/analyzers/variables.py` is the public analyzer entry point. It already delegates many responsibilities into sibling helper modules such as `src/sattlint/analyzers/_variables_submodules.py`, `src/sattlint/analyzers/_variables_execution.py`, `src/sattlint/analyzers/_variables_access.py`, `src/sattlint/analyzers/_usage_tracker.py`, `src/sattlint/analyzers/_validators.py`, `src/sattlint/analyzers/_variable_issue_collection.py`, and `src/sattlint/analyzers/_variable_traversal.py`. Those helpers are intentionally private now, which makes the package boundary more legible than the pre-plan public-looking module names.

`src/sattlint/analyzers/variable_usage_reporting.py` is related but different. It does not currently behave like a shared analyzer registry surface. Instead, it contains reporting helpers that build human-readable strings for variable usage inspection workflows in `src/sattlint/app_analysis.py`. This distinction matters because the architecture test for public `analyze_*` entry points must not force every reporting helper into the analyzer registry by accident.

The current drift shows up in four places. First, analyzer registry keys use both kebab-case and snake_case in `src/sattlint/analyzers/_registry_spec_templates.py`. In this plan, `kebab-case` means lowercase words separated by hyphens, such as `picture-display-paths`. `snake_case` means lowercase words separated by underscores, such as `signal_lifecycle`. Second, `src/sattlint/analyzers/registry.py` mixes absolute imports like `from sattlint.analyzers.alarm_integrity import ...` with relative imports like `from .comment_code import ...` in the same file. Third, module-walking and root-origin helpers are duplicated across many analyzer helpers instead of being reused through one shared seam. Fourth, several helper modules look public even though the repository only imports them internally.

The nearby tests already provide a good enforcement seam. `tests/_analyzers_suites_part3.py` exercises registry catalog behavior, key exposure, and analyzer-metadata branches. `tests/test_analyzers_suites.py` re-exports that suite. `tests/test_analyzers_variables.py`, `tests/test_variables_helper_coverage.py`, and `tests/test_variables_access_and_contract_helpers.py` cover the variable-analysis helper surfaces. `tests/test_reset_contamination_ratchet.py` and `tests/test_reset_contamination_ratchet_helpers.py` cover the reset-contamination helper module directly. This plan should add one new focused architecture suite rather than overloading those files with unrelated structural assertions.

In this plan, an `architecture test` means a focused test that protects structural conventions rather than domain semantics. Examples include “all new analyzer keys must be kebab-case” or “a file may not mix absolute and relative imports to the same package.” A `compatibility alias` means a temporary way to accept an old spelling or import path while migrating callers to the new canonical one. A `module-walk seam` means one shared helper that traverses nested module instances and concrete child modules so later analyzers reuse one traversal contract instead of inventing another.

## Plan of Work

Start by adding the smallest enforcement layer that can stop further drift. Add one analyzer-scoped instruction file under `.github/instructions/`, for example `.github/instructions/analyzer-architecture.instructions.md`, that applies to `src/sattlint/analyzers/**` and `tests/**` where relevant. That file should name the canonical registry-key style, the requirement that public analyzer entry points be registry-backed `analyze_*` functions, the rule against mixing absolute and relative analyzer-package imports in the same file, and the requirement to search for existing traversal or origin helpers before adding new ones. Then add one short pointer in `AGENTS.md` that directs analyzer work toward the scoped instruction file and the canonical helper seams. Keep the AGENTS addition short because repo policy explicitly prefers scoped instructions over growing AGENTS into another large control surface.

Once the guidance exists, add a dedicated architecture test module, preferably `tests/test_analyzer_architecture.py`. The first test should protect registry-key normalization without forcing an immediate break. Define a temporary allowlist such as `LEGACY_UNDERSCORE_ANALYZER_KEYS` inside the test or in a small shared test helper, assert that every key from `default_spec_templates(...)` is either kebab-case or in that allowlist, and add an assertion that every allowed legacy key must still be explicitly listed. This creates a ratchet: no new underscore keys can appear, and the allowlist can shrink to zero as the migration lands. The second test should scan analyzer modules for public `analyze_*` functions and assert that each one is either imported into the registry or explicitly marked as a non-registry reporting helper. The cleanest implementation path is to rename the two reporting helpers in `src/sattlint/analyzers/variable_usage_reporting.py` before tightening the test. The third test should parse import statements under `src/sattlint/analyzers/` and fail when a file mixes analyzer-package absolute imports with sibling relative imports in the same module.

After the tests are in place, normalize naming and registry surfaces. In `src/sattlint/analyzers/_registry_spec_templates.py`, migrate the legacy underscore keys such as `interface_contracts`, `signal_lifecycle`, `loop_stability`, `fault_handling`, `numeric_constraints`, `data_dependency`, `config_drift`, `resource_usage`, `scan_concurrency`, and `state_inference` to kebab-case spellings. Update any dependent constants in `src/sattlint/analyzers/registry.py`, including default CLI keys and rule-alias metadata. Add compatibility handling so old underscore spellings still resolve for one transition period. The most conservative place for that aliasing is in registry lookup or spec-building code, because that keeps the canonical keys normalized while still accepting legacy selections. In the same slice, rename `analyze_datatype_usage(...)` and `analyze_module_localvar_fields(...)` in `src/sattlint/analyzers/variable_usage_reporting.py` to reporting-oriented names such as `report_datatype_usage(...)` and `report_module_localvar_fields(...)`, then update `src/sattlint/app_analysis.py` to call the new names.

Then make the internal helper boundary explicit. Rename `src/sattlint/analyzers/reset_contamination.py` to `src/sattlint/analyzers/_reset_contamination.py`, `usage_tracker.py` to `_usage_tracker.py`, `validators.py` to `_validators.py`, `variable_traversal.py` to `_variable_traversal.py`, and `variable_issue_collection.py` to `_variable_issue_collection.py`. Update imports in `src/sattlint/analyzers/variables.py`, `src/sattlint/analyzers/_variables_execution.py`, `src/sattlint/analyzers/_variables_contracts.py`, `src/sattlint/analyzers/_variables_analyzer_facade.py`, `src/sattlint/analyzers/_variables_facade_properties.py`, `src/sattlint/analyzers/_variables_status.py`, and any other touched analyzer helpers. Update test imports in the helper-coverage suites that currently import those modules directly. Because this repository is AI-only and the rename is deliberate, the tests should import the new underscore-prefixed paths directly rather than maintaining public re-export shims unless a real external compatibility requirement appears.

Only after the guardrails and rename slices are passing should the plan move into duplication reduction. Add one new shared traversal helper module such as `src/sattlint/analyzers/_walk_utils.py`. Keep the first extraction small and specific. The goal is not to replace every analyzer traversal in one sweep. Instead, define one reusable read-only traversal contract for nested `SingleModule`, `FrameModule`, and `ModuleTypeInstance` trees that yields the current node plus its resolved path. Then migrate the highest-duplication, lowest-risk walkers first, especially the simple tree searches used by reporting and variable helper code. In parallel, consolidate root-origin checks by expanding `src/sattlint/analyzers/variable_utils.py` into the one analyzer-owned origin helper seam. If some callers truly need library-aware origin comparison instead of file-stem-only comparison, add a second clearly named shared helper there instead of preserving several bespoke `is_from_root_origin(...)` copies.

Finish with the deferred orphan and overlap review. Re-check `src/sattlint/analyzers/symbolic_lite.py`, `src/sattlint/analyzers/_registry_delivery_data.py`, `src/sattlint/devtools/artifact_registry.py`, and `src/sattlint/analyzers/registry.py` after the earlier slices land. If `symbolic_lite` still has no supported analyzer or artifact owner, either retire its delivery metadata and update tests consistently, or document it as an intentional internal helper with matching naming and ownership. Apply the same evidence-first treatment to `_REGISTRY_MONKEYPATCH_SURFACE` and to the overlap between `framework.empty_issues()` and `src/sattlint/analyzers/_report_defaults.py`. Do not widen into repo-wide `.casefold()` rewrites until this analyzer-specific plan is complete.

## Concrete Steps

Run all commands from the repository root.

Begin by confirming the baseline drift and the current owner surfaces before editing:

    rg -n "interface_contracts|signal_lifecycle|loop_stability|fault_handling|numeric_constraints|data_dependency|config_drift|resource_usage|scan_concurrency|state_inference" src/sattlint/analyzers/_registry_spec_templates.py
    rg -n "^from sattlint\.analyzers\.|^from \." src/sattlint/analyzers/registry.py
    rg -n "def analyze_" src/sattlint/analyzers/*.py src/sattlint/analyzers/**/*.py
    rg -n "reset_contamination|usage_tracker|validators|variable_traversal|variable_issue_collection" src/sattlint/analyzers tests

Create the guidance and architecture test slice first. After adding the scoped instruction, the AGENTS pointer, and `tests/test_analyzer_architecture.py`, run the focused structural proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzer_architecture.py tests/test_analyzers_suites.py -x -q --tb=short

Expected behavior for that first slice:

    - the new architecture test file passes
    - the test fails if a new underscore analyzer key is added without being placed on the explicit legacy allowlist
    - the test fails if a new public `analyze_*` helper is added outside the registry without an explicit reporting-helper exception
    - the test fails if `src/sattlint/analyzers/registry.py` or another covered analyzer file mixes analyzer-package absolute and relative imports

Then implement the naming-normalization slice and rerun a narrow registry proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzer_architecture.py tests/test_analyzers_suites.py tests/test_cli.py -x -q --tb=short

After renaming the reporting helpers in `src/sattlint/analyzers/variable_usage_reporting.py` and updating `src/sattlint/app_analysis.py`, run the nearest variable-reporting proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_variables.py -k "library_target_report_shows_typedef_for_same_lib_different_file_moduletype or unused_summary_splits_moduletype_and_singlemodule_groups" -x -q --tb=short

After renaming the internal helper modules and updating imports, run the focused variable and reset-contamination suites:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_variables_helper_coverage.py tests/test_variables_access_and_contract_helpers.py tests/test_reset_contamination_ratchet.py tests/test_reset_contamination_ratchet_helpers.py -x -q --tb=short

When the shared traversal and origin helpers are extracted, rerun the same focused suites plus the broader variables analyzer owner suite:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_variables.py tests/test_variables_helper_coverage.py tests/test_reset_contamination_ratchet.py tests/test_reset_contamination_ratchet_helpers.py -x -q --tb=short

Finish every Python slice with touched-file lint and type checks. The exact file list will depend on the current slice, but the command shape must remain:

    bash scripts/run_repo_python.sh -m ruff check <touched python files>
    bash scripts/run_repo_python.sh -m pyright <touched python files>

## Validation and Acceptance

Acceptance for this plan is observable structural behavior, not only renamed files. After the first enforcement slice lands, adding a new analyzer key in snake_case must fail the architecture tests unless the key is deliberately added to the temporary legacy allowlist. Adding a new public `analyze_*` helper outside the registry must also fail unless the helper is explicitly classified as a reporting-only exception. Mixing analyzer-package absolute and relative imports in the same file must fail automatically.

Acceptance for the naming slice is that the canonical registry-facing spellings are kebab-case while legacy underscore spellings continue to resolve during the migration window. A maintainer should be able to run the focused registry and CLI tests and see that registry selection, catalog generation, and CLI exposure still work even after the canonical key spellings are normalized.

Acceptance for the helper-boundary slice is that the clearly internal helper modules are underscore-prefixed everywhere and all direct imports plus tests are updated to match. There should be no lingering imports of the old public helper-module paths inside `src/sattlint/analyzers/` or the directly affected test files.

Acceptance for the duplication-reduction slice is that at least one shared recursive module-walk seam and one shared analyzer-owned origin seam exist, and the migrated call sites use them without changing current analyzer behavior. The proof is focused pytest coverage for variables and reset-contamination helper flows plus touched-file Ruff and Pyright passing.

The plan is only complete when the repo can demonstrate all of the following from the repository root: the architecture suite passes, the nearest existing analyzer suites still pass, touched-file lint and type checks pass, and no new analyzer drift can be introduced without tripping focused structural tests.

## Idempotence and Recovery

This plan is safe to execute in small slices. The guidance and architecture tests are additive. If a naming or import-normalization step fails halfway, rerun the same focused pytest command after finishing the remaining imports or aliases; there is no destructive migration state outside the working tree.

Compatibility aliases are the main recovery tool for the key-migration slice. If a registry or CLI path still depends on a legacy underscore key, keep the alias in place and continue migrating the canonical spelling rather than reverting the whole naming normalization. Remove aliases only after the focused suites prove that the legacy spelling is no longer needed.

The private-module rename is mechanical but wide. If a test fails after renaming one helper module, search for the old module path in both `src/sattlint/analyzers/` and `tests/` and complete the rename before widening into behavior changes. Do not leave mixed old and new import paths in the tree.

The shared traversal extraction must stay incremental. If moving a caller to the new `_walk_utils.py` changes behavior, keep the shared helper and revert only that caller to its local traversal until the behavior mismatch is understood. The extraction is meant to ratchet duplication down, not to force every walker through one unproven abstraction in a single commit.

Do not remove `symbolic_lite`, `_REGISTRY_MONKEYPATCH_SURFACE`, or overlapping helper primitives on assumption alone. Treat deletion as the final step of a verified retirement path: search for callers, run focused tests, and then remove the seam only when no supported behavior depends on it.

## Artifacts and Notes

Baseline facts captured when this plan was created:

    - `src/sattlint/analyzers/_registry_spec_templates.py` currently mixes kebab-case and snake_case keys.
    - `src/sattlint/analyzers/registry.py` currently mixes `from sattlint.analyzers...` imports with `from .` imports.
    - `src/sattlint/analyzers/variable_usage_reporting.py` currently exports `analyze_datatype_usage(...)` and `analyze_module_localvar_fields(...)`, but those functions are used by `src/sattlint/app_analysis.py` rather than by the shared analyzer registry.
    - `src/sattlint/analyzers/variables.py` currently imports `usage_tracker`, `validators`, `variable_issue_collection`, and `variable_traversal` through public-looking module names.
    - tests already import `reset_contamination` and `variable_issue_collection` as modules, so the private-module rename must update tests rather than treating the change as invisible.

Key files the executor will touch during this plan:

    - `AGENTS.md`
    - `.github/instructions/analyzer-architecture.instructions.md`
    - `src/sattlint/analyzers/_registry_spec_templates.py`
    - `src/sattlint/analyzers/registry.py`
    - `src/sattlint/analyzers/_registry_specs.py`
    - `src/sattlint/analyzers/variable_usage_reporting.py`
    - `src/sattlint/app_analysis.py`
    - `src/sattlint/analyzers/variables.py`
    - `src/sattlint/analyzers/_variables_execution.py`
    - `src/sattlint/analyzers/_variables_contracts.py`
    - `src/sattlint/analyzers/_variables_analyzer_facade.py`
    - `src/sattlint/analyzers/_variables_facade_properties.py`
    - `src/sattlint/analyzers/_variables_status.py`
    - `src/sattlint/analyzers/variable_utils.py`
    - `src/sattlint/analyzers/_walk_utils.py`
    - `tests/test_analyzer_architecture.py`
    - the nearest existing variable and reset-contamination helper suites under `tests/`

Validation executed during implementation:

    - `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzer_architecture.py tests/test_analyzers_suites.py tests/test_cli.py::test_run_cli_analyze_passes_opt_in_state_inference_key tests/test_app_analysis.py::test_run_checks_runs_selected_non_default_cli_exposed_analyzer tests/test_app_analysis.py::test_run_checks_updates_live_status_for_active_analyzer tests/test_app_analysis.py::test_run_checks_uses_cached_report_when_available tests/test_app_analysis.py::test_run_checks_rebuilds_report_cache_when_cached_payload_is_stale tests/test_app_analysis.py::test_run_checks_handles_keyboard_interrupt_and_pauses tests/test_app_analysis.py::test_run_checks_accepts_legacy_underscore_analyzer_key tests/analyzers/test_data_dependency.py tests/analyzers/test_signal_lifecycle.py tests/analyzers/test_loop_stability.py tests/analyzers/test_fault_handling.py tests/analyzers/test_numeric_constraints.py tests/analyzers/test_resource_usage.py tests/analyzers/test_scan_concurrency.py tests/analyzers/test_interface_contracts.py tests/analyzers/test_dataflow.py tests/analyzers/test_sattline_semantics_tail.py tests/test_docgen.py -x -q --tb=short`
    - `bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_variables_helper_coverage.py tests/test_variables_access_and_contract_helpers.py tests/test_reset_contamination_ratchet.py tests/test_reset_contamination_ratchet_helpers.py tests/test_reset_contamination_latching_helpers.py tests/analyzers/test_reset_contamination.py -x -q --tb=short`
    - `bash scripts/run_repo_python.sh -m pytest --no-cov tests/analyzers/test_variable_usage_reporting.py tests/analyzers/test_sfc.py::test_iter_sfc_modulecodes_covers_root_nested_modules_and_typedefs tests/devtools/test_tracing.py::test_iter_sfc_modulecodes_yields_root_and_nested tests/devtools/test_tracing.py::test_iter_sfc_modulecodes_yields_moduletype_defs tests/test_variables_access_and_contract_helpers.py tests/test_reset_contamination_ratchet.py -x -q --tb=short`
    - `bash scripts/run_repo_python.sh -m ruff check <touched plan-66 python files>`
    - `bash scripts/run_repo_python.sh -m pyright <touched plan-66 source files>`

Expected steady-state conventions after implementation:

    - registry-facing analyzer keys are kebab-case
    - public analyzer entry points use `analyze_*` and are registry-backed
    - reporting-only helpers use names that do not imply registry-backed analyzers
    - internal-only analyzer helper modules are underscore-prefixed
    - analyzer-package imports do not mix absolute and relative styles within the same file
    - new recursive module-walk helpers are added only through the shared analyzer walk seam unless a test-backed exception is documented

## Interfaces and Dependencies

The registry and analyzer metadata interface remains centered on `src/sattlint/analyzers/registry.py`, `src/sattlint/analyzers/_registry_specs.py`, and `src/sattlint/analyzers/_registry_spec_templates.py`. By the end of this plan, those files must expose one canonical analyzer key spelling per analyzer, plus a deliberate compatibility path for legacy underscore spellings during migration. The registry must remain the only package-level owner for which public analyzer entry points are selectable.

The analyzer-owned origin helper seam remains `src/sattlint/analyzers/variable_utils.py`. If the current `same_origin_file_stem(origin_file: str | None, root_origin: str | None) -> bool` contract is insufficient for all surviving callers, extend that file with one second clearly named helper rather than preserving many file-local `is_from_root_origin(...)` copies. The goal is one owner file for analyzer-origin comparisons, not several synonymous helpers.

The new traversal interface should live in `src/sattlint/analyzers/_walk_utils.py`. The exact function names may change during implementation, but the module must provide one shared read-only traversal contract for nested module trees so callers do not each rebuild the same path-extension and submodule-resolution logic. Keep the interface narrow enough that the first migrated callers are easy to verify with existing tests.

The reporting-helper rename must leave `src/sattlint/app_analysis.py` with direct access to the same human-readable variable-usage reports, but those helpers should no longer look like registry-backed analyzers. That means the final module should export reporting-oriented names and the app surface should call those names directly.

Testing depends on existing owner suites rather than new broad framework scaffolding. `tests/test_analyzer_architecture.py` must become the focused structural ratchet. `tests/test_analyzers_suites.py`, `tests/test_analyzers_variables.py`, `tests/test_variables_helper_coverage.py`, `tests/test_variables_access_and_contract_helpers.py`, `tests/test_reset_contamination_ratchet.py`, and `tests/test_reset_contamination_ratchet_helpers.py` remain the nearest behavior suites for validating that the refactor slices preserve analyzer behavior.
