# Quality Score

Grades each SattLint domain and architectural layer.

Tracked by doc-gardening agent; fails CI when score drops.

## Domain Scores

| Domain | Path | Grade | Coverage | Last Updated | Blocker |
| -------- | ------ | ------- | ----------- | -------------- | ---------- |
| Application | `src/sattlint/` | B | 35% | 2026-04-28 | TD-004 |
| Analyzers | `src/sattlint/analyzers/` | B | 28% | 2026-04-28 | TD-004 |
| Core Semantics | `src/sattlint/core/` | B | 31% | 2026-04-28 | TD-004 |
| DevTools | `src/sattlint/devtools/` | B | 18% | 2026-04-28 | TD-004 |

## Layer Scores

| Layer | Grade | Reason |
| ------- | ------- | -------- |
| Parser → AST | A | Stable grammar, good test coverage (external `sattline-parser` package) |
| AST → Analyzers | B | Analyzer coverage improving, need remediation hints |
| App → Editor API | B | Editor facade coverage low, needs work |
| Docs/Process | B | Just restructured, tech debt tracked |

## Trend

| Date | Grade | Notes | Source |
|---|---|---|---|
| 2026-08-17 | B | pass; 4 pipeline findings; 10 doc findings; coverage n/a | Pipeline |
| 2026-05-19 | D | fail; 0 pipeline findings; 1 doc findings; coverage n/a | Pipeline |
| 2026-05-15 | D | fail; 0 pipeline findings; 0 doc findings; coverage n/a | Pipeline |
## Grading Scale

- **A**: ≥ 80% coverage, < 5 critical issues, docs current
- **B**: ≥ 30% coverage, < 15 issues, docs mostly current
- **C**: ≥ 15% coverage, < 30 issues, docs stale
- **D**: < 15% coverage or major architectural issues
