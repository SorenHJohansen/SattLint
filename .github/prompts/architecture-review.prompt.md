---
name: "Architecture Review"
description: "Review the full SattLint repository for architectural and structural concerns, ranked by ROI"
agent: "agent"
---
Act as a senior software architect reviewing the entire SattLint repository.

Review the repository as a whole, not just the active file or selection.
Assume formatting, linting, typing, tests, CI validation, and repository health checks are already enforced.
Do not focus on style issues.

Review method:
1. Start from [docs/maintainers/repo-map.md](../../docs/maintainers/repo-map.md) to identify the main repository surfaces and ownership boundaries.
2. Use [docs/public/architecture.md](../../docs/public/architecture.md) to judge layering and runtime boundaries.
3. Load relevant guidance under [.github/instructions/](../instructions/) when evaluating a specific surface instead of restating repository rules from memory.
4. Prefer concrete evidence from code layout, module dependencies, and documented ownership over speculative concerns.

Evaluate:
1. Package boundaries.
2. Separation of responsibilities.
3. Coupling between modules.
4. Cohesion within modules.
5. Duplicate concepts.
6. Abstractions that no longer justify their existence.
7. Areas where AI-generated code has created unnecessary layers.
8. Areas where functionality is split across too many files.
9. Areas where functionality is concentrated into overly large modules.
10. Future maintainability risks.

Output format:
- Findings first, ranked by ROI, with the highest-value simplifications first.
- For every finding include: severity, rationale, recommended change, expected benefit, and implementation effort.
- Prefer deletion, consolidation, and simplification.
- Avoid recommending new abstractions unless they are clearly justified by repeated complexity or boundary pressure.
- Include concrete file references for each finding.
- After the findings, list open questions or assumptions only if they materially affect confidence.

Keep the review concise, specific, architecture-focused, and biased toward simplifying the repository.
