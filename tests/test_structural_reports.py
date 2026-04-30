from __future__ import annotations

import json
from types import SimpleNamespace

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
    assert report["ratchet"]["regressions"] == [
        {
            "metric": "facade_private_entrypoint_count",
            "expected_max": 0,
            "actual": 1,
        }
    ]


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


def test_collect_structural_budget_report_records_scan_failure_for_syntax_error(tmp_path):
    broken = tmp_path / "src" / "pkg" / "broken_syntax.py"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("def bad syntax here((\n", encoding="utf-8")

    report = structural_reports.collect_structural_budget_report(tmp_path)

    failures = [f for f in report["scan_failures"] if "broken_syntax.py" in f.get("path", "")]
    assert len(failures) == 1
    assert failures[0]["error_type"] == "SyntaxError"


def test_collect_facade_private_entrypoints_detects_importfrom_direct_private_call():
    import ast as _ast

    source = "from . import _helper_func\n\ndef run():\n    return _helper_func()\n"
    tree = _ast.parse(source)

    violations = structural_reports._collect_facade_private_entrypoints(tree, relative_path="src/sattlint/app.py")

    assert any(v["target"].endswith("_helper_func") for v in violations)


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
