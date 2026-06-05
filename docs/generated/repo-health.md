# Repository Health

- Status: pass
- Generated: 2026-06-02T08:47:16.646422+00:00
- Audit dir: artifacts/audit
- Audit findings: 0 (blocking: 0)
- Coverage: 88.26% minimum 87.26%
- Context: 100/180 auto-loaded lines
- AI throughput: 9
- Merge success rate: n/a
- Root junk files: 0

## Quality

- Ruff issues: 0
- Pyright: 0 errors, 0 warnings
- Pytest runtime: 52.418 seconds
- Structural budget: 22 functions, 3 classes over budget

## Largest Files

- tests/_analyzers_variables_part4.py: 2061 lines (test)
- tests/devtools/test_source_diff_report.py: 1708 lines (test)
- tests/test_pipeline_run.py: 1582 lines (test)
- src/sattlint/devtools/source_diff_report.py: 1466 lines (source)
- scripts/repo_health.py: 1432 lines (source)

## Slowest Tests

- tests.test_repo_audit.test_audit_repository_run_history_keeps_last_ten_runs_and_marks_older_entries_stale: 2.422s (passed)
- tests.test_pipeline_collection.test_collect_architecture_report_includes_shadowing_cli_filter: 2.400s (passed)
- tests.test_pipeline.test_collect_architecture_report_includes_shadowing_cli_filter: 2.214s (passed)
- tests.parser.test_corpus_edge_cases.test_checked_in_corpus_manifests_pass_against_repo_fixtures: 1.425s (passed)
- tests.parser.test_parser_core.test_internal_modules_do_not_import_editor_api_compat_facade: 1.096s (passed)

## Trend Summary

- History snapshots: 1
- Coverage delta: 0.0
- Finding delta: -8
- Context delta: -18
- Largest file delta: -1056

## Ratchets

- Overall: pass_with_findings
- Coverage ratchet: pass at 88.26% against floor 87.26%
- Structural ratchet: pass_with_findings with 22 functions and 3 classes over budget
