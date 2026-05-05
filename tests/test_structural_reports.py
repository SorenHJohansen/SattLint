from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)
from sattlint.devtools import structural_reports


def _write(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_long_function(line_span: int) -> str:
    body = "\n".join(f"    value += {index}" for index in range(line_span - 3))
    return f"def too_long():\n    value = 0\n{body}\n    return value\n"


def _build_many_methods(method_count: int) -> str:
    methods = "\n\n".join(f"    def method_{index}(self):\n        return {index}" for index in range(method_count))
    return f"class TooManyMethods:\n{methods}\n"


def test_collect_structural_budget_report_detects_budget_offenders(tmp_path):
    filler_lines = "\n".join(f"# filler {index}" for index in range(560))
    oversized_source = "\n\n".join(
        [
            filler_lines,
            "def _walk_modules():\n    return None\n",
            _build_long_function(151),
            _build_many_methods(41),
        ]
    )
    _write(tmp_path / "src" / "pkg" / "oversized_module.py", oversized_source)

    for index in range(1, 5):
        _write(
            tmp_path / "src" / "pkg" / f"duplicate_{index}.py",
            "def _walk_modules():\n    return None\n",
        )

    oversized_test = "\n".join(
        [*(f"# filler {index}" for index in range(1205)), "def test_placeholder():", "    assert True"]
    )
    _write(tmp_path / "tests" / "test_oversized_module.py", oversized_test)

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["thresholds"] == structural_reports.STRUCTURAL_BUDGET_THRESHOLDS
    assert report["setpoints"] == structural_reports.STRUCTURAL_BUDGET_SETPOINTS
    assert report["summary"]["source_file_max_lines"] == len(oversized_source.splitlines())
    assert report["summary"]["test_file_max_lines"] == len(oversized_test.splitlines())
    assert report["metrics"]["source_file_max_lines"] == len(oversized_source.splitlines())
    assert report["metrics"]["test_file_max_lines"] == len(oversized_test.splitlines())
    assert report["source_files_over_budget"] == [
        {
            "path": "src/pkg/oversized_module.py",
            "line_count": len(oversized_source.splitlines()),
        }
    ]
    assert report["test_files_over_budget"] == [
        {
            "path": "tests/test_oversized_module.py",
            "line_count": len(oversized_test.splitlines()),
        }
    ]
    assert report["functions_over_budget"][0]["path"] == "src/pkg/oversized_module.py"
    assert report["functions_over_budget"][0]["qualname"] == "too_long"
    assert report["functions_over_budget"][0]["line_span"] == 151
    assert report["classes_over_budget"] == [
        {
            "path": "src/pkg/oversized_module.py",
            "qualname": "TooManyMethods",
            "method_count": 41,
            "start_line": report["classes_over_budget"][0]["start_line"],
            "end_line": report["classes_over_budget"][0]["end_line"],
        }
    ]
    assert report["repeated_private_names"] == [
        {
            "name": "_walk_modules",
            "file_count": 5,
            "paths": [
                "src/pkg/duplicate_1.py",
                "src/pkg/duplicate_2.py",
                "src/pkg/duplicate_3.py",
                "src/pkg/duplicate_4.py",
                "src/pkg/oversized_module.py",
            ],
        }
    ]
    assert report["scan_failures"] == []


def test_collect_structural_budget_report_ignores_short_and_method_private_name_duplicates(tmp_path):
    helper_source = "class First:\n    def _walk_modules(self):\n        return None\n\ndef _cf():\n    return None\n"
    for index in range(1, 5):
        _write(tmp_path / "src" / "pkg" / f"helper_{index}.py", helper_source)

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["repeated_private_names"] == []


def test_collect_architecture_report_includes_structural_budget_findings(monkeypatch):
    structural_budget_report = {
        "thresholds": dict(structural_reports.STRUCTURAL_BUDGET_THRESHOLDS),
        "source_files_over_budget": [{"path": "src/pkg/oversized_module.py", "line_count": 700}],
        "test_files_over_budget": [{"path": "tests/test_oversized_module.py", "line_count": 1300}],
        "functions_over_budget": [{"path": "src/pkg/oversized_module.py", "qualname": "too_long", "line_span": 151}],
        "classes_over_budget": [
            {"path": "src/pkg/oversized_module.py", "qualname": "TooManyMethods", "method_count": 41}
        ],
        "repeated_private_names": [{"name": "_walk_modules", "file_count": 5, "paths": ["src/pkg/a.py"]}],
        "facade_private_entrypoints": [
            {"path": "src/sattlint/app.py", "line": 42, "target": "app_analysis._run_checks"}
        ],
        "metrics": {"facade_private_entrypoint_count": 1},
        "ratchet": {
            "status": "fail",
            "path": "artifacts/analysis/structural_budget_ratchet.json",
            "expected_metrics": {"facade_private_entrypoint_count": 0},
            "current_metrics": {"facade_private_entrypoint_count": 1},
            "regressions": [{"metric": "facade_private_entrypoint_count", "expected_max": 0, "actual": 1}],
        },
        "scan_failures": [],
    }
    empty_catalog = SimpleNamespace(analyzers=[], rules=[])

    monkeypatch.setattr(
        structural_reports,
        "collect_structural_budget_report",
        lambda *_args, **_kwargs: structural_budget_report,
    )
    monkeypatch.setattr(structural_reports, "get_default_analyzer_catalog", lambda: empty_catalog)
    monkeypatch.setattr(structural_reports, "get_declared_cli_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_actual_cli_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_declared_lsp_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_actual_lsp_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "VARIABLE_ANALYSES", {})

    report = structural_reports.collect_architecture_report()
    finding_ids = {finding["id"] for finding in report["findings"]}

    assert report["structural_budgets"] == structural_budget_report
    assert {
        "structural-source-file-budget",
        "structural-test-file-budget",
        "structural-function-budget",
        "structural-class-budget",
        "structural-private-helper-duplication",
        "structural-facade-private-boundary",
        "structural-budget-ratchet-regression",
    } <= finding_ids


def test_collect_structural_budget_report_flags_facade_private_entrypoints_and_ratchet(tmp_path):
    _write(tmp_path / "src" / "sattlint" / "app_analysis.py", "def _run_checks():\n    return None\n")
    _write(
        tmp_path / "src" / "sattlint" / "app.py",
        "from . import app_analysis as app_analysis_module\n\n"
        "def run_menu():\n"
        "    return app_analysis_module._run_checks()\n",
    )
    _write(
        tmp_path / "artifacts" / "analysis" / "structural_budget_ratchet.json",
        json.dumps(
            {
                "kind": "sattlint.structural_budget_ratchet",
                "schema_version": 1,
                "metrics": {"facade_private_entrypoint_count": 0},
            },
            indent=2,
        ),
    )

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["facade_private_entrypoints"] == [
        {
            "path": "src/sattlint/app.py",
            "line": 4,
            "target": "app_analysis._run_checks",
        }
    ]
    assert report["metrics"]["facade_private_entrypoint_count"] == 1
    assert report["ratchet"]["status"] == "fail"
    assert report["ratchet"]["setpoint_metrics"] == structural_reports.STRUCTURAL_BUDGET_SETPOINTS
    assert report["ratchet"]["regressions"] == [
        {
            "metric": "facade_private_entrypoint_count",
            "expected_max": 0,
            "actual": 1,
        }
    ]


def test_collect_structural_budget_report_tracks_actual_max_lines_even_when_under_threshold(tmp_path):
    _write(tmp_path / "src" / "pkg" / "small.py", "def helper():\n    return 1\n")
    _write(tmp_path / "tests" / "test_small.py", "def test_helper():\n    assert True\n")

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["source_files_over_budget"] == []
    assert report["test_files_over_budget"] == []
    assert report["summary"]["source_file_max_lines"] == 2
    assert report["summary"]["test_file_max_lines"] == 2
    assert report["metrics"]["source_file_max_lines"] == 2
    assert report["metrics"]["test_file_max_lines"] == 2


def test_load_structural_budget_ratchet_returns_invalid_on_bad_json(tmp_path):
    ratchet = tmp_path / "ratchet.json"
    ratchet.write_text("not valid json{", encoding="utf-8")

    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)

    assert result["status"] == "invalid"
    assert result["metrics"] == {}
    assert "error" in result


def test_load_structural_budget_ratchet_returns_invalid_on_non_int_metrics(tmp_path):
    ratchet = tmp_path / "ratchet.json"
    import json

    ratchet.write_text(
        json.dumps({"kind": "k", "schema_version": 1, "metrics": {"count": "not_an_int"}}),
        encoding="utf-8",
    )

    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)

    assert result["status"] == "invalid"
    assert "ratchet metrics" in result["error"]


def test_load_structural_budget_ratchet_requires_exception_reason(tmp_path):
    ratchet = tmp_path / "ratchet.json"
    ratchet.write_text(
        json.dumps(
            {
                "kind": "k",
                "schema_version": 2,
                "metrics": {},
                "file_line_exceptions": {
                    "src/pkg/legacy.py": {"max_lines": 520, "reason": ""},
                },
            }
        ),
        encoding="utf-8",
    )

    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)

    assert result["status"] == "invalid"
    assert "file_line_exceptions['src/pkg/legacy.py'].reason" in result["error"]


def test_collect_structural_budget_report_allows_documented_file_line_exception(tmp_path):
    legacy_source = "\n".join(f"value_{index} = {index}" for index in range(520))
    _write(tmp_path / "src" / "pkg" / "legacy.py", legacy_source)
    _write(
        tmp_path / "artifacts" / "analysis" / "structural_budget_ratchet.json",
        json.dumps(
            {
                "kind": "sattlint.structural_budget_ratchet",
                "schema_version": 2,
                "metrics": {},
                "file_line_exceptions": {
                    "src/pkg/legacy.py": {
                        "max_lines": 520,
                        "reason": "Legacy owner module remains centralized pending extraction.",
                    }
                },
            },
            indent=2,
        ),
    )

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["source_files_over_budget"] == []
    assert report["ratchet"]["status"] == "pass"
    assert report["line_limit_exceptions"] == [
        {
            "path": "src/pkg/legacy.py",
            "line_count": 520,
            "max_lines": 520,
            "reason": "Legacy owner module remains centralized pending extraction.",
            "status": "pass",
        }
    ]


def test_collect_structural_budget_report_flags_file_line_exception_regression(tmp_path):
    legacy_source = "\n".join(f"value_{index} = {index}" for index in range(521))
    _write(tmp_path / "src" / "pkg" / "legacy.py", legacy_source)
    _write(
        tmp_path / "artifacts" / "analysis" / "structural_budget_ratchet.json",
        json.dumps(
            {
                "kind": "sattlint.structural_budget_ratchet",
                "schema_version": 2,
                "metrics": {},
                "file_line_exceptions": {
                    "src/pkg/legacy.py": {
                        "max_lines": 520,
                        "reason": "Legacy owner module remains centralized pending extraction.",
                    }
                },
            },
            indent=2,
        ),
    )

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["source_files_over_budget"] == [{"path": "src/pkg/legacy.py", "line_count": 521}]
    assert report["ratchet"]["status"] == "fail"
    assert report["ratchet"]["regressions"] == [
        {
            "path": "src/pkg/legacy.py",
            "expected_max": 520,
            "actual": 521,
            "reason": "Legacy owner module remains centralized pending extraction.",
        }
    ]


def test_collect_structural_budget_report_reads_structural_exception_from_file_debt_ratchet(tmp_path):
    legacy_source = "\n".join(f"value_{index} = {index}" for index in range(520))
    _write(tmp_path / "src" / "pkg" / "legacy.py", legacy_source)
    _write(
        tmp_path / "artifacts" / "analysis" / "structural_budget_ratchet.json",
        json.dumps(
            {
                "kind": "sattlint.structural_budget_ratchet",
                "schema_version": 3,
                "metrics": {},
                "file_line_exceptions": {},
            },
            indent=2,
        ),
    )
    _write(
        tmp_path / "artifacts" / "analysis" / "file_debt_ratchet.json",
        json.dumps(
            {
                "kind": "sattlint.file_debt_ratchet",
                "schema_version": 1,
                "files": {
                    "src/pkg/legacy.py": {
                        "structural": {
                            "allow_rebaseline": False,
                            "current_baseline": 520,
                            "target": 500,
                            "touch_rule": "must_not_grow",
                            "reason": "Legacy owner module remains centralized pending extraction.",
                        }
                    }
                },
            },
            indent=2,
        ),
    )

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["source_files_over_budget"] == []
    assert report["ratchet"]["status"] == "pass"
    assert report["line_limit_exceptions"] == [
        {
            "path": "src/pkg/legacy.py",
            "line_count": 520,
            "max_lines": 520,
            "reason": "Legacy owner module remains centralized pending extraction.",
            "status": "pass",
        }
    ]


def test_collect_structural_budget_report_records_scan_failure_for_syntax_error(tmp_path):
    broken = tmp_path / "src" / "pkg" / "broken_syntax.py"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("def bad syntax here((\n", encoding="utf-8")

    report = structural_reports.collect_structural_budget_report(tmp_path)

    failures = [f for f in report["scan_failures"] if "broken_syntax.py" in f.get("path", "")]
    assert len(failures) == 1
    assert failures[0]["error_type"] == "SyntaxError"


def test_collect_structural_budget_report_counts_non_utf8_files_in_line_budget(tmp_path):
    broken = tmp_path / "tests" / "test_non_utf8.py"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_bytes((b"value = 1\n" * 520) + b"\xf8\n")

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["test_files_over_budget"] == [{"path": "tests/test_non_utf8.py", "line_count": 521}]
    failures = [f for f in report["scan_failures"] if f.get("path") == "tests/test_non_utf8.py"]
    assert len(failures) == 1
    assert failures[0]["error_type"] == "UnicodeDecodeError"


def test_collect_facade_private_entrypoints_detects_importfrom_direct_private_call():
    import ast as _ast

    source = "from . import _helper_func\n\ndef run():\n    return _helper_func()\n"
    tree = _ast.parse(source)

    violations = structural_reports._collect_facade_private_entrypoints(tree, relative_path="src/sattlint/app.py")

    assert any(v["target"].endswith("_helper_func") for v in violations)


def test_structural_ratchet_main_reports_pass(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        structural_reports,
        "collect_structural_budget_report",
        lambda *_args, **_kwargs: {
            "ratchet": {
                "status": "pass",
                "path": "artifacts/analysis/structural_budget_ratchet.json",
                "expected_metrics": {"function_over_budget_count": 18},
                "current_metrics": {"function_over_budget_count": 18},
                "regressions": [],
            }
        },
    )

    exit_code = structural_reports.main(["--repo-root", str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Structural ratchet: pass" in captured.out
    assert "Regressions: []" in captured.out


def test_structural_ratchet_main_reports_json_failures(monkeypatch, capsys, tmp_path):
    expected = {
        "status": "fail",
        "path": "ratchet.json",
        "expected_metrics": {"function_over_budget_count": 12},
        "current_metrics": {"function_over_budget_count": 18},
        "regressions": [
            {
                "metric": "function_over_budget_count",
                "expected_max": 12,
                "actual": 18,
            }
        ],
    }
    monkeypatch.setattr(
        structural_reports,
        "collect_structural_budget_report",
        lambda *_args, **_kwargs: {"ratchet": expected},
    )

    exit_code = structural_reports.main(
        ["--repo-root", str(tmp_path), "--ratchet-path", str(tmp_path / "ratchet.json"), "--json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == expected


def test_structural_ratchet_main_uses_sys_argv_when_called_without_explicit_args(monkeypatch, capsys, tmp_path):
    expected = {
        "status": "fail",
        "path": "ratchet.json",
        "expected_metrics": {},
        "current_metrics": {},
        "regressions": [
            {
                "metric": "test_file_over_budget_count",
                "expected_max": 10,
                "actual": 17,
            }
        ],
    }
    monkeypatch.setattr(
        structural_reports,
        "collect_structural_budget_report",
        lambda *_args, **_kwargs: {"ratchet": expected},
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "sattlint-structural-ratchet",
            "--repo-root",
            str(tmp_path),
            "--json",
        ],
    )

    exit_code = structural_reports.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == expected


def test_collect_architecture_report_flags_missing_acceptance_tests(monkeypatch):
    empty_budget = {
        "thresholds": dict(structural_reports.STRUCTURAL_BUDGET_THRESHOLDS),
        "source_files_over_budget": [],
        "test_files_over_budget": [],
        "functions_over_budget": [],
        "classes_over_budget": [],
        "repeated_private_names": [],
        "facade_private_entrypoints": [],
        "metrics": {"facade_private_entrypoint_count": 0},
        "ratchet": {
            "status": "pass",
            "path": "ratchet.json",
            "expected_metrics": {},
            "current_metrics": {},
            "regressions": [],
        },
        "scan_failures": [],
    }
    fake_spec = SimpleNamespace(key="no-tests-analyzer", enabled=True, supports_live_diagnostics=False)
    fake_delivery = SimpleNamespace(
        cli_exposed=False, lsp_exposed=False, exposed_via=[], acceptance_tests=[], output_artifacts=[]
    )
    fake_analyzer = SimpleNamespace(spec=fake_spec, delivery=fake_delivery, summary_output="no-tests-analyzer.summary")
    monkeypatch.setattr(structural_reports, "collect_structural_budget_report", lambda *a, **k: empty_budget)
    monkeypatch.setattr(
        structural_reports,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=[fake_analyzer], rules=[]),
    )
    monkeypatch.setattr(structural_reports, "get_declared_cli_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_actual_cli_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_declared_lsp_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_actual_lsp_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "VARIABLE_ANALYSES", {})

    report = structural_reports.collect_architecture_report()
    finding_ids = {f["id"] for f in report["findings"]}

    assert "analyzer-acceptance-test-gap" in finding_ids


def test_collect_architecture_report_flags_metadata_drifts_and_rule_metadata_gaps(monkeypatch):
    empty_budget = {
        "thresholds": dict(structural_reports.STRUCTURAL_BUDGET_THRESHOLDS),
        "source_files_over_budget": [],
        "test_files_over_budget": [],
        "functions_over_budget": [],
        "classes_over_budget": [],
        "repeated_private_names": [],
        "facade_private_entrypoints": [],
        "metrics": {"facade_private_entrypoint_count": 0},
        "ratchet": {
            "status": "pass",
            "path": "ratchet.json",
            "expected_metrics": {},
            "current_metrics": {},
            "regressions": [],
        },
        "scan_failures": [],
    }
    fake_spec = SimpleNamespace(key="metadata-gap-analyzer", enabled=True, supports_live_diagnostics=False)
    fake_delivery = SimpleNamespace(
        cli_exposed=False,
        lsp_exposed=False,
        exposed_via=[],
        acceptance_tests=[],
        output_artifacts=["promised-artifact.json"],
    )
    fake_analyzer = SimpleNamespace(
        spec=fake_spec,
        delivery=fake_delivery,
        summary_output="metadata-gap-analyzer.summary",
    )
    fake_rule = SimpleNamespace(
        id="rule-gap",
        acceptance_tests=[],
        corpus_cases=[],
        mutation_applicability="applicable",
        suppression_modes=None,
        incremental_safe=None,
        outputs=[],
    )
    fake_unspecified_rule = SimpleNamespace(
        id="rule-unspecified",
        acceptance_tests=[],
        corpus_cases=[],
        mutation_applicability=None,
        suppression_modes=None,
        incremental_safe=None,
        outputs=[],
    )

    monkeypatch.setattr(structural_reports, "collect_structural_budget_report", lambda *a, **k: empty_budget)
    monkeypatch.setattr(
        structural_reports,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=[fake_analyzer], rules=[fake_rule, fake_unspecified_rule]),
    )
    monkeypatch.setattr(structural_reports, "get_declared_cli_analyzer_keys", lambda: ["declared-cli"])
    monkeypatch.setattr(structural_reports, "get_actual_cli_analyzer_keys", lambda: ["actual-cli"])
    monkeypatch.setattr(structural_reports, "get_declared_lsp_analyzer_keys", lambda: ["declared-lsp"])
    monkeypatch.setattr(structural_reports, "get_actual_lsp_analyzer_keys", lambda: ["actual-lsp"])
    monkeypatch.setattr(
        structural_reports,
        "VARIABLE_ANALYSES",
        {"unused": ("Unused", {structural_reports.IssueKind.UNUSED})},
    )

    report = structural_reports.collect_architecture_report()
    finding_ids = {finding["id"] for finding in report["findings"]}

    assert {
        "cli-variable-filter-gap",
        "cli-analyzer-metadata-drift",
        "lsp-analyzer-metadata-drift",
        "analyzer-exposure-gap",
        "analyzer-acceptance-test-gap",
        "rule-acceptance-test-gap",
        "rule-corpus-link-gap",
        "rule-mutation-metadata-gap",
        "rule-suppression-metadata-gap",
        "rule-incremental-safety-gap",
        "analyzer-output-artifact-gap",
    } <= finding_ids
    assert report["phase2_rule_metadata_gate"]["status"] == "fail"
    assert report["phase2_rule_metadata_gate"]["blocking_rule_ids"] == ["rule-gap", "rule-unspecified"]
    assert report["phase2_rule_metadata_gate"]["advisory_rule_ids"] == ["rule-gap", "rule-unspecified"]


def test_collect_workspace_graph_inputs_collects_snapshots_and_failures(monkeypatch, tmp_path):
    entry_ok = tmp_path / "ok.s"
    entry_fail = tmp_path / "fail.s"
    discovery = SimpleNamespace(program_files=[entry_ok, entry_fail])

    monkeypatch.setattr(structural_reports, "discover_workspace_sources", lambda _root: discovery)

    def fake_load_workspace_snapshot(entry_file, **_kwargs):
        if entry_file == entry_fail:
            raise RuntimeError("boom")
        return SimpleNamespace(entry_file=entry_file)

    monkeypatch.setattr(structural_reports, "load_workspace_snapshot", fake_load_workspace_snapshot)

    report = structural_reports.collect_workspace_graph_inputs(tmp_path)

    assert report.discovery is discovery
    assert report.snapshots == [SimpleNamespace(entry_file=entry_ok)]
    assert report.snapshot_failures == [
        {
            "entry_file": "fail.s",
            "error": "boom",
            "error_type": "RuntimeError",
        }
    ]


@pytest.mark.parametrize(
    ("index", "total", "expected"),
    [
        (1, 3, True),
        (1, 20, True),
        (10, 20, True),
        (11, 20, False),
        (20, 20, True),
    ],
)
def test_should_emit_snapshot_progress_uses_small_first_last_and_tenth_markers(index, total, expected):
    assert structural_reports._should_emit_snapshot_progress(index, total) is expected


def test_registry_and_discovery_helpers_cover_structural_entry_scoping(monkeypatch, tmp_path):
    monkeypatch.setattr(
        structural_reports,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(to_report=lambda *, generated_by: {"generated_by": generated_by}),
    )

    scoped_entry = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "entry.s"
    other_entry = tmp_path / "src" / "pkg" / "other.s"
    discovery = SimpleNamespace(
        workspace_root=tmp_path,
        source_dirs=(tmp_path / "src",),
        program_files=[scoped_entry, other_entry],
        dependency_files=[tmp_path / "Libs" / "dep.s"],
        abb_lib_dir=tmp_path / "Libs",
        program_files_by_stem={"entry": scoped_entry},
        dependency_files_by_stem={"dep": tmp_path / "Libs" / "dep.s"},
    )

    assert structural_reports.collect_analyzer_registry_report() == {"generated_by": "sattlint.devtools.pipeline"}
    assert structural_reports._structural_entry_files(tmp_path, (scoped_entry, other_entry)) == (scoped_entry,)

    scoped_discovery = structural_reports._structural_report_discovery(tmp_path, discovery)
    passthrough_discovery = structural_reports._structural_report_discovery(
        tmp_path,
        SimpleNamespace(**{**discovery.__dict__, "program_files": [other_entry]}),
    )

    assert scoped_discovery.program_files == (scoped_entry,)
    assert passthrough_discovery.program_files == [other_entry]


def test_graph_snapshot_helpers_build_and_collect_reports(tmp_path):
    entry_file = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "entry.s"
    discovery = SimpleNamespace(
        program_files=[entry_file],
        dependency_files=[tmp_path / "Libs" / "dep.s"],
    )
    definition = SimpleNamespace(
        declaration_module_path=("Target",),
        canonical_path="Target.value",
        field_path=None,
    )
    ignored_definition = SimpleNamespace(
        declaration_module_path=("Target",),
        canonical_path="Target.ignored",
        field_path=("child",),
    )
    read_access = SimpleNamespace(use_module_path=("Source",), kind=SimpleNamespace(value="read"))
    write_access = SimpleNamespace(use_module_path=None, kind=SimpleNamespace(value="write"))
    snapshot = SimpleNamespace(
        entry_file=entry_file,
        project_graph=SimpleNamespace(library_dependencies={"LibA": {"LibB"}}),
        base_picture=SimpleNamespace(name="Root"),
        definitions=[definition, ignored_definition],
        find_accesses_to=lambda current: [read_access, write_access] if current is definition else [],
    )

    dependency_nodes: dict[str, dict[str, object]] = {}
    dependency_edges: dict[tuple[str, str], dict[str, object]] = {}
    call_nodes: dict[str, dict[str, object]] = {}
    call_edges: dict[tuple[str, str], dict[str, object]] = {}

    structural_reports._accumulate_dependency_graph_snapshot(
        snapshot,
        workspace_root=tmp_path,
        node_index=dependency_nodes,
        edge_index=dependency_edges,
    )
    structural_reports._accumulate_call_graph_snapshot(
        snapshot,
        workspace_root=tmp_path,
        node_index=call_nodes,
        edge_index=call_edges,
    )

    dependency_report = structural_reports._build_dependency_graph_report(
        workspace_root=tmp_path,
        discovery=discovery,
        node_index=dependency_nodes,
        edge_index=dependency_edges,
        snapshot_count=1,
        snapshot_failures=[{"entry_file": "broken.s", "error": "boom", "error_type": "RuntimeError"}],
    )
    call_report = structural_reports._build_call_graph_report(
        workspace_root=tmp_path,
        node_index=call_nodes,
        edge_index=call_edges,
        snapshot_count=1,
        snapshot_failures=[],
    )
    collected_dependency_report = structural_reports.collect_dependency_graph_report(
        tmp_path,
        graph_inputs=(
            discovery,
            [snapshot],
            [{"entry_file": "broken.s", "error": "boom", "error_type": "RuntimeError"}],
        ),
    )
    collected_call_report = structural_reports.collect_call_graph_report(
        tmp_path,
        graph_inputs=(discovery, [snapshot], []),
    )

    assert dependency_nodes == {
        "LibA": {"id": "LibA", "kind": "library"},
        "LibB": {"id": "LibB", "kind": "library"},
    }
    assert dependency_report["edges"] == [
        {
            "source": "LibA",
            "target": "LibB",
            "kind": "depends_on",
            "entries": ["tests/fixtures/sample_sattline_files/entry.s"],
        }
    ]
    assert dependency_report["snapshot_count"] == 1
    assert dependency_report["snapshot_failures"][0]["entry_file"] == "broken.s"

    assert call_nodes == {
        "target": {"id": "Target", "kind": "module"},
        "source": {"id": "Source", "kind": "module"},
        "root": {"id": "Root", "kind": "module"},
    }
    assert call_report["edges"] == [
        {
            "source": "Root",
            "target": "Target",
            "kind": "module-access",
            "reads": 0,
            "writes": 1,
            "access_count": 1,
            "symbol_count": 1,
            "symbols": ["Target.value"],
            "entries": ["tests/fixtures/sample_sattline_files/entry.s"],
        },
        {
            "source": "Source",
            "target": "Target",
            "kind": "module-access",
            "reads": 1,
            "writes": 0,
            "access_count": 1,
            "symbol_count": 1,
            "symbols": ["Target.value"],
            "entries": ["tests/fixtures/sample_sattline_files/entry.s"],
        },
    ]
    assert collected_dependency_report["edges"] == dependency_report["edges"]
    assert collected_call_report["edges"] == call_report["edges"]


def test_stream_and_bundle_helpers_cover_progress_failures_and_normalization(monkeypatch, tmp_path):
    entry_ok = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "ok.s"
    entry_fail = tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "fail.s"
    full_discovery = SimpleNamespace(program_files=[entry_ok, entry_fail], dependency_files=[])
    filtered_discovery = SimpleNamespace(program_files=[entry_ok, entry_fail], dependency_files=[])
    ok_snapshot = SimpleNamespace(entry_file=entry_ok)
    progress_messages: list[str] = []
    streamed_graph_inputs = structural_reports.WorkspaceGraphInputs(
        discovery=filtered_discovery,
        snapshots=[],
        snapshot_failures=[
            {
                "entry_file": "tests/fixtures/sample_sattline_files/fail.s",
                "error": "boom",
                "error_type": "ValueError",
            }
        ],
    )

    monkeypatch.setattr(structural_reports, "discover_workspace_sources", lambda _root: full_discovery)
    monkeypatch.setattr(structural_reports, "_structural_report_discovery", lambda _root, _disc: filtered_discovery)

    def fake_load_workspace_snapshot(entry_file, **_kwargs):
        if entry_file == entry_fail:
            raise ValueError("boom")
        return ok_snapshot

    monkeypatch.setattr(structural_reports, "load_workspace_snapshot", fake_load_workspace_snapshot)
    monkeypatch.setattr(
        structural_reports,
        "_accumulate_dependency_graph_snapshot",
        lambda snapshot, **kwargs: kwargs["node_index"].setdefault(
            "dep", {"id": snapshot.entry_file.stem, "kind": "library"}
        ),
    )
    monkeypatch.setattr(
        structural_reports,
        "_accumulate_call_graph_snapshot",
        lambda snapshot, **kwargs: kwargs["node_index"].setdefault(
            "call", {"id": snapshot.entry_file.stem, "kind": "module"}
        ),
    )

    graph_inputs, dependency_report, call_report = structural_reports._stream_workspace_graph_reports(
        tmp_path,
        progress_callback=progress_messages.append,
    )

    assert graph_inputs.snapshots == []
    assert graph_inputs.snapshot_failures == streamed_graph_inputs.snapshot_failures
    assert dependency_report["snapshot_count"] == 1
    assert call_report["snapshot_count"] == 1
    assert progress_messages == [
        "Structural: loading 1/2 tests/fixtures/sample_sattline_files/ok.s",
        "Structural: loading 2/2 tests/fixtures/sample_sattline_files/fail.s",
        "Structural: failed 2/2 tests/fixtures/sample_sattline_files/fail.s (ValueError)",
    ]

    normalized_none = structural_reports._normalize_graph_inputs(None, workspace_root=tmp_path)
    normalized_tuple = structural_reports._normalize_graph_inputs(
        (filtered_discovery, [ok_snapshot], [{"entry_file": "fail.s"}]),
        workspace_root=tmp_path,
    )

    monkeypatch.setattr(structural_reports, "collect_workspace_graph_inputs", lambda _root: streamed_graph_inputs)
    normalized_none = structural_reports._normalize_graph_inputs(None, workspace_root=tmp_path)

    monkeypatch.setattr(structural_reports, "collect_architecture_report", lambda: {"name": "architecture"})
    monkeypatch.setattr(structural_reports, "collect_analyzer_registry_report", lambda: {"name": "registry"})
    monkeypatch.setattr(
        structural_reports,
        "_stream_workspace_graph_reports",
        lambda _root, progress_callback=None: (streamed_graph_inputs, {"name": "dependency"}, {"name": "call"}),
    )
    monkeypatch.setattr(structural_reports, "collect_graphics_layout_report", lambda *_a, **_k: {"name": "graphics"})
    monkeypatch.setattr(structural_reports, "collect_impact_analysis_report", lambda *_a, **_k: {"name": "impact"})

    bundle = structural_reports.collect_structural_reports(tmp_path)

    assert normalized_none is streamed_graph_inputs
    assert normalized_tuple.discovery is filtered_discovery
    assert normalized_tuple.snapshots == [ok_snapshot]
    assert normalized_tuple.snapshot_failures == [{"entry_file": "fail.s"}]
    assert bundle.architecture_report == {"name": "architecture"}
    assert bundle.analyzer_registry_report == {"name": "registry"}
    assert bundle.graph_inputs is streamed_graph_inputs
    assert bundle.dependency_graph_report == {"name": "dependency"}
    assert bundle.call_graph_report == {"name": "call"}
    assert bundle.graphics_layout_report == {"name": "graphics"}
    assert bundle.impact_analysis_report == {"name": "impact"}


def test_access_iteration_and_graphics_helpers_cover_iterator_and_optional_fields(tmp_path):
    definition = SimpleNamespace(canonical_path="Target.value", field_path=None)
    iterator_snapshot = SimpleNamespace(
        iter_access_events_by_definition=lambda *, roots_only: [(definition, ["access"])],
    )
    fallback_snapshot = SimpleNamespace(
        definitions=[definition, SimpleNamespace(field_path=("child",))],
        find_accesses_to=lambda current: [current.canonical_path],
    )
    header = ModuleHeader(
        name="Module",
        invoke_coord=(1, 2, 3, 4, 5),
        invocation_arguments=("A",),
        layer_info="L1",
        zoom_limits=(0.5, 2.0),
        zoomable=True,
    )
    moduledef = ModuleDef(
        clipping_bounds=((1, 2), (3, 4)),
        zoom_limits=(0.25, 1.5),
        grid=0.5,
        zoomable=True,
    )
    resolved_moduletype = ModuleTypeDef(name="MT", origin_file="lib/file.s", origin_lib="Lib")

    entry = structural_reports._graphics_layout_entry(
        workspace_root=tmp_path,
        entry_file=tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "entry.s",
        module_path=("Root", "Child"),
        module_kind="moduletype-instance",
        header=header,
        moduledef=moduledef,
        definition_scope="module",
        moduledef_origin_kind="moduletype-definition",
        moduletype_name="MT",
        resolved_moduletype=resolved_moduletype,
        resolution_error="warn",
    )
    drift_payload = structural_reports._graphics_layout_group_payload(
        module_kind="module",
        module_name="Child",
        members=[
            entry,
            {
                **entry,
                "module_path": "Root.Other",
                "moduledef": {**entry["moduledef"], "grid": 0.75},
            },
        ],
    )
    consistent_payload = structural_reports._graphics_layout_group_payload(
        module_kind="module",
        module_name="Child",
        members=[entry],
    )

    assert list(structural_reports._iter_snapshot_accesses_by_definition(iterator_snapshot)) == [
        (definition, ["access"])
    ]
    assert list(structural_reports._iter_snapshot_accesses_by_definition(fallback_snapshot)) == [
        (definition, ["Target.value"])
    ]
    assert structural_reports._serialize_invoke_coord(header) == {
        "coords": [1.0, 2.0, 3.0, 4.0, 5.0],
        "arguments": ["A"],
        "layer": "L1",
        "zoom_limits": [0.5, 2.0],
        "zoomable": True,
    }
    assert structural_reports._serialize_moduledef(moduledef) == {
        "clipping_origin": [1.0, 2.0],
        "clipping_size": [3.0, 4.0],
        "zoom_limits": [0.25, 1.5],
        "grid": 0.5,
        "zoomable": True,
    }
    assert structural_reports._stable_json_marker({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    assert structural_reports._graphics_field_value(entry, "moduledef.grid") == 0.5
    assert structural_reports._graphics_field_value(entry, "moduledef.grid.value") is None
    assert drift_payload["status"] == "drift"
    assert drift_payload["differing_fields"]
    assert drift_payload["field_variants"]
    assert consistent_payload["status"] == "consistent"
    assert entry["relative_module_path"] == "Child"
    assert entry["moduletype_name"] == "MT"
    assert entry["resolved_moduletype"] == {
        "name": "MT",
        "origin_file": "lib/file.s",
        "origin_lib": "Lib",
    }
    assert entry["resolution_error"] == "warn"


def test_walk_graphics_layout_children_covers_recursive_moduletype_and_resolution_failure(monkeypatch, tmp_path):
    recursive_type = ModuleTypeDef(
        name="ResolvedType",
        moduledef=ModuleDef(grid=0.25),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="NestedLeaf", invoke_coord=(0, 0, 0, 0, 0)),
                moduledef=ModuleDef(grid=0.5),
            ),
            ModuleTypeInstance(
                header=ModuleHeader(name="NestedSelf", invoke_coord=(0, 0, 0, 0, 0)),
                moduletype_name="ResolvedType",
            ),
        ],
        origin_lib="Lib",
        origin_file="Lib/ResolvedType.s",
    )

    def fake_resolve(_bp, moduletype_name, *, current_library=None, unavailable_libraries=None):
        assert unavailable_libraries == {"Ghost"}
        if moduletype_name == "MissingType":
            raise LookupError("missing moduletype")
        return recursive_type

    monkeypatch.setattr(structural_reports, "resolve_moduletype_def_strict", fake_resolve)

    entries: list[dict[str, object]] = []
    active_moduletype_keys: set[tuple[str, str]] = set()
    children = [
        SingleModule(
            header=ModuleHeader(name="Local", invoke_coord=(0, 0, 0, 0, 0)),
            moduledef=ModuleDef(grid=1.0),
        ),
        FrameModule(
            header=ModuleHeader(name="Frame", invoke_coord=(0, 0, 0, 0, 0)),
            submodules=[
                SingleModule(
                    header=ModuleHeader(name="FrameLeaf", invoke_coord=(0, 0, 0, 0, 0)),
                    moduledef=ModuleDef(grid=2.0),
                )
            ],
            moduledef=ModuleDef(grid=1.5),
        ),
        ModuleTypeInstance(
            header=ModuleHeader(name="Resolved", invoke_coord=(0, 0, 0, 0, 0)),
            moduletype_name="ResolvedType",
        ),
        ModuleTypeInstance(
            header=ModuleHeader(name="Broken", invoke_coord=(0, 0, 0, 0, 0)),
            moduletype_name="MissingType",
        ),
    ]

    structural_reports._walk_graphics_layout_children(
        bp=cast(Any, SimpleNamespace(name="BasePicture")),
        children=children,
        entry_file=tmp_path / "tests" / "fixtures" / "sample_sattline_files" / "entry.s",
        workspace_root=tmp_path,
        snapshot=SimpleNamespace(project_graph=SimpleNamespace(unavailable_libraries={"Ghost"})),
        entries=entries,
        parent_path=("BasePicture",),
        current_library=None,
        definition_scope="module",
        active_moduletype_keys=active_moduletype_keys,
    )

    entry_names = [entry["module_path"] for entry in entries]

    assert entry_names == [
        "BasePicture.Local",
        "BasePicture.Frame",
        "BasePicture.Frame.FrameLeaf",
        "BasePicture.Resolved",
        "BasePicture.Resolved.NestedLeaf",
        "BasePicture.Resolved.NestedSelf",
        "BasePicture.Broken",
    ]
    assert entries[3]["moduledef_origin_kind"] == "moduletype-definition"
    assert entries[5]["moduledef_origin_kind"] == "moduletype-definition"
    assert entries[6]["moduledef_origin_kind"] == "unresolved-moduletype"
    assert entries[6]["resolution_error"] == "missing moduletype"
    assert active_moduletype_keys == set()


def test_collect_structural_reports_uses_provided_graph_inputs_branch(monkeypatch, tmp_path):
    discovery = SimpleNamespace(program_files=[], dependency_files=[])
    tuple_graph_inputs = (discovery, [SimpleNamespace(entry_file=tmp_path / "entry.s")], [{"entry_file": "entry.s"}])
    collector_calls: list[tuple[str, object]] = []

    monkeypatch.setattr(structural_reports, "collect_architecture_report", lambda: {"name": "architecture"})
    monkeypatch.setattr(structural_reports, "collect_analyzer_registry_report", lambda: {"name": "registry"})
    monkeypatch.setattr(
        structural_reports,
        "collect_dependency_graph_report",
        lambda _root, *, graph_inputs: collector_calls.append(("dependency", graph_inputs)) or {"name": "dependency"},
    )
    monkeypatch.setattr(
        structural_reports,
        "collect_call_graph_report",
        lambda _root, *, graph_inputs: collector_calls.append(("call", graph_inputs)) or {"name": "call"},
    )
    monkeypatch.setattr(structural_reports, "collect_graphics_layout_report", lambda *_a, **_k: {"name": "graphics"})
    monkeypatch.setattr(structural_reports, "collect_impact_analysis_report", lambda *_a, **_k: {"name": "impact"})

    bundle = structural_reports.collect_structural_reports(tmp_path, graph_inputs=tuple_graph_inputs)

    assert isinstance(bundle.graph_inputs, structural_reports.WorkspaceGraphInputs)
    assert bundle.graph_inputs.discovery is discovery
    assert [name for name, _inputs in collector_calls] == ["dependency", "call"]
    assert collector_calls[0][1] is bundle.graph_inputs
    assert collector_calls[1][1] is bundle.graph_inputs
    assert bundle.dependency_graph_report == {"name": "dependency"}
    assert bundle.call_graph_report == {"name": "call"}
