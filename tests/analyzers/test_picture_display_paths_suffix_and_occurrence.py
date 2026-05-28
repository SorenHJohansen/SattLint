from sattline_parser.models.ast_model import (
    BasePicture,
    GraphObject,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    SourceSpan,
)
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.picture_display_paths import (
    PictureDisplayOccurrence,
    correlate_picture_display_records,
    diagnose_picture_display_paths,
    resolve_picture_display_path,
)
from tests.helpers.picture_display_paths_support import (
    base_picture_with_leading_dash_paths,
    base_picture_with_moduletype_form_picture_display,
    module,
)


def test_resolve_picture_display_path_recovers_missing_declaring_module_by_suffix() -> None:
    base_picture = BasePicture(
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
                                                                                        "UnitPanels",
                                                                                        [
                                                                                            module(
                                                                                                "L1",
                                                                                                [
                                                                                                    module(
                                                                                                        "L2",
                                                                                                        [
                                                                                                            module(
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


def test_correlate_picture_display_records_maps_local_moduletype_record_to_template_path() -> None:
    base_picture = base_picture_with_moduletype_form_picture_display()
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
                "UdDisp",
                "L1",
                "L2",
                "Form",
            ),
            record=record,
            parent_step_adjustment=0,
            resolution_module_path=(
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
            resolution_parent_step_adjustment=-1,
        ),
    )
    assert diagnose_picture_display_paths(base_picture, occurrences) == ()


def test_correlate_picture_display_records_treats_same_library_typedef_as_local() -> None:
    base_picture = base_picture_with_moduletype_form_picture_display()
    base_picture.origin_file = "KaHAMPCSojleLib.x"
    base_picture.origin_lib = "KaHAMPCSojleLib"
    base_picture.moduletype_defs[0].origin_file = "KaHASojleDisplay.x"
    base_picture.moduletype_defs[0].origin_lib = "KaHAMPCSojleLib"

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
                "UdDisp",
                "L1",
                "L2",
                "Form",
            ),
            record=record,
            parent_step_adjustment=0,
            resolution_module_path=(
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
            resolution_parent_step_adjustment=-1,
        ),
    )
    assert diagnose_picture_display_paths(base_picture, occurrences) == ()


def test_correlate_picture_display_records_keeps_local_templates_out_of_concrete_order() -> None:
    local_template = ModuleTypeDef(
        name="LocalTemplate",
        submodules=[
            SingleModule(
                header=ModuleHeader(name="Form", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
            )
        ],
    )
    base_picture = BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        name="BasePicture",
        moduletype_defs=[local_template],
        moduledef=ModuleDef(),
        submodules=[
            SingleModule(
                header=ModuleHeader(name="Parent", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
                submodules=[
                    SingleModule(
                        header=ModuleHeader(name="Leaf", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
                    ),
                    ModuleTypeInstance(
                        header=ModuleHeader(name="LocalTemplate", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                        moduletype_name="LocalTemplate",
                    ),
                ],
            )
        ],
    )
    records = tuple(
        PictureDisplayRecord(record_index=index, record_start_line=index, record_end_line=index + 1)
        for index in (1, 2, 3)
    )

    occurrences = correlate_picture_display_records(base_picture, records)

    assert tuple(occurrence.declaring_module_path for occurrence in occurrences) == (
        ("BasePicture", "Parent", "Leaf"),
        ("BasePicture", "Parent"),
        ("BasePicture", "LocalTemplate", "Form"),
    )


def test_resolve_picture_display_path_suffix_recovery_supports_wildcard_sibling_branch() -> None:
    base_picture = base_picture_with_leading_dash_paths()

    resolution = resolve_picture_display_path(
        "------CalculateVR_AS+AlarmsAndWarnings*Form",
        base_picture=base_picture,
        declaring_module_path=(
            "BasePicture",
            "L1",
            "KaHASojle",
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


def test_resolve_picture_display_path_retries_canonical_suffix_when_exact_local_branch_fails() -> None:
    base_picture = base_picture_with_leading_dash_paths()
    base_picture.submodules.append(
        module(
            "L1",
            [
                module(
                    "KaHASojle",
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
    )

    resolution = resolve_picture_display_path(
        "-------UnitHold+Udkobling",
        base_picture=base_picture,
        declaring_module_path=(
            "BasePicture",
            "L1",
            "KaHASojle",
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
        "UnitHold",
        "Udkobling",
    )
