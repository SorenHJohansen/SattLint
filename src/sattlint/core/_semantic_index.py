"""Internal semantic index construction helpers."""

from __future__ import annotations

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleHeader,
    ModuleTypeDef,
    Simple_DataType,
    SourceSpan,
    Variable,
)

from ..call_signatures import CallSignatureOccurrence
from ..reporting.variables_report import VariableIssue
from ..resolution import (
    CanonicalPath,
    CanonicalSymbolTable,
    ContextBuilder,
    SymbolKind,
    TypeGraph,
    decorate_segment,
)
from ._semantic_helpers import (
    cf,
    format_datatype,
    resolve_field_datatype,
)
from ._semantic_index_reference_support import _SemanticIndexReferenceSupportMixin
from ._semantic_snapshot import ReferenceOccurrence, SymbolDefinition, SymbolReference


class _SemanticIndexBuilder(_SemanticIndexReferenceSupportMixin):
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
        self._references_by_file: dict[str, list[ReferenceOccurrence]] = {}
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
        dict[str, tuple[ReferenceOccurrence, ...]],
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
                results[(root_type_name.casefold(), tuple(cf(segment) for segment in path))] = (
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
            (root_type.casefold(), tuple(cf(segment) for segment in field_path))
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
            )

            for field_segments in self.type_graph.iter_leaf_field_paths(variable.datatype):
                if not field_segments:
                    continue
                field_definition = self._lookup_field_definition(variable.datatype, field_segments)
                self._record_definition(
                    canonical_path=root_path.join(*field_segments),
                    kind="field",
                    datatype=resolve_field_datatype(self.type_graph, variable.datatype, field_segments),
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
            datatype=format_datatype(datatype),
            declaration_module_path=module_path,
            display_module_path=display_module_path,
            field_path=field_path,
            source_file=origin_file,
            source_library=origin_library,
            declaration_span=declaration_span,
        )
        self._definitions_by_key[canonical_path.key()] = definition
        self._definitions_in_order.append(definition)


SemanticIndexBuilder = _SemanticIndexBuilder
