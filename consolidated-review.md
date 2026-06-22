# SattLint v1.0 Release Roadmap

> Generated 2026-06-22. Consolidates all findings from 12 prior reviews and a comprehensive repository audit.
>
> **Codebase stats:** 422 Python source files, 281 test files, ~120,090 lines of Python, 73 devtools modules, 4 CI workflows.

---

## Phase Overview

| Phase | Theme | Total Items | Est. Effort |
|-------|-------|-------------|-------------|
| P1 | Distribution & packaging | 7 | ~4h |
| P3 | CI/CD hardening | 7 | ~4h |
| P4 | Technical debt — source | 9 | ~1 week |
| P5 | Technical debt — test | 6 | ~3 days |
| P6 | Technical debt — architecture | 10 | ~2 weeks |
| P7 | Polish & release | 4 | ~2h |

**Completed:** P0 (Quick hygiene & baseline, 14 items) and P2 (Documentation & governance, 8 items) — 22 items finished.

---

## P1 — Distribution & Packaging (7 items, ~4h)

Get the package ready for PyPI consumption. Every user will first encounter SattLint through `pip install`.

| # | Task | File(s) | Effort | Verification |
|---|------|---------|--------|-------------|
| P1.1 | Consolidate duplicate grammar packaging | `pyproject.toml` | 30m | `pip install -e . && pip show -f sattlint` shows grammar files only once |
| P1.2 | Make telemetry optional — move `opentelemetry-*` to `[telemetry]` extra with graceful degradation | `pyproject.toml`, import sites | 3h | `pip install sattlint` works without opentelemetry; telemetry code is a no-op when extra absent |
| P1.3 | Declare `__all__` in every public package | `src/sattlint/analyzers/__init__.py`, `src/sattlint/core/__init__.py`, `src/sattlint/resolution/__init__.py`, `src/sattlint/reporting/__init__.py`, etc. | 2h | `python -c "from sattlint import *"` succeeds and exports only intended names |
| P1.4 | Add clean-venv install test to CI | `.github/workflows/ci.yml` or `publish.yml` | 30m | CI job installs into fresh venv, runs `sattlint --version` |
| P1.5 | Add SBOM generation to publish workflow | `.github/workflows/publish.yml` | 30m | Published release includes SBOM artifact |
| P1.6 | Update PyPI metadata: add `long_description_content_type`, project URLs for docs | `pyproject.toml` | 10m | `twine check dist/*` passes |
| P1.7 | Add stable Python API surface documentation | `docs/public/python-api.md` | 1h | Documents all `__all__` exports per package |

---

## P3 — CI/CD Hardening (7 items, ~4h)

Make CI reliable, fast, and platform-complete.

| # | Task | File(s) | Effort | Verification |
|---|------|---------|--------|-------------|
| P3.1 | Run Windows pytest suite (not just quick audit) | `.github/workflows/ci.yml` | 2h | Windows CI runs `pytest -q --tb=short` |
| P3.2 | Add OpenSSF Scorecard workflow and badge | `.github/workflows/scorecard.yml`, `README.md` | 1h | Badge appears in README |
| P3.3 | Add performance benchmark step to CI | `.benchmarks/`, CI workflow | 1h | CI measures parse/analyze time on standard fixture, fails on regression |
| P3.4 | Add Pyright to pre-commit | `.pre-commit-config.yaml` | 30m | `pre-commit run --all-files` includes pyright |
| P3.5 | Remove or fix misleading coverage gate scope | `pyproject.toml` (coverage config) | 15m | `--cov-fail-under` matches actual measured surface |
| P3.6 | Start using pytest markers for CI tier differentiation | Test files | 1h | `pytest -m "not slow"` works, `pytest -m unit` runs fast subset |
| P3.7 | Add `pytest.mark.skipif` / `pytest.mark.skip` support for quarantining flaky tests | Test files | 15m | Mechanism exists and is documented |

---

## P4 — Technical Debt: Source Code (9 items, ~1 week)

Address the 500-line cap violation per AGENTS.md policy.

| # | Task | File(s) | Lines | Effort |
|---|------|---------|-------|--------|
| P4.1 | Split `src/sattlint/app_analysis.py` | `src/sattlint/app_analysis.py` | 1,656 | 1 day |
| P4.2 | Split `src/sattlint/engine.py` | `src/sattlint/engine.py` | 1,627 | 1 day |
| P4.3 | Split `src/sattlint/devtools/source_diff_report.py` | `src/sattlint/devtools/source_diff_report.py` | 1,474 | 4h |
| P4.4 | Split `scripts/repo_health.py` | `scripts/repo_health.py` | 1,437 | 4h |
| P4.5 | Split `scripts/check_ratchet_policy.py` | `scripts/check_ratchet_policy.py` | 1,552 | 4h |
| P4.6 | Split `src/sattlint/devtools/pipeline.py` | `src/sattlint/devtools/pipeline.py` | 1,261 | 4h |
| P4.7 | Split `src/sattlint/docgenerator/docgen.py` | `src/sattlint/docgenerator/docgen.py` | 1,392 | 4h |
| P4.8 | Split `src/sattlint/docgenerator/configgen.py` | `src/sattlint/docgenerator/configgen.py` | ~1,160 | 3h |
| P4.9 | Split remaining 10 files over 500 lines | `src/sattlint/_app_textual_setup.py`, `app.py`, `validation.py`, `cache.py`, `_app_analysis_loading.py`, `_picture_display_path_runtime.py`, `core/_semantic_snapshot.py`, `graphics_validation.py`, `analyzers/_reset_path_collection.py`, `analyzers/_dataflow_conditions.py` | 540–1,075 | 2 days |

**Note:** These are not v1.0 *blockers* in the strict sense — the packaged code works fine. They represent a policy violation per `AGENTS.md` that should be tracked on the post-v1.0 roadmap.

---

## P5 — Technical Debt: Test Files (6 items, ~3 days)

Overlong test files reduce maintainability and reviewability.

| # | File | Lines | Refactor strategy |
|---|------|-------|-------------------|
| P5.1 | `tests/test_analyzers_variables_part4.py` | ~2,493 | Split by checker; extract shared fixture data |
| P5.2 | `tests/test_app_live_adapters.py` | ~1,910 | Split by adapter type |
| P5.3 | `tests/devtools/test_source_diff_report.py` | ~1,708 | Split by diff scenario |
| P5.4 | `tests/test_pipeline_run.py` | ~1,582 | Split by pipeline stage |
| P5.5 | `tests/test_variables_access_and_contract_helpers.py` | ~1,422 | Extract helper factories |
| P5.6 | Remaining 9 files over 800 lines | ~1,000–1,378 each | Consolidate `_hdr()` and `_varref()` into `tests/helpers/` (currently copied in ~50 and ~47 files); parametrize copy-paste tests |

---

## P6 — Technical Debt: Architecture (10 items, ~2 weeks)

Structural improvements to internal architecture. These are the most invasive changes.

| # | Task | Area | Effort | Notes |
|---|------|------|--------|-------|
| P6.1 | Introduce shared `CliApp` base class for 11 standalone console scripts | CLI system | 2 days | Eliminates per-script argparse duplication |
| P6.2 | Consolidate exit code constants into `_exit_codes.py` | CLI system | 1h | Defined in 3 places today |
| P6.3 | Integrate `sattlint-trace` as `sattlint trace` subcommand | CLI system | 1h | Currently only works as standalone binary |
| P6.4 | Add `--output-format json` to all CLI commands | CLI system | 2 days | Only `simulate` and `telemetry-summary` support it |
| P6.5 | Add health/status endpoint to LSP server | LSP | 1 day | Liveness probe for editor clients |
| P6.6 | Consolidate DevTools `__init__.py` circular-import workaround | DevTools | 2 days | Replace `__getattr__` + dynamic routing with explicit subpackages |
| P6.7 | Register all schema kinds in `artifact_registry.py` | DevTools | 1 day | Currently ~15+ independent constants |
| P6.8 | Extract duplicated progress helpers into shared utility | DevTools | 1h | At least 5 files duplicate identical `_emit_progress` |
| P6.9 | Extract duplicated path-sanitizer wrappers into shared utility | DevTools | 1h | At least 3 files wrap `sanitize_path_for_report` identically |
| P6.10 | Consolidate cache persistence patterns; add HMAC guard to pickle usage | Cache | 2 days | 4 persistence patterns, `# nosec B301`/`B403` without HMAC |

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
P1.1–P1.7 (distribution)  ───────────────────────────────────> P7.2 (classifiers)
                                                                │
P7.1 (changelog) ─────────────────────────────────────────────> P7.3
                                                                │
P1.4 (clean-venv CI test)                                      │
P1.5 (SBOM)                                                    │
                                                                ▼
                                                           P7.4 (publish)
```

P4–P6 are independent of each other and of the release track.

---

## Quick Reference: Remaining Items by Location

| Location | Items |
|----------|-------|
| `pyproject.toml` | P1.1, P1.2, P1.6, P3.5 |
| `src/sattlint/` (source splits) | P4.1–P4.9 |
| `src/sattlint_lsp/` | P6.5 |
| `src/sattlint/__init__.py` + subpackages | P1.3, P1.7 |
| `.github/workflows/` | P1.4, P1.5, P3.1, P3.2, P3.3 |
| `.pre-commit-config.yaml` | P3.4 |
| `docs/public/` | P1.7 |
| `tests/` (test splits) | P5.1–P5.6 |
| `tests/helpers/` | P5.6 |
| `.benchmarks/` | P3.3 |

---

## Effort Summary

| Phase | Items | Est. Effort | Calendar (sequential) | Calendar (parallel) |
|-------|-------|-------------|----------------------|---------------------|
| P1 — Distribution | 7 | ~4h | 1 day | 1 day |
| P3 — CI/CD hardening | 7 | ~4h | 1 day | 1 day |
| P4 — Source debt | 9 | ~1 week | 1 week | 3 days |
| P5 — Test debt | 6 | ~3 days | 3 days | 2 days |
| P6 — Architecture debt | 10 | ~2 weeks | 2 weeks | 1 week |
| P7 — Polish & release | 4 | ~2h | 1 day | 1 day |
| **Total remaining** | **43** | **~4 weeks** | **~4 weeks** | **~2 weeks** |

> **Completed:** P0 (14 items, ~2h) and P2 (8 items, ~6h) — 22 items finished.
> **P4–P6 (post-v1.0 quality backlog):** ~4 weeks. These are not release blockers in the strict sense.
