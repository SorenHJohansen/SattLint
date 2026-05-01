# Context Loading Order

Controls prompt bloat for human-loaded context. Machine routing should start with `sattlint-repo-audit --profile full --planning-context --output-dir artifacts/audit`, then load only the instruction files and owner suites that report selects.

## Loading Priority

1. **AGENTS.md** - Entry point. Constraints, boundaries, workflow rules.
2. **Planning report** - `--planning-context` for changed files, owning surface, required instructions, first focused validation, finish-gate plan, and blocking invariants.
3. **Relevant subsystem docs** - Only the `.github/instructions/*.md` files selected by the planning report.
4. **Active design docs** - `docs/design-docs/` for architectural decisions.
5. **Tech debt** - `docs/exec-plans/tech-debt-tracker.md` for known issues.
6. **Current issue context** - Issue description, linked PRs, related commits.
7. **Lessons learned** - `docs/lessons-learned/known-failure-patterns.md` only when task matches a known failure smell, after one dead-end route, or after repeated validation failure.

## Stop Conditions

- Task clear after step 1 → stop.
- Planning report gives clear route after step 2 → stop.
- Subsystem work after step 3 → stop.
- Architecture change after step 4 → stop.
- Bug fix after step 5 → stop.
- Complex investigation after step 6.
- Do not load step 7 for routine tasks already resolved by steps 1-6.

## Anti-Patterns

- Manually stitching routing from AGENTS, validation docs, and generated maps instead of starting from `--planning-context`
- Dumping entire `docs/` into context
- Loading all design docs for single-line fix
- Reading `ARCHITECTURE.md` for typo corrections
- Opening `docs/quality-score.md` for routine analyzers work
- Loading `known-failure-patterns.md` wholesale for every task instead of consulting it by smell
