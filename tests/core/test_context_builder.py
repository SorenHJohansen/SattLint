# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportUnknownArgumentType=false
from __future__ import annotations

from sattline_parser.ast import MappingSource
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
from sattline_parser.models.expressions import VarRef

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
        modulecodes=[],
        moduledefs=[],
    )
    builder, issues = _builder(base_picture)
    parent_context = builder.build_for_basepicture()
    module = SingleModule(
        header=_hdr("Worker"),
        moduledefs=[],
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecodes=[],
        parametermappings=[
            ParameterMapping(
                target=VarRef(name="Input"),
                source_type=MappingSource.VALUE,
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


def test_build_for_basepicture_registers_moduleparameters() -> None:
    base_picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Local", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
    )
    builder, issues = _builder(base_picture)

    context = builder.build_for_basepicture()

    parameter, _field_path, _decl_path, _display = context.resolve_variable("Input")
    local, _local_field, _local_decl, _local_display = context.resolve_variable("Local")
    assert parameter is not None and parameter.name == "Input"
    assert local is not None and local.name == "Local"
    assert context.moduleparameter_keys == {"input"}
    assert issues == []


def test_build_for_typedef_without_parent_context_skips_source_resolution() -> None:
    base_picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
    )
    builder, issues = _builder(base_picture)
    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
    )
    instance = ModuleTypeInstance(
        header=_hdr("Worker"),
        moduletype_name="WorkerType",
        parametermappings=[
            ParameterMapping(
                target=VarRef(name="Input"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=VarRef(name="Outer"),
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


def test_build_for_basepicture_uses_explicit_root_library() -> None:
    base_picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Outer", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
    )
    builder = ContextBuilder(
        base_picture=base_picture,
        symbol_table=CanonicalSymbolTable(),
        type_graph=TypeGraph.from_basepicture(base_picture),
        issues=[],
        global_lookup_fn=lambda _name: None,
        root_library="ProjectLib",
    )

    context = builder.build_for_basepicture()

    assert context.current_library == "ProjectLib"


def test_build_for_typedef_reuses_cached_template_for_equivalent_mappings() -> None:
    outer = Variable(name="Outer", datatype=Simple_DataType.INTEGER)
    base_picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[outer],
        submodules=[],
        modulecodes=[],
        moduledefs=[],
    )
    builder, issues = _builder(base_picture)
    parent_context = ScopeContext(
        env={"outer": outer},
        param_mappings={},
        module_path=["Root"],
        display_module_path=["Root<BP>"],
        current_library="ProjectLib",
        parent_context=None,
    )
    calls = {"count": 0}

    def _resolve_variable(_var_ref: str):
        calls["count"] += 1
        return outer, "", ["Root"], ["Root<BP>"]

    parent_context.resolve_variable = _resolve_variable  # type: ignore[method-assign]

    moduletype = ModuleTypeDef(
        name="WorkerType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Buffer", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledefs=[],
        modulecodes=[],
        parametermappings=[],
    )
    instance = ModuleTypeInstance(
        header=_hdr("Worker"),
        moduletype_name="WorkerType",
        parametermappings=[
            ParameterMapping(
                target=VarRef(name="Input"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=VarRef(name="Outer"),
                source_literal=None,
            )
        ],
    )

    first = builder.build_for_typedef(
        moduletype,
        instance,
        parent_context=parent_context,
        module_path=["Root", "Worker"],
        display_module_path=["Root<BP>", "Worker<MT:WorkerType>"],
    )
    second = builder.build_for_typedef(
        moduletype,
        instance,
        parent_context=parent_context,
        module_path=["Root", "Worker"],
        display_module_path=["Root<BP>", "Worker<MT:WorkerType>"],
    )

    assert calls["count"] == 1
    assert first.env is second.env
    assert first.param_mappings is second.param_mappings
    assert first.param_mappings["input"][0] is outer
    assert issues == []


def test_resolve_variable_in_scope_uses_parent_scope_context() -> None:
    base_picture = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[
            ModuleTypeDef(
                name="WorkerType",
                moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
                localvariables=[Variable(name="Inner", datatype=Simple_DataType.INTEGER)],
                submodules=[],
                moduledefs=[],
                modulecodes=[],
                parametermappings=[],
            )
        ],
        localvariables=[Variable(name="Outer", datatype=Simple_DataType.INTEGER)],
        submodules=[
            SingleModule(
                header=_hdr("Parent"),
                moduleparameters=[Variable(name="ParentValue", datatype=Simple_DataType.INTEGER)],
                localvariables=[],
                submodules=[
                    ModuleTypeInstance(
                        header=_hdr("Worker"),
                        moduletype_name="WorkerType",
                        parametermappings=[],
                    )
                ],
                moduledefs=[],
                modulecodes=[],
                parametermappings=[],
            )
        ],
        modulecodes=[],
        moduledefs=[],
    )

    assert (
        ContextBuilder.resolve_variable_in_scope(base_picture, ["Root", "Parent", "Worker"], "ParentValue") is not None
    )
    assert ContextBuilder.resolve_variable_in_scope(base_picture, ["Root", "Parent", "Worker"], "Outer") is not None
    assert ContextBuilder.resolve_variable_in_scope(base_picture, ["Root", "Parent", "Worker"], "Missing") is None
