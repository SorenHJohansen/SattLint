from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.analyzers import unsafe_defaults as unsafe_defaults_module
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.unsafe_defaults import (
    UnsafeDefaultsAnalyzer,
    _identifier_tokens,
    analyze_unsafe_defaults,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def test_unsafe_defaults_reports_true_boolean_enable_default() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=True)],
        modulecode=None,
    )

    report = analyze_unsafe_defaults(bp)

    assert any(issue.kind == "unsafe_defaults.true_boolean_default" for issue in report.issues)
    assert any("EnablePump" in issue.message for issue in report.issues)
    assert any("activate equipment or logic from startup" in issue.message for issue in report.issues)


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

    report = analyze_unsafe_defaults(bp)

    issues = [issue for issue in report.issues if issue.kind == "unsafe_defaults.true_boolean_default"]
    assert len(issues) == 1
    assert issues[0].module_path == ["Root", "TypeDef:ValveType"]
    assert "bypass safety checks from startup" in issues[0].message


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

    report = analyze_unsafe_defaults(bp)

    assert report.issues == []


def test_unsafe_defaults_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "unsafe-defaults" in specs
    assert specs["unsafe-defaults"].enabled is True


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

    report = analyze_unsafe_defaults(bp)

    paths = {tuple(issue.module_path or []) for issue in report.issues}
    assert ("Root", "Child") in paths
    assert ("Root", "Frame", "NestedChild") in paths


def test_unsafe_defaults_summary_covers_ok_and_issue_outputs() -> None:
    empty_report = analyze_unsafe_defaults(
        BasePicture(header=_hdr("Root"), localvariables=[], submodules=[], modulecode=None)
    )
    assert "No unsafe default values found." in empty_report.summary()

    issue_report = analyze_unsafe_defaults(
        BasePicture(
            header=_hdr("Root"),
            localvariables=[Variable(name="EnablePump", datatype=Simple_DataType.BOOLEAN, init_value=True)],
            submodules=[],
            modulecode=None,
        )
    )

    summary = issue_report.summary()
    assert "Unsafe defaults" in summary
    assert "Issues: 1" in summary
    assert "[Root] Boolean variable 'EnablePump' defaults to True" in summary


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

    assert analyze_unsafe_defaults(bp).issues == []


def test_unsafe_defaults_helper_branches_cover_identifier_tokenization_and_safe_defaults() -> None:
    assert _identifier_tokens("Enable_Bypass42") == ("enable", "bypass", "42")
    assert _identifier_tokens("___") == ()

    analyzer = UnsafeDefaultsAnalyzer(
        BasePicture(header=_hdr("Root"), localvariables=[], submodules=[], modulecode=None)
    )

    assert (
        analyzer._unsafe_default_reason(Variable(name="EnablePump", datatype=Simple_DataType.INTEGER, init_value=True))
        is None
    )
    assert (
        analyzer._unsafe_default_reason(Variable(name="AlarmTrip", datatype=Simple_DataType.BOOLEAN, init_value=True))
        is None
    )


def test_unsafe_defaults_direct_helpers_cover_property_origin_and_instance_skip(monkeypatch) -> None:
    analyzer = UnsafeDefaultsAnalyzer(
        BasePicture(
            header=_hdr("Root"),
            localvariables=[],
            submodules=[
                ModuleTypeInstance(
                    header=_hdr("TypeInstance"),
                    moduletype_name="IgnoredType",
                    parametermappings=[],
                )
            ],
            modulecode=None,
        )
    )

    assert analyzer.issues == []
    assert analyzer._is_from_root_origin(None) is True
    analyzer.run()
    assert analyzer.issues == []

    class _NoMatches:
        def findall(self, _text: str) -> list[str]:
            return []

    monkeypatch.setattr(unsafe_defaults_module, "_IDENTIFIER_TOKEN_RE", _NoMatches())
    assert _identifier_tokens("NoMatches") == ("nomatches",)
