# SattLint v1.0 Release Roadmap

> Generated 2026-06-22. Consolidates all findings from 12 prior reviews and a comprehensive repository audit.
>
> **Codebase stats:** 422 Python source files, 281 test files, ~120,090 lines of Python, 73 devtools modules, 4 CI workflows.

---

## Phase Overview

| Phase | Theme | Total Items | Est. Effort |
|-------|-------|-------------|-------------|
| P4 | Technical debt — source | 9 | ~1 week |
| P5 | Technical debt — test | 6 | ~3 days |
| P6 | Technical debt — architecture | 10 | ~2 weeks |
| P7 | Polish & release | 4 | ~2h |

**Completed:** P0 (Quick hygiene & baseline, 14 items), P1 (Distribution & packaging, 7 items), P2 (Documentation & governance, 8 items), P3 (CI/CD hardening, 7 items) — 36 items finished.

## P5 — Technical Debt: Test Files (6 items, ~3 days)

Overlong test files reduce maintainability and reviewability.

| # | File | Lines | Refactor strategy |
|---|------|-------|-------------------|
| P5.1 | `tests/test_analyzers_variables_part4.py` | ~2,493 | Split by checker; extract shared fixture data |
| P5.2 | `tests/test_app_live_adapters.py` | ~1,910 | Split by adapter type |
| P5.3 | `tests/devtools/test_source_diff_report.py` | ~1,708 | Split by diff scenario |
| P5.4 | `tests/test_pipeline_run.py` | ~1,582 | Split by pipeline stage |
| P5.5 | `tests/test_variables_access_and_contract_helpers.py` | ~1,422 | Extract helper factories |
| P5.6a | Helper dedupe in analyzer/editor/app-analysis tests | ~845–1,287 | Replace remaining local `_hdr()` and `_varref()` copies with `tests.helpers.variable_test_support` in the oversized suites that still inline those AST builders |
| P5.6b | CLI/menu/app-analysis scenario tables | ~1,171–1,275 | Parametrize repeated CLI, menu, and app-analysis permutations in the remaining large app-facing test modules |
| P5.6c | Analyzer variable-suite dedupe | ~1,123–1,195 | Move repeated variable-analysis scenario builders into shared analyzer support modules and merge near-duplicate assertions |
| P5.6d | Parser/corpus/ICF fixture dedupe | ~1,048–1,238 | Table-drive repeated parser, corpus, engine-loader, and ICF validation scenarios; extract shared fixture builders instead of copying setup blocks |

---
---

## P7 — Polish & Release (4 items, ~2h)

| # | Task | Effort | Verification |
|---|------|--------|-------------|
| P7.1 | Populate CHANGELOG with full git history from `0.1.1` to `HEAD` | 1h | Changelog has entries covering all changes |
| P7.2 | Write PYPI classifiers for v1.0.0 release | 10m | `twine check dist/*` passes |
| P7.3 | Tag `v1.0.0` and push | 5m | GitHub release created |
| P7.4 | Run publish.yml and verify PyPI listing | 15m | `pip install sattlint` works from PyPI |

---

## Dependency Graph

```text
P7.1 (changelog) ─────────────────────────────────────────────> P7.3 (tag)
                                                                 │
                                                                 ▼
                                                            P7.4 (publish)
```

P4–P6 are independent of each other and of the release track.

---

## Quick Reference: Remaining Items by Location

| Location | Items |
|----------|-------|
| `pyproject.toml` | (none remaining) |
| `src/sattlint/` (source splits) | P4.1–P4.9 |
| `src/sattlint/__init__.py` + subpackages | (none remaining) |
| `.github/workflows/` | (none remaining) |
| `.pre-commit-config.yaml` | (none remaining) |
| `docs/public/` | (none remaining) |
| `tests/` (test splits) | P5.1–P5.6 |
| `tests/helpers/` | P5.6 |
| `.benchmarks/` | (none remaining) |

---

## Effort Summary

| Phase | Items | Est. Effort | Calendar (sequential) | Calendar (parallel) |
|-------|-------|-------------|----------------------|---------------------|
| P4 — Source debt | 9 | ~1 week | 1 week | 3 days |
| P5 — Test debt | 6 | ~3 days | 3 days | 2 days |
| P6 — Architecture debt | 10 | ~2 weeks | 2 weeks | 1 week |
| P7 — Polish & release | 4 | ~2h | 1 day | 1 day |
| **Total remaining** | **29** | **~4 weeks** | **~4 weeks** | **~2 weeks** |

> **Completed:** P0 (14 items, ~2h), P1 (7 items, ~4h), P2 (8 items, ~6h), P3 (7 items, ~4h) — 36 items finished.
> **P4–P6 (post-v1.0 quality backlog):** ~4 weeks. These are not release blockers in the strict sense.
