from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)


@dataclass(frozen=True)
class ResolvedModulePath:
    node: Any
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


def select_moduletype_def_strict(
    bp: BasePicture,
    moduletype_name: str,
    matches: list[ModuleTypeDef],
    *,
    current_library: str | None = None,
    current_file: str | None = None,
    unavailable_libraries: set[str] | None = None,
) -> ModuleTypeDef:
    if not matches:
        available = sorted({mt.name for mt in (bp.moduletype_defs or [])})
        note = ""
        if unavailable_libraries:
            note = f" Note: Some libraries are unavailable (e.g., proprietary): {sorted(unavailable_libraries)[:10]}"
        raise ValueError(f"Unknown moduletype {moduletype_name!r}.{note} Available moduletype defs: {available[:50]}")

    matches = dedupe_moduletype_defs(matches)
    preferred_extensions = preferred_source_extensions(current_file or bp.origin_file)

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

            deps = (bp.library_dependencies or {}).get(current_lib_cf, [])
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
) -> ModuleTypeDef:
    key = moduletype_name.casefold()
    matches = [mt for mt in (bp.moduletype_defs or []) if mt.name.casefold() == key]
    return select_moduletype_def_strict(
        bp,
        moduletype_name,
        matches,
        current_library=current_library,
        current_file=current_file,
        unavailable_libraries=unavailable_libraries,
    )


def resolve_module_by_strict_path(  # noqa: PLR0915
    bp: BasePicture,
    module_path: str,
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
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

    current: Any = bp
    resolved_path: list[str] = [bp.header.name]
    current_library = bp.origin_lib
    current_file = bp.origin_file

    def resolve_moduletype(node: ModuleTypeInstance) -> ModuleTypeDef:
        if moduletype_index is not None:
            matches = moduletype_index.get(node.moduletype_name.casefold(), [])
            if matches:
                return select_moduletype_def_strict(
                    bp,
                    node.moduletype_name,
                    matches,
                    current_library=current_library,
                    current_file=current_file,
                )
        return resolve_moduletype_def_strict(
            bp,
            node.moduletype_name,
            current_library=current_library,
            current_file=current_file,
        )

    def children_of(node: Any) -> list[Any]:
        if isinstance(node, BasePicture):
            return list(node.submodules or [])
        if isinstance(node, SingleModule | FrameModule | ModuleTypeDef):
            return list(node.submodules or [])
        if isinstance(node, ModuleTypeInstance):
            mt = resolve_moduletype(node)
            return list(mt.submodules or [])
        return []

    for segment in segments:
        wanted = segment.strip()
        candidates = children_of(current)
        if not candidates:
            raise ValueError(
                f"Module path {module_path!r} cannot continue past {resolved_path[-1]!r} "
                f"(node type: {type(current).__name__})."
            )

        matches: list[Any] = [
            module
            for module in candidates
            if hasattr(module, "header") and module.header.name.casefold() == wanted.casefold()
        ]

        if not matches:
            names = [module.header.name for module in candidates if hasattr(module, "header")]
            close = difflib.get_close_matches(wanted, names, n=5, cutoff=0.6)

            details: list[str] = []
            for module in candidates:
                if not hasattr(module, "header"):
                    continue
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
