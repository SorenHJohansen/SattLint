from __future__ import annotations

# pyright: reportUnusedFunction=false
from collections import defaultdict
from typing import Any

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef, ModuleTypeInstance, ParameterMapping, Variable

from ...reporting.icf_report import ICFEntry
from ...reporting.mms_report import MMSInterfaceReport
from ...resolution.type_graph import TypeGraph
from ..framework import Issue
from ..variables import VariablesAnalyzer
from ._mms_interface_analysis import (
    _InterfaceInventoryEntry,
    collect_icf_inventory_entries,
    collect_mms_inventory_entries,
    load_icf_entries_from_config,
)
from ._mms_interface_analysis import (
    extract_external_tag as extract_external_tag_impl,
)
from ._mms_interface_analysis import (
    normalize_external_tag as normalize_external_tag_impl,
)
from ._mms_interface_analysis import (
    tag_family_key as tag_family_key_impl,
)
from ._mms_interface_helpers import (
    find_parameter_mapping as find_parameter_mapping_impl,
)
from ._mms_interface_helpers import (
    find_variable as find_variable_impl,
)


def _extract_external_tag(
    base_picture: BasePicture,
    module_path: list[str],
    inst: ModuleTypeInstance,
    mt_def: ModuleTypeDef | None,
) -> str | None:
    return extract_external_tag_impl(base_picture, module_path, inst, mt_def)


def _normalize_external_tag(tag: str | None) -> str | None:
    return normalize_external_tag_impl(tag)


def _tag_family_key(tag: str | None) -> str | None:
    return tag_family_key_impl(tag)


def _find_parameter_mapping(
    mappings: list[ParameterMapping] | None,
    parameter_name: str,
) -> ParameterMapping | None:
    return find_parameter_mapping_impl(mappings, parameter_name)


def _find_variable(
    variables: list[Variable] | None,
    wanted_name: str,
) -> Variable | None:
    return find_variable_impl(variables, wanted_name)


def _source_label(source_kind: str) -> str:
    return "ICF" if source_kind == "icf" else "MMS"


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
            {datatype for datatype in (entry.source_datatype for entry in group) if datatype is not None}
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
    hits, inventory_entries = collect_mms_inventory_entries(
        base_picture,
        analyzer,
        type_graph,
        debug=debug,
    )

    active_icf_entries = (
        icf_entries
        if icf_entries is not None
        else load_icf_entries_from_config(
            base_picture,
            config,
        )
    )
    if active_icf_entries:
        inventory_entries.extend(collect_icf_inventory_entries(base_picture, active_icf_entries))

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
