from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattline_parser.models.ast_model import Simple_DataType, Variable
from sattlint.analyzers import _variables_access as variables_access_module
from sattlint.analyzers import _variables_contracts as variables_contracts_module
from sattlint.resolution import AccessKind, CanonicalPath


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


def test_variables_access_strict_datatype_and_leaf_helpers_cover_warning_and_error_paths() -> None:
    warnings: list[str] = []
    record_with_known_field = _ns(
        name="RecordType",
        fields_by_key={"known": _ns(name="Known", datatype=Simple_DataType.INTEGER)},
    )
    helper: Any = SimpleNamespace(
        fail_loudly=False,
        unavailable_libraries={"Lib"},
        opaque_builtin_types={"opaque"},
        type_graph=_ns(record=lambda name: None if name == "Unknown" else record_with_known_field),
        site_stack=["site"],
        warn=warnings.append,
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
    assert variables_access_module._is_from_root_origin(library_helper, "Other.s", "rootlib") is True

    class BrokenPath:
        def __init__(self, value: str) -> None:
            self.value = value

        def rsplit(self, sep: str, maxsplit: int) -> list[str]:
            return self.value.rsplit(sep, maxsplit)

    fallback_helper: Any = _ns(
        analyzed_target_is_library=False,
        bp=_ns(origin_file=BrokenPath("Root.s")),
    )
    assert variables_access_module._is_from_root_origin(fallback_helper, cast(Any, BrokenPath("Root.x"))) is True
    assert (
        variables_access_module._is_from_root_origin(_ns(analyzed_target_is_library=False, bp=_ns()), "Root.x") is False
    )

    broken_library_helper: Any = _ns(
        analyzed_target_is_library=True,
        bp=_ns(origin_lib="Root", origin_file=BrokenPath("Root.s")),
    )
    assert variables_access_module._is_from_root_origin(broken_library_helper, "Other.s", "root") is True


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
