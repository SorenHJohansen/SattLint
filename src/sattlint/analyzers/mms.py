from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)
from ..reporting.icf_report import ICFEntry
from ..reporting.mms_report import (
    MMSInterfaceHit,
    MMSInterfaceReport,
    WriteFields,
)
from ..resolution.common import (
    find_all_aliases,
    find_all_aliases_upstream,
    find_var_in_scope,
    resolve_moduletype_def_strict,
    varname_base,
    varname_full,
)
from ..resolution.type_graph import TypeGraph
from .framework import Issue
from .icf import parse_icf_file, validate_icf_entries_against_program
from .variables import VariablesAnalyzer

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
_TAG_PARAMETER_NAMES: tuple[str, ...] = (
    "remotevarname",
    "tag",
    "name",
)
_NUMERIC_TAG_RE = re.compile(r"^\d+$")
_TAG_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")


@dataclass(frozen=True)
class _InterfaceInventoryEntry:
    source_kind: str
    module_path: list[str]
    moduletype_name: str | None
    parameter_name: str | None
    source_variable: str
    source_datatype: str | None
    source_leaf_name: str | None
    external_tag: str | None
    external_tag_key: str | None
    tag_family_key: str | None
    direction: str | None = None
    write_fields: WriteFields = ()
    write_note: str | None = None


def _datatype_label(datatype: Simple_DataType | str | None) -> str | None:
    if datatype is None:
        return None
    if isinstance(datatype, Simple_DataType):
        return datatype.value
    return str(datatype)


def _normalize_external_tag(tag: str | None) -> str | None:
    if not isinstance(tag, str):
        return None
    cleaned = tag.strip()
    if not cleaned or _NUMERIC_TAG_RE.fullmatch(cleaned):
        return None
    return cleaned.casefold()


def _tag_family_key(tag: str | None) -> str | None:
    if not isinstance(tag, str):
        return None
    cleaned = tag.strip()
    if not cleaned or _NUMERIC_TAG_RE.fullmatch(cleaned):
        return None

    normalized = cleaned.replace(".", "_").replace("-", "_").replace(" ", "_")
    tokens: list[str] = []
    for chunk in normalized.split("_"):
        chunk = chunk.strip()
        if not chunk:
            continue
        matches = _TAG_TOKEN_RE.findall(chunk)
        if matches:
            tokens.extend(match.casefold() for match in matches)
            continue
        tokens.append(chunk.casefold())

    if not tokens:
        return None
    return "|".join(tokens)


def _source_label(source_kind: str) -> str:
    return "ICF" if source_kind == "icf" else "MMS"


def _build_moduletype_index(
    base_picture: BasePicture,
) -> dict[str, list[ModuleTypeDef]]:
    index: dict[str, list[ModuleTypeDef]] = {}
    for moduletype in base_picture.moduletype_defs or []:
        index.setdefault(moduletype.name.casefold(), []).append(moduletype)
    return index


def _program_name_candidates(base_picture: BasePicture) -> list[str]:
    candidates: list[str] = []
    origin_file = getattr(base_picture, "origin_file", None)
    if isinstance(origin_file, str) and origin_file.strip():
        stem = Path(origin_file).stem.strip()
        if stem:
            candidates.append(stem)

    header_name = base_picture.header.name.strip()
    if header_name and header_name.casefold() not in {name.casefold() for name in candidates}:
        candidates.append(header_name)

    return candidates or [base_picture.header.name]


def _load_icf_entries_from_config(
    base_picture: BasePicture,
    config: dict[str, Any] | None,
) -> list[ICFEntry]:
    if not isinstance(config, dict):
        return []

    icf_dir_raw = str(config.get("icf_dir", "") or "").strip()
    if not icf_dir_raw:
        return []

    icf_dir = Path(icf_dir_raw)
    if not icf_dir.exists() or not icf_dir.is_dir():
        return []

    for name in _program_name_candidates(base_picture):
        candidate = icf_dir / f"{name}.icf"
        if candidate.exists() and candidate.is_file():
            return parse_icf_file(candidate)

    return []


def _find_parameter_mapping(
    mappings: list[ParameterMapping] | None,
    parameter_name: str,
) -> ParameterMapping | None:
    wanted = parameter_name.casefold()
    for mapping in mappings or []:
        target_name = varname_base(mapping.target)
        if target_name == wanted:
            return mapping
    return None


def _find_variable(
    variables: list[Variable] | None,
    wanted_name: str,
) -> Variable | None:
    wanted = wanted_name.casefold()
    for variable in variables or []:
        if variable.name.casefold() == wanted:
            return variable
    return None


def _resolve_string_parameter(
    base_picture: BasePicture,
    module_path: list[str],
    inst: ModuleTypeInstance,
    mt_def: ModuleTypeDef | None,
    parameter_name: str,
) -> str | None:
    mapping = _find_parameter_mapping(inst.parametermappings, parameter_name)
    if mapping is not None:
        if mapping.source_type == const.KEY_VALUE and isinstance(mapping.source_literal, str):
            value = mapping.source_literal.strip()
            return value or None

        full_ref = varname_full(mapping.source)
        if full_ref and ":" not in full_ref:
            base_name = full_ref.split(".", 1)[0]
            variable = find_var_in_scope(base_picture, module_path, base_name)
            if variable is not None and isinstance(variable.init_value, str):
                value = variable.init_value.strip()
                return value or None
        return None

    if mt_def is None:
        return None

    parameter = _find_variable(mt_def.moduleparameters, parameter_name)
    if parameter is None or not isinstance(parameter.init_value, str):
        return None

    value = parameter.init_value.strip()
    return value or None


def _extract_external_tag(
    base_picture: BasePicture,
    module_path: list[str],
    inst: ModuleTypeInstance,
    mt_def: ModuleTypeDef | None,
) -> str | None:
    available_names = {
        variable.name.casefold()
        for variable in (mt_def.moduleparameters or [])
    } if mt_def is not None else set()
    for mapping in inst.parametermappings or []:
        target_name = varname_base(mapping.target)
        if target_name:
            available_names.add(target_name)

    for parameter_name in _TAG_PARAMETER_NAMES:
        if parameter_name not in available_names:
            continue
        value = _resolve_string_parameter(
            base_picture,
            module_path,
            inst,
            mt_def,
            parameter_name,
        )
        if value:
            return value

    return None


def _resolve_source_details(
    base_picture: BasePicture,
    type_graph: TypeGraph,
    module_path: list[str],
    source_variable: str,
) -> tuple[str | None, str | None]:
    if not source_variable:
        return None, None

    base_name = source_variable.split(".", 1)[0]
    field_segments = source_variable.split(".")[1:]
    variable = find_var_in_scope(base_picture, module_path, base_name)
    if variable is None:
        return None, field_segments[-1] if field_segments else None

    current_type: Simple_DataType | str | None = variable.datatype
    leaf_name = variable.name
    for field in field_segments:
        leaf_name = field
        if isinstance(current_type, Simple_DataType) or current_type is None:
            return _datatype_label(current_type), leaf_name

        field_def = type_graph.field(str(current_type), field)
        if field_def is None:
            return None, leaf_name
        current_type = field_def.datatype

    return _datatype_label(current_type), leaf_name


def _best_icf_validation_report(
    base_picture: BasePicture,
    entries: list[ICFEntry],
    moduletype_index: dict[str, list[ModuleTypeDef]],
) -> Any | None:
    best_report = None
    for program_name in _program_name_candidates(base_picture):
        candidate = validate_icf_entries_against_program(
            base_picture,
            entries,
            expected_program=program_name,
            moduletype_index=moduletype_index,
        )
        if best_report is None:
            best_report = candidate
            continue
        if candidate.valid_entries > best_report.valid_entries:
            best_report = candidate
            continue
        if (
            candidate.valid_entries == best_report.valid_entries
            and len(candidate.issues) < len(best_report.issues)
        ):
            best_report = candidate
    return best_report


def _emit_duplicate_tag_issues(
    entries: list[_InterfaceInventoryEntry],
) -> list[Issue]:
    grouped: dict[tuple[str, str], list[_InterfaceInventoryEntry]] = defaultdict(list)
    for entry in entries:
        if entry.external_tag_key is None:
            continue
        grouped[(entry.source_kind, entry.external_tag_key)].append(entry)

    issues: list[Issue] = []
    for (source_kind, _tag_key), group in grouped.items():
        if len(group) < 2:
            continue
        display_tag = group[0].external_tag or "<unknown tag>"
        locations = [".".join(entry.module_path) for entry in group if entry.module_path]
        issues.append(
            Issue(
                kind="mms.duplicate_tag",
                message=(
                    f"{_source_label(source_kind)} tag {display_tag!r} is configured "
                    f"{len(group)} times across the analyzed target."
                ),
                module_path=group[0].module_path,
                data={
                    "source_kind": source_kind,
                    "tag": display_tag,
                    "count": len(group),
                    "locations": locations,
                },
            )
        )

    return issues


def _emit_datatype_mismatch_issues(
    entries: list[_InterfaceInventoryEntry],
) -> list[Issue]:
    grouped: dict[tuple[str, str], list[_InterfaceInventoryEntry]] = defaultdict(list)
    for entry in entries:
        if entry.external_tag_key is None:
            continue
        grouped[(entry.source_kind, entry.external_tag_key)].append(entry)

    issues: list[Issue] = []
    for (source_kind, _tag_key), group in grouped.items():
        datatypes = sorted(
            {
                datatype
                for datatype in (entry.source_datatype for entry in group)
                if datatype is not None
            }
        )
        if len(datatypes) < 2:
            continue

        display_tag = group[0].external_tag or "<unknown tag>"
        issues.append(
            Issue(
                kind="mms.datatype_mismatch",
                message=(
                    f"{_source_label(source_kind)} tag {display_tag!r} resolves to conflicting "
                    f"datatypes: {', '.join(datatypes)}."
                ),
                module_path=group[0].module_path,
                data={
                    "source_kind": source_kind,
                    "tag": display_tag,
                    "datatypes": datatypes,
                },
            )
        )

    return issues


def _emit_naming_drift_issues(
    entries: list[_InterfaceInventoryEntry],
) -> list[Issue]:
    grouped: dict[tuple[str, str], list[_InterfaceInventoryEntry]] = defaultdict(list)
    for entry in entries:
        if entry.tag_family_key is None or entry.external_tag is None:
            continue
        grouped[(entry.source_kind, entry.tag_family_key)].append(entry)

    issues: list[Issue] = []
    for (source_kind, family_key), group in grouped.items():
        spellings = sorted({entry.external_tag for entry in group if entry.external_tag})
        if len(spellings) < 2:
            continue

        issues.append(
            Issue(
                kind="mms.naming_drift",
                message=(
                    f"{_source_label(source_kind)} tag family {family_key!r} appears with "
                    f"multiple spellings: {', '.join(spellings)}."
                ),
                module_path=group[0].module_path,
                data={
                    "source_kind": source_kind,
                    "family": family_key,
                    "spellings": spellings,
                },
            )
        )

    return issues


def _emit_dead_tag_issues(
    entries: list[_InterfaceInventoryEntry],
) -> list[Issue]:
    issues: list[Issue] = []
    for entry in entries:
        if entry.source_kind != "mms" or entry.direction != "outgoing":
            continue
        if entry.external_tag is None:
            continue
        if entry.write_note is not None:
            continue
        if entry.write_fields:
            continue
        issues.append(
            Issue(
                kind="mms.dead_tag",
                message=(
                    f"Outgoing MMS tag {entry.external_tag!r} maps to {entry.source_variable!r}, "
                    "but the source is never written inside the analyzed target."
                ),
                module_path=entry.module_path,
                data={
                    "source_kind": entry.source_kind,
                    "tag": entry.external_tag,
                    "source_variable": entry.source_variable,
                    "datatype": entry.source_datatype,
                },
            )
        )
    return issues


def analyze_mms_interface_variables(
    base_picture: BasePicture,
    debug: bool = False,
    config: dict[str, Any] | None = None,
    icf_entries: list[ICFEntry] | None = None,
) -> MMSInterfaceReport:
    """
    Find variables mapped into MMSWriteVar.WriteData or MMSReadVar.Outputvariable.

    This scans module instances and collects the source variables used in the
    parameter mapping for those module types.
    """
    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
    )
    analyzer.run()
    type_graph = TypeGraph.from_basepicture(base_picture)

    def _is_from_root_origin(origin_file: str | None) -> bool:
        if not origin_file:
            return True
        root_origin = getattr(base_picture, "origin_file", None)
        if not root_origin:
            return False
        return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()

    hits: list[MMSInterfaceHit] = []
    inventory_entries: list[_InterfaceInventoryEntry] = []

    def _collect_write_locations(
        module_path: list[str],
        source_variable: str,
    ) -> WriteFields | None:
        if not source_variable:
            return None

        base = source_variable.split(".", 1)[0]
        field_path = source_variable.split(".", 1)[1] if "." in source_variable else None

        # Use imported find_var_in_scope
        var = find_var_in_scope(base_picture, module_path, base)
        if var is None:
            return None

        # Access private _alias_links from analyzer
        aliases = find_all_aliases(var, analyzer._alias_links, debug=debug)
        aliases.insert(0, (var, ""))
        upstream_aliases = find_all_aliases_upstream(var, analyzer._alias_links)

        field_writes: dict[str, list[list[str]]] = {}
        whole_var_writes: list[list[str]] = []

        for alias_var, prefix in aliases:
            usage = analyzer.usage_tracker.get_usage(alias_var)
            for field, locs in (usage.field_writes or {}).items():
                if prefix and field:
                    full_field = f"{prefix}.{field}"
                elif prefix:
                    full_field = prefix
                else:
                    full_field = field

                field_writes.setdefault(full_field.casefold(), []).extend(locs)

            for loc, kind in (usage.usage_locations or []):
                if kind == "write":
                    whole_var_writes.append(loc)

        # Include upstream mappings (parent variables) by stripping the mapping prefix.
        for alias_var, strip_prefix in upstream_aliases:
            usage = analyzer.usage_tracker.get_usage(alias_var)
            for field, locs in (usage.field_writes or {}).items():
                if strip_prefix:
                    if field == strip_prefix:
                        full_field = ""
                    elif field.startswith(strip_prefix + "."):
                        full_field = field[len(strip_prefix) + 1 :]
                    else:
                        continue
                else:
                    full_field = field

                field_writes.setdefault(full_field.casefold(), []).extend(locs)

            if not strip_prefix:
                for loc, kind in (usage.usage_locations or []):
                    if kind == "write":
                        whole_var_writes.append(loc)

        if field_path:
            prefix = field_path.casefold()
            matched_fields = {
                field: locs
                for field, locs in field_writes.items()
                if field == prefix or field.startswith(prefix + ".")
            }
            if not matched_fields:
                return ()

            results = []
            for field, locs in sorted(matched_fields.items()):
                matched_counts: dict[tuple[str, ...], int] = {}
                for loc in locs:
                    key = tuple(loc)
                    matched_counts[key] = matched_counts.get(key, 0) + 1
                results.append(
                    (field, tuple(sorted(matched_counts.items(), key=lambda item: ".".join(item[0]))))
                )
            return tuple(results)

        if not field_writes and not whole_var_writes:
            return ()

        results = []
        for field, locs in sorted(field_writes.items()):
            counts: dict[tuple[str, ...], int] = {}
            for loc in locs:
                key = tuple(loc)
                counts[key] = counts.get(key, 0) + 1
            results.append(
                (field, tuple(sorted(counts.items(), key=lambda item: ".".join(item[0]))))
            )

        if whole_var_writes:
            whole_counts: dict[tuple[str, ...], int] = {}
            for loc in whole_var_writes:
                key = tuple(loc)
                whole_counts[key] = whole_counts.get(key, 0) + 1
            results.append(
                ("", tuple(sorted(whole_counts.items(), key=lambda item: ".".join(item[0]))))
            )

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
        for pm in param_mappings or []:
            target_name = varname_base(pm.target)
            if not target_name or pm.is_source_global:
                continue

            resolved_source = _resolve_param_source(
                param_map,
                pm.source,
                allow_passthrough,
            )
            if not resolved_source:
                continue

            resolved[target_name] = resolved_source
        return resolved

    def _walk_typedef(
        modules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
        path: list[str],
        param_map: dict[str, str],
        visited_types: set[str],
    ) -> None:
        for mod in modules or []:
            if isinstance(mod, ModuleTypeInstance):
                mt_name = mod.moduletype_name or ""
                mt_key = mt_name.casefold()
                next_path = [*path, mod.header.name]
                current_map = _build_param_map(
                    mod.parametermappings,
                    param_map,
                    allow_passthrough=False,
                )

                if mt_key in _INTERFACE_TARGETS:
                    param_targets = _INTERFACE_TARGETS[mt_key]
                    for target_name, direction in sorted(param_targets.items()):
                        resolved = current_map.get(target_name)
                        if not resolved:
                            continue

                        writes = _collect_write_locations(next_path, resolved)
                        source_datatype, source_leaf_name = _resolve_source_details(
                            base_picture,
                            type_graph,
                            next_path,
                            resolved,
                        )
                        external_tag = _extract_external_tag(base_picture, next_path, mod, None)
                        hits.append(
                            MMSInterfaceHit(
                                module_path=next_path,
                                moduletype_name=mt_name,
                                parameter_name=target_name,
                                source_variable=resolved,
                                write_fields=writes or (),
                                write_note=None if writes is not None else "unknown (variable not found)",
                            )
                        )
                        inventory_entries.append(
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
                                write_fields=writes or (),
                                write_note=None if writes is not None else "unknown (variable not found)",
                            )
                        )

                if mt_key in visited_types:
                    continue

                try:
                    inner_def = resolve_moduletype_def_strict(base_picture, mt_name)
                except ValueError:
                    continue

                visited_types.add(mt_key)
                _walk_typedef(
                    inner_def.submodules,
                    next_path,
                    current_map,
                    visited_types,
                )
                visited_types.remove(mt_key)
            elif isinstance(mod, (SingleModule, FrameModule)):
                _walk_typedef(
                    mod.submodules,
                    [*path, mod.header.name],
                    param_map,
                    visited_types,
                )

    def _walk_modules(
        modules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
        path: list[str],
        param_map: dict[str, str],
    ) -> None:
        for mod in modules or []:
            if isinstance(mod, (SingleModule, FrameModule)):
                next_path = [*path, mod.header.name]
                _walk_modules(mod.submodules, next_path, param_map)
            elif isinstance(mod, ModuleTypeInstance):
                next_path = [*path, mod.header.name]
                mt_name = mod.moduletype_name or ""
                mt_key = mt_name.casefold()
                mt_def: ModuleTypeDef | None = None
                current_map = _build_param_map(
                    mod.parametermappings,
                    param_map,
                    allow_passthrough=True,
                )

                try:
                    mt_def = resolve_moduletype_def_strict(base_picture, mt_name)
                except ValueError:
                    mt_def = None

                if mt_key in _INTERFACE_TARGETS:
                    param_targets = _INTERFACE_TARGETS[mt_key]
                    for target_name, direction in sorted(param_targets.items()):
                        resolved = current_map.get(target_name)
                        if not resolved:
                            continue

                        writes = _collect_write_locations(next_path, resolved)
                        source_datatype, source_leaf_name = _resolve_source_details(
                            base_picture,
                            type_graph,
                            next_path,
                            resolved,
                        )
                        external_tag = _extract_external_tag(base_picture, next_path, mod, mt_def)
                        hits.append(
                            MMSInterfaceHit(
                                module_path=next_path,
                                moduletype_name=mt_name,
                                parameter_name=target_name,
                                source_variable=resolved,
                                write_fields=writes or (),
                                write_note=None if writes is not None else "unknown (variable not found)",
                            )
                        )
                        inventory_entries.append(
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
                                write_fields=writes or (),
                                write_note=None if writes is not None else "unknown (variable not found)",
                            )
                        )

                if mt_def is None:
                    continue

                if not _is_from_root_origin(getattr(mt_def, "origin_file", None)):
                    continue

                if current_map:
                    _walk_typedef(
                        mt_def.submodules,
                        next_path,
                        current_map,
                        {mt_key},
                    )

    _walk_modules(base_picture.submodules, [base_picture.header.name], {})

    active_icf_entries = icf_entries if icf_entries is not None else _load_icf_entries_from_config(
        base_picture,
        config,
    )
    if active_icf_entries:
        icf_report = _best_icf_validation_report(
            base_picture,
            active_icf_entries,
            _build_moduletype_index(base_picture),
        )
        if icf_report is not None:
            for resolved in icf_report.resolved_entries:
                source_variable = resolved.variable_name
                if resolved.field_path:
                    source_variable = f"{source_variable}.{resolved.field_path}"
                tag_name = resolved.entry.key.strip() or None
                inventory_entries.append(
                    _InterfaceInventoryEntry(
                        source_kind="icf",
                        module_path=list(resolved.module_path),
                        moduletype_name=None,
                        parameter_name=resolved.entry.section,
                        source_variable=source_variable,
                        source_datatype=_datatype_label(resolved.datatype),
                        source_leaf_name=resolved.leaf_name,
                        external_tag=tag_name,
                        external_tag_key=_normalize_external_tag(tag_name),
                        tag_family_key=_tag_family_key(tag_name),
                    )
                )

    issues: list[Issue] = []
    issues.extend(_emit_duplicate_tag_issues(inventory_entries))
    issues.extend(_emit_dead_tag_issues(inventory_entries))
    issues.extend(_emit_datatype_mismatch_issues(inventory_entries))
    issues.extend(_emit_naming_drift_issues(inventory_entries))

    return MMSInterfaceReport(
        basepicture_name=base_picture.header.name,
        hits=hits,
        issues=issues,
    )
