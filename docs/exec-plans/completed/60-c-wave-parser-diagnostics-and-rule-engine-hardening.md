# C-Wave Parser, Diagnostics, and Rule Engine Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan hardens the parser, validation, semantic-rule, and diagnostic seams that currently make core behavior harder to trust and harder to extend. After this work lands, `sattlint syntax-check` and the LSP diagnostic path will report line and column locations that still point at the original source even when parser preprocessing strips comments, validation warnings will keep their location metadata instead of collapsing to plain strings, and adding a new semantic rule family will stop requiring hand-edited wiring in several files. The visible proof is that targeted parser and LSP tests stay green, inline-comment error scenarios report the original source position, dropped diagnostics become observable instead of silent, and the semantic aggregation path can be driven from analyzer metadata rather than a manual `issues.extend(...)` ladder.

## Progress

- [x] (2026-05-19 00:00Z) Create this ExecPlan and capture the current parser, validation, analyzer-registry, semantic-aggregation, and diagnostic-projection seams.
- [x] (2026-05-21 00:00Z) Harden parser location fidelity so parse errors and derived header metadata no longer depend on column-shifting comment stripping or header-string regex extraction.
- [x] (2026-05-21 00:00Z) Replace string-only validation warnings with structured notices that preserve message, line, column, and length across `validation.py` and `engine.py`.
- [x] (2026-05-21 00:00Z) Make semantic diagnostic projection report missing-site and missing-definition drops explicitly instead of silently skipping findings.
- [x] (2026-05-21 00:00Z) Consolidate competing parser, validation-warning, and semantic-diagnostic styles so new rule work reuses one declared path instead of adding another manual variant.
- [x] (2026-05-21 00:00Z) Consolidate semantic-rule aggregation so analyzer metadata, rule mapping, and LSP exposure are declared from one seam instead of repeated in `registry.py`, `_sattline_semantic_rules.py`, and `sattline_semantics.py`.
- [x] (2026-05-21 00:00Z) Add focused regression coverage in the parser, engine, LSP, and analyzer-suite tests for source mapping, warning retention, projection-drop visibility, and semantic aggregation.
- [ ] (2026-05-21 00:00Z) Run focused pytest, Ruff, and Pyright validation for the touched slice and move this plan to `docs/exec-plans/completed/` once all boxes are checked.
- [x] (2026-05-21 00:00Z) Focused pytest coverage for the touched parser, validation, LSP, cache, engine, and analyzer slices passed with `380 passed, 11 warnings`.
- [x] (2026-05-21 00:00Z) Ruff on the touched slice passed with `All checks passed!`.
- [x] (2026-05-21 00:00Z) Pyright on the touched source files passed with `0 errors, 0 warnings, 0 informations` after tightening local type annotations in the new diagnostic and semantic aggregation seams.
- [ ] (2026-05-21 00:00Z) Full touched-file Pyright remains blocked by pre-existing strict-test debt in `tests/test_lsp_diagnostics.py` and `tests/parser/test_engine.py`, so this plan stays in `active/` until that unrelated backlog is handled or the finish-gate expectation is narrowed.

## Surprises & Discoveries

- Observation: the parser core is already grammar-driven and is not dominated by ad-hoc regex parsing.
  Evidence: `src/sattline_parser/api.py` builds a cached Lark LALR parser from `src/sattline_parser/grammar/sattline.lark`, and the regex usage in `src/sattline_parser/grammar/constants.py` is concentrated in token patterns rather than whole-program parsing.
- Observation: the highest-risk parser fragility is not the grammar but source-position drift after comment stripping.
  Evidence: `src/sattline_parser/api.py` parses `strip_sl_comments(src)` and formats parse errors against that cleaned text, while `src/sattline_parser/utils/text_processing.py` preserves newlines but can remove same-line content and a following semicolon.
- Observation: validation warnings already choose between warning and error behavior, but warning mode drops all structured location data.
  Evidence: `src/sattlint/_validation_shared.py::_warn_or_raise()` accepts `line`, `column`, and `length`, then calls `warning_sink(message)` when a sink is present.
- Observation: diagnostic projection currently hides failed lookups instead of making them debuggable.
  Evidence: `src/sattlint/core/diagnostics.py` returns early when a site has no file or span, skips issues when `site is None`, and skips variable findings when no definition span is found.
- Observation: semantic aggregation is extensible in theory but still hardcoded in practice.
  Evidence: `src/sattlint/analyzers/_registry_spec_templates.py` already describes analyzer registration declaratively, but `src/sattlint/analyzers/sattline_semantics.py` still manually calls each analyzer and manually maps each report into semantic issues.
- Observation: parse-error remapping needed both caret-context rewriting and summary-suffix rewriting to stop leaking cleaned-source coordinates.
  Evidence: `src/sattline_parser/api.py` used Lark's stock error formatting, which still embedded `at line X col Y` text even after the main caret line was rebuilt against original source.
- Observation: warning retention changes ripple into engine tests because several test doubles emulate `ProjectGraph` with `SimpleNamespace` rather than real graph instances.
  Evidence: `tests/parser/test_engine.py` needed compatibility updates once `warning_notices` became part of the stable graph-facing contract.
- Observation: the practical Pyright blocker for this slice is not the new source code but legacy strictness debt in high-volume test files.
  Evidence: source-only Pyright on the touched implementation files completed with `0 errors`, while touched-file runs that included `tests/test_lsp_diagnostics.py` and `tests/parser/test_engine.py` reported hundreds of existing `reportPrivateUsage`, unknown-parameter, and unknown-member violations in unrelated lower sections of those files.

## Decision Log

- Decision: keep Lark and the existing parser-core structure; do not attempt a parser-library swap or a grammar rewrite in this plan.
  Rationale: the current risk is reliability and coupling around positions, warnings, and semantic aggregation, not a failure of the grammar engine itself.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)
- Decision: treat source-location fidelity and silent diagnostic loss as the first milestone.
  Rationale: if parser and diagnostic positions are not trustworthy, later rule-engine extensibility work is harder to verify and easier to regress.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)
- Decision: improve rule extensibility through declarative metadata consolidation, not through runtime plugin loading.
  Rationale: this repository already uses a static analyzer catalog; consolidating metadata removes duplicated wiring without introducing a new dynamic loading model.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

## Outcomes & Retrospective

This slice is implemented. Parser comment stripping now preserves a mapping back to original source so parse errors, caret output, and summary locations point at the user's real file instead of the cleaned parser input. Header `name:` extraction is deterministic rather than regex-scanned, and numeric literal spans are either real spans or explicitly absent instead of fake `(0, 0)` placeholders.

Validation warnings now travel as structured notices through validation and engine flows, with string rendering delayed until the CLI/result boundary. Semantic diagnostic projection now records dropped findings explicitly, and semantic snapshots retain that evidence for tests and debug inspection. Semantic aggregation no longer relies on a manual analyzer call-and-map ladder; the registry metadata now declares semantic contributors, mapping kinds, and rule sources.

Validation evidence for the completed slice is strong. Focused pytest for the touched parser, validation, engine, cache, LSP, and analyzer suites passed with `380 passed, 11 warnings`. Ruff on the touched slice passed cleanly. Pyright on the touched source files passed with `0 errors, 0 warnings, 0 informations` after local annotation fixes. The remaining finish-gate blocker is pre-existing strict-test debt in `tests/test_lsp_diagnostics.py` and `tests/parser/test_engine.py`, so the plan remains in `active/` pending a decision on whether to clean that backlog or narrow the finish-gate requirement.

## Context and Orientation

The parser core lives in `src/sattline_parser/`. The main entrypoints are `build_lark_parser()`, `parse_source_text()`, and `describe_parse_error()` in `src/sattline_parser/api.py`. The grammar is `src/sattline_parser/grammar/sattline.lark`, token constants live in `src/sattline_parser/grammar/constants.py`, comment preprocessing lives in `src/sattline_parser/utils/text_processing.py`, and the AST types live in `src/sattline_parser/models/ast_model.py`. The transformer root is `src/sattline_parser/transformer/sl_transformer.py`, with shared source-span extraction in `src/sattline_parser/transformer/_module_shared.py` and literal span attachment in `src/sattline_parser/transformer/_tokens_mixin.py`.

The validation layer sits in `src/sattlint/validation.py` and `src/sattlint/_validation_shared.py`. It runs after transformation, traverses the AST, and raises `StructuralValidationError` for hard failures. In some cases it can emit a warning instead of raising. The single-file and project-loading callers live in `src/sattlint/engine.py`, where `validate_single_file_syntax()` and the project loader collect validation warnings.

The analyzer registration and semantic aggregation layer lives in `src/sattlint/analyzers/`. `src/sattlint/analyzers/framework.py` defines the shared `AnalysisContext`, `AnalyzerSpec`, and `Issue` model. `src/sattlint/analyzers/_registry_spec_templates.py` and `src/sattlint/analyzers/_registry_specs.py` build the static analyzer catalog. `src/sattlint/analyzers/registry.py` is the central import-and-catalog owner. `src/sattlint/analyzers/_sattline_semantic_rules.py` and `src/sattlint/analyzers/_sattline_semantic_rules_data.py` define semantic rule metadata and contracts. `src/sattlint/analyzers/sattline_semantics.py` is the aggregator that currently calls many analyzers explicitly and translates their reports into a unified semantic report.

The editor-facing diagnostic path lives in `src/sattlint/core/diagnostics.py` and `src/sattlint/semantic_analysis.py`. In this repository, a diagnostic is the message eventually surfaced to the CLI or LSP with a source file, line, column, and message text. A module path is the case-insensitive list of module names used to match analyzer findings back to AST declaration sites. The current design has two finding shapes: generic analyzer `Issue` instances keyed by `module_path`, and `VariableIssue` instances keyed by variable definition lookup. Both are projected into `SemanticDiagnostic` values before they reach the LSP path tested by `tests/test_lsp_diagnostics.py`.

This plan is intentionally narrow. It does not rewrite the variable analyzer, does not add runtime plugin loading, and does not replace the AST model wholesale. It only hardens the existing seams so the current architecture scales better for future rule work.

## Plan of Work

Begin with parser position fidelity. Keep `strip_sl_comments(text) -> str` for existing callers, but add a new structured helper in `src/sattline_parser/utils/text_processing.py` that returns both the cleaned text and a mapping back to original source positions. Use that helper from `src/sattline_parser/api.py` so `describe_parse_error()` and any parse-failure formatting can convert the Lark position in cleaned text back to the original line and column. Do not change the grammar engine or the comment rules; the goal is only to preserve trustworthy error locations. In the same milestone, replace `_PROGRAM_NAME_RE` in `src/sattline_parser/transformer/sl_transformer.py` with a deterministic header parser that extracts the `name:` field from the header line without a free-form regex search, and stop using `SourceSpan(0, 0)` as a silent fallback for literal spans in `src/sattline_parser/models/ast_model.py`.

Next, harden validation notices. Introduce a structured notice type in `src/sattlint/_validation_shared.py`, for example `ValidationNotice`, that carries `message`, `line`, `column`, and `length`. Update `_warn_or_raise()` so warning mode emits that notice object instead of only a string. Thread the structured notice through `src/sattlint/validation.py` and `src/sattlint/engine.py`, keeping any user-facing warning text compatible by deriving strings from the structured notice at the CLI boundary rather than at the validation boundary. The important result is that callers retain location-rich warning data instead of losing it at the first sink.

Then harden semantic diagnostic projection. Promote the current private projection bookkeeping in `src/sattlint/core/diagnostics.py` into explicit result types that can carry both projected diagnostics and skipped findings. The implementation should record when a generic analyzer issue could not be matched to a module site and when a variable issue could not be matched to a definition span. Update `src/sattlint/semantic_analysis.py` to consume the projection result and preserve the current diagnostic output while also exposing projection-drop information for debug mode and tests. The first milestone does not need a new user-facing UI; it only needs to make the behavior observable and testable instead of silent.

Finally, consolidate semantic aggregation around declarative metadata. Extend the analyzer metadata seam under `src/sattlint/analyzers/_registry_spec_templates.py` so it can describe whether an analyzer contributes to the semantic report, how its report is mapped into `SemanticIssue` objects, and whether it supports LSP projection. Use that metadata to replace the manual analyzer call sequence and repeated `issues.extend(...)` mapping block in `src/sattlint/analyzers/sattline_semantics.py`. Keep the analyzer catalog static and explicit in `registry.py`, but remove the need to hand-edit the semantic aggregator every time a new rule family is added.

As each milestone lands, add focused tests before widening the surface. Parser-source-map and header tests belong in `tests/parser/test_parser_core.py` and `tests/parser/test_transformer.py`. Validation notice and single-file syntax behavior belong in `tests/parser/test_parser_validation.py` and `tests/parser/test_engine.py`. LSP and semantic projection behavior belong in `tests/test_lsp_diagnostics.py`. Analyzer-catalog and semantic-aggregation behavior belong in `tests/test_analyzers_suites.py` and `tests/test_app_analysis.py`.

## Concrete Steps

Run all commands from the repository root.

Inspect the owning seams before editing:

    rg -n "strip_sl_comments|describe_parse_error|parse_source_text|_PROGRAM_NAME_RE" src/sattline_parser/api.py src/sattline_parser/utils/text_processing.py src/sattline_parser/transformer/sl_transformer.py
    rg -n "_warn_or_raise|warning_sink|validate_transformed_basepicture" src/sattlint/_validation_shared.py src/sattlint/validation.py src/sattlint/engine.py
    rg -n "build_module_diagnostic_sites|project_report_issues_by_file|project_variable_issues_by_file|analyze_sattline_semantics" src/sattlint/core/diagnostics.py src/sattlint/semantic_analysis.py src/sattlint/analyzers/sattline_semantics.py
    rg -n "AnalyzerSpecTemplate|build_default_analyzers|RULE_CONTRACTS_BY_ID" src/sattlint/analyzers/_registry_spec_templates.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/_sattline_semantic_rules.py

Add the parser-position regression first. Use a temporary file with an inline comment before a syntax error and confirm the reported column still points to the original source, not the cleaned source:

    cat > /tmp/parser-location-inline-comment.s <<'EOF'
    "SyntaxVersion"
    "OriginalFileDate"
    "ProgramDate, name: Demo"
    BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
    LOCALVARIABLES
        DemoValue: integer := 0;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ModuleCode
        EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
            DemoValue = 1; (* inline comment *) ???
    ENDDEF (*BasePicture*);
    EOF
    bash scripts/run_repo_python.sh -m sattlint.app syntax-check /tmp/parser-location-inline-comment.s

Expected success signal after the parser-fidelity milestone: the error output still reports the original source line and a column at or after the `?` characters, not a column shifted left by removed comment text.

Run the focused parser and engine tests after the parser and validation edits:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_parser_core.py tests/parser/test_transformer.py tests/parser/test_parser_validation.py tests/parser/test_engine.py -x -q --tb=short

Run the focused diagnostics and analyzer-registration tests after the projection and semantic-aggregation edits:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_lsp_diagnostics.py tests/test_app_analysis.py tests/test_analyzers_suites.py -x -q --tb=short

Run the touched-file quality gates after the focused tests pass:

    bash scripts/run_repo_python.sh -m ruff check src/sattline_parser/api.py src/sattline_parser/utils/text_processing.py src/sattline_parser/models/ast_model.py src/sattline_parser/transformer/sl_transformer.py src/sattlint/_validation_shared.py src/sattlint/validation.py src/sattlint/engine.py src/sattlint/core/diagnostics.py src/sattlint/semantic_analysis.py src/sattlint/analyzers/_registry_spec_templates.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/sattline_semantics.py tests/parser/test_parser_core.py tests/parser/test_transformer.py tests/parser/test_parser_validation.py tests/parser/test_engine.py tests/test_lsp_diagnostics.py tests/test_app_analysis.py tests/test_analyzers_suites.py
    bash scripts/run_repo_python.sh -m pyright src/sattline_parser/api.py src/sattline_parser/utils/text_processing.py src/sattline_parser/models/ast_model.py src/sattline_parser/transformer/sl_transformer.py src/sattlint/_validation_shared.py src/sattlint/validation.py src/sattlint/engine.py src/sattlint/core/diagnostics.py src/sattlint/semantic_analysis.py src/sattlint/analyzers/_registry_spec_templates.py src/sattlint/analyzers/_registry_specs.py src/sattlint/analyzers/sattline_semantics.py tests/parser/test_parser_core.py tests/parser/test_transformer.py tests/parser/test_parser_validation.py tests/parser/test_engine.py tests/test_lsp_diagnostics.py tests/test_app_analysis.py tests/test_analyzers_suites.py

Expected final success signal: the focused pytest commands end with a `passed` summary and zero failures, Ruff prints `All checks passed!`, and Pyright reports `0 errors, 0 warnings, 0 informations`.

## Validation and Acceptance

Acceptance is behavior-focused. A user must be able to run `sattlint syntax-check` on a file whose parse error appears after an inline comment and still get the original source location, not a location based on stripped text. Parser-core tests must prove that header metadata extraction no longer depends on a free-form regex search and that literal spans are either real spans or explicitly absent rather than fake `(0, 0)` coordinates.

Validation warning acceptance requires that a warning-producing validation path still exposes location-rich notice data after it leaves `validation.py`. The CLI may still render warnings as text, but the engine and test surfaces must retain the structured warning object long enough for tests to assert line and column values.

Diagnostic projection acceptance requires that a finding with a missing module site or definition no longer disappears silently. The implementation may log, count, or collect dropped findings, but tests must be able to observe that the projection failed for a specific reason. LSP-facing diagnostics for valid issues must remain behavior-compatible with today’s output.

Rule-engine extensibility acceptance requires that adding a semantic analyzer family no longer requires a manual call-and-map block in `analyze_sattline_semantics()`. The semantic aggregation path should be driven by analyzer metadata, and the analyzer-suite tests must prove that declared analyzer metadata and semantic-rule aggregation stay in sync.

## Idempotence and Recovery

This plan is safe to execute incrementally. The parser-source-map helper should be added alongside the existing `strip_sl_comments()` function so callers can migrate without breaking in one large edit. The validation notice refactor should keep legacy string rendering at the boundary until all touched callers use the structured notice type. The diagnostic projection refactor should preserve the current `SemanticDiagnostic` output while adding explicit drop reporting so the behavior can be compared before and after.

If the parser source-map work proves unstable, keep the parser using cleaned text for parsing and limit the first recovery step to mapping error positions back to original coordinates in `describe_parse_error()` rather than changing any grammar behavior. If the semantic-aggregation consolidation grows too broad, stop at a compatibility adapter that derives semantic aggregation from metadata for one or two analyzer families first, then widen only after the analyzer-suite tests prove the pattern.

## Artifacts and Notes

Capture three short artifacts as the work progresses. The first is one `sattlint syntax-check` transcript from the inline-comment repro file showing the original source location. The second is one focused LSP or semantic-diagnostic test transcript showing that a valid issue still projects to the right file and line. The third is one short analyzer-suite transcript proving that semantic aggregation follows the analyzer metadata seam rather than a manual list.

Record one concise example of the new structured warning or projection-drop object once the implementation settles. Keep the example short, for example:

    ValidationNotice(message="unknown parameter target", line=12, column=9, length=7)

or:

    DroppedDiagnosticIssue(analyzer_key="variables", reason="missing-module-site", module_path=("BasePicture", "Child"))

These examples should be updated to the exact final names used in code.

## Interfaces and Dependencies

The parser milestone should leave `strip_sl_comments(text) -> str` intact for compatibility and add a new structured helper in `src/sattline_parser/utils/text_processing.py` that returns both cleaned text and source-position mapping. `src/sattline_parser/api.py` must use that helper for parse-error reporting. `src/sattline_parser/transformer/sl_transformer.py` must stop relying on `_PROGRAM_NAME_RE`, and `src/sattline_parser/models/ast_model.py` must stop manufacturing fake span coordinates for numeric literals.

The validation milestone must introduce a stable structured notice type in `src/sattlint/_validation_shared.py` and update `validate_transformed_basepicture()` in `src/sattlint/validation.py` plus the syntax-check and project-loader callers in `src/sattlint/engine.py` to pass and preserve those notice objects.

The diagnostic milestone must expose explicit projection result types from `src/sattlint/core/diagnostics.py` so `src/sattlint/semantic_analysis.py` can preserve both successful `SemanticDiagnostic` values and skipped-finding evidence. The user-facing `SemanticDiagnostic` shape should remain stable unless a compatibility adapter proves impossible.

The rule-engine milestone must keep the static analyzer catalog built by `src/sattlint/analyzers/_registry_spec_templates.py`, `src/sattlint/analyzers/_registry_specs.py`, and `src/sattlint/analyzers/registry.py`, but it must extend that metadata so `src/sattlint/analyzers/sattline_semantics.py` can iterate declaratively over semantic contributors instead of hand-coding one call and one mapping step per analyzer family. No runtime plugin loader is required or desired at the end of this plan.
