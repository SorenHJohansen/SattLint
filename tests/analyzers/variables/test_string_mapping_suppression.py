from sattline_parser.ast import MappingSource

# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnusedImport=false
from tests.helpers.analyzers_variables_support import *


def test_library_dependency_typedef_internal_string_mismatches_are_suppressed_but_edge_mismatches_remain():
    dependency_typedef = ModuleTypeDef(
        name="EquipModCoordinate",
        moduleparameters=[Variable(name="EdgeTarget", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[Variable(name="InnerSource", datatype=Simple_DataType.STRING)],
        submodules=[
            SingleModule(
                header=_hdr("InnerConsumer"),
                moduledefs=[],
                moduleparameters=[Variable(name="InnerTarget", datatype=Simple_DataType.IDENTSTRING)],
                localvariables=[],
                submodules=[],
                modulecodes=[],
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InnerTarget"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("InnerSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="exstruct.x",
        origin_lib="exstruct",
    )
    parent_typedef = ModuleTypeDef(
        name="Column",
        moduleparameters=[],
        localvariables=[Variable(name="EdgeSource", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Coordinate"),
                moduletype_name="EquipModCoordinate",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("EdgeTarget"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EdgeSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[dependency_typedef, parent_typedef],
        localvariables=[],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, include_dependency_moduletype_usage=True)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert [(issue.module_path, issue.variable.name, issue.source_variable.name) for issue in issues] == [
        (["Root", "TypeDef:Column", "Coordinate"], "EdgeTarget", "EdgeSource")
    ]


def test_library_dependency_nested_instance_string_mismatches_are_suppressed_but_edge_mismatches_remain():
    nested_dependency = ModuleTypeDef(
        name="OffButtonFB",
        moduleparameters=[Variable(name="TagPrefix", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="exstruct.x",
        origin_lib="exstruct",
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
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Name"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="exstruct.x",
        origin_lib="exstruct",
    )
    parent_typedef = ModuleTypeDef(
        name="Column",
        moduleparameters=[],
        localvariables=[Variable(name="EdgeSource", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Coordinate"),
                moduletype_name="EquipModCoordinate",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("EdgeTarget"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EdgeSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[nested_dependency, dependency_typedef, parent_typedef],
        localvariables=[],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, include_dependency_moduletype_usage=True)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert [(issue.module_path, issue.variable.name, issue.source_variable.name) for issue in issues] == [
        (["Root", "TypeDef:Column", "Coordinate"], "EdgeTarget", "EdgeSource")
    ]


def test_library_dependency_nested_instance_string_mismatches_stay_suppressed_without_dependency_origin_file():
    nested_dependency = ModuleTypeDef(
        name="OffButtonFB",
        moduleparameters=[Variable(name="TagPrefix", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="exstruct.x",
        origin_lib="exstruct",
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
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Name"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file=None,
        origin_lib="exstruct",
    )
    parent_typedef = ModuleTypeDef(
        name="Column",
        moduleparameters=[],
        localvariables=[Variable(name="EdgeSource", datatype=Simple_DataType.STRING)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Coordinate"),
                moduletype_name="EquipModCoordinate",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("EdgeTarget"),
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EdgeSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[nested_dependency, dependency_typedef, parent_typedef],
        localvariables=[],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
        origin_file="ColumnLib.s",
        origin_lib="ColumnLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True, include_dependency_moduletype_usage=True)
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]

    assert [(issue.module_path, issue.variable.name, issue.source_variable.name) for issue in issues] == [
        (["Root", "TypeDef:Column", "Coordinate"], "EdgeTarget", "EdgeSource")
    ]


def test_program_dependency_nested_instance_string_mismatches_stay_suppressed_without_dependency_origin_file():
    nested_dependency = ModuleTypeDef(
        name="OffButtonFB",
        moduleparameters=[Variable(name="TagPrefix", datatype=Simple_DataType.IDENTSTRING)],
        localvariables=[],
        submodules=[],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file="exstruct.x",
        origin_lib="exstruct",
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
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Name"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
        origin_file=None,
        origin_lib="exstruct",
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
                        source_type=MappingSource.VARIABLE,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EdgeSource"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecodes=[],
        moduledefs=[],
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
