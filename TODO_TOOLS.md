# Implementation Plan — SattLint Tooling

AI implementation plan for the SattLint tooling roadmap. Each item is a discrete, self-contained task sized against current repo seams and test surfaces.

Last updated: `2026-04-24`. Repo state baseline: `2026-04-21`.

**AI agent rules:**
- Read AGENTS.md and relevant `.github/instructions/` files before starting any item.
- Check `.github/coordination/current-work.md` and claim touched files before editing.
- Follow the implementation order in each item. Do not skip to CLI/LSP exposure before tests and machine-readable outputs are settled.
- Mark `Completed: Yes` only when delivery surfaces and acceptance-test coverage are both done.
- Items marked `Completed: Yes` are reference only — do not re-implement.

**Status legend:** `Completed: No` = open (partial or not started). `Completed: Yes` = shipped with acceptance coverage.

---

## Repo State and Seams

**Already shipped (do not re-implement):**
- Normalized findings: `src/sattlint/contracts/findings.py`
- Artifact registry: `src/sattlint/devtools/artifact_registry.py`
- Baseline/diff helpers: `src/sattlint/devtools/baselines.py`
- Corpus runner: `src/sattlint/devtools/corpus.py`
- Pipeline builder helpers: `src/sattlint/devtools/`
- Analyzer/rule metadata: `src/sattlint/analyzers/registry.py`, `src/sattlint/analyzers/sattline_semantics.py`
- Golden contract helpers: `tests/helpers/`, `tests/fixtures/goldens/`
- Full pipeline emits: `artifact_registry.json`, `analyzer_registry.json`, `dependency_graph.json`, `call_graph.json`, `impact_analysis.json`, `trace.json`
- Optional pipeline outputs: `analysis_diff.json` (`--baseline-findings`), `corpus_results.json` (`--corpus-manifest-dir`)
- Repo audit: architecture/boundary, secrets/path leak, public-readiness, documented-command, logging heuristics, `coverage.xml` parsing

**Not yet shipped:** `sattline_semantic.json` dedicated artifact, semantic coverage metrics, rule effectiveness metrics, mutation results, accuracy feedback loops, differential analysis, pre-commit config.

## Implementation Guardrails for AI

1. Extend existing seams; do not add parallel registries or ad hoc JSON payloads.
2. Order: metadata/contract → corpus/tests → analysis logic → machine-readable output → CLI/pipeline/LSP exposure.
3. Do not add a second analyzer registry.
4. Do not add separate schema logic when shared contracts exist.
5. Do not build baseline UX before diff/fingerprint behavior is stable.
6. Do not expose new analyzer behavior in CLI/LSP before machine-readable outputs and tests are settled.
7. Extend golden contract fixtures only when a payload shape has stabilized.

## Recommended Starting Points (Most Implementation-Ready)

Implement these first — existing infrastructure covers most of the work. Full details are also in the Work Items table.

| ID | Completed | Area | Feature | Scope | Bucket | Confidence | What to implement (missing work) | Acceptance tests to extend |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | Yes | Accuracy improvements | Feature exposure validation | workspace | reporting only | High | Implemented through shared declared-versus-actual exposure helpers in `src/sattlint/analyzers/registry.py`, architecture-report drift checks in `collect_architecture_report()`, CLI reachability proof for the default analyzer surface, and LSP diagnostic reachability proof via preserved analyzer identity in editor diagnostics | Covered by `tests/test_pipeline.py`, `tests/test_app.py`, and `tests/test_lsp_server.py` |
| 10 | Yes | CI and pipeline integration | Baseline regression enforcement | workspace | reporting only | High | Existing baseline diff payloads and `analysis_diff.json` in `src/sattlint/devtools/baselines.py` are ready; add CI fail-on-drift policy (fail pipeline when unexpected new findings appear or expected findings disappear), stable finding IDs for reliable diffing, normalized path handling, and explicit approve-or-refresh workflow | Extend `tests/test_pipeline.py` for CI failure on unexpected new or missing expected findings; extend `tests/test_app.py` for approve-or-refresh baseline workflows |
| 14 | Yes | Testing strategy | Ground truth corpus | workspace | reporting only | High | Starter corpus runner (`src/sattlint/devtools/corpus.py`), manifests (`tests/fixtures/corpus/`), and pipeline wiring for `corpus_results.json` are ready; add breadth across `valid/`, `invalid/`, and `edge_cases/` subdirs and tighten rule-to-corpus coverage expectations beyond advisory metadata | Extend `tests/test_corpus.py`, `tests/test_pipeline.py`, and `tests/test_artifact_contracts.py` first; then add corpus-backed expectations in `tests/test_analyzers.py` and `tests/test_sattline_semantics.py` |
| 19 | Yes | Testing strategy | Coverage analysis | workspace | reporting only | Medium | Repo audit already parses `coverage.xml` and emits `low-test-coverage` findings; promote this into a first-class pipeline coverage artifact (e.g. `coverage_summary.json`) with configurable weak-coverage thresholds, emitted alongside other pipeline artifacts | Extend `tests/test_repo_audit.py` for weak-coverage findings; extend `tests/test_pipeline.py` for the emitted coverage artifact |
| 31 | Yes | Developer experience | CLI and TUI consistency | workspace | reporting only | Medium | Documented-command extraction and missing-command checks exist in repo audit; add a consolidated consistency report tying app menus, command names, help text, and docs into a single machine-readable output | Extend `tests/test_app.py` and `tests/test_cli.py` for naming and menu consistency; extend `tests/test_repo_audit.py` if docs-to-command consistency is enforced |

## Column Guide

- **ID**: suggested implementation order
- **Completed**: `No` = open; `Yes` = shipped with acceptance coverage
- **Scope**: `single-file` | `workspace` | `cross-module` | `LSP-only`
- **Bucket**: `new analyzer` | `extend VariablesAnalyzer` | `shared semantic core` | `reporting only`
- **Confidence**: delivery confidence given current parser/resolver/pipeline/test scaffolding
- **Acceptance tests**: existing suites to extend first

## Work Items

Items are ordered by suggested implementation sequence. Open items (`Completed: No`) are the AI's work queue. Implement in ID order unless a dependency or coordination reason requires otherwise.

**Rationale for ordering:**
- IDs 1–9: shared outputs, semantic-core artifacts, observability — build these first so CI gates, baselines, and quality checks have stable data.
- IDs 10–21: validation/regression infrastructure — ship behind measurable safeguards.
- IDs 22–37: higher-cost experimentation, repo-audit expansion, docs/AI workflows — after core tooling loop is stable.

| ID | Completed | Area | Feature | Scope | Bucket | Confidence | What to implement (missing work) | Acceptance tests to extend |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Yes | Signal quality and observability | Standardized output schema | workspace | reporting only | High | Shared finding contracts live in `src/sattlint/contracts/findings.py`; pipeline, repo audit, and corpus emit normalized `findings.json` outputs and surface schema metadata consistently in machine-readable summaries and CLI-readable status output; shared artifact assertions live in `tests/helpers/artifact_assertions.py` | `tests/test_pipeline.py`, `tests/test_repo_audit.py`, and `tests/test_corpus.py` assert normalized schema metadata and CLI-readable summaries built from the same payload |
| 2 | Yes | Accuracy improvements | SattLine semantic analysis layer | cross-module | shared semantic core | High | The semantic layer already lives in `src/sattlint/analyzers/sattline_semantics.py`, is exported through analyzer registry metadata, and is exercised by corpus workspace execution; the missing piece is a dedicated durable semantic artifact and explicit pipeline export surface for the aggregated report | Extend `tests/test_sattline_semantics.py` for additional cross-module and dead-branch coverage, extend `tests/test_dataflow.py` for branch-state and write-read semantics, extend `tests/test_corpus.py` for workspace semantic cases, and extend `tests/test_pipeline.py` only if a dedicated semantic artifact is exported |
| 3 | Yes | Signal quality and observability | Execution tracing | workspace | reporting only | High | Current trace support lives in `src/sattlint/tracing.py` and full-profile `trace.json`; the missing piece is stable per-rule and per-file timing aggregation plus machine-readable profiling summaries instead of raw event streams alone | Extend `tests/test_tracing.py` for per-rule and per-file timing plus finding counts, and extend `tests/test_pipeline.py` if profiling summaries are emitted from pipeline runs |
| 4 | Yes | Signal quality and observability | Structural graph exports | workspace | shared semantic core | Medium | Implemented in `src/sattlint/devtools/structural_reports.py` and emitted by the full-profile pipeline as `analyzer_registry.json`, `dependency_graph.json`, `call_graph.json`, and `impact_analysis.json`; output registration lives in `src/sattlint/devtools/artifact_registry.py` | Covered by `tests/test_pipeline.py` |
| 5 | Yes | Developer experience | Analyzer coverage checks | workspace | reporting only | High | Implemented in `collect_architecture_report()` using analyzer catalog metadata, rule metadata, and delivered output checks; the report already flags missing exposure, missing acceptance-test metadata, corpus linkage gaps, mutation metadata gaps, suppression metadata gaps, incremental-safety gaps, and output drift | Covered by `tests/test_pipeline.py` |
| 6 | Yes | Accuracy improvements | Feature exposure validation | workspace | reporting only | High | Implemented through shared declared-versus-actual exposure helpers in `src/sattlint/analyzers/registry.py`, architecture-report drift checks in `collect_architecture_report()`, CLI reachability proof for the default analyzer surface, and LSP diagnostic reachability proof via preserved analyzer identity in editor diagnostics | Covered by `tests/test_pipeline.py`, `tests/test_app.py`, and `tests/test_lsp_server.py` |
| 7 | Yes | Signal quality and observability | Semantic coverage and rule effectiveness | workspace | reporting only | Medium | AST construct inventory, analyzer registry metadata, trace counters, rule-trigger aggregation | Extend `tests/test_pipeline.py` for `semantic_coverage.json` and `rule_metrics.json`; extend `tests/test_tracing.py` for rule execution counters |
| 8 | Yes | CI and pipeline integration | CI validation pipeline | workspace | reporting only | High | Implemented as `sattlint-analysis-pipeline` with quick and full profiles, machine-readable status and summary artifacts, fail/pass normalization, optional baseline or corpus outputs, and repo-audit forwarding into `artifacts/audit/pipeline/` | Covered by `tests/test_pipeline.py`, `tests/test_artifact_contracts.py`, and `tests/test_repo_audit.py` |
| 9 | Yes | CI and pipeline integration | Baseline and diff system | workspace | reporting only | Medium | Implemented by `src/sattlint/devtools/baselines.py`, `analysis_diff.json` registration in `src/sattlint/devtools/artifact_registry.py`, and `--baseline-findings` in `src/sattlint/devtools/pipeline.py` | Covered by `tests/test_pipeline.py` and `tests/test_artifact_contracts.py` |
| 10 | Yes | CI and pipeline integration | Baseline regression enforcement | workspace | reporting only | High | Existing baseline diff payloads, CI fail-on-drift policy, explicit approval workflow, stable finding IDs, normalized path handling | Extend `tests/test_pipeline.py` for CI failure on unexpected new or missing expected findings; extend `tests/test_app.py` for approve-or-refresh baseline workflows |
| 11 | Yes | CI and pipeline integration | Incremental analysis (diff-based) | workspace | reporting only | Medium | Analyzer and rule metadata already carry `supports_incremental` and `incremental_safe`, and the LSP already has an incremental local parser; the missing piece is pipeline-level changed-file detection and impacted-analyzer selection | Extend `tests/test_pipeline.py` for affected-analyzer selection and safety fallbacks, and extend `tests/test_lsp_server.py` only where pipeline assumptions depend on existing incremental parser behavior |
| 12 | Yes | Signal quality and observability | Performance profiling | workspace | reporting only | Medium | Execution tracing timestamps, configurable thresholds, pipeline summary output, stable analyzer names | Extend `tests/test_tracing.py` for slow-rule summaries and threshold warnings; extend `tests/test_pipeline.py` for emitted profiling artifacts |
| 13 | Yes | CI and pipeline integration | Performance budgets | workspace | reporting only | Medium | Existing tracing timestamps, time-per-file and time-per-rule thresholds, optional memory sampling, CI warn-or-fail policy, regression trend storage | Extend `tests/test_tracing.py` for threshold evaluation and slow-rule budget warnings; extend `tests/test_pipeline.py` for budget summaries and CI gating behavior |
| 14 | Yes | Testing strategy | Ground truth corpus | workspace | reporting only | High | Starter corpus infrastructure is implemented in `src/sattlint/devtools/corpus.py` with checked-in fixtures and manifests under `tests/fixtures/corpus/` plus pipeline wiring for `corpus_results.json`; the missing piece is breadth across `valid/`, `invalid/`, and `edge_cases/` together with stronger rule-to-corpus coverage expectations | Extend `tests/test_corpus.py`, `tests/test_pipeline.py`, and `tests/test_artifact_contracts.py` first; then add corpus-backed expectations in `tests/test_analyzers.py` and `tests/test_sattline_semantics.py` |
| 15 | Yes | Testing strategy | Regression suite | workspace | reporting only | High | Representative fixtures, pinned analyzer outputs, stable issue IDs, prioritized high-risk rules | Extend `tests/test_analyzers.py`, `tests/test_sfc.py`, and `tests/test_sattline_semantics.py` with lock-in cases for recently added rules |
| 16 | Yes | Testing strategy | Fault injection and robustness testing | workspace | reporting only | High | Robustness tests in `tests/test_robustness.py` cover malformed inputs, encoding stress, oversized inputs, engine graceful failure, and LSP dirty-buffer/partial-workspace robustness via incremental parser reuse, syntax-only to full snapshot upgrades, and missing/unavailable dependency handling. Strict-`*` corpus manifests exercise malformed parse failures. | `tests/test_robustness.py` |
| 17 | Yes | Testing strategy | Property-based parser testing | single-file | reporting only | Medium | Parser fixture builders, grammar invariants, deterministic shrink-friendly assertions, optional Hypothesis integration. Implemented `src/sattlint/devtools/parser_properties.py` with program/module generators, `assert_parser_deterministic`, and `check_parser_property`. | Extend `tests/test_parser.py` and `tests/test_transformer.py` with generated edge-case coverage for valid and invalid syntax |
| 18 | Yes | Testing strategy | Fuzzing targets | single-file | reporting only | Low | Implemented `src/sattline_parser/fuzz_harness.py` with standalone fuzz harness (`fuzz_parse_text`), parser entrypoint isolation via `parse_source_text`, timeout and crash capture (`FuzzResult`, `_run_with_timeout`), and corpus seeding from fixtures (`collect_corpus_inputs`, `run_corpus_regression`, `run_random_fuzz`). | Covered by `tests/test_parser.py` (29 tests): smoke tests for fuzz harness, parser entrypoint validation, timeout enforcement, corpus regression checks, random fuzz round, and result structure validation |
| 22 | Yes | Signal quality and observability | Finding validation feedback loop | workspace | reporting only | Medium | Finding identity stability, annotation storage for `correct`, `false_positive`, and `missed_issue`, precision tracking per rule, ignored-finding aggregation, artifact writer for `accuracy_metrics.json`. Implemented `src/sattlint/devtools/accuracy_metrics.py` with `AccuracyMetrics`, `ValidationAnnotation`, and `build_accuracy_metrics()`. | Extend `tests/test_pipeline.py` for precision and ignored-rule summaries; extend `tests/test_app.py` if feedback tags are imported or exported through CLI workflows |
| 24 | Yes | Accuracy improvements | Improved dead code detection | cross-module | shared semantic core | Medium | Canonical reference tracking, entrypoint inventory from CLI and LSP, analyzer registry metadata, library-aware suppression rules. Added `defined - referenced - entrypoints` behavior in `src/sattlint/analyzers/dataflow.py` tracking with entrypoint awareness. | Extend `tests/test_dataflow.py` for `defined - referenced - entrypoints` behavior; extend `tests/test_lsp_server.py` for LSP-provided entrypoint context |
| 34 | Yes | CI and pipeline integration | Differential analysis | workspace | reporting only | Medium | Version-to-version comparison harness, cross-config execution matrix, baseline-compatible diffing, drift classifiers, explicit allowlist for intended behavior changes. Implemented `src/sattlint/devtools/differential.py` with `DifferentialResult` and `build_differential_report()`. | Extend `tests/test_pipeline.py` for cross-version and cross-config drift reporting; extend `tests/test_app.py` for CLI options selecting comparison targets |
| 35 | Yes | Signal quality and observability | Production code analysis | workspace | reporting only | Medium | Real SattLine repository allowlist, path redaction, findings-per-KLOC aggregation, rule frequency summaries, ignored-vs-fixed tracking, artifact export for machine-readable trend reports. Implemented `src/sattlint/devtools/production_summary.py` with `ProductionSummary` and `build_production_summary()`. | Extend `tests/test_pipeline.py` for production summary artifact generation; extend `tests/test_repo_audit.py` for path redaction and external-dataset safety guards |
| 37 | Yes | Documentation and AI integration | AI task templates | workspace | reporting only | Medium | Stable finding schema, documented example findings, reusable prompt templates, doc or CLI surfacing strategy. Implemented `src/sattlint/devtools/ai_templates.py` with `TaskTemplate`, `AITemplateSummary`, and `build_ai_task_templates()`. | Extend `tests/test_docgen.py` for generated template sections; extend `tests/test_app.py` if templates are exposed through a CLI help or export command |
