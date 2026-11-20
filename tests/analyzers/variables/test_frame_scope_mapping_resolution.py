# pyright: reportPrivateUsage=false
"""Mapping actuals resolve through the scope chain, not only the immediate parent.

A frame's environment holds only its own declarations, so a mapping declared inside
a frame names an actual that lives in an ancestor. Resolving through the scope
context finds it; the immediate parent environment and the global index stay as
fallbacks.
"""

from __future__ import annotations

from sattline_parser.ast import MappingSource
from sattline_parser.models.ast_model import (
    Assignment,
    BasePicture,
    Equation,
    FrameModule,
    IntLiteral,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    ScalarDatatype,
    SingleModule,
    SLExpression,
    Variable,
)

from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.models.usage import AccessKind
from tests.analyzers.variables.test_variables_effect_flow import build_tracker, scope_context
from tests.helpers.variable_test_support import hdr as _hdr
from tests.helpers.variable_test_support import varref as _varref

ROOT_ORIGIN = "RootLib.s"


def _mapping(target: str, source: str) -> ParameterMapping:
    return ParameterMapping(
        target=_varref(target),
        source=_varref(source),
        source_type=MappingSource.VARIABLE,
        is_source_global=False,
        is_duration=False,
        source_literal=None,
    )


def _equation(name: str, target: str, value: SLExpression) -> Equation:
    return Equation(
        name=name,
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[Assignment(target=_varref(target), value=value)],
    )


def _meter_type(*, reads_input: bool, dependency: bool = False) -> ModuleTypeDef:
    return ModuleTypeDef(
        name="Meter",
        moduleparameters=[Variable(name="Input", datatype=ScalarDatatype.INTEGER)],
        localvariables=[Variable(name="Observed", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[_equation("Read", "Observed", _varref("Input") if reads_input else IntLiteral(0))]
        ),
        origin_file="DependencyLib.s" if dependency else ROOT_ORIGIN,
        origin_lib="DependencyLib" if dependency else None,
    )


def test_propagate_mapping_resolves_an_ancestor_actual_with_its_declaration_path() -> None:
    actual = Variable(name="Signal", datatype=ScalarDatatype.INTEGER)
    formal = Variable(name="Input", datatype=ScalarDatatype.INTEGER)
    tracker, edges, _external, usage_by_name, access_calls = build_tracker()
    vessel = scope_context(env={"signal": actual}, module_path=["Root", "Vessel"])
    frame = scope_context(env={}, module_path=["Root", "Vessel", "Panel"], parent_context=vessel)
    child_context = scope_context(env={"input": formal}, module_path=["Root", "Vessel", "Panel", "Gauge"])

    tracker.propagate_mapping_to_parent(
        pm=_mapping("Input", "Signal"),
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes=set(),
        # A frame's own environment holds only its own declarations.
        parent_env={},
        parent_path=["Root", "Vessel", "Panel"],
        external_typename=None,
        parent_context=frame,
        child_context=child_context,
    )

    assert usage_by_name["Signal"].read_paths == [("Root", "Vessel")]
    assert edges == {
        ("root", "vessel", "signal"): {("root", "vessel", "panel", "gauge", "input")},
    }
    assert access_calls == []


def test_external_mapping_records_the_ancestor_declaration_path() -> None:
    actual = Variable(name="Signal", datatype=ScalarDatatype.INTEGER)
    tracker, _edges, _external, usage_by_name, access_calls = build_tracker()
    vessel = scope_context(env={"signal": actual}, module_path=["Root", "Vessel"])
    frame = scope_context(env={}, module_path=["Root", "Vessel", "Panel"], parent_context=vessel)

    tracker.propagate_mapping_to_parent(
        pm=_mapping("Input", "Signal"),
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Vessel", "Panel"],
        external_typename="OpaqueType",
        parent_context=frame,
    )

    assert usage_by_name["Signal"].read_paths == [("Root", "Vessel")]
    assert usage_by_name["Signal"].write_paths == [("Root", "Vessel")]
    assert [call[2] for call in access_calls] == [("Root", "Vessel"), ("Root", "Vessel")]


def _frame_picture(
    *,
    reads_input: bool,
    formal_datatype: ScalarDatatype,
    dependency: bool = False,
) -> tuple[BasePicture, Variable]:
    actual = Variable(name="Signal", datatype=ScalarDatatype.STRING)
    instance = ModuleTypeInstance(
        header=_hdr("Gauge"),
        moduletype_name="Meter",
        parametermappings=[_mapping("Input", "Signal")],
    )
    frame_child = SingleModule(header=_hdr("Wrap"), submodules=[instance])
    panel = FrameModule(header=_hdr("Panel"), submodules=[frame_child])
    vessel = SingleModule(
        header=_hdr("Vessel"),
        localvariables=[actual],
        submodules=[panel],
        modulecode=ModuleCode(
            equationblocks=[_equation("Publish", "Signal", IntLiteral(1))],
        ),
    )
    meter = _meter_type(reads_input=reads_input, dependency=dependency)
    meter.moduleparameters = [Variable(name="Input", datatype=formal_datatype)]
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[meter],
        localvariables=[],
        submodules=[vessel],
        modulecode=None,
        moduledef=None,
        origin_file=ROOT_ORIGIN,
        origin_lib="RootLib" if dependency else None,
    )
    return bp, actual


def test_frame_scoped_mapping_marks_an_ancestor_actual_as_read() -> None:
    bp, actual = _frame_picture(reads_input=True, formal_datatype=ScalarDatatype.STRING)
    analyzer = VariablesAnalyzer(
        bp,
        selected_issue_kinds=frozenset({IssueKind.UNUSED, IssueKind.NEVER_READ}),
    )
    analyzer.run()

    assert analyzer.get_usage(actual).read is True
    assert not any(issue.kind is IssueKind.UNUSED and issue.variable is actual for issue in analyzer.issues)


def test_frame_scoped_external_mapping_records_the_ancestor_declaration_path() -> None:
    # The foreign contract is not analyzed, so nothing else marks the actual: only
    # resolving the mapping through the frame scope finds it.
    bp, actual = _frame_picture(
        reads_input=True,
        formal_datatype=ScalarDatatype.STRING,
        dependency=True,
    )
    analyzer = VariablesAnalyzer(
        bp,
        analyzed_target_is_library=True,
        include_dependency_moduletype_usage=False,
        selected_issue_kinds=frozenset({IssueKind.UNUSED, IssueKind.NEVER_READ}),
    )
    analyzer.run()

    usage = analyzer.get_usage(actual)
    assert usage.read is True
    assert usage.written is True
    assert usage.usage_locations == [
        (["BasePicture", "Vessel"], AccessKind.WRITE),
        (["BasePicture", "Vessel"], AccessKind.READ),
        (["BasePicture", "Vessel"], AccessKind.WRITE),
    ]


def test_frame_scoped_mapping_contract_check_uses_the_ancestor_declaration() -> None:
    # The formal is an identstring and the ancestor actual is a string, so the
    # mapping narrows; the check can only see it once the actual is resolved.
    bp, _actual = _frame_picture(reads_input=False, formal_datatype=ScalarDatatype.IDENTSTRING)
    analyzer = VariablesAnalyzer(bp, selected_issue_kinds=frozenset({IssueKind.STRING_MAPPING_MISMATCH}))
    analyzer.run()

    issues = [issue for issue in analyzer.issues if issue.kind is IssueKind.STRING_MAPPING_MISMATCH]
    assert len(issues) == 1
    assert issues[0].source_decl_module_path == ["BasePicture", "Vessel"]
