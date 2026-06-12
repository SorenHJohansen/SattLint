"""Helpers for MMS interface inventory analysis."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SingleModule,
)

from ...reporting.mms_report import MMSInterfaceHit, WriteFields
from ...resolution.common import (
    find_all_aliases,
    find_all_aliases_upstream,
    resolve_moduletype_def_strict,
    varname_base,
    varname_full,
)
from ...resolution.context_builder import ContextBuilder
from ...resolution.type_graph import TypeGraph
from ..shared.variable_utils import same_origin_file_stem
from ..variables import VariablesAnalyzer
from . import _mms_icf_inventory as _mms_icf_inventory_module
from ._mms_interface_helpers import (
    _extract_external_tag,
    _normalize_external_tag,
    _resolve_source_details,
    _tag_family_key,
)

_INTERFACE_TARGETS: dict[str, dict[str, str]] = {
    "mmswritevar": {
        "localvariable": "outgoing",
        "writedata": "outgoing",
    },
    "mmsreadvar": {
        "localvariable": "incoming",
        "outputvariable": "incoming",
    },
    "mmsreadvarcyc": {
        "outputvariable": "incoming",
    },
    "mmsreadwrite": {
        "inputvariable": "outgoing",
        "outputvariable": "incoming",
    },
}


_InterfaceInventoryEntry = _mms_icf_inventory_module.InterfaceInventoryEntry
collect_icf_inventory_entries = _mms_icf_inventory_module.collect_icf_inventory_entries
load_icf_entries_from_config = _mms_icf_inventory_module.load_icf_entries_from_config
extract_external_tag = _extract_external_tag
normalize_external_tag = _normalize_external_tag
tag_family_key = _tag_family_key


def _empty_mms_hits() -> list[MMSInterfaceHit]:
    return []


def _empty_inventory_entries() -> list[_InterfaceInventoryEntry]:
    return []


@dataclass(slots=True)
class _MMSInterfaceAnalysisState:
    base_picture: BasePicture
    analyzer: VariablesAnalyzer
    type_graph: TypeGraph
    debug: bool
    hits: list[MMSInterfaceHit] = dataclass_field(default_factory=_empty_mms_hits)
    inventory_entries: list[_InterfaceInventoryEntry] = dataclass_field(default_factory=_empty_inventory_entries)


def _collect_write_locations(  # noqa: PLR0915
    state: _MMSInterfaceAnalysisState,
    module_path: list[str],
    source_variable: str,
) -> WriteFields | None:
    if not source_variable:
        return None

    base = source_variable.split(".", 1)[0]
    field_path = source_variable.split(".", 1)[1] if "." in source_variable else None

    variable = ContextBuilder.resolve_variable_in_scope(state.base_picture, module_path, base)
    if variable is None:
        return None

    aliases = find_all_aliases(variable, state.analyzer._alias_links, debug=state.debug)
    aliases.insert(0, (variable, ""))
    upstream_aliases = find_all_aliases_upstream(variable, state.analyzer._alias_links)

    field_writes: dict[str, list[list[str]]] = {}
    whole_var_writes: list[list[str]] = []

    for alias_var, prefix in aliases:
        usage = state.analyzer.usage_tracker.get_usage(alias_var)
        for field, locations in (usage.field_writes or {}).items():
            if prefix and field:
                full_field = f"{prefix}.{field}"
            elif prefix:
                full_field = prefix
            else:
                full_field = field

            field_writes.setdefault(full_field.casefold(), []).extend(locations)

        for location, kind in usage.usage_locations or []:
            if kind == "write":
                whole_var_writes.append(location)

    for alias_var, strip_prefix in upstream_aliases:
        usage = state.analyzer.usage_tracker.get_usage(alias_var)
        for field, locations in (usage.field_writes or {}).items():
            if strip_prefix:
                if field == strip_prefix:
                    full_field = ""
                elif field.startswith(strip_prefix + "."):
                    full_field = field[len(strip_prefix) + 1 :]
                else:
                    continue
            else:
                full_field = field

            field_writes.setdefault(full_field.casefold(), []).extend(locations)

        if not strip_prefix:
            for location, kind in usage.usage_locations or []:
                if kind == "write":
                    whole_var_writes.append(location)

    if field_path:
        prefix = field_path.casefold()
        matched_fields = {
            field: locations
            for field, locations in field_writes.items()
            if field == prefix or field.startswith(prefix + ".")
        }
        if not matched_fields:
            return ()

        results: list[tuple[str, tuple[tuple[tuple[str, ...], int], ...]]] = []
        for field, locations in sorted(matched_fields.items()):
            matched_counts: dict[tuple[str, ...], int] = {}
            for location in locations:
                key = tuple(location)
                matched_counts[key] = matched_counts.get(key, 0) + 1
            results.append((field, tuple(sorted(matched_counts.items(), key=lambda item: ".".join(item[0])))))
        return tuple(results)

    if not field_writes and not whole_var_writes:
        return ()

    results: list[tuple[str, tuple[tuple[tuple[str, ...], int], ...]]] = []
    for field, locations in sorted(field_writes.items()):
        counts: dict[tuple[str, ...], int] = {}
        for location in locations:
            key = tuple(location)
            counts[key] = counts.get(key, 0) + 1
        results.append((field, tuple(sorted(counts.items(), key=lambda item: ".".join(item[0])))))

    if whole_var_writes:
        whole_counts: dict[tuple[str, ...], int] = {}
        for location in whole_var_writes:
            key = tuple(location)
            whole_counts[key] = whole_counts.get(key, 0) + 1
        results.append(("", tuple(sorted(whole_counts.items(), key=lambda item: ".".join(item[0])))))

    return tuple(results)


def _resolve_param_source(
    param_map: dict[str, str],
    source: Any,
    allow_passthrough: bool,
) -> str | None:
    full = varname_full(source)
    if not full:
        return None

    base = full.split(".", 1)[0] if full else ""
    suffix = full[len(base) :] if len(full) > len(base) else ""

    if base:
        mapped = param_map.get(base.casefold())
        if mapped:
            return f"{mapped}{suffix}"

    return full if allow_passthrough else None


def _build_param_map(
    param_mappings: list[ParameterMapping] | None,
    param_map: dict[str, str],
    allow_passthrough: bool,
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for parameter_mapping in param_mappings or []:
        target_name = varname_base(parameter_mapping.target)
        if not target_name or parameter_mapping.is_source_global:
            continue

        resolved_source = _resolve_param_source(
            param_map,
            parameter_mapping.source,
            allow_passthrough,
        )
        if not resolved_source:
            continue

        resolved[target_name.casefold()] = resolved_source
    return resolved


def _record_interface_hit(
    state: _MMSInterfaceAnalysisState,
    next_path: list[str],
    mt_name: str,
    target_name: str,
    resolved: str,
    direction: str,
    mt_def: ModuleTypeDef | None,
    inst: ModuleTypeInstance,
) -> None:
    writes = _collect_write_locations(state, next_path, resolved)
    source_datatype, source_leaf_name = _resolve_source_details(
        state.base_picture,
        state.type_graph,
        next_path,
        resolved,
    )
    external_tag = _extract_external_tag(state.base_picture, next_path, inst, mt_def)
    write_fields = writes or ()
    write_note = None if writes is not None else "unknown (variable not found)"
    state.hits.append(
        MMSInterfaceHit(
            module_path=next_path,
            moduletype_name=mt_name,
            parameter_name=target_name,
            source_variable=resolved,
            write_fields=write_fields,
            write_note=write_note,
        )
    )
    state.inventory_entries.append(
        _InterfaceInventoryEntry(
            source_kind="mms",
            module_path=next_path,
            moduletype_name=mt_name,
            parameter_name=target_name,
            source_variable=resolved,
            source_datatype=source_datatype,
            source_leaf_name=source_leaf_name,
            external_tag=external_tag,
            external_tag_key=_normalize_external_tag(external_tag),
            tag_family_key=_tag_family_key(external_tag),
            direction=direction,
            write_fields=write_fields,
            write_note=write_note,
        )
    )


def _walk_typedef(
    state: _MMSInterfaceAnalysisState,
    modules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
    path: list[str],
    param_map: dict[str, str],
    visited_types: set[str],
) -> None:
    for module in modules or []:
        if isinstance(module, ModuleTypeInstance):
            mt_name = module.moduletype_name or ""
            mt_key = mt_name.casefold()
            next_path = [*path, module.header.name]
            current_map = _build_param_map(
                module.parametermappings,
                param_map,
                allow_passthrough=False,
            )

            if mt_key in _INTERFACE_TARGETS:
                for target_name, direction in sorted(_INTERFACE_TARGETS[mt_key].items()):
                    resolved = current_map.get(target_name.casefold())
                    if resolved:
                        _record_interface_hit(
                            state,
                            next_path,
                            mt_name,
                            target_name,
                            resolved,
                            direction,
                            None,
                            module,
                        )

            if mt_key in visited_types:
                continue

            try:
                inner_def = resolve_moduletype_def_strict(state.base_picture, mt_name)
            except ValueError:
                continue

            visited_types.add(mt_key)
            _walk_typedef(
                state,
                inner_def.submodules,
                next_path,
                current_map,
                visited_types,
            )
            visited_types.remove(mt_key)
        else:
            _walk_typedef(
                state,
                module.submodules,
                [*path, module.header.name],
                param_map,
                visited_types,
            )


def _walk_modules(
    state: _MMSInterfaceAnalysisState,
    modules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
    path: list[str],
    param_map: dict[str, str],
) -> None:
    for module in modules or []:
        if isinstance(module, (SingleModule, FrameModule)):
            next_path = [*path, module.header.name]
            _walk_modules(state, module.submodules, next_path, param_map)
            continue

        next_path = [*path, module.header.name]
        mt_name = module.moduletype_name or ""
        mt_key = mt_name.casefold()
        current_map = _build_param_map(
            module.parametermappings,
            param_map,
            allow_passthrough=True,
        )

        try:
            mt_def = resolve_moduletype_def_strict(state.base_picture, mt_name)
        except ValueError:
            mt_def = None

        if mt_key in _INTERFACE_TARGETS:
            for target_name, direction in sorted(_INTERFACE_TARGETS[mt_key].items()):
                resolved = current_map.get(target_name.casefold())
                if resolved:
                    _record_interface_hit(
                        state,
                        next_path,
                        mt_name,
                        target_name,
                        resolved,
                        direction,
                        mt_def,
                        module,
                    )

        if mt_def is None:
            continue

        if not same_origin_file_stem(
            getattr(mt_def, "origin_file", None), getattr(state.base_picture, "origin_file", None)
        ):
            continue

        if current_map:
            _walk_typedef(
                state,
                mt_def.submodules,
                next_path,
                current_map,
                {mt_key},
            )


def collect_mms_inventory_entries(
    base_picture: BasePicture,
    analyzer: VariablesAnalyzer,
    type_graph: TypeGraph,
    *,
    debug: bool = False,
) -> tuple[list[MMSInterfaceHit], list[_InterfaceInventoryEntry]]:
    state = _MMSInterfaceAnalysisState(
        base_picture=base_picture,
        analyzer=analyzer,
        type_graph=type_graph,
        debug=debug,
    )
    _walk_modules(state, base_picture.submodules, [base_picture.header.name], {})
    return state.hits, state.inventory_entries


__all__ = [
    "_InterfaceInventoryEntry",
    "_extract_external_tag",
    "_normalize_external_tag",
    "_tag_family_key",
    "collect_icf_inventory_entries",
    "collect_mms_inventory_entries",
    "extract_external_tag",
    "load_icf_entries_from_config",
    "normalize_external_tag",
    "tag_family_key",
]
