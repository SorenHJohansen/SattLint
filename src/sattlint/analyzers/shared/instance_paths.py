"""Instance-path helpers for surfacing moduletype issues at real invocations.

In SattLine a source file that declares a ``MODULETYPE`` always contains an
invocation of it too, and SattLine removes moduletypes that have no invocation.
Analyzer passes that study a moduletype body once therefore currently attribute
their findings to a synthetic ``TypeDef:Name`` module path, which is invisible
to SattLine engineers. These helpers map such paths back to the first real
invocation (instance) in the analyzed picture. Reverse consumers loaded only to
measure usage are deliberately excluded, so a finding never names a unit that
was not part of the run.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass, replace
from typing import Any, cast

from sattlint.parser_api import BasePicture, ModuleTypeInstance

from ...models.project_graph import ProjectGraph

_TYPEDEF_PREFIX = "TypeDef:"
_TYPEDEF_TOKEN_RE = re.compile(r"TypeDef:([A-Za-z_][A-Za-z0-9_]*)")


def _walk_modules(
    modules: Iterable[Any],
    path: list[str],
    out: dict[str, list[list[str]]],
) -> None:
    for mod in modules or []:
        child_path = [*path, mod.header.name]
        if isinstance(mod, ModuleTypeInstance):
            moduletype_name = getattr(mod, "moduletype_name", "") or ""
            if moduletype_name:
                out.setdefault(moduletype_name.casefold(), []).append(child_path)
        _walk_modules(getattr(mod, "submodules", None) or (), child_path, out)
        _walk_moduletype_defs(getattr(mod, "moduletype_defs", None) or (), child_path, out)


def _walk_moduletype_defs(
    moduletype_defs: Iterable[Any],
    path: list[str],
    out: dict[str, list[list[str]]],
) -> None:
    for mt in moduletype_defs or []:
        typedef_path = [*path, f"TypeDef:{mt.name}"]
        _walk_modules(getattr(mt, "submodules", None) or (), typedef_path, out)
        _walk_moduletype_defs(getattr(mt, "moduletype_defs", None) or (), typedef_path, out)


def collect_instance_paths(
    base_picture: BasePicture,
    graph: ProjectGraph | None = None,
) -> dict[str, list[list[str]]]:
    """Map each moduletype name (casefolded) to every instance path found.

    Instances are collected from the whole module tree, including moduletype
    bodies (a typedef can only be invoked from within another typedef or a
    module), using the same ``TypeDef:`` prefixed paths the analyzers use.
    """
    out: dict[str, list[list[str]]] = {}
    root_name = base_picture.header.name
    _walk_modules(getattr(base_picture, "submodules", None) or (), [root_name], out)
    _walk_moduletype_defs(getattr(base_picture, "moduletype_defs", None) or (), [root_name], out)
    if graph is not None:
        for bp in cast(dict[str, BasePicture], getattr(graph, "ast_by_name", {})).values():
            if bp is base_picture:
                continue
            bp_name = bp.header.name
            _walk_modules(getattr(bp, "submodules", None) or (), [bp_name], out)
            _walk_moduletype_defs(getattr(bp, "moduletype_defs", None) or (), [bp_name], out)
    return out


def rewrite_typedef_paths[RecordT](
    records: Iterable[RecordT],
    base_picture: BasePicture,
) -> list[RecordT]:
    """Return copies of ``records`` with ``TypeDef:Name`` segments resolved.

    Frozen report records are never mutated: each record whose module path
    mentions a moduletype is rebuilt through ``dataclasses.replace`` and the
    caller rebinds its own collection. A record that is not a dataclass is
    returned unchanged. Also rewrites the same ``TypeDef:Name`` tokens inside
    a record's message and ``data`` so leaf text agrees with the rewritten
    branch. Only invocations inside the analyzed picture are used: a
    reverse consumer or dependency that happens to invoke the same type is
    outside the reported target, and routing a finding through its tree would
    name a unit the user did not analyze. If the picture has no invocation, the
    ``TypeDef:`` text is left unchanged so the finding is never lost.
    """
    index: dict[str, list[list[str]]] | None = None
    rewritten_records: list[RecordT] = []
    for record in records:
        module_path = getattr(record, "module_path", None)
        if not isinstance(module_path, list | tuple):
            rewritten_records.append(record)
            continue
        path_segments = cast(list[object] | tuple[object, ...], module_path)
        if not any(isinstance(segment, str) and segment.startswith(_TYPEDEF_PREFIX) for segment in path_segments):
            rewritten_records.append(record)
            continue
        if index is None:
            index = collect_instance_paths(base_picture)
        rewritten_records.append(_rewrite_typedef_record(record, path_segments, index))
    return rewritten_records


def _rewrite_typedef_record[RecordT](
    record: RecordT,
    module_path: list[object] | tuple[object, ...],
    index: Mapping[str, list[list[str]]],
) -> RecordT:
    if not is_dataclass(record) or isinstance(record, type):
        # Only dataclass records can be rebuilt without touching shared
        # state. A plugin that reports its own record type keeps its path.
        return record

    rewritten_path = _rewrite_typedef_path(list(module_path), index)
    updates: dict[str, Any] = {
        "module_path": tuple(rewritten_path) if isinstance(module_path, tuple) else rewritten_path,
    }
    field_names = {field_info.name for field_info in fields(record)}

    if "message" in field_names:
        message = getattr(record, "message", None)
        if isinstance(message, str) and message:
            rewritten_message = _replace_typedef_tokens(message, index)
            if rewritten_message != message:
                updates["message"] = rewritten_message

    if "data" in field_names:
        data = getattr(record, "data", None)
        if isinstance(data, dict):
            data_mapping = cast(dict[str, Any], data)
            updates["data"] = {key: _replace_typedef_tokens(value, index) for key, value in data_mapping.items()}

    return replace(record, **updates)


def _rewrite_typedef_path(
    module_path: list[object],
    index: Mapping[str, list[list[str]]],
) -> list[str]:
    """Resolve ``TypeDef:Name`` segments to their first invocation path.

    Iterates to a fixpoint so nested typedefs (an instance inside another
    typedef's body) resolve to the full invocation chain. Segments whose typedef
    has no invocation anywhere in the graph are left unchanged.
    """
    current = [str(segment) for segment in module_path]
    for _ in range(len(current) + 1):
        rewritten: list[str] = []
        changed = False
        for segment in current:
            if segment.startswith(_TYPEDEF_PREFIX):
                paths = index.get(segment.removeprefix(_TYPEDEF_PREFIX).casefold())
                if paths:
                    rewritten.extend(paths[0][1:])
                    changed = True
                else:
                    rewritten.append(segment)
            else:
                rewritten.append(segment)
        if not changed:
            break
        current = rewritten
    return current


def _replace_typedef_tokens(value: Any, index: Mapping[str, list[list[str]]]) -> Any:
    if isinstance(value, str):
        text = value
        for _ in range(10):
            rewritten = _TYPEDEF_TOKEN_RE.sub(
                lambda match: _typedef_replacement(match.group(1), index),
                text,
            )
            if rewritten == text:
                break
            text = rewritten
        return text
    if isinstance(value, list):
        sequence = cast(list[object], value)
        return [_replace_typedef_tokens(item, index) for item in sequence]
    if isinstance(value, tuple):
        sequence = cast(tuple[object, ...], value)
        return tuple(_replace_typedef_tokens(item, index) for item in sequence)
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        return {str(key): _replace_typedef_tokens(item, index) for key, item in mapping.items()}
    return value


def _typedef_replacement(moduletype_name: str, index: Mapping[str, list[list[str]]]) -> str:
    paths = index.get(moduletype_name.casefold())
    if not paths:
        return f"TypeDef:{moduletype_name}"
    instance_tail = paths[0][1:]
    if not instance_tail:
        return f"TypeDef:{moduletype_name}"
    return ".".join(instance_tail)


__all__ = [
    "collect_instance_paths",
    "rewrite_typedef_paths",
]
