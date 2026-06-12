"""Tests for canonical path resolution across parameter mappings."""

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.resolution.access_graph import AccessEvent, AccessGraph, AccessKind
from sattlint.resolution.paths import CanonicalPath, ModuleSegment, decorate_segment
from sattlint.resolution.type_graph import TypeGraph


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def test_resolves_submodule_parameter_access_to_canonical_parent_path():
    # Type chain:
    # Dv: ApplDvType
    #   I: ApplShInputType
    #     WT001: AIType
    #       comp_signal: RealSignal
    #         value: real
    bp_header = ModuleHeader(
        name="Root",
        invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0),
    )

    dt_real_signal = DataType(
        name="RealSignal",
        description=None,
        datecode=None,
        var_list=[Variable(name="value", datatype=Simple_DataType.REAL)],
    )
    dt_ai = DataType(
        name="AIType",
        description=None,
        datecode=None,
        var_list=[Variable(name="comp_signal", datatype="RealSignal")],
    )
    dt_input = DataType(
        name="ApplShInputType",
        description=None,
        datecode=None,
        var_list=[Variable(name="WT001", datatype="AIType")],
    )
    dt_dv = DataType(
        name="ApplDvType",
        description=None,
        datecode=None,
        var_list=[Variable(name="I", datatype="ApplShInputType")],
    )

    dv = Variable(name="Dv", datatype="ApplDvType")

    child = SingleModule(
        header=ModuleHeader(
            name="Analog_Profi_Scale",
            invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0),
        ),
        moduledef=None,
        moduleparameters=[Variable(name="signal", datatype="AIType")],
        localvariables=[],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("signal.comp_signal.value"),
                            1.0,
                        )
                    ],
                )
            ]
        ),
        parametermappings=[
            ParameterMapping(
                target=_varref("signal"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("Dv.I.WT001"),
            )
        ],
    )

    bp = BasePicture(
        header=bp_header,
        datatype_defs=[dt_dv, dt_input, dt_ai, dt_real_signal],
        moduletype_defs=[],
        localvariables=[dv],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    # The write to signal.comp_signal.value should resolve to Root.Dv.I.WT001.comp_signal.value
    write_events = [e for e in analyzer.access_graph.events if e.kind.value == "write"]
    assert write_events, "Expected at least one write event"

    canonical_strs = {str(e.canonical_path) for e in write_events}
    assert "Root.Dv.I.WT001.comp_signal.value" in canonical_strs


def test_disallows_param_and_local_name_collision_in_same_scope():
    bp_header = ModuleHeader(
        name="Root",
        invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0),
    )

    child = SingleModule(
        header=ModuleHeader(
            name="M1",
            invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0),
        ),
        moduledef=None,
        moduleparameters=[Variable(name="X", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="x", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=bp_header,
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(i.kind is IssueKind.NAME_COLLISION for i in analyzer.issues)


def test_access_graph_indexes_events_by_casefolded_canonical_path():
    graph = AccessGraph()
    read_event = AccessEvent(
        kind=AccessKind.READ,
        canonical_path=CanonicalPath(("Root", "Signal")),
        use_module_path=("Root",),
        use_display_path=("Root",),
        syntactic_ref="Signal",
    )
    write_event = AccessEvent(
        kind=AccessKind.WRITE,
        canonical_path=CanonicalPath(("root", "signal")),
        use_module_path=("Root",),
        use_display_path=("Root",),
        syntactic_ref="signal",
    )

    graph.add(read_event)
    graph.add(write_event)

    assert graph.events == [read_event, write_event]
    assert graph.by_path_key[("root", "signal")] == [read_event, write_event]


def test_resolution_path_helpers_cover_display_join_and_decorators():
    path = CanonicalPath(("Root", "Signal"))

    assert path.key() == ("root", "signal")
    assert path.join() is path
    assert path.join("Field").segments == ("Root", "Signal", "Field")
    assert str(path) == "Root.Signal"

    assert ModuleSegment(name="PumpType", kind="MT", moduletype_name="Motor").display() == "PumpType<MT:Motor>"
    assert ModuleSegment(name="Single", kind="SM").display() == "Single<SM>"
    assert ModuleSegment(name="Frame", kind="FM").display() == "Frame<FM>"
    assert ModuleSegment(name="TypeDef", kind="TD").display() == "TypeDef<TD>"
    assert ModuleSegment(name="Base", kind="BP").display() == "Base<BP>"
    assert ModuleSegment(name="Other", kind="MT").display() == "Other"

    assert decorate_segment("PumpType", "MT", "Motor") == "PumpType<MT:Motor>"
    assert decorate_segment("Single", "SM") == "Single<SM>"
    assert decorate_segment("Frame", "FM") == "Frame<FM>"
    assert decorate_segment("TypeDef", "TD") == "TypeDef<TD>"
    assert decorate_segment("Base", "BP") == "Base<BP>"
    assert decorate_segment("Other", "MT") == "Other"


def test_type_graph_reuses_cached_builtin_record_shells():
    left = TypeGraph.from_datatypes(())
    right = TypeGraph.from_datatypes(())

    builtin_name = next(iter(left._records_by_key.values())).name

    assert left.record(builtin_name) is right.record(builtin_name)
