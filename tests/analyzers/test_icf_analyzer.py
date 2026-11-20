# These tests deliberately exercise private analyzer seams.
# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from sattline_parser.models.ast_model import BasePicture, ModuleHeader, ModuleTypeDef
from sattline_parser.project import ProjectLoadError

import sattlint.analyzers.icf.analyzer as analyzer_module
from sattlint.analyzers.framework import build_analysis_context
from sattlint.analyzers.registry import (
    DEFAULT_CLI_ANALYZER_KEYS,
    get_default_analyzer_catalog,
    get_selectable_analyzers,
)
from sattlint.config.types import ConfigDict
from sattlint.models.project_graph import ProjectGraph
from sattlint.reporting.icf_report import ICFEntry, ICFValidationIssue, ICFValidationReport


def _config(**overrides: object) -> ConfigDict:
    return cast(ConfigDict, {"icf_dir": "icf", **overrides})


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


def _graph() -> ProjectGraph:
    return ProjectGraph()


def _loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
    del cfg
    return _base_picture(program_name), _graph()


def _failing_loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
    del cfg, program_name
    raise RuntimeError("boom")


def _parser_rejecting_loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
    del cfg
    raise ProjectLoadError(program_name, "missing code file")


def _base_picture(name: str = "Program") -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        program_name=name,
    )


def _patch_icf_inputs(monkeypatch: pytest.MonkeyPatch, icf_dir: Path, files: list[Path]) -> None:
    def _configured(_config: ConfigDict) -> tuple[Path | None, list[Path]]:
        return icf_dir, files

    def _parsed(_path: Path) -> list[ICFEntry]:
        return [_entry()]

    monkeypatch.setattr(analyzer_module, "configured_icf_files", _configured)
    monkeypatch.setattr(analyzer_module, "parse_icf_file", _parsed)


def _patch_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    def _merge(base_picture: BasePicture, _graph: ProjectGraph) -> BasePicture:
        return base_picture

    monkeypatch.setattr(analyzer_module, "merge_project_basepicture", _merge)


def _patch_validation(
    monkeypatch: pytest.MonkeyPatch,
    report: ICFValidationReport,
    *,
    seen_programs: list[str] | None = None,
) -> None:
    def _validate(
        _base_picture: BasePicture,
        _entries: list[ICFEntry],
        *,
        expected_program: str,
        debug: bool = False,
        moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    ) -> ICFValidationReport:
        del debug, moduletype_index
        if seen_programs is not None:
            seen_programs.append(expected_program)
        return report

    monkeypatch.setattr(analyzer_module, "validate_icf_entries_against_program", _validate)


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


def test_analyzes_all_configured_icf_files(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    f2 = icf_dir / "ProgramB.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, [f1, f2])
    _patch_merge(monkeypatch)

    seen_programs: list[str] = []
    _patch_validation(monkeypatch, _report(_issue("unresolved path")), seen_programs=seen_programs)

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_loader,
    )

    assert sorted(seen_programs) == ["ProgramA", "ProgramB"]
    assert len(report.issues) == 2
    assert report.issues[0].kind == "icf.unresolved_path"
    assert report.issues[0].module_path == ["ProgramA"]
    assert report.issues[1].module_path == ["ProgramB"]


def test_reuses_in_memory_program_when_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, [f1])
    _patch_merge(monkeypatch)

    def _should_not_load(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg, program_name
        raise AssertionError("the loader must not run when the program is already in memory")

    _patch_validation(monkeypatch, _report(_issue("program mismatch")))

    report = analyzer_module.analyze_icf_configuration(
        _base_picture("ProgramA"),
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_should_not_load,
    )

    assert len(report.issues) == 1
    assert report.issues[0].kind == "icf.program_mismatch"


def test_load_failure_emits_program_load_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, [f1])

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_failing_loader,
    )

    assert len(report.issues) == 1
    assert report.issues[0].kind == "icf.program_load_failed"
    assert report.issues[0].module_path == ["ProgramA"]


def test_parser_load_error_emits_program_load_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, [f1])

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_parser_rejecting_loader,
    )

    assert len(report.issues) == 1
    assert report.issues[0].kind == "icf.program_load_failed"
    assert report.issues[0].module_path == ["ProgramA"]


def test_requires_a_program_loader_for_referenced_programs(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, [f1])

    with pytest.raises(RuntimeError, match="program loader"):
        analyzer_module.analyze_icf_configuration(None, config=_config(icf_dir=str(icf_dir)))


def test_registry_passes_the_context_program_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, [f1])
    _patch_merge(monkeypatch)
    _patch_validation(monkeypatch, _report())

    loaded: list[str] = []

    def fake_loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg
        loaded.append(program_name)
        return _base_picture(program_name), _graph()

    spec = next(analyzer.spec for analyzer in get_default_analyzer_catalog().analyzers if analyzer.spec.key == "icf")
    context = build_analysis_context(
        cast(BasePicture, None),
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=fake_loader,
    )

    report = spec.run(context)

    assert loaded == ["ProgramA"]
    assert report.issues == []


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
