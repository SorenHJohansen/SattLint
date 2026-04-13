"""Editor-facing workspace discovery and semantic query helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .analyzers.context_builder import ContextBuilder
from .analyzers.variables import VariablesAnalyzer
from .engine import CodeMode, SattLineProjectLoader, merge_project_basepicture
from .grammar import constants as const
from .models.ast_model import (
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
from .models.project_graph import ProjectGraph
from .reporting.variables_report import VariableIssue
from .resolution import CanonicalPath, CanonicalSymbolTable, SymbolKind, TypeGraph, decorate_segment
from .resolution.common import resolve_moduletype_def_strict, resolve_module_by_strict_path
from .resolution.scope import ScopeContext
from sattline_parser import parse_source_text as parser_core_parse_source_text

_SOURCE_EXTENSIONS = {".s", ".x", ".l", ".z"}
_PROGRAM_EXTENSIONS = {".s", ".x"}
_DEPENDENCY_EXTENSIONS = {".l", ".z"}
_IGNORED_DISCOVERY_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    ".pytest_cache",
    ".mypy_cache",
}


def _cf(value: str) -> str:
    return value.casefold()


def _format_datatype(datatype: Simple_DataType | str | None) -> str | None:
    if datatype is None:
        return None
    if isinstance(datatype, Simple_DataType):
        return datatype.value
    return str(datatype)


def _path_key(path: Path) -> str:
    return path.as_posix().casefold()


def _path_startswith(path: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    if len(prefix) > len(path):
        return False
    return tuple(_cf(part) for part in path[: len(prefix)]) == tuple(
        _cf(part) for part in prefix
    )


def _resolve_field_datatype(
    type_graph: TypeGraph,
    root_type: Simple_DataType | str,
    field_path: tuple[str, ...],
) -> Simple_DataType | str | None:
    current: Simple_DataType | str | None = root_type
    for segment in field_path:
        if current is None or isinstance(current, Simple_DataType):
            return current
        field = type_graph.field(str(current), segment)
        if field is None:
            return None
        current = field.datatype
    return current


def _normalize_mode(mode: CodeMode | str) -> CodeMode:
    if isinstance(mode, CodeMode):
        return mode
    return CodeMode(str(mode).strip().lower())


def _source_file_key(value: Path | str | None) -> str | None:
    if value is None:
        return None
    return Path(str(value)).name.casefold()


def _identifier_contains_column(start_column: int, text: str, column: int) -> bool:
    if start_column <= 0 or not text:
        return False
    return start_column <= column <= (start_column + len(text) - 1)


def _iter_variable_refs(node: object):
    if isinstance(node, dict) and const.KEY_VAR_NAME in node:
        yield node
        return

    if isinstance(node, dict):
        for value in node.values():
            yield from _iter_variable_refs(value)
        return

    if isinstance(node, tuple):
        for item in node:
            yield from _iter_variable_refs(item)
        return

    if isinstance(node, list):
        for item in node:
            yield from _iter_variable_refs(item)
        return

    children = getattr(node, "children", None)
    if children is not None:
        for child in children:
            yield from _iter_variable_refs(child)
        return

    node_dict = getattr(node, "__dict__", None)
    if node_dict is not None:
        for value in node_dict.values():
            yield from _iter_variable_refs(value)


@dataclass(frozen=True, slots=True)
class WorkspaceSourceDiscovery:
    workspace_root: Path
    source_dirs: tuple[Path, ...]
    program_files: tuple[Path, ...]
    dependency_files: tuple[Path, ...]
    abb_lib_dir: Path | None = None

    def other_lib_dirs_for(self, entry_file: Path) -> tuple[Path, ...]:
        entry_parent = entry_file.resolve().parent
        abb_dir = self.abb_lib_dir.resolve() if self.abb_lib_dir else None
        results: list[Path] = []
        for source_dir in self.source_dirs:
            resolved = source_dir.resolve()
            if resolved == entry_parent:
                continue
            if abb_dir is not None and resolved == abb_dir:
                continue
            results.append(source_dir)
        return tuple(results)


@dataclass(frozen=True, slots=True)
class SymbolDefinition:
    canonical_path: str
    kind: str
    datatype: str | None
    declaration_module_path: tuple[str, ...]
    display_module_path: tuple[str, ...]
    field_path: str | None = None
    source_file: str | None = None
    source_library: str | None = None
    declaration_span: SourceSpan | None = None


@dataclass(frozen=True, slots=True)
class _ReferenceOccurrence:
    line: int
    column: int
    text: str
    root_definition_key: tuple[str, ...]
    resolved_definition_key: tuple[str, ...]

    def matches(self, line: int, column: int) -> bool:
        return self.line == line and _identifier_contains_column(self.column, self.text, column)

    def definition_key_for_column(self, column: int) -> tuple[str, ...]:
        base_text = self.text.split(".", 1)[0]
        if column <= (self.column + len(base_text) - 1):
            return self.root_definition_key
        return self.resolved_definition_key


@dataclass(frozen=True, slots=True)
class CompletionItem:
    label: str
    kind: str
    detail: str | None = None
    declaration_module_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SemanticSnapshot:
    workspace_root: Path
    entry_file: Path
    discovery: WorkspaceSourceDiscovery
    base_picture: BasePicture
    project_graph: ProjectGraph
    symbol_table: CanonicalSymbolTable
    type_graph: TypeGraph
    definitions: tuple[SymbolDefinition, ...]
    diagnostics: tuple[VariableIssue, ...] = ()
    _definitions_by_key: dict[tuple[str, ...], SymbolDefinition] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
    _moduletype_index: dict[str, list[ModuleTypeDef]] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
    _references_by_file: dict[str, tuple[_ReferenceOccurrence, ...]] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    def list_symbols(self, query: str = "", *, roots_only: bool = False, limit: int | None = None) -> list[SymbolDefinition]:
        needle = query.strip().casefold()
        matches: list[SymbolDefinition] = []
        for definition in self.definitions:
            if roots_only and definition.field_path is not None:
                continue
            if needle and needle not in definition.canonical_path.casefold():
                continue
            matches.append(definition)
        if limit is not None:
            return matches[:limit]
        return matches

    def find_definitions(self, query: str, *, limit: int | None = None) -> list[SymbolDefinition]:
        raw = query.strip()
        if not raw:
            return []

        segments = tuple(segment for segment in raw.split(".") if segment)
        key = tuple(_cf(segment) for segment in segments)

        direct = self._definitions_by_key.get(key)
        if direct is not None:
            return [direct]

        matches: list[tuple[int, int, SymbolDefinition]] = []
        for definition in self.definitions:
            definition_key = tuple(_cf(segment) for segment in definition.canonical_path.split("."))
            if segments and definition_key[-len(key) :] == key:
                matches.append((len(key), len(definition_key), definition))
            elif len(key) == 1 and definition_key[-1] == key[0]:
                matches.append((1, len(definition_key), definition))

        matches.sort(key=lambda item: (-item[0], item[1], item[2].canonical_path.casefold()))
        results = [item[2] for item in matches]
        if limit is not None:
            return results[:limit]
        return results

    def find_definitions_at(
        self,
        source_file: Path | str,
        line: int,
        column: int,
    ) -> list[SymbolDefinition]:
        file_key = _source_file_key(source_file)
        if file_key is None:
            return []

        matches: list[SymbolDefinition] = []
        seen: set[tuple[str, ...]] = set()
        for occurrence in self._references_by_file.get(file_key, ()):
            if not occurrence.matches(line, column):
                continue
            definition_key = occurrence.definition_key_for_column(column)
            definition = self._definitions_by_key.get(definition_key)
            if definition is None and definition_key != occurrence.root_definition_key:
                definition = self._definitions_by_key.get(occurrence.root_definition_key)
                definition_key = occurrence.root_definition_key
            if definition is None or definition_key in seen:
                continue
            seen.add(definition_key)
            matches.append(definition)
        return matches

    def complete(
        self,
        prefix: str = "",
        *,
        module_path: str | None = None,
        limit: int | None = None,
    ) -> list[CompletionItem]:
        prefix_cf = prefix.casefold()
        if module_path:
            try:
                resolved = resolve_module_by_strict_path(
                    self.base_picture,
                    module_path,
                    moduletype_index=self._moduletype_index,
                )
                visible_path = tuple(resolved.path)
                current_node: Any | None = resolved.node
            except ValueError:
                visible_path = tuple(segment for segment in module_path.split(".") if segment)
                if visible_path and _cf(visible_path[0]) == _cf(self.base_picture.header.name):
                    visible_path = visible_path[1:]
                current_node = None
        else:
            visible_path = (self.base_picture.header.name,)
            current_node = self.base_picture

        items_by_label: dict[str, CompletionItem] = {}

        for definition in self.definitions:
            if definition.field_path is not None:
                continue
            if not _path_startswith(visible_path, definition.declaration_module_path):
                continue
            if prefix_cf and not definition.canonical_path.split(".")[-1].casefold().startswith(prefix_cf):
                continue

            label = definition.canonical_path.split(".")[-1]
            existing = items_by_label.get(label.casefold())
            current = CompletionItem(
                label=label,
                kind=definition.kind,
                detail=definition.datatype,
                declaration_module_path=definition.declaration_module_path,
            )
            if existing is None or len(current.declaration_module_path) > len(existing.declaration_module_path):
                items_by_label[label.casefold()] = current

        if current_node is not None:
            for child_name, child_kind in _child_module_items(
                self.base_picture,
                current_node,
                self._moduletype_index,
                self.project_graph.unavailable_libraries,
            ):
                if prefix_cf and not child_name.casefold().startswith(prefix_cf):
                    continue
                items_by_label.setdefault(
                    child_name.casefold(),
                    CompletionItem(label=child_name, kind=child_kind, detail=None),
                )

        items = sorted(
            items_by_label.values(),
            key=lambda item: (item.label.casefold(), item.kind),
        )
        if limit is not None:
            return items[:limit]
        return items


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
        )
        self._record_scope_references(
            self.base_picture.modulecode,
            context=root_context,
            source_file=self.base_picture.origin_file,
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
        )

    def _build_datatype_field_definitions(
        self,
    ) -> dict[tuple[str, tuple[str, ...]], tuple[Variable, str | None, str | None]]:
        datatype_index = {
            dt.name.casefold(): dt for dt in (self.base_picture.datatype_defs or [])
        }
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
            for field in datatype.var_list or []:
                path = prefix + (field.name,)
                results[(root_type_name.casefold(), tuple(_cf(segment) for segment in path))] = (
                    field,
                    datatype.origin_file,
                    datatype.origin_lib,
                )
                if not isinstance(field.datatype, Simple_DataType):
                    walk(root_type_name, str(field.datatype), path, next_active)

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
            root_path = CanonicalPath(module_path + (variable.name,))
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
    ) -> None:
        file_key = _source_file_key(source_file)
        if file_key is None or node is None:
            return

        for ref in _iter_variable_refs(node):
            full_name = ref.get(const.KEY_VAR_NAME)
            span = ref.get("span")
            if not isinstance(full_name, str) or not isinstance(span, SourceSpan):
                continue

            resolved_var, field_path, declaration_path, _ = context.resolve_variable(full_name)
            if resolved_var is None:
                continue

            root_key = CanonicalPath(tuple(declaration_path + [resolved_var.name])).key()
            resolved_key = root_key
            if field_path:
                resolved_key = CanonicalPath(
                    tuple(declaration_path + [resolved_var.name] + [segment for segment in field_path.split(".") if segment])
                ).key()

            state = ref.get("state")
            text = full_name if not state else f"{full_name}:{state}"
            self._references_by_file.setdefault(file_key, []).append(
                _ReferenceOccurrence(
                    line=span.line,
                    column=span.column,
                    text=text,
                    root_definition_key=root_key,
                    resolved_definition_key=resolved_key,
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
                child_module_path = module_path + (module.header.name,)
                child_display_path = display_module_path + (
                    decorate_segment(module.header.name, "SM"),
                )
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
                )
                self._record_scope_references(
                    module.modulecode,
                    context=child_context,
                    source_file=current_origin_file,
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
                child_module_path = module_path + (module.header.name,)
                child_display_path = display_module_path + (
                    decorate_segment(module.header.name, "FM"),
                )
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

            child_module_path = module_path + (module.header.name,)
            child_display_path = display_module_path + (
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
            )
            self._record_scope_references(
                moduletype.modulecode,
                context=typedef_context,
                source_file=moduletype.origin_file,
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
            )
            self._record_scope_references(
                moduletype.modulecode,
                context=typedef_context,
                source_file=moduletype.origin_file,
            )
            self._walk_submodules(
                moduletype.submodules or [],
                parent_context=typedef_context,
                module_path=module_path,
                display_module_path=display_module_path,
                current_origin_file=moduletype.origin_file,
                current_origin_library=moduletype.origin_lib,
            )


def _child_module_items(
    base_picture: BasePicture,
    node: BasePicture | SingleModule | FrameModule | ModuleTypeInstance | ModuleTypeDef,
    moduletype_index: dict[str, list[ModuleTypeDef]],
    unavailable_libraries: set[str],
) -> list[tuple[str, str]]:
    if isinstance(node, BasePicture):
        children = list(node.submodules or [])
    elif isinstance(node, (SingleModule, FrameModule, ModuleTypeDef)):
        children = list(node.submodules or [])
    elif isinstance(node, ModuleTypeInstance):
        typedef = _try_resolve_instance_typedef(
            base_picture,
            node,
            moduletype_index,
            unavailable_libraries,
        )
        children = list(typedef.submodules or []) if typedef is not None else []
    else:
        children = []

    items: list[tuple[str, str]] = []
    for child in children:
        if isinstance(child, SingleModule):
            items.append((child.header.name, "module"))
        elif isinstance(child, FrameModule):
            items.append((child.header.name, "frame"))
        elif isinstance(child, ModuleTypeInstance):
            items.append((child.header.name, "moduletype-instance"))
    return items


def _resolve_instance_typedef(
    base_picture: BasePicture,
    instance: ModuleTypeInstance,
    moduletype_index: dict[str, list[ModuleTypeDef]],
    unavailable_libraries: set[str],
    current_library: str | None = None,
) -> ModuleTypeDef:
    matches = moduletype_index.get(instance.moduletype_name.casefold(), [])
    if len(matches) == 1:
        return matches[0]
    return resolve_moduletype_def_strict(
        base_picture,
        instance.moduletype_name,
        current_library=current_library,
        unavailable_libraries=unavailable_libraries,
    )


def _try_resolve_instance_typedef(
    base_picture: BasePicture,
    instance: ModuleTypeInstance,
    moduletype_index: dict[str, list[ModuleTypeDef]],
    unavailable_libraries: set[str],
    current_library: str | None = None,
) -> ModuleTypeDef | None:
    try:
        return _resolve_instance_typedef(
            base_picture,
            instance,
            moduletype_index,
            unavailable_libraries,
            current_library=current_library,
        )
    except ValueError:
        return None


def discover_workspace_sources(workspace_root: Path) -> WorkspaceSourceDiscovery:
    root = Path(workspace_root).resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Workspace root does not exist: {root}")

    source_dirs: set[Path] = set()
    program_files: list[Path] = []
    dependency_files: list[Path] = []

    for current_root, dir_names, file_names in os.walk(root):
        dir_names[:] = [
            name
            for name in dir_names
            if name.casefold() not in _IGNORED_DISCOVERY_DIRS
        ]

        current_dir = Path(current_root)
        for file_name in file_names:
            path = current_dir / file_name
            suffix = path.suffix.lower()
            if suffix not in _SOURCE_EXTENSIONS:
                continue
            source_dirs.add(current_dir)
            if suffix in _PROGRAM_EXTENSIONS:
                program_files.append(path)
            elif suffix in _DEPENDENCY_EXTENSIONS:
                dependency_files.append(path)

    abb_candidates = sorted(
        (directory for directory in source_dirs if "abb" in directory.name.casefold()),
        key=_path_key,
    )
    abb_lib_dir = abb_candidates[0] if abb_candidates else None

    return WorkspaceSourceDiscovery(
        workspace_root=root,
        source_dirs=tuple(sorted(source_dirs, key=_path_key)),
        program_files=tuple(sorted(program_files, key=_path_key)),
        dependency_files=tuple(sorted(dependency_files, key=_path_key)),
        abb_lib_dir=abb_lib_dir,
    )


def _single_entry_discovery(entry_path: Path, workspace_root: Path) -> WorkspaceSourceDiscovery:
    suffix = entry_path.suffix.lower()
    program_files = (entry_path,) if suffix in _PROGRAM_EXTENSIONS else ()
    dependency_files = (entry_path,) if suffix in _DEPENDENCY_EXTENSIONS else ()
    return WorkspaceSourceDiscovery(
        workspace_root=workspace_root,
        source_dirs=(entry_path.parent,),
        program_files=program_files,
        dependency_files=dependency_files,
        abb_lib_dir=None,
    )


def _build_semantic_snapshot(
    base_picture: BasePicture,
    *,
    entry_path: Path,
    workspace_root: Path,
    discovery: WorkspaceSourceDiscovery,
    project_graph: ProjectGraph,
    collect_variable_diagnostics: bool,
    debug: bool,
) -> SemanticSnapshot:
    builder = _SemanticIndexBuilder(
        base_picture,
        unavailable_libraries=project_graph.unavailable_libraries,
    )
    (
        symbol_table,
        type_graph,
        definitions,
        definitions_by_key,
        moduletype_index,
        references_by_file,
    ) = builder.build()

    diagnostics: tuple[VariableIssue, ...] = ()
    if collect_variable_diagnostics:
        analyzer = VariablesAnalyzer(
            base_picture,
            debug=debug,
            fail_loudly=False,
            unavailable_libraries=project_graph.unavailable_libraries,
        )
        diagnostics = tuple(analyzer.run())

    return SemanticSnapshot(
        workspace_root=workspace_root,
        entry_file=entry_path,
        discovery=discovery,
        base_picture=base_picture,
        project_graph=project_graph,
        symbol_table=symbol_table,
        type_graph=type_graph,
        definitions=definitions,
        diagnostics=diagnostics,
        _definitions_by_key=definitions_by_key,
        _moduletype_index=moduletype_index,
        _references_by_file=references_by_file,
    )


def load_source_snapshot(
    source_file: Path,
    source_text: str,
    *,
    workspace_root: Path | None = None,
    collect_variable_diagnostics: bool = False,
    debug: bool = False,
) -> SemanticSnapshot:
    base_picture = parser_core_parse_source_text(source_text, debug=(print if debug else None))
    return build_source_snapshot_from_basepicture(
        base_picture,
        source_file,
        workspace_root=workspace_root,
        collect_variable_diagnostics=collect_variable_diagnostics,
        debug=debug,
    )


def build_source_snapshot_from_basepicture(
    base_picture: BasePicture,
    source_file: Path,
    *,
    workspace_root: Path | None = None,
    collect_variable_diagnostics: bool = False,
    debug: bool = False,
) -> SemanticSnapshot:
    entry_path = Path(source_file).resolve()
    root = Path(workspace_root).resolve() if workspace_root else entry_path.parent
    discovery = _single_entry_discovery(entry_path, root)

    project_graph = ProjectGraph()
    project_graph.index_from_basepic(
        base_picture,
        source_path=entry_path,
        library_name=entry_path.parent.name,
    )

    return _build_semantic_snapshot(
        base_picture,
        entry_path=entry_path,
        workspace_root=root,
        discovery=discovery,
        project_graph=project_graph,
        collect_variable_diagnostics=collect_variable_diagnostics,
        debug=debug,
    )


def load_workspace_snapshot(
    entry_file: Path,
    *,
    workspace_root: Path | None = None,
    mode: CodeMode | str = CodeMode.DRAFT,
    other_lib_dirs: list[Path] | None = None,
    abb_lib_dir: Path | None = None,
    scan_root_only: bool = False,
    debug: bool = False,
    collect_variable_diagnostics: bool = True,
) -> SemanticSnapshot:
    entry_path = Path(entry_file).resolve()
    if not entry_path.exists():
        raise FileNotFoundError(f"Entry file does not exist: {entry_path}")

    root = Path(workspace_root).resolve() if workspace_root else entry_path.parent
    discovery = discover_workspace_sources(root)
    normalized_mode = _normalize_mode(mode)
    selected_other_lib_dirs = list(other_lib_dirs) if other_lib_dirs is not None else list(
        discovery.other_lib_dirs_for(entry_path)
    )
    selected_abb_lib_dir = abb_lib_dir or discovery.abb_lib_dir or (root / "__missing_abb_lib__")

    loader = SattLineProjectLoader(
        program_dir=entry_path.parent,
        other_lib_dirs=selected_other_lib_dirs,
        abb_lib_dir=selected_abb_lib_dir,
        mode=normalized_mode,
        scan_root_only=scan_root_only,
        debug=debug,
    )

    graph = loader.resolve(entry_path.stem, strict=False)
    root_bp = graph.ast_by_name.get(entry_path.stem)
    if root_bp is None:
        raise RuntimeError(
            f"Target {entry_path.stem!r} was not parsed. "
            f"Resolved targets: {sorted(graph.ast_by_name.keys())}. Missing: {graph.missing}"
        )

    project_bp = merge_project_basepicture(root_bp, graph)

    return _build_semantic_snapshot(
        project_bp,
        entry_path=entry_path,
        workspace_root=root,
        discovery=discovery,
        project_graph=graph,
        collect_variable_diagnostics=collect_variable_diagnostics,
        debug=debug,
    )


__all__ = [
    "CompletionItem",
    "SemanticSnapshot",
    "SymbolDefinition",
    "WorkspaceSourceDiscovery",
    "discover_workspace_sources",
    "load_source_snapshot",
    "load_workspace_snapshot",
]
