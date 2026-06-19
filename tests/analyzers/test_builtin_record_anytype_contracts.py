# pyright: reportPrivateUsage=false
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.reporting.variables_report import IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _eq(code: list[object]) -> Equation:
    return Equation(
        name="E1",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=code,
    )


def test_anytype_contract_accepts_present_nested_required_field() -> None:
    inner_dt = DataType(
        name="InnerType",
        description=None,
        datecode=None,
        var_list=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
    )
    payload_dt = DataType(
        name="PayloadType",
        description=None,
        datecode=None,
        var_list=[Variable(name="Inner", datatype="InnerType")],
    )

    consumer = ModuleTypeDef(
        name="GenericConsumer",
        moduleparameters=[Variable(name="Payload", datatype="AnyType")],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_ASSIGN,
                            _varref("Mirror"),
                            _varref("Payload.Inner.Value"),
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[inner_dt, payload_dt],
        moduletype_defs=[consumer],
        localvariables=[Variable(name="Source", datatype="PayloadType")],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Consumer"),
                moduletype_name="GenericConsumer",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Payload"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Source"),
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

    assert not any(issue.kind is IssueKind.CONTRACT_MISMATCH for issue in analyzer.issues)


def test_anytype_contract_builder_handles_typedef_submodules_during_init() -> None:
    inner_dt = DataType(
        name="InnerType",
        description=None,
        datecode=None,
        var_list=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
    )

    consumer = ModuleTypeDef(
        name="GenericConsumer",
        moduleparameters=[Variable(name="Payload", datatype="AnyType")],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("NestedReader"),
                moduledef=None,
                moduleparameters=[],
                localvariables=[],
                submodules=[],
                modulecode=None,
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_ASSIGN,
                            _varref("Mirror"),
                            _varref("Payload.Inner.Value"),
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[inner_dt],
        moduletype_defs=[consumer],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)

    assert id(consumer) in analyzer._anytype_field_contracts_by_owner
    payload_contracts = analyzer._anytype_field_contracts_by_owner[id(consumer)]
    assert payload_contracts["payload"].field_paths == ("Inner.Value",)


def test_anytype_contract_reports_missing_nested_required_field() -> None:
    inner_dt = DataType(
        name="InnerType",
        description=None,
        datecode=None,
        var_list=[Variable(name="Other", datatype=Simple_DataType.INTEGER)],
    )
    payload_dt = DataType(
        name="PayloadType",
        description=None,
        datecode=None,
        var_list=[Variable(name="Inner", datatype="InnerType")],
    )

    consumer = ModuleTypeDef(
        name="GenericConsumer",
        moduleparameters=[Variable(name="Payload", datatype="AnyType")],
        localvariables=[Variable(name="Mirror", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        (
                            const.KEY_ASSIGN,
                            _varref("Mirror"),
                            _varref("Payload.Inner.Value"),
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[inner_dt, payload_dt],
        moduletype_defs=[consumer],
        localvariables=[Variable(name="Source", datatype="PayloadType")],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Consumer"),
                moduletype_name="GenericConsumer",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Payload"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("Source"),
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

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.CONTRACT_MISMATCH]
    assert len(issues) == 1
    assert issues[0].field_path == "Inner.Value"
    assert "missing required field 'Inner.Value'" in (issues[0].role or "")
