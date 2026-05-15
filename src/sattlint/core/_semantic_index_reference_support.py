from __future__ import annotations

from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import FrameModule, ModuleTypeDef, ModuleTypeInstance, SingleModule, SourceSpan

from ..call_signatures import CallSignatureOccurrence, resolve_call_signature
from ..grammar import constants as const
from ..resolution import CanonicalPath, decorate_segment
from ..resolution.scope import ScopeContext
from ._semantic_helpers import _source_file_key, _try_resolve_instance_typedef
from ._semantic_snapshot import _ReferenceOccurrence
from .ast_tools import iter_call_sites, iter_variable_refs


class _SemanticIndexReferenceSupportMixin:
    def _record_scope_references(
        self: Any,
        node: object,
        *,
        context: ScopeContext,
        source_file: str | None,
        source_library: str | None,
    ) -> None:
        file_key = _source_file_key(source_file)
        if file_key is None or node is None:
            return

        source_file_name = Path(str(source_file)).name if source_file is not None else None

        for ref in iter_variable_refs(node, key_name=const.KEY_VAR_NAME):
            full_name = ref.get(const.KEY_VAR_NAME)
            span = ref.get("span")
            if not isinstance(full_name, str) or not isinstance(span, SourceSpan):
                continue

            resolved_var, field_path, declaration_path, _ = context.resolve_variable(full_name)
            if resolved_var is None:
                continue

            reference_segments = tuple(segment for segment in full_name.split(".") if segment)
            if not reference_segments:
                continue

            resolved_segments = [segment for segment in field_path.split(".") if segment] if field_path else []
            definition_keys = [CanonicalPath((*declaration_path, resolved_var.name)).key()]
            for index in range(1, min(len(reference_segments), len(resolved_segments) + 1)):
                definition_keys.append(
                    CanonicalPath((*declaration_path, resolved_var.name, *resolved_segments[:index])).key()
                )
            if len(definition_keys) < len(reference_segments):
                definition_keys.extend([definition_keys[-1]] * (len(reference_segments) - len(definition_keys)))

            state = ref.get("state")
            text = full_name if not state else f"{full_name}:{state}"
            occurrence = _ReferenceOccurrence(
                line=span.line,
                column=span.column,
                text=text,
                source_file=source_file_name,
                source_library=source_library,
                segment_texts=reference_segments,
                definition_keys=tuple(definition_keys),
            )
            self._references_by_file.setdefault(file_key, []).append(occurrence)

            recorded_keys: set[tuple[str, ...]] = set()
            for definition_key in occurrence.definition_keys:
                if definition_key in recorded_keys:
                    continue
                recorded_keys.add(definition_key)
                symbol_reference = occurrence.reference_for_definition_key(definition_key)
                if symbol_reference is None:
                    continue
                self._references_by_definition_key.setdefault(definition_key, []).append(symbol_reference)

    def _record_call_signatures(
        self: Any,
        node: object,
        *,
        module_path: tuple[str, ...],
        source_file: str | None,
        source_library: str | None,
    ) -> None:
        source_file_name = Path(str(source_file)).name if source_file is not None else None
        for call_kind, call_name, _args in iter_call_sites(node):
            signature = resolve_call_signature(call_name)
            if signature is None:
                continue
            self._call_signatures.append(
                CallSignatureOccurrence(
                    name=call_name,
                    call_kind=call_kind,
                    module_path=module_path,
                    source_file=source_file_name,
                    source_library=source_library,
                    signature=signature,
                )
            )

    def _repath_context(
        self: Any,
        context: ScopeContext,
        module_path: tuple[str, ...],
        display_module_path: tuple[str, ...],
    ) -> ScopeContext:
        return ScopeContext(
            env=context.env,
            param_mappings=context.param_mappings,
            module_path=list(module_path),
            display_module_path=list(display_module_path),
            current_library=context.current_library,
            parent_context=context.parent_context,
        )

    def _walk_submodules(
        self: Any,
        modules: list[SingleModule | FrameModule | ModuleTypeInstance],
        *,
        parent_context: ScopeContext,
        module_path: tuple[str, ...],
        display_module_path: tuple[str, ...],
        current_origin_file: str | None,
        current_origin_library: str | None,
    ) -> None:
        for module in modules:
            if isinstance(module, SingleModule):
                child_module_path = (*module_path, module.header.name)
                child_display_path = (*display_module_path, decorate_segment(module.header.name, "SM"))
                child_context = self.context_builder.build_for_single(
                    module,
                    parent_context,
                    module_path=list(child_module_path),
                    display_module_path=list(child_display_path),
                )
                self._record_variables(
                    list(module.moduleparameters or []) + list(module.localvariables or []),
                    module_path=child_module_path,
                    display_module_path=child_display_path,
                    kind=self._symbol_kind_local(),
                    origin_file=current_origin_file,
                    origin_library=current_origin_library,
                )
                self._record_scope_references(
                    module.moduledef,
                    context=child_context,
                    source_file=current_origin_file,
                    source_library=current_origin_library,
                )
                self._record_call_signatures(
                    module.moduledef,
                    module_path=child_module_path,
                    source_file=current_origin_file,
                    source_library=current_origin_library,
                )
                self._record_scope_references(
                    module.modulecode,
                    context=child_context,
                    source_file=current_origin_file,
                    source_library=current_origin_library,
                )
                self._record_call_signatures(
                    module.modulecode,
                    module_path=child_module_path,
                    source_file=current_origin_file,
                    source_library=current_origin_library,
                )
                self._walk_submodules(
                    module.submodules or [],
                    parent_context=child_context,
                    module_path=child_module_path,
                    display_module_path=child_display_path,
                    current_origin_file=current_origin_file,
                    current_origin_library=current_origin_library,
                )
                continue

            if isinstance(module, FrameModule):
                child_module_path = (*module_path, module.header.name)
                child_display_path = (*display_module_path, decorate_segment(module.header.name, "FM"))
                frame_context = self._repath_context(
                    parent_context,
                    module_path=child_module_path,
                    display_module_path=child_display_path,
                )
                self._walk_submodules(
                    module.submodules or [],
                    parent_context=frame_context,
                    module_path=child_module_path,
                    display_module_path=child_display_path,
                    current_origin_file=current_origin_file,
                    current_origin_library=current_origin_library,
                )
                continue

            child_module_path = (*module_path, module.header.name)
            child_display_path = (
                *display_module_path,
                decorate_segment(module.header.name, "MT", module.moduletype_name),
            )
            moduletype = _try_resolve_instance_typedef(
                self.base_picture,
                module,
                self._moduletype_index,
                self.unavailable_libraries,
                current_library=parent_context.current_library,
            )
            if moduletype is None:
                continue
            typedef_context = self.context_builder.build_for_typedef(
                moduletype,
                module,
                parent_context=parent_context,
                module_path=list(child_module_path),
                display_module_path=list(child_display_path),
            )
            self._record_variables(
                list(moduletype.moduleparameters or []) + list(moduletype.localvariables or []),
                module_path=child_module_path,
                display_module_path=child_display_path,
                kind=self._symbol_kind_parameter(),
                origin_file=moduletype.origin_file,
                origin_library=moduletype.origin_lib,
            )
            self._record_scope_references(
                moduletype.moduledef,
                context=typedef_context,
                source_file=moduletype.origin_file,
                source_library=moduletype.origin_lib,
            )
            self._record_call_signatures(
                moduletype.moduledef,
                module_path=child_module_path,
                source_file=moduletype.origin_file,
                source_library=moduletype.origin_lib,
            )
            self._record_scope_references(
                moduletype.modulecode,
                context=typedef_context,
                source_file=moduletype.origin_file,
                source_library=moduletype.origin_lib,
            )
            self._record_call_signatures(
                moduletype.modulecode,
                module_path=child_module_path,
                source_file=moduletype.origin_file,
                source_library=moduletype.origin_lib,
            )
            self._walk_submodules(
                moduletype.submodules or [],
                parent_context=typedef_context,
                module_path=child_module_path,
                display_module_path=child_display_path,
                current_origin_file=moduletype.origin_file,
                current_origin_library=moduletype.origin_lib,
            )

    def _walk_moduletype_defs(
        self: Any,
        moduletype_defs: list[ModuleTypeDef],
        *,
        parent_context: ScopeContext,
    ) -> None:
        for moduletype in moduletype_defs:
            module_path = (moduletype.name,)
            display_module_path = (decorate_segment(moduletype.name, "MT"),)
            synthetic_instance = ModuleTypeInstance(
                header=self._synthetic_module_header(moduletype.name),
                moduletype_name=moduletype.name,
            )
            typedef_context = self.context_builder.build_for_typedef(
                moduletype,
                synthetic_instance,
                parent_context=parent_context,
                module_path=list(module_path),
                display_module_path=list(display_module_path),
            )
            self._record_variables(
                list(moduletype.moduleparameters or []),
                module_path=module_path,
                display_module_path=display_module_path,
                kind=self._symbol_kind_parameter(),
                origin_file=moduletype.origin_file,
                origin_library=moduletype.origin_lib,
            )
            self._record_variables(
                list(moduletype.localvariables or []),
                module_path=module_path,
                display_module_path=display_module_path,
                kind=self._symbol_kind_local(),
                origin_file=moduletype.origin_file,
                origin_library=moduletype.origin_lib,
            )
            self._record_scope_references(
                moduletype.moduledef,
                context=typedef_context,
                source_file=moduletype.origin_file,
                source_library=moduletype.origin_lib,
            )
            self._record_call_signatures(
                moduletype.moduledef,
                module_path=module_path,
                source_file=moduletype.origin_file,
                source_library=moduletype.origin_lib,
            )
            self._record_scope_references(
                moduletype.modulecode,
                context=typedef_context,
                source_file=moduletype.origin_file,
                source_library=moduletype.origin_lib,
            )
            self._record_call_signatures(
                moduletype.modulecode,
                module_path=module_path,
                source_file=moduletype.origin_file,
                source_library=moduletype.origin_lib,
            )
            self._walk_submodules(
                moduletype.submodules or [],
                parent_context=typedef_context,
                module_path=module_path,
                display_module_path=display_module_path,
                current_origin_file=moduletype.origin_file,
                current_origin_library=moduletype.origin_lib,
            )


__all__ = ["_SemanticIndexReferenceSupportMixin"]
