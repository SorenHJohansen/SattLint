from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.analyzers.variables import VariableIssue
from sattlint.analyzers.variables import _variables_submodules as variables_submodules_module


def _ns(**kwargs: Any) -> Any:
    return SimpleNamespace(**kwargs)


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
    assert variables_submodules_module._mapping_source_full_ref(_ns(source={"var_name": 5})) is None
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


def test_framemodule_subtree_uses_repathed_context(monkeypatch: pytest.MonkeyPatch) -> None:
    repathed = _ns(name="repathed")
    frame_calls: list[tuple[str, object, list[str]]] = []
    frame = FrameModule(
        header=ModuleHeader(name="Frame", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduledef=None,
        modulecode=None,
        submodules=[],
    )
    frame_helper: Any = _ns(
        repath_context=lambda context, **kwargs: repathed,
        walk_moduledef=lambda moduledef, context, path: frame_calls.append(("def", context, path)),
        walk_module_code=lambda modulecode, context, path: frame_calls.append(("code", context, path)),
        contexts_by_module_path={},
    )
    monkeypatch.setattr(
        variables_submodules_module,
        "_walk_submodules",
        lambda helper, children, context, path: frame_calls.append(("subs", context, path)),
    )

    variables_submodules_module._walk_framemodule_subtree(
        frame_helper,
        frame,
        _ns(),
        ["Root", "Frame"],
        ["Root", "Frame"],
    )

    assert frame_calls == [
        ("def", repathed, ["Root", "Frame"]),
        ("code", repathed, ["Root", "Frame"]),
        ("subs", repathed, ["Root", "Frame"]),
    ]


def test_dependency_mapping_distinguishes_program_and_library_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    propagated: list[str | None] = []
    checked: list[tuple[list[str], str | None]] = []
    dependency_typedef = ModuleTypeDef(
        name="DependencyType",
        moduleparameters=[Variable(name="signal", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="DependencyType.s",
        origin_lib="SupportLib",
    )
    child = ModuleTypeInstance(
        header=ModuleHeader(name="Dep", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="DependencyType",
        parametermappings=[
            ParameterMapping(
                target={"var_name": "signal"},
                source_type="var_name",
                is_duration=False,
                is_source_global=False,
                source={"var_name": "ProgramVar"},
                source_literal=None,
            ),
            ParameterMapping(
                target={"var_name": "signal"},
                source_type="var_name",
                is_duration=False,
                is_source_global=False,
                source={"var_name": "ProgramVar.Field"},
                source_literal=None,
            ),
        ],
    )
    helper: Any = _ns(
        is_external_typename=lambda name: False,
        bp=_ns(),
        unavailable_libraries=set(),
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        is_from_root_origin=lambda *args, **kwargs: False,
        check_param_mappings_for_type_instance=lambda child, parent_env, parent_context=None, parent_path=None, current_library=None: (
            checked.append(((parent_path if parent_path is not None else parent_context), current_library))
        ),
        context_builder=_ns(build_for_typedef=lambda *args, **kwargs: _ns(env={})),
        param_reads_by_typedef={},
        param_ui_reads_by_typedef={},
        param_non_ui_reads_by_typedef={},
        param_writes_by_typedef={},
        analyzing_typedefs=set(),
        analyze_typedef_with_context=lambda *args, **kwargs: None,
        alias_links=[],
        contexts_by_module_path={},
    )
    monkeypatch.setattr(
        variables_submodules_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: dependency_typedef,
    )
    monkeypatch.setattr(
        variables_submodules_module,
        "_propagate_mapping_to_parent",
        lambda helper, mapping, **kwargs: propagated.append(kwargs["external_typename"]),
    )

    variables_submodules_module._walk_moduletype_instance_subtree(
        helper,
        child,
        _ns(current_library="ProjectLib", env={}),
        ["Root"],
        ["Root", "Dep"],
        ["Root", "Dep"],
    )

    assert checked == [(["Root", "Dep"], "ProjectLib")]
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
    env_var = Variable(name="Signal", datatype=Simple_DataType.INTEGER)
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
            {"var_name": "Signal.Field"},
            {"signal": env_var},
        )
        is env_var
    )
    assert variables_submodules_module._lookup_env_var_from_varname_dict(_ns(), {}, {"signal": env_var}) is None

    declared_type = DataType(
        name="DeclaredPayload",
        description=None,
        datecode=None,
        var_list=[Variable(name="Leaf", datatype=Simple_DataType.INTEGER)],
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
            is_from_root_origin=lambda *args, **kwargs: True,
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
    walker: Any = _ns(limit_to_module_path=["Elsewhere"], repath_context=lambda context, **kwargs: _ns())
    monkeypatch.setattr(
        variables_submodules_module,
        "_walk_submodule_headers",
        lambda *args, **kwargs: skipped_calls.append("headers"),
    )
    monkeypatch.setattr(
        variables_submodules_module,
        "_walk_framemodule_subtree",
        lambda *args, **kwargs: skipped_calls.append("frame"),
    )
    variables_submodules_module._walk_submodules(walker, [frame], _ns(display_module_path=["Root"]), ["Root"])

    walker.limit_to_module_path = None
    monkeypatch.setattr(
        variables_submodules_module,
        "_walk_submodule_headers",
        lambda *args, **kwargs: walked_calls.append("headers"),
    )
    monkeypatch.setattr(
        variables_submodules_module,
        "_walk_framemodule_subtree",
        lambda *args, **kwargs: walked_calls.append("frame"),
    )
    variables_submodules_module._walk_submodules(walker, [frame], _ns(display_module_path=["Root"]), ["Root"])

    assert skipped_calls == []
    assert walked_calls == ["headers", "frame"]


def test_missing_typedef_and_singlemodule_branch_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    propagate_calls: list[str | None] = []
    helper: Any = _ns(
        is_external_typename=lambda name: False,
        bp=_ns(),
        unavailable_libraries=set(),
        analyzed_target_is_library=True,
        include_dependency_moduletype_usage=False,
        is_from_root_origin=lambda *args, **kwargs: True,
        check_param_mappings_for_type_instance=lambda *args, **kwargs: None,
        context_builder=_ns(build_for_typedef=lambda *args, **kwargs: _ns(env={})),
        param_reads_by_typedef={},
        param_ui_reads_by_typedef={},
        param_non_ui_reads_by_typedef={},
        param_writes_by_typedef={},
        analyzing_typedefs=set(),
        analyze_typedef_with_context=lambda *args, **kwargs: None,
        alias_links=[],
        contexts_by_module_path={},
    )
    monkeypatch.setattr(
        variables_submodules_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("missing")),
    )
    monkeypatch.setattr(
        variables_submodules_module,
        "_propagate_mapping_to_parent",
        lambda helper, mapping, **kwargs: propagate_calls.append(kwargs["external_typename"]),
    )

    external_child = ModuleTypeInstance(
        header=ModuleHeader(name="Ext", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="MissingType",
        parametermappings=[
            ParameterMapping(
                target={"var_name": "signal"},
                source_type="var_name",
                is_duration=False,
                is_source_global=False,
                source={"var_name": "ProgramVar"},
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
    single_helper: Any = _ns(
        context_builder=_ns(
            build_for_single=lambda *args, **kwargs: _ns(
                env={"input": Variable(name="Input", datatype=Simple_DataType.INTEGER)}
            )
        ),
        walk_moduledef=lambda *args, **kwargs: None,
        walk_module_code=lambda *args, **kwargs: None,
        get_usage=lambda variable: _UsageStub(),
        alias_links=alias_links,
        check_param_mappings_for_single=lambda *args, **kwargs: None,
        contexts_by_module_path={},
    )
    monkeypatch.setattr(variables_submodules_module, "_walk_submodules", lambda *args, **kwargs: None)
    monkeypatch.setattr(variables_submodules_module, "_propagate_mapping_to_parent", lambda *args, **kwargs: None)

    single = SingleModule(
        header=ModuleHeader(name="Single", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduledef=None,
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target={"var_name": "Input"},
                source_type="var_name",
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
        _ns(resolve_variable=lambda ref: (None, None, [], []), env={}),
        ["Root"],
        ["Root", "Single"],
        ["Root", "Single"],
    )

    assert propagate_calls == ["MissingType"]
    assert alias_links == []


def test_internal_typedef_and_frame_duplication_branch_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    internal_typedef = ModuleTypeDef(
        name="InternalType",
        moduleparameters=[Variable(name="signal", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="Root.s",
        origin_lib="ProjectLib",
    )
    internal_helper: Any = _ns(
        is_external_typename=lambda name: False,
        bp=_ns(),
        unavailable_libraries=set(),
        analyzed_target_is_library=False,
        include_dependency_moduletype_usage=False,
        is_from_root_origin=lambda *args, **kwargs: True,
        check_param_mappings_for_type_instance=lambda *args, **kwargs: None,
        effect_flow_tracker=_ns(propagate_mapping_to_parent=lambda *args, **kwargs: None),
        context_builder=_ns(
            build_for_typedef=lambda *args, **kwargs: _ns(
                env={"signal": Variable(name="signal", datatype=Simple_DataType.INTEGER)}
            )
        ),
        param_reads_by_typedef={},
        param_ui_reads_by_typedef={},
        param_non_ui_reads_by_typedef={},
        param_writes_by_typedef={},
        analyzing_typedefs=set(),
        analyze_typedef_with_context=lambda *args, **kwargs: None,
        alias_links=[],
        contexts_by_module_path={},
    )
    monkeypatch.setattr(
        variables_submodules_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: internal_typedef,
    )

    internal_child = ModuleTypeInstance(
        header=ModuleHeader(name="Int", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        moduletype_name="InternalType",
        parametermappings=[
            ParameterMapping(
                target={"var_name": "signal"},
                source_type="var_name",
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
        _ns(current_library="ProjectLib", env={}, resolve_variable=lambda ref: (None, None, [], [])),
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
            is_from_root_origin=lambda *args, **kwargs: True,
            append_issue=frame_issues.append,
        )
    )

    assert internal_helper.alias_links == []
    assert frame_issues == []
