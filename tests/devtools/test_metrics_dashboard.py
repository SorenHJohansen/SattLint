import json
from types import SimpleNamespace

from sattlint.analyzers.framework import Issue
from sattlint.devtools.structural import metrics_dashboard
from sattlint.devtools.structural.structural_reports import WorkspaceGraphInputs


def test_build_metrics_dashboard_aggregates_structure_and_analyzers(tmp_path, monkeypatch):
    entry_a = tmp_path / "Program" / "A.s"
    entry_b = tmp_path / "Program" / "B.s"
    snapshot_a = SimpleNamespace(
        entry_file=entry_a,
        base_picture=SimpleNamespace(header=SimpleNamespace(name="A")),
        definitions=[object()],
    )
    snapshot_b = SimpleNamespace(
        entry_file=entry_b,
        base_picture=SimpleNamespace(header=SimpleNamespace(name="B")),
        definitions=[object(), object()],
    )
    graph_inputs = WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=[entry_a, entry_b], dependency_files=[tmp_path / "deps" / "Lib.l"]),
        snapshots=[snapshot_b, snapshot_a],
        snapshot_failures=[{"entry_file": "Program/Broken.s", "error": "boom", "error_type": "ValueError"}],
    )

    monkeypatch.setattr(
        metrics_dashboard,
        "collect_ast_summary",
        lambda bp: {
            "datatype_definition_count": 1 if bp.header.name == "A" else 2,
            "moduletype_definition_count": 0,
            "root_localvariable_count": 1,
            "submodule_count": 2 if bp.header.name == "A" else 3,
            "single_module_count": 1,
            "frame_module_count": 0,
            "moduletype_instance_count": 0,
            "moduleparameter_count": 1,
            "module_localvariable_count": 2,
            "sequence_count": 3 if bp.header.name == "A" else 1,
            "equation_count": 1 if bp.header.name == "A" else 4,
        },
    )
    monkeypatch.setattr(
        metrics_dashboard,
        "analyze_cyclomatic_complexity",
        lambda bp: SimpleNamespace(
            issues=(
                [
                    Issue(
                        kind="module.cyclomatic_complexity",
                        message="module issue",
                        module_path=[bp.header.name],
                        data={"scope": "module", "complexity": 14, "threshold": 10},
                    )
                ]
                if bp.header.name == "A"
                else [
                    Issue(
                        kind="step.cyclomatic_complexity",
                        message="step issue",
                        module_path=[bp.header.name, "Seq"],
                        data={
                            "scope": "step",
                            "sequence": "Seq",
                            "step": "Step1",
                            "complexity": 9,
                            "threshold": 6,
                        },
                    )
                ]
            )
        ),
    )
    monkeypatch.setattr(
        metrics_dashboard,
        "analyze_version_drift",
        lambda bp: SimpleNamespace(
            issues=(
                [
                    Issue(
                        kind="module.version_drift",
                        message="drift issue",
                        data={
                            "module_name": "Mixer",
                            "total_found": 3,
                            "unique_variants": 2,
                            "location_preview": ["Root -> Mixer"],
                            "upgrade_notes": ["note"],
                        },
                    )
                ]
                if bp.header.name == "B"
                else []
            )
        ),
    )

    report = metrics_dashboard.build_metrics_dashboard(tmp_path, graph_inputs=graph_inputs)

    assert report["status"] == "partial"
    assert report["summary"] == {
        "program_file_count": 2,
        "snapshot_count": 2,
        "snapshot_failure_count": 1,
        "complexity_issue_count": 2,
        "version_drift_issue_count": 1,
    }
    assert report["metrics"]["workspace"] == {
        "program_file_count": 2,
        "dependency_file_count": 1,
        "snapshot_count": 2,
        "snapshot_failure_count": 1,
    }
    assert report["metrics"]["structure"] == {
        "datatype_definition_count": 3,
        "moduletype_definition_count": 0,
        "root_localvariable_count": 2,
        "submodule_count": 5,
        "single_module_count": 2,
        "frame_module_count": 0,
        "moduletype_instance_count": 0,
        "moduleparameter_count": 2,
        "module_localvariable_count": 4,
        "sequence_count": 4,
        "equation_count": 5,
    }
    assert report["metrics"]["complexity"] == {
        "issue_count": 2,
        "module_issue_count": 1,
        "step_issue_count": 1,
        "max_complexity": 14,
        "top_findings": [
            {
                "entry_file": "Program/A.s",
                "kind": "module.cyclomatic_complexity",
                "module_path": ["A"],
                "scope": "module",
                "sequence": None,
                "step": None,
                "complexity": 14,
                "threshold": 10,
                "message": "module issue",
            },
            {
                "entry_file": "Program/B.s",
                "kind": "step.cyclomatic_complexity",
                "module_path": ["B", "Seq"],
                "scope": "step",
                "sequence": "Seq",
                "step": "Step1",
                "complexity": 9,
                "threshold": 6,
                "message": "step issue",
            },
        ],
    }
    assert report["metrics"]["version_drift"] == {
        "issue_count": 1,
        "affected_module_count": 1,
        "max_unique_variants": 2,
        "modules": [
            {
                "entry_file": "Program/B.s",
                "module_name": "Mixer",
                "total_found": 3,
                "unique_variants": 2,
                "location_preview": ["Root -> Mixer"],
                "upgrade_notes": ["note"],
                "message": "drift issue",
            }
        ],
    }
    assert [entry["entry_file"] for entry in report["entries"]] == ["Program/A.s", "Program/B.s"]
    assert report["snapshot_failures"] == graph_inputs.snapshot_failures


def test_main_writes_report_json(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.structural.metrics_dashboard",
        "report_kind": "metrics-dashboard",
        "status": "ok",
        "workspace_root": ".",
        "summary": {
            "program_file_count": 1,
            "snapshot_count": 1,
            "snapshot_failure_count": 0,
            "complexity_issue_count": 0,
            "version_drift_issue_count": 0,
        },
        "metrics": {
            "workspace": {
                "program_file_count": 1,
                "dependency_file_count": 0,
                "snapshot_count": 1,
                "snapshot_failure_count": 0,
            },
            "structure": {
                "datatype_definition_count": 0,
                "moduletype_definition_count": 0,
                "root_localvariable_count": 0,
                "submodule_count": 0,
                "single_module_count": 0,
                "frame_module_count": 0,
                "moduletype_instance_count": 0,
                "moduleparameter_count": 0,
                "module_localvariable_count": 0,
                "sequence_count": 0,
                "equation_count": 0,
            },
            "complexity": {
                "issue_count": 0,
                "module_issue_count": 0,
                "step_issue_count": 0,
                "max_complexity": 0,
                "top_findings": [],
            },
            "version_drift": {
                "issue_count": 0,
                "affected_module_count": 0,
                "max_unique_variants": 0,
                "modules": [],
            },
        },
        "entries": [],
        "snapshot_failures": [],
    }
    monkeypatch.setattr(metrics_dashboard, "build_metrics_dashboard", lambda *args, **kwargs: expected_report)

    output_dir = tmp_path / "artifacts"
    exit_code = metrics_dashboard.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == expected_report
    assert (
        json.loads((output_dir / metrics_dashboard.DEFAULT_OUTPUT_FILENAME).read_text(encoding="utf-8"))
        == expected_report
    )


def test_main_returns_failure_when_output_report_write_fails(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.structural.metrics_dashboard",
        "report_kind": "metrics-dashboard",
        "status": "ok",
        "workspace_root": ".",
        "summary": {
            "program_file_count": 1,
            "snapshot_count": 1,
            "snapshot_failure_count": 0,
            "complexity_issue_count": 0,
            "version_drift_issue_count": 0,
        },
        "metrics": {
            "workspace": {
                "program_file_count": 1,
                "dependency_file_count": 0,
                "snapshot_count": 1,
                "snapshot_failure_count": 0,
            },
            "structure": {
                "datatype_definition_count": 0,
                "moduletype_definition_count": 0,
                "root_localvariable_count": 0,
                "submodule_count": 0,
                "single_module_count": 0,
                "frame_module_count": 0,
                "moduletype_instance_count": 0,
                "moduleparameter_count": 0,
                "module_localvariable_count": 0,
                "sequence_count": 0,
                "equation_count": 0,
            },
            "complexity": {
                "issue_count": 0,
                "module_issue_count": 0,
                "step_issue_count": 0,
                "max_complexity": 0,
                "top_findings": [],
            },
            "version_drift": {
                "issue_count": 0,
                "affected_module_count": 0,
                "max_unique_variants": 0,
                "modules": [],
            },
        },
        "entries": [],
        "snapshot_failures": [],
    }
    monkeypatch.setattr(metrics_dashboard, "build_metrics_dashboard", lambda *args, **kwargs: expected_report)
    monkeypatch.setattr(
        metrics_dashboard,
        "_write_metrics_report",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("locked")),
    )

    exit_code = metrics_dashboard.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--no-progress",
            "--output-dir",
            str(tmp_path / "artifacts"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == expected_report
    assert "metrics dashboard output error: locked" in captured.err


def test_main_reports_progress_on_stderr(tmp_path, monkeypatch, capsys):
    expected_report = {
        "generated_by": "sattlint.devtools.structural.metrics_dashboard",
        "report_kind": "metrics-dashboard",
        "status": "ok",
        "workspace_root": ".",
        "summary": {
            "program_file_count": 1,
            "snapshot_count": 1,
            "snapshot_failure_count": 0,
            "complexity_issue_count": 0,
            "version_drift_issue_count": 0,
        },
        "metrics": {
            "workspace": {
                "program_file_count": 1,
                "dependency_file_count": 0,
                "snapshot_count": 1,
                "snapshot_failure_count": 0,
            },
            "structure": {
                "datatype_definition_count": 0,
                "moduletype_definition_count": 0,
                "root_localvariable_count": 0,
                "submodule_count": 0,
                "single_module_count": 0,
                "frame_module_count": 0,
                "moduletype_instance_count": 0,
                "moduleparameter_count": 0,
                "module_localvariable_count": 0,
                "sequence_count": 0,
                "equation_count": 0,
            },
            "complexity": {
                "issue_count": 0,
                "module_issue_count": 0,
                "step_issue_count": 0,
                "max_complexity": 0,
                "top_findings": [],
            },
            "version_drift": {
                "issue_count": 0,
                "affected_module_count": 0,
                "max_unique_variants": 0,
                "modules": [],
            },
        },
        "entries": [],
        "snapshot_failures": [],
    }

    def _build_metrics_dashboard(*_args, **kwargs):
        progress_callback = kwargs.get("progress_callback")
        assert progress_callback is not None
        progress_callback("Metrics dashboard: loading workspace graph inputs")
        return expected_report

    monkeypatch.setattr(metrics_dashboard, "build_metrics_dashboard", _build_metrics_dashboard)

    output_dir = tmp_path / "artifacts"
    exit_code = metrics_dashboard.main(
        [
            "--workspace-root",
            str(tmp_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Metrics dashboard: loading workspace graph inputs" in captured.err
    assert json.loads(captured.out) == expected_report
    assert (
        json.loads((output_dir / metrics_dashboard.DEFAULT_OUTPUT_FILENAME).read_text(encoding="utf-8"))
        == expected_report
    )
