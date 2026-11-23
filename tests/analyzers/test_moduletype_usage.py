# These tests deliberately exercise private analyzer seams.
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

from sattlint.analyzers.catalog import get_selectable_analyzer_keys, get_selectable_analyzers
from sattlint.analyzers.framework import AnalysisContext
from sattlint.analyzers.moduletype_usage import analyze_moduletype_usage
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
        moduleparameters=[],
        localvariables=[],
        submodules=[],
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
        origin_file=f"{name}.s",
        origin_lib=name,
    )


def _stop_drain_instance(name: str) -> ModuleTypeInstance:
    return ModuleTypeInstance(
        header=_header(name),
        moduletype_name="Stop_Drain",
        parametermappings=[],
    )


def test_same_library_duplicate_type_names_resolve_by_declaring_file() -> None:
    local_definition = ModuleTypeDef(
        name="Stop_Drain",
        datecode=1,
        origin_file="DiluteLib.s",
        origin_lib="ProjectLib",
    )
    private_definition = ModuleTypeDef(
        name="Stop_Drain",
        datecode=2,
        is_private=True,
        origin_file="CIPXLib.x",
        origin_lib="ProjectLib",
    )
    public_definition = ModuleTypeDef(
        name="Stop_Drain",
        datecode=3,
        origin_file="ModullLib.x",
        origin_lib="ProjectLib",
    )
    library = BasePicture(
        header=_header("DiluteLib"),
        moduletype_defs=[local_definition],
        submodules=[_stop_drain_instance("Local")],
        origin_file="DiluteLib.s",
        origin_lib="ProjectLib",
    )
    consumer = BasePicture(
        header=_header("CIPXLib"),
        moduletype_defs=[private_definition, public_definition],
        submodules=[_stop_drain_instance("Uses")],
        origin_file="CIPXLib.x",
        origin_lib="ProjectLib",
    )
    graph = ProjectGraph(ast_by_name={"DiluteLib": library, "CIPXLib": consumer})
    graph.source_dependencies["cipxlib"] = {"modullib"}

    report = analyze_moduletype_usage(
        library,
        AnalysisContext(library, graph, target_is_library=True),
    )

    # Each file's invocation resolves to its own declaration instead of
    # raising an ambiguity error across the shared library folder.
    assert len(report.issues) == 1
    assert "Stop_Drain" in report.issues[0].message


@pytest.mark.parametrize("analyzed_target_is_library", [False, True])
def test_module_type_usage_suppresses_an_in_file_only_type_with_a_consumer(
    analyzed_target_is_library: bool,
) -> None:
    # The library instantiates its own type; that is not external use. Its
    # exporting contract is what matters, and the importing consumer supplies it.
    library = _picture()
    consumer = _picture("Consumer", definitions=[], instances=[])
    graph = ProjectGraph(
        ast_by_name={"EquipmentLib": library, "Consumer": consumer},
        source_dependencies={"consumer": {"equipmentlib"}},
    )

    report = analyze_moduletype_usage(
        library,
        AnalysisContext(library, graph, target_is_library=analyzed_target_is_library),
    )

    # Program/library classification is irrelevant: the consumer decides.
    assert report.issues == []


def test_module_type_usage_reports_an_in_file_only_type_without_a_consumer() -> None:
    library = _picture()
    graph = ProjectGraph(ast_by_name={"EquipmentLib": library})

    report = analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True))

    assert len(report.issues) == 1
    assert report.issues[0].module_path == ["EquipmentLib", "LibraryInstance"]
    assert "Equipment" in report.issues[0].message
    assert "declaring unit 'EquipmentLib.s'" in report.issues[0].message


def test_module_type_usage_external_invocation_is_a_use() -> None:
    library = _picture()
    consumer = _picture("Consumer", definitions=[], instances=[_instance("ProgramInstance")])
    graph = ProjectGraph(ast_by_name={"EquipmentLib": library, "Consumer": consumer})

    assert analyze_moduletype_usage(library, AnalysisContext(library, graph)).issues == []


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
    graph = ProjectGraph(
        ast_by_name={"EquipmentLib": library, "OtherLib": other_library, "Consumer": consumer},
        library_dependencies={"consumer": {"otherlib"}},
    )

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


def test_module_type_usage_counts_invocations_in_another_units_type_body() -> None:
    # A consumer imports a library whose module type instantiates Equipment.
    # The invocation lives one hop away from the consuming program, so the
    # search has to look inside the module types that consumer imports.
    wrapper = ModuleTypeDef(
        name="Wrapper",
        datecode=1,
        submodules=[_instance("NestedEquipment")],
        origin_file="ConsumerLib.s",
        origin_lib="ConsumerLib",
    )
    library = _picture()
    consumer_library = _picture("ConsumerLib", definitions=[wrapper], instances=[])
    graph = ProjectGraph(
        ast_by_name={"EquipmentLib": library, "ConsumerLib": consumer_library},
        source_dependencies={"consumerlib": {"equipmentlib"}},
    )

    report = analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True))

    assert report.issues == []
    assert "No unused module types found." in report.summary()


def test_module_type_usage_ignores_in_file_uses_in_another_type_body() -> None:
    # A type used only by a sibling type in the same file is still reachable
    # only from within its declaring unit, so it has no audience of its own.
    wrapper = replace(_definition(), name="Wrapper", submodules=[_instance("NestedEquipment")])
    library = _picture(definitions=[_definition(), wrapper])

    report = analyze_moduletype_usage(library, analyzed_target_is_library=True)

    messages = sorted(issue.message for issue in report.issues)
    assert len(messages) == 2
    assert "Equipment" in messages[0] and "no consumer in the scanned workspace" in messages[0]
    assert "Wrapper" in messages[1] and "no invocations" in messages[1]


def test_module_type_usage_never_reports_a_private_definition() -> None:
    # PRIVATE_ states the contract: file scope only, so no consumer exists and
    # none is required.
    private_definition = ModuleTypeDef(
        name="PRIVATE_Helper",
        datecode=1,
        is_private=True,
        submodules=[],
        origin_file="EquipmentLib.s",
        origin_lib="EquipmentLib",
    )
    library = _picture(definitions=[_definition(), private_definition], instances=[])

    report = analyze_moduletype_usage(library, analyzed_target_is_library=True)

    assert len(report.issues) == 1
    assert "Equipment" in report.issues[0].message
    assert all("PRIVATE_Helper" not in issue.message for issue in report.issues)


def test_module_type_usage_reports_in_file_use_regardless_of_target_kind() -> None:
    # The only invocation is the declaring file instantiating its own type.
    assert len(analyze_moduletype_usage(_picture()).issues) == 1
    assert len(analyze_moduletype_usage(_picture(), analyzed_target_is_library=True).issues) == 1


def test_module_type_usage_rejects_incomplete_graph() -> None:
    library = _picture()
    graph = ProjectGraph(missing=["Consumer source is unavailable"])

    with pytest.raises(ValueError, match="incomplete"):
        analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True))


def test_module_type_usage_ignores_missing_downstream_source() -> None:
    library = _picture()
    dependency = _picture(
        "ConfigurationLib",
        definitions=[],
        instances=[replace(_instance("Controller"), moduletype_name="Controller")],
    )
    graph = ProjectGraph(
        ast_by_name={"EquipmentLib": library, "ConfigurationLib": dependency},
        source_dependencies={"equipmentlib": {"configurationlib"}, "configurationlib": {"controllib"}},
        unavailable_libraries={"controllib"},
        missing=["Dependent source is unavailable"],
    )

    report = analyze_moduletype_usage(library, AnalysisContext(library, graph, target_is_library=True))

    assert len(report.issues) == 1


def test_module_type_usage_still_rejects_missing_consumer_source() -> None:
    library = _picture()
    graph = ProjectGraph(
        source_dependencies={"consumer": {"equipmentlib"}},
        unavailable_libraries={"consumer"},
        missing=["Consumer source is unavailable"],
    )

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

    assert spec.key in get_selectable_analyzer_keys()
    report = spec.run(AnalysisContext(library, target_is_library=True))
    findings = extract_report_findings(report, default_name="EquipmentLib")

    assert len(findings) == 1
    assert kind_human_label(findings[0].kind) == "Unused module type"
    assert findings[0].module_path == ("EquipmentLib", "LibraryInstance")


@pytest.mark.parametrize("mode,suffix", [("draft", ".l"), ("official", ".z")])
def test_module_type_usage_loads_transitive_consumers_including_the_abb_root(
    tmp_path: Path, mode: Literal["draft", "official"], suffix: str
) -> None:
    programs = tmp_path / "programs"
    abb_lib = tmp_path / "abb"
    programs.mkdir()
    abb_lib.mkdir()
    (programs / f"ConsumerA{suffix}").write_text("equipmentlib\n", encoding="utf-8")
    (programs / f"ConsumerB{suffix}").write_text("ConsumerA\n", encoding="utf-8")
    (programs / f"Unrelated{suffix}").write_text("OtherLib\n", encoding="utf-8")
    (abb_lib / f"AbbConsumer{suffix}").write_text("equipmentlib\n", encoding="utf-8")
    library = _picture()
    graph = ProjectGraph(ast_by_name={"EquipmentLib": library})
    visits: list[tuple[str, Path]] = []
    cfg = cast(ConfigDict, deepcopy(DEFAULT_CONFIG))
    cfg["program_dir"] = str(programs)
    cfg["ABB_lib_dir"] = str(abb_lib)
    cfg["other_lib_dirs"] = []
    cfg["mode"] = mode
    cfg["analyzed_programs_and_libraries"] = ["EquipmentLib"]

    def read_dependencies(path: Path | None) -> list[str]:
        return [] if path is None else path.read_text(encoding="utf-8").splitlines()

    def visit_consumers(targets: list[tuple[str, Path | None]]) -> None:
        for name, directory in targets:
            assert directory is not None
            visits.append((name, directory))
            deps_path = directory / f"{name}{suffix}"
            graph.source_dependencies[name.casefold()] = {
                line.strip().casefold() for line in deps_path.read_text(encoding="utf-8").splitlines() if line.strip()
            }
            graph.ast_by_name[name] = _picture(name, definitions=[], instances=[])

    _include_reverse_library_consumers(
        cfg,
        selected_target="EquipmentLib",
        root_bp=library,
        graph=graph,
        find_dependency_path_fn=lambda _name: None,
        read_dependency_names_fn=read_dependencies,
        visit_targets_fn=visit_consumers,
        require_analyzed_targets_fn=lambda config: config["analyzed_programs_and_libraries"],
    )
    spec = next(spec for spec in get_selectable_analyzers() if spec.key == "moduletype-usage")
    report = spec.run(AnalysisContext(library, graph, target_is_library=True))

    # ConsumerA and AbbConsumer import the target directly; ConsumerB reaches it
    # through ConsumerA, so the closure pulls it in too. Unrelated is ignored.
    assert sorted(visits) == [
        ("AbbConsumer", abb_lib),
        ("ConsumerA", programs),
        ("ConsumerB", programs),
    ]
    # The declaring unit has consumers, so its in-file-only type is exported API.
    assert report.issues == []


@pytest.mark.parametrize("invocations", [0, 1, 2])
def test_in_file_invocations_never_count_as_a_consumer(invocations: int) -> None:
    library = _picture(
        instances=[_instance(f"LibraryInstance{index}") for index in range(invocations)],
    )

    report = analyze_moduletype_usage(library)

    assert len(report.issues) == 1
    assert report.issues[0].data is not None
    assert report.issues[0].data["invocation_count"] == invocations


def test_a_single_invocation_from_another_file_means_the_type_is_used() -> None:
    library = _picture(instances=[])
    consumer = _picture("Consumer", definitions=[], instances=[_instance("ProgramInstance")])
    graph = ProjectGraph(ast_by_name={"EquipmentLib": library, "Consumer": consumer})

    assert analyze_moduletype_usage(library, AnalysisContext(library, graph)).issues == []
