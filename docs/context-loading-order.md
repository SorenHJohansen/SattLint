# Context Loading Order

Controls prompt bloat. Load in order, stop when context sufficient.

## Loading Priority

1. **AGENTS.md** - Entry point. Constraints, boundaries, workflow rules.
2. **Relevant subsystem docs** - `.github/instructions/*.md` for targeted work.
3. **Active design docs** - `docs/design-docs/` for architectural decisions.
4. **Tech debt** - `docs/exec-plans/tech-debt-tracker.md` for known issues.
5. **Current issue context** - Issue description, linked PRs, related commits.
6. **Lessons learned** - `docs/lessons-learned/known-failure-patterns.md` for repeated issues.

## Stop Conditions

- Task clear after step 1 → stop.
- Subsystem work after step 2 → stop.
- Architecture change after step 3 → stop.
- Bug fix after step 4 → stop.
- Complex investigation after step 5.

## Anti-Patterns

- Dumping entire `docs/` into context
- Loading all design docs for single-line fix
- Reading `ARCHITECTURE.md` for typo corrections
- Opening `docs/quality-score.md` for routine analyzers work
