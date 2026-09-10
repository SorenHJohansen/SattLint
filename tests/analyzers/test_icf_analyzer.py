# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from sattline_parser.models.ast_model import BasePicture

import sattlint.analyzers.icf.analyzer as analyzer_module
from sattlint.analyzers.registry import (
    DEFAULT_CLI_ANALYZER_KEYS,
    get_default_analyzer_catalog,
    get_selectable_analyzers,
)
from sattlint.config.types import ConfigDict
from sattlint.reporting.icf_report import ICFEntry, ICFValidationIssue, ICFValidationReport


def _config(**overrides: object) -> ConfigDict:
    return cast(ConfigDict, {"icf_dir": "/tmp/icf", **overrides})


def _entry(line: int = 3, value: str = "Program:Module.Var") -> ICFEntry:
    return ICFEntry(
        file_path=Path("Program.icf"),
        line_no=line,
        section="TAGLIST",
        key="X1",
        value=value,
    )


def _issue(reason: str, detail: str | None = None) -> ICFValidationIssue:
    return ICFValidationIssue(entry=_entry(), reason=reason, detail=detail)


def _report(*issues: ICFValidationIssue) -> ICFValidationReport:
    return ICFValidationReport(
        icf_file=Path("Program.icf"),
        program_name="Program",
        total_entries=1,
        validated_entries=1,
        valid_entries=0,
        skipped_entries=0,
        issues=list(issues),
    )


def _graph() -> SimpleNamespace:
    return SimpleNamespace(ast_by_name={})


def _base_picture(name: str = "Program") -> BasePicture:
    return cast(BasePicture, SimpleNamespace(header=SimpleNamespace(name=name)))


@pytest.mark.parametrize(
    ("reason", "expected_kind"),
    [
        ("program mismatch", "icf.program_mismatch"),
        ("unresolved path", "icf.unresolved_path"),
        ("invalid field path", "icf.invalid_field_path"),
        ("reference case mismatch", "icf.reference_case_mismatch"),
        ("unit tag mismatch", "icf.unit_tag_mismatch"),
        ("group tag mismatch", "icf.group_tag_mismatch"),
        ("missing journal parameter fields", "icf.missing_journal_field"),
        ("unit structure drift", "icf.unit_structure_drift"),
        ("mixed ICF value prefix letters", "icf.value_prefix_inconsistency"),
    ],
)
def test_reason_maps_to_icf_kind(reason: str, expected_kind: str) -> None:
    assert analyzer_module._kind_for_reason(reason) == expected_kind


def test_unknown_reason_falls_back_to_generic_kind() -> None:
    assert analyzer_module._kind_for_reason("something new") == "icf.issue"


def test_analyzes_all_configured_icf_files(monkeypatch) -> None:
    icf_dir = Path("/tmp/icf")
    f1 = icf_dir / "ProgramA.icf"
    f2 = icf_dir / "ProgramB.icf"
    monkeypatch.setattr(analyzer_module, "configured_icf_files", lambda config: (icf_dir, [f1, f2]))
    monkeypatch.setattr(analyzer_module, "parse_icf_file", lambda path: [_entry()])
    monkeypatch.setattr(
        analyzer_module,
        "load_program_ast",
        lambda cfg, name: (_base_picture(name), _graph()),
    )
    monkeypatch.setattr(analyzer_module, "merge_project_basepicture", lambda bp, graph: bp)

    seen_programs: list[str] = []

    def fake_validate(bp, entries, *, expected_program, debug=False, moduletype_index=None):
        seen_programs.append(expected_program)
        return _report(_issue("unresolved path"))

    monkeypatch.setattr(analyzer_module, "validate_icf_entries_against_program", fake_validate)

    report = analyzer_module.analyze_icf_configuration(None, config=_config(icf_dir=str(icf_dir)))

    assert sorted(seen_programs) == ["ProgramA", "ProgramB"]
    assert len(report.issues) == 2
    assert report.issues[0].kind == "icf.unresolved_path"
    assert report.issues[0].module_path == ["ProgramA"]
    assert report.issues[1].module_path == ["ProgramB"]


def test_reuses_in_memory_program_when_matching(monkeypatch) -> None:
    icf_dir = Path("/tmp/icf")
    f1 = icf_dir / "ProgramA.icf"
    monkeypatch.setattr(analyzer_module, "configured_icf_files", lambda config: (icf_dir, [f1]))
    monkeypatch.setattr(analyzer_module, "parse_icf_file", lambda path: [_entry()])
    monkeypatch.setattr(analyzer_module, "merge_project_basepicture", lambda bp, graph: bp)

    def _should_not_load(cfg, name):
        raise AssertionError("load_program_ast should not be called when the program is already in memory")

    monkeypatch.setattr(analyzer_module, "load_program_ast", _should_not_load)
    monkeypatch.setattr(
        analyzer_module,
        "validate_icf_entries_against_program",
        lambda bp, entries, *, expected_program, debug=False, moduletype_index=None: _report(
            _issue("program mismatch")
        ),
    )

    report = analyzer_module.analyze_icf_configuration(_base_picture("ProgramA"), config=_config(icf_dir=str(icf_dir)))

    assert len(report.issues) == 1
    assert report.issues[0].kind == "icf.program_mismatch"


def test_load_failure_emits_program_load_failed(monkeypatch) -> None:
    icf_dir = Path("/tmp/icf")
    f1 = icf_dir / "ProgramA.icf"
    monkeypatch.setattr(analyzer_module, "configured_icf_files", lambda config: (icf_dir, [f1]))
    monkeypatch.setattr(analyzer_module, "parse_icf_file", lambda path: [_entry()])
    monkeypatch.setattr(
        analyzer_module, "load_program_ast", lambda cfg, name: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    report = analyzer_module.analyze_icf_configuration(None, config=_config(icf_dir=str(icf_dir)))

    assert len(report.issues) == 1
    assert report.issues[0].kind == "icf.program_load_failed"
    assert report.issues[0].module_path == ["ProgramA"]


def test_no_config_returns_empty_report() -> None:
    report = analyzer_module.analyze_icf_configuration(None, config=None)
    assert report.issues == []


def test_icf_is_registered_and_selectable() -> None:
    assert "icf" in DEFAULT_CLI_ANALYZER_KEYS
    assert any(spec.key == "icf" for spec in get_selectable_analyzers())

    catalog = get_default_analyzer_catalog()
    icf_analyzers = [analyzer for analyzer in catalog.analyzers if analyzer.spec.key == "icf"]
    assert len(icf_analyzers) == 1
    assert icf_analyzers[0].spec.category == "correctness"
