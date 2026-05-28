# C-Wave-9 Record Component Order-Dependence Check

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan adds a semantic warning for SattLine code that reads from or writes to record fields by numeric position instead of by field name. After this work lands, SattLint will flag code where changing the declaration order of a datatype can silently change runtime behavior. The concrete motivating case is code that copies only the first `X` record components into an array or picklist. Today that pattern is invisible to the analyzer even though it makes datatype field order part of the runtime contract.

The observable proof is simple. A focused analyzer test that models `GetRecordComponent(...)` or `PutRecordComponent(...)` over a record must produce a new variable-analysis finding. A report-level test must show that the finding renders in the variables report and editor diagnostics with plain-language guidance that reordering datatype fields can break the module.

## Progress

- [x] (2026-05-27 11:58Z) Created this ExecPlan and captured the owning seams: builtin traversal in `src/sattlint/analyzers/_variable_traversal_support.py`, variable issue/report plumbing in `src/sattlint/analyzers/variable_issue_collection.py` and `src/sattlint/reporting/variables_report.py`, and editor diagnostic projection in `src/sattlint/core/diagnostics.py`.
- [x] (2026-05-27 12:02Z) Verified the live motivating example through the workstation SattLint config. The default config at `~/.config/sattlint/config.toml` includes `KaHASoejleLib` under `/home/sqhj/Projects/Libs/HA/ProjectLib`, and that library reaches `KaHARecipePicklist` in `KaHASøjleSupportLib.s`.
- [x] (2026-05-27 12:05Z) Confirmed the dangerous implementation pattern in the live source: `KaHARecipePicklist` builds an array by calling `GetRecordComponent(RecipeRecord, EmptyElementNo, ...)` and `GetRecordComponent(RecipeRecord, GetComponentIndex, ...)`, then `PutArray(...)`, so changing datatype field order changes the picklist contents.
- [x] (2026-05-28 06:48Z) Added `IssueKind.RECORD_COMPONENT_ORDER_DEPENDENCE`, made it default-visible in variable reports, added the section title `Positional record component access`, added editor diagnostic guidance, and exposed the check in the interactive variable-analysis menu.
- [x] (2026-05-28 06:48Z) Added traversal handling for `GetRecordComponent`, `GetRecordCompNoSort`, `PutRecordComponent`, and `PutRecordCompNoSort`. The analyzer now emits an additive variable issue on the affected record variable, preserves the existing signature-based read/write accounting, and includes the ordinal index plus resolved field name when the index is a literal on a concrete record type.
- [x] (2026-05-28 06:48Z) Added focused regression coverage for direct `GetRecordComponent` and `PutRecordComponent` calls, an `AnyType` wrapper that mirrors the KaHARecipePicklist dynamic-index shape, a rendered variables-report check, an interactive menu routing check, and an editor-diagnostics guidance check.
- [x] (2026-05-28 06:48Z) Validation passed with focused pytest slices for builtin semantics, report rendering, menu routing, and diagnostics guidance, plus touched-file Ruff and Pyright on the final edited file set.

## Surprises & Discoveries

Observation: the user-facing symptom appears in `KaHASoejleLib`, but the real dangerous behavior lives one level deeper in a support-library moduletype.
Evidence: `KaHASoejleLib.s` computes `MinNoOfElements`, `MaxNoOfElements`, and `SingleElementNo`, then passes `RecipeRecord => SolventCMD` into `KaHARecipePicklist`; `KaHASøjleSupportLib.s` performs the positional record reads.

Observation: the core risk is broader than arrays.
Evidence: the breaking behavior comes from `GetRecordComponent*` and `PutRecordComponent*` themselves. Array and picklist population are only one common downstream use.

Observation: SattLint already models whole-record copy builtins precisely, but it does not have any special handling for order-based record component builtins.
Evidence: `src/sattlint/analyzers/_variable_traversal_support.py` has explicit branches for `CopyVariable`, `CopyVarNoSort`, and `InitVariable`, while `GetRecordComponent*` and `PutRecordComponent*` currently fall through generic signature handling.

Observation: the initial rule does not need exact record field-name resolution to be useful.
Evidence: the live `KaHARecipePicklist` example uses `RecipeRecord: AnyType`, so the dangerous positional access is obvious even when the concrete caller datatype is not known at the call site.

Observation: the existing top-level aggregate test modules are poor touched-file Pyright targets because they already aggregate unrelated import and strict-typing noise.
Evidence: the focused feature tests for report rendering, app-menu routing, and diagnostics guidance were moved into dedicated standalone test files so the finish gate could type-check the actual slice instead of failing on unrelated legacy test aggregation patterns.

## Decision Log

Decision: implement the first rule as a direct builtin-use check on positional record-component access, not as a special-case array-copy heuristic.
Rationale: the array wrapper is only a manifestation of the underlying problem. Flagging the builtin calls themselves catches the real root cause and also covers non-array consumers.
Date/Author: 2026-05-27 / Copilot (GPT-5.4)

Decision: include both `GetRecordComponent*` and `PutRecordComponent*` families in the first slice.
Rationale: reading a field by ordinal and writing a field by ordinal are equally order-dependent. The user example is a `Get...` flow, but the maintenance risk exists in both directions.
Date/Author: 2026-05-27 / Copilot (GPT-5.4)

Decision: treat this finding as a default-visible variable-analysis issue, not a low-confidence advisory.
Rationale: if code depends on record component ordinal position, field reordering really can change behavior. That is a concrete compatibility hazard, not a style opinion.
Date/Author: 2026-05-27 / Copilot (GPT-5.4)

Decision: do not require full dataflow proof that the record component is eventually copied into an array before raising the finding.
Rationale: the direct builtin call is already the order-sensitive contract. Requiring downstream array proof would miss real bugs and add unnecessary complexity to the first slice.
Date/Author: 2026-05-27 / Copilot (GPT-5.4)

Decision: keep the builtin-semantics proof in `tests/analyzers/test_builtin_record_semantics.py`, but place the report, menu, and diagnostics assertions in small dedicated test files instead of extending the existing aggregate test entrypoints.
Rationale: that kept the behavior proof narrow while also allowing touched-file Pyright to validate the feature slice without pulling in unrelated strict-typing debt from legacy aggregate test modules.
Date/Author: 2026-05-28 / Copilot (GPT-5.4)

## Outcomes & Retrospective

At plan creation time, SattLint can already detect named-field usage, unused datatype fields, whole-record copy semantics, and several cross-module variable hazards, but it has no warning for positional record access. The implementation described here closes that blind spot with a focused rule that matches the real production pattern found through the active workstation config.

The main risk is overfitting the rule to the `KaHARecipePicklist` wrapper instead of the builtin. This plan deliberately avoids that trap: the wrapper is motivating evidence, not the detection surface.

After implementation, the variables analyzer emits `RECORD_COMPONENT_ORDER_DEPENDENCE` findings for all four positional record-component builtins, reports them by default, and renders diagnostics that explain the compatibility hazard and suggested remediation. Literal ordinal accesses on concrete records now mention the resolved field name, while `AnyType` wrappers still produce a generic but actionable warning.

The final proof stayed behavior-scoped: builtin AST tests cover direct `Get...` and `Put...` calls plus the dynamic `AnyType` wrapper shape, and dedicated report/menu/diagnostic tests cover user-facing output without widening the slice into unrelated analyzer or workspace behavior.

## Context and Orientation

The owning analyzer is the variables analyzer under `src/sattlint/analyzers/`. Function-call traversal lives in `src/sattlint/analyzers/_variable_traversal_support.py`. That module already contains special-case handling for builtins whose semantics are richer than plain parameter directions, such as `CopyVariable`, `CopyVarNoSort`, and `InitVariable`. Variable-analysis issues are represented by `IssueKind` and `VariableIssue` in `src/sattlint/reporting/variables_report.py`, then rendered for CLI and reports through `src/sattlint/reporting/_variables_report_rendering.py` and projected into editor diagnostics by `src/sattlint/core/diagnostics.py`. The interactive CLI menu for selecting variable analyses is wired in `src/sattlint/_app_analysis_variable_analyses.py`.

In this plan, `order-dependent record component access` means any use of SattLine builtins that address record components by a numeric index rather than by a field name. The builtins to treat as dangerous are `GetRecordComponent`, `GetRecordCompNoSort`, `PutRecordComponent`, and `PutRecordCompNoSort`. These builtins make the physical declaration order of a datatype part of the runtime behavior. If somebody later reorders fields inside the datatype, the code still parses, but it may start reading or writing the wrong fields.

The live example that motivated this plan is external to the repository, so the implementation must not depend on that file being present. The relevant evidence is reproduced here so the plan stays self-contained. First, `KaHASoejleLib.s` computes a variable window over `SolventCMD` and passes it into a picklist wrapper:

    MinIndex => MinNoOfElements,
    MaxIndex => MaxNoOfElements,
    EmptyElementNo => SingleElementNo,
    RecipeRecord => SolventCMD,

Then the wrapper implementation in `KaHASøjleSupportLib.s` turns that record window into an array by ordinal position:

    IF EmptyElementNo > 0 AND ComponentIndex < 2 THEN
       GetRecordComponent(RecipeRecord, EmptyElementNo, StateElement, si2);
       CopyString(StateElement, ListElement.Line, si3);
       PutArray(RecipeArray, ComponentIndex, ListElement, Si4);
    ENDIF;
    IF GetComponentIndex <= MaxNoOfIndex THEN
       GetRecordComponent(RecipeRecord, GetComponentIndex, StateElement, si2);
       CopyString(StateElement, ListElement.Line, si3);
       PutArray(RecipeArray, ComponentIndex, ListElement, Si4);
    ENDIF;

That is the behavior this plan must make visible.

There is already a nearby focused test home for builtin-record semantics in `tests/analyzers/test_builtin_record_semantics.py`. Broader variable-report integration tests live in `tests/test_analyzers_variables.py`. Keep the first proof narrow there rather than inventing a new broad suite.

## Plan of Work

Start by introducing a new variable-analysis issue kind in `src/sattlint/reporting/variables_report.py`. Use a name that reads clearly in both code and user output, for example `RECORD_COMPONENT_ORDER_DEPENDENCE` or `POSITIONAL_RECORD_COMPONENT_ACCESS`. Add it to the default-visible analysis kinds, summary ordering, and section titles so the new finding shows up naturally in existing variable reports. Update `src/sattlint/core/diagnostics.py` with an editor-facing label and guidance that explains why ordinal component access is risky. Update `src/sattlint/_app_analysis_variable_analyses.py` so the interactive analysis menu can expose the new check explicitly.

Next, add the actual detection in `src/sattlint/analyzers/_variable_traversal_support.py`, because that is where builtin calls are already interpreted semantically. Do not build a new whole-program dataflow pass for this first slice. Instead, add a small helper that runs when the function name is one of the four positional record-component builtins. That helper should resolve the first argument as the affected variable when possible, capture the current module path, record the builtin name in `role` or `site`, and append a `VariableIssue` immediately. If the second argument is an integer literal and the record type is concrete, include the component index and resolved field name in the role text. If the datatype is `AnyType` or otherwise unknown, still emit the issue with a generic message that the code depends on record declaration order.

While adding that branch, preserve the existing generic argument-walking behavior for read and write accounting. The new issue is additive; it must not stop `GetRecordComponent*` and `PutRecordComponent*` arguments from contributing to ordinary usage tracking. If the easiest safe implementation is to emit the new issue and then continue through the existing signature-based traversal, do that. Avoid rewriting unrelated builtin handling.

After detection exists, thread the new issue through rendering. If the generic variable-issue list already produces clear output once `SECTION_TITLES` and `DiagnosticGuidance` are present, keep it generic. Do not create a custom report renderer unless the default output is too vague. The minimum acceptable message is that the module accesses record components by numeric position and will change behavior if the datatype field order changes.

Then add focused tests. In `tests/analyzers/test_builtin_record_semantics.py`, add one direct AST-based test for a simple `GetRecordComponent` call on a record variable and one test for `PutRecordComponent`. Add a second test that mirrors the `KaHARecipePicklist` pattern: use a `RecipeRecord: AnyType` parameter, dynamic `GetComponentIndex` and `MaxNoOfIndex` locals, and repeated `GetRecordComponent` plus `PutArray` inside sequence or module code. That test should prove the rule fires even when the concrete caller datatype is not known locally. In `tests/test_analyzers_variables.py`, add one report-level test that checks the new issue kind appears in the rendered output with readable guidance.

If editor diagnostics already project variable issues by declaration site for similar findings, reuse that mechanism. If the new issue needs a more precise anchor later, record that as a follow-on rather than widening this slice immediately. The first deliverable is a trustworthy warning, not perfect call-site pinpointing.

## Concrete Steps

Run all commands from the repository root.

First, add the focused regression tests before changing analyzer behavior so the new rule is driven by executable proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/analyzers/test_builtin_record_semantics.py -k "record_component or positional_record" -x -q --tb=short

That command should fail before the implementation because the new tests will expect a finding that does not exist yet.

After wiring the new issue kind and traversal branch, rerun the same focused builtin test slice:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/analyzers/test_builtin_record_semantics.py -k "record_component or positional_record" -x -q --tb=short

When the builtin test slice passes, run the report-integration proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_analyzers_variables.py -k "record_component_order or positional_record_component" -x -q --tb=short

Then run the touched-file finish gate:

    bash scripts/run_repo_python.sh -m ruff check src/sattlint/analyzers/_variable_traversal_support.py src/sattlint/reporting/variables_report.py src/sattlint/core/diagnostics.py src/sattlint/_app_analysis_variable_analyses.py tests/analyzers/test_builtin_record_semantics.py tests/test_analyzers_variables.py
    bash scripts/run_repo_python.sh -m pyright src/sattlint/analyzers/_variable_traversal_support.py src/sattlint/reporting/variables_report.py src/sattlint/core/diagnostics.py src/sattlint/_app_analysis_variable_analyses.py tests/analyzers/test_builtin_record_semantics.py tests/test_analyzers_variables.py

Optional workstation-only smoke, if the live external library tree is present and the default config still points at it:

    python - <<'PY'
    from pathlib import Path
    from sattlint.config import get_config_path, load_config
    path = get_config_path()
    cfg, _ = load_config(path)
    print(path)
    print(cfg["program_dir"])
    print(cfg["other_lib_dirs"])
    PY

Use that only as supporting evidence. The authoritative acceptance proof for this plan remains the checked-in pytest coverage.

## Validation and Acceptance

Acceptance requires more than a new enum member. A direct call to `GetRecordComponent` or `PutRecordComponent` in a focused analyzer test must create a new visible finding. A KaHARecipePicklist-style wrapper that computes a dynamic range and then uses `GetRecordComponent` to populate an array must also produce the finding, even when the wrapper parameter is typed as `AnyType` locally.

The variables report must render the new issue in a readable section with guidance that explains the real hazard: record field order has become part of the contract. The editor diagnostics mapping in `src/sattlint/core/diagnostics.py` must include a short label and remediation text so workspace users do not see an unlabeled generic issue.

Existing variable-usage behavior must remain intact. Whole-record copy handling, unused datatype field reporting, and generic parameter-direction read/write tracking must still pass their nearby tests after this slice lands.

## Idempotence and Recovery

The implementation is safe to land incrementally. Adding the new tests first is harmless and gives a clear failure target. Adding the new issue kind and message plumbing is also safe before the traversal branch exists, as long as the tests still fail for the intended reason.

If the first implementation produces too many false positives, narrow it by limiting the rule to the four record-component builtins only. Do not widen the first slice into call-chain inference, wrapper recognition, or array-flow tracking. Those are follow-on refinements, not requirements for the initial warning.

If diagnostics anchoring becomes awkward because the current variable issue structure prefers declaration sites over call sites, keep the warning anchored to the affected variable for this slice and record precise call-site anchoring as follow-on work. Do not block the main feature on span plumbing unless the result is unusably vague.

## Artifacts and Notes

Captured live-config evidence at plan creation time:

    ~/.config/sattlint/config.toml
    analyzed_programs_and_libraries = [..., "KaHASoejleLib", ...]
    program_dir = "/home/sqhj/Projects/Libs/HA/UnitLib"
    other_lib_dirs = ["/home/sqhj/Projects/Libs/HA/ProjectLib", "/home/sqhj/Projects/Libs/HA/NNELib"]

Resolved live library files through that config:

    /home/sqhj/Projects/Libs/HA/ProjectLib/KaHASoejleLib.l
    /home/sqhj/Projects/Libs/HA/ProjectLib/KaHASoejleLib.s
    /home/sqhj/Projects/Libs/HA/ProjectLib/KaHASoejleLib.x
    /home/sqhj/Projects/Libs/HA/ProjectLib/KaHASoejleLib.z

Relevant lines from the live support-library owner:

    GetRecordComponent(RecipeRecord, EmptyElementNo, StateElement, si2);
    PutArray(RecipeArray, ComponentIndex, ListElement, Si4);
    GetRecordComponent(RecipeRecord, GetComponentIndex, StateElement, si2);
    PutArray(RecipeArray, ComponentIndex, ListElement, Si4);

Those excerpts are evidence only. The implementation and acceptance tests for this plan must remain repository-local.

## Interfaces and Dependencies

The main interface addition is a new `IssueKind` in `src/sattlint/reporting/variables_report.py`, plus matching report titles and diagnostic guidance. The analyzer entry point remains `VariablesAnalyzer` in `src/sattlint/analyzers/variables.py`; do not create a separate analyzer class for this slice.

The primary implementation seam is `src/sattlint/analyzers/_variable_traversal_support.py:_handle_function_call()`. If a small helper improves clarity, keep it in that module or in the nearest existing analyzer helper module rather than creating a parallel subsystem. Reuse `VariableIssue.site` and `role` to carry human-readable context. Do not invent a second issue transport structure.

The validation dependencies are the existing repo Python wrapper script, focused pytest in `tests/analyzers/test_builtin_record_semantics.py` and `tests/test_analyzers_variables.py`, plus touched-file Ruff and Pyright. Keep the first proof narrow and behavior-scoped.
