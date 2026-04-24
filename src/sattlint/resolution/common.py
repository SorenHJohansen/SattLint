from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..grammar import constants as const
from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)


@dataclass(frozen=True)
class ResolvedModulePath:
    node: Any
    path: list[str]
    display_path_str: str
    current_library: str | None = None
    current_file: str | None = None


def path_startswith_casefold(location: list[str], prefix: list[str]) -> bool:
    if len(location) < len(prefix):
        return False
    return all(location[i].casefold() == seg.casefold() for i, seg in enumerate(prefix))


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


def resolve_module_by_strict_path(
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

    # Accept optional leading "<BasePictureName>." for convenience.
    bp_prefix = f"{bp.header.name}."
    if raw.casefold().startswith(bp_prefix.casefold()):
        raw = raw[len(bp_prefix) :].strip()
    if not raw:
        raise ValueError("Module path cannot point to BasePicture itself")

    if raw.startswith(".") or raw.endswith(".") or ".." in raw:
        raise ValueError(f"Invalid module path syntax: {module_path!r}")

    segments = raw.split(".")
    if any(not s.strip() for s in segments):
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

    for seg in segments:
        wanted = seg.strip()
        candidates = children_of(current)
        if not candidates:
            raise ValueError(
                f"Module path {module_path!r} cannot continue past {resolved_path[-1]!r} "
                f"(node type: {type(current).__name__})."
            )

        matches: list[Any] = [
            m for m in candidates if hasattr(m, "header") and m.header.name.casefold() == wanted.casefold()
        ]

        if not matches:
            names = [m.header.name for m in candidates if hasattr(m, "header")]
            close = difflib.get_close_matches(wanted, names, n=5, cutoff=0.6)

            details: list[str] = []
            for m in candidates:
                if not hasattr(m, "header"):
                    continue
                if isinstance(m, ModuleTypeInstance):
                    try:
                        mt = resolve_moduletype(m)
                        details.append(f"{m.header.name} ({format_moduletype_label(mt)})")
                    except (ValueError, AttributeError):
                        details.append(f"{m.header.name} ({m.moduletype_name})")
                else:
                    details.append(m.header.name)

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
                f"Matches: {[m.header.name for m in matches]}"
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


def find_module_by_name(bp: BasePicture, name: str):
    """Recursively find a module by name in the AST."""
    name_lower = name.lower()

    # First check if it's a ModuleTypeDef
    for mt in bp.moduletype_defs or []:
        if mt.name.lower() == name_lower:
            return mt

    # Then search in submodules (instances)
    def search(modules):
        for mod in modules or []:
            if hasattr(mod, "header") and mod.header.name.lower() == name_lower:
                return mod
            if hasattr(mod, "submodules"):
                result = search(mod.submodules)
                if result:
                    return result
        return None

    return search(bp.submodules)


def get_module_path(bp: BasePicture, target_module) -> list[str]:
    """Get the full path to a module."""

    # Check if it's a ModuleTypeDef
    if isinstance(target_module, ModuleTypeDef):
        return [bp.header.name, f"TypeDef:{target_module.name}"]

    # Otherwise search in submodules
    def search(modules, path):
        for mod in modules or []:
            current_path = [*path, mod.header.name]
            if mod is target_module:
                return current_path
            if hasattr(mod, "submodules"):
                result = search(mod.submodules, current_path)
                if result:
                    return result
        return None

    result = search(bp.submodules, [bp.header.name])
    return result or []


def is_external_to_module(location_path: list[str], module_path: list[str]) -> bool:
    """
    Check if a location is external to the module.

    For ModuleTypeDef (e.g., "TypeDef:Applik"):
    - External: location does NOT contain "TypeDef:Applik" in its path
    - Internal: location contains "TypeDef:Applik" in its path

    For regular modules:
    - External: location path doesn't start with the module's path
    - Internal: location path starts with the module's path
    """
    # Check if this is a TypeDef path
    if len(module_path) >= 2 and module_path[-1].startswith("TypeDef:"):
        typedef_segment = module_path[-1]
        # Internal if the typedef segment appears anywhere in the location path
        return typedef_segment not in location_path

    # For regular module instances, check if location starts with module_path
    if len(location_path) < len(module_path):
        return True

    # Check if location_path starts with module_path
    return any(i >= len(location_path) or location_path[i] != segment for i, segment in enumerate(module_path))


def find_var_in_scope(bp: BasePicture, instance_path: list[str], var_name: str) -> Variable | None:
    """
    Find a variable by name that's in scope at the given instance path.
    Searches from the instance location upwards through parent modules.
    """
    var_name_lower = var_name.lower()

    # Start from the parent of the instance (exclude the instance itself)
    parent_path = instance_path[:-1]

    # Search from the parent path upwards
    for i in range(len(parent_path), 0, -1):
        search_path = parent_path[:i]

        # Navigate to the module at this path
        if len(search_path) == 1:
            # At BasePicture level
            for v in bp.localvariables or []:
                if v.name.lower() == var_name_lower:
                    return v
            continue

        # Navigate through the path
        current: SingleModule | FrameModule | ModuleTypeInstance | ModuleTypeDef | None = None
        for j, segment in enumerate(search_path[1:], 1):  # Skip "BasePicture"
            if j == 1:
                # First level: check if it's a TypeDef or submodule
                if segment.startswith("TypeDef:"):
                    typedef_name = segment.split(":", 1)[1]
                    current = next((mt for mt in bp.moduletype_defs or [] if mt.name == typedef_name), None)
                else:
                    current = next(
                        (mod for mod in bp.submodules or [] if hasattr(mod, "header") and mod.header.name == segment),
                        None,
                    )
            else:
                # Navigate deeper
                if current is None:
                    break

                if segment.startswith("TypeDef:"):
                    # We're at a typedef in the path - this shouldn't happen in normal navigation
                    # but let's handle it
                    break
                else:
                    if isinstance(current, SingleModule | FrameModule):
                        current = next(
                            (
                                mod
                                for mod in current.submodules or []
                                if hasattr(mod, "header") and mod.header.name == segment
                            ),
                            None,
                        )
                    else:
                        break

        if current is None:
            continue

        # Check variables at this level
        if isinstance(current, SingleModule | ModuleTypeDef):
            # Check localvariables
            for v in current.localvariables or []:
                if v.name.lower() == var_name_lower:
                    return v
            # Check moduleparameters
            for v in current.moduleparameters or []:
                if v.name.lower() == var_name_lower:
                    return v

    # Not found anywhere in the hierarchy
    return None


def varname_base(var_dict_or_str: Any) -> str | None:
    """Extract base variable name from a variable_name dict or string."""
    if isinstance(var_dict_or_str, dict) and const.KEY_VAR_NAME in var_dict_or_str:
        full = var_dict_or_str[const.KEY_VAR_NAME]
    elif isinstance(var_dict_or_str, str):
        full = var_dict_or_str
    else:
        return None
    base = full.split(".", 1)[0] if full else None
    return base.lower() if base else None


def varname_full(var_dict_or_str: Any) -> str | None:
    """Extract full variable name from a variable_name dict or string."""
    if isinstance(var_dict_or_str, dict) and const.KEY_VAR_NAME in var_dict_or_str:
        return var_dict_or_str[const.KEY_VAR_NAME]
    if isinstance(var_dict_or_str, str):
        return var_dict_or_str
    return None


def find_all_aliases(
    target_var: Variable,
    alias_links: list[tuple[Variable, Variable, str]],
    debug: bool = False,
) -> list[tuple[Variable, str]]:
    """
    Given a target variable and the analyzer's alias links, find all variables
    that are transitively connected to it through parameter mappings.
    Returns list of (Variable, field_prefix_to_prepend) tuples.
    """
    aliases: list[tuple[Variable, str]] = []
    to_visit: list[tuple[Variable, str]] = [(target_var, "")]
    visited: list[tuple[Variable, str]] = []

    while to_visit:
        current, current_prefix = to_visit.pop()

        # Check if already visited using identity
        if any(current is v for v, _ in visited):
            continue

        visited.append((current, current_prefix))
        aliases.append((current, current_prefix))

        # Find all variables linked FROM current (only parent->child direction)
        for parent, child, mapping_name in alias_links:
            if parent is current and not any(child is v for v, _ in visited):
                # When following parent->child link, accumulate the prefix
                if current_prefix and mapping_name:
                    new_prefix = f"{current_prefix}.{mapping_name}"
                elif current_prefix:
                    new_prefix = current_prefix
                else:
                    new_prefix = mapping_name
                to_visit.append((child, new_prefix))

    # Remove the original
    aliases = [(v, p) for v, p in aliases if v is not target_var]
    return aliases


def find_all_aliases_upstream(
    target_var: Variable,
    alias_links: list[tuple[Variable, Variable, str]],
) -> list[tuple[Variable, str]]:
    """
    Find alias sources by walking parent links (child -> parent).
    Returns (parent_var, field_prefix_to_strip) tuples.
    """
    aliases: list[tuple[Variable, str]] = []
    to_visit: list[tuple[Variable, str]] = [(target_var, "")]
    visited: list[tuple[Variable, str]] = []

    while to_visit:
        current, current_prefix = to_visit.pop()

        if any(current is v and current_prefix == p for v, p in visited):
            continue

        visited.append((current, current_prefix))

        for parent, child, mapping_name in alias_links:
            if child is current:
                if current_prefix and mapping_name:
                    new_prefix = f"{mapping_name}.{current_prefix}"
                elif mapping_name:
                    new_prefix = mapping_name
                else:
                    new_prefix = current_prefix
                to_visit.append((parent, new_prefix))

    aliases = [(v, p) for v, p in visited if v is not target_var]
    return aliases
