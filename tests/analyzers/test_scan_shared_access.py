# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
from types import SimpleNamespace

from sattline_parser.models.ast_model import BasePicture, ModuleCode, ModuleHeader, Simple_DataType, Variable
from sattlint import constants as const
from sattlint.analyzers import scan_shared_access as scan_shared_access_module
from sattlint.analyzers.framework import Issue
from sattlint.analyzers.registry import get_actual_cli_analyzer_keys, get_default_analyzers
from sattlint.analyzers.scan_shared_access import analyze_scan_shared_access


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _assign(name: str, value: object) -> tuple[object, object, object]:
    return (const.KEY_ASSIGN, _varref(name), value)


def test_scan_shared_access_analyzer_is_registered_and_opt_in_for_cli() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "scan-shared-access" in specs
    assert specs["scan-shared-access"].enabled is True
    assert "scan-shared-access" not in get_actual_cli_analyzer_keys()


def test_scan_shared_access_reports_filtered_same_cycle_hazard() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                SimpleNamespace(name="ReadEq", code=[_assign("Sink", _varref("SharedValue"))]),
                SimpleNamespace(name="WriteEq", code=[_assign("SharedValue", 2)]),
            ],
            sequences=[],
        ),
    )

    report = analyze_scan_shared_access(bp)

    assert [issue.kind for issue in report.issues] == ["same_cycle_non_state_multi_site_hazard"]
    assert report.summary().startswith("Report: Scan shared access")


def test_scan_shared_access_reports_clean_program_without_issues() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="SharedValue", datatype=Simple_DataType.INTEGER),
            Variable(name="Sink", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                SimpleNamespace(name="ReadEq", code=[_assign("Sink", _varref("SharedValue"))]),
            ],
            sequences=[],
        ),
    )

    report = analyze_scan_shared_access(bp)

    assert report.issues == []
    assert "No scan shared-access issues found." in report.summary()


def test_scan_shared_access_requests_only_new_issue_kind(monkeypatch) -> None:
    bp = BasePicture(header=_hdr("Root"), localvariables=[], modulecode=ModuleCode(sequences=[], equations=[]))
    seen_selected_kinds: list[object] = []

    def _fake_analyze_same_cycle(*_args, **kwargs):
        seen_selected_kinds.append(kwargs.get("selected_issue_kinds"))
        return SimpleNamespace(
            issues=[
                Issue(
                    kind="same_cycle_non_state_multi_site_hazard",
                    message="hazard",
                    module_path=["Root"],
                    data=None,
                ),
                Issue(kind="same_cycle_shared_access_hazard", message="other", module_path=["Root"], data=None),
            ]
        )

    monkeypatch.setattr(scan_shared_access_module, "analyze_same_cycle", _fake_analyze_same_cycle)

    report = scan_shared_access_module.analyze_scan_shared_access(bp)

    assert seen_selected_kinds == [scan_shared_access_module._SCAN_SHARED_ACCESS_ISSUE_KINDS]
    assert [issue.kind for issue in report.issues] == ["same_cycle_non_state_multi_site_hazard"]
