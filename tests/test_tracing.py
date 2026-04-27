from pathlib import Path

from sattlint.tracing import trace_source_file_analysis


def test_trace_source_file_analysis_reports_issue_counts_and_events(tmp_path):
    source_file = Path("tests/fixtures/sample_sattline_files/LinterTestProgram.s")
    output_path = tmp_path / "trace.json"

    payload = trace_source_file_analysis(source_file, output_path=output_path)

    assert output_path.exists()
    assert payload["source_file"] == "tests/fixtures/sample_sattline_files/LinterTestProgram.s"
    assert payload["syntax_validation"]["ok"] is True
    assert payload["variable_analysis"]["issue_count"] >= 1
    assert payload["dataflow_analysis"]["issue_count"] >= 0
    assert payload["ast_summary"]["sequence_count"] >= 0
    assert any(event["phase"] == "variables" for event in payload["events"])
    assert any(
        event["action"] == "basepicture-loaded"
        and event.get("data", {}).get("source_file") == "tests/fixtures/sample_sattline_files/LinterTestProgram.s"
        for event in payload["events"]
    )


def test_trace_source_file_analysis_redacts_external_paths(tmp_path):
    source_file = tmp_path / "ExternalProgram.s"
    source_file.write_text(
        '"SyntaxVersion"\n"OriginalFileDate"\n"ProgramDate"\nBasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123\nENDDEF (*BasePicture*);\n',
        encoding="utf-8",
    )

    payload = trace_source_file_analysis(source_file)

    assert payload["source_file"] == "<external>/ExternalProgram.s"


def test_trace_source_file_analysis_includes_timing_summary(tmp_path):
    source_file = Path("tests/fixtures/sample_sattline_files/LinterTestProgram.s")
    output_path = tmp_path / "trace.json"

    payload = trace_source_file_analysis(source_file, output_path=output_path)

    assert "timing_summary" in payload
    assert "variables" in payload["timing_summary"]
    assert payload["timing_summary"]["variables"]["event_count"] >= 1
    assert payload["timing_summary"]["variables"]["span_ms"] >= 0.0
