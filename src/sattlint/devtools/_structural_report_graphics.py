"""Graphics layout report helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)


def _serialize_invoke_coord(header: ModuleHeader) -> dict[str, Any]:
    return {
        "coords": [float(value) for value in header.invoke_coord],
        "arguments": list(getattr(header, "invocation_arguments", ()) or ()),
        "layer": header.layer_info,
        "zoom_limits": ([float(value) for value in header.zoom_limits] if header.zoom_limits is not None else None),
        "zoomable": bool(header.zoomable),
    }


def _serialize_moduledef(moduledef: ModuleDef | None) -> dict[str, Any] | None:
    if moduledef is None:
        return None

    clipping_origin: list[float] | None = None
    clipping_size: list[float] | None = None
    if moduledef.clipping_bounds is not None:
        clipping_origin = [float(value) for value in moduledef.clipping_bounds[0]]
        clipping_size = [float(value) for value in moduledef.clipping_bounds[1]]

    return {
        "clipping_origin": clipping_origin,
        "clipping_size": clipping_size,
        "zoom_limits": (
            [float(value) for value in moduledef.zoom_limits] if moduledef.zoom_limits is not None else None
        ),
        "grid": float(moduledef.grid),
        "zoomable": bool(moduledef.zoomable),
    }


def _stable_json_marker(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _graphics_field_value(entry: dict[str, Any], field_name: str) -> Any:
    value: Any = entry
    for segment in field_name.split("."):
        if not isinstance(value, dict):
            return None
        value = cast(dict[str, Any], value).get(segment)
    return value


def _graphics_layout_group_payload(
    *,
    module_kind: str,
    module_name: str,
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    differing_fields: list[str] = []
    field_variants: dict[str, list[Any]] = {}

    for field_name in structural_reports_module.GRAPHICS_LAYOUT_COMPARISON_FIELDS:
        variants: dict[str, Any] = {}
        for member in members:
            value = _graphics_field_value(member, field_name)
            variants.setdefault(_stable_json_marker(value), value)
        if len(variants) > 1:
            differing_fields.append(field_name)
            field_variants[field_name] = list(variants.values())

    return {
        "group_key": f"{module_kind}:{module_name.casefold()}",
        "module_kind": module_kind,
        "module_name": module_name,
        "status": "drift" if differing_fields else "consistent",
        "entry_count": len(members),
        "module_paths": [member["module_path"] for member in members],
        "differing_fields": differing_fields,
        "field_variants": field_variants,
    }


def _graphics_layout_entry(
    *,
    workspace_root: Path,
    entry_file: Path,
    module_path: tuple[str, ...],
    module_kind: str,
    header: ModuleHeader,
    moduledef: ModuleDef | None,
    definition_scope: str,
    moduledef_origin_kind: str,
    moduletype_name: str | None = None,
    resolved_moduletype: ModuleTypeDef | None = None,
    resolution_error: str | None = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    relative_path = ".".join(module_path[1:]) if len(module_path) > 1 else ""
    module_name = module_path[-1] if module_path else ""
    payload = {
        "entry_file": structural_reports_module.sanitize_path_for_report(entry_file, repo_root=workspace_root),
        "module_path": ".".join(module_path),
        "relative_module_path": relative_path,
        "module_name": module_name,
        "module_kind": module_kind,
        "definition_scope": definition_scope,
        "moduledef_origin_kind": moduledef_origin_kind,
        "invocation": _serialize_invoke_coord(header),
        "moduledef": _serialize_moduledef(moduledef),
    }
    if moduletype_name is not None:
        payload["moduletype_name"] = moduletype_name
    if resolved_moduletype is not None:
        payload["resolved_moduletype"] = {
            "name": resolved_moduletype.name,
            "origin_file": resolved_moduletype.origin_file,
            "origin_lib": resolved_moduletype.origin_lib,
        }
    if resolution_error is not None:
        payload["resolution_error"] = resolution_error
    return payload


def _walk_graphics_layout_children(
    *,
    bp: BasePicture,
    children: list[SingleModule | FrameModule | ModuleTypeInstance],
    entry_file: Path,
    workspace_root: Path,
    snapshot: Any,
    entries: list[dict[str, Any]],
    parent_path: tuple[str, ...],
    current_library: str | None,
    definition_scope: str,
    active_moduletype_keys: set[tuple[str, str]],
) -> None:
    from sattlint.devtools import structural_reports as structural_reports_module

    project_graph: object = getattr(snapshot, "project_graph", None)
    raw_unavailable_libraries: object = (
        getattr(project_graph, "unavailable_libraries", None) if project_graph is not None else None
    )
    unavailable_libraries: set[str] = set()
    if isinstance(raw_unavailable_libraries, set):
        unavailable_libraries = {str(item) for item in cast(set[object], raw_unavailable_libraries)}

    for child in children:
        child_path = (*parent_path, child.header.name)
        if isinstance(child, SingleModule):
            entries.append(
                _graphics_layout_entry(
                    workspace_root=workspace_root,
                    entry_file=entry_file,
                    module_path=child_path,
                    module_kind="module",
                    header=child.header,
                    moduledef=child.moduledef,
                    definition_scope=definition_scope,
                    moduledef_origin_kind="local-module",
                )
            )
            _walk_graphics_layout_children(
                bp=bp,
                children=child.submodules or [],
                entry_file=entry_file,
                workspace_root=workspace_root,
                snapshot=snapshot,
                entries=entries,
                parent_path=child_path,
                current_library=current_library,
                definition_scope=definition_scope,
                active_moduletype_keys=active_moduletype_keys,
            )
            continue

        if isinstance(child, FrameModule):
            entries.append(
                _graphics_layout_entry(
                    workspace_root=workspace_root,
                    entry_file=entry_file,
                    module_path=child_path,
                    module_kind="frame",
                    header=child.header,
                    moduledef=child.moduledef,
                    definition_scope=definition_scope,
                    moduledef_origin_kind="local-module",
                )
            )
            _walk_graphics_layout_children(
                bp=bp,
                children=child.submodules or [],
                entry_file=entry_file,
                workspace_root=workspace_root,
                snapshot=snapshot,
                entries=entries,
                parent_path=child_path,
                current_library=current_library,
                definition_scope=definition_scope,
                active_moduletype_keys=active_moduletype_keys,
            )
            continue

        resolved_moduletype: ModuleTypeDef | None = None
        resolution_error: str | None = None
        try:
            resolved_moduletype = structural_reports_module.resolve_moduletype_def_strict(
                bp,
                child.moduletype_name,
                current_library=current_library,
                unavailable_libraries=unavailable_libraries,
            )
        except Exception as exc:
            resolution_error = str(exc)

        entries.append(
            _graphics_layout_entry(
                workspace_root=workspace_root,
                entry_file=entry_file,
                module_path=child_path,
                module_kind="moduletype-instance",
                header=child.header,
                moduledef=(resolved_moduletype.moduledef if resolved_moduletype is not None else None),
                definition_scope=definition_scope,
                moduledef_origin_kind=(
                    "moduletype-definition" if resolved_moduletype is not None else "unresolved-moduletype"
                ),
                moduletype_name=child.moduletype_name,
                resolved_moduletype=resolved_moduletype,
                resolution_error=resolution_error,
            )
        )
        if resolved_moduletype is None:
            continue

        moduletype_key = (
            (resolved_moduletype.origin_lib or current_library or "").casefold(),
            resolved_moduletype.name.casefold(),
        )
        if moduletype_key in active_moduletype_keys:
            continue

        active_moduletype_keys.add(moduletype_key)
        try:
            _walk_graphics_layout_children(
                bp=bp,
                children=resolved_moduletype.submodules or [],
                entry_file=entry_file,
                workspace_root=workspace_root,
                snapshot=snapshot,
                entries=entries,
                parent_path=child_path,
                current_library=resolved_moduletype.origin_lib or current_library,
                definition_scope=f"moduletype:{resolved_moduletype.name}",
                active_moduletype_keys=active_moduletype_keys,
            )
        finally:
            active_moduletype_keys.discard(moduletype_key)


def _accumulate_graphics_layout_snapshot(
    snapshot: Any,
    *,
    workspace_root: Path,
    entries: list[dict[str, Any]],
) -> None:
    bp = snapshot.base_picture
    if not hasattr(bp, "header"):
        return
    root_path = (bp.header.name,)
    entries.append(
        _graphics_layout_entry(
            workspace_root=workspace_root,
            entry_file=snapshot.entry_file,
            module_path=root_path,
            module_kind="basepicture",
            header=bp.header,
            moduledef=bp.moduledef,
            definition_scope="root",
            moduledef_origin_kind="local-module",
        )
    )
    _walk_graphics_layout_children(
        bp=bp,
        children=bp.submodules or [],
        entry_file=snapshot.entry_file,
        workspace_root=workspace_root,
        snapshot=snapshot,
        entries=entries,
        parent_path=root_path,
        current_library=getattr(bp, "origin_lib", None),
        definition_scope="root",
        active_moduletype_keys=set(),
    )


def _build_graphics_layout_report(
    *,
    workspace_root: Path,
    entries: list[dict[str, Any]],
    snapshot_count: int,
    snapshot_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    sorted_entries = sorted(entries, key=lambda item: (item["entry_file"] or "", item["module_path"].casefold()))

    grouped_entries: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for entry in sorted_entries:
        if entry["module_kind"] == "basepicture":
            continue
        grouped_entries.setdefault(
            (entry["module_kind"], entry["module_name"].casefold()),
            [],
        ).append(entry)

    groups = [
        _graphics_layout_group_payload(
            module_kind=members[0]["module_kind"],
            module_name=members[0]["module_name"],
            members=members,
        )
        for _key, members in sorted(grouped_entries.items(), key=lambda item: item[0])
        if len(members) > 1
    ]
    findings = [
        {
            "id": "graphics-layout-drift",
            "severity": "medium",
            "message": (
                f"Repeated {group['module_kind']} modules named {group['module_name']!r} "
                "have inconsistent graphics layout settings."
            ),
            "module_kind": group["module_kind"],
            "module_name": group["module_name"],
            "entry_count": group["entry_count"],
            "differing_fields": group["differing_fields"],
            "module_paths": group["module_paths"],
        }
        for group in groups
        if group["status"] == "drift"
    ]

    return {
        "generated_by": "sattlint.devtools.pipeline",
        "report_kind": "graphics-layout",
        "workspace_root": structural_reports_module.sanitize_path_for_report(
            workspace_root,
            repo_root=workspace_root,
        ),
        "comparison_fields": list(structural_reports_module.GRAPHICS_LAYOUT_COMPARISON_FIELDS),
        "entries": sorted_entries,
        "groups": groups,
        "findings": findings,
        "snapshot_count": snapshot_count,
        "snapshot_failures": snapshot_failures,
    }


def collect_graphics_layout_report(
    workspace_root: Path,
    *,
    graph_inputs: Any = None,
) -> dict[str, Any]:
    from sattlint.devtools import structural_reports as structural_reports_module

    resolved_inputs = structural_reports_module.normalize_graph_inputs(graph_inputs, workspace_root=workspace_root)
    entries: list[dict[str, Any]] = []

    for snapshot in resolved_inputs.snapshots:
        structural_reports_module.accumulate_graphics_layout_snapshot(
            snapshot,
            workspace_root=workspace_root,
            entries=entries,
        )

    return structural_reports_module.build_graphics_layout_report(
        workspace_root=workspace_root,
        entries=entries,
        snapshot_count=len(resolved_inputs.snapshots),
        snapshot_failures=resolved_inputs.snapshot_failures,
    )


__all__ = [
    "_accumulate_graphics_layout_snapshot",
    "_build_graphics_layout_report",
    "_graphics_field_value",
    "_graphics_layout_entry",
    "_graphics_layout_group_payload",
    "_serialize_invoke_coord",
    "_serialize_moduledef",
    "_stable_json_marker",
    "_walk_graphics_layout_children",
    "collect_graphics_layout_report",
]
