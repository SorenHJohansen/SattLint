from __future__ import annotations

# pyright: reportPrivateUsage=false
from typing import Protocol

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SingleModule,
    Variable,
)

from ..casefolding import casefold_key
from ..grammar import constants as const
from ..resolution.common import resolve_moduletype_def_strict, varname_base
from ..resolution.scope import ScopeContext
from .shared.variable_utils import matches_root_origin


class _DependencyUsageScopeState(Protocol):
    bp: BasePicture
    _analyzed_target_is_library: bool
    _unavailable_libraries: set[str]
    _moduleparameter_keys_by_context: dict[int, set[str]]

    def _walk_module_code(
        self,
        modulecode: ModuleCode | None,
        context: ScopeContext,
        module_path: list[str],
    ) -> None: ...

    def _walk_modules(
        self,
        children: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None: ...

    def _walk_typedef(
        self,
        moduletype: ModuleTypeDef,
        context: ScopeContext,
        module_path: list[str],
    ) -> None: ...

    def _build_scope_context(
        self,
        variables: list[Variable],
        *,
        moduleparameters: list[Variable] | None,
        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]],
        module_path: list[str],
        current_library: str | None,
        parent_context: ScopeContext | None,
    ) -> ScopeContext: ...

    def _build_parameter_mappings(
        self,
        mappings: list[ParameterMapping],
        parent_context: ScopeContext,
    ) -> dict[str, tuple[Variable, str, list[str], list[str]]]: ...

    def _walk_moduletype_instance(
        self,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext,
        child_path: list[str],
    ) -> None: ...

    def _is_from_root_origin(
        self,
        origin_file: str | None,
        origin_lib: str | None = None,
    ) -> bool: ...


class _DependencyUsageScopeSupportMixin:
    def _iter_root_typedefs(self: _DependencyUsageScopeState) -> list[ModuleTypeDef]:
        return [
            moduletype
            for moduletype in (self.bp.moduletype_defs or [])
            if self._is_from_root_origin(
                getattr(moduletype, "origin_file", None),
                getattr(moduletype, "origin_lib", None),
            )
        ]

    def _build_scope_context(
        self: _DependencyUsageScopeState,
        variables: list[Variable],
        *,
        moduleparameters: list[Variable] | None,
        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]],
        module_path: list[str],
        current_library: str | None,
        parent_context: ScopeContext | None,
    ) -> ScopeContext:
        context = ScopeContext(
            env={casefold_key(variable.name): variable for variable in variables},
            param_mappings=param_mappings,
            module_path=module_path.copy(),
            display_module_path=module_path.copy(),
            current_library=current_library,
            parent_context=parent_context,
        )
        self._moduleparameter_keys_by_context[id(context)] = {
            casefold_key(variable.name) for variable in (moduleparameters or [])
        }
        return context

    def _build_parameter_mappings(
        self: _DependencyUsageScopeState,
        mappings: list[ParameterMapping],
        parent_context: ScopeContext,
    ) -> dict[str, tuple[Variable, str, list[str], list[str]]]:
        resolved: dict[str, tuple[Variable, str, list[str], list[str]]] = {}
        for mapping in mappings:
            if mapping.is_source_global:
                continue
            target_name = varname_base(mapping.target)
            if not target_name:
                continue
            if isinstance(mapping.source, dict) and const.KEY_VAR_NAME in mapping.source:
                full_source = mapping.source[const.KEY_VAR_NAME]
            elif isinstance(mapping.source, str):
                full_source = mapping.source
            else:
                continue
            source_var, field_prefix, decl_path, decl_display_path = parent_context.resolve_variable(str(full_source))
            if source_var is None:
                continue
            resolved[target_name.casefold()] = (
                source_var,
                field_prefix,
                decl_path,
                decl_display_path,
            )
        return resolved

    def _walk_modules(
        self: _DependencyUsageScopeState,
        children: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None:
        for child in children:
            child_path = [*parent_path, child.header.name]
            if isinstance(child, SingleModule):
                child_context = self._build_scope_context(
                    [*(child.moduleparameters or []), *(child.localvariables or [])],
                    moduleparameters=child.moduleparameters or [],
                    param_mappings=self._build_parameter_mappings(child.parametermappings or [], parent_context),
                    module_path=child_path,
                    current_library=parent_context.current_library,
                    parent_context=parent_context,
                )
                self._walk_module_code(child.modulecode, child_context, child_path)
                self._walk_modules(child.submodules or [], child_context, child_path)
                continue

            if isinstance(child, FrameModule):
                frame_context = ScopeContext(
                    env=parent_context.env,
                    param_mappings=parent_context.param_mappings,
                    module_path=child_path.copy(),
                    display_module_path=child_path.copy(),
                    current_library=parent_context.current_library,
                    parent_context=parent_context,
                )
                self._walk_module_code(child.modulecode, frame_context, child_path)
                self._walk_modules(child.submodules or [], frame_context, child_path)
                continue

            self._walk_moduletype_instance(child, parent_context, child_path)

    def _walk_moduletype_instance(
        self: _DependencyUsageScopeState,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext,
        child_path: list[str],
    ) -> None:
        try:
            moduletype = resolve_moduletype_def_strict(
                self.bp,
                instance.moduletype_name,
                current_library=parent_context.current_library,
                unavailable_libraries=self._unavailable_libraries,
            )
        except ValueError:
            return

        if not self._is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        ):
            return

        typedef_context = self._build_scope_context(
            [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])],
            moduleparameters=moduletype.moduleparameters or [],
            param_mappings=self._build_parameter_mappings(instance.parametermappings or [], parent_context),
            module_path=child_path,
            current_library=moduletype.origin_lib or parent_context.current_library,
            parent_context=parent_context,
        )
        self._walk_typedef(moduletype, typedef_context, child_path)

    def _is_from_root_origin(
        self: _DependencyUsageScopeState,
        origin_file: str | None,
        origin_lib: str | None = None,
    ) -> bool:
        return matches_root_origin(
            origin_file,
            getattr(self.bp, "origin_file", None),
            analyzed_target_is_library=self._analyzed_target_is_library,
            origin_lib=origin_lib,
            root_origin_lib=getattr(self.bp, "origin_lib", None),
        )


__all__ = ["_DependencyUsageScopeSupportMixin"]
