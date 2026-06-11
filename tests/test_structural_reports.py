from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

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
    filler_lines = "\n".join(f"value_{index} = {index}" for index in range(560))
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
        [*(f"FILLER_{index} = {index}" for index in range(1205)), "def test_placeholder():", "    assert True"]
    )
    _write(tmp_path / "tests" / "test_oversized_module.py", oversized_test)

    report = structural_reports.collect_structural_budget_report(tmp_path)
    oversized_source_structural_lines = structural_reports.count_structural_lines(oversized_source)
    oversized_test_structural_lines = structural_reports.count_structural_lines(oversized_test)

    assert report["thresholds"] == structural_reports.STRUCTURAL_BUDGET_THRESHOLDS
    assert report["setpoints"] == structural_reports.STRUCTURAL_BUDGET_SETPOINTS
    assert report["summary"]["source_file_max_lines"] == oversized_source_structural_lines
    assert report["summary"]["test_file_max_lines"] == oversized_test_structural_lines
    assert report["metrics"]["source_file_max_lines"] == oversized_source_structural_lines
    assert report["metrics"]["test_file_max_lines"] == oversized_test_structural_lines
    assert report["source_files_over_budget"] == [
        {
            "path": "src/pkg/oversized_module.py",
            "line_count": oversized_source_structural_lines,
        }
    ]
    assert report["test_files_over_budget"] == [
        {
            "path": "tests/test_oversized_module.py",
            "line_count": oversized_test_structural_lines,
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


def test_collect_structural_budget_report_treats_scripts_as_source_budget_files(tmp_path):
    oversized_script = "\n".join(f"value_{index} = {index}" for index in range(520))
    _write(tmp_path / "scripts" / "check_demo.py", oversized_script)

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["source_files_over_budget"] == [{"path": "scripts/check_demo.py", "line_count": 520}]
    assert report["test_files_over_budget"] == []
    assert report["summary"]["source_file_max_lines"] == 520
    assert report["metrics"]["source_file_max_lines"] == 520


def test_load_structural_budget_ratchet_returns_invalid_on_bad_json(tmp_path):
    ratchet = tmp_path / "ratchet.json"
    ratchet.write_text("not valid json{", encoding="utf-8")

    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)

    assert result["status"] == "invalid"
    assert result["metrics"] == {}
    assert "error" in result


def test_load_structural_budget_ratchet_returns_invalid_on_non_int_metrics(tmp_path):
    ratchet = tmp_path / "ratchet.json"
    import json  # noqa: PLC0415

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
    import ast as _ast  # noqa: PLC0415

    source = "from . import _helper_func\n\ndef run():\n    return _helper_func()\n"
    tree = _ast.parse(source)

    violations = structural_reports._collect_facade_private_entrypoints(tree, relative_path="src/sattlint/app.py")

    assert any(v["target"].endswith("_helper_func") for v in violations)


def test_collect_facade_private_entrypoints_and_exception_normalization_cover_validation_edges():
    import ast as _ast  # noqa: PLC0415

    source = "import pkg.helpers as helpers_module\n\ndef run():\n    return helpers_module._secret()\n"
    tree = _ast.parse(source)

    violations = structural_reports._collect_facade_private_entrypoints(tree, relative_path="src/sattlint/app.py")

    assert violations == [{"path": "src/sattlint/app.py", "line": 4, "target": "pkg.helpers._secret"}]

    with pytest.raises(ValueError, match="JSON object keyed"):
        structural_reports._normalize_file_line_exceptions([], label="ratchet")
    with pytest.raises(ValueError, match="non-empty strings"):
        structural_reports._normalize_file_line_exceptions({"": {"max_lines": 1, "reason": "ok"}}, label="ratchet")
    with pytest.raises(ValueError, match="JSON object"):
        structural_reports._normalize_file_line_exceptions({"src/demo.py": []}, label="ratchet")
    with pytest.raises(ValueError, match="positive integer"):
        structural_reports._normalize_file_line_exceptions(
            {"src/demo.py": {"max_lines": 0, "reason": "ok"}},
            label="ratchet",
        )


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


def test_load_structural_budget_ratchet_rejects_invalid_file_debt_shapes(tmp_path):
    ratchet = tmp_path / "ratchet.json"
    ratchet.write_text(json.dumps({"kind": "k", "schema_version": 1, "metrics": {}}), encoding="utf-8")
    file_debt = tmp_path / structural_reports.FILE_DEBT_RATCHET_PATH
    file_debt.parent.mkdir(parents=True, exist_ok=True)

    file_debt.write_text("{not json", encoding="utf-8")
    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)
    assert result["status"] == "invalid"

    file_debt.write_text(json.dumps({"files": []}), encoding="utf-8")
    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)
    assert result["status"] == "invalid"

    file_debt.write_text(json.dumps({"files": {"src/demo.py": []}}), encoding="utf-8")
    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)
    assert result["status"] == "invalid"

    file_debt.write_text(json.dumps({"files": {"src/demo.py": {"other": {}}}}), encoding="utf-8")
    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)
    assert result["status"] == "loaded"
    assert result["file_line_exceptions"] == {}

    file_debt.write_text(json.dumps({"files": {"src/demo.py": {"structural": []}}}), encoding="utf-8")
    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)
    assert result["status"] == "invalid"

    file_debt.write_text(
        json.dumps({"files": {"src/demo.py": {"structural": {"current_baseline": 0, "reason": "ok"}}}}),
        encoding="utf-8",
    )
    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)
    assert result["status"] == "invalid"

    file_debt.write_text(
        json.dumps({"files": {"src/demo.py": {"structural": {"current_baseline": 5, "reason": ""}}}}),
        encoding="utf-8",
    )
    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)
    assert result["status"] == "invalid"

    ratchet.write_text(
        json.dumps(
            {
                "kind": "k",
                "schema_version": 1,
                "metrics": {},
                "file_line_exceptions": {"src/demo.py": {"max_lines": 7, "reason": "legacy"}},
            }
        ),
        encoding="utf-8",
    )
    file_debt.write_text(
        json.dumps({"files": {"src/demo.py": {"structural": {"current_baseline": 5, "reason": "different"}}}}),
        encoding="utf-8",
    )
    result = structural_reports._load_structural_budget_ratchet(tmp_path, ratchet_path=ratchet)
    assert result["status"] == "invalid"


def test_collect_structural_budget_report_skips_missing_line_counts_and_functions_without_end_lines(
    monkeypatch, tmp_path
):
    source_file = tmp_path / "src" / "demo.py"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("def helper():\n    return 1\n", encoding="utf-8")

    monkeypatch.setattr(structural_reports, "iter_structural_python_files", lambda _root: (("src", source_file),))
    monkeypatch.setattr(structural_reports, "iter_structural_markdown_files", lambda _root: ())
    monkeypatch.setattr(
        structural_reports,
        "read_structural_text",
        lambda _path: (None, None, {"error": "decode failed", "error_type": "UnicodeDecodeError"}),
    )

    skipped_report = structural_reports.collect_structural_budget_report(tmp_path)

    assert skipped_report["scan_failures"] == [
        {"path": "src/demo.py", "error": "decode failed", "error_type": "UnicodeDecodeError"}
    ]

    tree = structural_reports.ast.parse(source_file.read_text(encoding="utf-8"), filename="src/demo.py")
    function_node = next(
        node for node in structural_reports.ast.walk(tree) if isinstance(node, structural_reports.ast.FunctionDef)
    )
    function_node.end_lineno = None
    monkeypatch.setattr(
        structural_reports, "read_structural_text", lambda _path: (source_file.read_text(encoding="utf-8"), 2, None)
    )
    monkeypatch.setattr(structural_reports.ast, "parse", lambda *args, **kwargs: tree)

    report = structural_reports.collect_structural_budget_report(tmp_path)

    assert report["functions_over_budget"] == []


def test_structural_ratchet_main_reports_text_regressions(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        structural_reports,
        "collect_structural_budget_report",
        lambda *_args, **_kwargs: {
            "ratchet": {
                "status": "fail",
                "path": "artifacts/analysis/structural_budget_ratchet.json",
                "expected_metrics": {},
                "current_metrics": {},
                "regressions": [
                    {"metric": "function_over_budget_count", "expected_max": 3, "actual": 5},
                    {"path": "src/demo.py", "expected_max": 500, "actual": 520, "reason": "legacy exception regressed"},
                ],
            }
        },
    )

    exit_code = structural_reports.main(["--repo-root", str(tmp_path)])

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Regressions:" in output
    assert "function_over_budget_count: 5 > 3" in output
    assert "src/demo.py: 520 > 500 (legacy exception regressed)" in output


def test_structural_reports_module_main_invokes_cli(monkeypatch, tmp_path):
    import runpy  # noqa: PLC0415

    monkeypatch.setattr(sys, "argv", ["structural_reports", "--repo-root", str(tmp_path), "--json"])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("sattlint.devtools.structural_reports", run_name="__main__")

    assert exit_info.value.code in {0, 1}


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


def test_collect_architecture_report_flags_missing_acceptance_test_paths(monkeypatch, tmp_path):
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
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    existing_test = tests_dir / "test_existing.py"
    existing_test.write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")

    fake_spec = SimpleNamespace(key="path-gap-analyzer", enabled=True, supports_live_diagnostics=False)
    fake_delivery = SimpleNamespace(
        cli_exposed=True,
        lsp_exposed=False,
        exposed_via=[],
        acceptance_tests=("tests/test_existing.py", "tests/test_missing.py"),
        output_artifacts=[],
    )
    fake_analyzer = SimpleNamespace(
        spec=fake_spec,
        delivery=fake_delivery,
        summary_output="path-gap-analyzer.summary",
    )
    fake_rule = SimpleNamespace(
        id="rule-path-gap",
        acceptance_tests=("tests/test_missing.py",),
        corpus_cases=("workspace-common-quality-issues",),
        mutation_applicability="required",
        suppression_modes=("baseline",),
        incremental_safe=True,
        outputs=[],
    )

    monkeypatch.setattr(structural_reports, "collect_structural_budget_report", lambda *a, **k: empty_budget)
    monkeypatch.setattr(
        structural_reports,
        "get_default_analyzer_catalog",
        lambda: SimpleNamespace(analyzers=[fake_analyzer], rules=[fake_rule]),
    )
    monkeypatch.setattr(structural_reports, "get_declared_cli_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_actual_cli_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_declared_lsp_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "get_actual_lsp_analyzer_keys", lambda: [])
    monkeypatch.setattr(structural_reports, "VARIABLE_ANALYSES", {})

    report = structural_reports.collect_architecture_report(tmp_path)
    findings_by_id = {finding["id"]: finding for finding in report["findings"]}

    assert findings_by_id["analyzer-acceptance-test-path-gap"]["missing_analyzers"] == ["path-gap-analyzer"]
    assert findings_by_id["analyzer-acceptance-test-path-gap"]["missing_acceptance_test_paths"] == [
        {
            "analyzer": "path-gap-analyzer",
            "missing_paths": ["tests/test_missing.py"],
        }
    ]
    assert findings_by_id["rule-acceptance-test-path-gap"]["missing_rule_ids"] == ["rule-path-gap"]
    assert findings_by_id["rule-acceptance-test-path-gap"]["missing_acceptance_test_paths"] == [
        {
            "rule_id": "rule-path-gap",
            "missing_paths": ["tests/test_missing.py"],
        }
    ]
    assert report["phase2_rule_metadata_gate"]["status"] == "fail"
    assert report["phase2_rule_metadata_gate"]["blocking_rule_ids"] == ["rule-path-gap"]
