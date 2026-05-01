# Coverage Campaign Progress

This file is the tracked template for the local coordination ledger.

The live working file is `.github/coordination/current-work.md`.
It is intentionally local-only and ignored by git.

When the local ledger is missing, hook scripts and repo tooling can bootstrap from this template.
When the local ledger exceeds 500 lines, oldest `Status: done` workstreams are pruned automatically.

Record workstreams using the existing markdown shape:

- `### Workstream <id>`
- `- Owner: ...`
- `- Goal: ...`
- `- Claims: ...`
- `- First validation: ...`
- `- Status: planned|active|blocked|ready-for-merge|done`
- `- Notes: ...`
