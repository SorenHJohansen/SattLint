# pyright: reportPrivateUsage=false
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from sattline_parser.ast import MappingSource, VarRef
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    ScalarDatatype,
    SingleModule,
    Variable,
)

from sattlint.analyzers.variables import VariableIssue
from sattlint.analyzers.variables import _variables_submodules as variables_submodules_module


def _ns(**kwargs: Any) -> Any:
    return SimpleNamespace(**kwargs)


def _ignore_call(*args: object, **kwargs: object) -> None:
    """Accept and discard an analyzer callback."""


def _root_origin(*args: object, **kwargs: object) -> bool:
    """Every origin belongs to the root program."""
    return True


def _unresolved_variable(ref: object) -> tuple[Variable | None, str | None, list[str], list[str]]:
    """Every variable reference is unresolved."""
    return (None, None, [], [])


class _UsageStub:
    def __init__(
        self,
        *,
        read: bool = False,
        written: bool = False,
        is_unused: bool = False,
        is_display_only: bool = False,
        is_read_only: bool = False,
        non_ui_read: bool = False,
        ui_read: bool = False,
        field_reads: dict[str, object] | None = None,
        field_writes: dict[str, object] | None = None,
    ) -> None:
        self.read = read
        self.written = written
        self.is_unused = is_unused
        self.is_display_only = is_display_only
        self.is_read_only = is_read_only
        self.non_ui_read = non_ui_read
        self.ui_read = ui_read
        self.field_reads = field_reads or {}
        self.field_writes = field_writes or {}


def test_submodule_mapping_and_display_helpers() -> None:
    assert variables_submodules_module._mapping_source_full_ref(_ns(source="Signal.Value")) == "Signal.Value"
    assert variables_submodules_module._mapping_source_full_ref(_ns(source=5)) is None

    assert variables_submodules_module._should_walk_submodule_path(_ns(limit_to_module_path=None), ["Root", "Child"])
    assert not variables_submodules_module._should_walk_submodule_path(
        _ns(limit_to_module_path=["Other"]), ["Root", "Child"]
    )

    parent_context = _ns(display_module_path=["Root"])
    frame = FrameModule(
        header=ModuleHeader(name="Frame", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduledef=None,
        modulecode=None,
        submodules=[],
    )
    inst = ModuleTypeInstance(
        header=ModuleHeader(name="Pump", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="PumpType",
        parametermappings=[],
    )

    assert variables_submodules_module._display_path_for_child(_ns(), frame, parent_context) == [
        "Root",
        variables_submodules_module.decorate_segment("Frame", "FM"),
    ]
    assert variables_submodules_module._display_path_for_child(_ns(), inst, parent_context) == [
        "Root",
        variables_submodules_module.decorate_segment("Pump", "MT", moduletype_name="PumpType"),
    ]


def test_frame_module_subtree_walks_code_in_the_frame_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    frame_scope = _ns(name="frame-scope")
    frame_calls: list[tuple[str, object, list[str]]] = []
    frame = FrameModule(
        header=ModuleHeader(name="Frame", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduledef=None,
        modulecode=None,
        submodules=[],
    )

    def _walk_moduledef(moduledef: object, context: object, path: list[str]) -> None:
        frame_calls.append(("def", context, path))

    def _walk_module_code(modulecode: object, context: object, path: list[str]) -> None:
        frame_calls.append(("code", context, path))

    def _walk_submodules(helper: object, children: object, context: object, path: list[str]) -> None:
        frame_calls.append(("subs", context, path))

    frame_helper: Any = _ns(
        walk_moduledef=_walk_moduledef,
        walk_module_code=_walk_module_code,
        contexts_by_module_path={},
    )
    monkeypatch.setattr(variables_submodules_module, "_walk_submodules", _walk_submodules)

    variables_submodules_module._walk_framemodule_subtree(
        frame_helper,
        frame,
        frame_scope,
        ["Root", "Frame"],
    )

    assert frame_calls == [
        ("def", frame_scope, ["Root", "Frame"]),
        ("code", frame_scope, ["Root", "Frame"]),
        ("subs", frame_scope, ["Root", "Frame"]),
    ]


def test_dependency_mapping_distinguishes_program_and_library_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    propagated: list[str | None] = []
    checked: list[tuple[list[str], str | None]] = []
    dependency_typedef = ModuleTypeDef(
        name="DependencyType",
        moduleparameters=[Variable(name="signal", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file="DependencyType.s",
        origin_lib="SupportLib",
    )
    child = ModuleTypeInstance(
        header=ModuleHeader(name="Dep", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="DependencyType",
        parametermappings=[
            ParameterMapping(
                target=VarRef(name="signal"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=VarRef(name="ProgramVar"),
                source_literal=None,
            ),
            ParameterMapping(
                target=VarRef(name="signal"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=VarRef(name="ProgramVar.Field"),
                source_literal=None,
            ),
        ],
    )

    def _no_external_type(name: str) -> bool:
        return False

    def _not_root_origin(*args: object, **kwargs: object) -> bool:
        return False

    def _empty_env(*args: object, **kwargs: object) -> Any:
        return _ns(env={})

    def _resolve_dependency(*args: object, **kwargs: object) -> ModuleTypeDef:
        return dependency_typedef

    def _record_propagation(helper: object, mapping: object, **kwargs: str | None) -> None:
        propagated.append(kwargs["external_typename"])

    def _record_mapping_check(
        child: object,
        parent_env: object,
        parent_context: list[str] | None = None,
        parent_path: list[str] | None = None,
        current_library: str | None = None,
    ) -> None:
        resolved_path = parent_path if parent_path is not None else parent_context
        assert resolved_path is not None
        checked.append((resolved_path, current_library))

    helper: Any = _ns(
        is_external_typename=_no_external_type,
        bp=_ns(),
        unavailable_libraries=set(),
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        is_from_root_origin=_not_root_origin,
        check_param_mappings_for_type_instance=_record_mapping_check,
        context_builder=_ns(build_for_typedef=_empty_env),
        param_reads_by_typedef={},
        param_ui_reads_by_typedef={},
        param_non_ui_reads_by_typedef={},
        param_writes_by_typedef={},
        analyzing_typedefs=set(),
        analyze_typedef_with_context=_ignore_call,
        alias_links=[],
        contexts_by_module_path={},
    )
    monkeypatch.setattr(variables_submodules_module, "resolve_moduletype_def_strict", _resolve_dependency)
    monkeypatch.setattr(variables_submodules_module, "_propagate_mapping_to_parent", _record_propagation)

    variables_submodules_module._walk_moduletype_instance_subtree(
        helper,
        child,
        _ns(current_library="ProjectLib", env={}),
        ["Root"],
        ["Root", "Dep"],
        ["Root", "Dep"],
    )

    assert checked == [(["Root", "Dep"], "SupportLib")]
    assert propagated == [None, "DependencyType"]

    propagated.clear()
    helper.analyzed_target_is_library = True
    variables_submodules_module._walk_moduletype_instance_subtree(
        helper,
        child,
        _ns(current_library="ProjectLib", env={}),
        ["Root"],
        ["Root", "Dep"],
        ["Root", "Dep"],
    )

    assert propagated == ["DependencyType", "DependencyType"]


def test_submodule_lookup_and_duplication_helpers() -> None:
    env_var = Variable(name="Signal", datatype=ScalarDatatype.INTEGER)
    assert (
        variables_submodules_module._lookup_env_var_from_varname_dict(
            _ns(),
            _ns(var_name="Signal.Field"),
            {"signal": env_var},
        )
        is None
    )
    assert (
        variables_submodules_module._lookup_env_var_from_varname_dict(
            _ns(),
            VarRef(name="Signal.Field"),
            {"signal": env_var},
        )
        is env_var
    )
    assert variables_submodules_module._lookup_env_var_from_varname_dict(_ns(), {}, {"signal": env_var}) is None

    declared_type = DataType(
        name="DeclaredPayload",
        description=None,
        datecode=None,
        var_list=[Variable(name="Leaf", datatype=ScalarDatatype.INTEGER)],
    )
    issues: list[VariableIssue] = []
    variables_submodules_module._detect_datatype_duplications(
        _ns(
            bp=BasePicture(
                header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
                datatype_defs=[declared_type],
                moduletype_defs=[],
                localvariables=[
                    Variable(name="A", datatype="DeclaredPayload"),
                    Variable(name="B", datatype="DeclaredPayload"),
                    Variable(name="OnlyOne", datatype="ExternalPayload"),
                ],
                submodules=[],
                modulecode=None,
                moduledef=None,
            ),
            is_from_root_origin=_root_origin,
            append_issue=issues.append,
        )
    )

    assert issues == []


def test_walk_submodules_respects_limit_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    skipped_calls: list[str] = []
    walked_calls: list[str] = []
    frame = FrameModule(
        header=ModuleHeader(name="Frame", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduledef=None,
        modulecode=None,
        submodules=[],
    )

    def _build_frame_context(*args: object, **kwargs: object) -> Any:
        return _ns()

    def _skip_headers(*args: object, **kwargs: object) -> None:
        skipped_calls.append("headers")

    def _skip_frame(*args: object, **kwargs: object) -> None:
        skipped_calls.append("frame")

    def _walk_headers(*args: object, **kwargs: object) -> None:
        walked_calls.append("headers")

    def _walk_frame(*args: object, **kwargs: object) -> None:
        walked_calls.append("frame")

    walker: Any = _ns(
        limit_to_module_path=["Elsewhere"],
        context_builder=_ns(build_for_frame=_build_frame_context),
    )
    monkeypatch.setattr(variables_submodules_module, "_walk_submodule_headers", _skip_headers)
    monkeypatch.setattr(variables_submodules_module, "_walk_framemodule_subtree", _skip_frame)
    variables_submodules_module._walk_submodules(walker, [frame], _ns(display_module_path=["Root"]), ["Root"])

    walker.limit_to_module_path = None
    monkeypatch.setattr(variables_submodules_module, "_walk_submodule_headers", _walk_headers)
    monkeypatch.setattr(variables_submodules_module, "_walk_framemodule_subtree", _walk_frame)
    variables_submodules_module._walk_submodules(walker, [frame], _ns(display_module_path=["Root"]), ["Root"])

    assert skipped_calls == []
    assert walked_calls == ["headers", "frame"]


def test_missing_typedef_and_singlemodule_branch_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    propagate_calls: list[str | None] = []

    def _no_external_type(name: str) -> bool:
        return False

    def _empty_env(*args: object, **kwargs: object) -> Any:
        return _ns(env={})

    def _raise_missing_typedef(*args: object, **kwargs: object) -> ModuleTypeDef:
        raise ValueError("missing")

    def _record_propagation(helper: object, mapping: object, **kwargs: str | None) -> None:
        propagate_calls.append(kwargs["external_typename"])

    helper: Any = _ns(
        is_external_typename=_no_external_type,
        bp=_ns(),
        unavailable_libraries=set(),
        analyzed_target_is_library=True,
        include_dependency_moduletype_usage=False,
        is_from_root_origin=_root_origin,
        check_param_mappings_for_type_instance=_ignore_call,
        context_builder=_ns(build_for_typedef=_empty_env),
        param_reads_by_typedef={},
        param_ui_reads_by_typedef={},
        param_non_ui_reads_by_typedef={},
        param_writes_by_typedef={},
        analyzing_typedefs=set(),
        analyze_typedef_with_context=_ignore_call,
        alias_links=[],
        contexts_by_module_path={},
    )
    monkeypatch.setattr(variables_submodules_module, "resolve_moduletype_def_strict", _raise_missing_typedef)
    monkeypatch.setattr(variables_submodules_module, "_propagate_mapping_to_parent", _record_propagation)

    external_child = ModuleTypeInstance(
        header=ModuleHeader(name="Ext", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="MissingType",
        parametermappings=[
            ParameterMapping(
                target=VarRef(name="signal"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=VarRef(name="ProgramVar"),
                source_literal=None,
            )
        ],
    )
    variables_submodules_module._walk_moduletype_instance_subtree(
        helper,
        external_child,
        _ns(current_library="ProjectLib", env={}),
        ["Root"],
        ["Root", "Ext"],
        ["Root", "Ext"],
    )

    alias_links: list[tuple[Variable, Variable, str]] = []

    def _build_single_env(*args: object, **kwargs: object) -> Any:
        return _ns(env={"input": Variable(name="Input", datatype=ScalarDatatype.INTEGER)})

    def _single_usage(variable: Variable) -> _UsageStub:
        return _UsageStub()

    single_helper: Any = _ns(
        context_builder=_ns(build_for_single=_build_single_env),
        walk_moduledef=_ignore_call,
        walk_module_code=_ignore_call,
        get_usage=_single_usage,
        alias_links=alias_links,
        check_param_mappings_for_single=_ignore_call,
        contexts_by_module_path={},
    )
    monkeypatch.setattr(variables_submodules_module, "_walk_submodules", _ignore_call)
    monkeypatch.setattr(variables_submodules_module, "_propagate_mapping_to_parent", _ignore_call)

    single = SingleModule(
        header=ModuleHeader(name="Single", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduledef=None,
        moduleparameters=[Variable(name="Input", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                # Deliberately a mapping-name dict rather than a variable reference.
                target=cast(VarRef, {"var_name": "Input"}),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=None,
            )
        ],
    )
    variables_submodules_module._walk_singlemodule_subtree(
        single_helper,
        single,
        _ns(resolve_variable=_unresolved_variable, env={}),
        ["Root"],
        ["Root", "Single"],
        ["Root", "Single"],
    )

    assert propagate_calls == ["MissingType"]
    assert alias_links == []


def test_internal_typedef_and_frame_duplication_branch_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    internal_typedef = ModuleTypeDef(
        name="InternalType",
        moduleparameters=[Variable(name="signal", datatype=ScalarDatatype.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )

    def _no_external_type(name: str) -> bool:
        return False

    def _internal_env(*args: object, **kwargs: object) -> Any:
        return _ns(env={"signal": Variable(name="signal", datatype=ScalarDatatype.INTEGER)})

    def _resolve_internal(*args: object, **kwargs: object) -> ModuleTypeDef:
        return internal_typedef

    internal_helper: Any = _ns(
        is_external_typename=_no_external_type,
        bp=_ns(),
        unavailable_libraries=set(),
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        is_from_root_origin=_root_origin,
        check_param_mappings_for_type_instance=_ignore_call,
        effect_flow_tracker=_ns(propagate_mapping_to_parent=_ignore_call),
        context_builder=_ns(build_for_typedef=_internal_env),
        param_reads_by_typedef={},
        param_ui_reads_by_typedef={},
        param_non_ui_reads_by_typedef={},
        param_writes_by_typedef={},
        analyzing_typedefs=set(),
        analyze_typedef_with_context=_ignore_call,
        alias_links=[],
        contexts_by_module_path={},
    )
    monkeypatch.setattr(variables_submodules_module, "resolve_moduletype_def_strict", _resolve_internal)

    internal_child = ModuleTypeInstance(
        header=ModuleHeader(name="Int", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="InternalType",
        parametermappings=[
            ParameterMapping(
                target=VarRef(name="signal"),
                source_type=MappingSource.VARIABLE,
                is_duration=False,
                is_source_global=False,
                source=None,
                source_literal=None,
            )
        ],
    )
    variables_submodules_module._walk_moduletype_instance_subtree(
        internal_helper,
        internal_child,
        _ns(current_library="ProjectLib", env={}, resolve_variable=_unresolved_variable),
        ["Root"],
        ["Root", "Int"],
        ["Root", "Int"],
    )

    frame_bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[
            FrameModule(
                header=ModuleHeader(name="Frame", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
                moduledef=None,
                modulecode=None,
                submodules=[
                    SingleModule(
                        header=ModuleHeader(name="Nested", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
                        moduledef=None,
                        moduleparameters=[Variable(name="Payload", datatype="ExternalPayload")],
                        localvariables=[],
                        submodules=[],
                        modulecode=None,
                        parametermappings=[],
                    )
                ],
            )
        ],
        modulecode=None,
        moduledef=None,
    )
    frame_issues: list[VariableIssue] = []
    variables_submodules_module._detect_datatype_duplications(
        _ns(
            bp=frame_bp,
            is_from_root_origin=_root_origin,
            append_issue=frame_issues.append,
        )
    )

    assert internal_helper.alias_links == []
    assert frame_issues == []
