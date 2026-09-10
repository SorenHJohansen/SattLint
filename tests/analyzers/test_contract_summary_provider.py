# pyright: reportPrivateUsage=false
from types import MappingProxyType

import pytest
from sattline_parser.models.ast_model import (
    Assignment,
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
from sattline_parser.models.expressions import VarRef

from sattlint import constants as const
from sattlint.analyzers.framework._shared_analysis import AnalysisSharedArtifacts
from sattlint.analyzers.shared._contract_index import (
    ContractIndex,
    ContractIndexKey,
)
from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.analyzers.variables._contract_summary_provider import ContractSummaryProvider


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> VarRef:
    return VarRef(name=name)


def _eq(code: list[object]) -> Equation:
    return Equation(
        name="E1",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=code,  # pyright: ignore[reportArgumentType]
    )


def _required_names_legacy(analyzer: VariablesAnalyzer, mt: ModuleTypeDef) -> set[str]:
    return set(analyzer._get_required_parameter_names_for_typedef(mt).keys())


def _required_names_provider(provider: ContractSummaryProvider, mt: ModuleTypeDef) -> set[str]:
    contract = provider.get(mt)
    return {key for key, effect in contract.effects_by_parameter.items() if effect.required}


def _nested_picture() -> BasePicture:
    leaf = ModuleTypeDef(
        name="Leaf",
        moduleparameters=[
            Variable(name="ReadIn", datatype=Simple_DataType.INTEGER),
            Variable(name="Out", datatype=Simple_DataType.INTEGER),
            Variable(name="UiOnly", datatype=Simple_DataType.INTEGER),
        ],
        localvariables=[Variable(name="Buf", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        Assignment(target=_varref("Buf"), value=_varref("ReadIn")),
                        Assignment(target=_varref("Out"), value=_varref("Buf")),
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    parent = ModuleTypeDef(
        name="Parent",
        moduleparameters=[Variable(name="PIn", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="PBuf", datatype=Simple_DataType.INTEGER)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("LeafInst"),
                moduletype_name="Leaf",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("ReadIn"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("PBuf"),
                        source_literal=None,
                    ),
                    ParameterMapping(
                        target=_varref("Out"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("PIn"),
                        source_literal=None,
                    ),
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                _eq(
                    [
                        Assignment(target=_varref("PBuf"), value=_varref("PIn")),
                    ]
                )
            ]
        ),
        parametermappings=[],
    )

    root = ModuleTypeInstance(
        header=_hdr("RootLeaf"),
        moduletype_name="Parent",
        parametermappings=[
            ParameterMapping(
                target=_varref("PIn"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("RootIn"),
                source_literal=None,
            )
        ],
    )

    return BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[leaf, parent],
        localvariables=[Variable(name="RootIn", datatype=Simple_DataType.INTEGER)],
        submodules=[root],
        moduledef=None,
        modulecode=None,
    )


def test_provider_required_names_match_legacy_for_acyclic_typedefs() -> None:
    bp = _nested_picture()
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    provider = ContractSummaryProvider(
        bp,
        collector_class=VariablesAnalyzer,
        unavailable_libraries=None,
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
    )

    assert len(bp.moduletype_defs) >= 2
    for mt in bp.moduletype_defs:
        legacy = _required_names_legacy(analyzer, mt)
        provider_names = _required_names_provider(provider, mt)
        assert provider_names == legacy, f"typedef {mt.name}: provider={provider_names} legacy={legacy}"


def test_provider_read_and_write_flags_match_legacy() -> None:
    bp = _nested_picture()
    # Legacy read-out lives on param_reads_by_typedef / param_writes_by_typedef after a run.
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    provider = ContractSummaryProvider(
        bp,
        collector_class=VariablesAnalyzer,
        unavailable_libraries=None,
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
    )

    leaf = next(mt for mt in bp.moduletype_defs if mt.name == "Leaf")
    contract = provider.get(leaf)
    read_effect = contract.effect("ReadIn")
    assert read_effect is not None
    assert read_effect.read is True
    assert read_effect.written is False
    out_effect = contract.effect("Out")
    assert out_effect is not None
    assert out_effect.read is True or out_effect.written is True

    lk = next(iter(analyzer.param_reads_by_typedef.get("leaf", set())))
    assert lk is not None


def test_provider_recursive_typedef_does_not_hang() -> None:
    recursive = ModuleTypeDef(
        name="Rec",
        moduleparameters=[Variable(name="Self", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="L", datatype=Simple_DataType.INTEGER)],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("RecInst"),
                moduletype_name="Rec",
                parametermappings=[
                    ParameterMapping(
                        target=_varref("Self"),
                        source_type=const.TREE_TAG_VARIABLE_NAME,
                        is_duration=False,
                        is_source_global=False,
                        source=_varref("L"),
                        source_literal=None,
                    )
                ],
            )
        ],
        moduledef=None,
        modulecode=ModuleCode(equations=[_eq([Assignment(target=_varref("L"), value=_varref("Self"))])]),
        parametermappings=[],
    )
    bp = BasePicture(
        header=_hdr("Root"),
        moduletype_defs=[recursive],
        localvariables=[],
        submodules=[
            ModuleTypeInstance(
                header=_hdr("RecRoot"),
                moduletype_name="Rec",
                parametermappings=[],
            )
        ],
        moduledef=None,
        modulecode=None,
    )

    provider = ContractSummaryProvider(
        bp,
        collector_class=VariablesAnalyzer,
        unavailable_libraries=None,
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
    )
    contract = provider.get(recursive)
    assert contract is not None


def test_ensure_contract_index_builds_once_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    shared = AnalysisSharedArtifacts()
    build_calls: list[int] = []

    def _make(generation: int) -> ContractIndex:
        build_calls.append(generation)
        return ContractIndex(
            snapshot_generation=generation,
            entries_by_owner_id=MappingProxyType({}),
            cyclic_owner_ids=frozenset(),
        )

    k1 = ContractIndexKey(
        unavailable_libraries=frozenset(),
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        semantics_flavor="variable",
    )
    k2 = ContractIndexKey(
        unavailable_libraries=frozenset(),
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        semantics_flavor="other",
    )

    first = shared.ensure_contract_index(k1, lambda: _make(1))
    second = shared.ensure_contract_index(k1, lambda: _make(999))
    assert first is not None and second is first
    assert first.snapshot_generation == 1

    other = shared.ensure_contract_index(k2, lambda: _make(2))
    assert other is not None and other is not first
    assert other.snapshot_generation == 2

    assert build_calls == [1, 2]
