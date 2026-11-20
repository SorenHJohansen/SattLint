# pyright: reportPrivateUsage=false
"""Variables mapped into a child outside the analyzed origin are consumed.

The child's contract is real but its definition is not the analyzed origin, so the
analyzer cannot see the read. Only ``unused`` and ``never_read`` are suppressed; no
read or write mark is fabricated for the mapping actual.
"""

from __future__ import annotations

import pytest
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
    Variable,
)

from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.reporting.variables_report import VariableTargetIssue
from tests.helpers.variable_test_support import hdr as _hdr
from tests.helpers.variable_test_support import varref as _varref

ROOT_ORIGIN = "KaHCBInlineLib.s"


def _mapping(target: str, source: str, *, is_global: bool = False) -> ParameterMapping:
    return ParameterMapping(
        target=_varref(target),
        source=_varref(source),
        source_type=MappingSource.VARIABLE,
        is_source_global=is_global,
        is_duration=False,
        source_literal=None,
    )


def _opaque_dependency_type(name: str = "EquipModPanelShort") -> ModuleTypeDef:
    """A dependency-owned type whose body never references its parameter."""
    return ModuleTypeDef(
        name=name,
        moduleparameters=[Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file="nnestruct.x",
        origin_lib="nnestruct",
    )


def _opaque_dependency_type_with(*parameters: str) -> ModuleTypeDef:
    """A dependency-owned type with several formals, all unused in its body."""
    return ModuleTypeDef(
        name="EquipModPanelShort",
        moduleparameters=[Variable(name=name, datatype=ScalarDatatype.INTEGER) for name in parameters],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file="nnestruct.x",
        origin_lib="nnestruct",
    )


def _root_owned_type(name: str = "LocalPanel") -> ModuleTypeDef:
    """A type in the analyzed origin, so its body is authoritative."""
    return ModuleTypeDef(
        name=name,
        moduleparameters=[Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file=ROOT_ORIGIN,
    )


def _base_picture(submodules: list[SingleModule | FrameModule], *types: ModuleTypeDef) -> BasePicture:
    return BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=list(types),
        localvariables=[],
        submodules=list(submodules),
        modulecode=None,
        moduledef=None,
        origin_file=ROOT_ORIGIN,
    )


def _run(
    base_picture: BasePicture,
    kinds: frozenset[IssueKind] = frozenset({IssueKind.UNUSED, IssueKind.NEVER_READ}),
) -> VariablesAnalyzer:
    analyzer = VariablesAnalyzer(base_picture, selected_issue_kinds=kinds)
    analyzer.run()
    return analyzer


def _reported(analyzer: VariablesAnalyzer, kind: IssueKind, variable: Variable) -> bool:
    return any(
        issue.kind is kind and isinstance(issue, VariableTargetIssue) and issue.variable is variable
        for issue in analyzer.issues
    )


@pytest.mark.parametrize("is_global", [False, True])
def test_unused_local_mapped_into_dependency_child_is_not_reported(is_global: bool) -> None:
    state = Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Panel1"),
        moduletype_name="EquipModPanelShort",
        parametermappings=[_mapping("CurrentState", "CurrentState", is_global=is_global)],
    )
    filling = SingleModule(
        header=_hdr("Fyldning"),
        localvariables=[state],
        submodules=[instance],
    )
    analyzer = _run(_base_picture([filling], _opaque_dependency_type()))

    assert not _reported(analyzer, IssueKind.UNUSED, state)
    # The suppression must not fabricate a read: the analyzer still knows nothing.
    assert analyzer.get_usage(state).is_unused is True


def test_unused_module_parameter_mapped_into_dependency_child_is_not_reported() -> None:
    state = Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Panel1"),
        moduletype_name="EquipModPanelShort",
        parametermappings=[_mapping("CurrentState", "CurrentState")],
    )
    filling = SingleModule(
        header=_hdr("Fyldning"),
        moduleparameters=[state],
        submodules=[instance],
    )
    analyzer = _run(_base_picture([filling], _opaque_dependency_type()))

    assert not _reported(analyzer, IssueKind.UNUSED, state)
    assert analyzer.get_usage(state).is_unused is True


def test_never_read_local_mapped_into_dependency_child_is_not_reported() -> None:
    state = Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Panel1"),
        moduletype_name="EquipModPanelShort",
        parametermappings=[_mapping("CurrentState", "CurrentState")],
    )
    filling = SingleModule(
        header=_hdr("Fyldning"),
        localvariables=[state],
        submodules=[instance],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Publish",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("CurrentState"), value=IntLiteral(1))],
                )
            ]
        ),
    )
    analyzer = _run(_base_picture([filling], _opaque_dependency_type()))

    assert not _reported(analyzer, IssueKind.NEVER_READ, state)
    assert analyzer.get_usage(state).written is True
    assert analyzer.get_usage(state).read is False


def test_unused_local_mapped_into_unresolved_child_is_not_reported() -> None:
    state = Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Panel1"),
        moduletype_name="MissingPanelType",
        parametermappings=[_mapping("CurrentState", "CurrentState")],
    )
    filling = SingleModule(
        header=_hdr("Fyldning"),
        localvariables=[state],
        submodules=[instance],
    )
    analyzer = _run(_base_picture([filling]))

    assert not _reported(analyzer, IssueKind.UNUSED, state)
    # An unresolved child is treated as an external contract, so the actual keeps
    # the conservative read+write marks the external mapping policy already applies.
    assert analyzer.get_usage(state).read is True
    assert analyzer.get_usage(state).written is True


def test_mapping_actual_resolves_through_ancestors_of_a_frame_scope() -> None:
    state = Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Gauge"),
        moduletype_name="EquipModPanelShort",
        parametermappings=[_mapping("CurrentState", "CurrentState")],
    )
    nested = SingleModule(header=_hdr("Nested"), submodules=[instance])
    panel = FrameModule(header=_hdr("Panel"), submodules=[nested])
    filling = SingleModule(header=_hdr("Fyldning"), localvariables=[state], submodules=[panel])
    analyzer = _run(_base_picture([filling], _opaque_dependency_type()))

    assert not _reported(analyzer, IssueKind.UNUSED, state)
    assert analyzer.get_usage(state).is_unused is True


def test_in_scope_child_keeps_reporting_an_ignored_mapping_actual() -> None:
    state = Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Panel1"),
        moduletype_name="LocalPanel",
        parametermappings=[_mapping("CurrentState", "CurrentState")],
    )
    filling = SingleModule(
        header=_hdr("Fyldning"),
        localvariables=[state],
        submodules=[instance],
    )
    analyzer = _run(_base_picture([filling], _root_owned_type()))

    assert _reported(analyzer, IssueKind.UNUSED, state)


def test_read_only_non_const_is_untouched_by_the_consumer_rule() -> None:
    consumed = Variable(name="Level", datatype=ScalarDatatype.INTEGER)
    sink = Variable(name="Scratch", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Gauge"),
        moduletype_name="EquipModPanelShort",
        parametermappings=[_mapping("CurrentState", "Level")],
    )
    filling = SingleModule(
        header=_hdr("Fyldning"),
        localvariables=[consumed, sink],
        submodules=[instance],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Copy",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("Scratch"), value=_varref("Level"))],
                )
            ]
        ),
    )
    analyzer = _run(
        _base_picture([filling], _opaque_dependency_type()),
        frozenset({IssueKind.READ_ONLY_NON_CONST}),
    )

    assert _reported(analyzer, IssueKind.READ_ONLY_NON_CONST, consumed)


def test_unused_base_picture_locals_mapped_into_dependency_child_are_not_reported() -> None:
    unwritten = Variable(name="RootState", datatype=ScalarDatatype.INTEGER)
    written = Variable(name="RootWritten", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Panel1"),
        moduletype_name="EquipModPanelShort",
        parametermappings=[
            _mapping("First", "RootState"),
            _mapping("Second", "RootWritten"),
        ],
    )
    filling = SingleModule(header=_hdr("Fyldning"), submodules=[instance])
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[_opaque_dependency_type_with("First", "Second")],
        localvariables=[unwritten, written],
        submodules=[filling],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Publish",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("RootWritten"), value=IntLiteral(1))],
                )
            ]
        ),
        moduledef=None,
        origin_file=ROOT_ORIGIN,
    )
    analyzer = _run(bp)

    assert not _reported(analyzer, IssueKind.UNUSED, unwritten)
    assert not _reported(analyzer, IssueKind.NEVER_READ, written)
    assert analyzer.get_usage(unwritten).is_unused is True
    assert analyzer.get_usage(written).read is False


def test_unused_typedef_members_mapped_into_dependency_child_are_not_reported() -> None:
    parameter = Variable(name="Level", datatype=ScalarDatatype.INTEGER)
    local = Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)
    written = Variable(name="Published", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Panel1"),
        moduletype_name="EquipModPanelShort",
        parametermappings=[
            _mapping("First", "Level"),
            _mapping("Second", "CurrentState"),
            _mapping("Third", "Published"),
        ],
    )
    root_type = ModuleTypeDef(
        name="RootPanel",
        moduleparameters=[parameter],
        localvariables=[local, written],
        submodules=[instance],
        moduledef=None,
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="Publish",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("Published"), value=IntLiteral(1))],
                )
            ]
        ),
        origin_file=ROOT_ORIGIN,
    )
    bp = _base_picture([], root_type, _opaque_dependency_type_with("First", "Second", "Third"))
    analyzer = _run(bp)

    assert not _reported(analyzer, IssueKind.UNUSED, parameter)
    assert not _reported(analyzer, IssueKind.UNUSED, local)
    assert not _reported(analyzer, IssueKind.NEVER_READ, written)
    assert analyzer.get_usage(parameter).is_unused is True
    assert analyzer.get_usage(local).is_unused is True


def test_out_of_origin_consumer_evidence_is_reset_between_runs() -> None:
    state = Variable(name="CurrentState", datatype=ScalarDatatype.INTEGER)
    instance = ModuleTypeInstance(
        header=_hdr("Panel1"),
        moduletype_name="EquipModPanelShort",
        parametermappings=[_mapping("CurrentState", "CurrentState")],
    )
    filling = SingleModule(header=_hdr("Fyldning"), localvariables=[state], submodules=[instance])
    analyzer = _run(_base_picture([filling], _opaque_dependency_type()))
    assert not _reported(analyzer, IssueKind.UNUSED, state)

    filling.submodules.clear()
    analyzer.run()

    assert _reported(analyzer, IssueKind.UNUSED, state)
