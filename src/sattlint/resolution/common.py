from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)

from . import _alias_utils as alias_utils
from . import _moduletype_resolution as _moduletype_resolution
from . import paths as _paths

ResolvableModule = SingleModule | FrameModule | ModuleTypeInstance
ModuleLookupResult = ModuleTypeDef | ResolvableModule
find_all_aliases = alias_utils.find_all_aliases
find_all_aliases_upstream = alias_utils.find_all_aliases_upstream
varname_base = alias_utils.varname_base
varname_full = alias_utils.varname_full
ResolvedModulePath = _moduletype_resolution.ResolvedModulePath
dedupe_moduletype_defs = _moduletype_resolution.dedupe_moduletype_defs
format_moduletype_label = _moduletype_resolution.format_moduletype_label
narrow_matches_by_source_preference = _moduletype_resolution.narrow_matches_by_source_preference
preferred_source_extensions = _moduletype_resolution.preferred_source_extensions
resolve_module_by_strict_path = _moduletype_resolution.resolve_module_by_strict_path
resolve_moduletype_def_strict = _moduletype_resolution.resolve_moduletype_def_strict
select_moduletype_def_strict = _moduletype_resolution.select_moduletype_def_strict


def path_startswith_casefold(location: list[str], prefix: list[str]) -> bool:
    return _paths.path_startswith_casefold(location, prefix)


def is_external_to_module(location_path: list[str], module_path: list[str]) -> bool:
    return _paths.is_external_to_module(location_path, module_path)


def find_module_by_name(bp: BasePicture, name: str) -> ModuleLookupResult | None:
    """Recursively find a module by name in the AST."""
    name_lower = name.casefold()

    # First check if it's a ModuleTypeDef
    for mt in bp.moduletype_defs or []:
        if mt.name.casefold() == name_lower:
            return mt

    # Then search in submodules (instances)
    def search(modules: list[ResolvableModule] | None) -> ModuleLookupResult | None:
        for mod in modules or []:
            if mod.header.name.casefold() == name_lower:
                return mod
            if isinstance(mod, SingleModule | FrameModule):
                result = search(mod.submodules)
                if result:
                    return result
        return None

    return search(bp.submodules)


def get_module_path(bp: BasePicture, target_module: ModuleLookupResult) -> list[str]:
    """Get the full path to a module."""

    # Check if it's a ModuleTypeDef
    if isinstance(target_module, ModuleTypeDef):
        return [bp.header.name, f"TypeDef:{target_module.name}"]

    # Otherwise search in submodules
    def search(modules: list[ResolvableModule] | None, path: list[str]) -> list[str] | None:
        for mod in modules or []:
            current_path = [*path, mod.header.name]
            if mod is target_module:
                return current_path
            if isinstance(mod, SingleModule | FrameModule):
                result = search(mod.submodules, current_path)
                if result:
                    return result
        return None

    result = search(bp.submodules, [bp.header.name])
    return result or []
