# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false
from typing import cast

from lark import Tree

from ._analyzers_variables_test_support import *


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
