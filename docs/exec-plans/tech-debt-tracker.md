# Tech Debt Tracker

Living document of known technical debt in SattLint.
Updated by doc-gardening agent and human developers.
Last updated: 2026-05-13

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

- `docs/exec-plans/active/33-t-wave-1-config-and-type-foundations.md` covers T-005 and T-008.
- `docs/exec-plans/active/34-t-wave-1-doc-gardener-pipeline-consumption.md` covers T-006.
- `docs/exec-plans/active/35-t-wave-2-workspace-hot-reload.md` covers T-003.
- `docs/exec-plans/active/36-t-wave-4-analyzer-refactor-follow-ons.md` covers T-018 and T-025.
- `docs/exec-plans/active/37-t-wave-4-repo-audit-decomposition.md` covers T-019.
- `docs/exec-plans/active/38-t-wave-5-analyzer-coverage-follow-ons.md` covers T-017.
- `docs/exec-plans/active/39-t-wave-5-parser-failure-logging.md` covers T-026.

---

## Scan Log

| Date | Findings | Action Taken |
|------|-----------|--------------|
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
