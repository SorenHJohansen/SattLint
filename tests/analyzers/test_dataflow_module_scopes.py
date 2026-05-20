from __future__ import annotations

from sattline_parser.models.ast_model import (
    AstNodeDict,
    BasePicture,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.dataflow import analyze_dataflow


def _varref(name: str) -> AstNodeDict:
    return {const.KEY_VAR_NAME: name}


def test_root_typedefs_from_same_origin_are_analyzed():
    typedef = ModuleTypeDef(
        name="WorkerType",
        localvariables=[
            Variable(name="Input", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Mirror", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="TypedefEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Mirror"), _varref("Input"))],
                )
            ]
        ),
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_defs=[typedef],
        origin_file="Root.s",
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.read_before_write"
        and issue.module_path == ["Root", "TypeDef:WorkerType"]
        and issue.data is not None
        and issue.data.get("symbol") == "Input"
        for issue in report.issues
    )


def test_root_typedefs_from_other_origins_are_skipped():
    typedef = ModuleTypeDef(
        name="LibraryType",
        localvariables=[
            Variable(name="Input", datatype=Simple_DataType.BOOLEAN),
            Variable(name="Mirror", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="LibraryEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Mirror"), _varref("Input"))],
                )
            ]
        ),
        origin_file="SharedLib.l",
    )
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_defs=[typedef],
        origin_file="Root.s",
    )

    report = analyze_dataflow(bp)

    assert report.issues == []


def test_moduletype_instance_uses_parameter_mapping_source_variables():
    child_type = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ChildEq",
                    position=(0.0, 0.0),
                    size=(1.0, 0.0),
                    code=[
                        (
                            const.GRAMMAR_VALUE_IF,
                            [(_varref("Input"), [(const.KEY_ASSIGN, _varref("Mirror"), True)])],
                            [(const.KEY_ASSIGN, _varref("Mirror"), False)],
                        )
                    ],
                )
            ]
        ),
        origin_file="Root.s",
    )
    child = ModuleTypeInstance(
        header=ModuleHeader(name="Child", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="ChildType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("Source"),
                source_literal=None,
            )
        ],
    )
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_defs=[child_type],
        localvariables=[Variable(name="Source", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        submodules=[child],
        origin_file="Root.s",
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.condition_always_true"
        and issue.module_path == ["Root", "Child"]
        and issue.data is not None
        and issue.data.get("condition") == "Input"
        for issue in report.issues
    )
    assert any(
        issue.kind == "dataflow.unreachable_branch"
        and issue.module_path == ["Root", "Child"]
        and issue.data is not None
        and issue.data.get("branch") == "ELSE"
        for issue in report.issues
    )


def test_global_parameter_mappings_do_not_alias_parent_state():
    child_type = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.BOOLEAN)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="ChildEq",
                    position=(0.0, 0.0),
                    size=(1.0, 0.0),
                    code=[(const.KEY_ASSIGN, _varref("Mirror"), _varref("Input"))],
                )
            ]
        ),
        origin_file="Root.s",
    )
    child = ModuleTypeInstance(
        header=ModuleHeader(name="Child", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="ChildType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=True,
                source=_varref("Source"),
                source_literal=None,
            )
        ],
    )
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_defs=[child_type],
        localvariables=[Variable(name="Source", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        submodules=[child],
        origin_file="Root.s",
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.read_before_write"
        and issue.module_path == ["Root", "Child"]
        and issue.data is not None
        and issue.data.get("symbol") == "Input"
        for issue in report.issues
    )


def test_unresolved_moduletype_instances_are_ignored():
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        submodules=[
            ModuleTypeInstance(
                header=ModuleHeader(name="Child", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
                moduletype_name="MissingType",
            )
        ],
        origin_file="Root.s",
    )

    report = analyze_dataflow(bp)

    assert report.issues == []
