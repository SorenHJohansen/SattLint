# Quality Gates

SattLint already has strong lint, type, test, and repo-audit seams.
This file defines the layered operating contract so executor, test, reviewer, and human workflows all use the same gate names.

## Validation Stages

| Stage | Responsibility | Required commands | Expected proof |
| --- | --- | --- | --- |
| AI edit | Immediate correctness on the touched slice | `python scripts/run_ai_edit_gate.py [touched-files]`, focused pytest or owner validation, touched-file Pyright when Python files changed | Ruff autofix plus one focused executable check before widening |
| Pre-commit | Fast local hygiene before sharing work | `python -m pre_commit run --all-files` | Ruff fix, Ruff format, changed Markdown lint, SattLine syntax-check, context health when AI-control files changed |
| Pre-push | Broader branch health | `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` | Recommended finish gate plus machine-readable audit output |
| CI | Full trust on PRs and main | Fast pre-commit gate, doc-gardener, `check-my-changes` on PRs, full audit on main and manual CI runs | Deterministic install, diff-scoped proof on PRs, full audit on main, artifact upload |
| Nightly | Strategic health and trend visibility | Scheduled `ci.yml` run with repo and context health outputs | Trend snapshot, slowest tests, structural drift, context efficiency review |

## AI Edit Contract

1. Start from the controlling file or symbol.
2. Make the smallest local edit.
3. Run `python scripts/run_ai_edit_gate.py` immediately after Python or AI-control file edits.
4. Run the first focused validation immediately.
5. Only widen after the local check passes.
6. Emit a handoff when the slice moves to test or review.

## Pre-Commit Gate

`python -m pre_commit run --all-files`

This remains the default local safety gate.
It now stays fast and file-scoped: Ruff autofix, Ruff format, changed Markdown lint, SattLine syntax-check, and context health only when the AI-control plane changes.

## Pre-Push Gate

`sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`

Use this as the real local pre-push gate. It chooses the correct finish gate automatically and carries the heavier proof burden that no longer belongs in default pre-commit.

## CI Gate

- Lint and formatting stay in `lint.yml`.
- Type and test enforcement stay in `typing.yml`.
- Repo-audit owner checks stay in `repo-audit.yml`.
- `ci.yml` runs the fast pre-commit gate and doc-gardener, then uses `check-my-changes` on pull requests and the full repo audit on `main`, manual runs, and nightly health.

## Nightly Gate

Nightly runs should generate:

- repo audit summary
- context health summary
- repo health JSON and Markdown
- slowest tests
- largest current files
- ratchet and debt indicators
- AI task throughput and merge success metrics when handoffs exist
