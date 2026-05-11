from __future__ import annotations

import json
import types
from pathlib import Path, PosixPath
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint.devtools import _pipeline_optional_reports_helpers as pipeline_optional_report_helpers
from sattlint.devtools import _pipeline_parsing_helpers as pipeline_parsing_helpers
from sattlint.devtools import pipeline


def test_resolve_python_executable_preserves_venv_entrypoint(monkeypatch, tmp_path):
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    target = tmp_path / "python3.14"
    target.write_text("", encoding="utf-8")
    venv_python = venv_bin / "python"
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
    monkeypatch.setattr(helper.os, "name", "nt")
    monkeypatch.setattr(helper, "Path", PosixPath)
    monkeypatch.setattr(helper.sys, "prefix", str(windows_prefix.parent))

    assert helper._resolve_python_executable() == str(windows_python.resolve())

    monkeypatch.setattr(helper.shutil, "which", lambda _name: None)
    monkeypatch.setattr(helper.os, "name", "posix")

    assert helper._resolve_python_executable() == str(missing_executable)


def test_pipeline_execution_helpers_cover_venv_tool_run_command_and_changed_file_detection(monkeypatch, tmp_path):
    helper = pipeline.pipeline_execution_helpers
    monkeypatch.chdir(tmp_path)

    windows_tool = tmp_path / ".venv" / "Scripts" / "ruff.exe"
    windows_tool.parent.mkdir(parents=True)
    windows_tool.write_text("", encoding="utf-8")
    monkeypatch.setattr(helper.os, "name", "nt")
    monkeypatch.setattr(helper, "Path", PosixPath)
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
                    "?? nested\\path.py",
                    "X",
                    "??   ",
                ]
            ),
            stderr="",
        ),
    )

    assert helper._detect_changed_files(repo_root=tmp_path) == [
        "nested/path.py",
        "renamed/new.py",
        "src/file.py",
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


def test_check_core_invariants_returns_empty_without_finding_collection():
    assert pipeline._check_core_invariants({}, {}) == []


def test_pipeline_helper_wrappers_cover_remaining_collection_branches(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        pipeline, "_read_pyproject", lambda: {"project": {"name": "sattlint", "optional-dependencies": {}}}
    )
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "_tool_version", lambda _name: "1.0")
    monkeypatch.setattr(
        pipeline,
        "_collect_workspace_graph_inputs",
        lambda workspace_root=pipeline.REPO_ROOT: ("discovery", ["snapshot"], [{"error": "none"}]),
    )
    monkeypatch.setattr(
        pipeline,
        "build_graphics_layout_report",
        lambda workspace_root, graph_inputs: {"workspace_root": str(workspace_root), "graph_inputs": graph_inputs},
    )
    monkeypatch.setattr(
        pipeline,
        "build_structural_reports",
        lambda workspace_root, progress_callback=None: {"workspace_root": str(workspace_root), "called": True},
    )
    monkeypatch.setattr(pipeline, "build_trace_report", lambda trace_target: {"trace_target": trace_target.name})
    monkeypatch.setattr(
        pipeline.pipeline_execution_helpers,
        "_run_command",
        lambda name, command, cwd=pipeline.REPO_ROOT: pipeline.CommandResult(
            name=name,
            command=command,
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        ),
    )

    junit_path = tmp_path / "pytest.junit.xml"
    junit_path.write_text(
        """
<testsuites>
  <testsuite tests="4" failures="1" errors="1" skipped="1">
    <testcase classname="pkg.Test" name="failed" time="0.1"><failure message="boom">details</failure></testcase>
    <testcase classname="pkg.Test" name="error" time="0.2"><error message="oops">details</error></testcase>
    <testcase classname="pkg.Test" name="skipped" time="0.3"><skipped message="skip">details</skipped></testcase>
    <testcase classname="pkg.Test" name="passed" time="0.4" />
  </testsuite>
</testsuites>
""".strip(),
        encoding="utf-8",
    )

    assert pipeline._normalize_pytest_workers(" 2 ") == "2"
    with pytest.raises(ValueError, match="Unsupported pipeline profile"):
        pipeline._profile_settings("weird")

    timing = pipeline._build_pipeline_timing_summary(
        progress=cast(
            Any,
            SimpleNamespace(
                to_dict=lambda: {
                    "stages": [
                        {"key": "", "duration_seconds": 9.0},
                        {"key": "ruff", "duration_seconds": "bad"},
                        {"key": "pytest", "duration_seconds": 1.25},
                    ]
                }
            ),
        ),
        tool_statuses={"ruff": {"status": "pass"}, "pytest": {"status": "pass"}},
        pytest_workers=" 2 ",
    )

    assert timing["stage_durations_seconds"]["ruff"] == 0.0
    assert timing["check_durations_seconds"]["pytest"] == 1.25
    assert timing["pytest_workers"] == "2"

    run_result = pipeline._run_command("echo", ["echo", "ok"])
    assert run_result.name == "echo"

    assert pipeline._parse_json_lines('{"a": 1}\n\n{"b": 2}\n') == [{"a": 1}, {"b": 2}]
    assert pipeline._parse_vulture_output(
        "src/file.py:12: unused thing (80% confidence)\nignored",
    ) == [{"file": "src/file.py", "line": 12, "message": "unused thing", "confidence": 80}]
    parsed_junit = pipeline._parse_pytest_junit(junit_path)
    assert parsed_junit["summary"] == {"tests": 4, "failures": 1, "errors": 1, "skipped": 1}
    assert [case["outcome"] for case in parsed_junit["testcases"]] == ["failed", "error", "skipped", "passed"]

    environment = pipeline._collect_environment_report()
    assert environment["project_name"] == "sattlint"
    assert environment["python"]["executable"] == "python"

    graphics_report = pipeline._collect_graphics_layout_report(tmp_path)
    assert graphics_report["graph_inputs"] == ("discovery", ["snapshot"], [{"error": "none"}])
    assert pipeline._collect_structural_report_bundle(tmp_path) == {"workspace_root": str(tmp_path), "called": True}
    assert pipeline._collect_trace_report(tmp_path / "trace.s") == {"trace_target": "trace.s"}

    pipeline._print_cli_summary(
        {
            "profile": "full",
            "overall_status": "pass",
            "tool_statuses": {},
            "status_report": "reports/status.json",
            "summary_report": "reports/summary.json",
            "corpus_results_report": "reports/corpus_results.json",
        }
    )
    output = capsys.readouterr().out
    assert "Corpus results report: reports/corpus_results.json" in output


def test_run_stage_helpers_cover_fallback_and_missing_junit_branches(monkeypatch, tmp_path):
    class ProgressStub:
        def __init__(self) -> None:
            self.events: list[tuple[str, str, str | None]] = []

        def start_stage(self, key: str) -> None:
            self.events.append(("start", key, None))

        def complete_stage(self, key: str, detail: str | None = None) -> None:
            self.events.append(("complete", key, detail))

    progress = ProgressStub()
    typed_progress = cast(Any, progress)
    commands: list[list[str]] = []

    monkeypatch.setattr(pipeline, "_resolve_venv_tool", lambda _name: None)

    def fake_run_command(name, command, cwd=pipeline.REPO_ROOT):
        commands.append(command)
        if name == "ruff":
            return pipeline.CommandResult(
                name=name, command=command, exit_code=0, duration_seconds=0.0, stdout="[]", stderr=""
            )
        if name == "pyright":
            return pipeline.CommandResult(
                name=name,
                command=command,
                exit_code=1,
                duration_seconds=0.0,
                stdout=json.dumps({"generalDiagnostics": [], "summary": {"errorCount": 1, "warningCount": 2}}),
                stderr="",
            )
        return pipeline.CommandResult(
            name=name, command=command, exit_code=1, duration_seconds=0.0, stdout="", stderr="missing junit"
        )

    monkeypatch.setattr(pipeline, "_run_command", fake_run_command)
    monkeypatch.setattr(pipeline, "_parse_pytest_junit", lambda _path: (_ for _ in ()).throw(FileNotFoundError()))

    ruff_report, _ = pipeline._run_ruff_stage(typed_progress, python_cmd=["python"])
    pyright_report, _ = pipeline._run_pyright_stage(typed_progress, python_cmd=["python"])
    pytest_report = pipeline._run_pytest_stage(
        typed_progress, output_dir=tmp_path, python_cmd=["python"], profile="quick"
    )

    assert commands[0][:3] == ["python", "-m", "ruff"]
    assert commands[1][:3] == ["python", "-m", "pyright"]
    assert ruff_report["finding_count"] == 0
    assert pyright_report["warning_count"] == 2
    assert pytest_report["errors"][0]["message"] == "JUnit XML not generated: missing junit"


def test_prepare_pipeline_run_covers_missing_baseline_and_worker_command(monkeypatch, tmp_path):
    missing_baseline = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError, match="Baseline findings file does not exist"):
        pipeline._prepare_pipeline_run(
            tmp_path / "missing-baseline",
            trace_target=None,
            mutation_target=None,
            profile="quick",
            include_vulture=False,
            include_bandit=False,
            baseline_findings=missing_baseline,
            corpus_manifest_dir=None,
            changed_files=None,
            selected_checks=None,
            run_mutation_analysis=False,
            pytest_workers=None,
        )

    trace_target = tmp_path / "trace.s"
    trace_target.write_text("trace", encoding="utf-8")
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    mutation_target = tmp_path / "mutation.s"
    mutation_target.write_text("mutation", encoding="utf-8")
    monkeypatch.setattr(pipeline, "_resolve_python_executable", lambda: "python")
    monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "_detect_changed_files", lambda repo_root=pipeline.REPO_ROOT: ["src/example.py"])

    context = pipeline._prepare_pipeline_run(
        tmp_path / "prepared",
        trace_target=trace_target,
        mutation_target=mutation_target,
        profile="full",
        include_vulture=True,
        include_bandit=True,
        baseline_findings=None,
        corpus_manifest_dir=corpus_dir,
        changed_files=None,
        selected_checks=["ruff", "pyright"],
        run_mutation_analysis=True,
        pytest_workers=" 3 ",
    )

    progress_payload = context["progress"].to_dict()
    assert context["pytest_workers"] == "3"
    assert context["run_mutation_analysis"] is True
    assert "--check ruff --check pyright" in progress_payload["canonical_command"]
    assert progress_payload["canonical_command"].endswith("--pytest-workers 3")


def test_run_pipeline_skips_unselected_tools(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pipeline,
        "_prepare_pipeline_run",
        lambda output_dir, **kwargs: {
            "artifact_registry_report": {},
            "changed_files": [],
            "enabled_artifacts": {"progress", "status", "summary", "findings"},
            "output_dir": output_dir,
            "profile": kwargs["profile"],
            "progress": SimpleNamespace(),
            "pytest_workers": None,
            "python_cmd": ["python"],
            "resolved_changed_files": [],
            "resolved_corpus_manifest_dir": None,
            "mutation_target": None,
            "run_bandit": False,
            "run_corpus": False,
            "run_coverage_summary": False,
            "run_mutation_analysis": False,
            "run_structural_reports": False,
            "run_trace": False,
            "run_vulture": False,
            "sanitized_output_dir": output_dir.as_posix(),
            "selected_checks": ["trace"],
        },
    )
    monkeypatch.setattr(pipeline, "_collect_optional_reports", lambda context, trace_target=None: {})
    monkeypatch.setattr(
        pipeline,
        "_build_derived_reports",
        lambda context, stage_reports, optional_reports, **kwargs: {
            "finding_collection": SimpleNamespace(findings=[]),
            "trace_report": {},
        },
    )
    monkeypatch.setattr(
        pipeline,
        "_finalize_pipeline_outputs",
        lambda context, stage_reports, optional_reports, derived_reports, **kwargs: {
            "stage_reports": stage_reports,
            "status": {"overall_status": "pass"},
        },
    )

    summary = pipeline._run_pipeline(tmp_path, trace_target=None, profile="quick", selected_checks=["trace"])

    assert summary["stage_reports"]["ruff_report"]["skipped"] is True
    assert summary["stage_reports"]["pyright_report"]["skipped"] is True
    assert summary["stage_reports"]["pytest_report"]["skipped"] is True
    assert summary["stage_reports"]["vulture_report"]["skipped"] is True
    assert summary["stage_reports"]["bandit_report"]["skipped"] is True


def test_finalize_pipeline_outputs_records_selected_checks(monkeypatch, tmp_path):
    progress = SimpleNamespace(
        start_stage=lambda _key: None,
        complete_stage=lambda _key: None,
        finalize=lambda overall_status: None,
        to_dict=lambda: {"stages": []},
    )
    monkeypatch.setattr(pipeline, "artifact_reports_map", lambda *args, **kwargs: {"summary": "summary.json"})
    monkeypatch.setattr(pipeline, "_build_core_tool_statuses", lambda *args, **kwargs: {"ruff": {"status": "pass"}})
    monkeypatch.setattr(pipeline, "_build_policy_tool_statuses", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        pipeline,
        "build_pipeline_status_report",
        lambda **kwargs: {"tool_statuses": kwargs["tool_statuses"], "overall_status": kwargs["overall_status_value"]},
    )
    monkeypatch.setattr(
        pipeline,
        "build_pipeline_summary_report",
        lambda **kwargs: {"status": {"overall_status": kwargs["overall_status_value"]}, "reports": kwargs["reports"]},
    )
    monkeypatch.setattr(pipeline, "_build_pipeline_tool_exit_codes", lambda *args, **kwargs: {})
    monkeypatch.setattr(pipeline, "_build_pipeline_counts", lambda *args, **kwargs: {})
    monkeypatch.setattr(pipeline, "write_pipeline_artifacts", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "write_json_artifact", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "_build_pipeline_timing_summary", lambda **kwargs: {"total_duration_seconds": 0.0})

    summary = pipeline._finalize_pipeline_outputs(
        {
            "artifact_registry_report": {},
            "enabled_artifacts": {"progress", "status", "summary", "findings"},
            "output_dir": tmp_path,
            "profile": "quick",
            "progress": progress,
            "sanitized_output_dir": tmp_path.as_posix(),
            "selected_checks": ("ruff", "pyright"),
            "changed_files": [],
        },
        {
            "environment_report": {},
            "ruff_report": {"skipped": True},
            "pyright_report": {"skipped": True},
            "pytest_report": {"skipped": True},
            "vulture_report": {"skipped": True},
            "bandit_report": {"skipped": True},
            "ruff_findings": [],
            "pyright_findings": [],
        },
        {
            "architecture_report": {"skipped": True},
            "analyzer_registry_report": {"skipped": True},
            "dependency_graph_report": {"skipped": True},
            "call_graph_report": {"skipped": True},
            "graphics_layout_report": {"skipped": True},
            "impact_analysis_report": {"skipped": True},
            "trace_report": {"skipped": True},
            "corpus_results_report": None,
        },
        {
            "analysis_diff_report": None,
            "coverage_summary_report": None,
            "current_debt_snapshot_report": None,
            "differential_report": None,
            "finding_collection": SimpleNamespace(to_dict=lambda: {"findings": []}),
            "findings_schema": {"kind": "sattlint.findings", "schema_version": 1},
            "incremental_analysis_report": {},
            "mutation_results": None,
            "performance_budget_report": None,
            "profiling_summary_report": None,
            "rule_metrics_report": None,
            "sattline_semantic_report": None,
        },
        fail_on_drift=False,
        fail_on_budget=False,
    )

    assert summary["selected_checks"] == ["ruff", "pyright"]
