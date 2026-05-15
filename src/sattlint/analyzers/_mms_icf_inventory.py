"""ICF inventory loading and translation helpers for MMS analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sattline_parser.models.ast_model import BasePicture

from ..reporting.icf_report import ICFEntry
from ..reporting.mms_report import WriteFields
from ._mms_interface_helpers import (
    _best_icf_validation_report,
    _build_moduletype_index,
    _datatype_label,
    _load_icf_entries_from_config,
    _normalize_external_tag,
    _tag_family_key,
)


@dataclass(frozen=True)
class InterfaceInventoryEntry:
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


def load_icf_entries_from_config(
    base_picture: BasePicture,
    config: dict[str, Any] | None,
) -> list[ICFEntry]:
    return _load_icf_entries_from_config(base_picture, config)


def collect_icf_inventory_entries(
    base_picture: BasePicture,
    active_icf_entries: list[ICFEntry],
) -> list[InterfaceInventoryEntry]:
    icf_report = _best_icf_validation_report(
        base_picture,
        active_icf_entries,
        _build_moduletype_index(base_picture),
    )
    if icf_report is None:
        return []

    inventory_entries: list[InterfaceInventoryEntry] = []
    for resolved in icf_report.resolved_entries:
        source_variable = resolved.variable_name
        if resolved.field_path:
            source_variable = f"{source_variable}.{resolved.field_path}"
        tag_name = resolved.entry.key.strip() or None
        inventory_entries.append(
            InterfaceInventoryEntry(
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
    return inventory_entries


__all__ = [
    "InterfaceInventoryEntry",
    "collect_icf_inventory_entries",
    "load_icf_entries_from_config",
]
