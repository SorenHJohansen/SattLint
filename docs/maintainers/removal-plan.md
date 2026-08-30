# Removal Plan

Goal: Make the repo leaner by removing high-maintenance, low-signal components.
Generated: 2026-08-24

## Phase 1: Dead weight in devtools (low risk)

These submodules have zero or near-zero consumers outside devtools itself.

| Module | Why remove | Lines |
|--------|-----------|-------|
| `devtools/property_tests` | No tests, no imports from any consumer, only `__init__` re-export | ~200 |
| `devtools/ai_templates` | Only referenced by `artifact_registry` (a mapping), no test or code consumer | ~150 |
| `devtools/parser_properties` | Only `__init__` re-export, no imports, no tests | ~100 |
| `devtools/production_summary` | Only `__init__` re-export, no imports, no tests | ~100 |
| `devtools/compare_audit_findings` | Only consumed by tests, no production consumer | ~200 |

After deletion, remove entries from `devtools/__init__.py` `__all__`.

## Phase 2: Standalone CLI entry points (medium risk)

Remove redundant or unused entry points from `pyproject.toml` `[project.scripts]`.

| Entry point | Reason | Used in CI? |
|-------------|--------|-------------|
| `sattlint-trace` | One-line wrapper around `sattlint trace` subcommand, fully redundant | No |
| `sattlint-observability` | No CI or script usage, developer-only tool | No |
| `sattlint-review` | No CI or script usage, agent review tool | No |
| `sattlint-structural-ratchet` | No CI invocation, only pipeline-internal | No |
| `sattlint-analysis-pipeline` | No CI invocation, only pipeline-internal | No |
| `sattlint-corpus-runner` | No CI invocation, only manual use | No |

**Keep** (CI-active): `sattlint-repo-audit`, `sattlint-doc-gardener`, `sattlint-layer-lint`, `sattlint-release-smoke`.

When removing, also delete the `cli()` entry function in each module if it exists solely for the standalone entry point.

## Phase 3: Unused fixtures (low risk)

| Path | Lines | Status |
|------|-------|--------|
| `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.s` | 14,957 | Zero test references |
| `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.g` | 430 | Zero test references |
| `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.l` | ~500 | Zero test references |
| `tests/fixtures/sample_sattline_files/SattLineFullGrammarTest.p` | ~500 | Zero test references |
| `tests/fixtures/sample_sattline_files/PowerUp.s` | ~200 | Zero test references |
| `tests/fixtures/sample_sattline_files/ModuleVersionDrift.s` | ~200 | Zero test references |
| `test_programs/` (entire directory) | ~200 | Zero test references |

## Phase 4: Stale metadata (trivial)

| Path | Change |
|------|--------|
| `pyproject.toml` description | Remove "LSP" — no LSP implementation exists |
| `pyproject.toml` keywords | Remove "lsp" keyword |

## Phase 5: CI-only devtools candidates (requires careful verification)

These modules are only used by `sattlint-analysis-pipeline` or by other devtools modules. If Phase 2 removes the pipeline entry point, these become removable:

| Module | Depends on | Used by |
|--------|-----------|---------|
| `devtools/mutation_engine` | shared/ | pipeline, _pipeline_optional_reports_helpers |
| `devtools/differential` | shared/ | _pipeline_optional_reports_helpers |
| `devtools/semantic_reports` | shared/ | _pipeline_optional_reports_helpers, pipeline |
| `devtools/tool_reports` | shared/ | pipeline |
| `devtools/trace_reports` | shared/ | pipeline |
| `devtools/accuracy_metrics` | shared/ | pipeline_artifacts |

**Do NOT remove these yet** — they form the analysis pipeline's report generation chain. Remove only if the entire pipeline is dropped.

## Phase 6: Working tree cleanup (no code changes)

Delete gitignored regenerable directories to free disk space:

```bash
rm -rf artifacts/audit/ artifacts/analysis/ htmlcov/ build/ dist/ .pytest_cache/ .ruff_cache/ coverage.xml
```

~55 MB recovered.

## Execution order

1. Phase 1 (devtools dead weight) — immediate, no risk
2. Phase 3 (fixtures) — immediate, no risk
3. Phase 4 (metadata) — immediate, trivial
4. Phase 6 (working tree) — immediate, no code impact
5. Phase 2 (CLI entry points) — after verifying no hidden consumers
6. Phase 5 (pipeline modules) — only if pipeline is being removed

## What NOT to remove

- `devtools/audit/` — CI-critical, 17+ test files
- `devtools/pipeline/` — CLI entry point, actively tested
- `devtools/doc_gardener` — CI gating tool
- `devtools/layer_linter` — CI gating tool
- `devtools/release_smoke` — release gating tool
- `devtools/source_diff_report` — core app imports it
- `devtools/structural/` — core app imports it
- `devtools/shared/` — core infrastructure used by many modules
- `scripts/` — lean CI infrastructure
- `docs/` — well-maintained, all hand-written
- `.github/` — clean CI setup
- Core engine files (`_engine_*.py`)
