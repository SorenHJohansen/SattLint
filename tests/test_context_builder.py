from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.reporting.variables_report import IssueKind
from sattlint.resolution.context_builder import ContextBuilder
from sattlint.resolution.scope import ScopeContext
from sattlint.resolution.symbol_table import CanonicalSymbolTable
from sattlint.resolution.type_graph import TypeGraph


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _builder(base_picture: BasePicture):
    issues = []
    return (
        ContextBuilder(
            base_picture=base_picture,
            symbol_table=CanonicalSymbolTable(),
            type_graph=TypeGraph.from_basepicture(base_picture),
            issues=issues,
            global_lookup_fn=lambda _name: None,
        ),
        issues,
    )


def test_build_for_single_skips_empty_non_global_sources() -> None:
    base_picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Outer", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    builder, issues = _builder(base_picture)
    parent_context = builder.build_for_basepicture()
    module = SingleModule(
        header=_hdr("Worker"),
        moduledef=None,
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target={"var_name": "Input"},
                source_type="value",
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=None,
            )
        ],
    )

    context = builder.build_for_single(
        module,
        parent_context,
        module_path=["Root", "Worker"],
        display_module_path=["Root<BP>", "Worker<SM>"],
    )

    assert context.param_mappings == {}
    assert issues == []


def test_build_for_typedef_reports_name_collisions_and_skips_empty_sources() -> None:
    shared_param = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
    shared_local = Variable(name="Shared", datatype=Simple_DataType.INTEGER)
    base_picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Outer", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    builder, issues = _builder(base_picture)
    parent_context = ScopeContext(
        env={"outer": base_picture.localvariables[0]},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root<BP>"],
        current_library="ProjectLib",
        parent_context=None,
    )
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[shared_param],
        localvariables=[shared_local],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    instance = ModuleTypeInstance(
        header=_hdr("Worker"),
        moduletype_name="WorkerType",
        parametermappings=[
            ParameterMapping(
                target={"var_name": "Shared"},
                source_type="value",
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=None,
            )
        ],
    )

    context = builder.build_for_typedef(
        moduletype,
        instance,
        parent_context=parent_context,
        module_path=["Root", "Worker"],
        display_module_path=["Root<BP>", "Worker<MT:WorkerType>"],
    )

    assert context.param_mappings == {}
    assert len(issues) == 1
    assert issues[0].kind is IssueKind.NAME_COLLISION
    assert issues[0].variable is shared_local
    assert issues[0].source_variable is shared_param


def test_build_for_typedef_without_parent_context_skips_source_resolution() -> None:
    base_picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    builder, issues = _builder(base_picture)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )
    instance = ModuleTypeInstance(
        header=_hdr("Worker"),
        moduletype_name="WorkerType",
        parametermappings=[
            ParameterMapping(
                target={"var_name": "Input"},
                source_type="var_name",
                is_duration=False,
                is_source_global=False,
                source={"var_name": "Outer"},
                source_literal=None,
            )
        ],
    )

    context = builder.build_for_typedef(
        moduletype,
        instance,
        parent_context=None,
        module_path=["Root", "Worker"],
        display_module_path=["Root<BP>", "Worker<MT:WorkerType>"],
    )

    assert context.param_mappings == {}
    assert issues == []
