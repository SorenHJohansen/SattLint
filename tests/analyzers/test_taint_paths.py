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
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.analyzers.taint_paths import analyze_taint_paths
from sattlint.core import taint_paths as taint_paths_core
from sattlint.core.taint_paths import build_taint_path_traces, classify_taint_source_path, is_critical_sink_path


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


def test_taint_path_helpers_cover_empty_segments_and_display_fallbacks() -> None:
    assert classify_taint_source_path("Root..Operator-Command") == "operator"
    assert classify_taint_source_path("Root.ProcessSignal") is None
    assert is_critical_sink_path("Root..EmergencyShutdown") is True
    assert is_critical_sink_path("Root.ProcessSignal") is False

    accesses_by_key = {
        ("root", "operator"): (
            _access_event(
                "Root.OperatorCommand",
                kind="write",
                use_module_path=("Root",),
                syntactic_ref="OperatorCommand",
            ),
        )
    }

    assert (
        taint_paths_core._display_canonical_path(
            ("root", "operator"),
            accesses_by_key,
            {("root", "operator"): "Display.OperatorCommand"},
        )
        == "Display.OperatorCommand"
    )
    assert taint_paths_core._display_canonical_path(("root", "operator"), accesses_by_key) == "Root.OperatorCommand"
    assert taint_paths_core._display_canonical_path(("root", "fallback"), accesses_by_key) == "root.fallback"
    assert taint_paths_core._path_matches_query(("Root.OperatorCommand", "Root.Guard.EmergencyShutdown"), "guard")
    assert not taint_paths_core._path_matches_query(
        ("Root.OperatorCommand", "Root.Guard.EmergencyShutdown"),
        "sensor",
    )


def test_build_taint_path_traces_covers_source_recheck_cycles_and_limit(monkeypatch) -> None:
    classify_calls: dict[str, int] = {}

    def _fake_classify(
        canonical_path: str,
        *,
        source_keywords: dict[str, tuple[str, ...]] = taint_paths_core.DEFAULT_TAINT_SOURCE_KEYWORDS,
    ) -> str | None:
        _ = source_keywords
        classify_calls[canonical_path] = classify_calls.get(canonical_path, 0) + 1
        if canonical_path == "Root.AOperatorCommand":
            return "operator" if classify_calls[canonical_path] == 1 else None
        if canonical_path == "Root.BOperatorCommand":
            return "operator"
        if canonical_path == "Root.SensorReading":
            return "sensor"
        return None

    monkeypatch.setattr(taint_paths_core, "classify_taint_source_path", _fake_classify)

    accesses_by_key = {
        ("a",): (
            _access_event(
                "Root.AOperatorCommand",
                kind="write",
                use_module_path=("Root",),
                syntactic_ref="AOperatorCommand",
            ),
        ),
        ("b",): (
            _access_event(
                "Root.BOperatorCommand",
                kind="write",
                use_module_path=("Root",),
                syntactic_ref="BOperatorCommand",
            ),
        ),
        ("mid",): (
            _access_event(
                "Root.BufferNode",
                kind="read",
                use_module_path=("Root", "Guard"),
                syntactic_ref="BufferNode",
            ),
        ),
        ("sink",): (
            _access_event(
                "Root.Guard.EmergencyShutdown",
                kind="write",
                use_module_path=("Root", "Guard"),
                syntactic_ref="EmergencyShutdown",
            ),
        ),
    }
    effect_flow_edges = {
        ("a",): (("sink",),),
        ("b",): (("mid",),),
        ("mid",): (("sink",),),
        ("sink",): (("mid",),),
    }

    traces = build_taint_path_traces(effect_flow_edges, accesses_by_key)

    assert len(traces) == 1
    assert traces[0].source_canonical_path == "Root.BOperatorCommand"
    assert traces[0].sink_canonical_path == "Root.Guard.EmergencyShutdown"
    assert traces[0].path == (
        "Root.BOperatorCommand",
        "Root.BufferNode",
        "Root.Guard.EmergencyShutdown",
    )

    limited_traces = build_taint_path_traces(
        {
            ("operator",): (("mid",), ("sink",)),
            ("mid",): (("sink",),),
            ("sink",): (),
            ("sensor",): (("sink2",),),
            ("sink2",): (),
        },
        {
            ("operator",): accesses_by_key[("b",)],
            ("mid",): accesses_by_key[("mid",)],
            ("sink",): accesses_by_key[("sink",)],
            ("sensor",): (
                _access_event(
                    "Root.SensorReading",
                    kind="write",
                    use_module_path=("Root",),
                    syntactic_ref="SensorReading",
                ),
            ),
            ("sink2",): (
                _access_event(
                    "Root.TripSignal",
                    kind="write",
                    use_module_path=("Root", "Sensor"),
                    syntactic_ref="TripSignal",
                ),
            ),
        },
        query="trip",
        limit=1,
    )
    assert len(limited_traces) == 1
    assert limited_traces[0].sink_canonical_path == "Root.TripSignal"

    capped_traces = build_taint_path_traces(
        {("operator",): (("sink",),), ("sink",): ()},
        {
            ("operator",): accesses_by_key[("b",)],
            ("sink",): accesses_by_key[("sink",)],
        },
        limit=5,
    )
    assert len(capped_traces) == 1


def test_taint_paths_trace_operator_input_to_shutdown_sink_across_moduletype_mapping() -> None:
    guard_type = ModuleTypeDef(
        name="GuardType",
        moduleparameters=[Variable(name="InCommand", datatype=Simple_DataType.BOOLEAN)],
        localvariables=[Variable(name="EmergencyShutdown", datatype=Simple_DataType.BOOLEAN, init_value=False)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="GuardEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("EmergencyShutdown"), _varref("InCommand"))],
                )
            ]
        ),
        parametermappings=[],
        origin_file="Root.s",
    )
    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[Variable(name="OperatorCommand", datatype=Simple_DataType.BOOLEAN, init_value=False)],
        moduletype_defs=[guard_type],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("Guard"),
                moduletype_name="GuardType",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("InCommand"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("OperatorCommand"),
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
                    code=[(const.KEY_ASSIGN, _varref("OperatorCommand"), True)],
                )
            ]
        ),
        origin_file="Root.s",
    )

    report = analyze_taint_paths(bp)

    assert len(report.traces) == 1
    assert len(report.issues) == 1
    assert report.traces[0].source_kind == "operator"
    assert report.traces[0].source_canonical_path == "Root.OperatorCommand"
    assert report.traces[0].sink_canonical_path == "Root.Guard.EmergencyShutdown"
    assert report.traces[0].spans_multiple_modules is True
    assert report.issues[0].kind == "taint-path.external_input_to_critical_sink"


def test_taint_paths_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "taint-paths" in specs
    assert specs["taint-paths"].enabled is True
