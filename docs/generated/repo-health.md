# Repository Health

- Status: pass
- Generated: 2026-05-11T15:42:51.679805+00:00
- Audit dir: artifacts/audit
- Audit findings: 0 (blocking: 0)
- Coverage: 88.26% minimum 87.26%
- Context: 112/180 auto-loaded lines
- AI throughput: 4
- Merge success rate: n/a
- Root junk files: 0

## Quality

- Ruff issues: 0
- Pyright: 0 errors, 0 warnings
- Pytest runtime: 32.711 seconds
- Structural budget: 22 functions, 3 classes over budget

## Largest Files

- src/sattlint/devtools/pipeline.py: 1748 lines (source)
- tests/test_gui.py: 1743 lines (test)
- tests/test_lsp_diagnostics.py: 1657 lines (test)
- src/sattlint/analyzers/modules.py: 1436 lines (source)
- scripts/repo_health.py: 1414 lines (source)

## Slowest Tests

- tests.test_pipeline_collection.test_collect_architecture_report_includes_shadowing_cli_filter: 1.351s (passed)
- tests.test_pipeline.test_collect_architecture_report_includes_shadowing_cli_filter: 1.237s (passed)
- tests.parser.test_corpus.test_checked_in_corpus_manifests_pass_against_repo_fixtures: 1.127s (passed)
- tests.test_recommendation_routing.test_verify_check_catalog_passes_for_repo_audit_catalog: 0.691s (passed)
- tests.test_recommendation_routing.test_verify_check_catalog_passes_for_pipeline_catalog: 0.603s (passed)

## Trend Summary

- History snapshots: 1
- Coverage delta: 0.0
- Finding delta: -8
- Context delta: -6
- Largest file delta: -1369

## Ratchets

- Overall: pass_with_findings
- Coverage ratchet: pass at 88.26% against floor 87.26%
- Structural ratchet: pass_with_findings with 22 functions and 3 classes over budget
