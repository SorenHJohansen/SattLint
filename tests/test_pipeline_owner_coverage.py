# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from __future__ import annotations

import json
import os
import types
from pathlib import Path, PosixPath
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint.devtools import coverage_reports, pipeline
from sattlint.devtools.pipeline import _pipeline_optional_reports_helpers as pipeline_optional_report_helpers
from sattlint.devtools.pipeline import _pipeline_parsing_helpers as pipeline_parsing_helpers


def test_resolve_python_executable_preserves_venv_entrypoint(monkeypatch, tmp_path):
    is_win = os.name == "nt"
    venv_bin = tmp_path / ".venv" / ("Scripts" if is_win else "bin")
    venv_bin.mkdir(parents=True)
    target = tmp_path / "python3.14"
    target.write_text("", encoding="utf-8")
    venv_python = venv_bin / ("python.exe" if is_win else "python")
    try:
        venv_python.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this environment.")

    monkeypatch.setattr(pipeline.pipeline_execution_helpers, "REPO_ROOT", tmp_path)

    assert pipeline.pipeline_execution_helpers._resolve_python_executable() == str(venv_python)


def test_pipeline_execution_helpers_cover_python_resolution_fallbacks(monkeypatch, tmp_path):
    helper = pipeline.pipeline_execution_helpers
    monkeypatch.setattr(helper, "REPO_ROOT", tmp_path)

    override_python = tmp_path / "override-python"
    override_python.write_text("", encoding="utf-8")
    missing_executable = tmp_path / "missing-python"
    missing_base = tmp_path / "missing-base-python"
    prefix_dir = tmp_path / "prefix"
    (prefix_dir / "bin").mkdir(parents=True)

    monkeypatch.setenv("SATTLINT_PYTHON", str(override_python))
    monkeypatch.setattr(helper.sys, "executable", str(missing_executable))
    monkeypatch.setattr(helper.sys, "_base_executable", str(missing_base), raising=False)
    monkeypatch.setattr(helper.sys, "prefix", str(prefix_dir))
    monkeypatch.setattr(helper.shutil, "which", lambda _name: None)

    assert helper._resolve_python_executable() == str(override_python.resolve())

    monkeypatch.delenv("SATTLINT_PYTHON")
    monkeypatch.setattr(helper.shutil, "which", lambda name: "/usr/bin/python3" if name == "python" else None)

    assert helper._resolve_python_executable() == "/usr/bin/python3"

    windows_prefix = tmp_path / "windows-prefix" / "Scripts"
    windows_prefix.mkdir(parents=True)
    windows_python = windows_prefix / "python.exe"
    windows_python.write_text("", encoding="utf-8")
    monkeypatch.setattr(helper.sys, "prefix", str(windows_prefix.parent))
    if os.name != "nt":
        monkeypatch.setattr(helper, "Path", PosixPath)
    monkeypatch.setattr(helper.os, "name", "nt")

    assert helper._resolve_python_executable() == str(windows_python.resolve())

    monkeypatch.setattr(helper.shutil, "which", lambda _name: None)
    if os.name != "nt":
        monkeypatch.setattr(helper.os, "name", "posix")
    monkeypatch.setattr(helper.sys, "prefix", str(tmp_path / "no-such-prefix"))

    assert helper._resolve_python_executable() == str(missing_executable)


def test_pipeline_execution_helpers_cover_venv_tool_run_command_and_changed_file_detection(monkeypatch, tmp_path):
    helper = pipeline.pipeline_execution_helpers
    monkeypatch.chdir(tmp_path)

    windows_tool = tmp_path / ".venv" / "Scripts" / "ruff.exe"
    windows_tool.parent.mkdir(parents=True)
    windows_tool.write_text("", encoding="utf-8")
    if os.name != "nt":
        monkeypatch.setattr(helper, "Path", PosixPath)
    monkeypatch.setattr(helper.os, "name", "nt")
    assert helper._resolve_venv_tool("ruff") == str(windows_tool.resolve())

    monkeypatch.setattr(helper.os, "name", "posix")
    monkeypatch.setattr(helper.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert helper._resolve_venv_tool("pyright") == "/usr/bin/pyright"

    command_calls: list[tuple[list[str], Path, bool | None]] = []
    perf_counter_values = iter((10.0, 10.4321))
    monkeypatch.setattr(helper.time, "perf_counter", lambda: next(perf_counter_values))
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda command, cwd, capture_output, text, encoding, check=False: (
            command_calls.append((command, cwd, check)),
            SimpleNamespace(returncode=3, stdout="stdout", stderr="stderr"),
        )[1],
    )

    result = helper._run_command("demo", ["python", "-V"], cwd=tmp_path)

    assert result == helper.CommandResult(
        name="demo",
        command=["python", "-V"],
        exit_code=3,
        duration_seconds=0.432,
        stdout="stdout",
        stderr="stderr",
    )
    assert command_calls == [(["python", "-V"], tmp_path, False)]

    monkeypatch.setattr(helper.shutil, "which", lambda _name: None)
    assert helper._detect_changed_files(repo_root=tmp_path) == []

    monkeypatch.setattr(helper.shutil, "which", lambda _name: "git")
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    assert helper._detect_changed_files(repo_root=tmp_path) == []

    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    assert helper._detect_changed_files(repo_root=tmp_path) == []

    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="\n".join(
                [
                    " M src/file.py",
                    "R  old.py -> renamed/new.py",
                    'R  "old path.s" -> "renamed/new path.s"',
                    "?? nested\\path.py",
                    '?? "path with spaces/file.s"',
                    '?? "s\\303\\270ren/file.s"',
                    "X",
                    "??   ",
                ]
            ),
            stderr="",
        ),
    )

    assert helper._detect_changed_files(repo_root=tmp_path) == [
        "nested/path.py",
        "path with spaces/file.s",
        "renamed/new path.s",
        "renamed/new.py",
        "src/file.py",
        "s\u00f8ren/file.s",
    ]


def test_pipeline_parsing_helpers_cover_pyproject_decode_fallbacks_and_missing_package(tmp_path, monkeypatch):
    cp1252_file = tmp_path / "pyproject-cp1252.toml"
    cp1252_file.write_bytes('[project]\nname = "caf\xe9"\n'.encode("cp1252"))

    utf8_sig_file = tmp_path / "pyproject-utf8-sig.toml"
    utf8_sig_file.write_bytes('\ufeff[project]\nname = "demo"\n'.encode("utf-8"))

    assert pipeline_parsing_helpers.read_pyproject(cp1252_file)["project"]["name"] == "café"
    assert pipeline_parsing_helpers.read_pyproject(utf8_sig_file)["project"]["name"] == "demo"

    monkeypatch.setattr(
        pipeline_parsing_helpers.metadata,
        "version",
        lambda _package: (_ for _ in ()).throw(pipeline_parsing_helpers.metadata.PackageNotFoundError()),
    )
    assert pipeline_parsing_helpers.tool_version("missing-package") is None


def test_pipeline_parsing_helpers_read_pyproject_uses_final_utf8_replace_fallback(tmp_path, monkeypatch):
    pyproject_file = tmp_path / "pyproject-invalid.toml"
    pyproject_file.write_bytes(b"not-used")
    attempts = {"count": 0}

    def fake_loads(raw_text: str) -> dict[str, Any]:
        attempts["count"] += 1
        if attempts["count"] < 5:
            raise pipeline_parsing_helpers.tomllib.TOMLDecodeError("bad", raw_text, 0)
        return {"project": {"name": "fallback"}}

    monkeypatch.setattr(pipeline_parsing_helpers.tomllib, "loads", fake_loads)

    assert pipeline_parsing_helpers.read_pyproject(pyproject_file)["project"]["name"] == "fallback"
    assert attempts["count"] == 5


def test_pipeline_optional_report_helpers_cover_optional_collection_paths(tmp_path):
    events: list[tuple[str, str, str | None]] = []

    progress = SimpleNamespace(
        log=lambda _message: None,
        start_stage=lambda key, detail=None: events.append(("start", key, detail)),
        complete_stage=lambda key, detail=None: events.append(("complete", key, detail)),
        skip_stage=lambda key, detail=None: events.append(("skip", key, detail)),
    )
    context = {
        "progress": progress,
        "run_structural_reports": True,
        "run_trace": True,
        "run_corpus": True,
        "output_dir": tmp_path,
        "resolved_corpus_manifest_dir": tmp_path / "manifests",
    }
    bundle = SimpleNamespace(
        structural_budget_report={"summary": {"source_file_max_lines": 1, "test_file_max_lines": 2}},
        architecture_report={"findings": []},
        analyzer_registry_report={"rules": []},
        graph_inputs="graph-inputs",
        dependency_graph_report={"edges": [{"source": "main", "target": "support"}]},
        call_graph_report={"edges": [{"source": "Main", "target": "Worker"}]},
        graphics_layout_report={"entries": [], "groups": [], "findings": []},
        impact_analysis_report={"library_impacts": [{"id": "support"}], "module_impacts": [{"id": "Main"}]},
    )

    report = pipeline_optional_report_helpers.collect_optional_reports(
        context,
        trace_target=tmp_path / "trace.s",
        repo_root=tmp_path,
        collect_structural_report_bundle=lambda progress_callback=None: bundle,
        collect_trace_report=lambda trace_target: {"trace_target": trace_target.name},
        run_corpus_suite_fn=lambda *args, **kwargs: SimpleNamespace(
            to_dict=lambda: {"summary": {"case_count": 2, "failed_count": 1}}
        ),
    )

    assert report["workspace_graph_inputs"] == "graph-inputs"
    assert report["trace_report"] == {"trace_target": "trace.s"}
    assert report["corpus_results_report"]["summary"]["case_count"] == 2
    assert ("complete", "structural_reports", "1 dependency edges, 1 call edges") in events
    assert ("complete", "trace", "trace.s") in events
    assert ("complete", "corpus", "2 cases, 1 failed") in events


def test_pipeline_optional_report_helpers_require_trace_target_and_corpus_report(tmp_path):
    progress = SimpleNamespace(
        log=lambda _message: None,
        start_stage=lambda *_args, **_kwargs: None,
        complete_stage=lambda *_args, **_kwargs: None,
        skip_stage=lambda *_args, **_kwargs: None,
    )

    with pytest.raises(ValueError, match="trace_target is required"):
        pipeline_optional_report_helpers.collect_optional_reports(
            {
                "progress": progress,
                "run_structural_reports": False,
                "run_trace": True,
                "run_corpus": False,
                "output_dir": tmp_path,
                "resolved_corpus_manifest_dir": None,
            },
            trace_target=None,
            repo_root=tmp_path,
            collect_structural_report_bundle=lambda progress_callback=None: None,
            collect_trace_report=lambda trace_target: {},
            run_corpus_suite_fn=lambda *args, **kwargs: None,
        )

    with pytest.raises(ValueError, match="run_corpus_suite returned no report"):
        pipeline_optional_report_helpers.collect_optional_reports(
            {
                "progress": progress,
                "run_structural_reports": False,
                "run_trace": False,
                "run_corpus": True,
                "output_dir": tmp_path,
                "resolved_corpus_manifest_dir": tmp_path / "manifests",
            },
            trace_target=None,
            repo_root=tmp_path,
            collect_structural_report_bundle=lambda progress_callback=None: None,
            collect_trace_report=lambda trace_target: {},
            run_corpus_suite_fn=lambda *args, **kwargs: SimpleNamespace(to_dict=lambda: None),
        )


def test_pipeline_optional_report_helpers_build_derived_reports_cover_remaining_branches(tmp_path, monkeypatch):
    progress_events: list[tuple[str, str, str | None]] = []
    progress = SimpleNamespace(
        start_stage=lambda key, detail=None: progress_events.append(("start", key, detail)),
        complete_stage=lambda key, detail=None: progress_events.append(("complete", key, detail)),
    )
    finding_collection = SimpleNamespace(
        findings=[SimpleNamespace(id="finding-a")],
        schema_metadata={"kind": "sattlint.findings", "schema_version": 1},
        to_dict=lambda: {"findings": [{"id": "finding-a"}]},
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_incremental_analysis_report",
        lambda *args, **kwargs: {"changed": ["src/demo.py"]},
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_current_debt_snapshot_report",
        lambda *args, **kwargs: {"kind": "sattlint.current_debt_snapshot"},
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_profiling_summary_report",
        lambda trace_report, slow_phase_threshold_ms: {"trace": trace_report, "threshold": slow_phase_threshold_ms},
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_performance_budget_report",
        lambda profiling_summary_report, total_budget_ms, phase_budget_ms: {
            "total_budget_ms": total_budget_ms,
            "phase_budget_ms": phase_budget_ms,
        },
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_pipeline_finding_collection",
        lambda **kwargs: finding_collection,
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_sattline_semantic_report",
        lambda findings_dict: {"kind": "semantic", "finding_count": len(findings_dict["findings"])},
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_rule_metrics_report",
        lambda findings_dict, analyzer_registry_report: {
            "kind": "rule-metrics",
            "rules": analyzer_registry_report["rules"] if analyzer_registry_report else [],
        },
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "load_finding_collection",
        lambda _path: "baseline-collection",
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_analysis_diff_report",
        lambda **kwargs: {"kind": "analysis-diff", "baseline": kwargs["baseline_label"]},
    )
    monkeypatch.setattr(
        pipeline_optional_report_helpers,
        "build_differential_report",
        lambda *args, **kwargs: SimpleNamespace(to_dict=lambda: {"kind": "differential"}),
    )

    fake_mutation_module = cast(Any, types.ModuleType("sattlint.devtools.mutation_engine"))
    fake_mutation_module.run_mutation_analysis = lambda target, finding_collection: SimpleNamespace(
        to_dict=lambda: {"kind": "mutation-results", "target": target.name}
    )
    monkeypatch.setitem(__import__("sys").modules, "sattlint.devtools.mutation_engine", fake_mutation_module)

    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text("{}", encoding="utf-8")
    mutation_target = tmp_path / "mutation.s"
    mutation_target.write_text("mutation", encoding="utf-8")
    default_trace_target = tmp_path / "default.s"
    default_trace_target.write_text("trace", encoding="utf-8")

    result = pipeline_optional_report_helpers.build_derived_reports(
        {
            "progress": progress,
            "resolved_changed_files": ["src/demo.py"],
            "run_structural_reports": True,
            "run_coverage_summary": True,
            "run_mutation_analysis": True,
            "mutation_target": mutation_target,
        },
        {
            "ruff_findings": [],
            "pyright_findings": [],
            "pytest_report": {"summary": {"tests": 1}},
            "vulture_report": {"skipped": False, "findings": [{"file": "dead.py"}]},
            "bandit_report": {"skipped": True, "findings": [{"issue": "ignored"}]},
        },
        {
            "analyzer_registry_report": {"rules": [{"id": "demo.rule"}]},
            "architecture_report": {"findings": [], "phase2_rule_metadata_gate": {"status": "fail"}},
            "structural_budget_report": {"summary": {"source_file_max_lines": 1, "test_file_max_lines": 2}},
            "trace_report": {"kind": "trace"},
        },
        baseline_findings=baseline_path,
        slow_phase_threshold_ms=5.0,
        phase_budget_ms=20.0,
        total_budget_ms=100.0,
        repo_root=tmp_path,
        default_trace_target=default_trace_target,
        build_coverage_summary_report_fn=lambda _root: {"kind": "coverage-summary"},
    )

    assert result["coverage_summary_report"] == {"kind": "coverage-summary"}
    assert result["current_debt_snapshot_report"] == {"kind": "sattlint.current_debt_snapshot"}
    assert result["phase2_rule_metadata_gate"] == {"status": "fail"}
    assert result["analysis_diff_report"]["kind"] == "analysis-diff"
    assert result["differential_report"] == {"kind": "differential"}
    assert result["mutation_results"] == {"kind": "mutation-results", "target": "mutation.s"}
    assert result["rule_metrics_report"]["kind"] == "rule-metrics"
    assert result["sattline_semantic_report"]["kind"] == "semantic"
    assert ("complete", "findings", "1 normalized findings") in progress_events


def test_derived_reports_helper_coercions_and_incremental_defaults(tmp_path, monkeypatch):
    from sattlint.devtools import derived_reports  # noqa: PLC0415

    generated_by_values: list[str] = []

    class _FakeCatalog:
        def to_report(self, *, generated_by: str) -> dict[str, object]:
            generated_by_values.append(generated_by)
            return {
                "analyzers": [
                    {"key": "variables", "supports_incremental": True},
                    "skip-me",
                    {"key": "dataflow", "supports_incremental": False},
                ]
            }

    def _fake_sanitize(path: Path, *, repo_root: Path) -> str:
        assert repo_root == tmp_path
        if path.name == "demo.py":
            return r"src\sattlint\analyzers\demo.py"
        return ""

    monkeypatch.setattr(derived_reports, "get_default_analyzer_catalog", lambda: _FakeCatalog())
    monkeypatch.setattr(derived_reports, "sanitize_path_for_report", _fake_sanitize)

    assert derived_reports._mapping_list("not-a-list") == []
    assert derived_reports._mapping_list([{"key": "value"}, "skip-me"]) == [{"key": "value"}]
    assert derived_reports._mapping_dict("not-a-mapping") == {}
    assert derived_reports._mapping_dict({1: {"ignored": True}, "bad": "value", "ok": {"value": 1}}) == {
        "ok": {"value": 1}
    }
    assert derived_reports._to_float(True) == 1.0
    assert derived_reports._to_float("bad", default=1.5) == 1.5
    assert derived_reports._to_float(object(), default=2.5) == 2.5
    assert derived_reports._to_int(True) == 1
    assert derived_reports._to_int(4.9) == 4
    assert derived_reports._to_int("bad", default=3) == 3
    assert derived_reports._to_int(object(), default=7) == 7

    relative_program = tmp_path / "programs" / "Main.s"
    relative_program.parent.mkdir(parents=True)
    relative_program.write_text("program", encoding="utf-8")

    result = derived_reports.build_incremental_analysis_report(
        ["programs/Main.s", "src/sattlint/analyzers/demo.py", "programs/Main.s"],
        repo_root=tmp_path,
    )

    assert generated_by_values == ["sattlint.devtools.derived_reports"]
    assert result is not None
    assert result["mode"] == "full"
    assert result["fallback_reasons"] == ["analyzer implementation changed"]
    assert result["changed_files"] == [relative_program.as_posix(), "src/sattlint/analyzers/demo.py"]


def test_build_profiling_summary_report_coerces_invalid_entries():
    from sattlint.devtools.derived_reports import build_profiling_summary_report  # noqa: PLC0415

    trace = {
        "source_file": "Main.s",
        "basepicture_name": "Main",
        "timing_summary": {
            "analysis": {"event_count": 2.9, "span_ms": "12.5"},
            "syntax": {"event_count": "bad", "span_ms": object()},
            1: {"event_count": 99, "span_ms": 30.0},
            "skip": "not-a-mapping",
        },
        "events": [{"time_offset_ms": True}, {"time_offset_ms": "bad"}, "skip-me"],
    }

    result = build_profiling_summary_report(trace, slow_phase_threshold_ms=1.0)

    assert result is not None
    assert result["total_duration_ms"] == 1.0
    assert result["phases"] == [
        {"phase": "analysis", "event_count": 2, "span_ms": 12.5},
        {"phase": "syntax", "event_count": 0, "span_ms": 0.0},
    ]
    assert result["slow_phases"] == [{"phase": "analysis", "event_count": 2, "span_ms": 12.5}]


def test_build_performance_budget_report_handles_pass_and_fail_states():
    from sattlint.devtools.derived_reports import build_performance_budget_report  # noqa: PLC0415

    assert build_performance_budget_report(None, total_budget_ms=10.0, phase_budget_ms=5.0) is None

    failing_result = build_performance_budget_report(
        {
            "total_duration_ms": "12.6",
            "phases": [
                {"phase": "parse", "span_ms": "7.2", "event_count": "3"},
                {"span_ms": True, "event_count": False},
                "skip-me",
            ],
        },
        total_budget_ms=10.0,
        phase_budget_ms=5.0,
    )

    assert failing_result == {
        "kind": "sattlint.performance_budget",
        "schema_version": 1,
        "total_budget_ms": 10.0,
        "phase_budget_ms": 5.0,
        "total_duration_ms": 12.6,
        "total_duration_exceeded": True,
        "over_budget_phases": [{"phase": "parse", "span_ms": 7.2, "event_count": 3}],
        "violation_count": 2,
        "status": "fail",
    }

    passing_result = build_performance_budget_report(
        {
            "total_duration_ms": 4,
            "phases": [{"phase": "syntax", "span_ms": 5.0, "event_count": 1}],
        },
        total_budget_ms=10.0,
        phase_budget_ms=5.0,
    )

    assert passing_result is not None
    assert passing_result["status"] == "pass"
    assert passing_result["violation_count"] == 0
    assert passing_result["over_budget_phases"] == []


def test_coverage_reports_normalize_filename_and_parse_zero_count_hunks():
    assert coverage_reports._normalize_coverage_filename("") == ""
    assert coverage_reports._normalize_coverage_filename("module.py") == "src/module.py"
    assert coverage_reports._normalize_coverage_filename("./package/module.py") == "src/package/module.py"
    windows_path = "C:" + r"\repo\src\module.py"
    assert coverage_reports._normalize_coverage_filename(windows_path) == "C:" + "/repo/src/module.py"
    assert coverage_reports._normalize_coverage_filename("/repo/tests/test_demo.py") == "/repo/tests/test_demo.py"

    diff_text = "\n".join(
        [
            "+++ b/src/demo.py",
            "@@ -1,1 +4,0 @@",
            "@@ -1,1 +9,2 @@",
            "+++ b/src/ignored.py",
            "@@ -1,1 +20,1 @@",
        ]
    )

    assert coverage_reports._parse_git_changed_line_map(diff_text, allowed_paths={"src/demo.py"}) == {
        "src/demo.py": {9, 10}
    }


def test_coverage_reports_discover_changed_line_map_merges_outputs_and_handles_failures(monkeypatch, tmp_path):
    assert coverage_reports._discover_changed_line_map(tmp_path, ["README.md"]) == {}
    monkeypatch.setattr(coverage_reports.shutil, "which", lambda _name: None)
    assert coverage_reports._discover_changed_line_map(tmp_path, ["src/demo.py"]) == {}

    monkeypatch.setattr(coverage_reports.shutil, "which", lambda _name: "git")
    monkeypatch.setattr(
        coverage_reports.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    assert coverage_reports._discover_changed_line_map(tmp_path, ["src/demo.py"]) == {}

    nonzero_results = iter(
        (
            SimpleNamespace(returncode=1, stdout="", stderr="boom"),
            SimpleNamespace(returncode=0, stdout="", stderr=""),
        )
    )
    monkeypatch.setattr(coverage_reports.subprocess, "run", lambda *args, **kwargs: next(nonzero_results))
    assert coverage_reports._discover_changed_line_map(tmp_path, ["src/demo.py"]) == {}

    completed_results = iter(
        (
            SimpleNamespace(returncode=0, stdout="+++ b/src/demo.py\n@@ -1,1 +2,1 @@", stderr=""),
            SimpleNamespace(returncode=0, stdout="+++ b/src/demo.py\n@@ -1,1 +5,2 @@", stderr=""),
        )
    )
    monkeypatch.setattr(coverage_reports.subprocess, "run", lambda *args, **kwargs: next(completed_results))

    assert coverage_reports._discover_changed_line_map(tmp_path, ["src/demo.py"]) == {"src/demo.py": [2, 5, 6]}


def test_coverage_reports_build_summary_skips_unreadable_empty_and_parse_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        coverage_reports,
        "_load_coverage_ratchet",
        lambda _root: {"status": "loaded", "path": "artifacts/analysis/coverage_ratchet.json", "metrics": {}},
    )

    missing_report = coverage_reports.build_coverage_summary_report(tmp_path, coverage_path=tmp_path / "missing.xml")
    assert missing_report["skipped"] is True
    assert missing_report["skip_reason"] == "coverage.xml not found"
    assert missing_report["ratchet"]["error_type"] == "FileNotFoundError"

    unreadable_path = tmp_path / "coverage-unreadable.xml"
    unreadable_path.write_text("placeholder", encoding="utf-8")
    read_text = type(unreadable_path).read_text

    def fake_read_text(self, *args, **kwargs):
        if self == unreadable_path:
            raise OSError("boom")
        return read_text(self, *args, **kwargs)

    monkeypatch.setattr(type(unreadable_path), "read_text", fake_read_text)

    unreadable_report = coverage_reports.build_coverage_summary_report(tmp_path, coverage_path=unreadable_path)
    assert unreadable_report["skipped"] is True
    assert unreadable_report["skip_reason"] == "coverage.xml unreadable"
    assert unreadable_report["ratchet"]["error_type"] == "OSError"

    empty_path = tmp_path / "coverage-empty.xml"
    empty_path.write_text("\n", encoding="utf-8")
    empty_report = coverage_reports.build_coverage_summary_report(tmp_path, coverage_path=empty_path)
    assert empty_report["skipped"] is True
    assert empty_report["skip_reason"] == "coverage.xml was empty"
    assert empty_report["ratchet"]["error_type"] == "ParseError"

    invalid_path = tmp_path / "coverage-invalid.xml"
    invalid_path.write_text("<coverage", encoding="utf-8")
    invalid_report = coverage_reports.build_coverage_summary_report(tmp_path, coverage_path=invalid_path)
    assert invalid_report["skipped"] is True
    assert invalid_report["skip_reason"] == "coverage.xml parse error"
    assert invalid_report["ratchet"]["error_type"] == "ParseError"


def test_coverage_reports_normalize_changed_files_and_parse_special_paths():
    assert coverage_reports._normalize_changed_files(None) == []
    assert coverage_reports._normalize_changed_files(
        [" src/demo.py ", "src/demo.py", r"tests\test_demo.py", "", "   "]
    ) == ["src/demo.py", "tests/test_demo.py"]
    assert coverage_reports._changed_source_files(["src/demo.py", "tests/test_demo.py", "src/demo.txt"]) == [
        "src/demo.py"
    ]

    diff_text = "\n".join(
        [
            "+++ /dev/null",
            "@@ -1,1 +1,1 @@",
            "+++ b/src/demo.py",
            "not a hunk",
            "@@ -1,1 +7 @@",
        ]
    )

    assert coverage_reports._parse_git_changed_line_map(diff_text, allowed_paths={"src/demo.py"}) == {
        "src/demo.py": {7}
    }


def test_coverage_reports_load_ratchet_states_and_evaluate(tmp_path, monkeypatch):
    ratchet_path = tmp_path / coverage_reports.COVERAGE_RATCHET_PATH
    ratchet_path.parent.mkdir(parents=True)
    original_json_loads = json.loads
    monkeypatch.setattr(
        coverage_reports, "sanitize_path_for_report", lambda _path, repo_root: "sanitized/coverage.json"
    )

    missing_state = coverage_reports._load_coverage_ratchet(tmp_path)
    assert missing_state == {"status": "missing", "path": "sanitized/coverage.json", "metrics": {}}

    ratchet_path.write_text("{", encoding="utf-8")
    invalid_json_state = coverage_reports._load_coverage_ratchet(tmp_path)
    assert invalid_json_state["status"] == "invalid"
    assert invalid_json_state["error_type"] == "JSONDecodeError"

    ratchet_path.write_text(json.dumps({"metrics": []}), encoding="utf-8")
    invalid_metrics_state = coverage_reports._load_coverage_ratchet(tmp_path)
    assert invalid_metrics_state["status"] == "invalid"
    assert invalid_metrics_state["error_type"] == "ValueError"

    ratchet_path.write_text(json.dumps({"metrics": {"min_line_rate_basis_points": "9500"}}), encoding="utf-8")
    invalid_value_state = coverage_reports._load_coverage_ratchet(tmp_path)
    assert invalid_value_state["status"] == "invalid"
    assert invalid_value_state["error_type"] == "ValueError"

    ratchet_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(coverage_reports.json, "loads", lambda _text: {"metrics": {1: 2}})
    invalid_key_state = coverage_reports._load_coverage_ratchet(tmp_path)
    assert invalid_key_state["status"] == "invalid"
    assert invalid_key_state["error_type"] == "ValueError"

    monkeypatch.setattr(coverage_reports.json, "loads", original_json_loads)
    ratchet_path.write_text(
        json.dumps(
            {
                "kind": coverage_reports.COVERAGE_RATCHET_SCHEMA_KIND,
                "schema_version": coverage_reports.COVERAGE_RATCHET_SCHEMA_VERSION,
                "metrics": {"min_line_rate_basis_points": 9500},
            }
        ),
        encoding="utf-8",
    )
    loaded_state = coverage_reports._load_coverage_ratchet(tmp_path)
    assert loaded_state["status"] == "loaded"
    assert loaded_state["metrics"] == {"min_line_rate_basis_points": 9500}

    invalid_evaluation = coverage_reports._evaluate_coverage_ratchet(
        {"line_rate_basis_points": 9000}, invalid_json_state
    )
    assert invalid_evaluation["status"] == "invalid"
    assert invalid_evaluation["error_type"] == "JSONDecodeError"

    failed_evaluation = coverage_reports._evaluate_coverage_ratchet({"line_rate_basis_points": 9400}, loaded_state)
    assert failed_evaluation["status"] == "fail"
    assert failed_evaluation["regressions"] == [
        {"metric": "line_rate_basis_points", "expected_min": 9500, "actual": 9400}
    ]

    passed_evaluation = coverage_reports._evaluate_coverage_ratchet({"line_rate_basis_points": 9600}, loaded_state)
    assert passed_evaluation["status"] == "pass"
    assert passed_evaluation["regressions"] == []


def test_coverage_reports_collect_modules_and_summarize_change_scoped_coverage():
    coverage_xml = """
    <coverage>
      <packages>
        <package>
          <classes>
            <class filename="./demo.py" line-rate="0.5" lines-valid="4">
              <lines>
                <line number="0" hits="1" />
                <line number="1" hits="1" />
                <line number="2" hits="0" />
                <line number="3" hits="1" />
                <line number="4" hits="0" />
              </lines>
            </class>
            <class filename="src/helper.py" line-rate="1.0" lines-valid="2" lines-covered="2">
              <lines>
                <line number="1" hits="1" />
                <line number="2" hits="1" />
              </lines>
            </class>
            <class filename="tests/test_demo.py" line-rate="0.0" lines-valid="1" lines-covered="0">
              <lines>
                <line number="1" hits="0" />
              </lines>
            </class>
          </classes>
        </package>
      </packages>
    </coverage>
    """
    root_xml = coverage_reports.ElementTree.fromstring(coverage_xml)

    modules, module_lookup, line_rates = coverage_reports._collect_modules(root_xml)

    assert [module["path"] for module in modules] == ["src/demo.py", "src/helper.py"]
    assert module_lookup["src/demo.py"]["lines_covered"] == 2
    assert module_lookup["src/demo.py"]["line_hits"] == {1: 1, 2: 0, 3: 1, 4: 0}
    assert line_rates == [0.5, 1.0]

    skipped_summary = coverage_reports._summarize_change_scoped_coverage(
        changed_files=None,
        changed_line_map=None,
        module_lookup=module_lookup,
        ratchet_state={"metrics": {}},
    )
    assert skipped_summary["status"] == "skipped"
    assert skipped_summary["mode"] == "skipped"

    changed_line_summary = coverage_reports._summarize_change_scoped_coverage(
        changed_files=["src/demo.py", "src/missing.py", "README.md"],
        changed_line_map={"src/demo.py": [1, 2, 9], r"src\missing.py": [4]},
        module_lookup=module_lookup,
        ratchet_state={
            "metrics": {
                "min_changed_line_rate_basis_points": 7000,
                "min_touched_file_line_rate_basis_points": 7000,
            }
        },
    )
    assert changed_line_summary["status"] == "fail"
    assert changed_line_summary["mode"] == "changed-lines"
    assert changed_line_summary["summary"]["changed_line_count"] == 2
    assert changed_line_summary["summary"]["changed_lines_covered"] == 1
    assert changed_line_summary["summary"]["unmeasured_changed_line_count"] == 1
    assert changed_line_summary["ratchet"]["regressions"] == [
        {"metric": "changed_line_rate_basis_points", "expected_min": 7000, "actual": 5000},
        {
            "metric": "reported_touched_source_files",
            "expected": "all touched source files must appear in focused coverage output",
            "actual": "missing files",
            "paths": ["src/missing.py"],
        },
    ]

    touched_file_summary = coverage_reports._summarize_change_scoped_coverage(
        changed_files=["src/helper.py"],
        changed_line_map=None,
        module_lookup=module_lookup,
        ratchet_state={"metrics": {"min_touched_file_line_rate_basis_points": 9000}},
    )
    assert touched_file_summary["status"] == "pass"
    assert touched_file_summary["mode"] == "touched-files"
    assert touched_file_summary["ratchet"]["actual"] == 10000


def test_coverage_reports_build_summary_report_covers_low_coverage_and_regressions(tmp_path, monkeypatch):
    coverage_path = tmp_path / "coverage-report.xml"
    coverage_path.write_text(
        """
        <coverage line-rate="0" lines-valid="0" lines-covered="0">
          <packages>
            <package>
              <classes>
                <class filename="src/high.py" line-rate="0.05" lines-valid="2">
                  <lines>
                    <line number="1" hits="0" />
                    <line number="2" hits="0" />
                  </lines>
                </class>
                <class filename="src/medium.py" line-rate="0.30" lines-valid="10">
                  <lines>
                    <line number="1" hits="1" />
                    <line number="2" hits="1" />
                    <line number="3" hits="1" />
                    <line number="4" hits="0" />
                    <line number="5" hits="0" />
                    <line number="6" hits="0" />
                    <line number="7" hits="0" />
                    <line number="8" hits="0" />
                    <line number="9" hits="0" />
                    <line number="10" hits="0" />
                  </lines>
                </class>
                <class filename="src/low.py" line-rate="0.50" lines-valid="4">
                  <lines>
                    <line number="1" hits="1" />
                    <line number="2" hits="1" />
                    <line number="3" hits="0" />
                    <line number="4" hits="0" />
                  </lines>
                </class>
                <class filename="src/stable.py" line-rate="1.0" lines-valid="2" lines-covered="2">
                  <lines>
                    <line number="1" hits="1" />
                    <line number="2" hits="1" />
                  </lines>
                </class>
              </classes>
            </package>
          </packages>
        </coverage>
        """,
        encoding="utf-8",
    )
    discover_calls: list[tuple[Path, list[str]]] = []
    monkeypatch.setattr(
        coverage_reports,
        "_load_coverage_ratchet",
        lambda _root: {
            "status": "loaded",
            "path": "artifacts/analysis/coverage_ratchet.json",
            "metrics": {
                "min_line_rate_basis_points": 9000,
                "min_changed_line_rate_basis_points": 10000,
                "min_touched_file_line_rate_basis_points": 9000,
            },
        },
    )
    monkeypatch.setattr(
        coverage_reports,
        "_discover_changed_line_map",
        lambda root, changed_files: (discover_calls.append((root, list(changed_files or []))), {"src/high.py": [1, 2]})[
            1
        ],
    )

    report = coverage_reports.build_coverage_summary_report(
        tmp_path,
        coverage_path=coverage_path,
        changed_files=["src/high.py"],
    )

    assert discover_calls == [(tmp_path, ["src/high.py"])]
    assert report["skipped"] is False
    assert [module["path"] for module in report["modules"]] == [
        "src/high.py",
        "src/low.py",
        "src/medium.py",
        "src/stable.py",
    ]
    assert report["summary"] == {
        "module_count": 4,
        "low_coverage_count": 3,
        "avg_line_rate": 0.4625,
        "total_line_rate": 0.3889,
        "total_lines_valid": 18,
        "total_lines_covered": 7,
        "total_lines_missing": 11,
    }
    assert report["ratchet"]["status"] == "fail"
    assert report["change_scoped"]["status"] == "fail"
    assert report["findings"] == [
        {
            "path": "src/high.py",
            "line_rate": 0.05,
            "severity": "high",
            "message": "Source module has low test coverage.",
            "suggestion": "Add targeted tests for this module or reduce dead code within it.",
        },
        {
            "path": "src/low.py",
            "line_rate": 0.5,
            "severity": "low",
            "message": "Source module has low test coverage.",
            "suggestion": "Add targeted tests for this module or reduce dead code within it.",
        },
        {
            "path": "src/medium.py",
            "line_rate": 0.3,
            "severity": "medium",
            "message": "Source module has low test coverage.",
            "suggestion": "Add targeted tests for this module or reduce dead code within it.",
        },
        {
            "id": "coverage-ratchet-regression",
            "path": "coverage-report.xml",
            "line_rate": 0.3889,
            "severity": "medium",
            "message": "Overall test coverage regressed below the checked-in ratchet baseline.",
            "suggestion": "Restore coverage before merging or refresh artifacts/analysis/coverage_ratchet.json after an intentional improvement.",
            "ratchet_path": "artifacts/analysis/coverage_ratchet.json",
        },
        {
            "id": "change-scoped-coverage-ratchet-regression",
            "path": "src/high.py",
            "severity": "medium",
            "message": "Changed source coverage proof fell below the checked-in diff-scoped ratchet.",
            "suggestion": "Run focused owner tests with coverage and raise changed-line coverage first; fall back to touched-file proof only when no executable changed lines exist.",
            "coverage_mode": "changed-lines",
        },
    ]
