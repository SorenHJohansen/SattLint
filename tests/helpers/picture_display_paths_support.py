from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    GraphObject,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)


def base_picture_with_single_chain() -> BasePicture:
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


def module(
    name: str,
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance] | None = None,
) -> SingleModule:
    return SingleModule(
        header=ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduledef=ModuleDef(),
        submodules=submodules or [],
    )


def picture_display_path_text(*segments: str) -> str:
    return "-----------+" + "+".join(segments)


def picture_display_jump_node_path_text() -> str:
    return picture_display_path_text("Opmessage", "l1", "l2", "COLUMNJUMPNODE")


def base_picture_with_leading_dash_paths() -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="BasePicture",
        moduledef=ModuleDef(),
        submodules=[
            module(
                "Soejle",
                [
                    module(
                        "L1",
                        [
                            module(
                                "L2",
                                [
                                    module(
                                        "UnitControl",
                                        [
                                            module(
                                                "L1",
                                                [
                                                    module(
                                                        "L2",
                                                        [
                                                            module("UnitHold", [module("Udkobling")]),
                                                            module(
                                                                "Operations",
                                                                [
                                                                    module(
                                                                        "L2",
                                                                        [
                                                                            module(
                                                                                "OprFrame",
                                                                                [
                                                                                    module(
                                                                                        "Produktion",
                                                                                        [
                                                                                            module(
                                                                                                "L1",
                                                                                                [
                                                                                                    module(
                                                                                                        "L2",
                                                                                                        [
                                                                                                            module(
                                                                                                                "Display",
                                                                                                                [
                                                                                                                    module(
                                                                                                                        "L2"
                                                                                                                    )
                                                                                                                ],
                                                                                                            ),
                                                                                                            module(
                                                                                                                "Displays",
                                                                                                                [
                                                                                                                    module(
                                                                                                                        "L1",
                                                                                                                        [
                                                                                                                            module(
                                                                                                                                "L2",
                                                                                                                                [
                                                                                                                                    module(
                                                                                                                                        "AlarmDisp",
                                                                                                                                        [
                                                                                                                                            module(
                                                                                                                                                "L1",
                                                                                                                                                [
                                                                                                                                                    module(
                                                                                                                                                        "L2",
                                                                                                                                                        [
                                                                                                                                                            module(
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
                                                                                                            module(
                                                                                                                "CalculateVR_AS",
                                                                                                                [
                                                                                                                    module(
                                                                                                                        "AlarmsAndWarnings",
                                                                                                                        [
                                                                                                                            module(
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


def base_picture_with_moduletype_form_picture_display() -> BasePicture:
    opmessage = module("Opmessage", [module("L1", [module("L2", [module("COLUMNJUMPNODE")])])])
    ud_disp = ModuleTypeDef(
        name="UdDisp",
        submodules=[
            module(
                "L1",
                [
                    module(
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
            module(
                "Soejle",
                [
                    module(
                        "L1",
                        [
                            module(
                                "L2",
                                [
                                    module(
                                        "UnitControl",
                                        [
                                            module(
                                                "L1",
                                                [
                                                    module(
                                                        "L2",
                                                        [
                                                            module(
                                                                "Operations",
                                                                [
                                                                    module(
                                                                        "L2",
                                                                        [
                                                                            opmessage,
                                                                            module(
                                                                                "OprFrame",
                                                                                [
                                                                                    module(
                                                                                        "Produktion",
                                                                                        [
                                                                                            module(
                                                                                                "L1",
                                                                                                [
                                                                                                    module(
                                                                                                        "L2",
                                                                                                        [
                                                                                                            module(
                                                                                                                "Recipe",
                                                                                                                [
                                                                                                                    module(
                                                                                                                        "L1",
                                                                                                                        [
                                                                                                                            module(
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
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    )
