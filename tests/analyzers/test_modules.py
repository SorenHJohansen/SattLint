import logging

import pytest
from sattline_parser.ast import MappingSource, ParameterMapping, SourceSpan
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    IntLiteral,
    ModuleCode,
    ModuleHeader,
    ScalarDatatype,
    SingleModule,
    Variable,
)
from sattline_parser.models.expressions import Assignment, VarRef

from sattlint.analyzers.modules import (
    CodeDiff,
    ComparisonResult,
    SubmoduleDiff,
    VariableDiff,
    compare_modules,
    compare_variable_lists,
    create_fingerprint,
    find_modules_by_name,
)
from sattlint.analyzers.registry import get_default_analyzers


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def test_variable_difference_ignores_declaration_location() -> None:
    modules = [
        SingleModule(
            header=_hdr("Panel"),
            moduleparameters=[
                Variable(
                    name="Name",
                    datatype=ScalarDatatype.IDENTSTRING,
                    declaration_span=SourceSpan(start=line * 10, end=line * 10 + 4, line=line, column=1),
                )
            ],
        )
        for line in (10, 50)
    ]
    diff = compare_variable_lists([create_fingerprint(module, ["Root", "Panel"]) for module in modules])
    assert diff.common == ["Name"]
    assert diff.modified == {}


def test_module_comparison_summary_lists_variant_differences() -> None:
    variant_a = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[Variable(name="CommonParam", datatype=ScalarDatatype.INTEGER)],
        localvariables=[Variable(name="OnlyA", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="MainEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("OnlyA"), value=IntLiteral(1))],
                )
            ]
        ),
        parametermappings=[],
    )
    variant_b = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[Variable(name="CommonParam", datatype=ScalarDatatype.INTEGER)],
        localvariables=[Variable(name="OnlyB", datatype=ScalarDatatype.INTEGER)],
        submodules=[],
        modulecode=ModuleCode(
            equationblocks=[
                Equation(
                    name="OtherEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[Assignment(target=_varref("OnlyB"), value=IntLiteral(2))],
                )
            ]
        ),
        parametermappings=[],
    )
    fingerprint_a = create_fingerprint(variant_a, ["Root", "PumpA"])
    fingerprint_b = create_fingerprint(variant_b, ["Root", "PumpB"])

    summary = ComparisonResult(
        module_name="Pump",
        total_found=2,
        unique_variants=2,
        fingerprints=[fingerprint_a, fingerprint_b],
        all_instances=[(["Root", "PumpA"], fingerprint_a), (["Root", "PumpB"], fingerprint_b)],
        parameter_diff=VariableDiff(common=["CommonParam"], only_in_variant={1: [], 2: []}),
        localvar_diff=VariableDiff(common=[], only_in_variant={1: ["OnlyA"], 2: ["OnlyB"]}),
        submodule_diff=SubmoduleDiff(common=[(0, "SharedChild", "Single")], only_in_variant={1: [], 2: []}),
        code_diff=CodeDiff(
            sequences_common=[],
            sequences_only_in_variant={1: [], 2: []},
            equations_common=[],
            equations_only_in_variant={1: ["MainEq"], 2: ["OtherEq"]},
        ),
    ).summary()

    assert "Found 2 different structural variants" in summary
    assert "Submodules Differences (Recursive Tree)" in summary
    assert "Equations Only in Variant 1 (1): ['MainEq']" in summary


def test_fingerprint_treats_mappings_that_differ_only_by_span_as_one_variant() -> None:
    def _mapping(span: SourceSpan) -> ParameterMapping:
        return ParameterMapping(
            target=VarRef(name="Input", span=span),
            source_type=MappingSource.VARIABLE,
            is_duration=False,
            is_source_global=False,
            source=VarRef(name="Outer", span=span),
            source_literal=None,
        )

    def _module(span: SourceSpan) -> SingleModule:
        return SingleModule(
            header=_hdr("Pump"),
            moduledef=None,
            moduleparameters=[Variable(name="Input", datatype=ScalarDatatype.INTEGER)],
            localvariables=[],
            submodules=[],
            modulecode=None,
            parametermappings=[_mapping(span)],
        )

    first = _module(SourceSpan(start=10, end=20, line=1, column=11))
    second = _module(SourceSpan(start=90, end=100, line=7, column=5))

    result = compare_modules([(["Root", "PumpA"], first), (["Root", "PumpB"], second)])

    assert result.total_found == 2
    assert result.unique_variants == 1


def test_modules_analyzer_is_enabled_by_default() -> None:
    specs = {spec.key: spec for spec in get_default_analyzers()}
    module = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    assert "version-drift" in specs
    assert specs["version-drift"].enabled is True
    assert compare_modules([(["Root", "Area", "PumpA"], module)]).module_name == "Pump"


def test_find_modules_by_name_debug_logs_summary_without_per_node_chatter(caplog: pytest.LogCaptureFixture) -> None:
    pump_a = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    pump_b = SingleModule(
        header=_hdr("Pump"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )
    area = SingleModule(
        header=_hdr("Area"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[],
        submodules=[pump_a, pump_b],
        modulecode=None,
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[area],
        modulecode=None,
        moduledef=None,
    )

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        matches = find_modules_by_name(bp, "Pump", debug=True)

    assert len(matches) == 2
    assert "Module search start: target='Pump' root='Root'" in caplog.messages
    assert any(message.startswith("Module search complete: target='Pump' visited=") for message in caplog.messages)
    assert any("matches=2" in message for message in caplog.messages)
    assert any(
        message == "Module search matches: Root -> Area -> Pump; Root -> Area -> Pump" for message in caplog.messages
    )
    assert not any("_walk_modules:" in message for message in caplog.messages)
    assert not any("Submodule[" in message for message in caplog.messages)
