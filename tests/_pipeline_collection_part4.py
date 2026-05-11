# ruff: noqa: F403, F405
from ._pipeline_collection_test_support import *


def test_collect_impact_analysis_report_aggregates_reverse_dependencies(tmp_path):
    dependency_graph_report = {
        "nodes": [
            {"id": "main", "kind": "library"},
            {"id": "support", "kind": "library"},
            {"id": "shared", "kind": "library"},
        ],
        "edges": [
            {
                "source": "main",
                "target": "support",
                "kind": "depends_on",
                "entries": ["Program/Main.s"],
            },
            {
                "source": "support",
                "target": "shared",
                "kind": "depends_on",
                "entries": ["Libraries/Support.s"],
            },
        ],
        "snapshot_failures": [
            {
                "entry_file": "Program/Broken.s",
                "error": "broken dependency graph input",
                "error_type": "RuntimeError",
            }
        ],
    }
    call_graph_report = {
        "nodes": [
            {"id": "Main", "kind": "module"},
            {"id": "Main.Guard", "kind": "module"},
            {"id": "Main.Observer", "kind": "module"},
        ],
        "edges": [
            {
                "source": "Main",
                "target": "Main",
                "kind": "module-access",
                "reads": 0,
                "writes": 1,
                "access_count": 1,
                "symbol_count": 1,
                "symbols": ["Main.ExecuteLocal"],
                "entries": ["Program/Main.s"],
            },
            {
                "source": "Main.Guard",
                "target": "Main",
                "kind": "module-access",
                "reads": 1,
                "writes": 0,
                "access_count": 1,
                "symbol_count": 1,
                "symbols": ["Main.ExecuteLocal"],
                "entries": ["Program/Main.s"],
            },
            {
                "source": "Main.Observer",
                "target": "Main.Guard",
                "kind": "module-access",
                "reads": 1,
                "writes": 0,
                "access_count": 1,
                "symbol_count": 1,
                "symbols": ["Main.Guard.Seen"],
                "entries": ["Program/Main.s"],
            },
        ],
        "snapshot_failures": [
            {
                "entry_file": "Program/Broken.s",
                "error": "broken dependency graph input",
                "error_type": "RuntimeError",
            }
        ],
    }

    report = pipeline._collect_impact_analysis_report(
        tmp_path,
        dependency_graph_report=dependency_graph_report,
        call_graph_report=call_graph_report,
    )

    assert report["report_kind"] == "impact-analysis"
    assert report["snapshot_failures"] == dependency_graph_report["snapshot_failures"]

    support_impact = next(item for item in report["library_impacts"] if item["id"] == "support")
    shared_impact = next(item for item in report["library_impacts"] if item["id"] == "shared")
    main_module_impact = next(item for item in report["module_impacts"] if item["id"] == "Main")

    assert support_impact["direct_dependents"] == ["main"]
    assert support_impact["transitive_dependents"] == ["main"]
    assert shared_impact["direct_dependents"] == ["support"]
    assert shared_impact["transitive_dependents"] == ["main", "support"]
    assert shared_impact["transitive_entry_files"] == ["Libraries/Support.s", "Program/Main.s"]

    assert main_module_impact["direct_dependents"] == ["Main.Guard"]
    assert main_module_impact["transitive_dependents"] == ["Main.Guard", "Main.Observer"]
    assert main_module_impact["direct_reads"] == 1
    assert main_module_impact["transitive_reads"] == 2
    assert main_module_impact["direct_access_count"] == 1
    assert main_module_impact["transitive_access_count"] == 2
    assert main_module_impact["direct_symbols"] == ["Main.ExecuteLocal"]
    assert main_module_impact["transitive_symbols"] == ["Main.ExecuteLocal", "Main.Guard.Seen"]
    assert main_module_impact["direct_symbol_count"] == 1
    assert main_module_impact["transitive_symbol_count"] == 2


def test_progress_reporter_fail_stage_marks_overall_failed(tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one"), ("two", "Stage two")],
        emit_stdout=False,
    )

    reporter.start_stage("one")
    reporter.fail_stage("one", detail="something went wrong")

    payload = reporter.to_dict()

    assert payload["overall_status"] == "failed"
    failed = next(s for s in payload["stages"] if s["key"] == "one")
    assert failed["status"] == "failed"
    assert failed["detail"] == "something went wrong"


def test_progress_reporter_complete_stage_without_prior_start_sets_started_at(tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
        emit_stdout=False,
    )

    reporter.complete_stage("one")

    stage = reporter.to_dict()["stages"][0]
    assert stage["status"] == "completed"
    assert stage["started_at"] is not None


def test_progress_reporter_active_stage_payload_returns_active_stage(tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one"), ("two", "Stage two")],
        emit_stdout=False,
    )

    reporter.start_stage("two")
    payload = reporter.to_dict()

    assert payload["active_stage"] is not None
    assert payload["active_stage"]["key"] == "two"
    assert payload["active_stage"]["label"] == "Stage two"


def test_progress_reporter_fail_stage_without_start_sets_started_at(tmp_path):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
        emit_stdout=False,
    )

    reporter.fail_stage("one")

    stage = reporter.to_dict()["stages"][0]
    assert stage["status"] == "failed"
    assert stage["started_at"] is not None


def test_progress_reporter_fail_stage_emits_stdout(tmp_path, capsys):
    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
        emit_stdout=True,
    )

    reporter.fail_stage("one", detail="exploded")

    captured = capsys.readouterr()
    assert "failed Stage one" in captured.out
    assert "exploded" in captured.out


def test_progress_reporter_stage_raises_on_unknown_key(tmp_path):
    import pytest

    reporter = ProgressReporter(
        kind="sattlint.test.progress",
        title="Test",
        output_dir=tmp_path,
        write_json=lambda path, payload: None,
        stages=[("one", "Stage one")],
        emit_stdout=False,
    )

    with pytest.raises(KeyError, match="Unknown progress stage"):
        reporter.start_stage("no-such-key")


# --- artifact_registry.py line 23 (is_available), line 24-39 (to_dict) ---
def test_artifact_definition_is_available_false_when_not_in_profile(tmp_path):
    from sattlint.devtools.artifact_registry import ArtifactDefinition

    ad = ArtifactDefinition(
        artifact_id="test",
        filename="test.json",
        producer="test",
        schema_kind="sattlint.test",
        schema_version=1,
        profiles=("full",),
    )
    assert ad.is_available(profile="quick") is False
    assert ad.is_available(profile="full") is True
    assert ad.is_available(profile="full", enabled=False) is False


def test_artifact_definition_to_dict_returns_expected_shape():
    from sattlint.devtools.artifact_registry import ArtifactDefinition

    ad = ArtifactDefinition(
        artifact_id="my-art",
        filename="my-art.json",
        producer="producer",
        schema_kind="sattlint.myart",
        schema_version=2,
        profiles=("quick", "full"),
        optional=True,
        blocking=False,
    )
    result = ad.to_dict(enabled=True)
    assert result["artifact_id"] == "my-art"
    assert result["profiles"] == ["quick", "full"]
    assert result["optional"] is True
    assert result["enabled"] is True


# --- tool_reports.py lines 26, 34, 35 (build_command_report) ---
def test_build_command_report_returns_expected_keys(tmp_path):
    from types import SimpleNamespace

    from sattlint.devtools.tool_reports import build_command_report

    result_obj = SimpleNamespace(
        name="mytool",
        command=["mytool", "--flag"],
        exit_code=0,
        duration_seconds=1.23,
        stdout="ok",
        stderr="",
    )
    report = build_command_report(cast(Any, result_obj), repo_root=tmp_path, extra_key="extra_val")
    assert report["tool"] == "mytool"
    assert report["exit_code"] == 0
    assert report["extra_key"] == "extra_val"


# --- issue.py lines 10-13 (format_report_header) ---
def test_format_report_header_includes_status_when_given():
    from sattlint.analyzers.issue import format_report_header

    lines = format_report_header("varcheck", "Main.s", status="pass")
    assert "Report: varcheck" in lines
    assert "Target: Main.s" in lines
    assert "Status: pass" in lines


def test_format_report_header_omits_status_when_none():
    from sattlint.analyzers.issue import format_report_header

    lines = format_report_header("varcheck", "Main.s")
    assert len(lines) == 2


# --- sattline_builtins.py line 2090 (is_builtin_function) ---
def test_is_builtin_function_returns_true_for_known_function():
    from sattlint.analyzers.sattline_builtins import is_builtin_function

    assert is_builtin_function("CopyVariable") is True
    assert is_builtin_function("copyvariable") is True
    assert is_builtin_function("nonexistent_xyz") is False


# --- call_signatures.py: channel_kind async-operation branch, status_parameters, resolve_call_signature ---
def test_call_parameter_signature_channel_kind_returns_async_operation():
    from sattlint.call_signatures import CallParameterSignature

    p = CallParameterSignature(
        name="AsyncOperation",
        datatype="AsyncOperation",
        direction="inout",
        sorting="RS/WS",
        ownership="RO/WO",
    )
    assert p.channel_kind == "async-operation"
    assert p.is_status_channel is True


def test_resolve_call_signature_returns_signature_for_known_builtin():
    from sattlint.call_signatures import resolve_call_signature

    sig = resolve_call_signature("CopyVariable")
    assert sig is not None
    assert sig.name == "copyvariable"
    status_params = sig.status_parameters
    assert len(status_params) > 0


# --- call_signatures.py lines 59 (early return) and 63 (builtin not found) ---
def test_resolve_call_signature_returns_none_for_falsy_name():
    from sattlint.call_signatures import resolve_call_signature

    assert resolve_call_signature(None) is None
    assert resolve_call_signature("") is None


def test_resolve_call_signature_returns_none_for_unknown_builtin():
    from sattlint.call_signatures import resolve_call_signature

    assert resolve_call_signature("NonExistentFunctionXyz123") is None


# --- casefolding.py lines 13, 17-28 ---
def test_casefold_equal_compares_case_insensitively():
    from sattlint.casefolding import casefold_equal

    assert casefold_equal("Hello", "hello") is True
    assert casefold_equal("FOO", "bar") is False


def test_dedupe_casefolded_strings_removes_duplicates_and_empties():
    from sattlint.casefolding import dedupe_casefolded_strings

    result = dedupe_casefolded_strings(["Alpha", "alpha", "", "Beta", "BETA"])
    assert result == ["Alpha", "Beta"]


# --- _validation_shared.py: RawSourceValidationError, _span_kwargs, _warn_or_raise, _ref_span ---
def test_raw_source_validation_error_stores_line_and_column():
    from sattlint._validation_shared import RawSourceValidationError

    err = RawSourceValidationError("bad input", line=5, column=10, length=3)
    assert err.line == 5
    assert err.column == 10
    assert err.length == 3
    assert str(err) == "bad input"


def test_span_kwargs_returns_line_and_column_from_span():
    from sattline_parser.models.ast_model import SourceSpan
    from sattlint._validation_shared import _span_kwargs

    span = SourceSpan(line=3, column=7)
    result = _span_kwargs(span)
    assert result == {"line": 3, "column": 7}


def test_warn_or_raise_raises_when_no_sink():
    import pytest

    from sattlint._validation_shared import StructuralValidationError, _warn_or_raise

    with pytest.raises(StructuralValidationError, match="something bad"):
        _warn_or_raise("something bad", line=1, column=2, length=5)


def test_ref_span_returns_span_from_dict_with_span():
    from sattline_parser.models.ast_model import SourceSpan
    from sattlint._validation_shared import _ref_span

    span = SourceSpan(line=1, column=0)
    result = _ref_span({"span": span})
    assert result is span


def test_ref_span_returns_none_for_non_dict():
    from sattlint._validation_shared import _ref_span

    assert _ref_span(None) is None
    assert _ref_span("string") is None
    assert _ref_span({"span": "not-a-span"}) is None


# --- coverage_reports.py: skipped when no coverage.xml, high severity branch ---
def test_build_coverage_summary_report_skipped_when_no_xml(tmp_path):
    from sattlint.devtools.coverage_reports import build_coverage_summary_report

    result = build_coverage_summary_report(tmp_path)
    assert result["skipped"] is True
    assert result["skip_reason"] == "coverage.xml not found"
    assert result["modules"] == []
    assert result["change_scoped"]["status"] == "skipped"
    assert result["ratchet"]["status"] == "skipped"
    assert result["ratchet"]["setpoint_metrics"] == {
        "min_line_rate_basis_points": 10000,
        "min_changed_line_rate_basis_points": 10000,
        "min_touched_file_line_rate_basis_points": 9000,
    }
