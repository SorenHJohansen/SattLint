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
- [x] (2026-05-15) Split `modules.py` into `src/sattlint/analyzers/_modules_fingerprints.py`, `src/sattlint/analyzers/_modules_diffing.py`, and `src/sattlint/analyzers/_modules_reporting.py` while keeping `compare_modules`, `analyze_module_duplicates`, and `analyze_version_drift` stable. `modules.py` shrank from 1425 lines to 636 lines, and the focused `tests/analyzers/test_modules.py` slice plus touched-file Ruff and Pyright all passed.
- [x] (2026-05-15) Split `reset_contamination.py` into reset-path collection versus boolean-latching helpers by moving the boolean traversal and implicit-latch emission stack into `src/sattlint/analyzers/_reset_latching.py` while keeping compatibility aliases in the owner for existing helper tests. `reset_contamination.py` shrank from 944 lines to 407 lines, and the focused reset pytest slice plus touched-file Ruff and Pyright all passed.
- [x] (2026-05-15) Narrow `_variables_analyzer_facade.py` by moving the pure forwarding properties into `src/sattlint/analyzers/_variables_facade_properties.py` and keeping the main facade mixin as the remaining wrapper surface. `_variables_analyzer_facade.py` shrank from 300 lines to 202 lines, the narrow variable-helper pytest slice passed, and touched-file Ruff and Pyright are clean after adding protocol-backed state typing for the extracted mixin.
- [x] (2026-05-15) Trim `_mms_interface_analysis.py` by separating ICF loading and translation into `src/sattlint/analyzers/_mms_icf_inventory.py` while keeping traversal and MMS hit collection in the owner. `_mms_interface_analysis.py` shrank from 692 lines to 407 lines, `tests/analyzers/test_mms.py` passed, and touched-file Ruff and Pyright are clean.
- [x] (2026-05-15) Split `sattline_semantics.py` by responsibility by moving the shared semantic models into `src/sattlint/analyzers/_sattline_semantic_models.py`, the static rule catalog into `src/sattlint/analyzers/_sattline_semantic_rules.py`, and the issue translation helpers into `src/sattlint/analyzers/_sattline_semantic_issue_mapping.py` while keeping `analyze_sattline_semantics`, the public dataclasses, and the summary surface stable. `sattline_semantics.py` shrank from 1185 lines to 199 lines, the focused semantics pytest slice passed with `32 passed`, and touched-file Ruff and Pyright are clean.
- [x] (2026-05-15) Split `icf.py` by restoring the missing file-formatting and parse helper seam in `src/sattlint/analyzers/_icf_file_io.py` while keeping validation and datatype resolution in the owner. `icf.py` shrank from 943 lines to 797 lines, `_icf_file_io.py` landed at 208 lines, the focused ICF pytest slice passed with `41 passed`, and touched-file Ruff and Pyright are clean.
- [x] (2026-05-15) Split `alarm_integrity.py` by separating alarm-path traversal into `src/sattlint/analyzers/_alarm_path_traversal.py` while keeping issue emission in the owner. `alarm_integrity.py` shrank from 745 lines to 606 lines, `tests/analyzers/test_alarm_integrity.py` passed, and touched-file Ruff and Pyright are clean.
- [x] (2026-05-15) Split `_sfc_collectors.py` by moving `StepContract` and `_SfcStepContractCollector` into `src/sattlint/analyzers/_sfc_step_contracts.py` while leaving `_SfcAccessCollector` in the owner and keeping `sfc.py` behavior stable. `_sfc_collectors.py` shrank from 673 lines to 270 lines, the focused SFC and step-contract pytest slice passed, and touched-file Ruff and Pyright are clean.
- [x] (2026-05-15) Decompose `_registry_specs.py::build_default_analyzers` and `_registry_delivery.py::_base_delivery_metadata_by_analyzer` into declarative template modules: `src/sattlint/analyzers/_registry_spec_templates.py` and `src/sattlint/analyzers/_registry_delivery_data.py`. `_registry_specs.py` shrank from 406 lines to 58 lines, the delivery data import break was repaired, and a direct registry validation plus touched-file Ruff and Pyright all passed.
- [x] (2026-05-15) Rerun focused analyzer pytest, then touched-file Ruff and Pyright. The final `sattline_semantics.py` slice passed focused pytest plus touched-file Ruff and Pyright after the helper extraction.

## Surprises & Discoveries

Observation: `modules.py` is carrying both algorithmic and presentation debt.
Evidence: the file owns normalized value comparison, fingerprint hashing, module walking, material-difference summaries, and user-facing upgrade-note formatting in one place.

Observation: `reset_contamination.py` is really two analyzers sharing one owner.
Evidence: the file owns reset contamination detection and implicit boolean latching detection, each with its own traversal and issue-emission paths.

Observation: `_variables_analyzer_facade.py` is mostly forwarding surface.
Evidence: the class is dominated by property accessors and thin wrappers over private methods, which is why the architecture report flags it for method-count debt even though the file is not one of the largest by line count.

Observation: extracted forwarding mixins need an explicit structural state contract to stay Pyright-clean.
Evidence: moving the facade properties into `_variables_facade_properties.py` surfaced `reportAttributeAccessIssue` errors for every forwarded attribute until the mixin cast `self` through a protocol describing the backing `VariablesAnalyzer` state.

Observation: analyzer coverage debt will surface immediately on touch.
Evidence: the repo-health snapshot lists low coverage ratchets for `src/sattlint/analyzers/safety_paths.py`, `src/sattlint/analyzers/scan_loop_resource_usage.py`, and `src/sattlint/analyzers/cyclomatic_complexity.py`, so any spillover changes into neighboring analyzer infrastructure should add focused tests rather than treating those owners as free cleanup.

Observation: four more ratcheted analyzer owners have no active plan.
Evidence: `sattline_semantics.py` (1185 lines), `icf.py` (943 lines), `alarm_integrity.py` (745 lines), and `_sfc_collectors.py` (673 lines) all appear in `artifacts/analysis/file_debt_ratchet.json` with `must_shrink` and no exec plan cross-reference. They share the same owner-split pattern as `modules.py` and belong in this plan.

Observation: the two largest single functions in the codebase are data tables encoded as imperative code.
Evidence: `_registry_specs.py::build_default_analyzers` is 406 lines and `_registry_delivery.py::_base_delivery_metadata_by_analyzer` is 308 lines. Both are long because they assemble large static records inline rather than loading them from a declarative data structure or splitting by domain category.

Observation: the `modules.py` split needs public helper exports, not cross-file imports of underscore names.
Evidence: the first touched-file Pyright run after extraction flagged `reportPrivateUsage` on `_empty_fingerprints`, `_empty_instance_fingerprints`, and `_normalize_name`, so the helper modules now expose public `empty_*` and `normalize_*` entry points for cross-file use.

Observation: half-applied owner splits can leave the repo in a type-broken state even when the intended seam is correct.
Evidence: `icf.py` and `_registry_delivery.py` both referenced missing helper modules during this tranche. Recreating `_icf_file_io.py` and `_registry_delivery_data.py` from the committed owner surfaces restored the intended splits without behavior drift.

Observation: semantic analyzers benefit from separating declarative rule catalogs from issue-translation logic before touching orchestration.
Evidence: `sattline_semantics.py` dropped from 1185 lines to 199 lines once the public dataclasses, rule catalog, and issue mappers were split into `_sattline_semantic_models.py`, `_sattline_semantic_rules.py`, and `_sattline_semantic_issue_mapping.py`, and the focused semantics pytest slice stayed green.

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

Decision: helper modules created during owner splits should expose public names for any cross-file API, even when the helpers are internal siblings.
Rationale: Pyright's private-usage checks treat imported underscore names as non-public API. Using public helper exports keeps the extracted seams lintable and type-check clean without suppressions.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: when extracting pure forwarding properties into a reusable mixin, preserve strict typing by giving the mixin an internal protocol-backed view of the owning analyzer state.
Rationale: the original facade relied on implicit subclass attributes. The extraction kept behavior the same, but Pyright needed a structural contract so the new mixin could remain strict without broad `Any` fallbacks or suppressions.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: when a partially landed split leaves a missing helper module behind, reconstruct the helper from the committed owner snapshot before attempting further refactors.
Rationale: restoring the intended seam from `HEAD` is safer than re-deriving formatting or metadata behavior from tests alone, and it preserves the owner API while getting the repo back to an executable state.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

Decision: split the semantic analyzer around stable API surfaces by keeping the report and public entry points in `sattline_semantics.py` and moving only models, rule data, and issue translation to siblings.
Rationale: tests and registry code import `SemanticRule`, `SemanticRuleGroup`, and `analyze_sattline_semantics` from the owner. Re-exporting imported dataclasses from the owner preserved that API while removing the largest non-behavioral sections.
Date/Author: 2026-05-15 / Copilot (GPT-5.4)

## Outcomes & Retrospective

The full plan-43 analyzer-owner tranche has landed. `src/sattlint/analyzers/modules.py` now delegates fingerprint construction, normalized diffing, and report-formatting helpers to three sibling modules while keeping the public analyzer entry points stable. `src/sattlint/analyzers/reset_contamination.py` delegates boolean-latching traversal to `src/sattlint/analyzers/_reset_latching.py`, `_variables_analyzer_facade.py` delegates forwarding properties to `src/sattlint/analyzers/_variables_facade_properties.py`, `_mms_interface_analysis.py` delegates ICF loading and translation to `src/sattlint/analyzers/_mms_icf_inventory.py`, `alarm_integrity.py` delegates boolean-write traversal to `src/sattlint/analyzers/_alarm_path_traversal.py`, `icf.py` delegates file decoding, formatting, and parsing to `src/sattlint/analyzers/_icf_file_io.py`, `_sfc_collectors.py` delegates step-contract analysis to `src/sattlint/analyzers/_sfc_step_contracts.py`, `sattline_semantics.py` now delegates shared models, static rule data, and issue translation to `_sattline_semantic_models.py`, `_sattline_semantic_rules.py`, and `_sattline_semantic_issue_mapping.py`, and the registry builders now pull declarative templates from `src/sattlint/analyzers/_registry_spec_templates.py` and `src/sattlint/analyzers/_registry_delivery_data.py`. Focused pytest slices and touched-file Ruff and Pyright are clean for each landed slice.

## Context and Orientation

`src/sattlint/analyzers/modules.py` is the module-comparison and version-drift owner. In this repository, a "fingerprint" is a normalized summary of a module's variables, submodules, code, and mappings that the analyzer uses to compare variants.

`src/sattlint/analyzers/reset_contamination.py` is the owner for reset contamination and implicit latching analysis. A "latch" here means a boolean value that can remain set because not all control-flow branches write the false path back.

`src/sattlint/analyzers/_variables_analyzer_facade.py` is the forwarding facade for `VariablesAnalyzer`, with pure state properties now split into `src/sattlint/analyzers/_variables_facade_properties.py`. `_mms_interface_analysis.py` now owns traversal and MMS hit collection, while `src/sattlint/analyzers/_mms_icf_inventory.py` owns ICF loading and translation into inventory entries. `icf.py` now keeps validation logic while `_icf_file_io.py` owns decode, format, and parse helpers. `_sfc_collectors.py` now keeps access collection while `_sfc_step_contracts.py` owns step-contract analysis. `sattline_semantics.py` now keeps orchestration and report rendering while `_sattline_semantic_models.py`, `_sattline_semantic_rules.py`, and `_sattline_semantic_issue_mapping.py` own the public semantic dataclasses, rule catalog, and issue translation helpers. The registry builder files now assemble data from declarative template modules instead of long inline tables.

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

    Current owner sizes after the first landed slice (2026-05-15):

        636 src/sattlint/analyzers/modules.py
        322 src/sattlint/analyzers/_modules_fingerprints.py
        330 src/sattlint/analyzers/_modules_diffing.py
        134 src/sattlint/analyzers/_modules_reporting.py

    Current owner sizes after the reset, variables facade, and MMS slices (2026-05-15):

        407 src/sattlint/analyzers/reset_contamination.py
        613 src/sattlint/analyzers/_reset_latching.py
        202 src/sattlint/analyzers/_variables_analyzer_facade.py
        152 src/sattlint/analyzers/_variables_facade_properties.py
        407 src/sattlint/analyzers/_mms_interface_analysis.py
         85 src/sattlint/analyzers/_mms_icf_inventory.py

    Current owner sizes after the alarm, ICF, SFC, and registry slices (2026-05-15):

        606 src/sattlint/analyzers/alarm_integrity.py
        193 src/sattlint/analyzers/_alarm_path_traversal.py
        797 src/sattlint/analyzers/icf.py
        208 src/sattlint/analyzers/_icf_file_io.py
        270 src/sattlint/analyzers/_sfc_collectors.py
        430 src/sattlint/analyzers/_sfc_step_contracts.py
         58 src/sattlint/analyzers/_registry_specs.py
        242 src/sattlint/analyzers/_registry_spec_templates.py
        397 src/sattlint/analyzers/_registry_delivery.py
        366 src/sattlint/analyzers/_registry_delivery_data.py

    Current owner sizes after the semantics slice (2026-05-15):

        199 src/sattlint/analyzers/sattline_semantics.py
         63 src/sattlint/analyzers/_sattline_semantic_models.py
        771 src/sattlint/analyzers/_sattline_semantic_rules.py
        198 src/sattlint/analyzers/_sattline_semantic_issue_mapping.py

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
