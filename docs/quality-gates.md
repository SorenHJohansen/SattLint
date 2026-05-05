# Quality Gates

SattLint already has strong lint, type, test, and repo-audit seams.
This file defines the layered operating contract so executor, test, reviewer, and human workflows all use the same gate names.

## Validation Stages

| Stage | Responsibility | Required commands | Expected proof |
| --- | --- | --- | --- |
| AI edit | Immediate correctness on the touched slice | `python scripts/run_ai_edit_gate.py [touched-files]`, focused pytest or owner validation, touched-file Pyright when Python files changed | Ruff autofix plus one focused executable check before widening |
| Pre-commit | Fast local hygiene before sharing work | `python -m pre_commit run --all-files` | Ruff fix, Ruff format, AI routing artifact regeneration when registry inputs change, changed Markdown lint, SattLine syntax-check, context health when AI-control files changed |
| Pre-push | Broader branch health | `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` | Recommended finish gate plus machine-readable audit output |
| CI | Full trust on PRs and main | Fast pre-commit gate, doc-gardener, `check-my-changes` on PRs, full audit on main and manual CI runs | Deterministic install, diff-scoped proof on PRs, full audit on main, artifact upload |
| Nightly | Strategic health and trend visibility | Scheduled `ci.yml` run with repo and context health outputs | Trend snapshot, slowest tests, structural drift, context efficiency review |

## AI Edit Contract

1. Start from the controlling file or symbol.
2. Make the smallest local edit.
3. Run `python scripts/run_ai_edit_gate.py` immediately after Python or AI-control file edits.
4. If a touched file appears in `artifacts/analysis/file_debt_ratchet.json`, satisfy its `touch_rule` in the same change.
5. Run the first focused validation immediately.
6. Only widen after the local check passes.
7. Emit a handoff when the slice moves to test or review.

## Per-File Debt Ledger

`artifacts/analysis/file_debt_ratchet.json`

This is the sparse, checked-in per-file debt ledger for AI-only ratchet work.
Only debt-bearing files belong in it.

- Structural entries mirror already approved structural file-line exceptions and now converge by policy: touched files above target must shrink on every touch until they reach target, then they must stay at or under target.
- Typing entries mirror `tool.sattlint.typing_ratchet.debt_allowlist` and define which touched files must exit debt immediately.
- Coverage entries now mirror the current per-file module rates in `coverage.xml` for the full checked-in source coverage debt inventory and currently use `must_reach_target_on_touch` toward 100% full-file proof. `scripts/check_ratchet_policy.py` remains the blocking policy seam, while `src/sattlint/devtools/coverage_reports.py` stays the reporting and recommendation surface for global, changed-line, and touched-file coverage proof rather than a second blocking policy engine.

Normal work keeps the ledger shrink-only:

- remove entries when debt is cleared
- tighten targets or touch rules when real fixes land
- do not add new debt entries without an approval record

Protected ratchet edits must carry an approval record under `.github/approvals/ratchet-rebaseline-<date>.md`.
For file-debt migrations, only add entries that already mirror existing checked-in debt authorities such as the structural ratchet exception list, the typing debt allowlist, or the current per-file module rates recorded in `coverage.xml`.

## Pre-Commit Gate

`python -m pre_commit run --all-files`

This remains the default local safety gate.
It now stays fast and file-scoped: Ruff autofix, Ruff format, AI routing artifact regeneration when the registry inputs change, changed Markdown lint, SattLine syntax-check, and context health only when the AI-control plane changes.

## Pre-Push Gate

`sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`

Use this as the real local pre-push gate. It chooses the correct finish gate automatically and carries the heavier proof burden that no longer belongs in default pre-commit.
The public-readiness slice also treats tracked helper or scratch entries at the repo root as hygiene failures; move reusable tooling under `scripts/` and keep the top-level layout canonical.

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
