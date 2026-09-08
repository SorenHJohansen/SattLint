# pyright: reportPrivateUsage=false
"""Semantic code model built from a ``SemanticSnapshot``.

The Change Review is driven by semantic structure, not raw text. This module
walks the merged ``BasePicture`` module tree exactly once and records, per
module, the code statements (with span-normalized fingerprints, original source
locations, referenced definition keys, and produced/assigned definition keys)
plus the sequence structure (for state/transition context). It also builds the
reverse indexes needed by impact analysis: which modules consume a given
definition key, which modules produce (assign) it, and which module owns a
given reference site.

The walk mirrors the reference-recording traversal used by the semantic index
builder (``ModuleTypeInstance`` code is attributed through its typedef) so the
resulting indexes line up with the snapshot's reference index.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    SourceSpan,
)
from sattline_parser.models.expressions import Assignment

from ..core._semantic_helpers import source_file_key
from ..core._semantic_snapshot import ReferenceOccurrence, SemanticSnapshot
from ..core.ast_tools import iter_variable_refs
from ._ast_normalize import normalize_ast_value

_StatementKey = tuple[str | int, ...]
_DefinitionKey = tuple[str, ...]


@dataclass(frozen=True)
class StatementModel:
    """A single code statement (or transition condition) inside a module."""

    key: _StatementKey
    node_type: str
    fingerprint: object
    span: SourceSpan | None
    source_file: str | None
    referenced_keys: tuple[_DefinitionKey, ...] = ()
    produced_keys: tuple[_DefinitionKey, ...] = ()


@dataclass(frozen=True)
class ModuleModel:
    """Semantic view of one module/function-block in the project."""

    module_path: tuple[str, ...]
    kind: str
    name: str
    origin_file: str | None
    origin_library: str | None
    statements: tuple[StatementModel, ...]
    dependency_keys: frozenset[_DefinitionKey]
    declaration_span: SourceSpan | None
    sequence_structure: dict[str, tuple[tuple[str, str | None], ...]] = field(compare=False)
    code_source_id: int = field(compare=False, repr=False)


@dataclass(frozen=True)
class CodeModel:
    """Indexes over every module in a single loaded project version."""

    modules: tuple[ModuleModel, ...]
    modules_by_path: dict[tuple[str, ...], ModuleModel] = field(compare=False)
    owner_by_site: dict[tuple[str, int], tuple[tuple[str, ...], ...]] = field(compare=False)
    consumers_by_key: dict[_DefinitionKey, tuple[tuple[str, ...], ...]] = field(compare=False)
    producers_by_key: dict[_DefinitionKey, tuple[tuple[str, ...], ...]] = field(compare=False)


def _iter_sfc_items(path: _StatementKey, items: list[Any] | None) -> Any:
    for index, item in enumerate(items or []):
        if isinstance(item, SFCStep):
            for block in ("enter", "active", "exit"):
                block_code = cast(list[Any], getattr(item.code, block, None) or [])
                for block_index, statement in enumerate(block_code):
                    yield (
                        (*path, "step", item.name or "", block, block_index),
                        statement,
                        "statement",
                    )
        elif isinstance(item, SFCTransition):
            yield (
                (*path, "transition", index),
                item.condition,
                "transition",
            )
        elif isinstance(item, SFCAlternative | SFCParallel):
            for branch_index, branch in enumerate(item.branches or []):
                for child in _iter_sfc_items((*path, "branch", branch_index), branch):
                    yield child
        elif isinstance(item, SFCSubsequence):
            for child in _iter_sfc_items((*path, "subsequence", item.name, index), item.body):
                yield child
        elif isinstance(item, SFCTransitionSub):
            for child in _iter_sfc_items((*path, "transition-sub", item.name or "", index), item.body):
                yield child
        # SFCFork / SFCBreak / CodeComment carry no reviewable code.


def _iter_code_statements(module_code: ModuleCode | None) -> Any:
    if module_code is None:
        return
    for seq in module_code.sequences or []:
        prefix = ("sequence", seq.name or "")
        yield from _iter_sfc_items(prefix, seq.code or [])
    for equation in module_code.equations or []:
        prefix = ("equation", equation.name or "")
        for index, statement in enumerate(equation.code or []):
            yield ((*prefix, index), statement, "statement")


def _collect_sequence_structure(
    module_code: ModuleCode | None,
) -> dict[str, tuple[tuple[str, str | None], ...]]:
    """Record the ordered node kinds per sequence, aligned to statement keys.

    Every entry corresponds to one item in ``seq.code`` (same enumerate index as
    ``_iter_sfc_items``) so a transition's statement key can be mapped to its
    surrounding steps for previous/next-state context.
    """
    structures: dict[str, list[tuple[str, str | None]]] = {}
    if module_code is None:
        return {}
    for seq in module_code.sequences or []:
        nodes: list[tuple[str, str | None]] = []
        for item in seq.code or []:
            if isinstance(item, SFCStep):
                nodes.append(("step", item.name))
            elif isinstance(item, SFCTransition):
                nodes.append(("transition", item.name))
            elif isinstance(item, SFCAlternative):
                nodes.append(("alternative", None))
            elif isinstance(item, SFCParallel):
                nodes.append(("parallel", None))
            elif isinstance(item, SFCSubsequence):
                nodes.append(("subsequence", item.name))
            elif isinstance(item, SFCTransitionSub):
                nodes.append(("transition-sub", item.name))
            else:
                nodes.append(("other", None))
        structures[seq.name or ""] = nodes
    return {name: tuple(nodes) for name, nodes in structures.items()}


def _module_name(node: BasePicture | SingleModule | FrameModule | ModuleTypeDef) -> str:
    if isinstance(node, ModuleTypeDef):
        return node.name
    return node.header.name


def _module_declaration_span(node: BasePicture | SingleModule | FrameModule | ModuleTypeDef) -> SourceSpan | None:
    if isinstance(node, ModuleTypeDef):
        return node.declaration_span
    span = getattr(node.header, "declaration_span", None)
    return span if isinstance(span, SourceSpan) else None


def _iter_child_values(node: Any) -> Any:
    if isinstance(node, tuple | list):
        yield from cast(tuple[Any, ...] | list[Any], node)
    elif is_dataclass(node) and not isinstance(node, type):
        for field_def in fields(node):
            if field_def.name == "span":
                continue
            yield getattr(node, field_def.name)


def _iter_assignment_targets(node: Any) -> Any:
    """Yield ``VarRef`` targets assigned anywhere inside *node*."""
    if isinstance(node, Assignment):
        yield node.target
        return
    for child in _iter_child_values(node):
        yield from _iter_assignment_targets(child)


def _build_ref_line_index(
    references_by_file: dict[str, tuple[ReferenceOccurrence, ...]],
) -> dict[str, dict[int, list[ReferenceOccurrence]]]:
    index: dict[str, dict[int, list[ReferenceOccurrence]]] = {}
    for file_key, occurrences in references_by_file.items():
        line_index: dict[int, list[ReferenceOccurrence]] = {}
        for occurrence in occurrences:
            line_index.setdefault(occurrence.line, []).append(occurrence)
        index[file_key] = line_index
    return index


def _resolve_ref_keys(
    ref_line_index: dict[str, dict[int, list[ReferenceOccurrence]]],
    file_key: str,
    span: SourceSpan,
) -> frozenset[_DefinitionKey]:
    keys: set[_DefinitionKey] = set()
    for occurrence in ref_line_index.get(file_key, {}).get(span.line, ()):
        if occurrence.matches(span.line, span.column):
            keys.update(occurrence.definition_keys)
    return frozenset(keys)


def _collect_statements(
    code_node: Any,
    *,
    source_file: str | None,
    ref_line_index: dict[str, dict[int, list[ReferenceOccurrence]]],
) -> tuple[tuple[StatementModel, ...], frozenset[tuple[str, int, int]], frozenset[str]]:
    statements: list[StatementModel] = []
    ref_sites: set[tuple[str, int, int]] = set()
    files: set[str] = set()
    file_key = source_file_key(source_file) if source_file is not None else None

    for key, node, node_type in _iter_code_statements(code_node):
        span = getattr(node, "span", None)
        normalized = normalize_ast_value(node)
        referenced_keys: set[_DefinitionKey] = set()
        produced_keys: set[_DefinitionKey] = set()
        if file_key is not None:
            for ref in iter_variable_refs(node):
                ref_span = getattr(ref, "span", None)
                if isinstance(ref_span, SourceSpan):
                    ref_sites.add((file_key, ref_span.line, ref_span.column))
                    referenced_keys.update(_resolve_ref_keys(ref_line_index, file_key, ref_span))
            for target in _iter_assignment_targets(node):
                target_span = getattr(target, "span", None)
                if isinstance(target_span, SourceSpan):
                    produced_keys.update(_resolve_ref_keys(ref_line_index, file_key, target_span))
        statements.append(
            StatementModel(
                key=key,
                node_type=node_type,
                fingerprint=normalized,
                span=span if isinstance(span, SourceSpan) else None,
                source_file=source_file,
                referenced_keys=tuple(sorted(referenced_keys)),
                produced_keys=tuple(sorted(produced_keys)),
            )
        )
        if source_file is not None:
            files.add(source_file)

    return tuple(statements), frozenset(ref_sites), frozenset(files)


class _ModuleTreeWalker:
    def __init__(self, snapshot: SemanticSnapshot):
        self._snapshot = snapshot
        self._typedef_index: dict[str, list[ModuleTypeDef]] = {}
        for moduletype in snapshot.base_picture.moduletype_defs or []:
            self._typedef_index.setdefault(moduletype.name.casefold(), []).append(moduletype)
        self._ref_line_index = _build_ref_line_index(snapshot._references_by_file)
        self._modules: list[ModuleModel] = []
        self._ref_sites_by_module: dict[tuple[str, ...], frozenset[tuple[str, int, int]]] = {}
        self._produced_keys_by_module: dict[tuple[str, ...], set[_DefinitionKey]] = {}

    def _add_module(
        self,
        node: BasePicture | SingleModule | FrameModule | ModuleTypeDef,
        *,
        module_path: tuple[str, ...],
        kind: str,
        origin_file: str | None,
        origin_library: str | None,
    ) -> None:
        statements, ref_sites, _files = _collect_statements(
            getattr(node, "modulecode", None),
            source_file=origin_file,
            ref_line_index=self._ref_line_index,
        )
        produced: set[_DefinitionKey] = set()
        for statement in statements:
            produced.update(statement.produced_keys)
        self._ref_sites_by_module[module_path] = ref_sites
        self._produced_keys_by_module[module_path] = produced
        self._modules.append(
            ModuleModel(
                module_path=module_path,
                kind=kind,
                name=_module_name(node),
                origin_file=origin_file,
                origin_library=origin_library,
                statements=statements,
                dependency_keys=frozenset(),
                declaration_span=_module_declaration_span(node),
                sequence_structure=_collect_sequence_structure(getattr(node, "modulecode", None)),
                code_source_id=id(node),
            )
        )

    def _walk_submodules(
        self,
        modules: list[SingleModule | FrameModule | ModuleTypeInstance],
        *,
        module_path: tuple[str, ...],
        origin_file: str | None,
        origin_library: str | None,
    ) -> None:
        for module in modules:
            if isinstance(module, SingleModule):
                child_path = (*module_path, module.header.name)
                self._add_module(
                    module,
                    module_path=child_path,
                    kind="SM",
                    origin_file=origin_file,
                    origin_library=origin_library,
                )
                self._walk_submodules(
                    module.submodules or [],
                    module_path=child_path,
                    origin_file=origin_file,
                    origin_library=origin_library,
                )
            elif isinstance(module, FrameModule):
                child_path = (*module_path, module.header.name)
                self._add_module(
                    module,
                    module_path=child_path,
                    kind="FM",
                    origin_file=origin_file,
                    origin_library=origin_library,
                )
                self._walk_submodules(
                    module.submodules or [],
                    module_path=child_path,
                    origin_file=origin_file,
                    origin_library=origin_library,
                )
            else:
                child_path = (*module_path, module.header.name)
                typedef = self._resolve_typedef(module)
                if typedef is None:
                    continue
                self._add_module(
                    typedef,
                    module_path=child_path,
                    kind="MT",
                    origin_file=typedef.origin_file,
                    origin_library=typedef.origin_lib,
                )
                self._walk_submodules(
                    typedef.submodules or [],
                    module_path=child_path,
                    origin_file=typedef.origin_file,
                    origin_library=typedef.origin_lib,
                )

    def _resolve_typedef(self, instance: ModuleTypeInstance) -> ModuleTypeDef | None:
        matches = self._typedef_index.get(instance.moduletype_name.casefold(), [])
        if len(matches) == 1:
            return matches[0]
        for candidate in matches:
            if candidate.origin_lib is not None:
                return candidate
        if matches:
            return matches[0]
        return None

    def _build_owner_and_consumers(
        self,
    ) -> tuple[dict[tuple[str, int], set[tuple[str, ...]]], dict[_DefinitionKey, set[tuple[str, ...]]]]:
        owner_by_site: dict[tuple[str, int], set[tuple[str, ...]]] = {}
        consumers_by_key: dict[_DefinitionKey, set[tuple[str, ...]]] = {}
        for module_path, ref_sites in self._ref_sites_by_module.items():
            for file_key, line, _column in ref_sites:
                owner_by_site.setdefault((file_key, line), set()).add(module_path)
        for definition in self._snapshot.definitions:
            key = tuple(segment.casefold() for segment in definition.canonical_path.split("."))
            for reference in self._snapshot.find_references_to(definition):
                if reference.source_file is None:
                    continue
                file_key = source_file_key(reference.source_file)
                if file_key is None:
                    continue
                site_key = (file_key, reference.line)
                owners = owner_by_site.get(site_key)
                if owners:
                    consumers_by_key.setdefault(key, set()).update(owners)
        return owner_by_site, consumers_by_key

    def build(self) -> CodeModel:
        root = self._snapshot.base_picture
        root_path = (root.header.name,)
        root_file = root.origin_file or self._snapshot.entry_file.name
        self._add_module(
            root,
            module_path=root_path,
            kind="BP",
            origin_file=root_file,
            origin_library=root.origin_lib,
        )
        self._walk_submodules(
            root.submodules or [],
            module_path=root_path,
            origin_file=root_file,
            origin_library=root.origin_lib,
        )
        for moduletype in self._snapshot.base_picture.moduletype_defs or []:
            module_path = (moduletype.name,)
            self._add_module(
                moduletype,
                module_path=module_path,
                kind="MT",
                origin_file=moduletype.origin_file,
                origin_library=moduletype.origin_lib,
            )
            self._walk_submodules(
                moduletype.submodules or [],
                module_path=module_path,
                origin_file=moduletype.origin_file,
                origin_library=moduletype.origin_lib,
            )

        owner_by_site, consumers_by_key = self._build_owner_and_consumers()

        producers_by_key: dict[_DefinitionKey, set[tuple[str, ...]]] = {}
        for module_path, produced_keys in self._produced_keys_by_module.items():
            for key in produced_keys:
                producers_by_key.setdefault(key, set()).add(module_path)

        dependency_keys_by_module: dict[tuple[str, ...], set[_DefinitionKey]] = {
            module_path: set() for module_path in self._ref_sites_by_module
        }
        for key, owners in consumers_by_key.items():
            for owner in owners:
                dependency_keys_by_module.setdefault(owner, set()).add(key)

        modules: list[ModuleModel] = []
        for module in self._modules:
            modules.append(
                ModuleModel(
                    module_path=module.module_path,
                    kind=module.kind,
                    name=module.name,
                    origin_file=module.origin_file,
                    origin_library=module.origin_library,
                    statements=module.statements,
                    dependency_keys=frozenset(dependency_keys_by_module.get(module.module_path, ())),
                    declaration_span=module.declaration_span,
                    sequence_structure=module.sequence_structure,
                    code_source_id=module.code_source_id,
                )
            )

        return CodeModel(
            modules=tuple(modules),
            modules_by_path={module.module_path: module for module in modules},
            owner_by_site={site: tuple(owners) for site, owners in owner_by_site.items()},
            consumers_by_key={key: tuple(owners) for key, owners in consumers_by_key.items()},
            producers_by_key={key: tuple(owners) for key, owners in producers_by_key.items()},
        )


def build_code_model(snapshot: SemanticSnapshot) -> CodeModel:
    """Build the per-module semantic code model for one project version."""
    return _ModuleTreeWalker(snapshot).build()
