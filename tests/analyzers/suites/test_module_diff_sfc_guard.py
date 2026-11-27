"""Suite tests for variable-usage reporting and the SFC guard helper.

These tests deliberately exercise private seams; the module comparison helpers
were removed with the version-drift analyzer.
"""

# pyright: reportPrivateUsage=false

from sattline_parser.ast import BoolOp, MappingSource, NotOp
from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    DataType,
    Equation,
    IntLiteral,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    ScalarDatatype,
    SingleModule,
    Variable,
)

from sattlint.analyzers.sfc._sfc_guard_logic import _normalize_guard_signature
from sattlint.analyzers.variable_usage_reporting import (
    _find_module_instances,
    report_module_localvar_fields,
)
from tests.helpers.variable_test_support import (
    hdr as _hdr,
)
from tests.helpers.variable_test_support import (
    varref as _varref,
)


def test_module_localvar_field_report_includes_filtered_summary_sections():
    record_type = DataType(
        name="UsageRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Source", datatype=ScalarDatatype.INTEGER),
            Variable(name="Target", datatype=ScalarDatatype.INTEGER),
        ],
    )
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[Variable(name="Input", datatype="UsageRecord")],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="ChildEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        Assignment(target=_varref("Input.Target"), value=IntLiteral(2)),
                    ],
                )
            ]
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=_varref("Dv"),
                source_literal=None,
            )
        ],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            SingleModule(
                header=_hdr("Unit"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[
                    Variable(name="Dv", datatype="UsageRecord"),
                    Variable(name="Mirror", datatype="UsageRecord"),
                    Variable(name="Sink", datatype=ScalarDatatype.INTEGER),
                ],
                submodules=[child],
                modulecode=ModuleCode(
                    equationblocks=[
                        Equation(
                            name="Usage",
                            position=(0.0, 0.0),
                            size=(1.0, 1.0),
                            code=[
                                Assignment(target=_varref("Sink"), value=_varref("Dv.Source")),
                                Assignment(target=_varref("Dv.Target"), value=IntLiteral(1)),
                                Assignment(target=_varref("Mirror"), value=_varref("Dv")),
                                Assignment(target=_varref("Dv"), value=_varref("Mirror")),
                            ],
                        )
                    ]
                ),
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    report = report_module_localvar_fields(bp, "Unit", "Dv")

    assert "Field usage analysis for local variable 'Dv' in module path 'Root.Unit'" in report
    assert "FIELD-LEVEL ACCESSES:" in report
    assert "dv.source [read]" in report.lower()
    assert "dv.target [write]" in report.lower()
    assert "WHOLE VARIABLE ACCESSES:" in report
    assert "Reads (1 total, 1 unique location(s))" in report
    assert "SUMMARY:" in report
    assert "Aliased parameters: 2" in report
    assert "Fields accessed: 2" in report
    assert "Total field reads: 1" in report
    assert "Total field writes: 3" in report
    assert "Whole variable reads: 1" in report
    assert "Whole variable writes: 2" in report


def test_find_module_instances_includes_direct_and_typedef_expansions():
    parent_typedef = ModuleTypeDef(
        name="ParentType",
        moduleparameters=[],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("WantedAlias"),
                moduletype_name="WantedType",
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=None,
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[parent_typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("DirectWanted"),
                moduletype_name="WantedType",
                parametermappings=[],
            ),
            ModuleTypeInstance(
                header=_hdr("ParentInstance"),
                moduletype_name="ParentType",
                parametermappings=[],
            ),
        ],
        modulecode=None,
        moduledef=None,
    )

    results = _find_module_instances(bp, "WantedType")
    paths = {tuple(path) for _module, path in results}

    assert ("Root", "DirectWanted") in paths
    assert ("Root", "ParentInstance", "WantedAlias") in paths


def test_sfc_guard_signature_collapses_contradictory_and_expression_to_false():
    signature = _normalize_guard_signature(
        BoolOp(
            op="AND",
            operands=(
                _varref("Permit"),
                NotOp(operand=_varref("Permit")),
            ),
        )
    )

    assert signature == ("bool", False)
