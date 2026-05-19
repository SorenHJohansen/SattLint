# T-Wave-8 Test Suite Fixture And Helper Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

## Purpose / Big Picture

This plan turns the 2026-05-19 tests-and-fixtures review into a concrete hardening slice for the repository test suite. After this work lands, the highest-risk test surfaces will be easier to navigate, the most brittle helper-heavy tests will depend less on private implementation details, and the missing negative and ambiguity scenarios called out by the review will be covered by focused deterministic tests.

The observable proof is that the corpus, artifact-contract, LSP workspace/navigation, app-menu, and GUI smoke-path suites all pass with new regression coverage; the most duplicated local test scaffolding is reduced in the touched areas; and the touched top-level test files point more clearly at their owning production surfaces.

## Progress

- [x] (2026-05-19) Create the ExecPlan from the test-suite, fixture, and helper review. Confirm the main risks: wrapper-style aggregator modules, direct testing of private helpers, over-coupled large fixture builders, duplicated micro-scaffolding, and missing negative-path scenarios in corpus, artifact-contract, LSP ambiguity, app integration, and GUI smoke coverage.
- [ ] Stabilize the highest-risk helper and fixture seams in the touched areas without broad rewrites.
- [ ] Add the missing negative and ambiguity scenarios in the corpus, artifact-contract, LSP, app-menu, and GUI slices.
- [ ] Reduce duplication in the variable/analyzer helper tests by centralizing repeated micro-builders used by the touched files.
- [ ] Improve owner alignment for the touched suites so test layout more clearly mirrors the production packages it validates.
- [ ] Run focused pytest, Ruff, and Pyright proof for the touched test and helper files, then record the results in this file.

## Surprises & Discoveries

- Observation: several of the largest public test entrypoints are only star-import wrappers over split shards.
  Evidence: `tests/test_repo_audit.py`, `tests/test_docgen.py`, `tests/test_analyzers_variables.py`, `tests/test_analyzers_state.py`, `tests/test_pipeline_collection.py`, `tests/parser/test_parser_core.py`, and `tests/parser/test_parser_validation.py` all exist primarily to re-export tests from `_part` modules.

- Observation: helper-coverage tests repeat the same lightweight stubs instead of sharing a narrow support seam.
  Evidence: `class _UsageStub` is defined separately in `tests/test_variables_helper_coverage.py`, `tests/test_variables_access_and_contract_helpers.py`, `tests/test_variables_execution.py`, and `tests/_analyzers_variables_test_support.py`. Small header helpers such as `_hdr()` are also repeated across many analyzer tests.

- Observation: some of the heaviest suites focus on private helper behavior rather than user-visible workflows.
  Evidence: `tests/test_lsp_diagnostics.py` directly exercises internal helper functions such as `_validated_text_document_uri`, `_normalize_workspace_diagnostics_mode`, `_merge_unique_diagnostics`, and `_definition_locations_from_candidates`. `tests/test_pipeline_owner_coverage.py` likewise targets private execution and parsing helpers directly.

- Observation: large shared fixture builders already exist, but they are concentrated in a few over-coupled modules instead of smaller behavior-specific builders.
  Evidence: `tests/_docgen_fixture_builders.py` constructs large `BasePicture` graphs reused across `tests/_docgen_part1.py` and `tests/_docgen_part2.py`, while app integration relies on opt-in environment-gated fixtures in `tests/_app_analysis_test_support.py` and `tests/_app_menus_support.py`.

- Observation: the test tree only partially mirrors the production tree.
  Evidence: `tests/analyzers/`, `tests/parser/`, and `tests/devtools/` map cleanly to `src/sattlint/analyzers/`, `src/sattline_parser/`, and `src/sattlint/devtools/`, but many other high-mass suites still live as top-level wrapper shells detached from their owner packages.

## Decision Log

- Decision: keep this slice focused on the highest-risk areas named in the review instead of flattening every split suite in one change.
  Rationale: the wrapper pattern is widespread, but a full-tree test reorganization would create a large, low-signal diff. This plan only reorganizes touched areas and establishes the pattern to continue later.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: prioritize behavior-facing regression coverage before helper cleanup when the same seam can serve both goals.
  Rationale: missing scenarios in `tests/parser/test_corpus.py`, `tests/test_artifact_contracts.py`, `tests/test_lsp_navigation.py`, `tests/test_lsp_rename_completion.py`, `tests/test_lsp_workspace_documents.py`, `tests/test_app_menus.py`, and the GUI smoke path provide more durable value than broad helper-only assertions.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: replace environment-gated "real context" test dependence with deterministic mini-project fixtures in touched app and GUI slices.
  Rationale: `SATTLINT_RUN_REAL_CONTEXT` based fixtures in `tests/_app_analysis_test_support.py` and `tests/_app_menus_support.py` create a gap between mocked unit tests and portable integration proof.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

- Decision: treat direct assertions on private helpers as acceptable only when no stable behavior-facing seam exists nearby.
  Rationale: some helper tests are still needed, but the default should be observable behavior through public commands, report payloads, and LSP request handlers.
  Date/Author: 2026-05-19 / Copilot (GPT-5.4)

## Outcomes & Retrospective

Fill this in after implementation. The final entry must state which missing scenarios were added, which helper duplications were consolidated, which wrapper or support files were slimmed or clarified, and whether the focused pytest, Ruff, and Pyright proof passed for the touched slice.

## Context and Orientation

This slice is about test quality, not production semantics. In this repository, the tests live under `tests/`, with the cleanest owner alignment already visible in `tests/analyzers/`, `tests/parser/`, and `tests/devtools/`. A "wrapper module" in this plan means a top-level test file that mostly imports tests from private shard files such as `_part1.py` or `_part2.py` instead of owning a coherent behavior-facing suite itself. A "support shard" means a shared test-only module such as `tests/_repo_audit_test_support.py` or `tests/_analyzers_variables_test_support.py`. A "fixture builder" means code that synthesizes reusable ASTs, project trees, or report payloads for tests, such as `tests/_docgen_fixture_builders.py` or `tests/helpers/lsp_support.py`.

The highest-risk files from the review fall into five groups. The first group is missing-scenario coverage: `tests/parser/test_corpus.py`, `tests/test_artifact_contracts.py`, `tests/test_lsp_navigation.py`, `tests/test_lsp_rename_completion.py`, `tests/test_lsp_workspace_documents.py`, `tests/test_app_menus.py`, `tests/test_app_analysis_project_cache.py`, `tests/test_gui.py`, `tests/test_gui_widgets.py`, and `tests/test_gui_frames_headless.py`. The second group is helper duplication in the variable-analysis tests: `tests/test_variables_helper_coverage.py`, `tests/test_variables_access_and_contract_helpers.py`, `tests/test_variables_execution.py`, and `tests/_analyzers_variables_test_support.py`. The third group is fixture coupling in `tests/_docgen_fixture_builders.py`, `tests/_app_analysis_test_support.py`, and `tests/_app_menus_support.py`. The fourth group is private-helper-heavy suites such as `tests/test_lsp_diagnostics.py` and `tests/test_pipeline_owner_coverage.py`. The fifth group is wrapper entrypoints such as `tests/test_docgen.py`, `tests/test_repo_audit.py`, and `tests/test_analyzers_variables.py`.

The plan does not require a full repository-wide migration away from split test shards. It only requires that the touched suites become easier to navigate and more owner-aligned than they are now. The clean model to follow already exists: package-shaped suites under `tests/parser/`, `tests/analyzers/`, and `tests/devtools/` that map directly to the corresponding production owners in `src/`.

## Plan of Work

Start with missing scenarios, because that yields the highest stability gain without large structure churn. Extend `tests/parser/test_corpus.py` with negative-path manifest coverage for malformed JSON, missing required fields, unsupported modes, and unsafe or non-repo-relative target paths if the corpus loader accepts them today. Extend `tests/test_artifact_contracts.py` with failing-schema coverage so the suite proves how contract drift is detected instead of only proving exact golden matches.

Then harden the LSP behavior seams. Add ambiguity and dirty-buffer coverage to the public request-path suites in `tests/test_lsp_navigation.py`, `tests/test_lsp_rename_completion.py`, and `tests/test_lsp_workspace_documents.py`. The missing case from the review is a same-name or same-filename dependency ambiguity where one document is dirty and multiple libraries provide the same apparent target. Add the new behavior tests near the current fallback and cache tests instead of expanding `tests/test_lsp_diagnostics.py`, because the goal is to cover public handler behavior rather than deepen private-helper coupling.

After that, replace the environment-gated app context path with deterministic small-project fixtures in the touched app suites. Add or extract minimal portable builders so `tests/test_app_menus.py` and `tests/test_app_analysis_project_cache.py` can exercise a real project-like path without relying on `SATTLINT_RUN_REAL_CONTEXT`. Reuse existing helper seams where possible, but keep each fixture focused on one behavior. Do not turn `tests/conftest.py` into a catch-all.

Next, add one real smoke-path GUI test under an environment guard or other stable portability seam so the GUI layer proves actual widget wiring in addition to fake-widget headless logic. Keep the bulk of GUI tests headless, but add one small end-to-end path in either `tests/test_gui_boot.py`, `tests/test_gui.py`, or `tests/test_gui_widgets.py` that demonstrates real callback wiring or event propagation.

Once the missing scenarios are covered, reduce duplication in the touched variable helper tests. Create a narrow shared seam for repeated `_UsageStub`, `_ns`, and `_hdr` scaffolding used by `tests/test_variables_helper_coverage.py`, `tests/test_variables_access_and_contract_helpers.py`, and `tests/test_variables_execution.py`. Keep it local to the variable helper area rather than creating a giant cross-suite helper module.

Finally, improve owner alignment for the touched suites. That does not mean flattening every wrapper file. It means that if a touched test file currently exists only to star-import shards, either move the new behavior tests into a more owner-aligned package path or make the wrapper file point more clearly at a coherent owning surface. For example, keep new corpus work in `tests/parser/test_corpus.py`, keep new LSP behavior work in the LSP request-path suites, and avoid adding more public-facing assertions to top-level wrapper shells.

## Concrete Steps

Run all commands from the repository root.

First, confirm the current structural hotspots and duplicate scaffolding before editing:

    find tests/ -name "*.py" -exec wc -l {} + | sort -rn | head -n 20
    rg -n '^from \._.* import \*$' tests
    rg -n 'class _UsageStub|def _hdr\(|def _ns\(' tests

Use those results only to guide touched-file cleanup. Do not widen the slice into a repo-wide reorganization.

Implement the first missing-scenario slice in the parser and artifact-contract tests, then run the narrow proof immediately:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/parser/test_corpus.py tests/test_artifact_contracts.py -x -q --tb=short

Implement the LSP ambiguity and dirty-buffer slice next, then rerun only the owning suites:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_lsp_navigation.py tests/test_lsp_rename_completion.py tests/test_lsp_workspace_documents.py -x -q --tb=short

Implement the app-menu and project-cache deterministic fixture slice next. If helper files change, include them in the same validation pass:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_app_menus.py tests/test_app_analysis_project_cache.py -x -q --tb=short

Implement the GUI smoke-path addition next and keep the proof tight:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_gui_boot.py tests/test_gui.py tests/test_gui_widgets.py tests/test_gui_frames_headless.py -x -q --tb=short

When the variable helper scaffolding is consolidated, run the local helper-focused proof:

    bash scripts/run_repo_python.sh -m pytest --no-cov tests/test_variables_helper_coverage.py tests/test_variables_access_and_contract_helpers.py tests/test_variables_execution.py tests/test_analyzers_variables.py -x -q --tb=short

After each Python test slice passes, run touched-file static proof on the changed Python tests and helpers. Replace the file list with the actual touched paths:

    bash scripts/run_repo_python.sh -m ruff check tests/parser/test_corpus.py tests/test_artifact_contracts.py tests/test_lsp_navigation.py tests/test_lsp_rename_completion.py tests/test_lsp_workspace_documents.py tests/test_app_menus.py tests/test_app_analysis_project_cache.py tests/test_gui_boot.py tests/test_gui.py tests/test_gui_widgets.py tests/test_gui_frames_headless.py tests/test_variables_helper_coverage.py tests/test_variables_access_and_contract_helpers.py tests/test_variables_execution.py tests/_app_analysis_test_support.py tests/_app_menus_support.py tests/helpers/lsp_support.py
    bash scripts/run_repo_python.sh -m pyright tests/parser/test_corpus.py tests/test_artifact_contracts.py tests/test_lsp_navigation.py tests/test_lsp_rename_completion.py tests/test_lsp_workspace_documents.py tests/test_app_menus.py tests/test_app_analysis_project_cache.py tests/test_gui_boot.py tests/test_gui.py tests/test_gui_widgets.py tests/test_gui_frames_headless.py tests/test_variables_helper_coverage.py tests/test_variables_access_and_contract_helpers.py tests/test_variables_execution.py tests/_app_analysis_test_support.py tests/_app_menus_support.py tests/helpers/lsp_support.py

If wrapper-file cleanup is performed in a touched area, rerun the narrow owner suite immediately after that refactor rather than waiting for a final aggregate run.

## Validation and Acceptance

Acceptance is behavioral. `tests/parser/test_corpus.py` must fail before the new negative manifest checks and pass after them, proving that malformed or incomplete corpus definitions are handled intentionally. `tests/test_artifact_contracts.py` must prove that schema drift is caught, not only that current goldens match. The LSP suites must demonstrate a dirty-buffer or ambiguous-dependency scenario through public request handlers, not by adding more direct assertions on helper internals. The app suites must exercise a deterministic mini-project path without requiring `SATTLINT_RUN_REAL_CONTEXT=1`. The GUI suites must include one small real smoke path in addition to the existing headless fakes.

The static acceptance bar is that every touched Python test or helper file is clean under focused Ruff and Pyright runs. The structural acceptance bar is that touched areas become more owner-aligned than before: new tests should land in package-shaped suites where possible, and duplicated local scaffolding should shrink rather than grow.

## Idempotence and Recovery

This slice is safe to execute incrementally. Each scenario addition or helper cleanup should be landed with its own narrow validation. Re-running the inspection and pytest commands is harmless. If a proposed fixture consolidation starts pulling unrelated suites into failure, stop and cut the seam back to the smallest local helper shared by the touched files only. If a GUI smoke test is unstable in headless CI, recover by keeping the stable headless assertions and gating the real-widget smoke path behind an explicit environment or availability check rather than deleting the entire behavioral proof.

Do not move large numbers of wrapper or shard files just to make the tree look cleaner. If a migration turns into a naming-only churn pass without improving behavior or validation, back out to the last passing narrow slice and continue with the missing-scenario work first.

## Artifacts and Notes

Facts captured from the review that this plan must address:

    Largest public test files include:
      tests/test_pipeline_run.py
      tests/test_lsp_diagnostics.py
      tests/parser/test_engine.py
      tests/test_editor_api.py
      tests/test_app_menus.py

    Repeated pattern counts gathered during review:
      from .* import * wrappers in tests: 113
      _resolve_python_executable stubs in tests: 26
      _build_documentation_fixture() uses in docgen shards: 10

    Duplicated local stubs confirmed during review:
      class _UsageStub in four variable-helper support paths
      many repeated _hdr() helpers across analyzer tests

    Missing scenarios prioritized by the review:
      malformed corpus manifests
      artifact-contract drift failures
      LSP same-name ambiguity with dirty buffers
      deterministic app integration without SATTLINT_RUN_REAL_CONTEXT
      one real GUI widget smoke path

## Interfaces and Dependencies

The main production interfaces exercised by this plan are `src/sattlint/devtools/corpus.py`, the artifact-report payload builders consumed by `tests/test_artifact_contracts.py`, the LSP request handlers in `src/sattlint_lsp/`, the app loading and menu surfaces in `src/sattlint/app.py`, `src/sattlint/app_base.py`, and `src/sattlint/app_analysis.py`, and the GUI binding and widget surfaces in `src/sattlint_gui/`.

Reuse existing narrow helper seams before creating new ones. `tests/helpers/artifact_assertions.py` is the right place for shared artifact-contract assertions. `tests/helpers/lsp_support.py` is the right place for small reusable LSP source builders and file-writing helpers. Variable-helper scaffolding should stay local to the variable-analysis test area rather than becoming a cross-repo dumping ground. Do not add external dependencies for this slice. Use the existing repo venv commands, existing test helpers, and existing package-shaped suite layout as the stable interfaces.
