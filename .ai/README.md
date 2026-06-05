# AI Workspace

This directory is for machine-authored AI artifacts and lightweight coordination files.

- Human workflow guidance stays in `AGENTS.md`.
- Human-facing maintainer docs stay under `docs/maintainers/`.
- Keep checked-in AI artifacts small, mechanical, and easy to prune.

Current scope:

- `tasks/` and `handoffs/` are for structured JSON contracts when a workflow needs them.
- New generated AI artifacts should prefer `.ai/` over `docs/`.
- Existing routing registries under `.github/skills/validation-routing/references/` stay in place until their runtime consumers move.
