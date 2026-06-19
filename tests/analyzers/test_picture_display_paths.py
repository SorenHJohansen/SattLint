from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint.analyzers.picture_display_paths import analyze_picture_display_paths
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.models.project_graph import ProjectGraph
from sattlint.picture_display_paths import (
    PictureDisplayOccurrence,
    resolve_picture_display_path,
)
from sattlint.string_inference import ExactStringInferenceEngine, StringProvenanceSegment
from tests.helpers.picture_display_paths_support import (
    base_picture_with_leading_dash_paths,
    base_picture_with_single_chain,
)

ROOT_PATH_STEP = "0"


def _varref(name: str) -> dict[str, str]:
    return {"var_name": name}


def _string_length_call(name: str) -> tuple[str, str, list[dict[str, str]]]:
    return (const.KEY_FUNCTION_CALL, "StringLength", [_varref(name)])


def _build_operation_path_base_picture() -> BasePicture:
    path_builder = ModuleTypeDef(
        name="PathBuilder",
        moduleparameters=[
            Variable(name="Prefix", datatype=Simple_DataType.STRING),
            Variable(name="Name", datatype=Simple_DataType.IDENTSTRING),
            Variable(name="Paths", datatype="PathsType"),
        ],
        localvariables=[Variable(name="BuilderStatus", datatype=Simple_DataType.INTEGER)],
        moduledef=ModuleDef(),
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_FUNCTION_CALL, "ClearString", [_varref("Paths.OperationPath")]),
                        (
                            const.KEY_FUNCTION_CALL,
                            "InsertString",
                            [
                                _varref("Paths.OperationPath"),
                                _varref("Prefix"),
                                _string_length_call("Prefix"),
                                _varref("BuilderStatus"),
                            ],
                        ),
                        (
                            const.KEY_FUNCTION_CALL,
                            "InsertString",
                            [
                                _varref("Paths.OperationPath"),
                                _varref("Name"),
                                _string_length_call("Name"),
                                _varref("BuilderStatus"),
                            ],
                        ),
                    ],
                )
            ]
        ),
    )

    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        moduledef=ModuleDef(),
        moduletype_defs=[path_builder],
        submodules=[
            SingleModule(
                header=ModuleHeader(name="UnitControl", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(),
                localvariables=[
                    Variable(name="Paths", datatype="PathsType"),
                    Variable(name="OprPath", datatype=Simple_DataType.STRING, init_value="+L2+Operations+L2*"),
                    Variable(
                        name="FyldOprName",
                        datatype=Simple_DataType.IDENTSTRING,
                        const=True,
                        init_value="FyldAppl",
                    ),
                ],
                submodules=[
                    ModuleTypeInstance(
                        header=ModuleHeader(name="Builder", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                        moduletype_name="PathBuilder",
                        parametermappings=[
                            ParameterMapping(
                                target=_varref("Prefix"),
                                source_type=const.TREE_TAG_VARIABLE_NAME,
                                is_duration=False,
                                is_source_global=False,
                                source=_varref("OprPath"),
                                source_literal=None,
                            ),
                            ParameterMapping(
                                target=_varref("Name"),
                                source_type=const.TREE_TAG_VARIABLE_NAME,
                                is_duration=False,
                                is_source_global=False,
                                source=_varref("FyldOprName"),
                                source_literal=None,
                            ),
                            ParameterMapping(
                                target=_varref("Paths"),
                                source_type=const.TREE_TAG_VARIABLE_NAME,
                                is_duration=False,
                                is_source_global=False,
                                source=_varref("Paths"),
                                source_literal=None,
                            ),
                        ],
                    )
                ],
            )
        ],
    )


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


def test_picture_display_path_analyzer_marks_library_target_findings_as_info() -> None:
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

    report = analyze_picture_display_paths(base_picture, analyzed_target_is_library=True)

    assert len(report.issues) == 1
    assert report.issues[0].severity == "info"


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


def test_picture_display_path_analyzer_reports_generic_variable_path_candidates() -> None:
    base_picture = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        moduledef=ModuleDef(),
        localvariables=[
            Variable(name="DisplayPath", datatype=Simple_DataType.STRING),
            Variable(name="Prefix", datatype=Simple_DataType.STRING, init_value="+"),
            Variable(name="PanelName", datatype=Simple_DataType.IDENTSTRING, init_value="MissingPanel"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_FUNCTION_CALL, "ClearString", [_varref("DisplayPath")]),
                        (
                            const.KEY_FUNCTION_CALL,
                            "InsertString",
                            [
                                _varref("DisplayPath"),
                                _varref("Prefix"),
                                _string_length_call("Prefix"),
                                _varref("Status"),
                            ],
                        ),
                        (
                            const.KEY_FUNCTION_CALL,
                            "InsertString",
                            [
                                _varref("DisplayPath"),
                                _varref("PanelName"),
                                _string_length_call("PanelName"),
                                _varref("Status"),
                            ],
                        ),
                    ],
                )
            ]
        ),
    )
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
                        index_token="1",
                        index_value=1,
                        kind="variable",
                        raw_text="DisplayPath",
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    report = analyze_picture_display_paths(base_picture)

    assert len(report.issues) == 1
    assert "DisplayPath" in report.issues[0].message
    assert "+MissingPanel" in report.issues[0].message


def test_picture_display_path_analyzer_reports_unresolved_operationpath_candidate_from_oprframe_name() -> None:
    base_picture = _build_operation_path_base_picture()
    base_picture.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="Root",
            declaring_module_path=("Root", "UnitControl"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token="1",
                        index_value=1,
                        kind="variable",
                        raw_text="Paths.OperationPath",
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    report = analyze_picture_display_paths(base_picture)

    assert len(report.issues) == 1
    assert "Paths.OperationPath" in report.issues[0].message
    assert "+L2+Operations+L2*FyldAppl" in report.issues[0].message
    assert "FyldAppl" in report.issues[0].message


def test_exact_string_inference_tracks_provenance_segments_across_mapped_module_writes() -> None:
    base_picture = _build_operation_path_base_picture()

    result = ExactStringInferenceEngine(base_picture).infer(
        "Paths.OperationPath",
        module_path=("Root", "UnitControl"),
    )

    assert result.texts == ("+L2+Operations+L2*FyldAppl",)
    assert result.candidates[0].segments == (
        StringProvenanceSegment(
            text="+L2+Operations+L2*",
            source_kind="initializer",
            source_label="OprPath",
            source_module_path=("Root", "UnitControl"),
        ),
        StringProvenanceSegment(
            text="FyldAppl",
            source_kind="initializer",
            source_label="FyldOprName",
            source_module_path=("Root", "UnitControl"),
        ),
    )


def test_exact_string_inference_tracks_setstringpos_and_cutstring() -> None:
    base_picture = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        moduledef=ModuleDef(),
        localvariables=[
            Variable(name="Tag", datatype=Simple_DataType.STRING),
            Variable(name="Source", datatype=Simple_DataType.STRING, init_value="ABCD"),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_FUNCTION_CALL, "ClearString", [_varref("Tag")]),
                        (
                            const.KEY_FUNCTION_CALL,
                            "InsertString",
                            [
                                _varref("Tag"),
                                _varref("Source"),
                                _string_length_call("Source"),
                                _varref("Status"),
                            ],
                        ),
                        (const.KEY_FUNCTION_CALL, "SetStringPos", [_varref("Tag"), 2, _varref("Status")]),
                        (const.KEY_FUNCTION_CALL, "CutString", [_varref("Tag"), 2, _varref("Status")]),
                    ],
                )
            ]
        ),
    )

    result = ExactStringInferenceEngine(base_picture).infer("Tag", module_path=("Root",))

    assert result.texts == ("AD",)
    assert result.cursor_positions == (2,)
    assert result.candidates[0].segments == (
        StringProvenanceSegment(
            text="AD",
            source_kind="initializer",
            source_label="Source",
            source_module_path=("Root",),
        ),
    )


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
