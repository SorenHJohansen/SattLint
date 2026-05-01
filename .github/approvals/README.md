# Ratchet Approval Records

Ratchet edits are blocked unless the same change also adds or updates an approval record that matches `.github/approvals/ratchet-rebaseline-*.md`.

Required lines:

- `Approved-by: <human reviewer>`
- `Reason: <why the ratchet or coverage floor needs to move>`

Monotonic rule still applies: looser structural budgets, a lower coverage ratchet, or a lower `--cov-fail-under` value are rejected even when an approval record exists.
