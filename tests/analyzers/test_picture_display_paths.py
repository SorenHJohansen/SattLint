from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    SourceSpan,
)
from sattlint.analyzers.picture_display_paths import analyze_picture_display_paths
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.models.project_graph import ProjectGraph
from sattlint.picture_display_paths import (
    PictureDisplayOccurrence,
    resolve_picture_display_path,
)
from tests.helpers.picture_display_paths_support import (
    base_picture_with_leading_dash_paths,
    base_picture_with_single_chain,
)

ROOT_PATH_STEP = "0"


def test_picture_display_path_analyzer_reports_unresolved_paths() -> None:
    base_picture = base_picture_with_single_chain()
    base_picture.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="Root",
            declaring_module_path=("Root",),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token=ROOT_PATH_STEP,
                        index_value=0,
                        kind="literal",
                        raw_text="+MissingPanel",
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    report = analyze_picture_display_paths(base_picture)

    assert len(report.issues) == 1
    assert report.issues[0].module_path == ["Root"]
    assert (
        report.issues[0].message == "PictureDisplay in module 'Root' path '+MissingPanel' could not be resolved: "
        "module 'MissingPanel' was not found under 'Root'"
    )


def test_picture_display_path_analyzer_ignores_resolved_paths() -> None:
    base_picture = base_picture_with_single_chain()
    base_picture.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="Root",
            declaring_module_path=("Root",),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token=ROOT_PATH_STEP,
                        index_value=0,
                        kind="literal",
                        raw_text="++Panel",
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    report = analyze_picture_display_paths(base_picture)

    assert report.issues == []


def test_resolve_picture_display_path_treats_single_plus_as_named_child_step() -> None:
    panel = SingleModule(
        header=ModuleHeader(name="Panel", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
    )
    l2 = SingleModule(
        header=ModuleHeader(name="L2", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
        submodules=[panel],
    )
    l1 = SingleModule(
        header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
        submodules=[l2],
    )
    base_picture = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        moduledef=ModuleDef(),
        submodules=[l1],
    )

    resolution = resolve_picture_display_path(
        "+L2+Panel",
        base_picture=base_picture,
        declaring_module_path=("Root", "L1"),
    )

    assert resolution.ok is True
    assert resolution.resolved_module_path == ("Root", "L1", "L2", "Panel")


def test_resolve_picture_display_path_uses_extra_plus_for_implicit_descent() -> None:
    base_picture = base_picture_with_single_chain()

    resolution = resolve_picture_display_path(
        "++Panel",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is True
    assert resolution.resolved_module_path == ("Root", "L1", "Panel")


def test_resolve_picture_display_path_reports_unimplemented_wmf_asset() -> None:
    base_picture = base_picture_with_single_chain()

    resolution = resolve_picture_display_path(
        "scr:nne_blue_web.wmf",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is False
    assert resolution.failure_reason == "unimplemented_asset"
    assert resolution.detail == ".emf and .wmf resolution is not implemented"


def test_resolve_picture_display_path_reports_unimplemented_env_var_wmf_asset() -> None:
    base_picture = base_picture_with_single_chain()

    resolution = resolve_picture_display_path(
        "sg_pictures:nne_blue_web.wmf",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is False
    assert resolution.failure_reason == "unimplemented_asset"
    assert resolution.detail == ".emf and .wmf resolution is not implemented"


def test_resolve_picture_display_path_reports_unimplemented_emf_asset() -> None:
    base_picture = base_picture_with_single_chain()

    resolution = resolve_picture_display_path(
        "Novo Bull SattLine Background Color.emf",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is False
    assert resolution.failure_reason == "unimplemented_asset"
    assert resolution.detail == ".emf and .wmf resolution is not implemented"


def test_resolve_picture_display_path_keeps_local_moduletype_defs_when_graph_has_dependencies() -> None:
    panel = SingleModule(
        header=ModuleHeader(name="Panel", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
    )
    local_typedef = ModuleTypeDef(
        name="LocalType",
        moduledef=ModuleDef(),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(),
                submodules=[panel],
            )
        ],
        origin_lib="RootLib",
        origin_file="RootLib.s",
    )
    dependency_typedef = ModuleTypeDef(
        name="DependencyType",
        moduledef=ModuleDef(),
        origin_lib="DepLib",
        origin_file="DepLib.s",
    )
    base_picture = BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="BasePicture",
        moduledef=ModuleDef(),
        submodules=[
            ModuleTypeInstance(
                header=ModuleHeader(name="Instance", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduletype_name="LocalType",
            )
        ],
        moduletype_defs=[local_typedef],
        origin_lib="RootLib",
        origin_file="RootLib.s",
    )
    graph = ProjectGraph(
        moduletype_defs={
            ("deplib", "dependencytype", "deplib.s"): dependency_typedef,
        }
    )

    resolution = resolve_picture_display_path(
        "++Panel",
        base_picture=base_picture,
        declaring_module_path=("BasePicture", "Instance"),
        graph=graph,
    )

    assert resolution.ok is True
    assert resolution.resolved_module_path == ("BasePicture", "Instance", "L1", "Panel")


def test_resolve_picture_display_path_implicit_plus_uses_first_declared_child() -> None:
    inlet_outlet_steps = SingleModule(
        header=ModuleHeader(name="InletOutletSteps", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
    )
    logic = SingleModule(
        header=ModuleHeader(name="Logic", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(),
                submodules=[inlet_outlet_steps],
            )
        ],
    )
    startup_panel = SingleModule(
        header=ModuleHeader(name="StartupPanel", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
    )
    opr_frame = SingleModule(
        header=ModuleHeader(name="OprFrame", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="Produktion", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(),
                submodules=[
                    SingleModule(
                        header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                        moduledef=ModuleDef(),
                        submodules=[
                            SingleModule(
                                header=ModuleHeader(name="L2", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                                moduledef=ModuleDef(),
                                submodules=[logic],
                            )
                        ],
                    )
                ],
            )
        ],
    )
    operations = SingleModule(
        header=ModuleHeader(name="Operations", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="L2", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(),
                submodules=[opr_frame],
            ),
            startup_panel,
        ],
    )
    base_picture = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        moduledef=ModuleDef(),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="First", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(),
                submodules=[operations],
            )
        ],
    )

    resolution = resolve_picture_display_path(
        "++Operations++OprFrame+Produktion+++Logic++InletOutletSteps",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is True
    assert resolution.resolved_module_path == (
        "Root",
        "First",
        "Operations",
        "L2",
        "OprFrame",
        "Produktion",
        "L1",
        "L2",
        "Logic",
        "L1",
        "InletOutletSteps",
    )


def test_resolve_picture_display_path_leading_dash_reaches_sibling_branch() -> None:
    base_picture = base_picture_with_leading_dash_paths()

    resolution = resolve_picture_display_path(
        "-------UnitHold+Udkobling",
        base_picture=base_picture,
        declaring_module_path=(
            "BasePicture",
            "Soejle",
            "L1",
            "L2",
            "UnitControl",
            "L1",
            "L2",
            "Operations",
            "L2",
            "OprFrame",
            "Produktion",
            "L1",
            "L2",
            "Display",
            "L2",
        ),
    )

    assert resolution.ok is True
    assert resolution.resolved_module_path == (
        "BasePicture",
        "Soejle",
        "L1",
        "L2",
        "UnitControl",
        "L1",
        "L2",
        "UnitHold",
        "Udkobling",
    )


def test_resolve_picture_display_path_leading_dash_supports_followup_wildcard() -> None:
    base_picture = base_picture_with_leading_dash_paths()

    resolution = resolve_picture_display_path(
        "------CalculateVR_AS+AlarmsAndWarnings*Form",
        base_picture=base_picture,
        declaring_module_path=(
            "BasePicture",
            "Soejle",
            "L1",
            "L2",
            "UnitControl",
            "L1",
            "L2",
            "Operations",
            "L2",
            "OprFrame",
            "Produktion",
            "L1",
            "L2",
            "Displays",
            "L1",
            "L2",
            "AlarmDisp",
            "L1",
            "L2",
            "Form",
        ),
    )

    assert resolution.ok is True
    assert resolution.resolved_module_path == (
        "BasePicture",
        "Soejle",
        "L1",
        "L2",
        "UnitControl",
        "L1",
        "L2",
        "Operations",
        "L2",
        "OprFrame",
        "Produktion",
        "L1",
        "L2",
        "CalculateVR_AS",
        "AlarmsAndWarnings",
        "Form",
    )


def test_resolve_picture_display_path_single_dash_plus_climbs_to_parent_module() -> None:
    base_picture = BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="BasePicture",
        moduledef=ModuleDef(),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="XAppl_231XY", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(),
                submodules=[
                    SingleModule(
                        header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                        moduledef=ModuleDef(),
                        submodules=[
                            SingleModule(
                                header=ModuleHeader(name="L2", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                                moduledef=ModuleDef(),
                                submodules=[
                                    SingleModule(
                                        header=ModuleHeader(name="OpMessage1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                                        moduledef=ModuleDef(),
                                    ),
                                    SingleModule(
                                        header=ModuleHeader(name="UnitControl", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                                        moduledef=ModuleDef(),
                                        submodules=[
                                            SingleModule(
                                                header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                                                moduledef=ModuleDef(),
                                                submodules=[
                                                    SingleModule(
                                                        header=ModuleHeader(
                                                            name="L2", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)
                                                        ),
                                                        moduledef=ModuleDef(),
                                                        submodules=[
                                                            SingleModule(
                                                                header=ModuleHeader(
                                                                    name="Operations",
                                                                    invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0),
                                                                ),
                                                                moduledef=ModuleDef(),
                                                                submodules=[
                                                                    SingleModule(
                                                                        header=ModuleHeader(
                                                                            name="L2",
                                                                            invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0),
                                                                        ),
                                                                        moduledef=ModuleDef(),
                                                                        submodules=[
                                                                            SingleModule(
                                                                                header=ModuleHeader(
                                                                                    name="OpMessage",
                                                                                    invoke_coord=(
                                                                                        0.0,
                                                                                        0.0,
                                                                                        0.0,
                                                                                        1.0,
                                                                                        1.0,
                                                                                    ),
                                                                                ),
                                                                                moduledef=ModuleDef(),
                                                                                submodules=[
                                                                                    SingleModule(
                                                                                        header=ModuleHeader(
                                                                                            name="L1",
                                                                                            invoke_coord=(
                                                                                                0.0,
                                                                                                0.0,
                                                                                                0.0,
                                                                                                1.0,
                                                                                                1.0,
                                                                                            ),
                                                                                        ),
                                                                                        moduledef=ModuleDef(),
                                                                                        submodules=[
                                                                                            SingleModule(
                                                                                                header=ModuleHeader(
                                                                                                    name="L2",
                                                                                                    invoke_coord=(
                                                                                                        0.0,
                                                                                                        0.0,
                                                                                                        0.0,
                                                                                                        1.0,
                                                                                                        1.0,
                                                                                                    ),
                                                                                                ),
                                                                                                moduledef=ModuleDef(),
                                                                                                submodules=[
                                                                                                    SingleModule(
                                                                                                        header=ModuleHeader(
                                                                                                            name="OperatorMessage1",
                                                                                                            invoke_coord=(
                                                                                                                0.0,
                                                                                                                0.0,
                                                                                                                0.0,
                                                                                                                1.0,
                                                                                                                1.0,
                                                                                                            ),
                                                                                                        ),
                                                                                                        moduledef=ModuleDef(),
                                                                                                    )
                                                                                                ],
                                                                                            )
                                                                                        ],
                                                                                    )
                                                                                ],
                                                                            )
                                                                        ],
                                                                    )
                                                                ],
                                                            )
                                                        ],
                                                    )
                                                ],
                                            )
                                        ],
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    )

    resolution = resolve_picture_display_path(
        "-+UnitControl+l1+l2+Operations+l2+Opmessage+l1+l2+Operatormessage1",
        base_picture=base_picture,
        declaring_module_path=("BasePicture", "XAppl_231XY", "L1", "L2", "OpMessage1"),
    )

    assert resolution.ok is True
    assert resolution.resolved_module_path == (
        "BasePicture",
        "XAppl_231XY",
        "L1",
        "L2",
        "UnitControl",
        "L1",
        "L2",
        "Operations",
        "L2",
        "OpMessage",
        "L1",
        "L2",
        "OperatorMessage1",
    )
