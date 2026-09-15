# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportPrivateUsage=false
from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    Simple_DataType,
    SingleModule,
    Variable,
)

from sattlint.analyzers.variables import _variables_unsafe_defaults as unsafe_defaults_module
from sattlint.analyzers.variables import analyze_variables
from sattlint.reporting.variables_report import DEFAULT_VARIABLE_ANALYSIS_KINDS, IssueKind


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _unsafe_only_report(bp: BasePicture):
    return analyze_variables(bp, selected_issue_kinds=frozenset({IssueKind.UNSAFE_BOOLEAN_DEFAULT}))


def test_unsafe_defaults_reports_true_boolean_enable_default() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        modulecode=None,
    )

    report = _unsafe_only_report(bp)

    unsafe = [issue for issue in report.issues if issue.kind is IssueKind.UNSAFE_BOOLEAN_DEFAULT]
    assert len(unsafe) == 1
    assert unsafe[0].variable is not None and unsafe[0].variable.name == "EnablePump"
    assert "activate equipment or logic from startup" in (unsafe[0].role or "")


def test_unsafe_defaults_reports_true_boolean_bypass_default_in_root_typedef() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[
            ModuleTypeDef(
                name="ValveType",
                moduleparameters=[Variable(name="SafetyBypass", datatype=Simple_DataType.BOOLEAN, init_value=True)],
                localvariables=[],
                submodules=[],
                moduledef=None,
                modulecode=None,
                parametermappings=[],
                origin_file="Root.s",
            )
        ],
        localvariables=[],
        submodules=[],
        modulecode=None,
        origin_file="Root.s",
    )

    report = _unsafe_only_report(bp)

    unsafe = [issue for issue in report.issues if issue.kind is IssueKind.UNSAFE_BOOLEAN_DEFAULT]
    assert len(unsafe) == 1
    assert unsafe[0].module_path == ["Root", "TypeDef:ValveType"]
    assert "bypass safety checks from startup" in (unsafe[0].role or "")


def test_unsafe_defaults_ignores_false_and_external_typedef_defaults() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[
            ModuleTypeDef(
                name="ExternalValveType",
                moduleparameters=[Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=True)],
                localvariables=[],
                submodules=[],
                moduledef=None,
                modulecode=None,
                parametermappings=[],
                origin_file="ExternalType.s",
            )
        ],
        localvariables=[
            Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=False),
            Variable(name="AlarmTrip", datatype=Simple_DataType.BOOLEAN, init_value=True),
        ],
        submodules=[],
        modulecode=None,
        origin_file="Root.s",
    )

    report = _unsafe_only_report(bp)

    assert not any(issue.kind is IssueKind.UNSAFE_BOOLEAN_DEFAULT for issue in report.issues)


def test_unsafe_boolean_default_is_default_variable_analysis_kind() -> None:
    assert IssueKind.UNSAFE_BOOLEAN_DEFAULT in DEFAULT_VARIABLE_ANALYSIS_KINDS


def test_unsafe_defaults_traverses_single_modules_and_nested_frames() -> None:
    nested_child = SingleModule(
        header=_hdr("NestedChild"),
        moduleparameters=[Variable(name="EnableValve", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    child = SingleModule(
        header=_hdr("Child"),
        moduleparameters=[],
        localvariables=[Variable(name="SafetyBypass", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    frame = FrameModule(header=_hdr("Frame"), submodules=[nested_child])
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[],
        submodules=[child, frame],
        modulecode=None,
    )

    report = _unsafe_only_report(bp)

    paths = {tuple(issue.module_path or []) for issue in report.issues}
    assert ("Root", "Child") in paths
    assert ("Root", "Frame", "NestedChild") in paths


def test_unsafe_defaults_summary_reports_unsafe_boolean_default_section() -> None:
    report = _unsafe_only_report(
        BasePicture(
            header=_hdr("Root"),
            localvariables=[Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=True)],
            submodules=[],
            modulecode=None,
        )
    )

    summary = report.summary()
    assert "Unsafe boolean defaults" in summary


def test_unsafe_defaults_ignores_typedefs_when_root_origin_is_unknown() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[
            ModuleTypeDef(
                name="ValveType",
                moduleparameters=[Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=True)],
                localvariables=[],
                submodules=[],
                moduledef=None,
                modulecode=None,
                parametermappings=[],
                origin_file="Root.s",
            )
        ],
        localvariables=[],
        submodules=[],
        modulecode=None,
    )

    report = _unsafe_only_report(bp)

    assert not any(issue.kind is IssueKind.UNSAFE_BOOLEAN_DEFAULT for issue in report.issues)


def test_unsafe_defaults_identifier_tokenization() -> None:
    assert unsafe_defaults_module._identifier_tokens("Enable_Bypass42") == ("enable", "bypass", "42")
    assert unsafe_defaults_module._identifier_tokens("___") == ()


def test_unsafe_defaults_token_set_is_configurable() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="OverrideStart", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        modulecode=None,
    )

    default_report = _unsafe_only_report(bp)
    assert not any(issue.kind is IssueKind.UNSAFE_BOOLEAN_DEFAULT for issue in default_report.issues)

    configured_report = analyze_variables(
        bp,
        selected_issue_kinds=frozenset({IssueKind.UNSAFE_BOOLEAN_DEFAULT}),
        config={"analysis": {"unsafe_default_tokens": ["override"]}},
    )
    unsafe = [issue for issue in configured_report.issues if issue.kind is IssueKind.UNSAFE_BOOLEAN_DEFAULT]
    assert len(unsafe) == 1
    assert unsafe[0].variable is not None and unsafe[0].variable.name == "OverrideStart"
