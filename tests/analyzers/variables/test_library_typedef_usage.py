from sattline_parser.ast import AssignClause, MappingSource, ProcedureCall, VarTail

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false
from tests.helpers.analyzers_variables_support import *


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
        moduledefs=[],
        modulecodes=[
            ModuleCode(
                equationblocks=[
                    Equation(
                        name="Main",
                        position=(0.0, 0.0),
                        size=(1.0, 1.0),
                        code=[Assignment(target=_varref("sink"), value=_varref("p.Used"))],
                    )
                ]
            )
        ],
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
        modulecodes=[],
        moduledefs=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    program_analyzer = VariablesAnalyzer(
        bp,
        analyzed_target_is_library=False,
        selected_issue_kinds=frozenset(DATATYPE_FIELD_ANALYSIS_KINDS),
    )
    program_analyzer.run()
    assert any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in program_analyzer.issues
    )

    library_analyzer = VariablesAnalyzer(
        bp,
        analyzed_target_is_library=True,
        selected_issue_kinds=frozenset(DATATYPE_FIELD_ANALYSIS_KINDS),
    )
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
        moduledefs=[
            ModuleDef(
                interact_objects=[
                    InteractObject(
                        type=const.GRAMMAR_VALUE_COMBUT,
                        properties={
                            "coords": [((0.0, 0.0), (1.0, 1.0))],
                            "tails": [VarTail(direction="in", value="xSize")],
                            "body": [AssignClause(name="ButtonType", value=0, tail=None)],
                        },
                    )
                ]
            )
        ],
        modulecodes=[],
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
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("XSize"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
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
        modulecodes=[],
        moduledefs=[],
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
        moduledefs=[
            ModuleDef(
                interact_objects=[
                    InteractObject(
                        type=const.GRAMMAR_VALUE_COMBUTPROC,
                        properties={
                            "coords": [((0.0, 0.0), (1.0, 1.0))],
                            "procedure": ProcedureCall(name="ToggleWindow", args=(_varref("xSize"),)),
                        },
                    )
                ]
            )
        ],
        modulecodes=[],
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
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("XSize"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
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
        modulecodes=[],
        moduledefs=[],
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
