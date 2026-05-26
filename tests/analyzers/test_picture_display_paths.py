from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    GraphObject,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    SourceSpan,
)
from sattlint.analyzers.picture_display_paths import analyze_picture_display_paths
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.picture_display_paths import (
    PictureDisplayOccurrence,
    correlate_picture_display_records,
    diagnose_picture_display_paths,
    resolve_picture_display_path,
)


def _base_picture_with_single_chain() -> BasePicture:
    leaf = SingleModule(
        header=ModuleHeader(name="Panel", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
    )
    wrapper = SingleModule(
        header=ModuleHeader(name="L1", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
        submodules=[leaf],
    )
    return BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="Root",
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        submodules=[wrapper],
    )


def _module(
    name: str,
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] | None = None,
) -> SingleModule:
    return SingleModule(
        header=ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
        submodules=submodules or [],
    )


def _base_picture_with_leading_dash_paths() -> BasePicture:
    base_picture = BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="BasePicture",
        moduledef=ModuleDef(),
        submodules=[
            _module(
                "Soejle",
                [
                    _module(
                        "L1",
                        [
                            _module(
                                "L2",
                                [
                                    _module(
                                        "UnitControl",
                                        [
                                            _module(
                                                "L1",
                                                [
                                                    _module(
                                                        "L2",
                                                        [
                                                            _module("UnitHold", [_module("Udkobling")]),
                                                            _module(
                                                                "Operations",
                                                                [
                                                                    _module(
                                                                        "L2",
                                                                        [
                                                                            _module(
                                                                                "OprFrame",
                                                                                [
                                                                                    _module(
                                                                                        "Produktion",
                                                                                        [
                                                                                            _module(
                                                                                                "L1",
                                                                                                [
                                                                                                    _module(
                                                                                                        "L2",
                                                                                                        [
                                                                                                            _module(
                                                                                                                "Display",
                                                                                                                [
                                                                                                                    _module(
                                                                                                                        "L2"
                                                                                                                    )
                                                                                                                ],
                                                                                                            ),
                                                                                                            _module(
                                                                                                                "Displays",
                                                                                                                [
                                                                                                                    _module(
                                                                                                                        "L1",
                                                                                                                        [
                                                                                                                            _module(
                                                                                                                                "L2",
                                                                                                                                [
                                                                                                                                    _module(
                                                                                                                                        "AlarmDisp",
                                                                                                                                        [
                                                                                                                                            _module(
                                                                                                                                                "L1",
                                                                                                                                                [
                                                                                                                                                    _module(
                                                                                                                                                        "L2",
                                                                                                                                                        [
                                                                                                                                                            _module(
                                                                                                                                                                "Form"
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
                                                                                                            _module(
                                                                                                                "CalculateVR_AS",
                                                                                                                [
                                                                                                                    _module(
                                                                                                                        "AlarmsAndWarnings",
                                                                                                                        [
                                                                                                                            _module(
                                                                                                                                "Form"
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
                        ],
                    )
                ],
            )
        ],
    )
    return base_picture


def _base_picture_with_moduletype_form_picture_display() -> BasePicture:
    opmessage = _module("Opmessage", [_module("L1", [_module("L2", [_module("COLUMNJUMPOUTLET")])])])
    ud_disp = ModuleTypeDef(
        name="UdDisp",
        submodules=[
            _module(
                "L1",
                [
                    _module(
                        "L2",
                        [
                            SingleModule(
                                header=ModuleHeader(name="Form", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                                moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
                            )
                        ],
                    )
                ],
            )
        ],
    )
    return BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="BasePicture",
        moduletype_defs=[ud_disp],
        submodules=[
            _module(
                "Soejle",
                [
                    _module(
                        "L1",
                        [
                            _module(
                                "L2",
                                [
                                    _module(
                                        "UnitControl",
                                        [
                                            _module(
                                                "L1",
                                                [
                                                    _module(
                                                        "L2",
                                                        [
                                                            _module(
                                                                "Operations",
                                                                [
                                                                    _module(
                                                                        "L2",
                                                                        [
                                                                            opmessage,
                                                                            _module(
                                                                                "OprFrame",
                                                                                [
                                                                                    _module(
                                                                                        "Produktion",
                                                                                        [
                                                                                            _module(
                                                                                                "L1",
                                                                                                [
                                                                                                    _module(
                                                                                                        "L2",
                                                                                                        [
                                                                                                            _module(
                                                                                                                "Recipe",
                                                                                                                [
                                                                                                                    _module(
                                                                                                                        "L1",
                                                                                                                        [
                                                                                                                            _module(
                                                                                                                                "L2",
                                                                                                                                [
                                                                                                                                    ModuleTypeInstance(
                                                                                                                                        header=ModuleHeader(
                                                                                                                                            name="UDDisp",
                                                                                                                                            invoke_coord=(
                                                                                                                                                0.0,
                                                                                                                                                0.0,
                                                                                                                                                0.0,
                                                                                                                                                1.0,
                                                                                                                                                1.0,
                                                                                                                                            ),
                                                                                                                                        ),
                                                                                                                                        moduletype_name="UdDisp",
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


def test_picture_display_path_analyzer_reports_unresolved_paths() -> None:
    base_picture = _base_picture_with_single_chain()
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
                        index_token="0",
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
    base_picture = _base_picture_with_single_chain()
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
                        index_token="0",
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
    base_picture = _base_picture_with_single_chain()

    resolution = resolve_picture_display_path(
        "++Panel",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is True
    assert resolution.resolved_module_path == ("Root", "L1", "Panel")


def test_resolve_picture_display_path_reports_unimplemented_wmf_asset() -> None:
    base_picture = _base_picture_with_single_chain()

    resolution = resolve_picture_display_path(
        "scr:nne_blue_web.wmf",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is False
    assert resolution.failure_reason == "unimplemented_asset"
    assert resolution.detail == ".emf and .wmf resolution is not implemented"


def test_resolve_picture_display_path_reports_unimplemented_env_var_wmf_asset() -> None:
    base_picture = _base_picture_with_single_chain()

    resolution = resolve_picture_display_path(
        "sg_pictures:nne_blue_web.wmf",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is False
    assert resolution.failure_reason == "unimplemented_asset"
    assert resolution.detail == ".emf and .wmf resolution is not implemented"


def test_resolve_picture_display_path_reports_unimplemented_emf_asset() -> None:
    base_picture = _base_picture_with_single_chain()

    resolution = resolve_picture_display_path(
        "Novo Bull SattLine Background Color.emf",
        base_picture=base_picture,
        declaring_module_path=("Root",),
    )

    assert resolution.ok is False
    assert resolution.failure_reason == "unimplemented_asset"
    assert resolution.detail == ".emf and .wmf resolution is not implemented"


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
    base_picture = _base_picture_with_leading_dash_paths()

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
    base_picture = _base_picture_with_leading_dash_paths()

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


def test_resolve_picture_display_path_recovers_missing_declaring_module_by_suffix() -> None:
    base_picture = BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="BasePicture",
        moduledef=ModuleDef(),
        submodules=[
            _module(
                "Soejle",
                [
                    _module(
                        "L1",
                        [
                            _module(
                                "L2",
                                [
                                    _module(
                                        "UnitControl",
                                        [
                                            _module(
                                                "L1",
                                                [
                                                    _module(
                                                        "L2",
                                                        [
                                                            _module(
                                                                "UnitControl",
                                                                [
                                                                    _module(
                                                                        "L1",
                                                                        [
                                                                            _module(
                                                                                "L2",
                                                                                [
                                                                                    _module(
                                                                                        "UnitPanels",
                                                                                        [
                                                                                            _module(
                                                                                                "L1",
                                                                                                [
                                                                                                    _module(
                                                                                                        "L2",
                                                                                                        [
                                                                                                            _module(
                                                                                                                "ToolBar"
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

    resolution = resolve_picture_display_path(
        "+L2+UnitControl+L1+L2+UnitPanels+L1+L2+ToolBar",
        base_picture=base_picture,
        declaring_module_path=(
            "BasePicture",
            "L1",
            "KaHASojle",
            "L1",
            "L2",
            "UnitControl",
            "L1",
        ),
        parent_step_adjustment=-1,
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
        "UnitControl",
        "L1",
        "L2",
        "UnitPanels",
        "L1",
        "L2",
        "ToolBar",
    )


def test_correlate_picture_display_records_reanchors_local_moduletype_occurrence_to_instance_path() -> None:
    base_picture = _base_picture_with_moduletype_form_picture_display()
    record = PictureDisplayRecord(
        record_index=1,
        record_start_line=1,
        record_end_line=5,
        path_rows=(
            PictureDisplayPathRow(
                record_index=1,
                index_token="0",
                index_value=0,
                kind="literal",
                raw_text="-----------+Opmessage+l1+l2+COLUMNJUMPOUTLET",
                span=SourceSpan(line=1, column=1),
            ),
        ),
    )

    occurrences = correlate_picture_display_records(base_picture, (record,))

    assert occurrences == (
        PictureDisplayOccurrence(
            program_name="BasePicture",
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
                "Recipe",
                "L1",
                "L2",
                "UDDisp",
                "L1",
                "L2",
                "Form",
            ),
            record=record,
            parent_step_adjustment=-1,
        ),
    )
    assert diagnose_picture_display_paths(base_picture, occurrences) == ()
