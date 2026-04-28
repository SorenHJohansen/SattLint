# Tech Debt Tracker

Living document of known technical debt in SattLint.
Updated by doc-gardening agent and human developers.
Last scan: 2026-04-28

## Active Debt

| ID | Area | Description | Severity | Planned Fix |
|----|------|-------------|----------|-------------|
| TD-001 | Analyzers | Remediation instructions not yet embedded in error messages | Medium | In progress: added to Issue, VariableIssue, shadowing analyzer |
| TD-002 | Docs | `docs/` not fully restructured per harness-engineering layout | Medium | Completed 2026-04-28 |
| TD-003 | LSP | No hot-reload when `WORKFLOW.md`-equivalent changes | Low | Add watch + restart mechanism |
| TD-004 | Tests | Coverage threshold now 100% enforced | Medium | Completed 2026-04-28: ratcheted to 100% |
| TD-005 | Config | No validation that `analyzed_programs_and_libraries` paths exist | Low | Add startup validation |
| TD-006 | DevTools | Pipeline outputs not yet consumed by doc-gardening agent | Low | Wire artifacts → quality-score.md |
| TD-007 | Parse/Validate | validation.py functions return bool instead of parsing to typed objects | Medium | Refactor _is_valid_* to return parsed types |
| TD-008 | Types | Semantic type names needed for discoverability (VariableId, ProjectPath) | Low | Add semantic type aliases |

## Resolved Debt

| ID | Area | Description | Fixed In |
|----|------|-------------|----------|
| TD-000 | AGENTS.md | Was 172 lines, bloated with duplicated detail | 2026-04-28 |

## Scan Log

| Date | Findings | Action Taken |
|------|-----------|--------------|
| 2026-04-28 | 0 findings | Doc-gardening scan |
| 2026-04-28 | 1 findings | Doc-gardening scan |
| 2026-04-28 | 0 findings | Doc-gardening scan |
| 2026-04-28 | AGENTS.md 172→100 lines, docs/ restructuring | Initial restructure |
| (next scan due: weekly via CI) | | |

## Debt Categories

- **Critical**: Blocks features, causes data loss, security issue
- **High**: Affects reliability, performance, or user experience
- **Medium**: Code smell, missing feature, incomplete coverage
- **Low**: Nice-to-have, cosmetic, future-proofing
