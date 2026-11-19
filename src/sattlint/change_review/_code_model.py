# pyright: reportPrivateUsage=false
"""Semantic code model built from a ``SemanticSnapshot``.

The Change Review is driven by semantic structure, not raw text. This module
walks the merged ``BasePicture`` module tree exactly once and records, per
module, the code statements (with span-normalized fingerprints, original source
locations, referenced definition keys, and produced/assigned definition keys),
the instance parameter connections, and the sequence structure (for
state/transition context). Dependencies are derived from each module's own
resolved statement references, never from shared source lines.

The walk mirrors the reference-recording traversal used by the semantic index
builder (``ModuleTypeInstance`` code is attributed through its typedef) so the
resulting indexes line up with the snapshot's reference index.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, cast

from sattlint.parser_api import (
    Assignment,
    BasePicture,
    CodeComment,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    SourceSpan,
    VarRef,
    walk,
)

from ..core._semantic_helpers import source_file_key
from ..core._semantic_snapshot import ReferenceOccurrence, SemanticSnapshot
from ..core.ast_tools import iter_variable_refs
from ..core.origin import is_root_origin
from ..models.project_graph import program_identity
from ._ast_normalize import normalize_ast_value

_StatementKey = tuple[str | int, ...]
_DefinitionKey = tuple[str, ...]


@dataclass(frozen=True)
class _SequenceFork:
    """Semantic fingerprint of a ``SEQFORK`` suffix.

    Forks are attributes of a step or transition instead of sequence items, so
    they are recorded as their own review statement to keep jump changes
    visible even when guards and actions are unchanged.
    """

    targets: tuple[str, ...]
    has_break: bool
    span: SourceSpan | None = field(default=None, metadata={"layout": True})


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
    source_library: str | None = None


@dataclass(frozen=True)
class ConnectionModel:
    """One parameter mapping on a module instance or inline module definition.

    A connection wires the instance's module parameter to the expression or
    literal the surrounding module supplies. It is part of the module's
    behaviour even though it is not a code statement, so it is modeled
    separately from ``StatementModel``.
    """

    target: str
    source_type: str
    source_name: str | None
    source_literal: object | None
    is_global: bool
    is_duration: bool
    span: SourceSpan | None
    source_file: str | None
    source_library: str | None


@dataclass(frozen=True)
class BlockModel:
    """A complete equation block or sequence within a module.

    Equation blocks and sequences are the natural behavioural context boundary
    for a change: the surrounding statements determine what the changed code
    means. This model keeps the complete block's statements plus the aggregate
    set of definition keys it reads and writes.
    """

    module_path: tuple[str, ...]
    kind: str  # "equation" | "sequence"
    name: str
    statements: tuple[StatementModel, ...]
    reads_keys: frozenset[_DefinitionKey]
    writes_keys: frozenset[_DefinitionKey]
    line_start: int | None
    last_span: SourceSpan | None
    source_file: str | None
    source_library: str | None = None

    @property
    def identity(self) -> tuple[tuple[str, ...], str, str]:
        return (self.module_path, self.kind, self.name)


@dataclass(frozen=True)
class ModuleModel:
    """Semantic view of one module/function-block in the project."""

    module_path: tuple[str, ...]
    kind: str
    name: str
    origin_file: str | None
    origin_library: str | None
    statements: tuple[StatementModel, ...]
    blocks: tuple[BlockModel, ...]
    dependency_keys: frozenset[_DefinitionKey]
    declaration_span: SourceSpan | None
    sequence_structure: dict[str, tuple[tuple[str, str | None], ...]] = field(compare=False)
    code_source_id: int = field(compare=False, repr=False)
    #: Every SFC step reachable in this module, as ``(sequence, step)`` pairs.
    #: Unlike ``statements`` this includes steps with empty blocks, and it
    #: descends into alternative/parallel branches and nested subsequences.
    sequence_steps: tuple[tuple[str, str], ...] = ()
    #: Parameter mappings supplied by the instance that owns this module.
    connections: tuple[ConnectionModel, ...] = ()


@dataclass(frozen=True)
class CodeModel:
    """Indexes over every module in a single loaded project version."""

    modules: tuple[ModuleModel, ...]
    modules_by_path: dict[tuple[str, ...], ModuleModel] = field(compare=False)
    producers_by_key: dict[_DefinitionKey, tuple[tuple[str, ...], ...]] = field(compare=False)
    blocks_by_key: dict[tuple[tuple[str, ...], str, str], BlockModel] = field(compare=False)
    blocks_touching_key: dict[_DefinitionKey, tuple[tuple[tuple[str, ...], str, str], ...]] = field(compare=False)


def _iter_sfc_items(path: _StatementKey, items: list[Any] | None) -> Any:
    # Comments are presentation only. Filtering them before enumerate keeps the
    # statement keys stable when someone adds or edits a comment.
    code_items = [item for item in (items or []) if not isinstance(item, CodeComment)]
    for index, item in enumerate(code_items):
        if isinstance(item, SFCStep):
            for block in ("enter", "active", "exit"):
                block_code = [
                    statement
                    for statement in cast(list[Any], getattr(item.code, block, None) or [])
                    if not isinstance(statement, CodeComment)
                ]
                for block_index, statement in enumerate(block_code):
                    yield (
                        (*path, "step", item.name or "", block, block_index),
                        statement,
                        "statement",
                        None,
                    )
            if item.fork is not None:
                yield (
                    (*path, "fork", "step", item.name or ""),
                    _SequenceFork(
                        targets=tuple(target.casefold() for target in item.fork.targets),
                        has_break=item.fork.has_break,
                        span=item.span,
                    ),
                    "fork",
                    item.span,
                )
        elif isinstance(item, SFCTransition):
            transition_span = item.span if isinstance(item.span, SourceSpan) else None
            if transition_span is None:
                condition_span = getattr(item.condition, "span", None)
                transition_span = condition_span if isinstance(condition_span, SourceSpan) else None
            yield (
                (*path, "transition", index),
                item.condition,
                "transition",
                transition_span,
            )
            if item.fork is not None:
                yield (
                    (*path, "fork", "transition", index),
                    _SequenceFork(
                        targets=tuple(target.casefold() for target in item.fork.targets),
                        has_break=item.fork.has_break,
                        span=item.span,
                    ),
                    "fork",
                    item.span,
                )
        elif isinstance(item, SFCAlternative | SFCParallel):
            for branch_index, branch in enumerate(item.branches or []):
                for child in _iter_sfc_items((*path, "branch", branch_index), branch):
                    yield child
        elif isinstance(item, SFCSubsequence):
            for child in _iter_sfc_items((*path, "subsequence", item.name or "", index), item.body):
                yield child
        elif isinstance(item, SFCTransitionSub):
            for child in _iter_sfc_items((*path, "transition-sub", item.name or "", index), item.body):
                yield child
        # Fork suffixes carry no reviewable code; comments were skipped above.


def _iter_code_statements(module_code: ModuleCode | None) -> Any:
    if module_code is None:
        return
    for seq in module_code.sequences or []:
        prefix = ("sequence", seq.name or "")
        yield from _iter_sfc_items(prefix, seq.code or [])
    for equation in module_code.equationblocks or []:
        prefix = ("equation", equation.name or "")
        statements = [statement for statement in equation.code or [] if not isinstance(statement, CodeComment)]
        for index, statement in enumerate(statements):
            yield ((*prefix, index), statement, "statement", None)


def _collect_sequence_structure(
    module_code: ModuleCode | None,
) -> dict[str, tuple[tuple[str, str | None], ...]]:
    """Record the ordered node kinds per sequence, aligned to statement keys.

    Every entry corresponds to one non-comment item in ``seq.code`` (the same
    filtered order ``_iter_sfc_items`` enumerates) so a transition's statement
    key can be mapped to its surrounding steps for previous/next-state context.
    """
    structures: dict[str, list[tuple[str, str | None]]] = {}
    if module_code is None:
        return {}
    for seq in module_code.sequences or []:
        nodes: list[tuple[str, str | None]] = []
        for item in seq.code or []:
            if isinstance(item, CodeComment):
                continue
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
            else:
                nodes.append(("transition-sub", item.name))
        structures[seq.name or ""] = nodes
    return {name: tuple(nodes) for name, nodes in structures.items()}


def _module_name(node: BasePicture | SingleModule | FrameModule | ModuleTypeDef) -> str:
    if isinstance(node, BasePicture):
        return program_identity(node)
    if isinstance(node, ModuleTypeDef):
        return node.name
    return node.header.name


def _module_declaration_span(node: BasePicture | SingleModule | FrameModule | ModuleTypeDef) -> SourceSpan | None:
    if isinstance(node, ModuleTypeDef):
        return node.declaration_span
    span = getattr(node.header, "declaration_span", None)
    return span if isinstance(span, SourceSpan) else None


def _iter_assignment_targets(node: object) -> Iterator[VarRef]:
    """Yield ``VarRef`` targets assigned anywhere inside *node*."""
    for event in walk(node):
        if isinstance(event.node, Assignment):
            yield event.node.target


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


def _node_declared_variables(
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef,
) -> list[Any]:
    return list(node.moduleparameters or []) + list(node.localvariables or [])


def _node_scope_keys(
    node: BasePicture | SingleModule | FrameModule | ModuleTypeDef,
    module_path: tuple[str, ...],
) -> dict[str, _DefinitionKey]:
    """Map a declared variable name to its canonical definition key.

    Direct reads/writes of a statement are resolved against the module that
    *declares* the code's variables. For a typedef's code this is the typedef
    itself (``ValveType``), not the instance path, so a parameter mapping such
    as ``Open => StartCmd`` is treated as a broader connection rather than a
    direct read of the changed expression.
    """
    if isinstance(node, ModuleTypeDef):
        scope_base = (node.name.casefold(),)
    else:
        scope_base = tuple(segment.casefold() for segment in module_path)
    scope_keys: dict[str, _DefinitionKey] = {}
    for variable in _node_declared_variables(node):
        name = getattr(variable, "name", None)
        if isinstance(name, str) and name:
            scope_keys[name.casefold()] = (*scope_base, name.casefold())
    return scope_keys


def _resolve_var_ref(
    ref: Any,
    *,
    scope_keys: dict[str, _DefinitionKey],
    ref_line_index: dict[str, dict[int, list[ReferenceOccurrence]]],
    file_key: str,
) -> frozenset[_DefinitionKey]:
    """Resolve one variable reference to definition keys.

    Scope resolution is tried first (the variable declared by the code's owning
    module); the reference-occurrence index is the fallback for references to
    variables outside the owning scope.
    """
    span = getattr(ref, "span", None)
    if not isinstance(span, SourceSpan):
        return frozenset()
    name = getattr(ref, "name", None)
    if isinstance(name, str):
        segments = [segment.casefold() for segment in name.split(".") if segment]
        if segments and segments[0] in scope_keys:
            base = scope_keys[segments[0]]
            return frozenset({(*base, *segments[1:])})
    return _resolve_ref_keys(ref_line_index, file_key, span)


def _iter_sfc_steps(items: list[Any] | None) -> Iterator[str]:
    for item in items or ():
        if isinstance(item, SFCStep):
            yield item.name or ""
        elif isinstance(item, (SFCAlternative, SFCParallel)):
            for branch in item.branches or []:
                yield from _iter_sfc_steps(branch)
        elif isinstance(item, (SFCSubsequence, SFCTransitionSub)):
            yield from _iter_sfc_steps(item.body)


def _collect_sequence_steps(module_code: ModuleCode | None) -> tuple[tuple[str, str], ...]:
    """Record every step name per sequence, including empty and nested steps."""
    steps: list[tuple[str, str]] = []
    if module_code is None:
        return ()
    for seq in module_code.sequences or []:
        steps.extend((seq.name or "", step_name) for step_name in _iter_sfc_steps(seq.code))
    return tuple(steps)


def _connection_source_type(mapping: ParameterMapping) -> str:
    return mapping.source_type.value


def _collect_connections(
    module: SingleModule | ModuleTypeInstance,
    *,
    source_file: str | None,
    source_library: str | None,
) -> tuple[ConnectionModel, ...]:
    """Record the parameter mappings supplied by one module instance."""
    connections: list[ConnectionModel] = []
    for mapping in module.parametermappings or []:
        target = mapping.target.name
        if not target:
            continue
        connections.append(
            ConnectionModel(
                target=target,
                source_type=_connection_source_type(mapping),
                source_name=mapping.source.name if mapping.source is not None else None,
                source_literal=mapping.source_literal,
                is_global=mapping.is_source_global,
                is_duration=mapping.is_duration,
                span=mapping.span if isinstance(mapping.span, SourceSpan) else None,
                source_file=source_file,
                source_library=source_library,
            )
        )
    return tuple(connections)


def _collect_statements(
    code_node: Any,
    *,
    source_file: str | None,
    source_library: str | None,
    ref_line_index: dict[str, dict[int, list[ReferenceOccurrence]]],
    scope_keys: dict[str, _DefinitionKey],
) -> tuple[tuple[StatementModel, ...], frozenset[tuple[str, int, int]], frozenset[str]]:
    statements: list[StatementModel] = []
    ref_sites: set[tuple[str, int, int]] = set()
    files: set[str] = set()
    file_key = source_file_key(source_file) if source_file is not None else None

    for key, node, node_type, span_override in _iter_code_statements(code_node):
        span = span_override if isinstance(span_override, SourceSpan) else getattr(node, "span", None)
        normalized = normalize_ast_value(node)
        referenced_keys: set[_DefinitionKey] = set()
        produced_keys: set[_DefinitionKey] = set()
        if file_key is not None:
            for ref in iter_variable_refs(node):
                ref_span = getattr(ref, "span", None)
                if isinstance(ref_span, SourceSpan):
                    ref_sites.add((file_key, ref_span.line, ref_span.column))
                    referenced_keys.update(
                        _resolve_var_ref(
                            ref,
                            scope_keys=scope_keys,
                            ref_line_index=ref_line_index,
                            file_key=file_key,
                        )
                    )
            for target in _iter_assignment_targets(node):
                produced_keys.update(
                    _resolve_var_ref(
                        target,
                        scope_keys=scope_keys,
                        ref_line_index=ref_line_index,
                        file_key=file_key,
                    )
                )
        statements.append(
            StatementModel(
                key=key,
                node_type=node_type,
                fingerprint=normalized,
                span=span if isinstance(span, SourceSpan) else None,
                source_file=source_file,
                referenced_keys=tuple(sorted(referenced_keys)),
                produced_keys=tuple(sorted(produced_keys)),
                source_library=source_library,
            )
        )
        if source_file is not None:
            files.add(source_file)

    return tuple(statements), frozenset(ref_sites), frozenset(files)


def _group_blocks(
    module_path: tuple[str, ...],
    statements: tuple[StatementModel, ...],
    source_file: str | None,
    source_library: str | None,
) -> tuple[BlockModel, ...]:
    """Group statements into their containing equation blocks and sequences."""
    groups: dict[tuple[str, str], list[StatementModel]] = {}
    for statement in statements:
        if not statement.key or statement.key[0] not in {"equation", "sequence"}:
            continue
        groups.setdefault((str(statement.key[0]), str(statement.key[1])), []).append(statement)

    blocks: list[BlockModel] = []
    for (kind, name), grouped in groups.items():
        reads: set[_DefinitionKey] = set()
        writes: set[_DefinitionKey] = set()
        for statement in grouped:
            writes.update(statement.produced_keys)
            reads.update(key for key in statement.referenced_keys if key not in statement.produced_keys)
        spans = [statement.span for statement in grouped if statement.span is not None]
        first_span = min(spans, key=lambda span: (span.line, span.start)) if spans else None
        last_span = max(spans, key=lambda span: (span.line, span.start)) if spans else None
        blocks.append(
            BlockModel(
                module_path=module_path,
                kind=kind,
                name=name,
                statements=tuple(grouped),
                reads_keys=frozenset(reads),
                writes_keys=frozenset(writes),
                line_start=first_span.line if first_span is not None else None,
                last_span=last_span,
                source_file=source_file,
                source_library=source_library,
            )
        )
    blocks.sort(key=lambda block: (block.kind, block.name.casefold()))
    return tuple(blocks)


class _ModuleTreeWalker:
    def __init__(self, snapshot: SemanticSnapshot, *, include_dependency_modules: bool = True):
        self._snapshot = snapshot
        self._include_dependency_modules = include_dependency_modules
        self._root_origin_file = snapshot.base_picture.origin_file or snapshot.entry_file.name
        self._root_origin_library = snapshot.base_picture.origin_lib
        self._typedef_index: dict[str, list[ModuleTypeDef]] = {}
        for moduletype in snapshot.base_picture.moduletype_defs or []:
            self._typedef_index.setdefault(moduletype.name.casefold(), []).append(moduletype)
        self._ref_line_index = _build_ref_line_index(snapshot._references_by_file)
        self._modules: list[ModuleModel] = []
        self._produced_keys_by_module: dict[tuple[str, ...], set[_DefinitionKey]] = {}
        # Every instance of the same typedef shares its statement models and
        # fingerprints. Rebuilding them per instance multiplies a large project's
        # memory by its instance count without changing one byte of the diff.
        self._typedef_statements: dict[int, tuple[StatementModel, ...]] = {}

    def _is_root_origin(self, origin_file: str | None, origin_lib: str | None) -> bool:
        if self._include_dependency_modules:
            return True
        return is_root_origin(
            origin_file,
            origin_lib,
            root_origin_file=self._root_origin_file,
            root_origin_library=self._root_origin_library,
        )

    def _add_module(
        self,
        node: BasePicture | SingleModule | FrameModule | ModuleTypeDef,
        *,
        module_path: tuple[str, ...],
        kind: str,
        origin_file: str | None,
        origin_library: str | None,
        connections: tuple[ConnectionModel, ...] = (),
    ) -> None:
        if isinstance(node, ModuleTypeDef):
            statements = self._typedef_statements.get(id(node))
            if statements is None:
                statements = _collect_statements(
                    node.modulecode,
                    source_file=origin_file,
                    source_library=origin_library,
                    ref_line_index=self._ref_line_index,
                    scope_keys=_node_scope_keys(node, module_path),
                )[0]
                self._typedef_statements[id(node)] = statements
        else:
            statements = _collect_statements(
                getattr(node, "modulecode", None),
                source_file=origin_file,
                source_library=origin_library,
                ref_line_index=self._ref_line_index,
                scope_keys=_node_scope_keys(node, module_path),
            )[0]
        produced: set[_DefinitionKey] = set()
        for statement in statements:
            produced.update(statement.produced_keys)
        blocks = _group_blocks(module_path, statements, origin_file, origin_library)
        self._produced_keys_by_module[module_path] = produced
        self._modules.append(
            ModuleModel(
                module_path=module_path,
                kind=kind,
                name=_module_name(node),
                origin_file=origin_file,
                origin_library=origin_library,
                statements=statements,
                blocks=blocks,
                dependency_keys=frozenset(),
                declaration_span=_module_declaration_span(node),
                sequence_structure=_collect_sequence_structure(getattr(node, "modulecode", None)),
                code_source_id=id(node),
                sequence_steps=_collect_sequence_steps(getattr(node, "modulecode", None)),
                connections=connections,
            )
        )

    def _add_instance_module(
        self,
        instance: ModuleTypeInstance,
        *,
        module_path: tuple[str, ...],
        origin_file: str | None,
        origin_library: str | None,
        connections: tuple[ConnectionModel, ...],
    ) -> None:
        """Record an instance whose typedef code is outside the reviewed origin.

        The connection list still belongs to the reviewed project even when the
        type's implementation lives in a dependency library, so the instance is
        kept as a connection-only module instead of being dropped.
        """
        self._modules.append(
            ModuleModel(
                module_path=module_path,
                kind="MT",
                name=instance.header.name,
                origin_file=origin_file,
                origin_library=origin_library,
                statements=(),
                blocks=(),
                dependency_keys=frozenset(),
                declaration_span=None,
                sequence_structure={},
                code_source_id=id(instance),
                sequence_steps=(),
                connections=connections,
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
                    connections=_collect_connections(
                        module,
                        source_file=origin_file,
                        source_library=origin_library,
                    ),
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
                if typedef is None or not self._is_root_origin(typedef.origin_file, typedef.origin_lib):
                    self._add_instance_module(
                        module,
                        module_path=child_path,
                        origin_file=origin_file,
                        origin_library=origin_library,
                        connections=_collect_connections(
                            module,
                            source_file=origin_file,
                            source_library=origin_library,
                        ),
                    )
                    continue
                self._add_module(
                    typedef,
                    module_path=child_path,
                    kind="MT",
                    origin_file=typedef.origin_file,
                    origin_library=typedef.origin_lib,
                    connections=_collect_connections(
                        module,
                        source_file=origin_file,
                        source_library=origin_library,
                    ),
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
        if not matches:
            return None
        # Same-named types from different libraries are legitimate, but only a
        # root-origin definition describes code the review can diff. When more
        # than one root definition shares the name, no choice is safe, so fail
        # loudly instead of diffing an arbitrary one.
        root_matches = [
            candidate for candidate in matches if self._is_root_origin(candidate.origin_file, candidate.origin_lib)
        ]
        if len(root_matches) == 1:
            return root_matches[0]
        if len(root_matches) > 1:
            libraries = ", ".join(sorted({candidate.origin_lib or "" for candidate in root_matches}))
            raise ValueError(
                f"Ambiguous module type '{instance.moduletype_name}' in {libraries or 'the analyzed project'}: "
                "more than one definition matches."
            )
        # Every match belongs to a dependency library, so the instance's code is
        # outside the reviewed origin regardless of which one is chosen. Returning
        # None keeps the instance as connection-only context without pretending an
        # arbitrary definition is the right one.
        return None

    def build(self) -> CodeModel:
        root = self._snapshot.base_picture
        root_path = (program_identity(root),)
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

        producers_by_key: dict[_DefinitionKey, set[tuple[str, ...]]] = {}
        for module_path, produced_keys in self._produced_keys_by_module.items():
            for key in produced_keys:
                producers_by_key.setdefault(key, set()).add(module_path)

        # Dependencies belong to the module whose own statements reference the
        # definition. Attributing a reference by source line would give every
        # instance that shares the same type code every instance-specific key.
        dependency_keys_by_module: dict[tuple[str, ...], set[_DefinitionKey]] = {}
        for module in self._modules:
            dependency_keys_by_module[module.module_path] = {
                key for statement in module.statements for key in statement.referenced_keys
            }

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
                    blocks=module.blocks,
                    dependency_keys=frozenset(dependency_keys_by_module.get(module.module_path, ())),
                    declaration_span=module.declaration_span,
                    sequence_structure=module.sequence_structure,
                    code_source_id=module.code_source_id,
                    sequence_steps=module.sequence_steps,
                    connections=module.connections,
                )
            )

        blocks_by_key: dict[tuple[tuple[str, ...], str, str], BlockModel] = {}
        blocks_touching_key: dict[_DefinitionKey, set[tuple[tuple[str, ...], str, str]]] = {}
        for module in modules:
            for block in module.blocks:
                blocks_by_key[block.identity] = block
                for key in (*block.reads_keys, *block.writes_keys):
                    blocks_touching_key.setdefault(key, set()).add(block.identity)

        return CodeModel(
            modules=tuple(modules),
            modules_by_path={module.module_path: module for module in modules},
            producers_by_key={key: tuple(owners) for key, owners in producers_by_key.items()},
            blocks_by_key=blocks_by_key,
            blocks_touching_key={key: tuple(identities) for key, identities in blocks_touching_key.items()},
        )


def build_code_model(snapshot: SemanticSnapshot, *, include_dependency_modules: bool = True) -> CodeModel:
    """Build the per-module semantic code model for one project version."""
    return _ModuleTreeWalker(snapshot, include_dependency_modules=include_dependency_modules).build()
