from __future__ import annotations

import difflib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from sattlint.parser_api import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)

type SubmoduleNode = SingleModule | FrameModule | ModuleTypeInstance
type ModuleNode = BasePicture | SubmoduleNode

# ``id(node)`` plus the resolution context identifies one module-type lookup.
# The node is kept in the value so an id is never reused while cached.
type ModuleTypeResolutionCache = dict[
    tuple[int, str | None, str | None],
    tuple[ModuleTypeInstance, ModuleTypeDef],
]


@dataclass(frozen=True)
class ResolvedModulePath:
    node: ModuleNode
    path: list[str]
    display_path_str: str
    current_library: str | None = None
    current_file: str | None = None


def format_moduletype_label(mt: ModuleTypeDef) -> str:
    file_label = f" ({mt.origin_file})" if mt.origin_file else ""
    if mt.origin_lib:
        return f"{mt.origin_lib}:{mt.name}{file_label}"
    return mt.name


def dedupe_moduletype_defs(matches: list[ModuleTypeDef]) -> list[ModuleTypeDef]:
    unique: dict[tuple[str, str, str], ModuleTypeDef] = {}
    for mt in matches:
        key = (
            mt.name.casefold(),
            (mt.origin_lib or "").casefold(),
            (mt.origin_file or "").casefold(),
        )
        if key not in unique:
            unique[key] = mt
    return list(unique.values())


def preferred_source_extensions(origin_file: str | None) -> list[str]:
    suffix = Path(origin_file).suffix.lower() if origin_file else ""
    if suffix == ".s":
        return [".s", ".x"]
    if suffix == ".x":
        return [".x", ".s"]
    return []


def narrow_matches_by_source_preference(
    matches: list[ModuleTypeDef],
    preferred_extensions: list[str],
) -> list[ModuleTypeDef]:
    if len(matches) <= 1 or not preferred_extensions:
        return matches

    for ext in preferred_extensions:
        scoped = [mt for mt in matches if Path(mt.origin_file or "").suffix.lower() == ext]
        if scoped:
            return scoped

    return matches


def select_moduletype_def_strict(  # noqa: PLR0915
    bp: BasePicture,
    moduletype_name: str,
    matches: list[ModuleTypeDef],
    *,
    current_library: str | None = None,
    current_file: str | None = None,
    unavailable_libraries: set[str] | None = None,
    library_dependencies: Mapping[str, Iterable[str]] | None = None,
    source_dependencies: Mapping[str, Iterable[str]] | None = None,
    available_names: Callable[[], Sequence[str]] | None = None,
) -> ModuleTypeDef:
    if not matches:
        candidates = (
            available_names() if available_names is not None else [mt.name for mt in (bp.moduletype_defs or [])]
        )
        available = sorted(set(candidates))
        note = ""
        if unavailable_libraries:
            note = f" Note: Some libraries are unavailable (e.g., proprietary): {sorted(unavailable_libraries)[:10]}"
        raise ValueError(f"Unknown moduletype {moduletype_name!r}.{note} Available moduletype defs: {available[:50]}")

    matches = dedupe_moduletype_defs(matches)
    preferred_extensions = preferred_source_extensions(current_file or bp.origin_file)

    if current_file is not None:
        current_file_cf = current_file.casefold()
        # A unit's own definition is the one its code means, even when other
        # units in the same library folder declare the same name.
        same_file = [mt for mt in matches if (mt.origin_file or "").casefold() == current_file_cf]
        if len(same_file) == 1:
            return same_file[0]

        # ``PRIVATE_`` types are visible only inside their declaring unit.
        visible = [mt for mt in matches if not mt.is_private or (mt.origin_file or "").casefold() == current_file_cf]
        if visible:
            matches = visible

        # The dependency sidecar names the units this file may use, which is
        # more precise than the library folder several units can share.
        unit_dependencies = (source_dependencies or {}).get(Path(current_file).stem.casefold(), ())
        dependencies = {item.casefold() for item in unit_dependencies}
        if dependencies:
            declared_by_dependency = [
                mt for mt in matches if Path(mt.origin_file or "").stem.casefold() in dependencies
            ]
            if declared_by_dependency:
                matches = declared_by_dependency

    if len(matches) > 1:
        if current_library is None and bp.origin_lib:
            current_library = bp.origin_lib

        if current_library:
            current_lib_cf = current_library.casefold()
            local_matches = [mt for mt in matches if (mt.origin_lib or "").casefold() == current_lib_cf]
            local_matches = narrow_matches_by_source_preference(local_matches, preferred_extensions)
            if len(local_matches) == 1:
                return local_matches[0]
            if len(local_matches) > 1:
                labels = sorted(format_moduletype_label(mt) for mt in local_matches)
                raise ValueError(f"Ambiguous moduletype {moduletype_name!r} (multiple definitions): {labels}")

            deps = library_dependencies.get(current_lib_cf, ()) if library_dependencies is not None else ()
            dep_candidates: list[ModuleTypeDef] = []
            for dep in deps:
                dep_cf = dep.casefold()
                dep_matches = [mt for mt in matches if (mt.origin_lib or "").casefold() == dep_cf]
                dep_matches = narrow_matches_by_source_preference(dep_matches, preferred_extensions)
                if len(dep_matches) > 1:
                    labels = sorted(format_moduletype_label(mt) for mt in dep_matches)
                    raise ValueError(f"Ambiguous moduletype {moduletype_name!r} (multiple definitions): {labels}")
                if len(dep_matches) == 1:
                    dep_candidates.append(dep_matches[0])

            if len(dep_candidates) == 1:
                return dep_candidates[0]
            if len(dep_candidates) > 1:
                labels = sorted(format_moduletype_label(mt) for mt in dep_candidates)
                raise ValueError(f"Ambiguous moduletype {moduletype_name!r} (multiple definitions): {labels}")

        matches = narrow_matches_by_source_preference(matches, preferred_extensions)
        if len(matches) == 1:
            return matches[0]

        labels = sorted(format_moduletype_label(mt) for mt in matches)
        raise ValueError(f"Ambiguous moduletype {moduletype_name!r} (multiple definitions): {labels}")

    return matches[0]


def resolve_moduletype_def_strict(
    bp: BasePicture,
    moduletype_name: str,
    current_library: str | None = None,
    current_file: str | None = None,
    unavailable_libraries: set[str] | None = None,
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    library_dependencies: Mapping[str, Iterable[str]] | None = None,
    source_dependencies: Mapping[str, Iterable[str]] | None = None,
) -> ModuleTypeDef:
    key = moduletype_name.casefold()
    available_names: Callable[[], list[str]] | None
    if moduletype_index is not None:
        index = moduletype_index
        matches = index.get(key, [])

        # The available-name listing only feeds the unknown-type diagnostic, so it
        # is built on demand: a hit must not walk every defined type to answer.
        def list_available_names() -> list[str]:
            return [mt.name for defs in index.values() for mt in defs]

        available_names = list_available_names
    else:
        matches = [mt for mt in (bp.moduletype_defs or []) if mt.name.casefold() == key]
        available_names = None
    return select_moduletype_def_strict(
        bp,
        moduletype_name,
        matches,
        current_library=current_library,
        current_file=current_file,
        unavailable_libraries=unavailable_libraries,
        library_dependencies=library_dependencies,
        source_dependencies=source_dependencies,
        available_names=available_names,
    )


def resolve_module_by_strict_path(  # noqa: PLR0915
    bp: BasePicture,
    module_path: str,
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    resolution_cache: ModuleTypeResolutionCache | None = None,
) -> ResolvedModulePath:
    """Resolve a strict dotted module path relative to the BasePicture.

    - Input is case-insensitive.
    - No fallback/heuristics.
    - Any missing segment fails with a loud error.
    - Any ambiguous segment fails with a loud error.

    ModuleTypeInstance nodes have no `submodules`; if the path continues past a
    ModuleTypeInstance, subsequent segments are resolved within its referenced
    ModuleTypeDef's `submodules`.
    """
    raw = (module_path or "").strip()
    if not raw:
        raise ValueError("Empty module path")

    bp_prefix = f"{bp.header.name}."
    if raw.casefold().startswith(bp_prefix.casefold()):
        raw = raw[len(bp_prefix) :].strip()
    if not raw:
        raise ValueError("Module path cannot point to BasePicture itself")

    if raw.startswith(".") or raw.endswith(".") or ".." in raw:
        raise ValueError(f"Invalid module path syntax: {module_path!r}")

    segments = raw.split(".")
    if any(not segment.strip() for segment in segments):
        raise ValueError(f"Invalid module path syntax: {module_path!r}")

    current: ModuleNode = bp
    resolved_path: list[str] = [bp.header.name]
    current_library = bp.origin_lib
    current_file = bp.origin_file

    def resolve_moduletype(node: ModuleTypeInstance) -> ModuleTypeDef:
        cache_key = (id(node), current_file, current_library)
        if resolution_cache is not None:
            cached = resolution_cache.get(cache_key)
            if cached is not None:
                return cached[1]
        resolved: ModuleTypeDef
        matches = moduletype_index.get(node.moduletype_name.casefold(), []) if moduletype_index is not None else []
        if matches and moduletype_index is not None:
            index = moduletype_index
            resolved = select_moduletype_def_strict(
                bp,
                node.moduletype_name,
                matches,
                current_library=current_library,
                current_file=current_file,
                available_names=lambda: [mt.name for defs in index.values() for mt in defs],
            )
        else:
            resolved = resolve_moduletype_def_strict(
                bp,
                node.moduletype_name,
                current_library=current_library,
                current_file=current_file,
            )
        if resolution_cache is not None:
            resolution_cache[cache_key] = (node, resolved)
        return resolved

    def children_of(node: object) -> list[ModuleNode]:
        if isinstance(node, BasePicture | SingleModule | FrameModule | ModuleTypeDef):
            return list(node.submodules or [])
        if isinstance(node, ModuleTypeInstance):
            return list(resolve_moduletype(node).submodules or [])
        raise TypeError(f"Unexpected module node {type(node).__name__} while resolving a module path")

    for segment in segments:
        wanted = segment.strip()
        candidates = children_of(current)
        if not candidates:
            raise ValueError(
                f"Module path {module_path!r} cannot continue past {resolved_path[-1]!r} "
                f"(node type: {type(current).__name__})."
            )

        matches: list[ModuleNode] = [
            module for module in candidates if module.header.name.casefold() == wanted.casefold()
        ]

        if not matches:
            names = [module.header.name for module in candidates]
            close = difflib.get_close_matches(wanted, names, n=5, cutoff=0.6)

            details: list[str] = []
            for module in candidates:
                if isinstance(module, ModuleTypeInstance):
                    try:
                        mt = resolve_moduletype(module)
                        details.append(f"{module.header.name} ({format_moduletype_label(mt)})")
                    except (ValueError, AttributeError):
                        details.append(f"{module.header.name} ({module.moduletype_name})")
                else:
                    details.append(module.header.name)

            msg = (
                f"Unknown module path segment {wanted!r} under {'.'.join(resolved_path)!r}. "
                f"Valid next segments: {details[:50]}"
            )
            if close:
                msg += f". Close matches: {close}"
            raise ValueError(msg)

        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous module path segment {wanted!r} under {'.'.join(resolved_path)!r}. "
                f"Matches: {[module.header.name for module in matches]}"
            )

        current = matches[0]
        resolved_path.append(matches[0].header.name)
        if isinstance(current, ModuleTypeInstance):
            mt = resolve_moduletype(current)
            if mt.origin_lib:
                current_library = mt.origin_lib
            if mt.origin_file:
                current_file = mt.origin_file
        elif isinstance(current, BasePicture | ModuleTypeDef):
            if current.origin_lib:
                current_library = current.origin_lib
            if current.origin_file:
                current_file = current.origin_file

    display_path = ".".join(resolved_path)
    return ResolvedModulePath(
        node=current,
        path=resolved_path,
        display_path_str=display_path,
        current_library=current_library,
        current_file=current_file,
    )
