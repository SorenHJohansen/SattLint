# pyright: reportAttributeAccessIssue=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportUnknownMemberType=false

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import (
    FloatLiteral,
    FrameModule,
    ModuleTypeInstance,
    SFCFork,
    Simple_DataType,
    SingleModule,
    Variable,
)
from sattlint.analyzers import _dependency_usage_scope_support as dependency_scope_module
from sattlint.analyzers import _variables_access as variables_access_module
from sattlint.analyzers import _variables_contracts as variables_contracts_module
from sattlint.analyzers import dataflow as dataflow_module
from sattlint.analyzers.dataflow import DataflowAnalyzer
from sattlint.reporting.variables_report import IssueKind
from sattlint.resolution import AccessKind, CanonicalPath
from tests.helpers.variable_test_support import UsageStub as _UsageStub
from tests.helpers.variable_test_support import ns as _ns


def _make_strict_access_helper(
    *,
    fail_loudly: bool = False,
    unavailable_libraries: set[str] | None = None,
    opaque_builtin_types: set[str] | None = None,
    record_resolver: Any | None = None,
    warnings: list[str] | None = None,
) -> Any:
    return SimpleNamespace(
        fail_loudly=fail_loudly,
        unavailable_libraries=unavailable_libraries or {"Lib"},
        opaque_builtin_types=opaque_builtin_types or {"opaque"},
        type_graph=_ns(record=record_resolver or (lambda name: None)),
        site_stack=["site"],
        warn=(warnings if warnings is not None else []).append,
    )


def test_variables_access_wrapper_helpers_delegate_and_parse_fields() -> None:
    tracker_calls: list[tuple[str, object]] = []
    usage_tracker = _ns(
        record_access=lambda **kwargs: tracker_calls.append(("record", kwargs)),
        mark_ref_access=lambda **kwargs: tracker_calls.append(("mark", kwargs)),
    )
    effect_tracker = _ns(
        effect_key_for_variable=lambda variable, decl_path: ("effect", variable.name, *decl_path),
        resolve_effect_key=lambda full_ref, context: ("resolved", full_ref),
        mapping_source_effect_key=lambda pm, **kwargs: ("mapping",),
        resolve_local_effect_key=lambda full_ref, context: ("local", full_ref),
        resolve_mapped_effect_source_key=lambda full_ref, context: ("mapped", full_ref),
        record_effect_flow=lambda source_key, target_key: tracker_calls.append(("flow", (source_key, target_key))),
        collect_function_input_effect_keys=lambda fn_name, args, context: {(fn_name or "", len(args))},
        collect_expression_effect_sources=lambda obj, context: {("expr",)},
        record_assignment_effect_flow=lambda target_ref, expr, context: tracker_calls.append(("assign", target_ref)),
        record_function_call_effect_flow=lambda fn_name, args, context: tracker_calls.append(("call", fn_name)),
    )
    helper: Any = SimpleNamespace(
        usage_tracker=usage_tracker,
        effect_flow_tracker=effect_tracker,
        root_env={},
        any_var_index={"fallback": [Variable(name="Fallback", datatype=Simple_DataType.INTEGER)]},
    )
    variable = Variable(name="Demo", datatype=Simple_DataType.INTEGER)
    context: Any = _ns(
        env={"local": variable},
        param_mappings={"local": object()},
        module_path=["Root"],
        resolve_variable=lambda full_ref: (
            (None, None, [], None) if full_ref == "local.field" else (variable, "field", ["Decl"], None)
        ),
    )

    assert variables_access_module._canonical_path(helper, ["Root"], variable, "field..leaf") == CanonicalPath(
        ("Root", "Demo", "field", "leaf")
    )
    variables_access_module._record_access(
        helper,
        AccessKind.READ,
        CanonicalPath(("Root", "Demo")),
        context,
        "Demo",
    )
    variables_access_module._mark_ref_access(helper, "local.field", context, ["Root"], AccessKind.READ)
    variables_access_module._mark_ref_access(helper, "resolved.field", context, ["Root"], AccessKind.WRITE)
    assert variables_access_module._effect_key_for_variable(helper, variable, ["Root"]) == ("effect", "Demo", "Root")
    assert variables_access_module._resolve_effect_key(helper, "x", context) == ("resolved", "x")
    assert variables_access_module._mapping_source_effect_key(
        helper, _ns(target="x"), parent_env={}, parent_context=None
    ) == ("mapping",)
    assert variables_access_module._resolve_local_effect_key(helper, "x", context) == ("local", "x")
    assert variables_access_module._resolve_mapped_effect_source_key(helper, "x", context) == ("mapped", "x")
    variables_access_module._record_effect_flow(helper, ("a",), ("b",))
    assert variables_access_module._collect_function_input_effect_keys(helper, "Fn", [1], context) == {("Fn", 1)}
    assert variables_access_module._collect_expression_effect_sources(helper, object(), context) == {("expr",)}
    variables_access_module._record_assignment_effect_flow(helper, "dest", object(), context)
    variables_access_module._record_function_call_effect_flow(helper, "Fn", [], context)

    assert len([call for call in tracker_calls if call[0] == "mark"]) == 2
    assert variables_access_module._lookup_global_variable(helper, None) is None
    helper.root_env["direct"] = variable
    assert variables_access_module._lookup_global_variable(helper, "direct") is variable
    assert variables_access_module._lookup_global_variable(helper, "fallback") is not None
    assert variables_access_module._extract_field_path(helper, {}) == (None, None)
    assert variables_access_module._extract_field_path(helper, {"var_name": 1}) == (None, None)
    assert variables_access_module._extract_field_path(helper, {"var_name": "Demo"}) == ("demo", None)
    assert variables_access_module._extract_field_path(helper, {"var_name": "Demo.Field"}) == ("demo", "Field")


def test_variables_access_effect_and_site_helpers_cover_remaining_branches() -> None:
    variable = Variable(name="Demo", datatype=Simple_DataType.INTEGER)
    sink_keys = {("sink",)}
    helper: Any = SimpleNamespace(
        bp=_ns(name="bp"),
        analyzed_target_is_library=False,
        is_from_root_origin=lambda *_args: True,
        effect_flow_tracker=_ns(
            collect_effect_sink_keys=lambda bp, is_library, matcher: sink_keys,
            compute_effective_output_keys=lambda keys: {("effect", "Demo", "Root")} if keys == sink_keys else set(),
            effect_key_for_variable=lambda variable, decl_path: ("effect", variable.name, *decl_path),
        ),
        effective_output_keys={("effect", "Demo", "Root")},
        site_stack=[],
    )

    assert variables_access_module._collect_effect_sink_keys(helper) == sink_keys
    assert variables_access_module._compute_effective_output_keys(helper) == {("effect", "Demo", "Root")}
    assert variables_access_module._has_output_effect(helper, variable, ["Root"]) is True
    assert variables_access_module._site_str(helper) == ""

    variables_access_module._push_site(helper, "")
    assert helper.site_stack == []
    variables_access_module._push_site(helper, "Step")
    assert helper.site_stack == ["Step"]
    variables_access_module._pop_site(helper)
    variables_access_module._pop_site(helper)
    assert helper.site_stack == []


def test_variables_access_strict_datatype_helper_covers_warning_and_error_paths() -> None:
    warnings: list[str] = []
    record_with_known_field = _ns(
        name="RecordType",
        fields_by_key={"known": _ns(name="Known", datatype=Simple_DataType.INTEGER)},
    )
    helper = _make_strict_access_helper(
        record_resolver=lambda name: None if name == "Unknown" else record_with_known_field,
        warnings=warnings,
    )

    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            Simple_DataType.INTEGER,
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == Simple_DataType.INTEGER
    )
    assert any("cannot access field" in warning for warning in warnings)

    helper.fail_loudly = True
    with pytest.raises(ValueError):
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            Simple_DataType.INTEGER,
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
    helper.fail_loudly = False

    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "opaque",
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == "opaque"
    )

    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "Unknown",
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == "Unknown"
    )

    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    with pytest.raises(ValueError):
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "Unknown",
            "field",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
    helper.fail_loudly = False
    helper.unavailable_libraries = {"Lib"}

    warnings.clear()
    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "RecordType",
            "know",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == "RecordType"
    )
    assert any("Close matches" in warning for warning in warnings)


def test_variables_access_leaf_helper_covers_unknown_and_builtin_paths() -> None:
    warnings: list[str] = []
    record_with_known_field = _ns(
        name="RecordType",
        fields_by_key={"known": _ns(name="Known", datatype=Simple_DataType.INTEGER)},
    )
    helper = _make_strict_access_helper(
        record_resolver=lambda name: None if name == "Unknown" else record_with_known_field,
        warnings=warnings,
    )

    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    with pytest.raises(ValueError):
        variables_access_module._iter_leaf_field_paths_strict(
            helper,
            "Unknown",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
        )

    helper.fail_loudly = False
    helper.unavailable_libraries = {"Lib"}
    warnings.clear()
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "Unknown",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert warnings

    helper.unavailable_libraries = set()
    warnings.clear()
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "Unknown",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert warnings

    helper.type_graph = _ns(record=lambda name: None if name in {"Unknown", "opaque"} else record_with_known_field)
    helper.opaque_builtin_types = {"opaque"}
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "opaque",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "AnyType",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]


def test_variables_access_leaf_helper_covers_record_and_cycle_paths() -> None:
    warnings: list[str] = []
    helper = _make_strict_access_helper(warnings=warnings)

    helper.type_graph = _ns(
        record=lambda name: (
            _ns(fields_by_key={"leaf": _ns(name="Leaf", datatype="AnyType")}) if name == "RecordType" else None
        )
    )
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "RecordType",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [("Leaf",)]

    cyclic_record = _ns(fields_by_key={"self": _ns(name="Self", datatype="Loop")})
    helper.type_graph = _ns(record=lambda name: cyclic_record if name == "Loop" else None)
    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    with pytest.raises(ValueError):
        variables_access_module._iter_leaf_field_paths_strict(
            helper,
            "Loop",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
        )


def test_variables_access_strict_and_leaf_helpers_cover_remaining_branches() -> None:
    warnings: list[str] = []
    helper = _make_strict_access_helper(warnings=warnings)
    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    helper.type_graph = _ns(
        record=lambda name: _ns(name="RecordType", fields_by_key={"known": _ns(name="Known", datatype="Nested")})
    )
    with pytest.raises(ValueError):
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "RecordType",
            "Missing",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
    assert (
        variables_access_module._strict_datatype_at_field_prefix(
            helper,
            "RecordType",
            "Known",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
        == "Nested"
    )

    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        Simple_DataType.INTEGER,
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]

    helper.fail_loudly = False
    helper.type_graph = _ns(
        record=lambda name: (
            _ns(fields_by_key={"nested": _ns(name="Nested", datatype="AnyType")}) if name == "Wrapper" else None
        )
    )
    helper.unavailable_libraries = set()
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "Wrapper",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [("Nested",)]

    helper.type_graph = _ns(
        record=lambda name: (
            _ns(fields_by_key={"leaf": _ns(name="Leaf", datatype=Simple_DataType.INTEGER)})
            if name == "ScalarWrapper"
            else None
        )
    )
    assert variables_access_module._iter_leaf_field_paths_strict(
        helper,
        "ScalarWrapper",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [("Leaf",)]


def test_variables_access_record_wide_access_and_origin_helpers() -> None:
    variable = Variable(name="Demo", datatype="RecordType")
    unresolved_context: Any = _ns(resolve_variable=lambda *_: (None, None, [], None))
    helper: Any = SimpleNamespace(site_stack=["site"])
    with pytest.raises(ValueError):
        variables_access_module._mark_record_wide_builtin_access(
            helper,
            "Demo",
            kind=AccessKind.READ,
            fn_name="Fn",
            context=unresolved_context,
            path=["Root"],
        )

    refs: list[tuple[str, bool]] = []
    context: Any = _ns(resolve_variable=lambda *_: (variable, None, ["Root"], None))
    original_strict = variables_access_module._strict_datatype_at_field_prefix
    original_iter = variables_access_module._iter_leaf_field_paths_strict
    original_mark = variables_access_module._mark_ref_access
    try:
        variables_access_module._strict_datatype_at_field_prefix = lambda *args, **kwargs: "RecordType"
        variables_access_module._iter_leaf_field_paths_strict = lambda *args, **kwargs: [(), ("Leaf",)]
        variables_access_module._mark_ref_access = lambda self, syntactic_ref, context, path, kind, is_ui_read=False: (
            refs.append((syntactic_ref, is_ui_read))
        )
        variables_access_module._mark_record_wide_builtin_access(
            helper,
            "Demo",
            kind=AccessKind.WRITE,
            fn_name="Fn",
            context=context,
            path=["Root"],
            is_ui_read=True,
        )
    finally:
        variables_access_module._strict_datatype_at_field_prefix = original_strict
        variables_access_module._iter_leaf_field_paths_strict = original_iter
        variables_access_module._mark_ref_access = original_mark

    assert refs == [("Demo", True), ("Demo.Leaf", True)]

    library_helper: Any = _ns(
        analyzed_target_is_library=True,
        bp=_ns(origin_lib="RootLib", origin_file="RootLib.s"),
    )
    assert variables_access_module.is_from_root_origin(library_helper, "Other.s", "rootlib") is True

    class BrokenPath:
        def __init__(self, value: str) -> None:
            self.value = value

        def rsplit(self, sep: str, maxsplit: int) -> list[str]:
            return self.value.rsplit(sep, maxsplit)

    fallback_helper: Any = _ns(
        analyzed_target_is_library=False,
        bp=_ns(origin_file=BrokenPath("Root.s")),
    )
    assert variables_access_module.is_from_root_origin(fallback_helper, cast(Any, BrokenPath("Root.x"))) is True
    assert (
        variables_access_module.is_from_root_origin(_ns(analyzed_target_is_library=False, bp=_ns()), "Root.x") is False
    )

    broken_library_helper: Any = _ns(
        analyzed_target_is_library=True,
        bp=_ns(origin_lib="Root", origin_file=BrokenPath("Root.s")),
    )
    assert variables_access_module.is_from_root_origin(broken_library_helper, "Other.s", "root") is True

    strict_library_helper: Any = _ns(
        _analyzed_target_is_library=True,
        bp=_ns(origin_lib="ProjectLib", origin_file="RootLib.s"),
    )
    assert DataflowAnalyzer._is_from_root_origin(strict_library_helper, "Other.s", "projectlib") is False
    assert (
        dependency_scope_module._DependencyUsageScopeSupportMixin._is_from_root_origin(
            strict_library_helper,
            "Other.s",
            "projectlib",
        )
        is False
    )

    specific_library_helper: Any = _ns(
        _analyzed_target_is_library=True,
        bp=_ns(origin_lib="RootLib", origin_file="RootLib.s"),
    )
    assert DataflowAnalyzer._is_from_root_origin(specific_library_helper, "Other.s", "rootlib") is True
    assert (
        dependency_scope_module._DependencyUsageScopeSupportMixin._is_from_root_origin(
            specific_library_helper,
            "Other.s",
            "rootlib",
        )
        is True
    )


def test_dataflow_facade_and_scalar_helpers_cover_remaining_branches(monkeypatch: Any) -> None:
    delegate_probe = DataflowAnalyzer.__new__(DataflowAnalyzer)
    delegate_probe._issues = ["issue"]
    delegate_probe._unavailable_libraries = {"Lib"}
    delegate_probe._build_scope_context = lambda *args, **kwargs: ("scope", args, kwargs)
    delegate_probe._seed_state = lambda state, module_path, variables: {
        ("seeded",): (tuple(module_path), len(variables))
    }
    delegate_probe._build_single_context = lambda mod, parent_context, module_path: ("single", tuple(module_path))
    delegate_probe._build_typedef_context = lambda moduletype, instance, parent_context, module_path: (
        "typedef",
        tuple(module_path),
    )
    delegate_probe._analyze_block = lambda statements, context, module_path, state: {("block",): len(statements)}
    delegate_probe._evaluate_condition = lambda condition, context, module_path, state: True

    assert delegate_probe.issues == ["issue"]
    assert delegate_probe.unavailable_libraries == {"Lib"}
    assert (
        delegate_probe.build_scope_context(
            [Variable(name="Param", datatype=Simple_DataType.INTEGER)],
            param_mappings={},
            module_path=["Root"],
            current_library=None,
            parent_context=None,
        )[0]
        == "scope"
    )
    assert delegate_probe.seed_state({}, ["Root"], [Variable(name="Local", datatype=Simple_DataType.INTEGER)]) == {
        ("seeded",): (("Root",), 1)
    }
    assert delegate_probe.build_single_context(_ns(), _ns(), ["Root", "Child"]) == ("single", ("Root", "Child"))
    assert delegate_probe.build_typedef_context(_ns(), _ns(), _ns(), ["Root", "TypeDef"]) == (
        "typedef",
        ("Root", "TypeDef"),
    )
    assert delegate_probe.analyze_block([1, 2], _ns(), ["Root"], {}) == {("block",): 2}
    assert delegate_probe.evaluate_condition(True, _ns(), ["Root"], {}) is True

    state = {("seed",): 1}
    context = _ns(module_path=["Root"])
    assert delegate_probe._apply_call_side_effects(None, [], context, state) is state

    monkeypatch.setattr(dataflow_module, "get_function_signature", lambda _name: None)
    assert delegate_probe._apply_call_side_effects("Fn", [], context, state) is state

    invalid_old_writes: list[tuple[str | None, tuple[str, ...], str]] = []
    applied_writes: list[tuple[str | None, object, tuple[str, ...], bool]] = []
    resolved_map = {
        "skip": None,
        "old": _ns(state_access="old"),
        "new": _ns(state_access=None),
    }

    def _apply_write_target(resolved: Any, value: object, next_state: object, **kwargs: object) -> dict[object, object]:
        applied_writes.append(
            (
                getattr(resolved, "state_access", None),
                value,
                tuple(cast(list[str], kwargs["module_path"])),
                bool(kwargs["treat_as_root_overwrite"]),
            )
        )
        updated = dict(cast(dict[object, object], next_state))
        updated[("written",)] = value
        return updated

    delegate_probe._resolve_ref = lambda arg, _context: resolved_map[arg]
    delegate_probe._report_invalid_old_write = lambda resolved, module_path, operation: invalid_old_writes.append(
        (getattr(resolved, "state_access", None), tuple(module_path), operation)
    )
    delegate_probe._apply_write_target = _apply_write_target
    monkeypatch.setattr(
        dataflow_module,
        "get_function_signature",
        lambda _name: _ns(parameters=[_ns(direction="out"), _ns(direction="inout"), _ns(direction="out")]),
    )

    next_state = delegate_probe._apply_call_side_effects("Fn", ["skip", "old", "new"], context, state)

    assert invalid_old_writes == [("old", ("Root",), "inout parameter")]
    assert applied_writes == [(None, dataflow_module.UNKNOWN, ("Root",), True)]
    assert next_state[("written",)] is dataflow_module.UNKNOWN

    write_probe = DataflowAnalyzer.__new__(DataflowAnalyzer)
    write_probe._resolve_ref = lambda _expr, _context: None
    assert write_probe._write_target({"var_name": "missing"}, 1, context, state) is state

    helper_probe = DataflowAnalyzer.__new__(DataflowAnalyzer)
    helper_probe._type_graph = _ns(
        field=lambda datatype, field_name: None if field_name == "missing" else _ns(datatype=None, state=True)
    )

    missing_context = _ns(
        module_path=["Root"],
        resolve_variable=lambda full_name: (
            (None, "", ["Root"], None)
            if full_name == "Missing"
            else (Variable(name="Value", datatype=Simple_DataType.INTEGER), "", ["Root"], None)
        ),
    )
    assert helper_probe._resolve_ref({"var_name": 1}, missing_context) is None
    assert helper_probe._resolve_ref({"var_name": "Missing"}, missing_context) is None
    assert helper_probe._resolve_state_flag(_ns(state=False, datatype=None), "leaf") is None
    assert helper_probe._resolve_state_flag(_ns(state=False, datatype="RecordType"), "missing") is None

    assert helper_probe._compare_values(1, "==", 1) is True
    assert helper_probe._compare_values(1, "<>", 2) is True
    assert helper_probe._compare_values(1, "<", 2) is True
    assert helper_probe._compare_values(2, ">", 1) is True
    assert helper_probe._compare_values(1, "<=", 1) is True
    assert helper_probe._compare_values(2, ">=", 1) is True
    assert helper_probe._compare_values(1, "<", "x") is None
    assert helper_probe._compare_values(1, "?", 1) is None

    assert helper_probe._apply_arithmetic("+", True, 2) is dataflow_module.UNKNOWN
    assert helper_probe._apply_arithmetic("+", "x", 2) is dataflow_module.UNKNOWN
    assert helper_probe._apply_arithmetic("+", 1, 2) == 3
    assert helper_probe._apply_arithmetic("-", 4, 1) == 3
    assert helper_probe._apply_arithmetic("*", 2, 3) == 6
    assert helper_probe._apply_arithmetic("/", 4, 0) is dataflow_module.UNKNOWN
    assert helper_probe._apply_arithmetic("/", 5, 2) == 2.5
    assert helper_probe._apply_arithmetic("%", 5, 2) is dataflow_module.UNKNOWN

    assert helper_probe._static_literal(FloatLiteral(2.5)) == 2.5
    assert helper_probe._static_literal(1.5) == 1.5
    assert helper_probe._static_literal("label") == "label"

    assert helper_probe._sequence_node_label(_ns(name="Gate")) == "SimpleNamespace:Gate"
    assert helper_probe._sequence_node_label(SFCFork(targets=("Left", "Right"))) == "SFCFork:Left,Right"
    assert helper_probe._sequence_node_label(object()) == "object"


def test_dependency_scope_support_context_and_mapping_helpers_cover_branches() -> None:
    class Probe(dependency_scope_module._DependencyUsageScopeSupportMixin):
        pass

    root_typedef = _ns(name="RootType", origin_file="Root.s", origin_lib=None)
    dep_typedef = _ns(name="DepType", origin_file="Dep.s", origin_lib=None)
    probe = Probe.__new__(Probe)
    probe.bp = _ns(moduletype_defs=[root_typedef, dep_typedef], origin_file="Root.s", origin_lib=None)
    probe._analyzed_target_is_library = False
    probe._unavailable_libraries = set()
    probe._moduleparameter_keys_by_context = {}
    probe._is_from_root_origin = lambda origin_file, origin_lib=None: origin_file == "Root.s"

    assert probe._iter_root_typedefs() == [root_typedef]

    parent_context = _ns(marker="parent")
    param = Variable(name="Param", datatype=Simple_DataType.INTEGER)
    local = Variable(name="Local", datatype=Simple_DataType.INTEGER)
    built = probe._build_scope_context(
        [param, local],
        moduleparameters=[param],
        param_mappings={"param": (param, "", ["Root"], ["Root"])},
        module_path=["Root", "Child"],
        current_library="Lib",
        parent_context=parent_context,
    )
    assert built.env == {"param": param, "local": local}
    assert built.module_path == ["Root", "Child"]
    assert built.display_module_path == ["Root", "Child"]
    assert built.current_library == "Lib"
    assert built.parent_context is parent_context
    assert probe._moduleparameter_keys_by_context[id(built)] == {"param"}

    source_var = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    resolved = probe._build_parameter_mappings(
        [
            _ns(is_source_global=True, target={"var_name": "Skip"}, source={"var_name": "Source"}),
            _ns(is_source_global=False, target={}, source={"var_name": "Source"}),
            _ns(is_source_global=False, target={"var_name": "TargetA"}, source=object()),
            _ns(is_source_global=False, target={"var_name": "TargetB"}, source={"var_name": "Missing"}),
            _ns(is_source_global=False, target={"var_name": "TargetC"}, source={"var_name": "Source.Field"}),
            _ns(is_source_global=False, target={"var_name": "TargetD"}, source="Source.Other"),
        ],
        _ns(
            resolve_variable=lambda full_source: (
                (source_var, "Field", ["Decl"], ["Display"])
                if str(full_source).startswith("Source")
                else (None, None, [], [])
            )
        ),
    )
    assert resolved == {
        "targetc": (source_var, "Field", ["Decl"], ["Display"]),
        "targetd": (source_var, "Field", ["Decl"], ["Display"]),
    }


def test_dependency_scope_support_walk_helpers_cover_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    class Probe(dependency_scope_module._DependencyUsageScopeSupportMixin):
        pass

    module_code_calls: list[tuple[object | None, list[str]]] = []
    typedef_calls: list[tuple[object, list[str], object]] = []
    instance_calls: list[tuple[object, list[str]]] = []

    probe = Probe.__new__(Probe)
    probe.bp = _ns(origin_file="Root.s", origin_lib=None)
    probe._analyzed_target_is_library = False
    probe._unavailable_libraries = set()
    probe._moduleparameter_keys_by_context = {}
    probe._walk_module_code = lambda modulecode, context, module_path: module_code_calls.append(
        (modulecode, module_path)
    )
    probe._walk_typedef = lambda moduletype, context, module_path: typedef_calls.append(
        (moduletype, module_path, context)
    )
    probe._is_from_root_origin = lambda origin_file, origin_lib=None: origin_file == "Root.s"

    single = SingleModule.__new__(SingleModule)
    single.header = _ns(name="Single")
    single.moduleparameters = [Variable(name="Param", datatype=Simple_DataType.INTEGER)]
    single.localvariables = [Variable(name="Local", datatype=Simple_DataType.INTEGER)]
    single.parametermappings = [_ns(is_source_global=False, target={"var_name": "Param"}, source="Source")]
    single.modulecode = "single-code"
    single.submodules = []

    frame = FrameModule.__new__(FrameModule)
    frame.header = _ns(name="Frame")
    frame.modulecode = "frame-code"
    frame.submodules = []

    inst = ModuleTypeInstance.__new__(ModuleTypeInstance)
    inst.header = _ns(name="Inst")
    inst.moduletype_name = "ChildType"
    inst.parametermappings = []

    parent_context = _ns(
        env={"source": Variable(name="Source", datatype=Simple_DataType.INTEGER)},
        param_mappings={},
        current_library="Lib",
        resolve_variable=lambda full_source: (
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            None,
            ["Decl"],
            ["Display"],
        ),
    )

    original_walk_instance = probe._walk_moduletype_instance if hasattr(probe, "_walk_moduletype_instance") else None
    probe._walk_moduletype_instance = lambda instance, parent_context, child_path: instance_calls.append(
        (instance, child_path)
    )
    probe._walk_modules([single, frame, inst], parent_context, ["Root"])
    assert module_code_calls == [
        ("single-code", ["Root", "Single"]),
        ("frame-code", ["Root", "Frame"]),
    ]
    assert instance_calls == [(inst, ["Root", "Inst"])]
    if original_walk_instance is not None:
        probe._walk_moduletype_instance = original_walk_instance

    resolved_typedef = _ns(
        origin_file="Root.s",
        origin_lib="ResolvedLib",
        moduleparameters=[Variable(name="Param", datatype=Simple_DataType.INTEGER)],
        localvariables=[Variable(name="Local", datatype=Simple_DataType.INTEGER)],
    )
    monkeypatch.setattr(
        dependency_scope_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("missing")),
    )
    probe._walk_moduletype_instance(inst, parent_context, ["Root", "Inst"])

    monkeypatch.setattr(
        dependency_scope_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: _ns(origin_file="Dep.s", origin_lib="DepLib", moduleparameters=[], localvariables=[]),
    )
    probe._walk_moduletype_instance(inst, parent_context, ["Root", "Inst"])

    monkeypatch.setattr(
        dependency_scope_module, "resolve_moduletype_def_strict", lambda *args, **kwargs: resolved_typedef
    )
    probe._walk_moduletype_instance(inst, parent_context, ["Root", "Inst"])
    assert len(typedef_calls) == 1
    moduletype, module_path, typedef_context = typedef_calls[0]
    assert moduletype is resolved_typedef
    assert module_path == ["Root", "Inst"]
    assert typedef_context.current_library == "ResolvedLib"


def test_variables_contracts_cover_guard_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    non_any = Variable(name="Scalar", datatype=Simple_DataType.INTEGER)
    any_param = Variable(name="AnyParam", datatype="AnyType")
    extractor: Any = _ns(get_usage=lambda variable: _UsageStub())
    assert variables_contracts_module._build_anytype_parameter_contract(_ns(), extractor, non_any) is None
    assert variables_contracts_module._build_anytype_parameter_contract(_ns(), extractor, any_param) is None

    helper: Any = SimpleNamespace(iter_anytype_typedefs=lambda: [])
    assert variables_contracts_module._build_anytype_field_contracts(helper) == {}

    display_only = Variable(name="DisplayOnly", datatype=Simple_DataType.INTEGER)
    required = Variable(name="Required", datatype=Simple_DataType.INTEGER)
    moduletype: Any = _ns(moduleparameters=[display_only, required], name="Worker")
    usage_by_id = {
        id(display_only): _UsageStub(read=True, is_display_only=True),
        id(required): _UsageStub(read=True),
    }
    monkeypatch.setattr(
        variables_contracts_module,
        "_make_nested_contract_extractor",
        lambda self: SimpleNamespace(
            analyze_typedef=lambda *args, **kwargs: None,
            get_usage=lambda variable: usage_by_id[id(variable)],
        ),
    )
    owner: Any = _ns(bp=_ns(header=_ns(name="Root")), required_parameter_names_by_owner={})
    assert variables_contracts_module._get_required_parameter_names_for_typedef(owner, moduletype) == {
        "required": "Required"
    }

    issues: list[str] = []
    parameter = Variable(name="Required", datatype=Simple_DataType.INTEGER)
    self_single: Any = SimpleNamespace(
        get_usage=lambda variable: _UsageStub(read=True, is_display_only=variable is not parameter),
        append_issue=lambda issue: issues.append(issue.role),
        check_param_mapping=lambda *args, **kwargs: issues.append("checked"),
    )
    mod: Any = _ns(
        moduleparameters=[Variable(name="Display", datatype=Simple_DataType.INTEGER), parameter], parametermappings=[]
    )
    variables_contracts_module._check_param_mappings_for_single(self_single, mod, {}, {}, ["Root"])
    assert issues == ["required parameter connection missing for 'Required'"]

    inst: Any = _ns(moduletype_name="Missing", parametermappings=[])
    self_inst: Any = SimpleNamespace(
        bp=_ns(),
        unavailable_libraries=set(),
        get_required_parameter_names_for_typedef=lambda mt: {"missing": "Missing"},
        append_issue=lambda issue: (_ for _ in ()).throw(AssertionError("unexpected issue")),
        check_param_mapping=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("missing")),
    )
    variables_contracts_module._check_param_mappings_for_type_instance(self_inst, inst, {}, ["Root"])
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: SimpleNamespace(moduleparameters=[]),
    )
    variables_contracts_module._check_param_mappings_for_type_instance(self_inst, inst, {}, ["Root"])


def test_variables_contracts_cover_remaining_collection_and_index_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    any_param = Variable(name="AnyParam", datatype="AnyType")
    any_usage = _UsageStub(field_reads={"Leaf": 1}, field_writes={"Other": 1})
    contract = variables_contracts_module._build_anytype_parameter_contract(
        _ns(),
        _ns(get_usage=lambda variable: any_usage),
        any_param,
    )
    assert contract is not None
    assert contract.field_paths == ("Leaf", "Other")

    nested_param = Variable(name="NestedParam", datatype=Simple_DataType.INTEGER)
    nested_local = Variable(name="NestedLocal", datatype=Simple_DataType.INTEGER)
    root_local = Variable(name="RootLocal", datatype=Simple_DataType.INTEGER)
    typedef_param = Variable(name="TypeParam", datatype=Simple_DataType.INTEGER)
    typedef_local = Variable(name="TypeLocal", datatype=Simple_DataType.INTEGER)

    nested_single = SingleModule.__new__(SingleModule)
    nested_single.moduleparameters = [nested_param]
    nested_single.localvariables = [nested_local]
    nested_single.submodules = []

    frame = FrameModule.__new__(FrameModule)
    frame.submodules = [nested_single]

    index_helper: Any = _ns(
        any_var_index={},
        bp=_ns(
            localvariables=[root_local],
            submodules=[frame],
            moduletype_defs=[_ns(moduleparameters=[typedef_param], localvariables=[typedef_local])],
        ),
    )
    variables_contracts_module._index_all_variables(index_helper)
    assert index_helper.any_var_index == {
        "rootlocal": [root_local],
        "nestedparam": [nested_param],
        "nestedlocal": [nested_local],
        "typeparam": [typedef_param],
        "typelocal": [typedef_local],
    }

    single_calls: list[str] = []
    single_param = Variable(name="Required", datatype=Simple_DataType.INTEGER)
    single_mod: Any = _ns(moduleparameters=[single_param], parametermappings=[])
    single_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.REQUIRED_PARAMETER_CONNECTION},
        get_usage=lambda variable: _UsageStub(read=True),
        append_issue=lambda issue: single_calls.append(issue.role),
        check_param_mapping=lambda *args, **kwargs: single_calls.append("checked"),
    )
    variables_contracts_module._check_param_mappings_for_single(single_helper, single_mod, {}, {}, ["Root"])
    assert single_calls == ["required parameter connection missing for 'Required'"]

    inst: Any = _ns(moduletype_name="Worker", parametermappings=[])
    disabled_type_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.UI_ONLY},
        bp=_ns(),
        unavailable_libraries=set(),
    )
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not resolve")),
    )
    variables_contracts_module._check_param_mappings_for_type_instance(disabled_type_helper, inst, {}, ["Root"])

    type_calls: list[str] = []
    missing_param = Variable(name="Missing", datatype=Simple_DataType.INTEGER)
    type_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.REQUIRED_PARAMETER_CONNECTION},
        bp=_ns(),
        unavailable_libraries=set(),
        get_required_parameter_names_for_typedef=lambda mt: {"missing": "Missing", "ghost": "Ghost"},
        append_issue=lambda issue: type_calls.append(issue.role),
        check_param_mapping=lambda *args, **kwargs: type_calls.append("checked"),
    )
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        lambda *args, **kwargs: _ns(moduleparameters=[missing_param]),
    )
    variables_contracts_module._check_param_mappings_for_type_instance(type_helper, inst, {}, ["Root"])
    assert type_calls == ["required parameter connection missing for 'Missing'"]

    mapping_calls: list[tuple[str, object]] = []
    src_var = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    tgt_var = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    pm_global: Any = _ns(is_source_global=True, source={"var_name": "Source"})
    pm_local: Any = _ns(is_source_global=False, source={"var_name": "RootSource"})
    mapping_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.CONTRACT_MISMATCH},
        lookup_env_var_from_varname_dict=lambda source_ref, env: None,
        root_env={"rootsource": src_var},
        contract_validator=_ns(check_contract_mapping=lambda *args, **kwargs: ["contract"]),
        string_validator=_ns(check_string_mapping=lambda *args, **kwargs: ["string"]),
        min_max_validator=_ns(check_min_max_mapping=lambda *args, **kwargs: ["range"]),
        append_param_mapping_issue=lambda pm, issue: mapping_calls.append((pm.source["var_name"], issue)),
    )
    variables_contracts_module._check_param_mapping(
        SimpleNamespace(_selected_issue_kinds={IssueKind.REQUIRED_PARAMETER_CONNECTION}),
        pm_local,
        tgt_var,
        {},
        ["Root"],
    )
    variables_contracts_module._check_param_mapping(mapping_helper, pm_global, tgt_var, {}, ["Root"])
    variables_contracts_module._check_param_mapping(mapping_helper, pm_local, tgt_var, {}, ["Root"])
    assert mapping_calls == [
        ("RootSource", "contract"),
        ("RootSource", "string"),
        ("RootSource", "range"),
    ]


def test_variables_contracts_cover_remaining_loop_and_guard_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    any_typedef = _ns(
        name="AnyTypeHolder",
        moduleparameters=[Variable(name="Payload", datatype="AnyType")],
    )
    build_calls: list[str] = []
    contract_owner: Any = SimpleNamespace(
        bp=_ns(header=_ns(name="Root")),
        iter_anytype_typedefs=lambda: [any_typedef],
        build_anytype_parameter_contract=lambda extractor, variable: build_calls.append(variable.name) or None,
    )
    monkeypatch.setattr(
        variables_contracts_module,
        "_make_nested_contract_extractor",
        lambda self: _ns(analyze_typedef=lambda *args, **kwargs: None),
    )
    assert variables_contracts_module._build_anytype_field_contracts(contract_owner) == {}
    assert build_calls == ["Payload"]

    guard_calls: list[str] = []
    mapped_parameter = Variable(name="Mapped", datatype=Simple_DataType.INTEGER)
    idle_parameter = Variable(name="Idle", datatype=Simple_DataType.INTEGER)
    mapping = _ns(target={"var_name": "Mapped"})
    single_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.UI_ONLY},
        get_usage=lambda variable: _UsageStub(read=True),
        append_issue=lambda issue: guard_calls.append(issue.role),
        check_param_mapping=lambda *args, **kwargs: guard_calls.append("checked"),
    )
    single_mod: Any = _ns(moduleparameters=[mapped_parameter, idle_parameter], parametermappings=[mapping])
    variables_contracts_module._check_param_mappings_for_single(single_helper, single_mod, {}, {}, ["Root"])
    assert guard_calls == []

    single_helper._selected_issue_kinds = {
        IssueKind.REQUIRED_PARAMETER_CONNECTION,
        IssueKind.CONTRACT_MISMATCH,
    }
    single_helper.get_usage = lambda variable: _UsageStub(read=False, written=False)
    variables_contracts_module._check_param_mappings_for_single(single_helper, single_mod, {}, {}, ["Root"])
    assert guard_calls == [("checked")]

    param_check_calls: list[tuple[str, object | None]] = []
    check_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.CONTRACT_MISMATCH},
        lookup_env_var_from_varname_dict=lambda source_ref, env: None,
        root_env={},
        contract_validator=_ns(check_contract_mapping=lambda *args, **kwargs: ["contract"]),
        string_validator=_ns(check_string_mapping=lambda *args, **kwargs: ["string"]),
        min_max_validator=_ns(check_min_max_mapping=lambda *args, **kwargs: ["range"]),
        append_param_mapping_issue=lambda pm, issue: param_check_calls.append((pm.source["var_name"], issue)),
    )
    variables_contracts_module._check_param_mapping(
        check_helper,
        _ns(is_source_global=False, source={"var_name": "Unknown"}),
        None,
        {},
        ["Root"],
    )
    variables_contracts_module._check_param_mapping(
        check_helper,
        _ns(is_source_global=False, source={"var_name": "Unknown"}),
        Variable(name="Target", datatype=Simple_DataType.INTEGER),
        {},
        ["Root"],
    )
    assert param_check_calls == [("Unknown", "contract")]
