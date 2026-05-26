"""Focused mapping propagation tests for effect-flow helpers."""

from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleCode,
    ModuleTypeDef,
    ParameterMapping,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const
from sattlint.resolution import AccessKind
from tests.test_variables_effect_flow import _build_tracker, _context, _hdr, _string_source, _varref


def test_effect_flow_tracker_collects_program_and_library_sink_keys() -> None:
    tracker, _edges, external_sinks, _usage, _access = _build_tracker()
    external_sinks.add(("external", "sink"))
    program_var = Variable(name="ProgramVar", datatype=Simple_DataType.INTEGER)
    included_param = Variable(name="IncludedParam", datatype=Simple_DataType.INTEGER)
    skipped_param = Variable(name="SkippedParam", datatype=Simple_DataType.INTEGER)
    included_typedef = ModuleTypeDef(
        name="Included",
        moduleparameters=[included_param],
        localvariables=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
    )
    included_typedef.origin_file = "root.s"
    skipped_typedef = ModuleTypeDef(
        name="Skipped",
        moduleparameters=[skipped_param],
        localvariables=[],
        moduledef=None,
        modulecode=ModuleCode(equations=[], sequences=[]),
    )
    skipped_typedef.origin_file = "dep.s"
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[included_typedef, skipped_typedef],
        localvariables=[program_var],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )

    program_sinks = tracker.collect_effect_sink_keys(
        bp, analyzed_target_is_library=False, is_from_root_origin_fn=lambda _origin: True
    )
    library_sinks = tracker.collect_effect_sink_keys(
        bp,
        analyzed_target_is_library=True,
        is_from_root_origin_fn=lambda origin: origin == "root.s",
    )

    assert tracker.compute_effective_output_keys(set()) == set()
    assert program_sinks == {("external", "sink"), ("root", "programvar")}
    assert library_sinks == {("external", "sink"), ("root", "typedef:included", "includedparam")}


def test_effect_flow_tracker_propagates_internal_mapping_reads_writes_and_edges() -> None:
    source = Variable(name="Source", datatype=Simple_DataType.INTEGER)
    input_var = Variable(name="Input", datatype=Simple_DataType.INTEGER)
    tracker, edges, _external, usage_by_name, _access = _build_tracker()
    child_context = _context(env={"input": input_var}, module_path=["Root", "Child"])
    mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("Source.Field"),
        source_literal=None,
    )

    tracker.propagate_mapping_to_parent(
        pm=mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={"source": source},
        parent_path=["Root", "Parent"],
        external_typename=None,
        child_context=child_context,
    )

    assert edges == {
        ("source", "source"): {("root", "child", "input")},
        ("root", "child", "input"): {("source", "source")},
    }
    usage = usage_by_name["Source"]
    assert usage.field_reads == [("Field", ("Root", "Parent"))]
    assert usage.field_writes == [("Field", ("Root", "Parent"))]


def test_effect_flow_tracker_propagates_global_internal_field_mapping_and_ignores_invalid_local_source() -> None:
    global_source = Variable(name="GlobalSource", datatype=Simple_DataType.INTEGER)
    invalid_local = Variable(name="InvalidLocal", datatype=Simple_DataType.INTEGER)
    tracker, _edges, _external, usage_by_name, access_calls = _build_tracker()
    parent_context = _context(env={"globalsource": global_source}, module_path=["Root", "Parent"])
    global_internal_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_varref("GlobalSource.Field"),
        source_literal=None,
    )
    invalid_local_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=invalid_local,
        source_literal=None,
    )

    tracker.propagate_mapping_to_parent(
        pm=global_internal_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename=None,
        parent_context=parent_context,
    )
    tracker.propagate_mapping_to_parent(
        pm=invalid_local_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename=None,
    )

    global_usage = usage_by_name["GlobalSource"]
    assert global_usage.field_reads == [("Field", ("Root", "Parent"))]
    assert global_usage.field_writes == [("Field", ("Root", "Parent"))]
    assert access_calls == []


def test_effect_flow_tracker_propagates_lookup_global_fallbacks_and_field_external_mappings() -> None:
    lookup_global = Variable(name="LookupGlobal", datatype=Simple_DataType.INTEGER)
    fallback_global = Variable(name="FallbackGlobal", datatype=Simple_DataType.INTEGER)
    tracker, _edges, _external, usage_by_name, access_calls = _build_tracker(
        lookup_global=lambda name: {
            "lookupglobal": lookup_global,
            "fallbackglobal": fallback_global,
        }.get(name.casefold())
    )

    local_field_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_string_source("LookupGlobal.Field"),
        source_literal=None,
    )
    global_field_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_string_source("FallbackGlobal.Field"),
        source_literal=None,
    )
    missing_local_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_string_source("Missing.Field"),
        source_literal=None,
    )

    tracker.propagate_mapping_to_parent(
        pm=local_field_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename="ExternalType",
    )
    tracker.propagate_mapping_to_parent(
        pm=global_field_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename="ExternalType",
    )
    tracker.propagate_mapping_to_parent(
        pm=missing_local_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename=None,
    )

    assert usage_by_name["LookupGlobal"].field_reads == [("Field", ("Root", "Parent"))]
    assert usage_by_name["LookupGlobal"].field_writes == [("Field", ("Root", "Parent"))]
    assert usage_by_name["FallbackGlobal"].field_reads == [("Field", ("Root", "Parent"))]
    assert usage_by_name["FallbackGlobal"].field_writes == [("Field", ("Root", "Parent"))]
    assert len(access_calls) == 4


def test_effect_flow_tracker_external_global_mapping_records_external_sink() -> None:
    global_source = Variable(name="GlobalSource", datatype=Simple_DataType.INTEGER)
    tracker, _edges, external_sinks, _usage, _access = _build_tracker()
    parent_context = _context(env={"globalsource": global_source}, module_path=["Root", "Parent"])

    external_global_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_varref("GlobalSource.Field"),
        source_literal=None,
    )

    tracker.propagate_mapping_to_parent(
        pm=external_global_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={"globalsource": global_source},
        parent_path=["Root", "Parent"],
        external_typename="ExternalType",
        parent_context=parent_context,
    )

    assert ("root", "parent", "globalsource") in external_sinks


def test_effect_flow_tracker_external_local_mapping_records_external_sink() -> None:
    local_source = Variable(name="LocalSource", datatype=Simple_DataType.INTEGER)
    tracker, _edges, external_sinks, _usage, _access = _build_tracker()
    parent_context = _context(env={"localsource": local_source}, module_path=["Root", "Parent"])

    external_local_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("LocalSource"),
        source_literal=None,
    )

    tracker.propagate_mapping_to_parent(
        pm=external_local_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={"localsource": local_source},
        parent_path=["Root", "Parent"],
        external_typename="ExternalType",
        parent_context=parent_context,
    )

    assert ("root", "parent", "localsource") in external_sinks


def test_effect_flow_tracker_propagates_global_and_external_mappings() -> None:
    global_source = Variable(name="GlobalSource", datatype=Simple_DataType.INTEGER)
    local_source = Variable(name="LocalSource", datatype=Simple_DataType.INTEGER)
    tracker, _edges, external_sinks, usage_by_name, access_calls = _build_tracker()
    parent_context = _context(env={"globalsource": global_source}, module_path=["Root", "Parent"])

    global_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_varref("GlobalSource.Member"),
        source_literal=None,
    )
    global_plain_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_varref("GlobalSource"),
        source_literal=None,
    )
    missing_external_global_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=_varref("MissingGlobal"),
        source_literal=None,
    )
    local_external_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=False,
        source=_varref("LocalSource"),
        source_literal=None,
    )
    missing_global_mapping = ParameterMapping(
        target=_varref("input"),
        source_type=const.TREE_TAG_VARIABLE_NAME,
        is_duration=False,
        is_source_global=True,
        source=None,
        source_literal=None,
    )

    tracker.propagate_mapping_to_parent(
        pm=global_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename="ExternalType",
        parent_context=parent_context,
    )
    tracker.propagate_mapping_to_parent(
        pm=global_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename=None,
        parent_context=parent_context,
    )
    tracker.propagate_mapping_to_parent(
        pm=global_plain_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename="ExternalType",
        parent_context=parent_context,
    )
    tracker.propagate_mapping_to_parent(
        pm=global_plain_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename=None,
        parent_context=parent_context,
    )
    tracker.propagate_mapping_to_parent(
        pm=missing_external_global_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename="ExternalType",
        parent_context=parent_context,
    )
    tracker.propagate_mapping_to_parent(
        pm=local_external_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={"localsource": local_source},
        parent_path=["Root", "Parent"],
        external_typename="ExternalType",
    )
    tracker.propagate_mapping_to_parent(
        pm=missing_global_mapping,
        child_used_reads={"input"},
        child_ui_reads=set(),
        child_non_ui_reads={"input"},
        child_used_writes={"input"},
        parent_env={},
        parent_path=["Root", "Parent"],
        external_typename=None,
        parent_context=parent_context,
    )

    global_usage = usage_by_name["GlobalSource"]
    local_usage = usage_by_name["LocalSource"]

    assert ("root", "parent", "globalsource") in external_sinks
    assert global_usage.field_reads == [
        ("Member", ("Root", "Parent")),
        ("Member", ("Root", "Parent")),
    ]
    assert global_usage.field_writes == [
        ("Member", ("Root", "Parent")),
        ("Member", ("Root", "Parent")),
    ]
    assert global_usage.read_paths == [("Root", "Parent"), ("Root", "Parent")]
    assert global_usage.write_paths == [("Root", "Parent"), ("Root", "Parent")]
    assert local_usage.read_paths == [("Root", "Parent")]
    assert local_usage.write_paths == [("Root", "Parent")]
    assert {call[0] for call in access_calls} == {AccessKind.READ, AccessKind.WRITE}
