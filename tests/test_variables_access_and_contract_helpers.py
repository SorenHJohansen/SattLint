from __future__ import annotations

from collections.abc import Callable
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
from sattlint.analyzers import dataflow as dataflow_module
from sattlint.analyzers.dataflow import DataflowAnalyzer
from sattlint.analyzers.shared import _dedupe as dedupe_module
from sattlint.analyzers.variables import _variables_access as variables_access_module
from sattlint.analyzers.variables import _variables_contracts as variables_contracts_module
from sattlint.reporting.variables_report import IssueKind
from sattlint.resolution import AccessKind, CanonicalPath
from tests.helpers.variable_test_support import UsageStub as _UsageStub
from tests.helpers.variable_test_support import ns as _ns

RecordResolver = Callable[[str], object | None]

variables_access_impl: Any = variables_access_module
variables_contracts_impl: Any = variables_contracts_module
dependency_scope_mixin_impl: Any = dependency_scope_module._DependencyUsageScopeSupportMixin
DataflowAnalyzerType: Any = DataflowAnalyzer


def _resolve_no_record(_name: str) -> None:
    return None


def _make_strict_access_helper(
    *,
    fail_loudly: bool = False,
    unavailable_libraries: set[str] | None = None,
    opaque_builtin_types: set[str] | None = None,
    record_resolver: RecordResolver | None = None,
    warnings: list[str] | None = None,
) -> Any:
    return SimpleNamespace(
        fail_loudly=fail_loudly,
        unavailable_libraries=unavailable_libraries or {"Lib"},
        opaque_builtin_types=opaque_builtin_types or {"opaque"},
        type_graph=_ns(record=record_resolver or _resolve_no_record),
        site_stack=["site"],
        warn=(warnings if warnings is not None else []).append,
    )


def test_variables_access_wrapper_helpers_delegate_and_parse_fields() -> None:
    tracker_calls: list[tuple[str, object]] = []

    def _record_access(**kwargs: object) -> None:
        tracker_calls.append(("record", kwargs))

    def _mark_access(**kwargs: object) -> None:
        tracker_calls.append(("mark", kwargs))

    def _effect_key_for_variable(variable_obj: Variable, decl_path: list[str]) -> tuple[object, ...]:
        return ("effect", variable_obj.name, *decl_path)

    def _resolve_effect_key(full_ref: str, _context: object) -> tuple[str, str]:
        return ("resolved", full_ref)

    def _mapping_source_effect_key(_pm: object, **_kwargs: object) -> tuple[str]:
        return ("mapping",)

    def _resolve_local_effect_key(full_ref: str, _context: object) -> tuple[str, str]:
        return ("local", full_ref)

    def _resolve_mapped_effect_source_key(full_ref: str, _context: object) -> tuple[str, str]:
        return ("mapped", full_ref)

    def _record_effect_flow(source_key: object, target_key: object) -> None:
        tracker_calls.append(("flow", (source_key, target_key)))

    def _collect_function_input_effect_keys(
        fn_name: str | None,
        args: list[object],
        _context: object,
    ) -> set[tuple[str, int]]:
        return {(fn_name or "", len(args))}

    def _collect_expression_effect_sources(_obj: object, _context: object) -> set[tuple[str]]:
        return {("expr",)}

    def _record_assignment_effect_flow(target_ref: object, _expr: object, _context: object) -> None:
        tracker_calls.append(("assign", target_ref))

    def _record_function_call_effect_flow(fn_name: str | None, _args: list[object], _context: object) -> None:
        tracker_calls.append(("call", fn_name))

    usage_tracker = _ns(
        record_access=_record_access,
        mark_ref_access=_mark_access,
    )
    effect_tracker = _ns(
        effect_key_for_variable=_effect_key_for_variable,
        resolve_effect_key=_resolve_effect_key,
        mapping_source_effect_key=_mapping_source_effect_key,
        resolve_local_effect_key=_resolve_local_effect_key,
        resolve_mapped_effect_source_key=_resolve_mapped_effect_source_key,
        record_effect_flow=_record_effect_flow,
        collect_function_input_effect_keys=_collect_function_input_effect_keys,
        collect_expression_effect_sources=_collect_expression_effect_sources,
        record_assignment_effect_flow=_record_assignment_effect_flow,
        record_function_call_effect_flow=_record_function_call_effect_flow,
    )
    helper: Any = SimpleNamespace(
        usage_tracker=usage_tracker,
        effect_flow_tracker=effect_tracker,
        root_env={},
        any_var_index={"fallback": [Variable(name="Fallback", datatype=Simple_DataType.INTEGER)]},
    )
    variable = Variable(name="Demo", datatype=Simple_DataType.INTEGER)

    def _resolve_variable(full_ref: str) -> tuple[Variable | None, str | None, list[str], None]:
        if full_ref == "local.field":
            return (None, None, [], None)
        return (variable, "field", ["Decl"], None)

    context: Any = _ns(
        env={"local": variable},
        param_mappings={"local": object()},
        module_path=["Root"],
        resolve_variable=_resolve_variable,
    )

    assert variables_access_impl._canonical_path(helper, ["Root"], variable, "field..leaf") == CanonicalPath(
        ("Root", "Demo", "field", "leaf")
    )
    variables_access_impl._record_access(
        helper,
        AccessKind.READ,
        CanonicalPath(("Root", "Demo")),
        context,
        "Demo",
    )
    variables_access_impl._mark_ref_access(helper, "local.field", context, ["Root"], AccessKind.READ)
    variables_access_impl._mark_ref_access(helper, "resolved.field", context, ["Root"], AccessKind.WRITE)
    assert variables_access_impl._effect_key_for_variable(helper, variable, ["Root"]) == ("effect", "Demo", "Root")
    assert variables_access_impl._resolve_effect_key(helper, "x", context) == ("resolved", "x")
    assert variables_access_impl._mapping_source_effect_key(
        helper, _ns(target="x"), parent_env={}, parent_context=None
    ) == ("mapping",)
    assert variables_access_impl._resolve_local_effect_key(helper, "x", context) == ("local", "x")
    assert variables_access_impl._resolve_mapped_effect_source_key(helper, "x", context) == ("mapped", "x")
    variables_access_impl._record_effect_flow(helper, ("a",), ("b",))
    assert variables_access_impl._collect_function_input_effect_keys(helper, "Fn", [1], context) == {("Fn", 1)}
    assert variables_access_impl._collect_expression_effect_sources(helper, object(), context) == {("expr",)}
    variables_access_impl._record_assignment_effect_flow(helper, "dest", object(), context)
    variables_access_impl._record_function_call_effect_flow(helper, "Fn", [], context)

    assert len([call for call in tracker_calls if call[0] == "mark"]) == 2
    assert variables_access_impl._lookup_global_variable(helper, None) is None
    helper.root_env["direct"] = variable
    assert variables_access_impl._lookup_global_variable(helper, "direct") is variable
    assert variables_access_impl._lookup_global_variable(helper, "fallback") is not None
    assert variables_access_impl._extract_field_path(helper, {}) == (None, None)
    assert variables_access_impl._extract_field_path(helper, {"var_name": 1}) == (None, None)
    assert variables_access_impl._extract_field_path(helper, {"var_name": "Demo"}) == ("demo", None)
    assert variables_access_impl._extract_field_path(helper, {"var_name": "Demo.Field"}) == ("demo", "Field")


def test_variables_access_effect_and_site_helpers_cover_remaining_branches() -> None:
    variable = Variable(name="Demo", datatype=Simple_DataType.INTEGER)
    sink_keys = {("sink",)}

    def _is_from_root_origin(*_args: object) -> bool:
        return True

    def _collect_effect_sink_keys(_bp: object, _is_library: bool, _matcher: object) -> set[tuple[str]]:
        return sink_keys

    def _compute_effective_output_keys(keys: set[tuple[str]]) -> set[tuple[object, ...]]:
        if keys == sink_keys:
            return {("effect", "Demo", "Root")}
        return set()

    def _effect_key_for_variable(variable_obj: Variable, decl_path: list[str]) -> tuple[object, ...]:
        return ("effect", variable_obj.name, *decl_path)

    helper: Any = SimpleNamespace(
        bp=_ns(name="bp"),
        analyzed_target_is_library=False,
        is_from_root_origin=_is_from_root_origin,
        effect_flow_tracker=_ns(
            collect_effect_sink_keys=_collect_effect_sink_keys,
            compute_effective_output_keys=_compute_effective_output_keys,
            effect_key_for_variable=_effect_key_for_variable,
        ),
        effective_output_keys={("effect", "Demo", "Root")},
        site_stack=[],
    )

    assert variables_access_impl._collect_effect_sink_keys(helper) == sink_keys
    assert variables_access_impl._compute_effective_output_keys(helper) == {("effect", "Demo", "Root")}
    assert variables_access_impl._has_output_effect(helper, variable, ["Root"]) is True
    assert variables_access_impl._site_str(helper) == ""

    variables_access_impl._push_site(helper, "")
    assert helper.site_stack == []
    variables_access_impl._push_site(helper, "Step")
    assert helper.site_stack == ["Step"]
    variables_access_impl._pop_site(helper)
    variables_access_impl._pop_site(helper)
    assert helper.site_stack == []


def test_shared_dedupe_helpers_cover_seen_and_index_paths() -> None:
    seen: set[tuple[str, ...]] = set()
    indexes: dict[tuple[str, ...], int] = {}

    assert dedupe_module.remember_once(seen, ("read",)) is True
    assert dedupe_module.remember_once(seen, ("read",)) is False
    assert dedupe_module.get_or_register_index(indexes, ("mapping",), 2) is None
    assert indexes == {("mapping",): 2}
    assert dedupe_module.get_or_register_index(indexes, ("mapping",), 9) == 2


def test_variables_access_strict_datatype_helper_covers_warning_and_error_paths() -> None:
    warnings: list[str] = []
    record_with_known_field = _ns(
        name="RecordType",
        fields_by_key={"known": _ns(name="Known", datatype=Simple_DataType.INTEGER)},
    )

    def _resolve_record(name: str) -> object | None:
        if name == "Unknown":
            return None
        return record_with_known_field

    helper = _make_strict_access_helper(
        record_resolver=_resolve_record,
        warnings=warnings,
    )

    assert (
        variables_access_impl._strict_datatype_at_field_prefix(
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
        variables_access_impl._strict_datatype_at_field_prefix(
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
        variables_access_impl._strict_datatype_at_field_prefix(
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
        variables_access_impl._strict_datatype_at_field_prefix(
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
        variables_access_impl._strict_datatype_at_field_prefix(
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
        variables_access_impl._strict_datatype_at_field_prefix(
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

    def _resolve_record(name: str) -> object | None:
        if name == "Unknown":
            return None
        return record_with_known_field

    helper = _make_strict_access_helper(
        record_resolver=_resolve_record,
        warnings=warnings,
    )

    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    with pytest.raises(ValueError):
        variables_access_impl._iter_leaf_field_paths_strict(
            helper,
            "Unknown",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
        )

    helper.fail_loudly = False
    helper.unavailable_libraries = {"Lib"}
    warnings.clear()
    assert variables_access_impl._iter_leaf_field_paths_strict(
        helper,
        "Unknown",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert warnings

    helper.unavailable_libraries = set()
    warnings.clear()
    assert variables_access_impl._iter_leaf_field_paths_strict(
        helper,
        "Unknown",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert warnings

    def _resolve_builtin_or_record(name: str) -> object | None:
        if name in {"Unknown", "opaque"}:
            return None
        return record_with_known_field

    helper.type_graph = _ns(record=_resolve_builtin_or_record)
    helper.opaque_builtin_types = {"opaque"}
    assert variables_access_impl._iter_leaf_field_paths_strict(
        helper,
        "opaque",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]
    assert variables_access_impl._iter_leaf_field_paths_strict(
        helper,
        "AnyType",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]


def test_variables_access_leaf_helper_covers_record_and_cycle_paths() -> None:
    warnings: list[str] = []
    helper = _make_strict_access_helper(warnings=warnings)

    def _resolve_record(name: str) -> object | None:
        if name == "RecordType":
            return _ns(fields_by_key={"leaf": _ns(name="Leaf", datatype="AnyType")})
        return None

    helper.type_graph = _ns(record=_resolve_record)
    assert variables_access_impl._iter_leaf_field_paths_strict(
        helper,
        "RecordType",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [("Leaf",)]

    cyclic_record = _ns(fields_by_key={"self": _ns(name="Self", datatype="Loop")})

    def _resolve_loop(name: str) -> object | None:
        if name == "Loop":
            return cyclic_record
        return None

    helper.type_graph = _ns(record=_resolve_loop)
    helper.fail_loudly = True
    helper.unavailable_libraries = set()
    with pytest.raises(ValueError):
        variables_access_impl._iter_leaf_field_paths_strict(
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

    def _resolve_nested_record(name: str) -> object | None:
        return _ns(name="RecordType", fields_by_key={"known": _ns(name="Known", datatype="Nested")})

    helper.type_graph = _ns(record=_resolve_nested_record)
    with pytest.raises(ValueError):
        variables_access_impl._strict_datatype_at_field_prefix(
            helper,
            "RecordType",
            "Missing",
            fn_name="Fn",
            syntactic_ref="Ref",
            resolved_var_name="Demo",
            use_path=["Root"],
        )
    assert (
        variables_access_impl._strict_datatype_at_field_prefix(
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

    assert variables_access_impl._iter_leaf_field_paths_strict(
        helper,
        Simple_DataType.INTEGER,
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [()]

    helper.fail_loudly = False

    def _resolve_wrapper(name: str) -> object | None:
        if name == "Wrapper":
            return _ns(fields_by_key={"nested": _ns(name="Nested", datatype="AnyType")})
        return None

    helper.type_graph = _ns(record=_resolve_wrapper)
    helper.unavailable_libraries = set()
    assert variables_access_impl._iter_leaf_field_paths_strict(
        helper,
        "Wrapper",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [("Nested",)]

    def _resolve_scalar_wrapper(name: str) -> object | None:
        if name == "ScalarWrapper":
            return _ns(fields_by_key={"leaf": _ns(name="Leaf", datatype=Simple_DataType.INTEGER)})
        return None

    helper.type_graph = _ns(record=_resolve_scalar_wrapper)
    assert variables_access_impl._iter_leaf_field_paths_strict(
        helper,
        "ScalarWrapper",
        fn_name="Fn",
        syntactic_ref="Ref",
        resolved_var_name="Demo",
    ) == [("Leaf",)]


def test_variables_access_record_wide_access_and_origin_helpers() -> None:
    variable = Variable(name="Demo", datatype="RecordType")

    def _resolve_missing_variable(*_args: object) -> tuple[None, None, list[str], None]:
        return (None, None, [], None)

    unresolved_context: Any = _ns(resolve_variable=_resolve_missing_variable)
    helper: Any = SimpleNamespace(site_stack=["site"])
    with pytest.raises(ValueError):
        variables_access_impl._mark_record_wide_builtin_access(
            helper,
            "Demo",
            kind=AccessKind.READ,
            fn_name="Fn",
            context=unresolved_context,
            path=["Root"],
        )

    refs: list[tuple[str, bool]] = []

    def _resolve_present_variable(*_args: object) -> tuple[Variable, None, list[str], None]:
        return (variable, None, ["Root"], None)

    def _strict_record_type(*_args: object, **_kwargs: object) -> str:
        return "RecordType"

    def _iter_leaf_paths(*_args: object, **_kwargs: object) -> list[tuple[str, ...]]:
        return [(), ("Leaf",)]

    def _mark_ref_access(
        _self: object,
        syntactic_ref: str,
        _context: object,
        _path: list[str],
        _kind: AccessKind,
        is_ui_read: bool = False,
    ) -> None:
        refs.append((syntactic_ref, is_ui_read))

    context: Any = _ns(resolve_variable=_resolve_present_variable)
    original_strict = variables_access_impl._strict_datatype_at_field_prefix
    original_iter = variables_access_impl._iter_leaf_field_paths_strict
    original_mark = variables_access_impl._mark_ref_access
    try:
        variables_access_impl._strict_datatype_at_field_prefix = _strict_record_type
        variables_access_impl._iter_leaf_field_paths_strict = _iter_leaf_paths
        variables_access_impl._mark_ref_access = _mark_ref_access
        variables_access_impl._mark_record_wide_builtin_access(
            helper,
            "Demo",
            kind=AccessKind.WRITE,
            fn_name="Fn",
            context=context,
            path=["Root"],
            is_ui_read=True,
        )
    finally:
        variables_access_impl._strict_datatype_at_field_prefix = original_strict
        variables_access_impl._iter_leaf_field_paths_strict = original_iter
        variables_access_impl._mark_ref_access = original_mark

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
    assert DataflowAnalyzerType._is_from_root_origin(strict_library_helper, "Other.s", "projectlib") is False
    assert (
        dependency_scope_mixin_impl._is_from_root_origin(
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
    assert DataflowAnalyzerType._is_from_root_origin(specific_library_helper, "Other.s", "rootlib") is True
    assert (
        dependency_scope_mixin_impl._is_from_root_origin(
            specific_library_helper,
            "Other.s",
            "rootlib",
        )
        is True
    )


def test_dataflow_facade_and_scalar_helpers_cover_remaining_branches(monkeypatch: Any) -> None:  # noqa: PLR0915
    delegate_probe: Any = DataflowAnalyzer.__new__(DataflowAnalyzer)
    delegate_probe._issues = ["issue"]
    delegate_probe._unavailable_libraries = {"Lib"}

    def _build_scope_context(*args: object, **kwargs: object) -> tuple[str, tuple[object, ...], dict[str, object]]:
        return ("scope", args, kwargs)

    def _seed_state(
        _state: object,
        module_path: list[str],
        variables: list[object],
    ) -> dict[tuple[str], tuple[tuple[str, ...], int]]:
        return {("seeded",): (tuple(module_path), len(variables))}

    def _build_single_context(
        _mod: object,
        _parent_context: object,
        module_path: list[str],
    ) -> tuple[str, tuple[str, ...]]:
        return ("single", tuple(module_path))

    def _build_typedef_context(
        _moduletype: object,
        _instance: object,
        _parent_context: object,
        module_path: list[str],
    ) -> tuple[str, tuple[str, ...]]:
        return ("typedef", tuple(module_path))

    def _analyze_block(
        statements: list[object],
        _context: object,
        _module_path: list[str],
        _state: object,
    ) -> dict[tuple[str], int]:
        return {("block",): len(statements)}

    def _evaluate_condition(
        _condition: object,
        _context: object,
        _module_path: list[str],
        _state: object,
    ) -> bool:
        return True

    delegate_probe._build_scope_context = _build_scope_context
    delegate_probe._seed_state = _seed_state
    delegate_probe._build_single_context = _build_single_context
    delegate_probe._build_typedef_context = _build_typedef_context
    delegate_probe._analyze_block = _analyze_block
    delegate_probe._evaluate_condition = _evaluate_condition

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

    def _resolve_no_signature(_name: object) -> None:
        return None

    monkeypatch.setattr(dataflow_module, "get_function_signature", _resolve_no_signature)
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

    def _resolve_ref(arg: str, _context: object) -> object:
        return resolved_map[arg]

    def _report_invalid_old_write(resolved: object, module_path: list[str], operation: str) -> None:
        invalid_old_writes.append((getattr(resolved, "state_access", None), tuple(module_path), operation))

    def _resolve_signature(_name: object) -> Any:
        return _ns(parameters=[_ns(direction="out"), _ns(direction="inout"), _ns(direction="out")])

    delegate_probe._resolve_ref = _resolve_ref
    delegate_probe._report_invalid_old_write = _report_invalid_old_write
    delegate_probe._apply_write_target = _apply_write_target
    monkeypatch.setattr(dataflow_module, "get_function_signature", _resolve_signature)

    next_state = delegate_probe._apply_call_side_effects("Fn", ["skip", "old", "new"], context, state)

    assert invalid_old_writes == [("old", ("Root",), "inout parameter")]
    assert applied_writes == [(None, dataflow_module.UNKNOWN, ("Root",), True)]
    assert next_state[("written",)] is dataflow_module.UNKNOWN

    write_probe: Any = DataflowAnalyzer.__new__(DataflowAnalyzer)

    def _resolve_missing_ref(_expr: object, _context: object) -> None:
        return None

    write_probe._resolve_ref = _resolve_missing_ref
    assert write_probe._write_target({"var_name": "missing"}, 1, context, state) is state

    helper_probe: Any = DataflowAnalyzer.__new__(DataflowAnalyzer)

    def _field(_datatype: object, field_name: str) -> object | None:
        if field_name == "missing":
            return None
        return _ns(datatype=None, state=True)

    def _resolve_context_variable(full_name: str) -> tuple[Variable | None, str, list[str], None]:
        if full_name == "Missing":
            return (None, "", ["Root"], None)
        return (Variable(name="Value", datatype=Simple_DataType.INTEGER), "", ["Root"], None)

    helper_probe._type_graph = _ns(field=_field)

    missing_context = _ns(
        module_path=["Root"],
        resolve_variable=_resolve_context_variable,
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
    probe: Any = Probe.__new__(Probe)
    probe.bp = _ns(moduletype_defs=[root_typedef, dep_typedef], origin_file="Root.s", origin_lib=None)
    probe._analyzed_target_is_library = False
    probe._unavailable_libraries = set()
    probe._moduleparameter_keys_by_context = cast(dict[int, set[str]], {})

    def _is_from_root_origin(origin_file: object, _origin_lib: object | None = None) -> bool:
        return origin_file == "Root.s"

    probe._is_from_root_origin = _is_from_root_origin

    assert probe._iter_root_typedefs() == [root_typedef]

    parent_context = _ns(marker="parent")
    param = Variable(name="Param", datatype=Simple_DataType.INTEGER)
    local = Variable(name="Local", datatype=Simple_DataType.INTEGER)
    built: Any = probe._build_scope_context(
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

    def _resolve_variable(full_source: object) -> tuple[Variable | None, str | None, list[str], list[str]]:
        if str(full_source).startswith("Source"):
            return (source_var, "Field", ["Decl"], ["Display"])
        return (None, None, [], [])

    resolved: Any = probe._build_parameter_mappings(
        [
            _ns(is_source_global=True, target={"var_name": "Skip"}, source={"var_name": "Source"}),
            _ns(is_source_global=False, target={}, source={"var_name": "Source"}),
            _ns(is_source_global=False, target={"var_name": "TargetA"}, source=object()),
            _ns(is_source_global=False, target={"var_name": "TargetB"}, source={"var_name": "Missing"}),
            _ns(is_source_global=False, target={"var_name": "TargetC"}, source={"var_name": "Source.Field"}),
            _ns(is_source_global=False, target={"var_name": "TargetD"}, source="Source.Other"),
        ],
        _ns(resolve_variable=_resolve_variable),
    )
    assert resolved == {
        "targetc": (source_var, "Field", ["Decl"], ["Display"]),
        "targetd": (source_var, "Field", ["Decl"], ["Display"]),
    }


def test_dependency_scope_support_walk_helpers_cover_branches(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: PLR0915
    class Probe(dependency_scope_module._DependencyUsageScopeSupportMixin):
        pass

    module_code_calls: list[tuple[object | None, list[str]]] = []
    typedef_calls: list[tuple[object, list[str], Any]] = []
    instance_calls: list[tuple[object, list[str]]] = []

    probe: Any = Probe.__new__(Probe)
    probe.bp = _ns(origin_file="Root.s", origin_lib=None)
    probe._analyzed_target_is_library = False
    probe._unavailable_libraries = set()
    probe._moduleparameter_keys_by_context = cast(dict[int, set[str]], {})

    def _walk_module_code(modulecode: object | None, _context: object, module_path: list[str]) -> None:
        module_code_calls.append((modulecode, module_path))

    def _walk_typedef(moduletype: object, context: object, module_path: list[str]) -> None:
        typedef_calls.append((moduletype, module_path, context))

    def _is_from_root_origin(origin_file: object, _origin_lib: object | None = None) -> bool:
        return origin_file == "Root.s"

    probe._walk_module_code = _walk_module_code
    probe._walk_typedef = _walk_typedef
    probe._is_from_root_origin = _is_from_root_origin

    single = SingleModule.__new__(SingleModule)
    single.header = _ns(name="Single")
    single.moduleparameters = [Variable(name="Param", datatype=Simple_DataType.INTEGER)]
    single.localvariables = [Variable(name="Local", datatype=Simple_DataType.INTEGER)]
    single.parametermappings = [_ns(is_source_global=False, target={"var_name": "Param"}, source="Source")]
    single.modulecode = cast(Any, "single-code")
    single.submodules = []

    frame = FrameModule.__new__(FrameModule)
    frame.header = _ns(name="Frame")
    frame.modulecode = cast(Any, "frame-code")
    frame.submodules = []

    inst = ModuleTypeInstance.__new__(ModuleTypeInstance)
    inst.header = _ns(name="Inst")
    inst.moduletype_name = "ChildType"
    inst.parametermappings = []

    def _resolve_parent_variable(_full_source: object) -> tuple[Variable, None, list[str], list[str]]:
        return (
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            None,
            ["Decl"],
            ["Display"],
        )

    parent_context = _ns(
        env={"source": Variable(name="Source", datatype=Simple_DataType.INTEGER)},
        param_mappings={},
        current_library="Lib",
        resolve_variable=_resolve_parent_variable,
    )

    original_walk_instance: Any | None = getattr(probe, "_walk_moduletype_instance", None)

    def _walk_instance(instance: object, _parent_context: object, child_path: list[str]) -> None:
        instance_calls.append((instance, child_path))

    def _raise_missing_typedef(*_args: object, **_kwargs: object) -> object:
        raise ValueError("missing")

    dep_resolved_typedef = _ns(origin_file="Dep.s", origin_lib="DepLib", moduleparameters=[], localvariables=[])

    def _resolve_dep_typedef(*_args: object, **_kwargs: object) -> Any:
        return dep_resolved_typedef

    def _resolve_root_typedef(*_args: object, **_kwargs: object) -> Any:
        return resolved_typedef

    probe._walk_moduletype_instance = _walk_instance
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
        _raise_missing_typedef,
    )
    probe._walk_moduletype_instance(inst, parent_context, ["Root", "Inst"])

    monkeypatch.setattr(
        dependency_scope_module,
        "resolve_moduletype_def_strict",
        _resolve_dep_typedef,
    )
    probe._walk_moduletype_instance(inst, parent_context, ["Root", "Inst"])

    monkeypatch.setattr(dependency_scope_module, "resolve_moduletype_def_strict", _resolve_root_typedef)
    probe._walk_moduletype_instance(inst, parent_context, ["Root", "Inst"])
    assert len(typedef_calls) == 1
    moduletype, module_path, typedef_context = typedef_calls[0]
    assert moduletype is resolved_typedef
    assert module_path == ["Root", "Inst"]
    assert typedef_context.current_library == "ResolvedLib"


def test_variables_contracts_cover_guard_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    non_any = Variable(name="Scalar", datatype=Simple_DataType.INTEGER)
    any_param = Variable(name="AnyParam", datatype="AnyType")

    def _get_empty_usage(_variable: Variable) -> _UsageStub:
        return _UsageStub()

    def _iter_no_typedefs() -> list[object]:
        return []

    extractor: Any = _ns(get_usage=_get_empty_usage)
    assert variables_contracts_impl._build_anytype_parameter_contract(_ns(), extractor, non_any) is None
    assert variables_contracts_impl._build_anytype_parameter_contract(_ns(), extractor, any_param) is None

    helper: Any = SimpleNamespace(iter_anytype_typedefs=_iter_no_typedefs)
    assert variables_contracts_impl._build_anytype_field_contracts(helper) == {}

    display_only = Variable(name="DisplayOnly", datatype=Simple_DataType.INTEGER)
    required = Variable(name="Required", datatype=Simple_DataType.INTEGER)
    moduletype: Any = _ns(moduleparameters=[display_only, required], name="Worker")
    usage_by_id = {
        id(display_only): _UsageStub(read=True, is_display_only=True),
        id(required): _UsageStub(read=True),
    }

    def _analyze_typedef_noop(*_args: object, **_kwargs: object) -> None:
        return None

    def _lookup_usage(variable: Variable) -> _UsageStub:
        return usage_by_id[id(variable)]

    def _make_nested_contract_extractor(_self: object) -> SimpleNamespace:
        return SimpleNamespace(analyze_typedef=_analyze_typedef_noop, get_usage=_lookup_usage)

    monkeypatch.setattr(
        variables_contracts_module,
        "_make_nested_contract_extractor",
        _make_nested_contract_extractor,
    )
    owner: Any = _ns(bp=_ns(header=_ns(name="Root")), required_parameter_names_by_owner={})
    assert variables_contracts_impl._get_required_parameter_names_for_typedef(owner, moduletype) == {
        "required": "Required"
    }

    issues: list[str] = []
    parameter = Variable(name="Required", datatype=Simple_DataType.INTEGER)

    def _get_parameter_usage(variable: Variable) -> _UsageStub:
        return _UsageStub(read=True, is_display_only=variable is not parameter)

    def _append_issue(issue: Any) -> None:
        issues.append(cast(str, issue.role))

    def _record_checked(*_args: object, **_kwargs: object) -> None:
        issues.append("checked")

    self_single: Any = SimpleNamespace(
        get_usage=_get_parameter_usage,
        append_issue=_append_issue,
        check_param_mapping=_record_checked,
    )
    mod: Any = _ns(
        moduleparameters=[Variable(name="Display", datatype=Simple_DataType.INTEGER), parameter], parametermappings=[]
    )
    variables_contracts_impl._check_param_mappings_for_single(self_single, mod, {}, {}, cast(Any, None), ["Root"])
    assert issues == ["required parameter connection missing for 'Required'"]

    inst: Any = _ns(moduletype_name="Missing", parametermappings=[])

    def _required_parameter_names(_mt: object) -> dict[str, str]:
        return {"missing": "Missing"}

    def _raise_unexpected_issue(_issue: object) -> None:
        raise AssertionError("unexpected issue")

    def _noop_mapping_check(*_args: object, **_kwargs: object) -> None:
        return None

    def _raise_missing_typedef(*_args: object, **_kwargs: object) -> object:
        raise ValueError("missing")

    def _resolve_empty_typedef(*_args: object, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(moduleparameters=[])

    self_inst: Any = SimpleNamespace(
        bp=_ns(),
        unavailable_libraries=set(),
        get_required_parameter_names_for_typedef=_required_parameter_names,
        append_issue=_raise_unexpected_issue,
        check_param_mapping=_noop_mapping_check,
    )
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        _raise_missing_typedef,
    )
    variables_contracts_impl._check_param_mappings_for_type_instance(self_inst, inst, {}, cast(Any, None), ["Root"])
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        _resolve_empty_typedef,
    )
    variables_contracts_impl._check_param_mappings_for_type_instance(self_inst, inst, {}, cast(Any, None), ["Root"])


def test_variables_contracts_cover_remaining_collection_and_index_branches(  # noqa: PLR0915
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    any_param = Variable(name="AnyParam", datatype="AnyType")
    any_usage = _UsageStub(field_reads={"Leaf": [object()]}, field_writes={"Other": [object()]})

    def _get_any_usage(_variable: Variable) -> _UsageStub:
        return any_usage

    contract = variables_contracts_impl._build_anytype_parameter_contract(
        _ns(),
        _ns(get_usage=_get_any_usage),
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
    nested_single.header = _ns(name="Nested")
    nested_single.moduleparameters = [nested_param]
    nested_single.localvariables = [nested_local]
    nested_single.submodules = []

    frame = FrameModule.__new__(FrameModule)
    frame.header = _ns(name="Frame")
    frame.submodules = [nested_single]

    index_helper: Any = _ns(
        any_var_index={},
        bp=_ns(
            localvariables=[root_local],
            submodules=[frame],
            moduletype_defs=[_ns(moduleparameters=[typedef_param], localvariables=[typedef_local])],
        ),
    )
    variables_contracts_impl._index_all_variables(index_helper)
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

    def _get_single_usage(_variable: Variable) -> _UsageStub:
        return _UsageStub(read=True)

    def _append_single_issue(issue: Any) -> None:
        single_calls.append(cast(str, issue.role))

    def _append_single_checked(*_args: object, **_kwargs: object) -> None:
        single_calls.append("checked")

    single_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.REQUIRED_PARAMETER_CONNECTION},
        get_usage=_get_single_usage,
        append_issue=_append_single_issue,
        check_param_mapping=_append_single_checked,
    )
    variables_contracts_impl._check_param_mappings_for_single(
        single_helper,
        single_mod,
        {},
        {},
        cast(Any, None),
        ["Root"],
    )
    assert single_calls == ["required parameter connection missing for 'Required'"]

    inst: Any = _ns(moduletype_name="Worker", parametermappings=[])
    disabled_type_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.UI_ONLY},
        bp=_ns(),
        unavailable_libraries=set(),
    )

    def _raise_should_not_resolve(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("should not resolve")

    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        _raise_should_not_resolve,
    )
    variables_contracts_impl._check_param_mappings_for_type_instance(
        disabled_type_helper,
        inst,
        {},
        cast(Any, None),
        ["Root"],
    )

    type_calls: list[str] = []
    missing_param = Variable(name="Missing", datatype=Simple_DataType.INTEGER)

    def _required_names(_mt: object) -> dict[str, str]:
        return {"missing": "Missing", "ghost": "Ghost"}

    def _append_type_issue(issue: Any) -> None:
        type_calls.append(cast(str, issue.role))

    def _append_type_checked(*_args: object, **_kwargs: object) -> None:
        type_calls.append("checked")

    def _resolve_type_instance(*_args: object, **_kwargs: object) -> Any:
        return _ns(moduleparameters=[missing_param])

    type_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.REQUIRED_PARAMETER_CONNECTION},
        bp=_ns(),
        unavailable_libraries=set(),
        get_required_parameter_names_for_typedef=_required_names,
        append_issue=_append_type_issue,
        check_param_mapping=_append_type_checked,
    )
    monkeypatch.setattr(
        variables_contracts_module,
        "resolve_moduletype_def_strict",
        _resolve_type_instance,
    )
    variables_contracts_impl._check_param_mappings_for_type_instance(
        type_helper,
        inst,
        {},
        cast(Any, None),
        ["Root"],
    )
    assert type_calls == ["required parameter connection missing for 'Missing'"]

    mapping_calls: list[tuple[str, object]] = []
    src_var = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    tgt_var = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    pm_global: Any = _ns(is_source_global=True, source={"var_name": "Source"})
    pm_local: Any = _ns(is_source_global=False, source={"var_name": "RootSource"})

    def _lookup_env_var(_source_ref: object, _env: object) -> None:
        return None

    def _check_contract_mapping(*_args: object, **_kwargs: object) -> list[SimpleNamespace]:
        return [SimpleNamespace(label="contract")]

    def _check_string_mapping(*_args: object, **_kwargs: object) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                label="string",
                source_variable=None,
                source_decl_module_path=None,
                source_role=None,
            )
        ]

    def _check_min_max_mapping(*_args: object, **_kwargs: object) -> list[SimpleNamespace]:
        return [SimpleNamespace(label="range")]

    def _append_mapping_issue(pm: Any, issue: Any) -> None:
        mapping_calls.append((pm.source["var_name"], issue.label))

    mapping_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.CONTRACT_MISMATCH},
        lookup_env_var_from_varname_dict=_lookup_env_var,
        root_env={"rootsource": src_var},
        contract_validator=_ns(check_contract_mapping=_check_contract_mapping),
        string_validator=_ns(check_string_mapping=_check_string_mapping),
        min_max_validator=_ns(check_min_max_mapping=_check_min_max_mapping),
        append_param_mapping_issue=_append_mapping_issue,
    )
    variables_contracts_impl._check_param_mapping(
        cast(Any, SimpleNamespace(_selected_issue_kinds={IssueKind.REQUIRED_PARAMETER_CONNECTION})),
        pm_local,
        tgt_var,
        {},
        cast(Any, None),
        ["Root"],
    )
    variables_contracts_impl._check_param_mapping(
        mapping_helper,
        pm_global,
        tgt_var,
        {},
        cast(Any, None),
        ["Root"],
    )
    variables_contracts_impl._check_param_mapping(
        mapping_helper,
        pm_local,
        tgt_var,
        {},
        cast(Any, None),
        ["Root"],
    )
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

    def _iter_anytype_typedefs() -> list[Any]:
        return [any_typedef]

    def _build_anytype_parameter_contract(_extractor: object, variable: Variable) -> None:
        build_calls.append(variable.name)
        return None

    def _analyze_typedef_noop(*_args: object, **_kwargs: object) -> None:
        return None

    def _make_nested_contract_extractor(_self: object) -> Any:
        return _ns(analyze_typedef=_analyze_typedef_noop)

    contract_owner: Any = SimpleNamespace(
        bp=_ns(header=_ns(name="Root")),
        iter_anytype_typedefs=_iter_anytype_typedefs,
        build_anytype_parameter_contract=_build_anytype_parameter_contract,
    )
    monkeypatch.setattr(
        variables_contracts_module,
        "_make_nested_contract_extractor",
        _make_nested_contract_extractor,
    )
    assert variables_contracts_impl._build_anytype_field_contracts(contract_owner) == {}
    assert build_calls == ["Payload"]

    guard_calls: list[str] = []
    mapped_parameter = Variable(name="Mapped", datatype=Simple_DataType.INTEGER)
    idle_parameter = Variable(name="Idle", datatype=Simple_DataType.INTEGER)
    mapping = _ns(target={"var_name": "Mapped"})

    def _get_guard_usage(_variable: Variable) -> _UsageStub:
        return _UsageStub(read=True)

    def _append_guard_issue(issue: Any) -> None:
        guard_calls.append(cast(str, issue.role))

    def _append_guard_checked(*_args: object, **_kwargs: object) -> None:
        guard_calls.append("checked")

    single_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.UI_ONLY},
        get_usage=_get_guard_usage,
        append_issue=_append_guard_issue,
        check_param_mapping=_append_guard_checked,
    )
    single_mod: Any = _ns(moduleparameters=[mapped_parameter, idle_parameter], parametermappings=[mapping])
    variables_contracts_impl._check_param_mappings_for_single(
        single_helper,
        single_mod,
        {},
        {},
        cast(Any, None),
        ["Root"],
    )
    assert guard_calls == []

    single_helper._selected_issue_kinds = {
        IssueKind.REQUIRED_PARAMETER_CONNECTION,
        IssueKind.CONTRACT_MISMATCH,
    }

    def _get_no_guard_usage(_variable: Variable) -> _UsageStub:
        return _UsageStub(read=False, written=False)

    single_helper.get_usage = _get_no_guard_usage
    variables_contracts_impl._check_param_mappings_for_single(
        single_helper,
        single_mod,
        {},
        {},
        cast(Any, None),
        ["Root"],
    )
    assert guard_calls == [("checked")]

    param_check_calls: list[tuple[str, object | None]] = []

    def _lookup_env_var(_source_ref: object, _env: object) -> None:
        return None

    def _check_contract_mapping(*_args: object, **_kwargs: object) -> list[str]:
        return ["contract"]

    def _check_string_mapping(*_args: object, **_kwargs: object) -> list[str]:
        return ["string"]

    def _check_min_max_mapping(*_args: object, **_kwargs: object) -> list[str]:
        return ["range"]

    def _append_param_check_issue(pm: Any, issue: object | None) -> None:
        param_check_calls.append((pm.source["var_name"], issue))

    check_helper: Any = SimpleNamespace(
        _selected_issue_kinds={IssueKind.CONTRACT_MISMATCH},
        lookup_env_var_from_varname_dict=_lookup_env_var,
        root_env={},
        contract_validator=_ns(check_contract_mapping=_check_contract_mapping),
        string_validator=_ns(check_string_mapping=_check_string_mapping),
        min_max_validator=_ns(check_min_max_mapping=_check_min_max_mapping),
        append_param_mapping_issue=_append_param_check_issue,
    )
    variables_contracts_impl._check_param_mapping(
        check_helper,
        _ns(is_source_global=False, source={"var_name": "Unknown"}, source_literal=None),
        None,
        {},
        cast(Any, None),
        ["Root"],
    )
    variables_contracts_impl._check_param_mapping(
        check_helper,
        _ns(is_source_global=False, source={"var_name": "Unknown"}, source_literal=None),
        Variable(name="Target", datatype=Simple_DataType.INTEGER),
        {},
        cast(Any, None),
        ["Root"],
    )
    assert param_check_calls == [("Unknown", "contract")]
