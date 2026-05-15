# T-Wave-6 Analyzer Owner Splits

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan covers the largest remaining analyzer-side structural debt from the 2026-05-15 architecture review. `src/sattlint/analyzers/modules.py`, `src/sattlint/analyzers/reset_contamination.py`, `src/sattlint/analyzers/_variables_analyzer_facade.py`, and `src/sattlint/analyzers/_mms_interface_analysis.py` still mix too many responsibilities in single owners. After this work lands, module comparison, reset-path analysis, variable-analyzer support, and MMS inventory traversal will still report the same findings, but the implementation will be split into smaller helpers that match the real responsibilities.

Four additional ratcheted analyzer owners — `sattline_semantics.py` (1185 lines), `icf.py` (943 lines), `alarm_integrity.py` (745 lines), and `_sfc_collectors.py` (673 lines) — have no active plan. They belong here because they share the same analyzer ownership pattern and the same must_shrink constraint.

Two registry files contain the largest single functions in the codebase by line count. `src/sattlint/analyzers/_registry_specs.py::build_default_analyzers` is 406 lines and `src/sattlint/analyzers/_registry_delivery.py::_base_delivery_metadata_by_analyzer` is 308 lines. Both encode static catalog data as imperative code instead of a declarative data structure. This plan covers decomposing them.

The observable proof is that focused analyzer tests still pass for module comparison, reset contamination, variable analysis, and MMS reporting, while the oversized owner files and over-budget facade class shrink instead of growing further.

## Progress

- [x] (2026-05-15) Create the ExecPlan and confirm `src/sattlint/analyzers/modules.py` is 1425 lines, `src/sattlint/analyzers/reset_contamination.py` is 944 lines, `src/sattlint/analyzers/_mms_interface_analysis.py` is 692 lines, and `src/sattlint/analyzers/_variables_analyzer_facade.py` still exposes 57 methods on one facade mixin.
- [x] (2026-05-15) Gap review adds `sattline_semantics.py` (1185 lines), `icf.py` (943 lines), `alarm_integrity.py` (745 lines), `_sfc_collectors.py` (673 lines), and the two over-budget registry functions to this plan.
- [ ] Split `modules.py` into fingerprinting, normalized-diff comparison, and report-formatting helpers while keeping `compare_modules`, `analyze_module_duplicates`, and `analyze_version_drift` stable.
- [ ] Split `reset_contamination.py` into reset-path collection versus boolean-latching helpers while keeping issue ordering and ratchet-helper behavior stable.
- [ ] Narrow `_variables_analyzer_facade.py` by replacing bulk forwarding properties and wrappers with smaller mixins, direct attribute ownership, or explicit helper objects that preserve `VariablesAnalyzer` behavior.
- [ ] Trim `_mms_interface_analysis.py` further by separating ICF loading or translation from traversal and inventory collection if that shrink is required while touching the owner.
- [ ] Split `sattline_semantics.py` by responsibility. Move datatype-validation helpers and semantic-contract checks into dedicated sibling helpers while keeping the public semantic-analysis entry points stable.
- [ ] Split `icf.py` by separating ICF config loading, validation, and report formatting into sibling helpers while keeping the public ICF analyzer entry points stable.
- [ ] Split `alarm_integrity.py` by separating alarm-path traversal from issue emission and suppression helpers.
- [ ] Split `_sfc_collectors.py` by separating SFC step and transition collection from guard-condition logic, reusing the existing `_sfc_guard_logic.py` seam where possible.
- [ ] Decompose `_registry_specs.py::build_default_analyzers` (406 lines) from an imperative function into a declarative data structure, and do the same for `_registry_delivery.py::_base_delivery_metadata_by_analyzer` (308 lines).
- [ ] Rerun focused analyzer pytest, then touched-file Ruff and Pyright.

## Surprises & Discoveries

Observation: `modules.py` is carrying both algorithmic and presentation debt.
Evidence: the file owns normalized value comparison, fingerprint hashing, module walking, material-difference summaries, and user-facing upgrade-note formatting in one place.

Observation: `reset_contamination.py` is really two analyzers sharing one owner.
Evidence: the file owns reset contamination detection and implicit boolean latching detection, each with its own traversal and issue-emission paths.

Observation: `_variables_analyzer_facade.py` is mostly forwarding surface.
Evidence: the class is dominated by property accessors and thin wrappers over private methods, which is why the architecture report flags it for method-count debt even though the file is not one of the largest by line count.

Observation: analyzer coverage debt will surface immediately on touch.
Evidence: the repo-health snapshot lists low coverage ratchets for `src/sattlint/analyzers/safety_paths.py`, `src/sattlint/analyzers/scan_loop_resource_usage.py`, and `src/sattlint/analyzers/cyclomatic_complexity.py`, so any spillover changes into neighboring analyzer infrastructure should add focused tests rather than treating those owners as free cleanup.

Observation: four more ratcheted analyzer owners have no active plan.
Evidence: `sattline_semantics.py` (1185 lines), `icf.py` (943 lines), `alarm_integrity.py` (745 lines), and `_sfc_collectors.py` (673 lines) all appear in `artifacts/analysis/file_debt_ratchet.json` with `must_shrink` and no exec plan cross-reference. They share the same owner-split pattern as `modules.py` and belong in this plan.

Observation: the two largest single functions in the codebase are data tables encoded as imperative code.
Evidence: `_registry_specs.py::build_default_analyzers` is 406 lines and `_registry_delivery.py::_base_delivery_metadata_by_analyzer` is 308 lines. Both are long because they assemble large static records inline rather than loading them from a declarative data structure or splitting by domain category.

## Decision Log

Decision: split each analyzer owner by responsibility, not by arbitrary helper count.
Rationale: future contributors need obvious homes for traversal, comparison, and formatting logic. Mechanical slicing without ownership clarity would only postpone the next monolith.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: preserve public analyzer entry points and report ordering while extracting helpers.
Rationale: these files are structural debt, not behavior change requests. Existing tests already pin the external behavior, so the split should work behind stable entry points.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: treat the variable-analyzer facade as API-shape debt rather than just a line-count problem.
Rationale: the method budget breach is a sign that the facade exposes too much surface area. The right fix is narrower ownership, not just moving wrappers to another file.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: fold the four additional ratcheted analyzer owners into this plan rather than creating a follow-on.
Rationale: they share the same extraction pattern and the same test-and-validation workflow. A single plan is easier to track and reduces context-switch cost between slices.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: decompose registry functions into declarative data structures rather than splitting them into more functions.
Rationale: both functions are long because they encode static data procedurally. Converting them to named constants or typed dataclass tables reduces function length, improves discoverability, and makes the analyzer catalog easier to diff.

## Outcomes & Retrospective

At creation time, no code has landed yet. The current outcome is a scoped analyzer refactor plan that groups the remaining owner-split work by behavior area and test surface instead of treating every analyzer file as an unrelated debt item.

## Context and Orientation

`src/sattlint/analyzers/modules.py` is the module-comparison and version-drift owner. In this repository, a "fingerprint" is a normalized summary of a module's variables, submodules, code, and mappings that the analyzer uses to compare variants.

`src/sattlint/analyzers/reset_contamination.py` is the owner for reset contamination and implicit latching analysis. A "latch" here means a boolean value that can remain set because not all control-flow branches write the false path back.

`src/sattlint/analyzers/_variables_analyzer_facade.py` is the forwarding facade for `VariablesAnalyzer`. `_mms_interface_analysis.py` is the helper module extracted from the MMS analyzer and now owns traversal, source resolution, and ICF-entry collection.

The nearest tests are `tests/analyzers/test_modules.py`, `tests/analyzers/test_reset_contamination.py`, `tests/test_reset_contamination_latching_helpers.py`, `tests/test_reset_contamination_ratchet.py`, `tests/test_reset_contamination_ratchet_helpers.py`, `tests/test_analyzers_variables.py`, `tests/analyzers/test_mms.py`, `tests/devtools/test_mms_report.py`, `tests/analyzers/test_icf.py`, `tests/test_icf_validation.py`, `tests/analyzers/test_alarm_integrity.py`, and any existing SFC and sattline-semantics tests.

## Plan of Work

Start with `modules.py`. Move fingerprint construction into `src/sattlint/analyzers/_modules_fingerprints.py`, move normalized-value comparison into `src/sattlint/analyzers/_modules_diffing.py`, and move output-summary or note-formatting helpers into `src/sattlint/analyzers/_modules_reporting.py`. Keep the public entry functions in `modules.py` as stable orchestration wrappers.

Then split `reset_contamination.py` by behavior. Reuse the existing `_reset_path_collection.py` and `_reset_path_state.py` seams for reset-path logic, and move boolean-latching traversal and issue emission into a new helper such as `src/sattlint/analyzers/_reset_latching.py`. Keep the public detection functions in the owner file only if they are still the narrowest stable entry points.

Finally, narrow `_variables_analyzer_facade.py` and `_mms_interface_analysis.py`. Move the pure forwarding properties into `src/sattlint/analyzers/_variables_facade_properties.py` if they still need a mixin surface, and move ICF loading or translation into `src/sattlint/analyzers/_mms_icf_inventory.py` so traversal and inventory collection are no longer coupled.

Then work through the four additional ratcheted owners. Split `sattline_semantics.py` by moving datatype-validation helpers into `src/sattlint/analyzers/_sattline_semantics_datatypes.py` and semantic-contract checks into `src/sattlint/analyzers/_sattline_semantics_contracts.py`, keeping the public entry points stable. Split `icf.py` by moving ICF config loading into a helper such as `src/sattlint/analyzers/_icf_config_loading.py` and report formatting into `src/sattlint/analyzers/_icf_report_helpers.py`. Split `alarm_integrity.py` by extracting alarm-path traversal into `src/sattlint/analyzers/_alarm_path_traversal.py`. Split `_sfc_collectors.py` by moving guard-condition logic into the existing `_sfc_guard_logic.py` seam if it fits there, or into a new `src/sattlint/analyzers/_sfc_collection_helpers.py`.

Finally, decompose the two registry functions. Convert `build_default_analyzers` in `_registry_specs.py` from a long imperative builder into a list of typed declarative records (dataclasses or named tuples) assembled at module load, split by domain category such as structural, variable, path, SFC, and interface. Apply the same pattern to `_base_delivery_metadata_by_analyzer` in `_registry_delivery.py`.

## Concrete Steps

Run all commands from the repository root.

Inspect the current owner surfaces before editing code:

    wc -l src/sattlint/analyzers/modules.py src/sattlint/analyzers/reset_contamination.py src/sattlint/analyzers/_mms_interface_analysis.py src/sattlint/analyzers/_variables_analyzer_facade.py src/sattlint/analyzers/sattline_semantics.py src/sattlint/analyzers/icf.py src/sattlint/analyzers/alarm_integrity.py src/sattlint/analyzers/_sfc_collectors.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/_registry_delivery.py
    rg -n "def compare_modules|def analyze_version_drift|def _check_for_modulecode|def _check_for_modulecode_latching|class VariablesAnalyzerFacadeMixin|def collect_mms_inventory_entries|def collect_icf_inventory_entries|def build_default_analyzers|def _base_delivery_metadata_by_analyzer" src/sattlint/analyzers/modules.py src/sattlint/analyzers/reset_contamination.py src/sattlint/analyzers/_variables_analyzer_facade.py src/sattlint/analyzers/_mms_interface_analysis.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/_registry_delivery.py

After the first extraction slice lands, run the narrow analyzer validation first:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/analyzers/test_modules.py tests/analyzers/test_reset_contamination.py tests/test_reset_contamination_latching_helpers.py tests/test_reset_contamination_ratchet.py tests/test_reset_contamination_ratchet_helpers.py tests/test_analyzers_variables.py tests/analyzers/test_mms.py tests/devtools/test_mms_report.py -x -q --tb=short

Run touched-file quality gates after the focused tests pass:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint/analyzers/modules.py src/sattlint/analyzers/_modules_fingerprints.py src/sattlint/analyzers/_modules_diffing.py src/sattlint/analyzers/_modules_reporting.py src/sattlint/analyzers/reset_contamination.py src/sattlint/analyzers/_reset_latching.py src/sattlint/analyzers/_variables_analyzer_facade.py src/sattlint/analyzers/_variables_facade_properties.py src/sattlint/analyzers/_mms_interface_analysis.py src/sattlint/analyzers/_mms_icf_inventory.py tests/analyzers/test_modules.py tests/analyzers/test_reset_contamination.py tests/test_analyzers_variables.py tests/analyzers/test_mms.py tests/devtools/test_mms_report.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint/analyzers/modules.py src/sattlint/analyzers/_modules_fingerprints.py src/sattlint/analyzers/_modules_diffing.py src/sattlint/analyzers/_modules_reporting.py src/sattlint/analyzers/reset_contamination.py src/sattlint/analyzers/_reset_latching.py src/sattlint/analyzers/_variables_analyzer_facade.py src/sattlint/analyzers/_variables_facade_properties.py src/sattlint/analyzers/_mms_interface_analysis.py src/sattlint/analyzers/_mms_icf_inventory.py tests/test_analyzers_variables.py tests/analyzers/test_mms.py

## Validation and Acceptance

Acceptance requires stable analyzer behavior. Module comparison and version-drift results must stay stable. Reset contamination and implicit latching findings must keep the same semantics and issue ordering. Variable analysis and MMS reporting must still pass their focused tests. The split is only successful if the large owners and the over-budget facade class become smaller and easier to route by responsibility.

## Idempotence and Recovery

This plan is safe to execute one owner at a time. Split `modules.py` first and validate it. Then split `reset_contamination.py`. Then narrow the variable facade or MMS helper. If any extraction changes report ordering or issue wording, keep a thin compatibility wrapper in the old owner and restore the previous output before continuing.

## Artifacts and Notes

Current owner sizes at plan creation time:

    1425 src/sattlint/analyzers/modules.py
    944 src/sattlint/analyzers/reset_contamination.py
    692 src/sattlint/analyzers/_mms_interface_analysis.py

Added by gap review (2026-05-15):

    1185 src/sattlint/analyzers/sattline_semantics.py  (ratcheted must_shrink, target 500)
     943 src/sattlint/analyzers/icf.py                 (ratcheted must_shrink, target 500)
     745 src/sattlint/analyzers/alarm_integrity.py     (ratcheted must_shrink, target 500)
     673 src/sattlint/analyzers/_sfc_collectors.py     (ratcheted must_shrink, target 500)

Largest over-budget functions added by gap review:

    406 lines: src/sattlint/analyzers/_registry_specs.py::build_default_analyzers
    308 lines: src/sattlint/analyzers/_registry_delivery.py::_base_delivery_metadata_by_analyzer

Current method-budget finding at plan creation time:

    src/sattlint/analyzers/_variables_analyzer_facade.py: VariablesAnalyzerFacadeMixin exposes 57 methods

## Interfaces and Dependencies

The implementation surface is `src/sattlint/analyzers/modules.py`, `src/sattlint/analyzers/reset_contamination.py`, `src/sattlint/analyzers/_variables_analyzer_facade.py`, `src/sattlint/analyzers/_mms_interface_analysis.py`, `src/sattlint/analyzers/sattline_semantics.py`, `src/sattlint/analyzers/icf.py`, `src/sattlint/analyzers/alarm_integrity.py`, `src/sattlint/analyzers/_sfc_collectors.py`, `src/sattlint/analyzers/_registry_specs.py`, and `src/sattlint/analyzers/_registry_delivery.py`. Preserve the current analyzer entry points, existing report contracts, and the public `VariablesAnalyzer` behavior used elsewhere in the analyzer package.
