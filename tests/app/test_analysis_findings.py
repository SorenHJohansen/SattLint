import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sattline_parser.models.ast_model import ScalarDatatype, Variable

from sattlint.analyzers.framework import Issue
from sattlint.analyzers.shared._validators import StringMappingValidator
from sattlint.application.checks import ChecksAnalyzerResult, ChecksRunResult, ChecksTargetResult
from sattlint.application.findings import (
    AnalysisFinding,
    extract_report_findings,
    finding_severity,
    kind_human_label,
)
from sattlint.cli._findings import (
    analyzer_default_severity,
    finding_payload,
    finding_summary,
    flat_findings,
)
from sattlint.cli.entry import run_cli
from sattlint.config.string_capacities import STANDARD_STRING_CAPACITIES
from sattlint.models._variable_issues import IssueKind, variable_issue_metadata
from sattlint.parser_api import SourceSpan
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


def test_extract_report_findings_reads_icf_source_location() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(
                kind="icf.unresolved_path",
                message="Demo.icf:12: unresolved path",
                module_path=["Program"],
                data={"file": "programs/Demo.icf", "line": 12},
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].file == "programs/Demo.icf"
    assert findings[0].line == 12
    assert findings[0].column is None
    assert findings[0].end_line is None


def test_extract_report_findings_reads_comment_code_source_location() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(
                kind="comment_code",
                message="Demo.s:4-6 commented code",
                module_path=["Root"],
                data={
                    "path": "programs/Demo.s",
                    "start_line": 4,
                    "end_line": 6,
                    "start_col": 2,
                    "end_col": 9,
                },
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].file == "programs/Demo.s"
    assert findings[0].line == 4
    assert findings[0].column == 2
    assert findings[0].end_line == 6


def test_extract_report_findings_reads_magic_number_literal_span() -> None:
    report = SimpleNamespace(
        issues=[
            MagicNumberIssue(
                module_path=["Root"],
                literal_value=7,
                literal_span=SourceSpan(start=41, end=42, line=9, column=3),
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].file is None
    assert findings[0].line == 9
    assert findings[0].column == 3
    assert findings[0].end_line is None


def test_extract_report_findings_reads_location_attributes_without_inventing_missing_fields() -> None:
    report = SimpleNamespace(
        issues=[
            SimpleNamespace(
                kind="comment_code",
                module_path=["Root"],
                file=Path("programs/Demo.s"),
                line=5,
                column=2,
                end_line=7,
            ),
            Issue(kind="unused", message="declared but never read", module_path=["Root"]),
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].file == "programs/Demo.s"
    assert findings[0].line == 5
    assert findings[0].column == 2
    assert findings[0].end_line == 7
    assert findings[1].file is None
    assert findings[1].line is None
    assert findings[1].column is None
    assert findings[1].end_line is None


def test_extract_report_findings_ignores_a_picture_path_as_a_source_file() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(
                kind="picture_display_paths.unresolved",
                message="unresolved path",
                module_path=["Root"],
                data={"path": "+MissingPanel"},
            )
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert findings[0].file is None
    assert findings[0].line is None
    assert findings[0].column is None
    assert findings[0].end_line is None


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


def test_analysis_finding_round_trips_source_location_through_dict() -> None:
    finding = AnalysisFinding(
        kind="comment_code",
        message="Demo.s:4-6 commented code",
        module_path=("Root",),
        file="programs/Demo.s",
        line=4,
        column=2,
        end_line=6,
    )

    payload = finding.to_dict()
    restored = AnalysisFinding.from_dict(payload)

    assert payload["file"] == "programs/Demo.s"
    assert payload["line"] == 4
    assert payload["column"] == 2
    assert payload["end_line"] == 6
    assert restored == finding


def test_analysis_finding_location_fields_default_to_none_in_dict() -> None:
    finding = AnalysisFinding(kind="unused", message="declared but never read")

    payload = finding.to_dict()

    assert payload["file"] is None
    assert payload["line"] is None
    assert payload["column"] is None
    assert payload["end_line"] is None


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


def _located_run(
    run_id: str,
    *,
    file: str | None = "programs/Demo.s",
    line: int | None = 12,
    column: int | None = 4,
    end_line: int | None = None,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_tag="Demo",
        project_path="",
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
                                file=file,
                                line=line,
                                column=column,
                                end_line=end_line,
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


def test_findings_text_line_includes_the_source_location(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runs(monkeypatch, [_located_run("located")])

    code = run_cli(["findings", "--run", "located"])

    assert code == 0
    output = capsys.readouterr().out
    assert "programs/Demo.s:12:4  Demo.A: Unused variable - declared but never read (variables)" in output


def test_findings_text_line_uses_a_line_only_location(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runs(monkeypatch, [_located_run("line-only", file=None, column=None)])

    code = run_cli(["findings", "--run", "line-only"])

    assert code == 0
    output = capsys.readouterr().out
    assert "line 12  Demo.A: Unused variable - declared but never read (variables)" in output


def test_finding_identity_ignores_the_source_location() -> None:
    first = _located_run("first", file="programs/Demo.s", line=12, column=4)
    moved = _located_run("moved", file="programs/Demo.s", line=40, column=1)

    assert flat_findings(first)[0].id == flat_findings(moved)[0].id


def test_findings_json_includes_the_source_location_and_null_when_absent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_runs(monkeypatch, [_located_run("located"), _run("plain", "")])

    code = run_cli(["findings", "--run", "located", "--format", "json"])

    assert code == 0
    located = json.loads(capsys.readouterr().out)["findings"][0]
    assert located["file"] == "programs/Demo.s"
    assert located["line"] == 12
    assert located["column"] == 4
    assert located["end_line"] is None

    code = run_cli(["findings", "--run", "plain", "--format", "json"])

    assert code == 0
    plain = json.loads(capsys.readouterr().out)["findings"][0]
    assert plain["file"] is None
    assert plain["line"] is None
    assert plain["column"] is None
    assert plain["end_line"] is None


def test_show_text_and_markdown_include_the_source_location(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _located_run("located", end_line=14)
    _install_runs(monkeypatch, [record])
    finding_id = flat_findings(record)[0].id

    code = run_cli(["show", finding_id, "--run", "located"])

    assert code == 0
    output = capsys.readouterr().out
    assert "File:    programs/Demo.s" in output
    assert "Line:    12-14" in output
    assert "Column:  4" in output

    code = run_cli(["show", finding_id, "--run", "located", "--format", "markdown"])

    assert code == 0
    markdown = capsys.readouterr().out
    assert "- **Location:** `programs/Demo.s:12-14:4`" in markdown


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


_ANALYZE_PROJECT_BODY = """
slproj_version = 2
analyzed_programs_and_libraries = ["Demo"]
analyzers = ["variables"]
mode = "official"
program_dir = "programs"
ABB_lib_dir = ""
icf_dir = ""
other_lib_dirs = []

[string_capacities]
identstring = 15
tagstring = 30
string = 40
linestring = 80
maxstring = 140
"""


@pytest.fixture
def isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.config_path_location", lambda: tmp_path / "config.toml")


def _write_analyze_project(tmp_path: Path) -> Path:
    (tmp_path / "programs").mkdir(exist_ok=True)
    project = tmp_path / "demo.slproj"
    project.write_text(_ANALYZE_PROJECT_BODY, encoding="utf-8")
    return project


def _checks_result(*findings: AnalysisFinding, analyzer_key: str = "variables") -> ChecksRunResult:
    return ChecksRunResult(
        output_lines=(),
        targets=(
            ChecksTargetResult(
                target_name="Demo",
                is_library=False,
                analyzers=(
                    ChecksAnalyzerResult(
                        key=analyzer_key,
                        name="Variable issues",
                        status="completed",
                        findings=tuple(findings),
                    ),
                ),
            ),
        ),
        selected_analyzers=(analyzer_key,),
        run_id="run-analyze",
    )


def _fake_collect(result: ChecksRunResult):
    def _collect(*_args: object, **_kwargs: object) -> ChecksRunResult:
        return result

    return _collect


def _run_with_findings(
    run_id: str,
    *findings: AnalysisFinding,
    analyzer_key: str = "variables",
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        project_tag="Demo",
        project_path="",
        selected_analyzers=(analyzer_key,),
        targets=(
            RunTargetRecord(
                target_name="Demo",
                is_library=False,
                analyzers=(
                    RunAnalyzerRecord(
                        key=analyzer_key,
                        name="Variable issues",
                        status="completed",
                        findings=tuple(findings),
                    ),
                ),
            ),
        ),
    )


def test_finding_severity_covers_error_warning_and_info_kinds() -> None:
    assert finding_severity("dataflow.dead_overwrite") == "error"
    assert finding_severity("string_capacity.literal_overflow") == "error"
    assert finding_severity("sfc_missing_initial_step") == "error"
    assert finding_severity("unused") == "warning"
    assert finding_severity("alarm.never_cleared") == "warning"
    assert finding_severity("magic_number") == "info"
    assert finding_severity("comment_code") == "info"
    assert finding_severity("custom.unknown_kind") is None


def test_extract_report_findings_sets_severity_from_the_kind_table() -> None:
    report = SimpleNamespace(
        issues=[
            Issue(kind="dataflow.dead_overwrite", message="overwritten", module_path=["Root"]),
            Issue(kind="unused", message="declared but never read", module_path=["Root"]),
            Issue(kind="magic_number", message="literal 7", module_path=["Root"]),
        ]
    )

    findings = extract_report_findings(report, default_name="Root")

    assert [finding.severity for finding in findings] == ["error", "warning", "info"]


def test_unknown_kind_stays_unknown_and_the_payload_uses_the_analyzer_default() -> None:
    report = SimpleNamespace(issues=[Issue(kind="custom.unknown_kind", message="custom check", module_path=["Root"])])
    extracted = extract_report_findings(report, default_name="Root")

    assert extracted[0].severity is None
    assert analyzer_default_severity("cyclomatic-complexity") == "info"
    assert analyzer_default_severity("not-in-the-catalog") == "warning"

    record = _run_with_findings("unknown", extracted[0], analyzer_key="cyclomatic-complexity")
    payload = finding_payload(flat_findings(record)[0])

    assert payload["severity"] == "info"


def test_finding_summary_counts_by_severity() -> None:
    record = _run_with_findings(
        "summary",
        AnalysisFinding(kind="a", message="one", module_path=("Demo", "A"), severity="error"),
        AnalysisFinding(kind="b", message="two", module_path=("Demo", "A"), severity="warning"),
        AnalysisFinding(kind="c", message="three", module_path=("Demo", "A"), severity="info"),
    )

    summary = finding_summary(flat_findings(record))

    assert summary["by_severity"] == {"error": 1, "warning": 1, "info": 1}


def test_analyze_fail_on_thresholds(
    isolate_user_config: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_analyze_project(tmp_path)
    info_finding = AnalysisFinding(
        kind="magic_number",
        message="literal 7",
        module_path=("Demo", "A"),
        severity="info",
    )
    monkeypatch.setattr(
        "sattlint.cli.commands.collect_checks_result",
        _fake_collect(_checks_result(info_finding)),
    )

    assert run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "warning"]) == 0
    capsys.readouterr()
    assert run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "any"]) == 1
    capsys.readouterr()

    warning_finding = AnalysisFinding(
        kind="unused",
        message="declared but never read",
        module_path=("Demo", "A"),
        severity="warning",
    )
    monkeypatch.setattr(
        "sattlint.cli.commands.collect_checks_result",
        _fake_collect(_checks_result(warning_finding)),
    )

    assert run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "warning"]) == 1
    capsys.readouterr()
    assert run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"]) == 0
    capsys.readouterr()
    assert run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "bogus"]) == 2
    assert "invalid choice" in capsys.readouterr().err


def test_analyze_json_and_text_carry_severity(
    isolate_user_config: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    project = _write_analyze_project(tmp_path)
    error_finding = AnalysisFinding(
        kind="dataflow.dead_overwrite",
        message="overwritten before it is read",
        module_path=("Demo", "A"),
        severity="error",
    )
    monkeypatch.setattr(
        "sattlint.cli.commands.collect_checks_result",
        _fake_collect(_checks_result(error_finding)),
    )

    code = run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "error"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"][0]["severity"] == "error"
    assert payload["summary"]["by_severity"] == {"error": 1, "warning": 0, "info": 0}
    assert payload["summary"]["fail_on"] == "error"

    code = run_cli(["analyze", "--project", str(project), "--format", "text", "--fail-on", "none"])

    assert code == 0
    assert "[error] Demo.A: Dead overwrite - overwritten before it is read (variables)" in capsys.readouterr().out


def test_findings_and_show_text_include_severity(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = _run_with_findings(
        "severity",
        AnalysisFinding(
            kind="unused",
            message="declared but never read",
            module_path=("Demo", "A"),
            severity="warning",
        ),
    )
    _install_runs(monkeypatch, [record])
    finding_id = flat_findings(record)[0].id

    code = run_cli(["findings", "--run", "severity"])

    assert code == 0
    assert "[warning] Demo.A: Unused variable - declared but never read (variables)" in capsys.readouterr().out

    code = run_cli(["findings", "--run", "severity", "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"][0]["severity"] == "warning"
    assert payload["summary"]["by_severity"] == {"error": 0, "warning": 1, "info": 0}

    code = run_cli(["show", finding_id, "--run", "severity"])

    assert code == 0
    assert "Severity: warning" in capsys.readouterr().out

    code = run_cli(["show", finding_id, "--run", "severity", "--format", "markdown"])

    assert code == 0
    assert "- **Severity:** `warning`" in capsys.readouterr().out
