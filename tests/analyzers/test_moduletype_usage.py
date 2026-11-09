# pyright: reportPrivateUsage=false
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Literal, cast

import pytest
from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)

from sattlint.analyzers.catalog import get_selectable_analyzers
from sattlint.analyzers.framework import AnalysisContext
from sattlint.analyzers.moduletype_usage import analyze_moduletype_usage
from sattlint.analyzers.registry import DEFAULT_CLI_ANALYZER_KEYS
from sattlint.application.findings import extract_report_findings, kind_human_label
from sattlint.config import DEFAULT_CONFIG, ConfigDict
from sattlint.models.project_graph import ProjectGraph
from sattlint.project.loading_support import _include_reverse_library_consumers


def _header(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _definition() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="Equipment",
        datecode=1,
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        origin_file="EquipmentLib.s",
        origin_lib="EquipmentLib",
    )


def _instance(name: str) -> ModuleTypeInstance:
    return ModuleTypeInstance(
        header=_header(name),
        moduletype_name="Equipment",
        parametermappings=[],
    )


def _picture(
    name: str = "EquipmentLib",
    definitions: list[ModuleTypeDef] | None = None,
    instances: Sequence[SingleModule | ModuleTypeInstance | FrameModule] | None = None,
) -> BasePicture:
    return BasePicture(
        header=_header(name),
        datatype_defs=[],
        moduletype_defs=[_definition()] if definitions is None else definitions,
        localvariables=[],
        submodules=[_instance("LibraryInstance")] if instances is None else list(instances),
        modulecode=None,
        moduledef=None,
        origin_file=f"{name}.s",
        origin_lib=name,
    )


@pytest.mark.parametrize("has_program_invocation", [False, True])
def test_module_type_usage_distinguishes_library_instance_from_consumer(has_program_invocation: bool) -> None:
    instances: list[SingleModule | FrameModule | ModuleTypeInstance] = [_instance("LibraryInstance")]
    if has_program_invocation:
        instances.append(_instance("ProgramInstance"))
    picture = BasePicture(
        header=_header("EquipmentLib"),
        datatype_defs=[],
        moduletype_defs=[_definition()],
        localvariables=[],
        submodules=instances,
        modulecode=None,
        moduledef=None,
        origin_file="EquipmentLib.s",
        origin_lib="EquipmentLib",
    )

    report = analyze_moduletype_usage(picture, analyzed_target_is_library=True)

    assert len(report.issues) == (0 if has_program_invocation else 1)
    if not has_program_invocation:
        assert report.issues[0].module_path == ["EquipmentLib", "LibraryInstance"]
        assert "Equipment" in report.issues[0].message


def test_module_type_usage_counts_consumer_graph_invocations() -> None:
    library = _picture()
    consumer = _picture("Consumer", definitions=[], instances=[_instance("EquipmentInstance")])
    graph = ProjectGraph(ast_by_name={"EquipmentLib": library, "Consumer": consumer})

    report = analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True))

    assert report.issues == []
    assert "No unused module types found." in report.summary()


def test_module_type_usage_deduplicates_library_ast_copies() -> None:
    library = _picture()
    graph = ProjectGraph(ast_by_name={"EquipmentLib": library, "RepeatedDependency": deepcopy(library)})

    report = analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True))

    assert len(report.issues) == 1
    assert report.issues[0].data is not None
    assert report.issues[0].data["invocation_count"] == 1
    assert "Equipment" in report.summary()


def test_module_type_usage_keeps_same_named_library_types_separate() -> None:
    library = _picture()
    other_definition = replace(_definition(), origin_file="OtherLib.s", origin_lib="OtherLib")
    other_library = _picture("OtherLib", definitions=[other_definition])
    consumer = _picture("Consumer", definitions=[], instances=[_instance("OtherEquipment")])
    consumer.library_dependencies = {"consumer": ["OtherLib"]}
    graph = ProjectGraph(ast_by_name={"EquipmentLib": library, "OtherLib": other_library, "Consumer": consumer})

    report = analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True))

    assert len(report.issues) == 1
    assert report.issues[0].data is not None
    assert report.issues[0].data["origin_library"] == "EquipmentLib"


def test_module_type_usage_counts_case_insensitive_nested_invocations() -> None:
    library = _picture()
    frame = FrameModule(header=_header("Plant"), submodules=[replace(_instance("Unit"), moduletype_name="equipment")])
    consumer = _picture("Consumer", definitions=[], instances=[frame])
    graph = ProjectGraph(ast_by_name={"Consumer": consumer})

    assert analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True)).issues == []


def test_module_type_usage_counts_invocations_in_other_type_bodies() -> None:
    wrapper = replace(_definition(), name="Wrapper", submodules=[_instance("NestedEquipment")])
    library = _picture(definitions=[_definition(), wrapper])

    report = analyze_moduletype_usage(library, analyzed_target_is_library=True)

    assert len(report.issues) == 1
    assert "Wrapper" in report.issues[0].message
    assert "no invocations" in report.issues[0].message


def test_module_type_usage_does_not_report_single_program_invocation() -> None:
    assert analyze_moduletype_usage(_picture()).issues == []


def test_module_type_usage_rejects_incomplete_graph() -> None:
    library = _picture()
    graph = ProjectGraph(missing=["Consumer source is unavailable"])

    with pytest.raises(ValueError, match="incomplete"):
        analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True))


def test_module_type_usage_requires_project_graph_contract() -> None:
    library = _picture()

    with pytest.raises(TypeError, match="loaded project graph"):
        analyze_moduletype_usage(library, AnalysisContext(library, object()))


def test_module_type_usage_resolves_unknown_types_strictly() -> None:
    library = _picture(instances=[replace(_instance("Missing"), moduletype_name="MissingType")])

    with pytest.raises(ValueError, match="Unknown moduletype"):
        analyze_moduletype_usage(library, analyzed_target_is_library=True)


def test_module_type_usage_is_selectable_and_produces_readable_findings() -> None:
    library = _picture()
    spec = next(spec for spec in get_selectable_analyzers() if spec.key == "moduletype-usage")

    assert spec.key not in DEFAULT_CLI_ANALYZER_KEYS
    report = spec.run(AnalysisContext(library, target_is_library=True))
    findings = extract_report_findings(report, default_name="EquipmentLib")

    assert len(findings) == 1
    assert kind_human_label(findings[0].kind) == "Unused module type"
    assert findings[0].module_path == ("EquipmentLib", "LibraryInstance")


@pytest.mark.parametrize("has_consumer_invocation", [False, True])
@pytest.mark.parametrize("mode,suffix", [("draft", ".l"), ("official", ".z")])
def test_module_type_usage_scans_all_unselected_dependent_programs(
    tmp_path: Path, has_consumer_invocation: bool, mode: Literal["draft", "official"], suffix: str
) -> None:
    programs = tmp_path / "programs"
    programs.mkdir()
    for name in ("ConsumerA", "ConsumerB"):
        (programs / f"{name}{suffix}").write_text("equipmentlib\n", encoding="utf-8")
    (programs / f"Unrelated{suffix}").write_text("OtherLib\n", encoding="utf-8")
    library = _picture()
    graph = ProjectGraph(ast_by_name={"EquipmentLib": library})
    visits: list[str] = []
    cfg = cast(ConfigDict, deepcopy(DEFAULT_CONFIG))
    cfg["program_dir"] = str(programs)
    cfg["other_lib_dirs"] = []
    cfg["mode"] = mode
    cfg["analyzed_programs_and_libraries"] = ["EquipmentLib"]

    def read_dependencies(path: Path | None) -> list[str]:
        return [] if path is None else path.read_text(encoding="utf-8").splitlines()

    def visit_consumers(targets: list[tuple[str, Path | None]]) -> None:
        for name, directory in targets:
            assert directory == programs
            visits.append(name)
            instances = [_instance("UsedEquipment")] if name == "ConsumerB" and has_consumer_invocation else []
            graph.ast_by_name[name] = _picture(name, definitions=[], instances=instances)

    _include_reverse_library_consumers(
        cfg,
        selected_target="EquipmentLib",
        root_bp=library,
        graph=graph,
        find_dependency_path_fn=lambda _name, _directory: None,
        read_dependency_names_fn=read_dependencies,
        visit_targets_fn=visit_consumers,
        require_analyzed_targets_fn=lambda config: config["analyzed_programs_and_libraries"],
        is_within_directory_fn=lambda _path, _directory: False,
        target_is_library_fn=lambda *_args, **_kwargs: True,
        source_paths_for_current_target_fn=lambda _picture, _graph: set(),
    )
    spec = next(spec for spec in get_selectable_analyzers() if spec.key == "moduletype-usage")
    report = spec.run(AnalysisContext(library, graph, target_is_library=True))

    assert visits == ["ConsumerA", "ConsumerB"]
    assert len(report.issues) == (0 if has_consumer_invocation else 1)
