from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint.devtools import pipeline


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
