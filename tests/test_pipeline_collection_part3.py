# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportMissingTypeArgument=false
# ruff: noqa: F403, F405
from ._pipeline_collection_test_support import *


def test_build_analysis_diff_report_classifies_changes():
    baseline = FindingCollection(
        (
            FindingRecord(
                id="unchanged",
                rule_id="ruff.f401",
                category="style",
                severity="high",
                confidence="high",
                message="Imported but unused",
                source="ruff",
            ),
            FindingRecord(
                id="changed-old",
                rule_id="pytest.failures",
                category="correctness",
                severity="high",
                confidence="high",
                message="Pytest reported failing tests.",
                source="pytest",
            ),
            FindingRecord(
                id="resolved",
                rule_id="vulture.dead-code",
                category="dead-code",
                severity="medium",
                confidence="medium",
                message="Potential dead code found.",
                source="vulture",
            ),
        )
    )
    current = FindingCollection(
        (
            FindingRecord(
                id="unchanged",
                rule_id="ruff.f401",
                category="style",
                severity="high",
                confidence="high",
                message="Imported but unused",
                source="ruff",
            ),
            FindingRecord(
                id="changed-new",
                rule_id="pytest.failures",
                category="correctness",
                severity="high",
                confidence="high",
                message="Pytest reported failing or erroring tests.",
                source="pytest",
            ),
            FindingRecord(
                id="new",
                rule_id="bandit.b101",
                category="security",
                severity="low",
                confidence="high",
                message="Use of assert detected.",
                source="bandit",
            ),
        )
    )

    report = build_analysis_diff_report(
        baseline=baseline,
        current=current,
        baseline_label="baseline.json",
        current_label="current.json",
    )

    assert_analysis_diff_report(
        report,
        summary={
            "new_count": 1,
            "resolved_count": 1,
            "changed_count": 1,
            "unchanged_count": 1,
        },
        baseline_label="baseline.json",
        current_label="current.json",
        new_rule_ids=("bandit.b101",),
        resolved_rule_ids=("vulture.dead-code",),
        unchanged_rule_ids=("ruff.f401",),
        changed_rule_ids=("pytest.failures",),
        changed_fields_by_rule_id={
            "pytest.failures": ("id", "message"),
        },
    )
    assert report["findings"]["changed"][0]["baseline"]["message"] == "Pytest reported failing tests."
    assert report["findings"]["changed"][0]["current"]["message"] == "Pytest reported failing or erroring tests."


def test_print_cli_summary_includes_analysis_diff_counts(capsys):
    pipeline._print_cli_summary(
        {
            "profile": "quick",
            "overall_status": "pass",
            "tool_statuses": {},
            "findings_schema": {
                "kind": "sattlint.findings",
                "schema_version": 1,
            },
            "analysis_diff_report": "<external>/analysis/analysis_diff.json",
            "analysis_diff_summary": {
                "new_count": 1,
                "changed_count": 2,
                "resolved_count": 3,
                "unchanged_count": 4,
            },
            "status_report": "<external>/analysis/status.json",
            "summary_report": "<external>/analysis/summary.json",
        }
    )

    output = capsys.readouterr().out

    assert "Findings schema: sattlint.findings v1" in output
    assert "Analysis diff: 1 new, 2 changed, 3 resolved, 4 unchanged" in output
    assert "Analysis diff report: <external>/analysis/analysis_diff.json" in output


def test_write_pipeline_artifacts_uses_registry_filenames(tmp_path):
    written: list[tuple[str, dict]] = []

    context = PipelineArtifactContext(
        payloads={
            "status": {"kind": "status"},
            "summary": {"kind": "summary"},
        }
    )

    def fake_write_json(path, payload):
        written.append((path.name, payload))

    artifact_ids = write_pipeline_artifacts(
        tmp_path,
        artifacts=pipeline.PIPELINE_ARTIFACTS,
        profile="quick",
        enabled_artifact_ids={"status", "summary"},
        context=context,
        write_json=fake_write_json,
    )

    assert artifact_ids == ("status", "summary")
    assert written == [
        ("status.json", {"kind": "status"}),
        ("summary.json", {"kind": "summary"}),
    ]


def test_write_pipeline_artifacts_uses_registry_producer_mapping(tmp_path):
    written: list[tuple[str, dict]] = []
    context = PipelineArtifactContext(payloads={})

    def fake_write_json(path, payload):
        written.append((path.name, payload))

    artifact_ids = write_pipeline_artifacts(
        tmp_path,
        artifacts=(
            ArtifactDefinition(
                "status",
                "status.json",
                "status_payload",
                "sattlint.pipeline.status",
                1,
                profiles=("quick",),
            ),
        ),
        profile="quick",
        enabled_artifact_ids={"status"},
        context=context,
        write_json=fake_write_json,
        producers=(
            PipelineArtifactProducer(
                "status_payload",
                lambda artifact_context: {"kind": "status"},
            ),
        ),
    )

    assert artifact_ids == ("status",)
    assert written == [("status.json", {"kind": "status"})]


def test_write_json_artifact_retries_permission_error(tmp_path, monkeypatch):
    target = tmp_path / "status.json"
    replace_calls = {"count": 0}
    real_replace = os.replace

    def flaky_replace(source, destination):
        replace_calls["count"] += 1
        if replace_calls["count"] == 1:
            raise PermissionError("temporary file lock")
        real_replace(source, destination)

    monkeypatch.setattr("sattlint.devtools.pipeline_artifacts.os.replace", flaky_replace)
    monkeypatch.setattr("sattlint.devtools.pipeline_artifacts.time.sleep", lambda _seconds: None)

    write_json_artifact(target, {"kind": "status"})

    assert replace_calls["count"] == 2
    assert json.loads(target.read_text(encoding="utf-8")) == {"kind": "status"}


def test_write_json_artifact_writes_source_digest_manifest(tmp_path):
    target = tmp_path / "status.json"
    source_file = tmp_path / "source.py"
    source_file.write_text("print('fresh')\n", encoding="utf-8")

    write_json_artifact(
        target,
        {
            "kind": "status",
            "schema_version": 1,
            "generated_by": "sattlint.devtools.pipeline_artifacts",
        },
        repo_root=tmp_path,
        source_paths=(source_file,),
    )

    manifest = json.loads(artifact_source_manifest_path(target).read_text(encoding="utf-8"))

    assert manifest["kind"] == SOURCE_DIGEST_MANIFEST_KIND
    assert manifest["artifact_file"] == "status.json"
    assert manifest["generated_by"] == "sattlint.devtools.pipeline_artifacts"
    assert manifest["source_count"] == 2
    assert {entry["path"] for entry in manifest["sources"]} == {
        "source.py",
        "src/sattlint/devtools/pipeline_artifacts.py",
    }


def test_write_pipeline_artifacts_requires_producer_for_enabled_artifact(tmp_path):
    context = PipelineArtifactContext(payloads={})

    try:
        write_pipeline_artifacts(
            tmp_path,
            artifacts=pipeline.PIPELINE_ARTIFACTS,
            profile="quick",
            enabled_artifact_ids={"status"},
            context=context,
            write_json=lambda path, payload: None,
            producers=(PipelineArtifactProducer("summary", lambda artifact_context: {"kind": "summary"}),),
        )
    except ValueError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("Expected missing artifact producer to raise ValueError")


def test_validate_pipeline_artifact_producers_covers_quick_and_full_profiles():
    quick_artifacts = validate_pipeline_artifact_producers(
        pipeline.PIPELINE_ARTIFACTS,
        profile="quick",
    )
    full_artifacts = validate_pipeline_artifact_producers(
        pipeline.PIPELINE_ARTIFACTS,
        profile="full",
    )

    assert "status" in quick_artifacts
    assert "summary" in quick_artifacts
    assert "trace" in full_artifacts
    assert "graphics_layout" in full_artifacts
    assert "impact_analysis" in full_artifacts


def test_collect_graphics_layout_report_resolves_moduletype_moduledefs(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    panel_type = ModuleTypeDef(
        name="PanelType",
        moduledef=ModuleDef(
            clipping_bounds=((0.0, 0.0), (1.0, 0.5)),
            zoom_limits=(0.9, 0.1),
            grid=0.01,
            zoomable=True,
        ),
        submodules=[
            SingleModule(
                header=ModuleHeader(
                    name="UnitControl",
                    invoke_coord=(1.43, 1.35, 0.0, 0.56, 0.56),
                    invocation_arguments=("LayerModule",),
                ),
                moduledef=ModuleDef(
                    clipping_bounds=((0.0, 0.0), (1.0, 0.21429)),
                    zoom_limits=(0.83738, 0.01),
                    grid=0.01,
                    zoomable=True,
                ),
            )
        ],
    )
    bp = BasePicture(
        header=ModuleHeader(name="Program", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Program",
        moduletype_defs=[panel_type],
        submodules=[
            SingleModule(
                header=ModuleHeader(name="Area", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
                submodules=[
                    ModuleTypeInstance(
                        header=ModuleHeader(
                            name="Panel",
                            invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0),
                            invocation_arguments=("IgnoreMaxModule",),
                        ),
                        moduletype_name="PanelType",
                    )
                ],
            )
        ],
    )
    snapshot = SimpleNamespace(
        entry_file=entry_file,
        base_picture=bp,
        project_graph=SimpleNamespace(unavailable_libraries=set()),
    )
    graph_inputs = structural_reports.WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=(entry_file,), dependency_files=()),
        snapshots=[snapshot],
        snapshot_failures=[],
    )

    report = structural_reports.collect_graphics_layout_report(tmp_path, graph_inputs=graph_inputs)

    panel_entry = next(entry for entry in report["entries"] if entry["module_path"] == "Program.Area.Panel")
    unit_control_entry = next(
        entry for entry in report["entries"] if entry["module_path"] == "Program.Area.Panel.UnitControl"
    )

    assert panel_entry["module_kind"] == "moduletype-instance"
    assert panel_entry["moduledef_origin_kind"] == "moduletype-definition"
    assert panel_entry["invocation"]["arguments"] == ["IgnoreMaxModule"]
    assert panel_entry["moduledef"]["clipping_size"] == [1.0, 0.5]
    assert unit_control_entry["definition_scope"] == "moduletype:PanelType"
    assert unit_control_entry["invocation"]["arguments"] == ["LayerModule"]
    assert unit_control_entry["moduledef"]["clipping_size"] == [1.0, 0.21429]


def test_collect_graphics_layout_report_flags_repeated_module_name_drift(tmp_path):
    entry_file = tmp_path / "Program" / "Main.s"
    bp = BasePicture(
        header=ModuleHeader(name="Program", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Program",
        submodules=[
            SingleModule(
                header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
                submodules=[
                    SingleModule(
                        header=ModuleHeader(
                            name="UnitControl",
                            invoke_coord=(1.43, 1.35, 0.0, 0.56, 0.56),
                        ),
                        moduledef=ModuleDef(
                            clipping_bounds=((0.0, 0.0), (1.0, 0.21429)),
                            zoom_limits=(0.83738, 0.01),
                            grid=0.01,
                            zoomable=True,
                        ),
                    )
                ],
            ),
            SingleModule(
                header=ModuleHeader(name="L2", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0))),
                submodules=[
                    SingleModule(
                        header=ModuleHeader(
                            name="UnitControl",
                            invoke_coord=(1.5, 1.4, 0.0, 0.56, 0.56),
                        ),
                        moduledef=ModuleDef(
                            clipping_bounds=((0.0, 0.0), (1.0, 0.25)),
                            zoom_limits=(0.83738, 0.01),
                            grid=0.01,
                            zoomable=True,
                        ),
                    )
                ],
            ),
        ],
    )
    snapshot = SimpleNamespace(
        entry_file=entry_file,
        base_picture=bp,
        project_graph=SimpleNamespace(unavailable_libraries=set()),
    )
    graph_inputs = structural_reports.WorkspaceGraphInputs(
        discovery=SimpleNamespace(program_files=(entry_file,), dependency_files=()),
        snapshots=[snapshot],
        snapshot_failures=[],
    )

    report = structural_reports.collect_graphics_layout_report(tmp_path, graph_inputs=graph_inputs)

    assert len(report["findings"]) == 1
    assert report["findings"][0]["id"] == "graphics-layout-drift"
    assert report["findings"][0]["module_name"] == "UnitControl"
    assert "invocation.coords" in report["findings"][0]["differing_fields"]
    assert "moduledef.clipping_size" in report["findings"][0]["differing_fields"]


def test_validate_pipeline_artifact_producers_rejects_duplicate_producer_ids():
    try:
        validate_pipeline_artifact_producers(
            pipeline.PIPELINE_ARTIFACTS,
            profile="quick",
            producers=(
                PipelineArtifactProducer("status", lambda artifact_context: {"kind": "status"}),
                PipelineArtifactProducer("status", lambda artifact_context: {"kind": "summary"}),
            ),
        )
    except ValueError as exc:
        assert "Duplicate pipeline artifact producers" in str(exc)
    else:
        raise AssertionError("Expected duplicate producer ids to raise ValueError")
