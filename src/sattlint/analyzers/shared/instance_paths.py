"""Instance-path helpers for surfacing moduletype issues at real invocations.

In SattLine a source file that declares a ``MODULETYPE`` always contains an
invocation of it too, and SattLine removes moduletypes that have no invocation.
Analyzer passes that study a moduletype body once therefore currently attribute
their findings to a synthetic ``TypeDef:Name`` module path, which is invisible
to SattLine engineers. These helpers map such paths back to the first real
invocation (instance) found anywhere in the loaded graph.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import FrozenInstanceError
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture, ModuleTypeInstance

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


def first_instance_path_for_moduletype(
    base_picture: BasePicture,
    moduletype_name: str,
    graph: ProjectGraph | None = None,
) -> list[str] | None:
    paths = collect_instance_paths(base_picture, graph).get(moduletype_name.casefold())
    if paths:
        return paths[0]
    return None


def rewrite_typedef_paths(
    issues: Iterable[Any],
    base_picture: BasePicture,
    graph: ProjectGraph | None = None,
) -> None:
    """Replace any ``TypeDef:Name`` segment in each issue's module path in place.

    Also rewrites the same ``TypeDef:Name`` tokens inside the issue's message and
    ``data`` so leaf text agrees with the rewritten branch. If no invocation
    exists anywhere in the loaded graph, the ``TypeDef:`` text is left unchanged
    so the finding is never lost.
    """
    index: dict[str, list[list[str]]] | None = None
    for issue in issues:
        raw_path = getattr(issue, "module_path", None)
        if not isinstance(raw_path, list):
            continue
        module_path = cast(list[object], raw_path)
        if not any(isinstance(seg, str) and seg.startswith(_TYPEDEF_PREFIX) for seg in module_path):
            continue
        if index is None:
            index = collect_instance_paths(base_picture, graph)
        rewritten = _rewrite_typedef_path(module_path, index)
        module_path[:] = cast(list[Any], rewritten)
        _rewrite_typedef_text(issue, index)


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


def _rewrite_typedef_text(issue: Any, index: Mapping[str, list[list[str]]]) -> None:
    message = getattr(issue, "message", None)
    if isinstance(message, str) and message:
        rewritten = _replace_typedef_tokens(message, index)
        if rewritten != message:
            try:
                issue.message = rewritten
            except FrozenInstanceError:
                object.__setattr__(issue, "message", rewritten)
    data = getattr(issue, "data", None)
    if isinstance(data, dict):
        mapping = cast(dict[str, Any], data)
        for key, value in list(mapping.items()):
            mapping[key] = _replace_typedef_tokens(value, index)


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
    "first_instance_path_for_moduletype",
    "rewrite_typedef_paths",
]
