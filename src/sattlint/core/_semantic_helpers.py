"""Internal helpers shared by semantic loading, snapshot, and indexing code."""

from __future__ import annotations

from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
)

from ..engine import CodeMode, expected_unavailable_library_reason
from ..models.project_graph import ProjectGraph
from ..resolution import TypeGraph
from ..resolution.common import resolve_moduletype_def_strict

_DEFAULT_LIST_DISPLAY_LIMIT = 12


def _cf(value: str) -> str:
    return value.casefold()


def _format_datatype(datatype: Simple_DataType | str | None) -> str | None:
    if datatype is None:
        return None
    if isinstance(datatype, Simple_DataType):
        return str(datatype.value)
    return str(datatype)


def _format_moduletype_label(moduletype: ModuleTypeDef) -> str:
    file_label = f" ({moduletype.origin_file})" if moduletype.origin_file else ""
    if moduletype.origin_lib:
        return f"{moduletype.origin_lib}:{moduletype.name}{file_label}"
    return moduletype.name


def _dedupe_moduletype_defs(matches: list[ModuleTypeDef]) -> list[ModuleTypeDef]:
    unique: dict[tuple[str, str, str], ModuleTypeDef] = {}
    for moduletype in matches:
        key = (
            moduletype.name.casefold(),
            (moduletype.origin_lib or "").casefold(),
            (moduletype.origin_file or "").casefold(),
        )
        if key not in unique:
            unique[key] = moduletype
    return list(unique.values())


def _format_name_list(items: list[str], *, limit: int = _DEFAULT_LIST_DISPLAY_LIMIT) -> str:
    if len(items) <= limit:
        return ", ".join(items)
    shown = ", ".join(items[:limit])
    return f"{shown}, ... (+{len(items) - limit} more)"


def _format_workspace_snapshot_failure(
    entry_name: str,
    graph: ProjectGraph,
    *,
    detail: str | None = None,
) -> str:
    target_prefix = f"{entry_name} parse/transform error:"
    dependency_issues = [
        message for message in graph.missing if not message.casefold().startswith(target_prefix.casefold())
    ]
    resolved = sorted(graph.ast_by_name.keys(), key=str.casefold)
    unavailable = sorted(graph.unavailable_libraries, key=str.casefold)

    if detail is not None:
        lines = [f"Target {entry_name!r} failed parse/transform: {detail}"]
    else:
        lines = [f"Target {entry_name!r} was not parsed."]

    if resolved:
        lines.append(f"Resolved targets ({len(resolved)}): {_format_name_list(resolved)}")

    if unavailable:
        lines.append(f"Unavailable libraries ({len(unavailable)}):")
        for name in unavailable[:8]:
            reason = expected_unavailable_library_reason(name)
            if reason:
                lines.append(f"- {name} ({reason})")
            else:
                lines.append(f"- {name}")
        if len(unavailable) > 8:
            lines.append(f"- ... (+{len(unavailable) - 8} more)")

    if dependency_issues:
        lines.append(f"Other dependency issues ({len(dependency_issues)}):")
        for message in dependency_issues[:8]:
            lines.append(f"- {message}")

    if graph.warnings:
        lines.append(f"Validation warnings ({len(graph.warnings)}):")
        for message in graph.warnings[:8]:
            lines.append(f"- {message}")
        if len(dependency_issues) > 8:
            lines.append(f"- ... (+{len(dependency_issues) - 8} more)")

    return "\n".join(lines)


def _path_startswith(path: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    if len(prefix) > len(path):
        return False
    return tuple(_cf(part) for part in path[: len(prefix)]) == tuple(_cf(part) for part in prefix)


def _resolve_field_datatype(
    type_graph: TypeGraph,
    root_type: Simple_DataType | str,
    field_path: tuple[str, ...],
) -> Simple_DataType | str | None:
    current: Simple_DataType | str = root_type
    for segment in field_path:
        if isinstance(current, Simple_DataType):
            return current
        field = type_graph.field(str(current), segment)
        if field is None:
            return None
        current = field.datatype
    return current


def _normalize_mode(mode: CodeMode | str) -> CodeMode:
    if isinstance(mode, CodeMode):
        return mode
    return CodeMode(str(mode).strip().lower())


def _source_file_key(value: Path | str | None) -> str | None:
    if value is None:
        return None
    return Path(str(value)).name.casefold()


def _identifier_contains_column(start_column: int, text: str, column: int) -> bool:
    if start_column <= 0 or not text:
        return False
    return start_column <= column <= (start_column + len(text) - 1)


def _child_module_items(
    base_picture: BasePicture,
    node: BasePicture | SingleModule | FrameModule | ModuleTypeInstance | ModuleTypeDef,
    moduletype_index: dict[str, list[ModuleTypeDef]],
    unavailable_libraries: set[str],
) -> list[tuple[str, str]]:
    if isinstance(node, BasePicture | SingleModule | FrameModule | ModuleTypeDef):
        children = list(node.submodules or [])
    else:
        typedef = _try_resolve_instance_typedef(
            base_picture,
            node,
            moduletype_index,
            unavailable_libraries,
        )
        children = list(typedef.submodules or []) if typedef is not None else []

    items: list[tuple[str, str]] = []
    for child in children:
        if isinstance(child, SingleModule):
            items.append((child.header.name, "module"))
        elif isinstance(child, FrameModule):
            items.append((child.header.name, "frame"))
        else:
            items.append((child.header.name, "moduletype-instance"))
    return items


def _resolve_instance_typedef(
    base_picture: BasePicture,
    instance: ModuleTypeInstance,
    moduletype_index: dict[str, list[ModuleTypeDef]],
    unavailable_libraries: set[str],
    current_library: str | None = None,
) -> ModuleTypeDef:
    matches = moduletype_index.get(instance.moduletype_name.casefold(), [])
    if len(matches) == 1:
        return matches[0]
    return resolve_moduletype_def_strict(
        base_picture,
        instance.moduletype_name,
        current_library=current_library,
        unavailable_libraries=unavailable_libraries,
    )


def _try_resolve_instance_typedef(
    base_picture: BasePicture,
    instance: ModuleTypeInstance,
    moduletype_index: dict[str, list[ModuleTypeDef]],
    unavailable_libraries: set[str],
    current_library: str | None = None,
) -> ModuleTypeDef | None:
    try:
        return _resolve_instance_typedef(
            base_picture,
            instance,
            moduletype_index,
            unavailable_libraries,
            current_library=current_library,
        )
    except ValueError:
        return None


cf = _cf
format_datatype = _format_datatype
format_moduletype_label = _format_moduletype_label
format_name_list = _format_name_list
format_workspace_snapshot_failure = _format_workspace_snapshot_failure
dedupe_moduletype_defs = _dedupe_moduletype_defs
path_startswith = _path_startswith
normalize_mode = _normalize_mode
source_file_key = _source_file_key
identifier_contains_column = _identifier_contains_column
child_module_items = _child_module_items
resolve_field_datatype = _resolve_field_datatype
try_resolve_instance_typedef = _try_resolve_instance_typedef
