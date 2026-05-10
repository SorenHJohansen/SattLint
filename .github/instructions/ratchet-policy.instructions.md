---
description: "Use when changing ratchet baselines, debt ledgers, approval records, coverage floors, or ratchet-policy tests in SattLint. Covers approval, monotonicity, per-file debt, and focused validation rules."
name: "Ratchet Policy Instructions"
applyTo: ["scripts/check_ratchet_policy.py", "tests/test_ratchet_policy.py", "artifacts/analysis/coverage_ratchet.json", "artifacts/analysis/structural_budget_ratchet.json", "artifacts/analysis/file_debt_ratchet.json", ".github/approvals/*.md", ".github/workflows/typing.yml", "docs/quality-gates.md", "pyproject.toml"]
---
# Ratchet Policy

- Treat `scripts/check_ratchet_policy.py` as the blocking policy seam. Keep report surfaces and workflow labels aligned, but do not introduce a second policy engine in docs, reports, or helper code.
- Ratchet is strictly monotonic and never loosens. No baseline inflation — ever. Fix code or tests to meet the existing ratchet; do not rebaseline upward to make a change pass.
- Protected ratchet edits must carry a same-change approval record at `.github/approvals/ratchet-rebaseline-<date>.md` with both `Approved-by:` and `Reason:` lines.
- Protected-path edits must verify approval-record discovery in both staged and worktree contexts before widening the change.
- If a protected edit fails because the approval record is untracked or invisible to change-context detection, fix the change-detection seam first instead of broadening the protected edit.
- Structural and typing ratchets are strictly monotonic and never loosen. Coverage uses the baseline-plus-buffer rule: `summary.total_line_rate` must not decrease, `metrics.min_line_rate_basis_points` must equal the recorded baseline minus `1.00` percentage point, and `pyproject.toml` `--cov-fail-under` must stay aligned to that derived floor.
- `artifacts/analysis/file_debt_ratchet.json` is sparse and shrink-only. Only debt-bearing files belong in it, and clearing debt should remove entries instead of leaving stale placeholders.
- New per-file debt entries must mirror checked-in debt authorities instead of inventing new debt categories: structural entries mirror approved file-line exceptions, typing entries mirror `tool.sattlint.typing_ratchet.debt_allowlist`, and coverage entries mirror the current `coverage.xml` module rates.
- Converging touch rules are required when debt remains above target. Structural debt above target should use `must_shrink` or `must_meet_target` as appropriate, typing debt must use `must_exit_on_touch`, and current coverage debt entries use `must_reach_target_on_touch` toward full proof.
- If a touched file appears in the per-file debt ledger, satisfy its touch rule in the same change. Do not touch debt-bearing files and leave them flat or weaker unless the file now meets the target.
- Do not answer typing-ratchet failures with broad strict-promotion unless the task explicitly includes typing-debt expansion.
- Start validation with the narrow ratchet suite: `python scripts/run_repo_python.py -m pytest --no-cov tests/test_ratchet_policy.py -x -q --tb=short`. When the change is docs-only or AI-control-only, validate the touched Markdown with workspace diagnostics or targeted markdownlint, then run `python scripts/context_health.py --check` before widening.
