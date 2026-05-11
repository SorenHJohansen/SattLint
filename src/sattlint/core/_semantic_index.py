"""Internal semantic index construction helpers."""

from __future__ import annotations

from pathlib import Path

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)

from ..call_signatures import CallSignatureOccurrence, resolve_call_signature
from ..grammar import constants as const
from ..reporting.variables_report import VariableIssue
from ..resolution import (
    CanonicalPath,
    CanonicalSymbolTable,
    ContextBuilder,
    SymbolKind,
    TypeGraph,
    decorate_segment,
)
from ..resolution.scope import ScopeContext
from ._semantic_helpers import (
    _cf,
    _format_datatype,
    _resolve_field_datatype,
    _source_file_key,
    _try_resolve_instance_typedef,
)
from ._semantic_snapshot import SymbolDefinition, SymbolReference, _ReferenceOccurrence
from .ast_tools import iter_call_sites, iter_variable_refs


class _SemanticIndexBuilder:
    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
    ):
        self.base_picture = base_picture
        self.type_graph = TypeGraph.from_basepicture(base_picture)
        self.symbol_table = CanonicalSymbolTable()
        self.unavailable_libraries = unavailable_libraries or set()
        self._issues: list[VariableIssue] = []
        self._root_env = {v.name.casefold(): v for v in (base_picture.localvariables or [])}
        self._definitions_by_key: dict[tuple[str, ...], SymbolDefinition] = {}
        self._definitions_in_order: list[SymbolDefinition] = []
        self._references_by_file: dict[str, list[_ReferenceOccurrence]] = {}
        self._references_by_definition_key: dict[tuple[str, ...], list[SymbolReference]] = {}
        self._call_signatures: list[CallSignatureOccurrence] = []
        self._moduletype_index: dict[str, list[ModuleTypeDef]] = {}
        self._datatype_field_definitions = self._build_datatype_field_definitions()
        for moduletype in base_picture.moduletype_defs or []:
            self._moduletype_index.setdefault(moduletype.name.casefold(), []).append(moduletype)
        self.context_builder = ContextBuilder(
            base_picture=base_picture,
            symbol_table=self.symbol_table,
            type_graph=self.type_graph,
            issues=self._issues,
            global_lookup_fn=self._lookup_global_variable,
        )

    def build(
        self,
    ) -> tuple[
        CanonicalSymbolTable,
        TypeGraph,
        tuple[SymbolDefinition, ...],
        dict[tuple[str, ...], SymbolDefinition],
        dict[str, list[ModuleTypeDef]],
        dict[str, tuple[_ReferenceOccurrence, ...]],
        dict[tuple[str, ...], tuple[SymbolReference, ...]],
        tuple[CallSignatureOccurrence, ...],
    ]:
        root_context = self.context_builder.build_for_basepicture()
        self._record_variables(
            self.base_picture.localvariables or [],
            module_path=(self.base_picture.header.name,),
            display_module_path=(decorate_segment(self.base_picture.header.name, "BP"),),
            kind=SymbolKind.LOCAL.value,
            origin_file=self.base_picture.origin_file,
            origin_library=self.base_picture.origin_lib,
        )
        self._record_scope_references(
            self.base_picture.moduledef,
            context=root_context,
            source_file=self.base_picture.origin_file,
            source_library=self.base_picture.origin_lib,
        )
        self._record_call_signatures(
            self.base_picture.moduledef,
            module_path=(self.base_picture.header.name,),
            source_file=self.base_picture.origin_file,
            source_library=self.base_picture.origin_lib,
        )
        self._record_scope_references(
            self.base_picture.modulecode,
            context=root_context,
            source_file=self.base_picture.origin_file,
            source_library=self.base_picture.origin_lib,
        )
        self._record_call_signatures(
            self.base_picture.modulecode,
            module_path=(self.base_picture.header.name,),
            source_file=self.base_picture.origin_file,
            source_library=self.base_picture.origin_lib,
        )
        self._walk_moduletype_defs(
            self.base_picture.moduletype_defs or [],
            parent_context=root_context,
        )
        self._walk_submodules(
            self.base_picture.submodules or [],
            parent_context=root_context,
            module_path=(self.base_picture.header.name,),
            display_module_path=(decorate_segment(self.base_picture.header.name, "BP"),),
            current_origin_file=self.base_picture.origin_file,
            current_origin_library=self.base_picture.origin_lib,
        )
        return (
            self.symbol_table,
            self.type_graph,
            tuple(self._definitions_in_order),
            self._definitions_by_key,
            self._moduletype_index,
            {key: tuple(value) for key, value in self._references_by_file.items()},
            {key: tuple(value) for key, value in self._references_by_definition_key.items()},
            tuple(self._call_signatures),
        )

    def _build_datatype_field_definitions(
        self,
    ) -> dict[tuple[str, tuple[str, ...]], tuple[Variable, str | None, str | None]]:
        datatype_index = {dt.name.casefold(): dt for dt in (self.base_picture.datatype_defs or [])}
        results: dict[tuple[str, tuple[str, ...]], tuple[Variable, str | None, str | None]] = {}

        def walk(
            root_type_name: str,
            current_type_name: str,
            prefix: tuple[str, ...],
            active_types: set[str],
        ) -> None:
            current_key = current_type_name.casefold()
            if current_key in active_types:
                return
            datatype = datatype_index.get(current_key)
            if datatype is None:
                return

            next_active = set(active_types)
            next_active.add(current_key)
            for variable_field in datatype.var_list or []:
                path = (*prefix, variable_field.name)
                results[(root_type_name.casefold(), tuple(_cf(segment) for segment in path))] = (
                    variable_field,
                    datatype.origin_file,
                    datatype.origin_lib,
                )
                if not isinstance(variable_field.datatype, Simple_DataType):
                    walk(root_type_name, str(variable_field.datatype), path, next_active)

        for datatype in self.base_picture.datatype_defs or []:
            walk(datatype.name, datatype.name, (), set())
        return results

    def _lookup_field_definition(
        self,
        root_type: Simple_DataType | str,
        field_path: tuple[str, ...],
    ) -> tuple[Variable, str | None, str | None] | None:
        if isinstance(root_type, Simple_DataType):
            return None
        return self._datatype_field_definitions.get(
            (root_type.casefold(), tuple(_cf(segment) for segment in field_path))
        )

    def _lookup_global_variable(self, name: str | None) -> Variable | None:
        if not name:
            return None
        return self._root_env.get(name.casefold())

    def _record_variables(
        self,
        variables: list[Variable],
        *,
        module_path: tuple[str, ...],
        display_module_path: tuple[str, ...],
        kind: str,
        origin_file: str | None,
        origin_library: str | None,
    ) -> None:
        for variable in variables:
            root_path = CanonicalPath((*module_path, variable.name))
            self._record_definition(
                canonical_path=root_path,
                kind=kind,
                datatype=variable.datatype,
                module_path=module_path,
                display_module_path=display_module_path,
                field_path=None,
                origin_file=origin_file,
                origin_library=origin_library,
                declaration_span=variable.declaration_span,
            )

            for field_segments in self.type_graph.iter_leaf_field_paths(variable.datatype):
                if not field_segments:
                    continue
                field_definition = self._lookup_field_definition(variable.datatype, field_segments)
                self._record_definition(
                    canonical_path=root_path.join(*field_segments),
                    kind="field",
                    datatype=_resolve_field_datatype(self.type_graph, variable.datatype, field_segments),
                    module_path=module_path,
                    display_module_path=display_module_path,
                    field_path=".".join(field_segments),
                    origin_file=field_definition[1] if field_definition else origin_file,
                    origin_library=field_definition[2] if field_definition else origin_library,
                    declaration_span=field_definition[0].declaration_span if field_definition else None,
                )

    def _record_definition(
        self,
        *,
        canonical_path: CanonicalPath,
        kind: str,
        datatype: Simple_DataType | str | None,
        module_path: tuple[str, ...],
        display_module_path: tuple[str, ...],
        field_path: str | None,
        origin_file: str | None,
        origin_library: str | None,
        declaration_span: SourceSpan | None,
    ) -> None:
        definition = SymbolDefinition(
            canonical_path=str(canonical_path),
            kind=kind,
            datatype=_format_datatype(datatype),
            declaration_module_path=module_path,
            display_module_path=display_module_path,
            field_path=field_path,
            source_file=origin_file,
            source_library=origin_library,
            declaration_span=declaration_span,
        )
        self._definitions_by_key[canonical_path.key()] = definition
        self._definitions_in_order.append(definition)

    def _record_scope_references(
        self,
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
        self,
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
        self,
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
        self,
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
                    kind=SymbolKind.LOCAL.value,
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
                kind=SymbolKind.PARAMETER.value,
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
        self,
        moduletype_defs: list[ModuleTypeDef],
        *,
        parent_context: ScopeContext,
    ) -> None:
        for moduletype in moduletype_defs:
            module_path = (moduletype.name,)
            display_module_path = (decorate_segment(moduletype.name, "MT"),)
            synthetic_instance = ModuleTypeInstance(
                header=ModuleHeader(name=moduletype.name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
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
                kind=SymbolKind.PARAMETER.value,
                origin_file=moduletype.origin_file,
                origin_library=moduletype.origin_lib,
            )
            self._record_variables(
                list(moduletype.localvariables or []),
                module_path=module_path,
                display_module_path=display_module_path,
                kind=SymbolKind.LOCAL.value,
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


SemanticIndexBuilder = _SemanticIndexBuilder
