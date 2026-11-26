import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sattline_parser.models.ast_model import ScalarDatatype, Variable

from sattlint.analyzers.framework import Issue
from sattlint.analyzers.shared._validators import StringMappingValidator
from sattlint.application.findings import AnalysisFinding, extract_report_findings, kind_human_label
from sattlint.cli._findings import flat_findings
from sattlint.cli.entry import run_cli
from sattlint.config.string_capacities import STANDARD_STRING_CAPACITIES
from sattlint.models._variable_issues import IssueKind, variable_issue_metadata
from sattlint.reporting.variables_report import (
    MagicNumberIssue,
    ProcedureStatusIssue,
    UnknownParameterTargetIssue,
    UnusedDatatypeFieldIssue,
    UnusedIssue,
    VariablesReport,
)
from sattlint.runs import RunAnalyzerRecord, RunRecord, RunSummary, RunTargetRecord


def test_extract_report_findings_normalizes_framework_issues() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(
                kind="unused",
                message="declared but never read",
                module_path=["Root", "Mod"],
                rule_id="unused.variable",
                explanation="Stale declarations add noise.",
                suggestion="Delete the declaration.",
            ),
            Issue(kind="shadowing", message="shadows outer scope"),
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 2
    first, second = findings
    assert first.kind == "unused"
    assert first.message == "declared but never read"
    assert first.module_path == ("Root", "Mod")
    assert first.rule_id == "unused.variable"
    assert first.explanation is not None
    assert first.suggestion is not None
    assert second.kind == "shadowing"
    assert second.module_path == ("Root",)


def test_extract_report_findings_keeps_distinct_data_at_the_same_site() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(
                kind="dataflow.dead_overwrite",
                message="overwritten",
                module_path=["Root", "Mod"],
                data={"site": "SQ:Seq > STEP:One", "symbol": "A"},
            ),
            Issue(
                kind="dataflow.dead_overwrite",
                message="overwritten",
                module_path=["Root", "Mod"],
                data={"site": "SQ:Seq > STEP:One", "symbol": "B"},
            ),
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 2


def test_extract_report_findings_handles_enum_kind_and_empty_module_path() -> None:
    class Kind:
        value = "never_read"

    report = SimpleNamespace(issues=[SimpleNamespace(kind=Kind(), message="written but never read", module_path=[])])

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 1
    assert findings[0].kind == "never_read"
    assert findings[0].module_path == ("Root",)


def test_extract_report_findings_handles_rule_based_issues_and_message_fallback() -> None:
    report = SimpleNamespace(
        issues=[
            SimpleNamespace(
                rule=SimpleNamespace(id="icf.program_mismatch"),
                message="entry points to another program",
                module_path=["Root", "Seq"],
            ),
            SimpleNamespace(kind="unused", module_path=["Root"]),
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].kind == "icf.program_mismatch"
    assert findings[0].message == "entry points to another program"
    assert findings[0].module_path == ("Root", "Seq")
    assert findings[1].kind == "unused"
    assert findings[1].message  # falls back to str(item)


def test_extract_report_findings_returns_empty_for_missing_or_non_list_issues() -> None:
    assert extract_report_findings(SimpleNamespace(), default_name="Root") == ()
    assert extract_report_findings(SimpleNamespace(issues=[]), default_name="Root") == ()
    assert extract_report_findings(SimpleNamespace(issues="not-a-list"), default_name="Root") == ()


def test_datatype_report_excludes_supporting_variable_findings() -> None:
    report = VariablesReport(
        basepicture_name="Root",
        issues=[
            UnusedDatatypeFieldIssue(
                module_path=["Root"], datatype_name="Payload", field_path="Field", role="datatype field"
            ),
            MagicNumberIssue(module_path=["Root"], literal_value=1, role="literal"),
            UnknownParameterTargetIssue(module_path=["Root"], role="mapping"),
        ],
        visible_kinds=frozenset({IssueKind.UNUSED_DATATYPE_FIELD}),
    )

    findings = extract_report_findings(report, default_name="Root")

    assert [finding.kind for finding in findings] == ["unused_datatype_field"]
    assert findings[0].data["field_path"] == "Field"
    assert "variable_name" not in findings[0].data


def test_string_mapping_finding_shows_both_capacities() -> None:
    issues = StringMappingValidator(STANDARD_STRING_CAPACITIES).check_string_mapping(
        Variable(name="Name", datatype=ScalarDatatype.IDENTSTRING),
        Variable(name="SourceName", datatype=ScalarDatatype.STRING),
        ["Root", "Child"],
    )
    findings = extract_report_findings(SimpleNamespace(issues=issues), default_name="Root")
    context = findings[0].data["context"]
    assert isinstance(context, str)
    assert "Name (identstring, 15 characters)" in context
    assert "SourceName (string, 40 characters)" in context


def test_extract_report_findings_records_the_variable_declaration_role() -> None:
    variable = Variable(name="Value", datatype=ScalarDatatype.INTEGER)
    report = SimpleNamespace(
        issues=[
            UnusedIssue(
                module_path=["Root"],
                variable=variable,
                role="moduleparameter",
                declaration_role="moduleparameter",
            ),
            ProcedureStatusIssue(
                module_path=["Root"],
                variable=variable,
                role="procedure status output is ignored",
                field_path=None,
                declaration_role="localvariable",
            ),
            MagicNumberIssue(module_path=["Root"], literal_value=1, role="literal"),
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].data["declaration_role"] == "moduleparameter"
    assert findings[1].data["declaration_role"] == "localvariable"
    assert "declaration_role" not in findings[2].data


def test_analysis_finding_round_trips_through_dict() -> None:
    finding = AnalysisFinding(
        kind="unused",
        message="declared but never read",
        module_path=("Root", "Mod"),
        rule_id="unused.variable",
        explanation="Explains.",
        suggestion="Fixes.",
    )

    restored = AnalysisFinding.from_dict(finding.to_dict())

    assert restored == finding


def test_extract_report_findings_carries_issue_data_and_sanitizes_values() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(
                kind="icf.unresolved_path",
                message="Program.icf:1: unresolved path",
                module_path=["Program"],
                data={"site": "Program.icf:1", "context": "X1 = Program:Path.Var", "nested": {"a": 1}},
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 1
    assert findings[0].data == {"site": "Program.icf:1", "context": "X1 = Program:Path.Var", "nested": {"a": 1}}


def test_extract_report_findings_synthesizes_site_and_context_from_attributes() -> None:
    variable = SimpleNamespace(name="TargetVal")
    source_variable = SimpleNamespace(name="SourceVal")
    report = SimpleNamespace(
        issues=[
            SimpleNamespace(
                kind="string_mapping_mismatch",
                module_path=["Root", "Child"],
                variable=variable,
                source_variable=source_variable,
                source_display_name="SourceVal",
                target_display_name="TargetVal",
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert len(findings) == 1
    # Scope and mapping relation are separate keys: the variable names the
    # scope, the arrow text names the relation.
    assert findings[0].data == {"context": "TargetVal", "relation": "TargetVal => SourceVal"}


def test_kind_human_label_returns_short_phrase() -> None:
    assert kind_human_label("magic_number") == "Magic number"
    assert kind_human_label("sfc_parallel_write_race") == "Parallel write race"
    assert kind_human_label("dataflow.condition_always_false") == "Condition always false"
    assert kind_human_label("sfc_missing_initial_step") == "Missing initial step at sequence start"
    assert kind_human_label("unknown_custom_kind") == "Unknown Custom Kind"


def test_stored_runs_still_render_removed_analyzer_kinds() -> None:
    # The analyzers are gone, but run history keeps their findings readable.
    assert kind_human_label("module.version_drift") == "Version drift"
    assert kind_human_label("spec.sequence_step_prefix") == "Sequence step prefix"
    assert kind_human_label("spec.transition_name_missing") == "Transition name missing"


def test_extract_report_findings_synthesizes_site_from_sequence_name() -> None:
    report = SimpleNamespace(issues=[SimpleNamespace(kind="unused", module_path=["Root"], sequence_name="MainSeq")])

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].data["site"] == "SQ:MainSeq"
    assert "context" not in findings[0].data


def test_extract_report_findings_sources_explanation_and_suggestion_from_variable_metadata() -> None:
    report = SimpleNamespace(issues=[SimpleNamespace(kind=IssueKind.UNUSED, module_path=["Root"])])

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].kind == "unused"
    assert findings[0].explanation
    assert findings[0].suggestion


def test_variable_issue_metadata_is_selected_by_kind_value() -> None:
    from_enum = variable_issue_metadata(IssueKind.UNUSED)

    assert from_enum.explanation
    assert from_enum.suggestion
    assert variable_issue_metadata("unused") == from_enum
    assert variable_issue_metadata("not_a_known_kind") == variable_issue_metadata(None)


def test_retired_kind_aliases_are_not_special_cased() -> None:
    assert kind_human_label("sfc_unreachable_sequence_node") == "Unreachable sequence node"
    assert kind_human_label("unreachable_sequence_node") == "Unreachable Sequence Node"
    assert kind_human_label("scan_cycle_shared_access_hazard") == "Scan Cycle Shared Access Hazard"


def test_extract_report_findings_uses_explicit_context_attribute() -> None:
    report = SimpleNamespace(
        issues=[
            SimpleNamespace(
                kind=IssueKind.MAGIC_NUMBER,
                module_path=["Root"],
                context="Output = 1",
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].data["context"] == "Output = 1"


_PROJECT_BODY = """
slproj_version = 2
mode = "official"
analyzers = []

[string_capacities]
identstring = 15
tagstring = 30
string = 40
linestring = 80
maxstring = 140
"""


def _write_project(path: Path) -> Path:
    path.write_text(_PROJECT_BODY, encoding="utf-8")
    return path.resolve()


def _run(run_id: str, project_path: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_tag="Demo",
        project_path=project_path,
        selected_analyzers=("variables",),
        targets=(
            RunTargetRecord(
                target_name="Demo",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key="variables",
                        name="Variable issues",
                        status="completed",
                        findings=(
                            AnalysisFinding(
                                kind="unused",
                                message="declared but never read",
                                module_path=("Demo", "A"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _install_runs(monkeypatch: pytest.MonkeyPatch, records: list[RunRecord]) -> None:
    summaries = tuple(RunSummary.from_record(record) for record in records)
    by_id = {record.run_id: record for record in records}
    monkeypatch.setattr("sattlint.cli._findings.list_runs", lambda: summaries)

    def _load(run_id: str) -> RunRecord | None:
        return by_id.get(run_id)

    monkeypatch.setattr("sattlint.cli._findings.load_run", _load)


def test_findings_latest_resolves_within_the_discovered_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _write_project(tmp_path / "app.slproj")
    foreign = _run("foreign", str(tmp_path / "elsewhere" / "other.slproj"))
    mine = _run("mine", str(project))
    # The foreign run is newer, so a machine-wide latest would pick it.
    _install_runs(monkeypatch, [foreign, mine])

    code = run_cli(["findings", "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["run_id"] == "mine"
    assert payload["run"]["project_path"] == str(project)


def test_findings_latest_never_returns_another_projects_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _write_project(tmp_path / "app.slproj")
    _install_runs(monkeypatch, [_run("foreign", str(tmp_path / "elsewhere" / "other.slproj"))])

    code = run_cli(["findings", "--format", "json"])

    assert project.exists()
    assert code == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "no_runs_for_project"


def test_findings_text_header_names_the_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _write_project(tmp_path / "app.slproj")
    _install_runs(monkeypatch, [_run("mine", str(project))])

    code = run_cli(["findings"])

    assert code == 0
    first_line = capsys.readouterr().out.splitlines()[0]
    assert first_line.startswith(f"Run: mine  Project: {project}")


def test_findings_ndjson_envelope_names_the_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _write_project(tmp_path / "app.slproj")
    _install_runs(monkeypatch, [_run("mine", str(project))])

    code = run_cli(["findings", "--format", "ndjson"])

    assert code == 0
    envelope = json.loads(capsys.readouterr().out.splitlines()[0])
    assert envelope["record_type"] == "envelope"
    assert envelope["run"]["project_path"] == str(project)


def test_findings_latest_refuses_without_a_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runs(monkeypatch, [_run("foreign", str(tmp_path / "other.slproj"))])

    code = run_cli(["findings", "--format", "json"])

    assert code == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "run_scope_unknown"
    assert "--project" in error["message"]
    assert "--run" in error["message"]


def test_findings_without_any_runs_reports_no_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runs(monkeypatch, [])

    code = run_cli(["findings", "--format", "json"])

    assert code == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "no_runs"


def test_findings_named_run_does_not_need_a_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runs(monkeypatch, [_run("foreign", str(tmp_path / "other.slproj"))])

    code = run_cli(["findings", "--run", "foreign", "--format", "json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["run"]["run_id"] == "foreign"


def test_findings_named_run_skips_ambiguous_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_project(tmp_path / "first.slproj")
    _write_project(tmp_path / "second.slproj")
    _install_runs(monkeypatch, [_run("foreign", "")])

    code = run_cli(["findings", "--run", "foreign", "--format", "json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["run"]["run_id"] == "foreign"


def test_findings_named_run_keeps_its_own_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_project(tmp_path / "app.slproj")
    foreign_path = str(tmp_path / "elsewhere" / "other.slproj")
    _install_runs(monkeypatch, [_run("foreign", foreign_path)])

    code = run_cli(["findings", "--run", "foreign", "--format", "json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["run"]["project_path"] == foreign_path


def test_findings_explicit_project_bypasses_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _write_project(tmp_path / "app.slproj")
    _install_runs(monkeypatch, [_run("mine", str(project))])

    def _fail() -> None:
        raise AssertionError("discovery must not run when --project is given")

    monkeypatch.setattr("sattlint.cli.commands.discover_project_result", _fail)

    code = run_cli(["findings", "--project", str(project), "--format", "json"])

    assert code == 0
    assert json.loads(capsys.readouterr().out)["run"]["run_id"] == "mine"


def test_findings_reports_ambiguous_project_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_project(tmp_path / "first.slproj")
    _write_project(tmp_path / "second.slproj")
    _install_runs(monkeypatch, [])

    code = run_cli(["findings", "--format", "json"])

    assert code == 2
    error = json.loads(capsys.readouterr().err)["error"]
    assert error["code"] == "project_ambiguous"
    candidates = {Path(item).name for item in error["details"]["candidates"]}
    assert candidates == {"first.slproj", "second.slproj"}
    assert "--project" in error["message"]


def test_show_latest_uses_the_discovered_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = _write_project(tmp_path / "app.slproj")
    foreign = _run("foreign", str(tmp_path / "elsewhere" / "other.slproj"))
    mine = _run("mine", str(project))
    _install_runs(monkeypatch, [foreign, mine])
    finding_id = flat_findings(mine)[0].id

    code = run_cli(["show", finding_id, "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["run_id"] == "mine"
    assert payload["run"]["project_path"] == str(project)
