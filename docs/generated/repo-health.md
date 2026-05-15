# Repository Health

- Status: pass
- Generated: 2026-05-13T14:08:07.862290+00:00
- Audit dir: artifacts/audit
- Audit findings: 0 (blocking: 0)
- Coverage: 88.26% minimum 87.26%
- Context: 122/180 auto-loaded lines
- AI throughput: 4
- Merge success rate: n/a
- Root junk files: 0

## Quality

- Ruff issues: 0
- Pyright: 0 errors, 0 warnings
- Pytest runtime: 62.397 seconds
- Structural budget: 22 functions, 3 classes over budget

## Largest Files

- src/sattlint/devtools/pipeline.py: 1898 lines (source)
- tests/test_gui.py: 1743 lines (test)
- tests/test_lsp_diagnostics.py: 1657 lines (test)
- tests/test_pipeline_run.py: 1458 lines (test)
- src/sattlint/analyzers/modules.py: 1432 lines (source)

## Slowest Tests

- tests.test_pipeline.test_collect_architecture_report_includes_shadowing_cli_filter: 3.137s (passed)
- tests.parser.test_corpus.test_checked_in_corpus_manifests_pass_against_repo_fixtures: 2.901s (passed)
- tests.test_pipeline_collection.test_collect_architecture_report_includes_shadowing_cli_filter: 2.702s (passed)
- tests.test_recommendation_routing.test_verify_check_catalog_passes_for_repo_audit_catalog: 1.750s (passed)
- tests.parser.test_parser_core.test_internal_modules_do_not_import_editor_api_compat_facade: 1.570s (passed)

## Trend Summary

- History snapshots: 1
- Coverage delta: 0.0
- Finding delta: -8
- Context delta: 4
- Largest file delta: -1219

## Ratchets

- Overall: pass_with_findings
- Coverage ratchet: pass at 88.26% against floor 87.26%
- Structural ratchet: pass_with_findings with 22 functions and 3 classes over budget
