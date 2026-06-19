# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false
from types import SimpleNamespace

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
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import interface_contracts as interface_contracts_module
from sattlint.analyzers.interface_contracts import analyze_interface_contracts
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers
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


def test_interface_contracts_analyzer_is_registered() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "interface-contracts" in specs
    assert specs["interface-contracts"].enabled is True
    assert "interface-contracts" not in get_actual_cli_analyzer_keys()


def test_interface_contracts_reports_missing_required_parameter_connection() -> None:
    typedef = ModuleTypeDef(
        name="ChildType",
        moduleparameters=[Variable(name="RequiredValue", datatype=Simple_DataType.INTEGER)],
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
                            _varref("RequiredValue"),
                        )
                    ]
                )
            ]
        ),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[typedef],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Child"),
                moduletype_name="ChildType",
                parametermappings=[],
            )
        ],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_interface_contracts(bp)

    issues = [issue for issue in report.issues if issue.kind is IssueKind.REQUIRED_PARAMETER_CONNECTION]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Child"]
    assert issues[0].role == "required parameter connection missing for 'RequiredValue'"
    assert report.summary().startswith("Report: Interface contracts")


def test_interface_contracts_reports_anytype_missing_required_field() -> None:
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

    report = analyze_interface_contracts(bp)

    issues = [issue for issue in report.issues if issue.kind is IssueKind.CONTRACT_MISMATCH]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "Consumer"]
    assert issues[0].field_path == "Inner.Value"
    assert "missing required field 'Inner.Value'" in (issues[0].role or "")


def test_interface_contracts_requests_only_contract_issue_kinds(monkeypatch) -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    seen_selected_kinds: list[object] = []

    def _fake_analyze_variables(*_args, **kwargs):
        seen_selected_kinds.append(kwargs.get("selected_issue_kinds"))
        return SimpleNamespace(issues=[])

    monkeypatch.setattr(interface_contracts_module, "analyze_variables", _fake_analyze_variables)

    report = interface_contracts_module.analyze_interface_contracts(bp)

    assert report.issues == []
    assert seen_selected_kinds == [interface_contracts_module.INTERFACE_CONTRACT_ISSUE_KINDS]
