# Quality Gates

SattLint already has strong lint, type, test, and repo-audit seams.
This file defines the layered operating contract so single-chat assistant work and human workflows use the same gate names.

## Validation Stages

| Stage | Responsibility | Required commands | Expected proof |
| --- | --- | --- | --- |
| Focused local | Immediate correctness on the touched slice | Focused pytest or owner validation, touched-file Pyright when Python files changed, `python scripts/context_health.py --check` when AI-control files changed | One focused executable check before widening |
| Pre-commit | Fast local hygiene before sharing work | `python -m pre_commit run --all-files` | Ruff fix, Ruff format, changed Markdown lint, SattLine syntax-check, context health when AI-control files changed |
| AI drift | Diff-scoped repo-audit proof after AI work | `sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit` | Recommended finish gate plus machine-readable current-slice audit output |
| Pre-push | Broader branch health | `sattlint-repo-audit --profile full --output-dir artifacts/audit` | Full-repo audit output that mirrors the CI trust gate |
| CI | Full trust on PRs and main | Fast pre-commit gate, doc-gardener, `check-my-changes` on PRs, full audit on main and manual CI runs | Deterministic install, diff-scoped proof on PRs, full audit on main, artifact upload |
| Nightly | Strategic health and trend visibility | Scheduled `ci.yml` run with repo and context health outputs | Trend snapshot, slowest tests, structural drift, context efficiency review |

## Focused Local Contract

1. Start from the controlling file or symbol.
2. Make the smallest local edit.
3. Run the first focused executable validation immediately.
4. If a touched file appears in `artifacts/analysis/file_debt_ratchet.json`, satisfy its `touch_rule` in the same change.
5. Run `python scripts/context_health.py --check` when AI-control files changed.
6. AI-touched files are also blocked through `.github/hooks/ai-edit-gate.json`; rerun `python scripts/run_ai_edit_gate.py <touched paths>` only when debugging that hook locally.
7. Only widen after the local check passes.
8. Summarize outcome and remaining risk directly in the final response when needed.

## Per-File Debt Ledger

`artifacts/analysis/file_debt_ratchet.json`

This is the sparse, checked-in per-file debt ledger for repo-maintenance ratchet work.
Only debt-bearing files belong in it.

- Structural entries mirror already approved structural file-line exceptions and now converge by policy: touched files above target must shrink on every touch until they reach target, then they must stay at or under target.
- Typing entries mirror `tool.sattlint.typing_ratchet.debt_allowlist` and define which touched files must exit debt immediately.
- Coverage entries now mirror the current per-file module rates in `coverage.xml` for the full checked-in source coverage debt inventory and currently use `must_reach_target_on_touch` toward 100% full-file proof. `scripts/check_ratchet_policy.py` remains the blocking policy seam, while `src/sattlint/devtools/coverage_reports.py` stays the reporting and recommendation surface for global, changed-line, and touched-file coverage proof rather than a second blocking policy engine.

The ratchet is strictly monotonic and never loosens. Normal work keeps the ledger shrink-only:

- remove entries when debt is cleared
- tighten targets or touch rules when real fixes land; never widen them
- do not add new debt entries without an approval record
- do not increase baselines, targets, or exception limits; fix code or tests instead

Protected ratchet edits must carry an approval record under `.github/approvals/ratchet-rebaseline-<date>.md`.
For file-debt migrations, only add entries that already mirror existing checked-in debt authorities such as the structural ratchet exception list, the typing debt allowlist, or the current per-file module rates recorded in `coverage.xml`.

## Pre-Commit Gate

`python -m pre_commit run --all-files`

This remains the default local safety gate.
It now stays fast and file-scoped: Ruff autofix, Ruff format, changed Markdown lint, SattLine syntax-check, and context health only when repo-guidance files change.

## AI Post-Change Gate

`python scripts/run_ai_edit_gate.py <repo-relative paths...>`

This is the local runner behind `.github/hooks/ai-edit-gate.json`.
For AI-touched files it applies Ruff fix and format, touched-file Pyright, AI-control checks such as `context_health.py --check`, existing doc-gardener and layer-linter checks for Python edits, and touched-file ratchet enforcement through the single policy engine in `scripts/check_ratchet_policy.py`.
Validation failures block the edit through the post-tool hook. Hook infrastructure failures still fail open and emit a warning payload.

## AI Drift Gate

`sattlint-repo-audit --profile full --check-my-changes --output-dir artifacts/audit`

Use this after AI-assisted coding to verify the current slice. It chooses the correct finish gate automatically and carries the heavier diff-scoped proof burden that no longer belongs in default pre-commit.
It now also evaluates changed-file structural surface proof for the recorded `import_max_count`, `dependency_max_count`, `public_symbol_max_count`, and `nesting_max_depth` ceilings, so new maxima fail here instead of in the AI post-tool hook.
The public-readiness slice also treats tracked helper or scratch entries at the repo root as hygiene failures; move reusable tooling under `scripts/` and keep the top-level layout canonical.

## Pre-Push Gate

`sattlint-repo-audit --profile full --output-dir artifacts/audit`

Use this before pushing when you want the same full-repo audit burden that CI expects on `main` and manual full runs.

For long-running quick or full audit snapshots, use the staged runner instead of writing directly into a reused `*-current` directory:

- `python scripts/run_repo_python.py -m sattlint.devtools.repo_audit_runs --final-output-dir artifacts/audit-quick-current --keep-history artifacts/audit-history --profile quick`
- `python scripts/run_repo_python.py -m sattlint.devtools.repo_audit_runs --final-output-dir artifacts/audit-full-current --keep-history artifacts/audit-history --profile full`

When a repo-owned Python command needs reliable post-run capture instead of shell redirection, `scripts/run_repo_python.py` also supports an opt-in artifact mode via environment variables:

- `SATTLINT_RUN_REPO_PYTHON_ARTIFACT_DIR=<dir>`
- `SATTLINT_RUN_REPO_PYTHON_ARTIFACT_PREFIX=<prefix>`

With both variables set, the runner writes `<prefix>.stdout`, `<prefix>.stderr`, and `<prefix>.exit` under the selected directory after the child process finishes. This mode is capture-only rather than live tee output; if early Python flushing matters for the child command, prefer `-u` in the forwarded Python arguments.

Validate a published audit directory with `python scripts/run_repo_python.py -m sattlint.devtools.artifact_readiness --artifact-dir <dir>` before reading JSON artifacts in automation. Compare before/after findings with `python scripts/run_repo_python.py -m sattlint.devtools.compare_audit_findings --before <dir> --after <dir>` instead of manually reading both `findings.json` files.

## CI Gate

- Lint and formatting stay in `lint.yml`.
- Type, test, pip-audit, and npm-audit stay in `typing.yml` under the workflow name `Typing And Quality`.
- Ratchet-policy enforcement no longer runs as a dedicated `typing.yml` job. AI-touched files are blocked locally through `.github/hooks/ai-edit-gate.json` and `scripts/run_ai_edit_gate.py`, while broader branch proof still comes from the repo-audit finish gates.
- Repo-audit owner checks stay in `repo-audit.yml`, but that owner workflow now covers packaging or leak validation and the Windows quick audit instead of a second Ubuntu full audit.
- `ci.yml` runs the fast pre-commit gate and doc-gardener, then uses `check-my-changes` on pull requests and the full repo audit on `main`, manual runs, and nightly health.

`publish.yml` now supports a manual `workflow_dispatch` rehearsal that builds distributions, runs `twine check`, runs `sattlint-release-smoke`, uploads distributions and smoke artifacts, and stops before publication. Only real `v*` tag pushes enter the final publish job, and only that job receives `id-token: write` while targeting the protected `pypi-release` environment.

When CI or local workflows need a stable long-running audit directory for later inspection, publish it through `sattlint.devtools.repo_audit_runs` and gate readers through `sattlint.devtools.artifact_readiness`.

## Nightly Gate

Nightly runs should generate:

- repo-audit artifacts under `artifacts/audit-nightly/`
- context health JSON and Markdown outputs
- repo health JSON, Markdown, HTML, and history artifacts
