# CI Green Plan

> Plan to get the repo into a fully green CI state.
> Delete this file when all gates pass.

Last updated: 2026-08-23

## CI gate status

| # | Gate | Command | Status |
|---|------|---------|--------|
| 1 | pytest | `pytest -q --tb=short` | **PASS** (0 failed / 2006 passed / 163 skipped) |
| 2 | ruff lint | `ruff check .` | **PASS** |
| 3 | ruff format | `ruff format --check src/` | **PASS** |
| 4 | pyright src | `pyright src/sattlint` | **PASS** (0 errors) |
| 5 | vulture | `vulture src --min-confidence 80` | **PASS** |
| 6 | context health | `python scripts/context_health.py --check` | **PASS** |
| 7 | pre-commit | `pre-commit run --all-files` | **PASS** (cast(Any) fixed) |
| 8 | doc gardener | `sattlint-doc-gardener --check-only` | 3 medium stale-doc findings |
| 9 | layer lint | `sattlint-layer-lint` | **PASS** |
| 10 | pyright tests | `pyright tests` | 483 errors in test files (CI only checks `src/`) |

**All CI-blocking gates pass.** The remaining work below fixes test-file pyright errors for code quality.

## Dead files to delete

These files are unused (not imported by anything):

- `tests/_docgen_fixture_builders.py` (229 pyright errors)
- `tests/_docgen_test_support.py` (imported only by above)
- `tests/parser/_parser_core_part{1,2,3,4,5,6}.py` (broken imports, can't be collected)
- `tests/parser/_parser_core_test_support.py` (broken `strip_sl_comments` import)

## Parser-only fixes (cannot fix in this repo)

These errors originate from `sattline_parser` type annotations that don't match runtime behavior.
The parser is an installed dependency — fixes require an upstream release.

### P1. Dict-vs-VarRef type mismatch

Parser stubs say `ParameterMapping.target: VarRef` but parser runtime produces `dict[str, str]`.
Analyzers also expect dicts (`isinstance(x, dict)` checks in `_dependency_usage_scope_support.py`).
Affects ~498 errors across ~40 test files.

### P2. Missing `sattline_parser.utils.text_processing`

Import cannot be resolved — module was removed/renamed in the parser package.
Causes cascading `reportUnknownMemberType` in `tests/parser/_parser_core_part1.py`.

### P3. SFC type union mismatches

`list[SFCStep | SFCTransition]` cannot be assigned to `list[SFCBodyItem]` — parser type unions
don't match actual runtime types. Affects `tests/analyzers/test_same_cycle.py`,
`tests/analyzers/test_cyclomatic_complexity.py`.

### P4. `Tree` type parameter mismatches

Parser `Tree` class type parameters don't match actual usage patterns.

### P5. Unknown types from parser

Cascading from P2 — types from `sattline_parser.utils.text_processing` are unknown.

## Fixable errors (in this repo)

### F1. Tests referencing removed features

These test functions call removed APIs. Fix: delete function bodies, keep skip markers.

| Removed API | Files affected |
|-------------|---------------|
| `run_docgen_command` | `test_app_cli_commands.py`, `test_cli.py` |
| `build_coverage_summary_report` | `test_repo_audit_reporting_helpers.py` |
| `build_cli_consistency_report` | `test_repo_audit_reporting_helpers.py` |
| `_load_coverage_ratchet` / `COVERAGE_RATCHET_*` | `test_pipeline_collection_part5.py`, `test_pipeline_owner_coverage.py` |
| `_normalize_documentation_rule_keys` / `get_documentation_config` | `test_app_config_validation.py` |
| `_workspace_dependency_suffixes` / `_iter_workspace_...` | `test_app_analysis_part3.py` |
| `collect_custom_findings` | `test_repo_audit_entrypoints_verify.py` |
| `structural_reports` (undefined) | `test_pipeline_collection_part2.py`, `_part3.py`, `_graphs.py` |
| `documentation_menu_fn` kwarg | `test_app_menu_helpers.py` |
| `ratchet_state` kwarg | `test_pipeline_collection_part5.py`, `test_pipeline_owner_coverage.py` |

### F2. Private API usage

Tests legitimately test private internals. Fix: `# pyright: reportPrivateUsage=false` per-file.

Files: `test_picture_display_row_parsing.py`, `test_app_analysis_project_cache.py`,
`test_coordination_lock_state.py`, `test_repo_audit_part{3,4,8}.py`,
`test_structural_budget_inventory.py`, `devtools/test_tracing.py`

### F3. Untyped lambdas

Test callbacks passed as arguments. Fix: `# pyright: reportUnknownLambdaType=false` per-file.

### F4. Unknown test helper types

From untyped `SimpleNamespace` fixtures and mock objects. Fix: add type annotations to helpers.

## Guardrails

- Fix root causes, not symptoms.
- Suppress only for: (a) testing private internals, (b) parser type mismatch documented above.
- Never suppress `reportArgumentType` for dict-vs-dataclass — that's a parser fix.
- Smallest grounded edit per hypothesis; focused validation immediately after first edit.
- All git commands are denied from AI agent access — see AGENTS.md.
