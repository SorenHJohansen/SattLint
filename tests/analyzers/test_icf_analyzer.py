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
    get_default_analyzer_catalog,
    get_selectable_analyzer_keys,
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


def _patch_icf_inputs(
    monkeypatch: pytest.MonkeyPatch,
    icf_dir: Path,
    programs_by_file: dict[Path, list[str]],
) -> None:
    def _configured(_config: ConfigDict) -> tuple[Path | None, list[Path]]:
        return icf_dir, list(programs_by_file)

    def _parsed(path: Path) -> list[ICFEntry]:
        return [
            _entry(line=line, value=f"{program}:Module.Var{line}")
            for line, program in enumerate(programs_by_file[path], start=1)
        ]

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
    seen: list[tuple[str, list[str]]] | None = None,
) -> None:
    def _validate(
        _base_picture: BasePicture,
        entries: list[ICFEntry],
        *,
        expected_program: str,
        debug: bool = False,
        moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    ) -> ICFValidationReport:
        del debug, moduletype_index
        if seen is not None:
            seen.append((expected_program, [entry.value for entry in entries]))
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


def test_issue_message_uses_the_first_detail_line() -> None:
    assert analyzer_module._issue_message(_issue("unresolved path")) == "Program.icf:3: unresolved path"
    assert analyzer_module._issue_message(_issue("unresolved path", "  \n  ")) == "Program.icf:3: unresolved path"
    assert (
        analyzer_module._issue_message(_issue("unresolved path", "  first line\nsecond line"))
        == "Program.icf:3: unresolved path: first line"
    )


def test_analyzes_all_configured_icf_files(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    f2 = icf_dir / "ProgramB.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA"], f2: ["ProgramB"]})
    _patch_merge(monkeypatch)

    seen: list[tuple[str, list[str]]] = []
    _patch_validation(monkeypatch, _report(_issue("unresolved path")), seen=seen)

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_loader,
    )

    assert sorted(program for program, _entries in seen) == ["ProgramA", "ProgramB"]
    assert len(report.issues) == 2
    assert report.issues[0].kind == "icf.unresolved_path"
    assert report.issues[0].module_path == ["ProgramA"]
    assert report.issues[1].module_path == ["ProgramB"]


def test_program_identity_comes_from_entries_not_the_file_name(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    channel_config = icf_dir / "KaHCBSolvent.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {channel_config: ["KaHCBZAMix", "KaHCBZASto"]})
    _patch_merge(monkeypatch)
    _patch_validation(monkeypatch, _report())

    loaded: list[str] = []

    def _counting_loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg
        loaded.append(program_name)
        return _base_picture(program_name), _graph()

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_counting_loader,
    )

    assert loaded == ["KaHCBZAMix", "KaHCBZASto"]
    assert not any(issue.kind == "icf.program_load_failed" for issue in report.issues)


def test_validates_each_program_against_only_its_own_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    multi_program = icf_dir / "Channel.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {multi_program: ["ProgramA", "ProgramB", "ProgramA"]})
    _patch_merge(monkeypatch)

    seen: list[tuple[str, list[str]]] = []
    _patch_validation(monkeypatch, _report(), seen=seen)

    analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_loader,
    )

    assert seen == [
        ("ProgramA", ["ProgramA:Module.Var1", "ProgramA:Module.Var3"]),
        ("ProgramB", ["ProgramB:Module.Var2"]),
    ]


def test_icf_file_without_a_referenced_program_is_not_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    unbound = icf_dir / "Unbound.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {unbound: []})
    _patch_validation(monkeypatch, _report(_issue("unresolved path")))

    def _should_not_load(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg, program_name
        raise AssertionError("an .icf file with no referenced program must not load anything")

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_should_not_load,
    )

    assert report.issues == []


def test_placeholder_only_entries_are_not_a_program_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    unbound = icf_dir / "Unbound.icf"

    def _configured(_config: ConfigDict) -> tuple[Path | None, list[Path]]:
        return icf_dir, [unbound]

    def _parsed(_path: Path) -> list[ICFEntry]:
        return [_entry(value="H::."), _entry(line=4, value="free text without a reference")]

    monkeypatch.setattr(analyzer_module, "configured_icf_files", _configured)
    monkeypatch.setattr(analyzer_module, "parse_icf_file", _parsed)

    def _should_not_load(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg, program_name
        raise AssertionError("a placeholder is not a program reference")

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_should_not_load,
    )

    assert report.issues == []


def test_program_identity_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["KaHCBZAMix", "kahcbzamix"]})
    _patch_merge(monkeypatch)

    seen: list[tuple[str, list[str]]] = []
    _patch_validation(monkeypatch, _report(), seen=seen)

    loaded: list[str] = []

    def _counting_loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg
        loaded.append(program_name)
        return _base_picture(program_name), _graph()

    analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_counting_loader,
    )

    assert loaded == ["KaHCBZAMix"]
    assert seen == [("KaHCBZAMix", ["KaHCBZAMix:Module.Var1", "kahcbzamix:Module.Var2"])]


def test_reuses_in_memory_program_when_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA"]})
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
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA"]})

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
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA"]})

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_parser_rejecting_loader,
    )

    assert len(report.issues) == 1
    assert report.issues[0].kind == "icf.program_load_failed"
    assert report.issues[0].module_path == ["ProgramA"]


def test_one_load_failure_does_not_hide_the_other_referenced_programs(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA", "Missing"]})
    _patch_merge(monkeypatch)
    _patch_validation(monkeypatch, _report(_issue("unresolved path")))

    def _partial_loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg
        if program_name == "Missing":
            raise ProjectLoadError(program_name, "missing code file")
        return _base_picture(program_name), _graph()

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_partial_loader,
    )

    kinds = sorted(issue.kind for issue in report.issues)
    assert kinds == ["icf.program_load_failed", "icf.unresolved_path"]
    load_failures = [issue for issue in report.issues if issue.kind == "icf.program_load_failed"]
    assert [issue.module_path for issue in load_failures] == [["Missing"]]


def test_program_is_loaded_once_across_files(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "First.icf"
    f2 = icf_dir / "Second.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA"], f2: ["ProgramA"]})
    _patch_merge(monkeypatch)

    seen: list[tuple[str, list[str]]] = []
    _patch_validation(monkeypatch, _report(), seen=seen)

    loaded: list[str] = []

    def _counting_loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg
        loaded.append(program_name)
        return _base_picture(program_name), _graph()

    analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_counting_loader,
    )

    assert loaded == ["ProgramA"]
    assert [program for program, _entries in seen] == ["ProgramA", "ProgramA"]


def test_requires_a_program_loader_for_referenced_programs(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA"]})

    with pytest.raises(RuntimeError, match="program loader"):
        analyzer_module.analyze_icf_configuration(None, config=_config(icf_dir=str(icf_dir)))


def test_registry_passes_the_context_program_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA"]})
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


def test_no_configured_icf_files_returns_empty_report(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    _patch_icf_inputs(monkeypatch, icf_dir, {})

    def _should_not_load(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg, program_name
        raise AssertionError("no ICF files means nothing to load")

    report = analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_should_not_load,
    )

    assert report.issues == []


def test_loaded_graph_moduletypes_reach_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    icf_dir = Path("icf")
    f1 = icf_dir / "ProgramA.icf"
    _patch_icf_inputs(monkeypatch, icf_dir, {f1: ["ProgramA"]})

    moduletype = ModuleTypeDef(name="TankType", localvariables=[])
    picture = _base_picture("ProgramA")
    picture.moduletype_defs = [moduletype]

    def _graph_loader(cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        del cfg
        return picture, ProjectGraph(ast_by_name={program_name: picture})

    seen_indexes: list[dict[str, list[ModuleTypeDef]] | None] = []

    def _validate(
        _base_picture_arg: BasePicture,
        _entries: list[ICFEntry],
        *,
        expected_program: str,
        debug: bool = False,
        moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    ) -> ICFValidationReport:
        del expected_program, debug
        seen_indexes.append(moduletype_index)
        return _report()

    monkeypatch.setattr(analyzer_module, "validate_icf_entries_against_program", _validate)

    analyzer_module.analyze_icf_configuration(
        None,
        config=_config(icf_dir=str(icf_dir)),
        program_ast_loader=_graph_loader,
    )

    assert seen_indexes == [{"tanktype": [moduletype]}]


def test_icf_is_registered_and_selectable() -> None:
    assert "icf" in get_selectable_analyzer_keys()
    assert any(spec.key == "icf" for spec in get_selectable_analyzers())

    catalog = get_default_analyzer_catalog()
    icf_analyzers = [analyzer for analyzer in catalog.analyzers if analyzer.spec.key == "icf"]
    assert len(icf_analyzers) == 1
    assert icf_analyzers[0].spec.category == "correctness"
