# Tech Debt Tracker

Living document of known technical debt in SattLint.
Updated by doc-gardening agent and human developers.
Last updated: 2026-05-15

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

Active follow-on plans from the 2026-05-15 architecture debt review:

- `docs/exec-plans/active/40-t-wave-6-pipeline-and-audit-catalog-extraction.md` covers the oversized pipeline and repo-audit coordination surfaces plus adjacent pipeline test debt.
- `docs/exec-plans/active/41-t-wave-6-app-config-and-doc-gardener-surface-split.md` covers the app-analysis, config, and doc-gardener control-surface split.
- `docs/exec-plans/active/42-t-wave-6-parser-module-normalization-split.md` covers the parser module-normalization mixin split.
- `docs/exec-plans/active/43-t-wave-6-analyzer-owner-splits.md` covers the remaining oversized analyzer owners and helper facades.
- `docs/exec-plans/active/44-t-wave-6-lsp-server-and-test-split.md` covers the LSP server, helper-coverage, and oversized LSP test split.
- `docs/exec-plans/active/45-t-wave-6-gui-test-and-coverage-ratchet.md` covers the GUI test bottleneck and lowest GUI coverage ratchets.
- `docs/exec-plans/active/50-t-wave-7-public-1-0-release-readiness.md` covers the cross-cutting `1.0.0` public-release contract, packaging rehearsal, version alignment, and community-facing repo polish required before the first stable tag.

---

## Scan Log

| Date | Findings | Action Taken |
|------|-----------|--------------|
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
