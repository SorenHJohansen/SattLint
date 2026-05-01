# Ratchet Approval Records

Ratchet edits are blocked unless the same change also adds or updates an approval record that matches `.github/approvals/ratchet-rebaseline-*.md`.

Required lines:

- `Approved-by: <human reviewer>`
- `Reason: <why the ratchet or coverage floor needs to move>`

Monotonic rule still applies for structural budgets and typing scope. Coverage uses a baseline-plus-buffer variant: `summary.total_line_rate` in `artifacts/analysis/coverage_ratchet.json` must not decrease, `metrics.min_line_rate_basis_points` must equal that baseline minus `1.00` percentage point, and `pyproject.toml` must keep `--cov-fail-under` aligned to the same derived floor.
