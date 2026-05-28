from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeInstance,
    SingleModule,
)
from sattlint import tracing
from sattlint.devtools import trace_reports
from sattlint.tracing import (
    collect_ast_summary,
    detect_transform_invariant_violations,
    trace_source_file_analysis,
)


def _sample_program_path() -> Path:
    return Path("tests/fixtures/sample_sattline_files/LinterTestProgram.s")


def test_trace_source_file_analysis_reports_issue_counts_and_events(tmp_path):
    source_file = _sample_program_path()
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
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0,0,0,1,1) : MODULEDEFINITION DateCode_ 123\n"
        "ENDDEF (*BasePicture*);\n",
        encoding="utf-8",
    )

    payload = trace_source_file_analysis(source_file)

    assert payload["source_file"] == "<external>/ExternalProgram.s"


def test_trace_source_file_analysis_includes_timing_summary(tmp_path):
    source_file = _sample_program_path()
    output_path = tmp_path / "trace.json"

    payload = trace_source_file_analysis(source_file, output_path=output_path)

    assert "timing_summary" in payload
    assert "variables" in payload["timing_summary"]
    assert payload["timing_summary"]["variables"]["event_count"] >= 1
    assert payload["timing_summary"]["variables"]["span_ms"] >= 0.0


def test_trace_source_file_analysis_reports_output_write_error(monkeypatch, tmp_path):
    source_file = _sample_program_path()
    output_path = tmp_path / "trace.json"
    original_write_text = Path.write_text

    def fail_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self == output_path:
            raise PermissionError("locked")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    payload = trace_source_file_analysis(source_file, output_path=output_path)

    assert payload["syntax_validation"]["ok"] is True
    assert payload["output_error"] == {
        "path": "<external>/trace.json",
        "error": "locked",
        "error_type": "PermissionError",
    }


def test_tracing_cli_returns_failure_when_output_write_fails(monkeypatch, tmp_path, capsys):
    source_file = str(_sample_program_path())
    output_path = tmp_path / "trace.json"
    original_write_text = Path.write_text

    def fail_write_text(self: Path, *args: object, **kwargs: object) -> int:
        if self == output_path:
            raise PermissionError("locked")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    exit_code = tracing.cli([source_file, "--output", str(output_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "Trace output error: locked" in captured.err


def test_collect_trace_report_delegates_to_trace_source_file_analysis(tmp_path):
    source_file = _sample_program_path()

    payload = trace_reports.collect_trace_report(source_file)

    assert payload["source_file"] == "tests/fixtures/sample_sattline_files/LinterTestProgram.s"
    assert payload["syntax_validation"]["ok"] is True


def _make_bp(*, submodules=None, moduletype_defs=None) -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        submodules=submodules or [],
        moduletype_defs=moduletype_defs or [],
    )


def _make_single(name: str) -> SingleModule:
    return SingleModule(
        header=ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.5, 0.5)),
        moduledef=None,
    )


def _make_frame(name: str, submodules=None) -> FrameModule:
    return FrameModule(
        header=ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        submodules=submodules or [],
    )


def _make_mti(name: str, type_name: str) -> ModuleTypeInstance:
    return ModuleTypeInstance(
        header=ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.5, 0.5)),
        moduletype_name=type_name,
    )


def test_collect_ast_summary_counts_frame_module_and_moduletype_instance():
    bp = _make_bp(
        submodules=[
            _make_frame("FM1", submodules=[_make_single("SM1")]),
            _make_mti("MTI1", "SomeType"),
        ]
    )

    summary = collect_ast_summary(bp)

    assert summary["submodule_count"] == 3
    assert summary["frame_module_count"] == 1
    assert summary["single_module_count"] == 1
    assert summary["moduletype_instance_count"] == 1


def test_detect_transform_invariant_violations_flags_unexpected_type():
    class _UnknownNode:
        pass

    bp = _make_bp(submodules=[_UnknownNode()])

    violations = detect_transform_invariant_violations(bp)

    assert len(violations) == 1
    assert violations[0]["kind"] == "unexpected_submodule_type"
    assert "_UnknownNode" in violations[0]["node_label"]


def test_detect_transform_invariant_violations_flags_duplicate_sibling_names():
    bp = _make_bp(submodules=[_make_single("Dup"), _make_single("Dup")])

    violations = detect_transform_invariant_violations(bp)

    assert any(v["kind"] == "duplicate_sibling_name" and v["module_name"] == "Dup" for v in violations)


def test_tracing_cli_writes_json_to_stdout(capsys):
    source_file = str(_sample_program_path())

    exit_code = tracing.cli([source_file])

    assert exit_code == 0
    output = capsys.readouterr().out
    payload = __import__("json").loads(output)
    assert payload["syntax_validation"]["ok"] is True


def test_tracing_cli_writes_to_output_file(tmp_path):
    source_file = str(_sample_program_path())
    output_file = str(tmp_path / "trace.json")

    exit_code = tracing.cli([source_file, "--output", output_file])

    assert exit_code == 0
    assert (tmp_path / "trace.json").exists()


# --- analyzers/_sfc_module_walk.py: iter_sfc_modulecodes with nested modules ---
def test_iter_sfc_modulecodes_yields_root_and_nested(tmp_path):
    from sattline_parser.models.ast_model import BasePicture, ModuleHeader, SingleModule
    from sattlint.analyzers._sfc_module_walk import iter_sfc_modulecodes

    bp_header = ModuleHeader(name="BP", invoke_coord=(0, 0, 0, 1, 1))
    sm_header = ModuleHeader(name="Child", invoke_coord=(0, 0, 0, 1, 1))
    sm = SingleModule(header=sm_header, moduledef=None)
    bp = BasePicture(header=bp_header, name="BP", submodules=[sm])

    results = list(iter_sfc_modulecodes(bp))
    module_paths = [r[0] for r in results]
    assert ["BP"] in module_paths
    assert ["BP", "Child"] in module_paths


def test_iter_sfc_modulecodes_yields_moduletype_defs():
    from sattline_parser.models.ast_model import BasePicture, ModuleHeader, ModuleTypeDef
    from sattlint.analyzers._sfc_module_walk import iter_sfc_modulecodes

    bp_header = ModuleHeader(name="BP", invoke_coord=(0, 0, 0, 1, 1))
    mtd = ModuleTypeDef(name="MyType")
    bp = BasePicture(header=bp_header, name="BP", moduletype_defs=[mtd])

    results = list(iter_sfc_modulecodes(bp))
    paths = [r[0] for r in results]
    assert any("TypeDef:MyType" in p for p in [str(p) for p in paths])
