# ruff: noqa: F403, F405
from typing import cast

from lark import Tree

from sattline_parser.models.ast_model import FrameModule, GraphicsBinding
from sattlint.graphics_validation import PictureDisplayPathRow, PictureDisplayRecord
from sattlint.picture_display_paths import PictureDisplayOccurrence

from ._analyzers_variables_test_support import *

COLUMN_TYPE_STEP = "ColumnType"
FIRST_RECORD_STEP = "1"


def test_library_typedef_moduleparameter_unused_fields_are_suppressed():
    record_type = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    exported = ModuleTypeDef(
        name="ExportedType",
        moduleparameters=[Variable(name="p", datatype="RecType")],
        localvariables=[Variable(name="sink", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("sink"),
                            _varref("p.Used"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[exported],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    program_analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=False)
    program_analyzer.run()
    assert any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in program_analyzer.issues
    )

    library_analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    library_analyzer.run()
    assert not any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in library_analyzer.issues
    )


def test_library_typedef_local_used_via_child_interact_coordinate_tail_is_not_unused():
    child_param = Variable(name="xSize", datatype=Simple_DataType.REAL)
    child_type = ModuleTypeDef(
        name="ButtonType",
        moduleparameters=[child_param],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(
            interact_objects=[
                InteractObject(
                    type=const.GRAMMAR_VALUE_COMBUT,
                    properties={
                        const.KEY_COORDS: [((0.0, 0.0), (1.0, 1.0))],
                        const.KEY_TAILS: [_varref("xSize")],
                        const.KEY_BODY: [{const.KEY_NAME: "ButtonType", const.KEY_VALUE: 0}],
                    },
                )
            ]
        ),
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    x_size = Variable(name="XSize", datatype=Simple_DataType.REAL)
    parent_type = ModuleTypeDef(
        name="EluMasterLinie",
        moduleparameters=[],
        localvariables=[x_size],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Button"),
                moduletype_name="ButtonType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("xSize"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("XSize"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[parent_type, child_type],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is x_size
        and issue.module_path == ["BasePicture", "TypeDef:EluMasterLinie"]
        for issue in analyzer.issues
    )


def test_library_typedef_local_used_via_child_combutproc_togglewindow_arg_is_not_unused():
    child_param = Variable(name="xSize", datatype=Simple_DataType.REAL)
    child_type = ModuleTypeDef(
        name="RecipePicklistSecond",
        moduleparameters=[child_param],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(
            interact_objects=[
                InteractObject(
                    type=const.GRAMMAR_VALUE_COMBUTPROC,
                    properties={
                        const.KEY_COORDS: [((0.0, 0.0), (1.0, 1.0))],
                        const.KEY_PROCEDURE: {
                            const.KEY_NAME: "ToggleWindow",
                            const.KEY_ARGS: [
                                "",
                                "Picklist",
                                False,
                                0.0,
                                0.0,
                                _varref("xSize"),
                                0.0,
                                False,
                                0,
                                0,
                                False,
                                0,
                            ],
                        },
                    },
                )
            ]
        ),
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    x_size = Variable(name="XSize", datatype=Simple_DataType.REAL)
    parent_type = ModuleTypeDef(
        name="EluMasterLinie",
        moduleparameters=[],
        localvariables=[x_size],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Picklist"),
                moduletype_name="RecipePicklistSecond",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("xSize"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("XSize"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[parent_type, child_type],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is x_size
        and issue.module_path == ["BasePicture", "TypeDef:EluMasterLinie"]
        for issue in analyzer.issues
    )


def test_library_typedef_local_used_via_child_legacy_combutproc_togglewindow_tree_is_not_unused():
    legacy_procedure_args = Tree(
        "procedure_args",
        cast(
            list[object],
            [
                Tree("proc_atom", cast(list[object], [""])),
                Tree("proc_atom", cast(list[object], ["Picklist"])),
                Tree("proc_atom", cast(list[object], [False])),
                Tree("proc_atom", cast(list[object], [0.0])),
                Tree("proc_atom", cast(list[object], [0.0])),
                Tree("proc_atom", cast(list[object], [0.0])),
                Tree("proc_atom", cast(list[object], ["xSize"])),
            ],
        ),
    )

    child_param = Variable(name="xSize", datatype=Simple_DataType.REAL)
    child_type = ModuleTypeDef(
        name="RecipePicklistSecond",
        moduleparameters=[child_param],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(
            interact_objects=[
                InteractObject(
                    type=const.GRAMMAR_VALUE_COMBUTPROC,
                    properties={
                        const.KEY_COORDS: [((0.0, 0.0), (1.0, 1.0))],
                        const.KEY_PROCEDURE: {
                            const.KEY_NAME: None,
                            const.KEY_ARGS: [
                                "ToggleWindow",
                                legacy_procedure_args,
                            ],
                        },
                    },
                )
            ]
        ),
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    x_size = Variable(name="XSize", datatype=Simple_DataType.REAL)
    parent_type = ModuleTypeDef(
        name="EluMasterLinie",
        moduleparameters=[],
        localvariables=[x_size],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Picklist"),
                moduletype_name="RecipePicklistSecond",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("xSize"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("XSize"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[parent_type, child_type],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is x_size
        and issue.module_path == ["BasePicture", "TypeDef:EluMasterLinie"]
        for issue in analyzer.issues
    )


def test_unused_datatype_fields_are_aggregated_across_variables():
    record_type = DataType(
        name="SharedRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    first = Variable(name="First", datatype="SharedRecord")
    second = Variable(name="Second", datatype="SharedRecord")

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[first, second],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("sinkA"), _varref("First.A")),
                        (const.KEY_ASSIGN, _varref("sinkB"), _varref("Second.B")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[
            Variable(name="sinkA", datatype=Simple_DataType.INTEGER),
            Variable(name="sinkB", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[module],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "SharedRecord"
    }

    assert unused_fields == {"C"}


def test_unused_datatype_fields_count_nested_record_field_accesses():
    op_type = DataType(
        name="KaHAOPType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="LOP19", datatype=Simple_DataType.BOOLEAN),
            Variable(name="LOP20", datatype=Simple_DataType.BOOLEAN),
            Variable(name="LOP21", datatype=Simple_DataType.BOOLEAN),
        ],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    config_type = DataType(
        name="ConfigType",
        description=None,
        datecode=None,
        var_list=[Variable(name="ActiveOP", datatype="KaHAOPType")],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    child_typedef = ModuleTypeDef(
        name="PanelType",
        moduleparameters=[Variable(name="ThisOPStation", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadThisOp",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("ThisOPStation")],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    root_typedef = ModuleTypeDef(
        name="RootType",
        moduleparameters=[],
        localvariables=[Variable(name="Config", datatype="ConfigType")],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Panel"),
                moduletype_name="PanelType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("ThisOPStation"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Config.ActiveOP.LOP19"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
        parametermappings=[],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[op_type, config_type],
        moduletype_defs=[root_typedef, child_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "KaHAOPType"
    }

    assert unused_fields == {"LOP20", "LOP21"}


def test_library_target_dependency_mapping_counts_root_record_field_usage_without_dependency_reads():
    record_type = DataType(
        name="ColumnShDataType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="TC601_AlarmDelay", datatype=Simple_DataType.INTEGER),
            Variable(name="TC601_GlitChDelay", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="KaHASoejleLib.s",
        origin_lib="KaHASoejleLib",
    )
    dependency_typedef = ModuleTypeDef(
        name="MES_BatchControl",
        moduleparameters=[Variable(name="AlarmDelay", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
        parametermappings=[],
        origin_file="NNEMESIFLib.s",
        origin_lib="NNEMESIFLib",
    )
    root_typedef = ModuleTypeDef(
        name="ColumnType",
        moduleparameters=[],
        localvariables=[
            Variable(name="ColumnSh", datatype="ColumnShDataType"),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("MES_BatchControl"),
                moduletype_name="MES_BatchControl",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("AlarmDelay"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("ColumnSh.TC601_AlarmDelay"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Sink"),
                            _varref("ColumnSh.TC601_GlitChDelay"),
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="KaHASoejleLib.s",
        origin_lib="KaHASoejleLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[root_typedef, dependency_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHASoejleLib.s",
        origin_lib="KaHASoejleLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, include_dependency_moduletype_usage=True)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "ColumnShDataType"
    }

    assert unused_fields == {"Unused"}


def test_picture_display_variable_rows_count_as_field_usage_for_datatype_reporting():
    record_type = DataType(
        name="StepTextType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="CleanCycle", datatype=Simple_DataType.STRING),
            Variable(name="WaitCleanCycle", datatype=Simple_DataType.STRING),
            Variable(name="Unused", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    module = SingleModule(
        header=_hdr("DisplayModule"),
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        moduleparameters=[],
        localvariables=[Variable(name="StepTexts", datatype="StepTextType")],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[module],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "DisplayModule"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token="<token>",
                        index_value=0,
                        kind="variable",
                        raw_text="StepTexts.CleanCycle",
                        span=SourceSpan(line=9, column=1),
                    ),
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token="<token>",
                        index_value=1,
                        kind="variable",
                        raw_text="StepTexts.WaitCleanCycle",
                        span=SourceSpan(line=10, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "StepTextType"
    }

    assert unused_fields == {"Unused"}


def test_library_target_picture_display_variable_rows_count_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "Soejle"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token=COLUMN_TYPE_STEP,
                        index_value=None,
                        kind="variable",
                        raw_text="ColumnType",
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Soejle"]
        for issue in analyzer.issues
    )


def test_library_target_picture_display_index_variable_counts_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "Soejle"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token=COLUMN_TYPE_STEP,
                        index_value=None,
                        kind="literal",
                        raw_text="+InletMPC+++Inlet_Z2",
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Soejle"]
        for issue in analyzer.issues
    )


def test_library_dependency_typedef_internal_string_mismatches_are_suppressed_but_edge_mismatches_remain():
    dependency_typedef = ModuleTypeDef(
        name="EquipModCoordinate",
        moduleparameters=[Variable(name="EdgeTarget", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[Variable(name="InnerSource", datatype=Simple_DataType.STRING)],
        submodules=[
            SingleModule(
                header=_hdr("InnerConsumer"),
                moduledef=None,
                moduleparameters=[Variable(name="InnerTarget", datatype=Simple_DataType.IDENTSTRING)],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InnerTarget"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("InnerSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="nnestruct.x",
        origin_lib="nnestruct",
    )
    parent_typedef = ModuleTypeDef(
        name="KaHAMPCSoejle",
        moduleparameters=[],
        localvariables=[Variable(name="EdgeSource", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Coordinate"),
                moduletype_name="EquipModCoordinate",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("EdgeTarget"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EdgeSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[dependency_typedef, parent_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, include_dependency_moduletype_usage=True)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert [(issue.module_path, issue.variable.name, issue.source_variable.name) for issue in issues] == [
        (["Root", "TypeDef:KaHAMPCSoejle", "Coordinate"], "EdgeTarget", "EdgeSource")
    ]


def test_library_dependency_nested_instance_string_mismatches_are_suppressed_but_edge_mismatches_remain():
    nested_dependency = ModuleTypeDef(
        name="OffButtonFB",
        moduleparameters=[Variable(name="TagPrefix", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="nnestruct.x",
        origin_lib="nnestruct",
    )
    dependency_typedef = ModuleTypeDef(
        name="EquipModCoordinate",
        moduleparameters=[Variable(name="EdgeTarget", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[Variable(name="Name", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AutoButton"),
                moduletype_name="OffButtonFB",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("TagPrefix"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Name"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="nnestruct.x",
        origin_lib="nnestruct",
    )
    parent_typedef = ModuleTypeDef(
        name="KaHAMPCSoejle",
        moduleparameters=[],
        localvariables=[Variable(name="EdgeSource", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Coordinate"),
                moduletype_name="EquipModCoordinate",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("EdgeTarget"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EdgeSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[nested_dependency, dependency_typedef, parent_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, include_dependency_moduletype_usage=True)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert [(issue.module_path, issue.variable.name, issue.source_variable.name) for issue in issues] == [
        (["Root", "TypeDef:KaHAMPCSoejle", "Coordinate"], "EdgeTarget", "EdgeSource")
    ]


def test_library_dependency_nested_instance_string_mismatches_stay_suppressed_without_dependency_origin_file():
    nested_dependency = ModuleTypeDef(
        name="OffButtonFB",
        moduleparameters=[Variable(name="TagPrefix", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="nnestruct.x",
        origin_lib="nnestruct",
    )
    dependency_typedef = ModuleTypeDef(
        name="EquipModCoordinate",
        moduleparameters=[Variable(name="EdgeTarget", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[Variable(name="Name", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AutoButton"),
                moduletype_name="OffButtonFB",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("TagPrefix"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Name"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file=None,
        origin_lib="nnestruct",
    )
    parent_typedef = ModuleTypeDef(
        name="KaHAMPCSoejle",
        moduleparameters=[],
        localvariables=[Variable(name="EdgeSource", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Coordinate"),
                moduletype_name="EquipModCoordinate",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("EdgeTarget"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EdgeSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[nested_dependency, dependency_typedef, parent_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, include_dependency_moduletype_usage=True)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert [(issue.module_path, issue.variable.name, issue.source_variable.name) for issue in issues] == [
        (["Root", "TypeDef:KaHAMPCSoejle", "Coordinate"], "EdgeTarget", "EdgeSource")
    ]


def test_program_dependency_nested_instance_string_mismatches_stay_suppressed_without_dependency_origin_file():
    nested_dependency = ModuleTypeDef(
        name="OffButtonFB",
        moduleparameters=[Variable(name="TagPrefix", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="nnestruct.x",
        origin_lib="nnestruct",
    )
    dependency_typedef = ModuleTypeDef(
        name="EquipModCoordinate",
        moduleparameters=[Variable(name="EdgeTarget", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[Variable(name="Name", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("AutoButton"),
                moduletype_name="OffButtonFB",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("TagPrefix"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Name"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file=None,
        origin_lib="nnestruct",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[nested_dependency, dependency_typedef],
        localvariables=[Variable(name="EdgeSource", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Coordinate"),
                moduletype_name="EquipModCoordinate",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("EdgeTarget"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EdgeSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="PlantProgram.s",
        origin_lib="PlantProgram",
    )

    analyzer = VariablesAnalyzer(
        bp,
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
    )
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert [(issue.module_path, issue.variable.name, issue.source_variable.name) for issue in issues] == [
        (["Root", "Coordinate"], "EdgeTarget", "EdgeSource")
    ]


def test_library_target_picture_display_record_binding_counts_typedef_moduleparameter_usage_at_root():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="var",
            raw_text="ColumnType",
            value=_varref("ColumnType"),
            span=SourceSpan(line=1, column=1),
        )
    ]
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "Soejle"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token=FIRST_RECORD_STEP,
                        index_value=1,
                        kind="literal",
                        raw_text="+InletMPC+++Inlet_Z2",
                        span=SourceSpan(line=2, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Soejle"]
        for issue in analyzer.issues
    )


def test_library_target_picture_display_runtime_instance_path_counts_typedef_moduleparameter_usage():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Panel"),
                moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[
            FrameModule(
                header=_hdr("L1"),
                submodules=[
                    ModuleTypeInstance(
                        header=_hdr("KaHASoejle"),
                        moduletype_name="Soejle",
                        parametermappings=[],
                    )
                ],
                moduledef=None,
                modulecode=None,
            )
        ],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="var",
            raw_text="ColumnType",
            value=_varref("ColumnType"),
            span=SourceSpan(line=1, column=1),
        )
    ]
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "L1", "KaHASoejle", "Panel"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token=FIRST_RECORD_STEP,
                        index_value=1,
                        kind="literal",
                        raw_text="+InletMPC+++Inlet_Z2",
                        span=SourceSpan(line=2, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        for issue in analyzer.issues
    )


def test_library_target_picture_display_variable_rows_count_typedef_moduleparameter_usage_in_submodule():
    root_typedef = ModuleTypeDef(
        name="Soejle",
        moduleparameters=[Variable(name="ColumnType", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Panel"),
                moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSoejleLib.s",
        origin_lib="KaHAMPCSoejleLib",
    )
    bp.graphics_picture_display_occurrences = [
        PictureDisplayOccurrence(
            program_name="BasePicture",
            declaring_module_path=("BasePicture", "Soejle", "Panel"),
            record=PictureDisplayRecord(
                record_index=1,
                record_start_line=1,
                record_end_line=5,
                path_rows=(
                    PictureDisplayPathRow(
                        record_index=1,
                        index_token=COLUMN_TYPE_STEP,
                        index_value=None,
                        kind="variable",
                        raw_text="ColumnType",
                        span=SourceSpan(line=1, column=1),
                    ),
                ),
            ),
        )
    ]

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.role == "moduleparameter"
        and issue.variable is not None
        and issue.variable.name == "ColumnType"
        and issue.module_path == ["BasePicture", "TypeDef:Soejle"]
        for issue in analyzer.issues
    )


def test_library_target_direct_typedef_code_counts_field_usage_for_datatype_reporting():
    record_type = DataType(
        name="StepTextType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="CleanCycle", datatype=Simple_DataType.STRING),
            Variable(name="WaitCleanCycle", datatype=Simple_DataType.STRING),
            Variable(name="Unused", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    root_typedef = ModuleTypeDef(
        name="DiluteType",
        moduleparameters=[],
        localvariables=[
            Variable(name="StepText", datatype="StepTextType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyString",
                            [_varref("StepText.CleanCycle"), _varref("Sink"), _varref("Status")],
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[root_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "StepTextType"
    }

    assert unused_fields == {"WaitCleanCycle", "Unused"}


def test_iter_variables_for_datatype_field_analysis_includes_context_only_variables():
    root_var = Variable(name="RootTexts", datatype="StepTextType")
    context_var = Variable(name="StepText", datatype="StepTextType")
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[root_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    fake_analyzer = SimpleNamespace(
        bp=bp,
        limit_to_module_path=None,
        analyzed_target_is_library=True,
        include_dependency_moduletype_usage=True,
        contexts_by_module_path={
            ("BasePicture", "Nested", "Display"): SimpleNamespace(
                env={"steptext": context_var},
                param_mappings={"steptext": (root_var, "", ["BasePicture"], ["BasePicture"])},
            )
        },
        is_from_root_origin=lambda origin_file, origin_lib=None: True,
    )

    collected = variable_issue_collection_module._iter_variables_for_datatype_field_analysis(fake_analyzer)

    assert any(variable is root_var for _path, variable, _role, _root_owned in collected)
    assert any(
        variable is context_var and path == ["BasePicture", "Nested", "Display"] and role == "moduleparameter"
        for path, variable, role, _root_owned in collected
    )


def test_unused_datatype_fields_include_context_only_variable_usage():
    root_var = Variable(name="RootTexts", datatype="StepTextType")
    context_var = Variable(name="StepText", datatype="StepTextType")
    record_type = DataType(
        name="StepTextType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="CleanCycle", datatype=Simple_DataType.STRING),
            Variable(name="WaitCleanCycle", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[root_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAXDiluteLib.s",
        origin_lib="KaHAXDiluteLib",
    )
    usage_by_id = {
        id(root_var): _UsageStub(field_reads={"WaitCleanCycle": [object()]}),
        id(context_var): _UsageStub(field_reads={"CleanCycle": [object()]}),
    }
    issues: list[VariableIssue] = []
    fake_analyzer = SimpleNamespace(
        bp=bp,
        limit_to_module_path=None,
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        contexts_by_module_path={
            ("BasePicture", "Nested", "Display"): SimpleNamespace(
                env={"steptext": context_var},
                param_mappings={"steptext": (root_var, "", ["BasePicture"], ["BasePicture"])},
            )
        },
        type_graph=SimpleNamespace(
            iter_leaf_field_paths=lambda _datatype: [("CleanCycle",), ("WaitCleanCycle",)],
            record=lambda _datatype: None,
        ),
        is_from_root_origin=lambda origin_file, origin_lib=None: True,
        get_usage=lambda variable: usage_by_id[id(variable)],
        append_issue=issues.append,
    )

    variable_issue_collection_module._add_unused_datatype_field_issues(fake_analyzer)

    assert not any(issue.kind is IssueKind.UNUSED_DATATYPE_FIELD for issue in issues)


def test_analyze_variables_library_target_counts_dependency_typedef_field_reads():
    from sattlint.analyzers.variables import analyze_variables

    op_text_type = DataType(
        name="ApplOpTxtType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="LSH", datatype=Simple_DataType.STRING),
            Variable(name="DrainPipe", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    dependency_typedef = ModuleTypeDef(
        name="ConsumerType",
        moduleparameters=[],
        localvariables=[
            Variable(name="OPText", datatype="ApplOpTxtType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Sink"),
                            _varref("OPText.LSH"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="KaHAApplLib.s",
        origin_lib="KaHAApplLib",
    )
    support_typedef = ModuleTypeDef(
        name="SupportType",
        moduleparameters=[],
        localvariables=[
            Variable(name="OPText", datatype="ApplOpTxtType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
        ],
        submodules=[ModuleTypeInstance(header=_hdr("Consumer"), moduletype_name="ConsumerType", parametermappings=[])],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadRootField",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Sink"),
                            _varref("OPText.DrainPipe"),
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[op_text_type],
        moduletype_defs=[support_typedef, dependency_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )

    report = analyze_variables(bp, analyzed_target_is_library=True)

    unused_fields = {
        issue.field_path
        for issue in report.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "ApplOpTxtType"
    }

    assert "LSH" not in unused_fields
    assert unused_fields == set()


def test_analyze_variables_library_target_counts_reverse_consumer_typedef_field_reads():
    from sattlint.analyzers.variables import analyze_variables

    op_text_type = DataType(
        name="ApplOpTxtType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="LSH", datatype=Simple_DataType.STRING),
            Variable(name="DrainPipe", datatype=Simple_DataType.STRING),
        ],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    support_typedef = ModuleTypeDef(
        name="SupportType",
        moduleparameters=[],
        localvariables=[Variable(name="OPText", datatype="ApplOpTxtType")],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
        parametermappings=[],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    consumer_typedef = ModuleTypeDef(
        name="ConsumerType",
        moduleparameters=[],
        localvariables=[
            Variable(name="OPText", datatype="ApplOpTxtType"),
            Variable(name="Sink", datatype=Simple_DataType.STRING),
        ],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ReadLSH",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("Sink"),
                            _varref("OPText.LSH"),
                        )
                    ],
                )
            ],
            sequences=[],
        ),
        parametermappings=[],
        origin_file="KaHAApplLib.s",
        origin_lib="KaHAApplLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[op_text_type],
        moduletype_defs=[support_typedef, consumer_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )

    report = analyze_variables(bp, analyzed_target_is_library=True)

    unused_fields = {
        issue.field_path
        for issue in report.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD and issue.datatype_name == "ApplOpTxtType"
    }

    assert "LSH" not in unused_fields
    assert unused_fields == {"DrainPipe"}


def test_sample_fixture_contains_common_variable_quality_issues():
    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "CommonQualityIssues.s"

    bp = parse_source_file(fixture)
    issues = VariablesAnalyzer(bp).run()

    unused = {issue.variable.name for issue in issues if issue.kind is IssueKind.UNUSED and issue.variable is not None}
    read_only_non_const = {
        issue.variable.name
        for issue in issues
        if issue.kind is IssueKind.READ_ONLY_NON_CONST and issue.variable is not None
    }
    never_read = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.NEVER_READ and issue.variable is not None
    }
    unused_fields = {
        (issue.datatype_name, issue.field_path) for issue in issues if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
    }

    assert "UnusedValue" in unused
    assert "ReadOnlyValue" in read_only_non_const
    assert "NeverReadValue" in never_read
    assert ("QualityRecord", "UnusedField") in unused_fields


def test_gfile_var_and_expr_reads_count_as_used_for_unused_analysis():
    from sattlint.engine import CodeMode, SattLineProjectLoader, merge_project_basepicture

    fixture = Path(__file__).parent / "fixtures" / "sample_sattline_files" / "TestGFileParse.s"
    loader = SattLineProjectLoader(
        program_dir=fixture.parent,
        other_lib_dirs=[],
        abb_lib_dir=fixture.parent,
        mode=CodeMode.DRAFT,
        scan_root_only=True,
        debug=False,
        use_file_ast_cache=False,
    )

    graph = loader.resolve(fixture.stem, strict=False)
    bp = merge_project_basepicture(graph.ast_by_name[fixture.stem], graph)
    analyzer = VariablesAnalyzer(bp)
    issues = analyzer.run()

    usage_by_name = {variable.name: analyzer._get_usage(variable) for variable in bp.localvariables}
    unused = {issue.variable.name for issue in issues if issue.kind is IssueKind.UNUSED and issue.variable is not None}

    assert unused == set()
    assert all(usage.read for usage in usage_by_name.values())


def test_nested_gfile_bindings_count_as_used_end_to_end(tmp_path: Path):
    from sattlint.engine import CodeMode, SattLineProjectLoader, merge_project_basepicture

    source = """"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Shared: integer := 0;
SUBMODULES
    Panel Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
    LOCALVARIABLES
        NestedOnly, Shared: integer := 0;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        CompositeObject
    ENDDEF (*Panel*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    graphics = """" Syntax version 2.23, date: 2026-05-26-00:00:00.000 N "

 1
 Var  True  10 NestedOnly
 Var  True   6 Shared
           0
"""

    fixture = tmp_path / "NestedGraphics.s"
    fixture.write_text(source, encoding="utf-8")
    fixture.with_suffix(".g").write_text(graphics, encoding="utf-8")

    loader = SattLineProjectLoader(
        program_dir=tmp_path,
        other_lib_dirs=[],
        abb_lib_dir=tmp_path,
        mode=CodeMode.DRAFT,
        scan_root_only=True,
        debug=False,
        use_file_ast_cache=False,
    )

    graph = loader.resolve(fixture.stem, strict=False)
    bp = merge_project_basepicture(graph.ast_by_name[fixture.stem], graph)
    analyzer = VariablesAnalyzer(bp)
    issues = analyzer.run()
    issue_tuples = {
        (
            issue.kind,
            tuple(issue.module_path),
            issue.variable.name if issue.variable is not None else None,
            issue.role,
            issue.field_path,
        )
        for issue in issues
    }

    assert (IssueKind.UI_ONLY, ("BasePicture", "Panel"), "NestedOnly", "localvariable", None) in issue_tuples
    assert (IssueKind.UI_ONLY, ("BasePicture", "Panel"), "Shared", "localvariable", None) in issue_tuples
    assert not any(
        issue.kind is IssueKind.UI_ONLY
        and issue.variable is not None
        and issue.variable.name == "Shared"
        and issue.module_path == ["BasePicture"]
        for issue in issues
    )


def test_nested_composite_gfile_bindings_use_declaring_module_scope():
    module = SingleModule(
        header=_hdr("Panel"),
        moduledef=ModuleDef(graph_objects=[GraphObject("CompositeObject")]),
        moduleparameters=[],
        localvariables=[
            Variable(name="NestedOnly", datatype=Simple_DataType.INTEGER),
            Variable(name="Shared", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="RootOnly", datatype=Simple_DataType.INTEGER),
            Variable(name="Shared", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[module],
        modulecode=None,
        moduledef=ModuleDef(),
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="var",
            raw_text="NestedOnly",
            value=_varref("NestedOnly"),
            span=SourceSpan(line=9, column=1),
        ),
        GraphicsBinding(
            kind="var",
            raw_text="Shared",
            value=_varref("Shared"),
            span=SourceSpan(line=10, column=1),
        ),
    ]
    bp.graphics_composite_records = [SimpleNamespace(record_index=1, record_start_line=8, record_end_line=12)]

    analyzer = VariablesAnalyzer(bp)
    issues = analyzer.run()
    issue_tuples = {
        (
            issue.kind,
            tuple(issue.module_path),
            issue.variable.name if issue.variable is not None else None,
            issue.role,
            issue.field_path,
        )
        for issue in issues
    }

    assert not any(
        issue.kind is IssueKind.UNUSED and issue.variable is not None and issue.variable.name == "NestedOnly"
        for issue in issues
    )
    assert not any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "Shared"
        and issue.module_path == ["BasePicture", "Panel"]
        for issue in issues
    )
    assert not any(
        issue.kind is IssueKind.UI_ONLY
        and issue.variable is not None
        and issue.variable.name == "Shared"
        and issue.module_path == ["BasePicture"]
        for issue in issues
    )
    assert (IssueKind.UI_ONLY, ("BasePicture", "Panel"), "NestedOnly", "localvariable", None) in issue_tuples
    assert (IssueKind.UI_ONLY, ("BasePicture", "Panel"), "Shared", "localvariable", None) in issue_tuples


def test_unparsed_gfile_expr_still_counts_named_variables_as_reads():
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="Alpha", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Beta", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=None,
        moduledef=ModuleDef(),
    )
    bp.graphics_bindings = [
        GraphicsBinding(
            kind="expr",
            raw_text="Alpha ??? Beta",
            value="Alpha ??? Beta",
            span=SourceSpan(line=1, column=1),
        )
    ]

    analyzer = VariablesAnalyzer(bp)
    issues = analyzer.run()
    issue_tuples = {
        (
            issue.kind,
            tuple(issue.module_path),
            issue.variable.name if issue.variable is not None else None,
            issue.role,
            issue.field_path,
        )
        for issue in issues
    }

    assert not any(
        issue.kind is IssueKind.UNUSED and issue.variable is not None and issue.variable.name in {"Alpha", "Beta"}
        for issue in issues
    )
    assert (IssueKind.UI_ONLY, ("BasePicture",), "Alpha", "localvariable", None) in issue_tuples
    assert (IssueKind.UI_ONLY, ("BasePicture",), "Beta", "localvariable", None) in issue_tuples


def test_search_rec_component_found_record_output_is_not_flagged_never_read():
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[
            Variable(name="CR", datatype=Simple_DataType.INTEGER),
            Variable(name="Index", datatype=Simple_DataType.INTEGER),
            Variable(name="SearchUnit", datatype=Simple_DataType.INTEGER),
            Variable(name="FoundUnit", datatype=Simple_DataType.INTEGER),
            Variable(name="srci", datatype=Simple_DataType.INTEGER),
            Variable(name="SearchSucceeded", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Mirror", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Search",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("SearchSucceeded"),
                            (
                                const.KEY_FUNCTION_CALL,
                                "SearchRecComponent",
                                [
                                    _varref("CR"),
                                    _varref("Index"),
                                    10,
                                    _varref("SearchUnit"),
                                    _varref("SearchUnit"),
                                    _varref("FoundUnit"),
                                    _varref("srci"),
                                ],
                            ),
                        ),
                        (const.KEY_ASSIGN, _varref("Mirror"), _varref("Index")),
                    ],
                )
            ],
            sequences=[],
        ),
        moduledef=None,
    )

    issues = VariablesAnalyzer(bp).run()

    never_read = {
        issue.variable.name for issue in issues if issue.kind is IssueKind.NEVER_READ and issue.variable is not None
    }

    assert "FoundUnit" not in never_read


def test_datatype_duplication_is_scoped_per_module_and_excludes_anytype():
    fyld = ModuleTypeDef(
        name="Fyld",
        moduleparameters=[
            Variable(name="WildcardA", datatype="AnyType"),
            Variable(name="WildcardB", datatype="AnyType"),
        ],
        localvariables=[
            Variable(name="PhaseTimer", datatype="Timer"),
            Variable(name="PhaseTimerCopy", datatype="Timer"),
        ],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )
    applik = ModuleTypeDef(
        name="Applik",
        moduleparameters=[Variable(name="WildcardC", datatype="AnyType")],
        localvariables=[Variable(name="PhaseTimer", datatype="Timer")],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[fyld, applik],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    duplication_issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.DATATYPE_DUPLICATION]
    assert len(duplication_issues) == 1

    issue = duplication_issues[0]
    assert issue.module_path == ["BasePicture", "TypeDef:Fyld"]
    assert issue.variable is not None
    assert issue.variable.name == "PhaseTimer"
    assert issue.variable.datatype_text == "Timer"
    assert issue.duplicate_count == 2
    assert issue.duplicate_locations == [(["BasePicture", "TypeDef:Fyld"], "localvariable", "PhaseTimerCopy")]

    summary = VariablesReport(basepicture_name=bp.header.name, issues=duplication_issues).summary()
    assert "Datatype 'Timer' declared 2 times in BasePicture.TypeDef:Fyld:" in summary
    assert "+ PhaseTimerCopy (localvariable)" in summary
    assert "AnyType" not in summary
    assert "TypeDef:Applik" not in summary


def test_library_target_report_shows_typedef_for_same_lib_different_file_moduletype():
    typedef = ModuleTypeDef(
        name="InfoPanelType",
        moduleparameters=[Variable(name="EnableInteraktion", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(header=_hdr("Y_Info_Panel"), moduletype_name="InfoPanelType", parametermappings=[]),
            ModuleTypeInstance(header=_hdr("X_Info_Panel"), moduletype_name="InfoPanelType", parametermappings=[]),
        ],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert any(
        issue.kind is IssueKind.UNUSED
        and issue.variable is not None
        and issue.variable.name == "EnableInteraktion"
        and issue.module_path == ["BasePicture", "TypeDef:InfoPanelType"]
        for issue in analyzer.issues
    )

    summary = VariablesReport(basepicture_name=bp.header.name, issues=analyzer.issues).summary()
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Y_Info_Panel :: moduleparameter EnableInteraktion (boolean)" not in summary
    assert "BasePicture.X_Info_Panel :: moduleparameter EnableInteraktion (boolean)" not in summary


def test_program_target_report_dedupes_root_owned_typedef_instance_findings():
    typedef = ModuleTypeDef(
        name="InfoPanelType",
        moduleparameters=[Variable(name="EnableInteraktion", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(header=_hdr("Y_Info_Panel"), moduletype_name="InfoPanelType", parametermappings=[]),
            ModuleTypeInstance(header=_hdr("X_Info_Panel"), moduletype_name="InfoPanelType", parametermappings=[]),
        ],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAApplSupportLib.s",
        origin_lib="KaHAApplSupportLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=False)
    analyzer.run()

    matching_issues = [
        issue
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED and issue.variable is not None and issue.variable.name == "EnableInteraktion"
    ]
    assert len(matching_issues) == 1
    assert matching_issues[0].module_path == ["BasePicture", "TypeDef:InfoPanelType"]

    summary = VariablesReport(basepicture_name=bp.header.name, issues=analyzer.issues).summary()
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Y_Info_Panel :: moduleparameter EnableInteraktion (boolean)" not in summary
    assert "BasePicture.X_Info_Panel :: moduleparameter EnableInteraktion (boolean)" not in summary


def test_library_target_does_not_report_typedefs_from_sibling_projectlib_files():
    foreign_local = Variable(name="FirstIndex", datatype=Simple_DataType.INTEGER)
    foreign_typedef = ModuleTypeDef(
        name="ListKernel",
        moduleparameters=[],
        localvariables=[foreign_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="KaHAListeLibX.x",
        origin_lib="ProjectLib",
    )
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[foreign_typedef],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="KaHAMPCSøjleLib.x",
        origin_lib="ProjectLib",
    )
    usage_by_id = {id(foreign_local): _UsageStub(read=True, is_read_only=True)}
    issues: list[tuple[IssueKind, tuple[str, ...], str]] = []
    helper: Any = SimpleNamespace(
        bp=bp,
        analyzed_target_is_library=True,
        _limit_to_module_path=None,
        _analyze_typedef=lambda *args, **kwargs: None,
        _compute_effective_output_keys=lambda: set(),
        _is_from_root_origin=lambda origin, origin_lib=None: VariablesAnalyzer._is_from_root_origin(
            helper, origin, origin_lib
        ),
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _procedure_status_issue=lambda *_args, **_kwargs: None,
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
        _collect_issues_from_module=lambda *args, **kwargs: None,
    )

    variables_execution_module._collect_typedef_issues(helper)

    assert issues == []


def test_unused_summary_splits_moduletype_and_singlemodule_groups():
    moduletype_var = Variable(name="EnableInteraktion", datatype=Simple_DataType.BOOLEAN)
    singlemodule_var = Variable(name="MinMax", datatype=Simple_DataType.INTEGER)
    issues = [
        VariableIssue(
            kind=IssueKind.UNUSED,
            module_path=["BasePicture", "TypeDef:InfoPanelType"],
            variable=moduletype_var,
            role="moduleparameter",
        ),
        VariableIssue(
            kind=IssueKind.UNUSED,
            module_path=["BasePicture", "TypeDef:Soejle", "L1", "L2", "RPDisp"],
            variable=singlemodule_var,
            role="localvariable",
        ),
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=issues).summary()

    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Soejle.L1.L2.RPDisp :: localvariable MinMax (integer)" in summary
    assert "BasePicture.TypeDef:Soejle.L1.L2.RPDisp :: localvariable MinMax (integer)" not in summary


def test_never_read_summary_splits_moduletype_and_singlemodule_groups():
    moduletype_var = Variable(name="EnableInteraktion", datatype=Simple_DataType.BOOLEAN)
    singlemodule_var = Variable(name="MinMax", datatype=Simple_DataType.INTEGER)
    issues = [
        VariableIssue(
            kind=IssueKind.NEVER_READ,
            module_path=["BasePicture", "TypeDef:InfoPanelType"],
            variable=moduletype_var,
            role="moduleparameter",
        ),
        VariableIssue(
            kind=IssueKind.NEVER_READ,
            module_path=["BasePicture", "TypeDef:Soejle", "L1", "L2", "RPDisp"],
            variable=singlemodule_var,
            role="localvariable",
        ),
    ]

    summary = VariablesReport(basepicture_name="BasePicture", issues=issues).summary()

    assert "Written but never read variables" in summary
    assert "      Moduletype:" in summary
    assert "BasePicture.TypeDef:InfoPanelType :: moduleparameter EnableInteraktion (boolean)" in summary
    assert "      SingleModule:" in summary
    assert "BasePicture.Soejle.L1.L2.RPDisp :: localvariable MinMax (integer)" in summary
    assert "BasePicture.TypeDef:Soejle.L1.L2.RPDisp :: localvariable MinMax (integer)" not in summary


def test_string_mapping_summary_dedupes_root_typedef_singlemodule_rows():
    child_typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="TargetValue", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    parent_typedef = ModuleTypeDef(
        name="ParentType",
        moduleparameters=[Variable(name="SourceValue", datatype=Simple_DataType.STRING)],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("TargetValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("SourceValue"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[child_typedef, parent_typedef],
        localvariables=[],
        submodules=[ModuleTypeInstance(header=_hdr("Parent"), moduletype_name="ParentType", parametermappings=[])],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "TypeDef:ParentType", "Child"]
    assert issues[0].source_decl_module_path == ["Root", "TypeDef:ParentType"]
    assert issues[0].source_role == "moduleparameter"

    summary = VariablesReport(basepicture_name=bp.header.name, issues=issues).summary()

    assert "Root.TypeDef:ParentType.Child" in summary
    assert "Root.Parent.Child" not in summary
    assert "SourceValue" in summary
    assert "moduleparameter" in summary
    assert "identstring" in summary


def test_string_mapping_summary_prefers_original_declaration_type_for_intermediate_path_rows():
    final_typedef = ModuleTypeDef(
        name="FinalType",
        moduleparameters=[Variable(name="FinalValue", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    relay_typedef = ModuleTypeDef(
        name="RelayType",
        moduleparameters=[Variable(name="RelayValue", datatype=Simple_DataType.STRING)],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Final"),
                moduletype_name="FinalType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("FinalValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("RelayValue"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[final_typedef, relay_typedef],
        localvariables=[Variable(name="OriginalValue", datatype=Simple_DataType.IDENTSTRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Relay"),
                moduletype_name="RelayType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("RelayValue"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("OriginalValue"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert len(issues) == 1
    assert issues[0].source_variable is not None
    assert issues[0].source_variable.name == "OriginalValue"
    assert issues[0].source_variable.datatype_text == "identstring"

    summary = VariablesReport(basepicture_name=bp.header.name, issues=issues).summary()

    assert "Intermediate path mismatch only (1):" in summary
    assert "Declaration/final destination mismatch (0):" in summary
    assert "OriginalValue" in summary
    assert "identstring" in summary
    assert "Root.Relay.Final" in summary
    assert "Root.TypeDef:RelayType" not in summary


def test_string_mapping_summary_uses_resolved_field_source_and_target_names():
    issue = VariableIssue(
        kind=IssueKind.STRING_MAPPING_MISMATCH,
        module_path=["Root", "Parent", "Panel", "ActivateButton"],
        variable=Variable(name="Text", datatype=Simple_DataType.IDENTSTRING),
        source_variable=Variable(name="DV.StopText", datatype=Simple_DataType.IDENTSTRING),
        source_decl_module_path=["Root", "Parent"],
        source_role="localvariable",
        target_display_name="Text",
    )

    summary = VariablesReport(basepicture_name="Root", issues=[issue]).summary()

    assert "Intermediate path mismatch only (1):" in summary
    assert "Declaration/final destination mismatch (0):" in summary
    assert "DV.StopText" in summary
    assert "Text" in summary


def test_variables_execution_collect_typedef_issues_covers_branchy_typedef_roles():
    display_param = Variable(name="DisplayParam", datatype=Simple_DataType.INTEGER)
    effect_param = Variable(name="EffectParam", datatype=Simple_DataType.INTEGER)
    procedure_local = Variable(name="ProcedureLocal", datatype=Simple_DataType.INTEGER)
    display_local = Variable(name="DisplayLocal", datatype=Simple_DataType.INTEGER)
    read_only_local = Variable(name="ReadOnlyLocal", datatype=Simple_DataType.INTEGER)
    written_only_local = Variable(name="WrittenOnlyLocal", datatype=Simple_DataType.INTEGER)
    effect_local = Variable(name="EffectLocal", datatype=Simple_DataType.INTEGER)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[display_param, effect_param],
        localvariables=[procedure_local, display_local, read_only_local, written_only_local, effect_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[moduletype],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    usage_by_id = {
        id(display_param): _UsageStub(is_display_only=True),
        id(effect_param): _UsageStub(read=True, written=True),
        id(procedure_local): _UsageStub(read=True),
        id(display_local): _UsageStub(is_display_only=True),
        id(read_only_local): _UsageStub(read=True, is_read_only=True),
        id(written_only_local): _UsageStub(written=True),
        id(effect_local): _UsageStub(read=True, written=True),
    }
    issues: list[tuple[IssueKind, tuple[str, ...], str, str, str | None]] = []
    helper: Any = SimpleNamespace(
        bp=bp,
        _limit_to_module_path=None,
        _analyze_typedef=lambda *args, **kwargs: None,
        _compute_effective_output_keys=lambda: set(),
        _is_from_root_origin=lambda origin, origin_lib=None: True,
        _get_usage=lambda variable: usage_by_id[id(variable)],
        _procedure_status_issue=lambda variable, usage: (
            ("procedure-status", "Status") if variable is procedure_local else None
        ),
        _add_issue=lambda kind, path, variable, role, field_path=None: issues.append(
            (kind, tuple(path), variable.name, role, field_path)
        ),
        _has_output_effect=lambda *args, **kwargs: False,
        _has_ignorable_output_binding=lambda *args, **kwargs: False,
        _has_procedure_status_binding=lambda *args, **kwargs: False,
        _is_const_candidate=lambda *args, **kwargs: True,
    )

    variables_execution_module._collect_typedef_issues(helper)

    assert (IssueKind.UI_ONLY, ("Root", "TypeDef:WorkerType"), "DisplayParam", "moduleparameter", None) in issues
    assert (
        IssueKind.WRITE_WITHOUT_EFFECT,
        ("Root", "TypeDef:WorkerType"),
        "EffectParam",
        "moduleparameter",
        None,
    ) in issues
    assert (
        IssueKind.PROCEDURE_STATUS,
        ("Root", "TypeDef:WorkerType"),
        "ProcedureLocal",
        "procedure-status",
        "Status",
    ) in issues
    assert (IssueKind.UI_ONLY, ("Root", "TypeDef:WorkerType"), "DisplayLocal", "localvariable", None) in issues
    assert (
        IssueKind.READ_ONLY_NON_CONST,
        ("Root", "TypeDef:WorkerType"),
        "ReadOnlyLocal",
        "localvariable",
        None,
    ) in issues
    assert (
        IssueKind.NEVER_READ,
        ("Root", "TypeDef:WorkerType"),
        "WrittenOnlyLocal",
        "localvariable",
        None,
    ) in issues
    assert (
        IssueKind.WRITE_WITHOUT_EFFECT,
        ("Root", "TypeDef:WorkerType"),
        "EffectLocal",
        "localvariable",
        None,
    ) in issues
