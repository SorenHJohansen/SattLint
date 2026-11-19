"""Internal semantic index construction helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import cast

from sattlint.parser_api import (
    BasePicture,
    ModuleHeader,
    ModuleTypeDef,
    ScalarDatatype,
    SourceSpan,
    Variable,
)

from ..models._variable_issues import VariableIssue
from ..models.project_graph import EMPTY_GRAPHICS_ATTACHMENTS, GraphicsAttachments, program_identity
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
    cf,
    format_datatype,
    resolve_field_datatype,
)
from ._semantic_index_reference_support import SemanticIndexReferenceSupportMixin
from ._semantic_snapshot import ReferenceOccurrence, SymbolDefinition, SymbolReference
from .call_signatures import CallSignatureOccurrence
from .origin import is_root_origin


@dataclass(frozen=True, slots=True)
class SemanticIndex:
    """Typed result of semantic-index construction.

    Replaces the historical 8-element tuple so callers use named attributes
    instead of positional indexing.
    """

    symbol_table: CanonicalSymbolTable
    type_graph: TypeGraph
    definitions: tuple[SymbolDefinition, ...]
    definitions_by_key: dict[tuple[str, ...], SymbolDefinition]
    moduletype_index: dict[str, list[ModuleTypeDef]]
    references_by_file: dict[str, tuple[ReferenceOccurrence, ...]]
    references_by_definition_key: dict[tuple[str, ...], tuple[SymbolReference, ...]]
    call_signatures: tuple[CallSignatureOccurrence, ...]


class _SemanticIndexBuilder(SemanticIndexReferenceSupportMixin):
    def __init__(
        self,
        base_picture: BasePicture,
        root_origin_file: str | None = None,
        root_origin_library: str | None = None,
        unavailable_libraries: set[str] | None = None,
        include_dependency_modules: bool = True,
        graphics_attachments: GraphicsAttachments | None = None,
        build_reference_index: bool = True,
    ):
        self.base_picture = base_picture
        self.graphics_attachments = graphics_attachments or EMPTY_GRAPHICS_ATTACHMENTS
        self.root_origin_file = root_origin_file if root_origin_file is not None else base_picture.origin_file
        self.root_origin_library = root_origin_library if root_origin_library is not None else base_picture.origin_lib
        self.include_dependency_modules = include_dependency_modules
        self.build_reference_index = build_reference_index
        self.type_graph = TypeGraph.from_basepicture(base_picture)
        self.symbol_table = CanonicalSymbolTable()
        self.unavailable_libraries = unavailable_libraries or set()
        self._issues: list[VariableIssue] = []
        self._root_env = {
            v.name.casefold(): v for v in (*(base_picture.moduleparameters or []), *(base_picture.localvariables or []))
        }
        self._definitions_by_key: dict[tuple[str, ...], SymbolDefinition] = {}
        self._references_by_file: dict[str, list[ReferenceOccurrence]] = {}
        self._references_by_definition_key: dict[tuple[str, ...], list[SymbolReference]] = {}
        self._call_signatures: list[CallSignatureOccurrence] = []
        self._moduletype_index: dict[str, list[ModuleTypeDef]] = {}
        self._datatype_field_definitions = self._build_datatype_field_definitions()
        for moduletype in base_picture.moduletype_defs or []:
            self._moduletype_index.setdefault(moduletype.name.casefold(), []).append(moduletype)
        self._known_typedef_ids = {
            id(moduletype) for moduletypes in self._moduletype_index.values() for moduletype in moduletypes
        }
        # Resolution derives the root module path from ``header.name``, which is
        # the literal keyword for a loaded program. Give it a root view named by
        # the program's identity so reference keys match definition keys.
        root_picture = base_picture
        identity = program_identity(base_picture)
        if base_picture.header.name != identity:
            root_picture = replace(base_picture, header=replace(base_picture.header, name=identity))
        self.context_builder = ContextBuilder(
            base_picture=root_picture,
            symbol_table=self.symbol_table,
            type_graph=self.type_graph,
            issues=self._issues,
            global_lookup_fn=self._lookup_global_variable,
            root_library=self.root_origin_library,
        )

    def _is_root_origin(self, origin_file: str | None, origin_lib: str | None) -> bool:
        if self.include_dependency_modules:
            return True
        return is_root_origin(
            origin_file,
            origin_lib,
            root_origin_file=self.root_origin_file,
            root_origin_library=self.root_origin_library,
        )

    def build(
        self,
    ) -> SemanticIndex:
        root_context = self.context_builder.build_for_basepicture()
        # ``header.name`` holds the ``BasePicture`` keyword for a loaded
        # program, so the path root must use the program's identity instead.
        root_name = program_identity(self.base_picture)
        root_module_path = (root_name,)
        root_display_path = (decorate_segment(root_name, "BP"),)
        self._record_variables(
            self.base_picture.moduleparameters or [],
            module_path=root_module_path,
            display_module_path=root_display_path,
            kind=SymbolKind.PARAMETER.value,
            origin_file=self.root_origin_file,
            origin_library=self.root_origin_library,
        )
        self._record_variables(
            self.base_picture.localvariables or [],
            module_path=root_module_path,
            display_module_path=root_display_path,
            kind=SymbolKind.LOCAL.value,
            origin_file=self.root_origin_file,
            origin_library=self.root_origin_library,
        )
        self._record_scope_references(
            self.base_picture.moduledef,
            context=root_context,
            source_file=self.root_origin_file,
            source_library=self.root_origin_library,
        )
        self._record_call_signatures(
            self.base_picture.moduledef,
            module_path=root_module_path,
            source_file=self.root_origin_file,
            source_library=self.root_origin_library,
        )
        self._record_scope_references(
            self.base_picture.modulecode,
            context=root_context,
            source_file=self.root_origin_file,
            source_library=self.root_origin_library,
        )
        self._record_call_signatures(
            self.base_picture.modulecode,
            module_path=root_module_path,
            source_file=self.root_origin_file,
            source_library=self.root_origin_library,
        )
        self._record_graphics_attachments(root_context)
        self._walk_moduletype_defs(
            self.base_picture.moduletype_defs or [],
            parent_context=root_context,
        )
        self._walk_submodules(
            self.base_picture.submodules or [],
            parent_context=root_context,
            module_path=root_module_path,
            display_module_path=root_display_path,
            current_origin_file=self.root_origin_file,
            current_origin_library=self.root_origin_library,
        )
        return SemanticIndex(
            symbol_table=self.symbol_table,
            type_graph=self.type_graph,
            # Derive the ordered list from the keyed map so the two views can
            # never disagree about which definition owns a canonical path.
            definitions=tuple(self._definitions_by_key.values()),
            definitions_by_key=self._definitions_by_key,
            moduletype_index=self._moduletype_index,
            references_by_file={key: tuple(value) for key, value in self._references_by_file.items()},
            references_by_definition_key={
                key: tuple(value) for key, value in self._references_by_definition_key.items()
            },
            call_signatures=tuple(self._call_signatures),
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
                results[(root_type_name.casefold(), tuple(cf(segment) for segment in path))] = (
                    variable_field,
                    datatype.origin_file,
                    datatype.origin_lib,
                )
                if not isinstance(variable_field.datatype, ScalarDatatype):
                    walk(root_type_name, str(variable_field.datatype), path, next_active)

        for datatype in self.base_picture.datatype_defs or []:
            walk(datatype.name, datatype.name, (), set())
        return results

    def _lookup_field_definition(
        self,
        root_type: ScalarDatatype | str,
        field_path: tuple[str, ...],
    ) -> tuple[Variable, str | None, str | None] | None:
        if isinstance(root_type, ScalarDatatype):
            return None
        return self._datatype_field_definitions.get(
            (root_type.casefold(), tuple(cf(segment) for segment in field_path))
        )

    def _record_graphics_attachments(self, context: ScopeContext) -> None:
        """Index references and calls inside graphics bindings.

        The parser walker deliberately excludes graphics binding wrappers from
        AST traversal, so each binding's typed value must be visited directly.
        The binding's own span is inherited by the value, which keeps the
        recorded source location intact.
        """
        source_file = self.graphics_attachments.file_name
        module_path = (program_identity(self.base_picture),)
        for binding in self.graphics_attachments.bindings:
            value = binding.value
            if value is None:
                continue
            self._record_scope_references(
                value,
                context=context,
                source_file=source_file,
                source_library=self.root_origin_library,
            )
            self._record_call_signatures(
                value,
                module_path=module_path,
                source_file=source_file,
                source_library=self.root_origin_library,
            )

    def _lookup_global_variable(self, name: str | None) -> Variable | None:
        if not name:
            return None
        return self._root_env.get(name.casefold())

    @staticmethod
    def _symbol_kind_local() -> str:
        return SymbolKind.LOCAL.value

    @staticmethod
    def _symbol_kind_parameter() -> str:
        return SymbolKind.PARAMETER.value

    @staticmethod
    def _variable_modifiers(variable: Variable) -> tuple[str, ...]:
        modifiers: list[str] = []
        if variable.const:
            modifiers.append("const")
        if variable.state:
            modifiers.append("state")
        if variable.opsave:
            modifiers.append("opsave")
        if variable.secure:
            modifiers.append("secure")
        if variable.global_var:
            modifiers.append("global")
        return tuple(modifiers)

    @staticmethod
    def _initializer_text(value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, int | float):
            return str(value)
        if isinstance(value, str):
            return f'"{value}"'
        if isinstance(value, dict):
            return json.dumps(
                {str(key): item for key, item in cast(dict[object, object], value).items()},
                sort_keys=True,
                ensure_ascii=True,
            )
        return repr(value)

    @staticmethod
    def _synthetic_module_header(name: str) -> ModuleHeader:
        return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))

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
                initializer=self._initializer_text(variable.init_value),
                modifiers=self._variable_modifiers(variable),
            )

            for field_segments in self.type_graph.iter_leaf_field_paths(variable.datatype):
                if not field_segments:
                    continue
                field_definition = self._lookup_field_definition(variable.datatype, field_segments)
                field_variable = field_definition[0] if field_definition else None
                self._record_definition(
                    canonical_path=root_path.join(*field_segments),
                    kind="field",
                    datatype=resolve_field_datatype(self.type_graph, variable.datatype, field_segments),
                    module_path=module_path,
                    display_module_path=display_module_path,
                    field_path=".".join(field_segments),
                    origin_file=field_definition[1] if field_definition else origin_file,
                    origin_library=field_definition[2] if field_definition else origin_library,
                    declaration_span=field_variable.declaration_span if field_variable is not None else None,
                    initializer=self._initializer_text(field_variable.init_value)
                    if field_variable is not None
                    else None,
                    modifiers=self._variable_modifiers(field_variable) if field_variable is not None else (),
                )

    def _record_definition(
        self,
        *,
        canonical_path: CanonicalPath,
        kind: str,
        datatype: ScalarDatatype | str | None,
        module_path: tuple[str, ...],
        display_module_path: tuple[str, ...],
        field_path: str | None,
        origin_file: str | None,
        origin_library: str | None,
        declaration_span: SourceSpan | None,
        initializer: str | None = None,
        modifiers: tuple[str, ...] = (),
    ) -> None:
        definition = SymbolDefinition(
            canonical_path=str(canonical_path),
            kind=kind,
            datatype=format_datatype(datatype),
            declaration_module_path=module_path,
            display_module_path=display_module_path,
            field_path=field_path,
            source_file=origin_file,
            source_library=origin_library,
            declaration_span=declaration_span,
            initializer=initializer,
            modifiers=modifiers,
        )
        self._definitions_by_key[canonical_path.key()] = definition


SemanticIndexBuilder = _SemanticIndexBuilder

__all__ = ["SemanticIndex", "SemanticIndexBuilder"]
