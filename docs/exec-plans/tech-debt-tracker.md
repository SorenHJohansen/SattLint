# Tech Debt Tracker

Living document of known technical debt in SattLint.
Updated by doc-gardening agent and human developers.
Last updated: 2026-06-01

Active work now lives in:

- `docs/exec-plans/active/`

Completed debt closeouts live in:

- `docs/exec-plans/completed/`

This tracker remains valid for legacy TD-* entries, still-open tech debt, and scan history.

## Consolidation Source Ledger

| Source | State | Snapshot | Sync Basis | Coverage | Notes |
|---|---|---|---|---|---|
| TODO_GUI.md | retired | 2026-05-01 | retired | Program E | Legacy GUI backlog retired into roadmap and exec-plan tracking. |
| TODO_REFACTOR.md | retired | 2026-05-01 | retired | Program T | Legacy refactor backlog retired into the consolidated tech-debt tracker and exec-plan tracking. |
| TODO_SATTLINT.md | retired | 2026-05-01 | retired | Program C | Legacy SattLint backlog retired into roadmap and exec-plan tracking. |
| TODO_TOOLS.md | retired | 2026-05-01 | retired | Program D | Legacy tools backlog retired into the consolidated tech-debt tracker and exec-plan tracking. |

The consolidation source ledger is the single source of truth for legacy `TODO_*.md` source status. The doc-gardener source-drift scan derives retired-source behavior from these rows rather than from a second hard-coded list.

## Program T: Technical Debt Items

Program T debt with active ownership now lives in the ExecPlans below. The tracker no longer duplicates the full debt text once a plan exists.

Recent completed closeouts:

- `docs/exec-plans/completed/33-t-wave-1-config-and-type-foundations.md` covers the earlier config and type-foundation cleanup.
- `docs/exec-plans/completed/34-t-wave-1-doc-gardener-pipeline-consumption.md` covers the earlier doc-gardener pipeline-consumption slice.
- `docs/exec-plans/completed/35-t-wave-2-workspace-hot-reload.md` covers the earlier workspace hot-reload slice.
- `docs/exec-plans/completed/36-t-wave-4-analyzer-refactor-follow-ons.md` covers the earlier analyzer follow-on split.
- `docs/exec-plans/completed/37-t-wave-4-repo-audit-decomposition.md` covers the earlier repo-audit shrink slice.
- `docs/exec-plans/completed/38-t-wave-5-analyzer-coverage-follow-ons.md` covers the earlier analyzer coverage closeout.
- `docs/exec-plans/completed/39-t-wave-5-parser-failure-logging.md` covers the earlier parser logging slice.
- `docs/exec-plans/completed/43-t-wave-6-analyzer-owner-splits.md` covers the earlier oversized analyzer-owner split.
- `docs/exec-plans/completed/45-t-wave-6-gui-test-and-coverage-ratchet.md` covers the earlier GUI-test and coverage-ratchet slice.

Active follow-on plans from the 2026-05-15 architecture debt review:

- `docs/exec-plans/completed/40-t-wave-6-pipeline-and-audit-catalog-extraction.md` covers the oversized pipeline and repo-audit coordination surfaces plus adjacent pipeline test debt.
- `docs/exec-plans/completed/41-t-wave-6-app-config-and-doc-gardener-surface-split.md` covers the app-analysis, config, and doc-gardener control-surface split.
- `docs/exec-plans/completed/42-t-wave-6-parser-module-normalization-split.md` covers the parser module-normalization mixin split.
- `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md` covers the cross-cutting `1.0.0` public-release contract, packaging rehearsal, version alignment, community-facing repo polish, and public-doc truthfulness required before the first stable tag.
- `docs/exec-plans/completed/58-t-wave-8-ci-workflow-consolidation-and-release-rehearsal.md` covers GitHub Actions consolidation, shared CI setup, release rehearsal wiring, AI-only workflow-doc alignment, and stale or ceremonial automation cleanup.

Active follow-on plan from the 2026-05-19 test-suite, fixture, and helper review:

- `docs/exec-plans/active/59-t-wave-8-test-suite-fixture-helper-hardening.md` covers behavior-over-implementation test hardening, duplicated helper and fixture scaffolding, and the highest-count suites that still provide low confidence.

Active follow-on plan from the 2026-05-19 parser, diagnostics, and rule-engine review:

- `docs/exec-plans/active/60-c-wave-parser-diagnostics-and-rule-engine-hardening.md` covers parser-location fidelity, structured validation notices, diagnostic projection visibility, and consolidation of competing parser or error-reporting styles.

Active follow-on plans from the 2026-05-18 strict-typing inventory review:

- `docs/exec-plans/completed/51-t-wave-7-parser-strict-typing-promotion.md` covers the remaining parser strict blocker plus the uncovered parser transformer helper files.
- `docs/exec-plans/active/52-t-wave-7-lsp-strict-typing-promotion.md` covers the uncovered LSP helper files.
- `docs/exec-plans/active/53-t-wave-7-core-support-strict-typing-promotion.md` covers the uncovered semantic-core, reporting, resolution, and simulation support files.
- `docs/exec-plans/completed/54-t-wave-7-app-config-strict-typing-promotion.md` covers the current app or config strict blocker plus the uncovered app-side helper files.
- `docs/exec-plans/completed/55-t-wave-7-devtools-strict-typing-promotion.md` covers the uncovered devtools surface and the remaining devtools debt-allowlist exits.
- `docs/exec-plans/completed/56-t-wave-7-analyzers-strict-typing-promotion.md` covers the uncovered analyzer helper and domain-analyzer files.

Active follow-on plan from the 2026-05-19 repo-map and architecture review:

- `docs/exec-plans/completed/58-t-wave-8-repo-structure-and-architecture-alignment.md` covers canonical root-layout cleanup, architecture-doc alignment, the undocumented GUI and editor-facade surfaces, stale `arch_linter` naming, and one explicit map of the actual runtime architecture.

Active follow-on plan from the 2026-05-19 security review:

- `docs/exec-plans/active/61-t-wave-8-repo-security-and-supply-chain-hardening.md` covers release trust-boundary tightening, workflow-security policy enforcement, legacy helper-script removal, and complete Python-plus-Node dependency monitoring.

Active follow-on plans from the 2026-05-19 performance and scalability review:

- `docs/exec-plans/active/67-t-wave-9-analyzer-execution-performance-hardening.md` covers analyzer batch execution reuse, semantic rerun elimination, shared per-target artifacts for the variable-family analyzers, and the follow-on measurement path for standalone performance-adjacent subsystems such as graphics, layout, and ICF validation.
- `docs/exec-plans/active/68-t-wave-9-project-loading-pipeline-performance-hardening.md` covers project-cache manifest separation, file-AST validation de-duplication, project-payload size reduction, and safe parallelization of sibling dependency loading in the project-loader hot path.

Active follow-on plan from the 2026-05-19 CLI UX review:

- `docs/exec-plans/completed/63-t-wave-8-cli-ux-and-documentation-trustworthiness.md` covers top-level CLI flag discoverability, actionable output and exit-code consistency, repo-audit alias help parity, and reproducible command examples in the README and CLI reference.

Active follow-on plan from the 2026-05-19 maintainability blind-spot review:

- `docs/exec-plans/completed/64-t-wave-8-maintainer-blind-spot-reconciliation.md` turns the broad review into one durable routing artifact, closes the remaining retired-TODO source-ledger seam in doc-gardener, records which existing active plans own the other suspicious paths, and names the active owners for duplicate abstractions, unused sophistication, disconnected systems, architecture entropy, hallucination residue, and runtime-architecture mapping.
- Use that plan as the canonical routing artifact for the 2026-05-19 blind-spot review so suspicious maintainability findings map to an owning active plan instead of chat-only history.

Active follow-on plan from the 2026-06-01 analyzer architecture-drift review:

- `docs/exec-plans/active/66-t-wave-9-analyzer-architecture-drift-hardening.md` covers analyzer registry key normalization, analyzer-specific drift-prevention guardrails, private helper-module naming, import-style consistency, and the first shared traversal plus origin-helper consolidation inside `src/sattlint/analyzers/`.

---

## Scan Log

| Date | Findings | Action Taken |
|------|-----------|--------------|
| 2026-05-19 | 1 findings | Doc-gardening scan |
| 2026-05-19 | 0 findings | Doc-gardening scan |
| 2026-05-19 | 1 findings | Doc-gardening scan |
| 2026-05-15 | 0 findings | Doc-gardening scan |
| 2026-05-15 | 0 findings | Doc-gardening scan |
| 2026-05-06 | 0 findings | Doc-gardening scan |
| 2026-05-04 | 264 findings | Doc-gardening scan |
| 2026-05-01 | 0 findings | Doc-gardening scan |
| 2026-04-30 | 15 items | Manual tech debt review and update to exec-plan template |
| 2026-04-29 | 1 findings | Doc-gardening scan |
| 2026-04-29 | 1 findings | Doc-gardening scan |
| 2026-04-28 | 0 findings | Doc-gardening scan |
| 2026-04-28 | 1 findings | Doc-gardening scan |
| 2026-04-28 | 0 findings | Doc-gardening scan |
| 2026-04-28 | AGENTS.md 172?100 lines, docs/ restructuring | Initial restructure |
| (next scan due: weekly via CI) | | |

## Debt Categories

- **Critical**: Blocks features, causes data loss, security issue
- **High**: Affects reliability, performance, or user experience
- **Medium**: Code smell, missing feature, incomplete coverage
- **Low**: Nice-to-have, cosmetic, future-proofing
