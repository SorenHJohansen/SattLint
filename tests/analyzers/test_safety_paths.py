from types import SimpleNamespace

from sattline_parser.models.ast_model import (
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
from sattlint.analyzers import safety_paths as safety_paths_module
from sattlint.analyzers.framework import Issue
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.safety_paths import SafetyPathAnalyzer, SafetyPathReport, analyze_safety_paths
from sattlint.core.safety_paths import (
    SafetyPathTrace,
    build_safety_path_traces,
    build_symbol_accesses,
    is_safety_critical_path,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict:
    return {const.KEY_VAR_NAME: name}


def _access_event(
    canonical_path: str,
    *,
    kind: str,
    use_module_path: tuple[str, ...],
    syntactic_ref: str,
    use_display_path: tuple[str, ...] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        canonical_path=canonical_path,
        kind=SimpleNamespace(value=kind),
        use_module_path=use_module_path,
        use_display_path=use_display_path or use_module_path,
        syntactic_ref=syntactic_ref,
    )


def test_is_safety_critical_path_normalizes_keywords_and_returns_false_when_no_match() -> None:
    assert is_safety_critical_path("Root.Guard.E-Stop Signal", keywords=("E Stop",)) is True
    assert is_safety_critical_path("Root..EmergencyShutdown") is True
    assert is_safety_critical_path("Root.Guard.ProcessSignal") is False


def test_build_safety_path_traces_skips_empty_and_filtered_paths_and_applies_limit() -> None:
    accesses_by_key = {
        ("empty",): (),
        ("query-miss",): (
            _access_event(
                "Root.Guard.EStopSignal",
                kind="write",
                use_module_path=("Root", "Guard"),
                syntactic_ref="EStopSignal",
            ),
        ),
        ("non-safety",): (
            _access_event(
                "Root.Guard.ProcessSignal",
                kind="write",
                use_module_path=("Root", "Guard"),
                syntactic_ref="ProcessSignal",
            ),
        ),
        ("match-a",): (
            _access_event(
                "Root.EmergencyShutdown",
                kind="read",
                use_module_path=("Root", "Guard"),
                syntactic_ref="EmergencyShutdown",
            ),
            _access_event(
                "Root.EmergencyShutdown",
                kind="write",
                use_module_path=("Root",),
                syntactic_ref="EmergencyShutdown",
            ),
        ),
        ("match-b",): (
            _access_event(
                "Root.MainShutdown",
                kind="write",
                use_module_path=("Root",),
                syntactic_ref="MainShutdown",
            ),
        ),
    }

    traces = build_safety_path_traces(accesses_by_key, query="shutdown", limit=1)

    assert len(traces) == 1
    assert traces[0].canonical_path == "Root.EmergencyShutdown"
    assert traces[0].writer_count == 1
    assert traces[0].reader_count == 1
    assert traces[0].writer_module_paths == (("Root",),)
    assert traces[0].reader_module_paths == (("Root", "Guard"),)


def test_build_symbol_accesses_orders_events_by_module_kind_and_reference() -> None:
    accesses = build_symbol_accesses(
        [
            _access_event(
                "Root.EmergencyShutdown",
                kind="write",
                use_module_path=("Root", "Guard"),
                syntactic_ref="z_ref",
            ),
            _access_event(
                "Root.EmergencyShutdown",
                kind="read",
                use_module_path=("Root",),
                syntactic_ref="BRef",
            ),
            _access_event(
                "Root.EmergencyShutdown",
                kind="read",
                use_module_path=("Root",),
                syntactic_ref="aref",
            ),
        ]
    )

    assert [access.use_module_path for access in accesses] == [
        ("Root",),
        ("Root",),
        ("Root", "Guard"),
    ]
    assert [access.syntactic_ref for access in accesses] == ["aref", "BRef", "z_ref"]
    assert [access.kind for access in accesses] == ["read", "read", "write"]


def test_safety_paths_trace_emergency_signal_across_moduletype_mapping() -> None:
    guard_type = ModuleTypeDef(
        name="GuardType",
        moduleparameters=[Variable(name="InSignal", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[Variable(name="Seen", datatype=Simple_DataType.BOOLEAN, init_value=False)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Seen"), _varref("InSignal"))],
                )
            ]
        ),
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False)],
        moduletype_defs=[guard_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Guard"),
                moduletype_name="GuardType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InSignal"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("EmergencyShutdown"),
                        source_literal=None,
                    )
                ],
            )
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("EmergencyShutdown"), True)],
                )
            ]
        ),
        origin_file="Root.s",
    )

    report = analyze_safety_paths(bp)

    assert report.issues == []
    assert len(report.traces) == 1
    assert report.traces[0].canonical_path == "Root.EmergencyShutdown"
    assert report.traces[0].writer_module_paths == (("Root",),)
    assert report.traces[0].reader_module_paths == (("Root", "Guard"),)
    assert report.traces[0].spans_multiple_modules is True


def test_safety_paths_reports_unconsumed_shutdown_signal() -> None:
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("EmergencyShutdown"), True)],
                )
            ]
        ),
    )

    report = analyze_safety_paths(bp)

    assert len(report.traces) == 1
    assert len(report.issues) == 1
    assert report.issues[0].kind == "safety-path.unconsumed_signal"
    assert report.issues[0].data is not None
    assert report.issues[0].data["canonical_path"] == "Root.EmergencyShutdown"


def test_safety_paths_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "safety-paths" in specs
    assert specs["safety-paths"].enabled is True


def test_safety_paths_report_summary_covers_ok_and_issue_outputs() -> None:
    ok_report = SafetyPathReport(basepicture_name="Root")

    assert ok_report.name == "Root"
    ok_summary = ok_report.summary()
    assert ok_report.traces == []
    assert "Traced paths: 0" in ok_summary
    assert "No safety-critical path issues found." in ok_summary

    traced_report = SafetyPathReport(
        basepicture_name="Root",
        traces=[
            SafetyPathTrace(
                canonical_path="Root.EmergencyShutdown",
                accesses=(),
                writer_count=1,
                reader_count=1,
                writer_module_paths=(("Root",),),
                reader_module_paths=(("Root", "Guard"),),
                spans_multiple_modules=True,
            )
        ],
    )
    assert "Traced paths: 1" in traced_report.summary()

    issue_report = SafetyPathReport(
        basepicture_name="Root",
        traces=traced_report.traces,
        issues=[
            Issue(
                kind="safety-path.unconsumed_signal",
                message="EmergencyShutdown is never read.",
                module_path=["Root", "Guard"],
            )
        ],
    )

    issue_summary = issue_report.summary()
    assert "Issues: 1" in issue_summary
    assert "Unconsumed safety-critical signals: 1" in issue_summary
    assert "[Root.Guard] EmergencyShutdown is never read." in issue_summary

    unlabeled_issue_report = SafetyPathReport(
        basepicture_name="Root",
        issues=[Issue(kind="safety-path.other", message="Other issue")],
    )
    unlabeled_summary = unlabeled_issue_report.summary()
    assert "Kinds:" in unlabeled_summary
    assert "Unconsumed safety-critical signals" not in unlabeled_summary


def test_safety_paths_analyzer_properties_and_trace_filtering(monkeypatch) -> None:
    observed_kwargs: dict[str, object] = {}

    class _FakeVariablesAnalyzer:
        def __init__(self, bp, **kwargs):
            observed_kwargs.update(kwargs)
            self.bp = bp
            self.access_graph = type("AccessGraph", (), {"by_path_key": {("root",): ()}})()

        def run(self) -> None:
            return None

    traces = [
        SafetyPathTrace(
            canonical_path="Root.NoWriter",
            accesses=(),
            writer_count=0,
            reader_count=0,
            writer_module_paths=(),
            reader_module_paths=(),
            spans_multiple_modules=False,
        ),
        SafetyPathTrace(
            canonical_path="Root.AlreadyConsumed",
            accesses=(),
            writer_count=1,
            reader_count=1,
            writer_module_paths=(("Root",),),
            reader_module_paths=(("Root", "Guard"),),
            spans_multiple_modules=True,
        ),
        SafetyPathTrace(
            canonical_path="Root.EmergencyShutdown",
            accesses=(),
            writer_count=1,
            reader_count=0,
            writer_module_paths=(),
            reader_module_paths=(),
            spans_multiple_modules=False,
        ),
    ]

    monkeypatch.setattr(safety_paths_module, "VariablesAnalyzer", _FakeVariablesAnalyzer)
    monkeypatch.setattr(safety_paths_module, "build_safety_path_traces", lambda _accesses: traces)

    analyzer = SafetyPathAnalyzer(
        BasePicture(header=_hdr("Root"), localvariables=[], submodules=[], modulecode=None),
        unavailable_libraries={"OtherLib"},
        analyzed_target_is_library=True,
    )

    assert analyzer.issues == []
    assert analyzer.traces == []

    issues = analyzer.run()

    assert observed_kwargs["include_dependency_moduletype_usage"] is True
    assert observed_kwargs["analyzed_target_is_library"] is True
    assert observed_kwargs["unavailable_libraries"] == {"OtherLib"}
    assert analyzer.traces == traces
    assert issues == analyzer.issues
    assert len(issues) == 1
    assert issues[0].module_path == ["Root"]
    assert issues[0].data is not None
    assert issues[0].data["writer_count"] == 1
    assert issues[0].data["reader_count"] == 0
