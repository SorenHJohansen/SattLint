from __future__ import annotations

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
