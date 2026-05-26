"""Focused tests for effect-flow helper coverage and mapping propagation."""

from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace
from typing import Any

from sattline_parser.models.ast_model import (
    ModuleHeader,
    ParameterMapping,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.analyzers import _variables_effect_flow as effect_flow_module
from sattlint.analyzers import _variables_effect_sources as effect_sources_module
from sattlint.analyzers._variables_effect_flow import EffectFlowTracker
from sattlint.resolution import AccessKind
from sattlint.resolution.scope import ScopeContext


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def _string_source(text: str) -> Any:
    return text


def test_parameter_mapping_normalizes_string_variable_refs() -> None:
    mapping = ParameterMapping(
        target="Input",
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source="ParentLocal.Member",
        source_literal=None,
    )

    assert mapping.target == _varref("Input")
    assert mapping.source == _varref("ParentLocal.Member")


class _UsageRecorder:
    def __init__(self) -> None:
        self.read_paths: list[tuple[str, ...]] = []
        self.ui_read_paths: list[tuple[str, ...]] = []
        self.write_paths: list[tuple[str, ...]] = []
        self.field_reads: list[tuple[str, tuple[str, ...]]] = []
        self.field_writes: list[tuple[str, tuple[str, ...]]] = []

    def mark_read(self, path: list[str], *, ui: bool = False) -> None:
        path_tuple = tuple(path)
        self.read_paths.append(path_tuple)
        if ui:
            self.ui_read_paths.append(path_tuple)

    def mark_ui_read(self, path: list[str]) -> None:
        self.mark_read(path, ui=True)

    def mark_written(self, path: list[str]) -> None:
        self.write_paths.append(tuple(path))

    def mark_field_read(self, field_path: str, path: list[str], *, ui: bool = False) -> None:
        if ui:
            self.ui_read_paths.append(tuple(path))
        self.field_reads.append((field_path, tuple(path)))

    def mark_field_written(self, field_path: str, path: list[str]) -> None:
        self.field_writes.append((field_path, tuple(path)))


def _build_tracker(*, lookup_global=None):
    edges: defaultdict[tuple[str, ...], set[tuple[str, ...]]] = defaultdict(set)
    effect_flow_display_names: dict[tuple[str, ...], str] = {}
    external_effect_sinks: set[tuple[str, ...]] = set()
    usage_by_name: dict[str, _UsageRecorder] = {}
    access_calls: list[tuple[AccessKind, tuple[tuple[str, ...], str, str], tuple[str, ...], str]] = []

    def _get_usage(variable: Variable) -> _UsageRecorder:
        return usage_by_name.setdefault(variable.name, _UsageRecorder())

    def _canonical_path(path: list[str], variable: Variable, field_path: str) -> tuple[tuple[str, ...], str, str]:
        return (tuple(path), variable.name, field_path)

    def _record_access(
        kind: AccessKind,
        canonical_path: tuple[tuple[str, ...], str, str],
        context: ScopeContext,
        full_ref: str,
    ) -> None:
        access_calls.append((kind, canonical_path, tuple(context.module_path), full_ref))

    tracker = EffectFlowTracker(
        effect_flow_edges=edges,
        effect_flow_display_names=effect_flow_display_names,
        external_effect_sinks=external_effect_sinks,
        effective_output_keys=set(),
        lookup_global_variable_fn=lookup_global or (lambda _name: None),
        get_usage_fn=_get_usage,
        canonical_path_fn=_canonical_path,
        record_access_fn=_record_access,
    )
    return tracker, edges, external_effect_sinks, usage_by_name, access_calls


def _context(
    *,
    env: dict[str, Variable],
    param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]] | None = None,
    module_path: list[str] | None = None,
    parent_context: ScopeContext | None = None,
) -> ScopeContext:
    path = module_path or ["Root"]
    return ScopeContext(
        env=env,
        param_mappings=param_mappings or {},
        module_path=path,
        display_module_path=path.copy(),
        parent_context=parent_context,
    )


class _ResolveContext(ScopeContext):
    def __init__(self, result: tuple[Variable | None, str, list[str], list[str]]) -> None:
        super().__init__(
            env={},
            param_mappings={},
            module_path=["Root"],
            display_module_path=["Root"],
            parent_context=None,
        )
        self._result = result

    def resolve_variable(self, var_ref: str) -> tuple[Variable | None, str, list[str], list[str]]:
        return self._result


def test_effect_source_helpers_cover_fallback_and_signature_paths(monkeypatch) -> None:
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    mapped = Variable(name="Mapped", datatype=Simple_DataType.INTEGER)
    tracker, _edges, _external, _usage, _access = _build_tracker()
    context = _context(
        env={"source": source, "target": target},
        param_mappings={"mapped": (mapped, "inner", ["Decl"], ["Decl"])},
    )

    def _signature(name: str):
        if name == "SignedFn":
            return SimpleNamespace(
                parameters=[
                    SimpleNamespace(direction="in"),
                    SimpleNamespace(direction="out"),
                    SimpleNamespace(direction="inout"),
                ]
            )
        return None

    monkeypatch.setattr(effect_sources_module, "get_function_signature", _signature)

    no_name_sources = effect_sources_module.collect_function_input_effect_keys(
        None,
        [SimpleNamespace(data="Expr", children=[_varref("Source")]), [_varref("Mapped")]],
        context,
        resolve_effect_key=tracker.resolve_effect_key,
    )
    unknown_sources = effect_sources_module.collect_function_input_effect_keys(
        "UnknownFn",
        [("Pair", _varref("Source"), {"nested": [_varref("Mapped")]})],
        context,
        resolve_effect_key=tracker.resolve_effect_key,
    )
    signed_sources = effect_sources_module.collect_function_input_effect_keys(
        "SignedFn",
        [_varref("Source"), _varref("Target"), _varref("Mapped")],
        context,
        resolve_effect_key=tracker.resolve_effect_key,
    )
    expression_sources = effect_sources_module.collect_expression_effect_sources(
        (const.KEY_FUNCTION_CALL, "SignedFn", [_varref("Source"), _varref("Target"), _varref("Mapped")]),
        context,
        resolve_effect_key=tracker.resolve_effect_key,
    )

    expected = {("root", "source"), ("decl", "mapped")}
    assert no_name_sources == expected
    assert unknown_sources == expected
    assert signed_sources == expected
    assert expression_sources == expected


def test_effect_source_helpers_cover_guard_returns_and_missing_resolution(monkeypatch) -> None:
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    context = _context(env={"source": source})

    monkeypatch.setattr(effect_sources_module, "get_function_signature", lambda _name: None)

    assert (
        effect_sources_module.collect_expression_effect_sources(
            None,
            context,
            resolve_effect_key=lambda _ref, _ctx: None,
        )
        == set()
    )

    assert (
        effect_sources_module.collect_function_input_effect_keys(
            "CopyVariable",
            [],
            context,
            resolve_effect_key=lambda _ref, _ctx: None,
        )
        == set()
    )
    assert (
        effect_sources_module.collect_function_input_effect_keys(
            "InitVariable",
            [_varref("Source")],
            context,
            resolve_effect_key=lambda _ref, _ctx: None,
        )
        == set()
    )
    assert (
        effect_sources_module.collect_expression_effect_sources(
            _varref("Missing"),
            context,
            resolve_effect_key=lambda _ref, _ctx: None,
        )
        == set()
    )


def test_effect_flow_tracker_initvariable_inputs_include_source_only() -> None:
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    context = _context(env={"source": source, "target": target})
    tracker = EffectFlowTracker(
        effect_flow_edges={},
        effect_flow_display_names={},
        external_effect_sinks=set(),
        effective_output_keys=set(),
        lookup_global_variable_fn=lambda _name: None,
        get_usage_fn=lambda _var: None,
        canonical_path_fn=lambda _path, _var, _field: None,
        record_access_fn=lambda _kind, _path, _ctx, _ref: None,
    )

    sources = tracker.collect_function_input_effect_keys(
        "CopyVariable",
        [_varref("Source"), _varref("Target")],
        context,
    )
    init_sources = tracker.collect_function_input_effect_keys(
        "InitVariable",
        [_varref("Target"), _varref("Source")],
        context,
    )

    assert sources == {("root", "source")}
    assert init_sources == {("root", "source")}


def test_effect_flow_tracker_resolve_and_assignment_helpers_cover_local_mapped_and_missing() -> None:
    local = Variable(name="Local", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    mapped = Variable(name="Mapped", datatype=Simple_DataType.INTEGER)
    tracker, edges, _external, _usage, _access = _build_tracker(
        lookup_global=lambda name: local if name == "fallback" else None
    )
    context = _context(
        env={"local": local, "target": target},
        param_mappings={"mapped": (mapped, "inner", ["Decl"], ["Decl"])},
    )
    resolved = Variable(name="Resolved", datatype=Simple_DataType.INTEGER)
    resolved_context = _ResolveContext((resolved, "deep", ["Decl"], ["Decl"]))
    missing_context = _ResolveContext((None, "", ["Root"], ["Root"]))

    assert tracker.resolve_effect_key("Local.Member", context) == ("root", "local")
    assert tracker.resolve_effect_key("Resolved.Member", resolved_context) == ("decl", "resolved")
    assert tracker.resolve_effect_key("Missing", missing_context) is None
    assert tracker.resolve_local_effect_key("Local.Member", context) == ("root", "local")
    assert tracker.resolve_local_effect_key("Unknown.Member", context) is None
    assert tracker.resolve_mapped_effect_source_key("Mapped.Value", context) == ("decl", "mapped")
    assert tracker.resolve_mapped_effect_source_key("Unknown.Value", context) is None

    non_global_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("Local.Member"),
        source_literal=None,
    )
    invalid_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=None,
        source_literal=None,
    )

    assert tracker.mapping_source_effect_key(non_global_mapping, parent_env={"local": local}, parent_context=None) == (
        "local",
        "local",
    )
    assert tracker.mapping_source_effect_key(invalid_mapping, parent_env={}, parent_context=None) is None

    tracker.record_effect_flow(None, ("root", "target"))
    tracker.record_effect_flow(("root", "source"), None)
    assert dict(edges) == {}

    tracker.record_assignment_effect_flow(
        "Target",
        ("Pair", _varref("Local"), {"nested": [_varref("Mapped")]}),
        context,
    )

    assert edges == {
        ("root", "local"): {("root", "target")},
        ("decl", "mapped"): {("root", "target")},
    }


def test_effect_flow_tracker_mapping_source_effect_key_covers_string_parent_and_missing_cases() -> None:
    parent_local = Variable(name="ParentLocal", datatype=Simple_DataType.INTEGER)
    parent_global = Variable(name="ParentGlobal", datatype=Simple_DataType.INTEGER)
    tracker, _edges, _external, _usage, _access = _build_tracker()
    parent_context = _context(
        env={"parentlocal": parent_local, "parentglobal": parent_global},
        module_path=["Root", "Parent"],
    )

    global_string = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_string_source("ParentGlobal.Member"),
        source_literal=None,
    )
    missing_global = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_string_source(""),
        source_literal=None,
    )
    unknown_global = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_string_source("Unknown.Member"),
        source_literal=None,
    )
    local_string = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_string_source("ParentLocal.Member"),
        source_literal=None,
    )
    missing_local = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_string_source(""),
        source_literal=None,
    )
    unknown_local = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_string_source("Unknown.Member"),
        source_literal=None,
    )

    assert global_string.source == _varref("ParentGlobal.Member")
    assert local_string.source == _varref("ParentLocal.Member")

    assert tracker.mapping_source_effect_key(global_string, parent_env={}, parent_context=parent_context) == (
        "root",
        "parent",
        "parentglobal",
    )
    assert tracker.mapping_source_effect_key(missing_global, parent_env={}, parent_context=parent_context) is None
    assert tracker.mapping_source_effect_key(unknown_global, parent_env={}, parent_context=parent_context) is None
    assert tracker.mapping_source_effect_key(local_string, parent_env={}, parent_context=parent_context) == (
        "root",
        "parent",
        "parentlocal",
    )
    assert tracker.mapping_source_effect_key(missing_local, parent_env={}, parent_context=None) is None
    assert tracker.mapping_source_effect_key(unknown_local, parent_env={}, parent_context=None) is None


def test_effect_flow_tracker_record_function_call_effect_flow_covers_special_and_signature_paths(monkeypatch) -> None:
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    mapped = Variable(name="Mapped", datatype=Simple_DataType.INTEGER)
    tracker, edges, _external, _usage, _access = _build_tracker()
    context = _context(
        env={"source": source, "target": target},
        param_mappings={"mapped": (mapped, "inner", ["Decl"], ["Decl"])},
    )

    def _signature(name: str):
        if name == "SignedFn":
            return SimpleNamespace(
                parameters=[
                    SimpleNamespace(direction="in"),
                    SimpleNamespace(direction="out"),
                    SimpleNamespace(direction="inout"),
                ]
            )
        return None

    monkeypatch.setattr(effect_flow_module, "get_function_signature", _signature)

    tracker.record_function_call_effect_flow(None, [], context)
    tracker.record_function_call_effect_flow("CopyVariable", [_varref("Source")], context)
    tracker.record_function_call_effect_flow("CopyVariable", ["bad", _varref("Target")], context)
    assert dict(edges) == {}

    tracker.record_function_call_effect_flow("InitVariable", [_varref("Target"), _varref("Source")], context)
    assert edges == {("root", "source"): {("root", "target")}}

    edges.clear()
    tracker.record_function_call_effect_flow(
        "SignedFn",
        [_varref("Source"), _varref("Target"), _varref("Mapped")],
        context,
    )
    tracker.record_function_call_effect_flow("UnknownFn", [_varref("Source")], context)

    assert ("root", "target") in edges[("root", "source")]
    assert ("decl", "mapped") in edges[("root", "source")]
    assert ("decl", "mapped") in edges[("decl", "mapped")]


def test_effect_flow_tracker_record_function_call_effect_flow_ignores_unresolved_outputs(monkeypatch) -> None:
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    tracker, edges, _external, _usage, _access = _build_tracker()
    context = _context(env={"source": source})

    monkeypatch.setattr(
        effect_flow_module,
        "get_function_signature",
        lambda name: (
            SimpleNamespace(
                parameters=[
                    SimpleNamespace(direction="in"),
                    SimpleNamespace(direction="out"),
                ]
            )
            if name == "SignedFn"
            else None
        ),
    )

    tracker.record_function_call_effect_flow("InitVariable", [_varref("Source")], context)
    tracker.record_function_call_effect_flow("InitVariable", ["bad", _varref("Source")], context)

    tracker.record_function_call_effect_flow(
        "SignedFn",
        [_varref("Source"), _varref("MissingTarget")],
        context,
    )

    assert dict(edges) == {}


def test_effect_flow_tracker_special_function_paths_ignore_unreadable_var_refs(monkeypatch) -> None:
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    target = Variable(name="Target", datatype=Simple_DataType.INTEGER)
    tracker, edges, _external, _usage, _access = _build_tracker()
    context = _context(env={"source": source, "target": target})

    monkeypatch.setattr(
        effect_flow_module,
        "_var_ref_text",
        lambda raw: (
            None if isinstance(raw, dict) and raw.get(const.KEY_VAR_NAME) == "Missing" else str(raw[const.KEY_VAR_NAME])
        ),
    )

    tracker.record_function_call_effect_flow("CopyVariable", [_varref("Missing"), _varref("Target")], context)
    tracker.record_function_call_effect_flow("InitVariable", [_varref("Target"), _varref("Missing")], context)

    assert dict(edges) == {}
