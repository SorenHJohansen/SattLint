"""Semantic diff between an official and a draft project version.

The diff is driven entirely by the semantic model: ``SemanticSnapshot``
definitions, the per-module code model, and call signatures. Raw text is only
used as a presentation detail (source snippets attached by a provider). Parser
noise from formatting or layout never becomes a change because comparison uses
span-normalized fingerprints.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from typing import cast

from ..core._semantic_snapshot import SymbolDefinition
from ._ast_normalize import normalize_ast_value, statement_shape
from ._code_model import ConnectionModel, ModuleModel, StatementModel
from .facts import ChangeSemanticContext
from .loader import VersionSnapshot

SnippetProvider = Callable[[str | None, str | None, object], str | None]


class ChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    DECLARATION_CHANGED = "declaration_changed"
    IMPLEMENTATION_CHANGED = "implementation_changed"
    EXPRESSION_CHANGED = "expression_changed"
    STATEMENT_CHANGED = "statement_changed"
    TRANSITION_CHANGED = "transition_changed"
    CALL_CHANGED = "call_changed"
    CONNECTION_CHANGED = "connection_changed"
    DEPENDENCY_CHANGED = "dependency_changed"
    S88_CHANGED = "s88_changed"


@dataclass(frozen=True)
class SourceLocation:
    file: str | None
    line: int | None
    column: int | None
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class ChangeChange:
    """One semantically meaningful change between the two versions."""

    symbol: str
    module_path: tuple[str, ...]
    kind: ChangeKind
    detail: str
    official: object | None = None
    draft: object | None = None
    location: SourceLocation | None = None
    draft_location: SourceLocation | None = None
    containing_symbol: str | None = None
    statement_context: str | None = None
    read_keys: tuple[tuple[str, ...], ...] = ()
    produced_keys: tuple[tuple[str, ...], ...] = ()
    sequence_name: str | None = None
    previous_state: str | None = None
    next_state: str | None = None
    containing_state: str | None = None
    block_kind: str | None = None
    block_name: str | None = None
    semantic_context: ChangeSemanticContext | None = None


def _canonical_key(path: str) -> tuple[str, ...]:
    return tuple(segment.casefold() for segment in path.split("."))


def _canonical_module_path(path: tuple[str, ...]) -> tuple[str, ...]:
    """Module paths compare case-insensitively, like every SattLine identifier."""
    return tuple(segment.casefold() for segment in path)


def _canonical_statement_key(key: tuple[str | int, ...]) -> tuple[str | int, ...]:
    """Statement keys embed names (sequence, equation, step); fold those too."""
    return tuple(segment.casefold() if isinstance(segment, str) else segment for segment in key)


def _module_symbol(module_path: tuple[str, ...]) -> str:
    return ".".join(module_path)


def _statement_context_label(key: tuple[str | int, ...]) -> str | None:
    """Human-readable container label for a statement key.

    Statement keys encode the module's code structure, e.g.
    ``("sequence", "MainSeq", "step", "Fill", "enter", 0)`` or
    ``("equation", "Main", 0)``. This renders that structure so a reviewer can
    see exactly which sequence/equation/step a change belongs to.
    """
    if not key or key[0] not in {"sequence", "equation"}:
        return None
    if key[0] == "sequence":
        parts: list[str] = [f"sequence {key[1]}"]
    else:
        parts = [f"equation {key[1]}"]
    for index, segment in enumerate(key):
        if segment == "step" and index + 1 < len(key):
            block = key[index + 2] if index + 2 < len(key) else ""
            parts.append(f"step {key[index + 1]}" + (f" ({block})" if block else ""))
        elif segment == "transition":
            parts.append("transition")
        elif segment == "branch" and index + 1 < len(key):
            parts.append(f"branch #{key[index + 1]}")
        elif segment == "subsequence" and index + 1 < len(key):
            parts.append(f"subsequence {key[index + 1]}")
        elif segment == "transition-sub" and index + 1 < len(key):
            parts.append(f"transition sub {key[index + 1]}")
        elif segment == "fork":
            parts.append("fork")
    return " > ".join(parts)


def _structural_context(
    statement: StatementModel,
    module: ModuleModel,
) -> tuple[str | None, str | None, str | None, str | None]:
    """Return (sequence_name, previous_state, next_state, containing_state)."""
    key = statement.key
    if not key or key[0] != "sequence":
        return None, None, None, None
    sequence_name = str(key[1])
    for index, segment in enumerate(key):
        if segment == "step" and index + 1 < len(key):
            block = str(key[index + 2]) if index + 2 < len(key) else ""
            state = str(key[index + 1])
            return sequence_name, None, None, f"{state} ({block})" if block else state
        if segment == "transition" and index + 1 < len(key):
            transition_index = key[index + 1]
            if not isinstance(transition_index, int):
                return sequence_name, None, None, None
            nodes = module.sequence_structure.get(sequence_name, ())
            if transition_index >= len(nodes):
                return sequence_name, None, None, None
            previous_node = nodes[transition_index - 1] if transition_index > 0 else None
            next_node = nodes[transition_index + 1] if transition_index + 1 < len(nodes) else None
            previous_state = previous_node[1] if previous_node and previous_node[0] == "step" else None
            next_state = next_node[1] if next_node and next_node[0] == "step" else None
            return sequence_name, previous_state, next_state, None
    return sequence_name, None, None, None


def _to_location(source_file: str | None, span: object) -> SourceLocation | None:
    line = getattr(span, "line", None)
    column = getattr(span, "column", None)
    start = getattr(span, "start", None)
    end = getattr(span, "end", None)
    if not isinstance(line, int) or not isinstance(column, int):
        return SourceLocation(file=source_file, line=None, column=None)
    return SourceLocation(
        file=source_file,
        line=line,
        column=column,
        start=start if isinstance(start, int) else None,
        end=end if isinstance(end, int) else None,
    )


def _declaration_signature(definition: SymbolDefinition) -> tuple[object, ...]:
    """Case-insensitive declaration identity.

    Keywords, datatypes, field names, and modifiers are SattLine identifiers or
    reserved words, so ``Integer`` and ``integer`` declare the same variable.
    The initializer is kept verbatim: string literals are case-sensitive data.
    """
    return (
        definition.kind.casefold(),
        definition.datatype.casefold() if definition.datatype is not None else None,
        definition.field_path.casefold() if definition.field_path is not None else None,
        definition.initializer,
        tuple(modifier.casefold() for modifier in definition.modifiers),
    )


def _declaration_repr(definition: SymbolDefinition) -> str | None:
    parts: list[str] = []
    if definition.modifiers:
        parts.append(" ".join(modifier.upper() for modifier in definition.modifiers))
    if definition.datatype is not None:
        parts.append(definition.datatype)
    else:
        parts.append(definition.kind)
    if definition.initializer is not None:
        parts.append(f"= {definition.initializer}")
    return " ".join(parts)


class _DefinitionDiff:
    def __init__(self, official: VersionSnapshot, draft: VersionSnapshot):
        self._official = official
        self._draft = draft

    @staticmethod
    def _index(snapshot: VersionSnapshot) -> dict[tuple[str, ...], SymbolDefinition]:
        return {_canonical_key(definition.canonical_path): definition for definition in snapshot.snapshot.definitions}

    def changes(self) -> list[ChangeChange]:
        official_by_key = self._index(self._official)
        draft_by_key = self._index(self._draft)
        changes: list[ChangeChange] = []

        for key in sorted(draft_by_key, key=lambda item: ".".join(item)):
            if key not in official_by_key:
                definition = draft_by_key[key]
                changes.append(
                    ChangeChange(
                        symbol=definition.canonical_path,
                        module_path=tuple(definition.declaration_module_path),
                        kind=ChangeKind.ADDED,
                        detail="Symbol added",
                        draft=_declaration_repr(definition),
                        location=self._definition_location(definition),
                        containing_symbol=self._containing_symbol(definition),
                    )
                )

        for key in sorted(official_by_key, key=lambda item: ".".join(item)):
            if key not in draft_by_key:
                definition = official_by_key[key]
                changes.append(
                    ChangeChange(
                        symbol=definition.canonical_path,
                        module_path=tuple(definition.declaration_module_path),
                        kind=ChangeKind.REMOVED,
                        detail="Symbol removed",
                        official=_declaration_repr(definition),
                        location=self._definition_location(definition),
                        containing_symbol=self._containing_symbol(definition),
                    )
                )

        for key in sorted(official_by_key, key=lambda item: ".".join(item)):
            official_def = official_by_key[key]
            draft_def = draft_by_key.get(key)
            if draft_def is None:
                continue
            official_repr = _declaration_repr(official_def)
            draft_repr = _declaration_repr(draft_def)
            if _declaration_signature(official_def) == _declaration_signature(draft_def):
                continue
            changes.append(
                ChangeChange(
                    symbol=draft_def.canonical_path,
                    module_path=tuple(draft_def.declaration_module_path),
                    kind=ChangeKind.DECLARATION_CHANGED,
                    detail="Declaration changed",
                    official=official_repr,
                    draft=draft_repr,
                    location=self._definition_location(official_def),
                    draft_location=self._definition_location(draft_def),
                    containing_symbol=self._containing_symbol(draft_def),
                )
            )
        return changes

    @staticmethod
    def _definition_location(definition: SymbolDefinition) -> SourceLocation | None:
        span = definition.declaration_span
        line = getattr(span, "line", None)
        column = getattr(span, "column", None)
        start = getattr(span, "start", None)
        end = getattr(span, "end", None)
        if not isinstance(line, int) or not isinstance(column, int):
            return SourceLocation(file=definition.source_file, line=None, column=None)
        return SourceLocation(
            file=definition.source_file,
            line=line,
            column=column,
            start=start if isinstance(start, int) else None,
            end=end if isinstance(end, int) else None,
        )

    @staticmethod
    def _containing_symbol(definition: SymbolDefinition) -> str | None:
        if len(definition.declaration_module_path) <= 1:
            return None
        return ".".join(definition.declaration_module_path)


def _step_names(module: ModuleModel) -> dict[tuple[str, str], tuple[str, str]]:
    """Map a folded ``(sequence, step)`` to its display names.

    ``sequence_steps`` covers empty and branch-nested steps, which have no
    statement of their own to discover them from.
    """
    steps: dict[tuple[str, str], tuple[str, str]] = {}
    for sequence_name, step_name in module.sequence_steps:
        steps[(sequence_name.casefold(), step_name.casefold())] = (sequence_name, step_name)
    return steps


def _snippet(
    snippet_fn: SnippetProvider | None,
    statement: StatementModel,
) -> object | None:
    if snippet_fn is None:
        return None
    return snippet_fn(statement.source_file, statement.source_library, statement.span)


def _read_keys(statement: StatementModel) -> tuple[tuple[str, ...], ...]:
    produced = frozenset(statement.produced_keys)
    return tuple(sorted(key for key in statement.referenced_keys if key not in produced))


def _block_identity(statement: StatementModel) -> tuple[str | None, str | None]:
    if not statement.key or statement.key[0] not in {"equation", "sequence"}:
        return None, None
    return str(statement.key[0]), str(statement.key[1])


def _container_key(key: tuple[str | int, ...]) -> tuple[str | int, ...]:
    """Group statements that belong to the same equation, step block or transition run."""
    return key[:-1] if key and isinstance(key[-1], int) else key


def _as_tuple(value: object) -> tuple[object, ...] | None:
    if isinstance(value, tuple):
        return cast(tuple[object, ...], value)
    return None


def _statement_identity(statement: StatementModel) -> tuple[str, object]:
    """Identity used to align replacement runs without pairing unrelated statements."""
    if statement.node_type in {"transition", "fork"}:
        return ("transition", statement.node_type)
    shape = _as_tuple(statement_shape(statement.fingerprint))
    if shape is None or len(shape) == 0:
        return ("shape", shape)
    kind = str(shape[0])
    if kind == "assignment" and len(shape) >= 2:
        target = _as_tuple(shape[1])
        if target is not None and len(target) >= 2 and target[0] == "varref":
            return ("assignment", str(target[1]).casefold())
        return ("assignment-shape", shape[1])
    if kind == "callstmt" and len(shape) >= 2:
        call = _as_tuple(shape[1])
        if call is not None and len(call) >= 2 and call[0] == "call":
            return ("call", str(call[1]).casefold())
    if kind == "if":
        return ("if", "if")
    if kind == "dc" and len(shape) >= 3:
        return ("dc", str(shape[1]))
    return ("shape", shape)


def _group_statements(
    module: ModuleModel,
) -> dict[tuple[str | int, ...], list[StatementModel]]:
    groups: dict[tuple[str | int, ...], list[StatementModel]] = {}
    for statement in module.statements:
        groups.setdefault(_container_key(_canonical_statement_key(statement.key)), []).append(statement)
    return groups


def _align_replacement_run(
    official_run: list[StatementModel],
    draft_run: list[StatementModel],
) -> tuple[list[tuple[StatementModel, StatementModel]], list[StatementModel], list[StatementModel]]:
    """Pair replacement statements by semantic identity, never by raw position.

    Statements with the same assignment target, call name or statement kind are
    modifications of one another. Everything else is a genuine addition or
    removal; pairing the leftovers by position is what created the misleading
    ``A = 1`` -> ``B = 2`` replacements in the review.
    """
    draft_by_identity: dict[tuple[object, ...], list[int]] = {}
    for index, statement in enumerate(draft_run):
        draft_by_identity.setdefault(_statement_identity(statement), []).append(index)

    paired: list[tuple[StatementModel, StatementModel]] = []
    used_draft: set[int] = set()
    paired_official: set[int] = set()
    for official_index, official_statement in enumerate(official_run):
        candidates = draft_by_identity.get(_statement_identity(official_statement), [])
        while candidates:
            draft_index = candidates.pop(0)
            if draft_index in used_draft:
                continue
            paired.append((official_statement, draft_run[draft_index]))
            used_draft.add(draft_index)
            paired_official.add(official_index)
            break

    removed = [statement for index, statement in enumerate(official_run) if index not in paired_official]
    added = [statement for index, statement in enumerate(draft_run) if index not in used_draft]
    return paired, removed, added


def _align_statements(
    official: list[StatementModel],
    draft: list[StatementModel],
) -> list[tuple[str, StatementModel, StatementModel | None]]:
    """Align one container's statements and yield changed/removed/added entries."""
    matcher = SequenceMatcher(
        None,
        [statement.fingerprint for statement in official],
        [statement.fingerprint for statement in draft],
        autojunk=False,
    )
    aligned: list[tuple[str, StatementModel, StatementModel | None]] = []
    for tag, official_start, official_end, draft_start, draft_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            aligned.extend(("removed", statement, None) for statement in official[official_start:official_end])
            continue
        if tag == "insert":
            aligned.extend(("added", statement, None) for statement in draft[draft_start:draft_end])
            continue
        paired, removed, added = _align_replacement_run(
            official[official_start:official_end],
            draft[draft_start:draft_end],
        )
        aligned.extend(
            ("changed", official_statement, draft_statement) for official_statement, draft_statement in paired
        )
        aligned.extend(("removed", statement, None) for statement in removed)
        aligned.extend(("added", statement, None) for statement in added)
    return aligned


def _changed_statement_change(
    official_module: ModuleModel,
    draft_module: ModuleModel,
    official_statement: StatementModel,
    draft_statement: StatementModel,
    *,
    snippet_fn: SnippetProvider | None,
) -> ChangeChange:
    kind = _classify_statement_change(official_statement, draft_statement)
    sequence_name, previous_state, next_state, containing_state = _structural_context(draft_statement, draft_module)
    block_kind, block_name = _block_identity(draft_statement)
    return ChangeChange(
        symbol=_module_symbol(official_module.module_path),
        module_path=official_module.module_path,
        kind=kind,
        detail=_statement_detail(official_statement, kind),
        official=_snippet(snippet_fn, official_statement),
        draft=_snippet(snippet_fn, draft_statement),
        location=_to_location(official_statement.source_file, official_statement.span),
        draft_location=_to_location(draft_statement.source_file, draft_statement.span),
        statement_context=_statement_context_label(draft_statement.key),
        read_keys=_read_keys(draft_statement),
        produced_keys=draft_statement.produced_keys,
        sequence_name=sequence_name,
        previous_state=previous_state,
        next_state=next_state,
        containing_state=containing_state,
        block_kind=block_kind,
        block_name=block_name,
    )


def _diff_module_statement_lists(
    official_module: ModuleModel,
    draft_module: ModuleModel,
    *,
    snippet_fn: SnippetProvider | None,
) -> list[ChangeChange]:
    changes: list[ChangeChange] = []
    official_groups = _group_statements(official_module)
    draft_groups = _group_statements(draft_module)
    container_order = list(dict.fromkeys((*official_groups, *draft_groups)))

    for container in container_order:
        for kind, statement, counterpart in _align_statements(
            official_groups.get(container, []),
            draft_groups.get(container, []),
        ):
            if kind == "changed" and counterpart is not None:
                changes.append(
                    _changed_statement_change(
                        official_module,
                        draft_module,
                        statement,
                        counterpart,
                        snippet_fn=snippet_fn,
                    )
                )
            elif kind == "removed":
                changes.append(
                    _added_or_removed_change(
                        official_module,
                        statement,
                        kind=ChangeKind.REMOVED,
                        detail="Statement removed",
                        snippet_fn=snippet_fn,
                    )
                )
            else:
                changes.append(
                    _added_or_removed_change(
                        draft_module,
                        statement,
                        kind=ChangeKind.ADDED,
                        detail="Statement added",
                        snippet_fn=snippet_fn,
                    )
                )

    changes.extend(_diff_step_membership(official_module, draft_module, snippet_fn=snippet_fn))
    return changes


def _added_or_removed_change(
    module: ModuleModel,
    statement: StatementModel,
    *,
    kind: ChangeKind,
    detail: str,
    snippet_fn: SnippetProvider | None,
) -> ChangeChange:
    sequence_name, previous_state, next_state, containing_state = _structural_context(statement, module)
    block_kind, block_name = _block_identity(statement)
    return ChangeChange(
        symbol=_module_symbol(module.module_path),
        module_path=module.module_path,
        kind=kind,
        detail=detail,
        official=_snippet(snippet_fn, statement) if kind is ChangeKind.REMOVED else None,
        draft=_snippet(snippet_fn, statement) if kind is ChangeKind.ADDED else None,
        location=_to_location(statement.source_file, statement.span),
        draft_location=_to_location(statement.source_file, statement.span),
        statement_context=_statement_context_label(statement.key),
        read_keys=_read_keys(statement),
        produced_keys=statement.produced_keys,
        sequence_name=sequence_name,
        previous_state=previous_state,
        next_state=next_state,
        containing_state=containing_state,
        block_kind=block_kind,
        block_name=block_name,
    )


def _diff_step_membership(
    official_module: ModuleModel,
    draft_module: ModuleModel,
    *,
    snippet_fn: SnippetProvider | None,
) -> list[ChangeChange]:
    del snippet_fn
    changes: list[ChangeChange] = []
    symbol = _module_symbol(official_module.module_path)
    official_steps = _step_names(official_module)
    draft_steps = _step_names(draft_module)
    for key in sorted(set(draft_steps) - set(official_steps)):
        sequence_name, step_name = draft_steps[key]
        changes.append(
            ChangeChange(
                symbol=symbol,
                module_path=official_module.module_path,
                kind=ChangeKind.S88_CHANGED,
                detail=f"Step {step_name!r} added to sequence {sequence_name!r}",
                draft=step_name,
            )
        )
    for key in sorted(set(official_steps) - set(draft_steps)):
        sequence_name, step_name = official_steps[key]
        changes.append(
            ChangeChange(
                symbol=symbol,
                module_path=official_module.module_path,
                kind=ChangeKind.S88_CHANGED,
                detail=f"Step {step_name!r} removed from sequence {sequence_name!r}",
                official=step_name,
            )
        )
    return changes


def _classify_statement_change(official_statement: StatementModel, draft_statement: StatementModel) -> ChangeKind:
    if official_statement.node_type == "fork" or draft_statement.node_type == "fork":
        return ChangeKind.STATEMENT_CHANGED
    if official_statement.node_type == "transition" or draft_statement.node_type == "transition":
        return ChangeKind.TRANSITION_CHANGED
    official_shape = statement_shape(official_statement.fingerprint)
    draft_shape = statement_shape(draft_statement.fingerprint)
    if official_shape == draft_shape:
        return ChangeKind.EXPRESSION_CHANGED
    return ChangeKind.STATEMENT_CHANGED


def _statement_detail(statement: StatementModel, kind: ChangeKind) -> str:
    if statement.node_type == "fork":
        return "Sequence jump changed"
    if kind is ChangeKind.TRANSITION_CHANGED:
        return "Transition condition changed"
    if kind is ChangeKind.EXPRESSION_CHANGED:
        return "Expression changed"
    return "Statement changed"


def _code_source_by_path(
    official: VersionSnapshot,
    draft: VersionSnapshot,
) -> dict[tuple[str, ...], int]:
    mapping: dict[tuple[str, ...], int] = {}
    for version in (official, draft):
        for module in version.code_model.modules:
            mapping[_canonical_module_path(module.module_path)] = module.code_source_id
    return mapping


def _module_display_paths(version: VersionSnapshot) -> dict[tuple[str, ...], tuple[str, ...]]:
    return {_canonical_module_path(module.module_path): module.module_path for module in version.code_model.modules}


def _connection_literal_text(value: object) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def _connection_text(connection: ConnectionModel) -> str:
    if connection.is_global:
        source = f"GLOBAL {connection.source_name}" if connection.source_name else "GLOBAL"
        return f"{connection.target} => {source}"
    if connection.source_type == "variable_name" and connection.source_name:
        return f"{connection.target} => {connection.source_name}"
    if connection.source_literal is not None:
        return f"{connection.target} => {_connection_literal_text(connection.source_literal)}"
    return f"{connection.target} => <none>"


def _connection_signature(connection: ConnectionModel) -> tuple[object, ...]:
    return (
        connection.target.casefold(),
        connection.source_type,
        connection.source_name.casefold() if connection.source_name is not None else None,
        normalize_ast_value(connection.source_literal),
        connection.is_global,
        connection.is_duration,
    )


def _diff_connections(
    official: VersionSnapshot,
    draft: VersionSnapshot,
) -> list[ChangeChange]:
    official_modules = {_canonical_module_path(module.module_path): module for module in official.code_model.modules}
    draft_modules = {_canonical_module_path(module.module_path): module for module in draft.code_model.modules}
    changes: list[ChangeChange] = []
    for module_key in sorted(set(official_modules) | set(draft_modules)):
        official_module = official_modules.get(module_key)
        draft_module = draft_modules.get(module_key)
        if official_module is None or draft_module is None:
            continue
        official_connections = {connection.target.casefold(): connection for connection in official_module.connections}
        draft_connections = {connection.target.casefold(): connection for connection in draft_module.connections}
        module_path = official_module.module_path
        symbol = _module_symbol(module_path)
        for target in sorted(set(official_connections) | set(draft_connections)):
            official_connection = official_connections.get(target)
            draft_connection = draft_connections.get(target)
            if draft_connection is not None:
                display_target = draft_connection.target
            elif official_connection is not None:
                display_target = official_connection.target
            else:
                display_target = target
            if official_connection is None and draft_connection is not None:
                changes.append(
                    ChangeChange(
                        symbol=symbol,
                        module_path=module_path,
                        kind=ChangeKind.CONNECTION_CHANGED,
                        detail=f"Connection {display_target!r} added",
                        draft=_connection_text(draft_connection),
                        draft_location=_to_location(draft_connection.source_file, draft_connection.span),
                        statement_context=f"connection {display_target}",
                    )
                )
                continue
            if draft_connection is None and official_connection is not None:
                changes.append(
                    ChangeChange(
                        symbol=symbol,
                        module_path=module_path,
                        kind=ChangeKind.CONNECTION_CHANGED,
                        detail=f"Connection {display_target!r} removed",
                        official=_connection_text(official_connection),
                        location=_to_location(official_connection.source_file, official_connection.span),
                        statement_context=f"connection {display_target}",
                    )
                )
                continue
            if official_connection is None or draft_connection is None:
                continue
            if _connection_signature(official_connection) == _connection_signature(draft_connection):
                continue
            changes.append(
                ChangeChange(
                    symbol=symbol,
                    module_path=module_path,
                    kind=ChangeKind.CONNECTION_CHANGED,
                    detail=f"Connection {display_target!r} changed",
                    official=_connection_text(official_connection),
                    draft=_connection_text(draft_connection),
                    location=_to_location(official_connection.source_file, official_connection.span),
                    draft_location=_to_location(draft_connection.source_file, draft_connection.span),
                    statement_context=f"connection {display_target}",
                )
            )
    return changes


def _diff_calls(
    official: VersionSnapshot,
    draft: VersionSnapshot,
) -> list[ChangeChange]:
    official_by_module: dict[tuple[str, ...], set[str]] = {}
    for occurrence in official.snapshot.call_signatures:
        official_by_module.setdefault(_canonical_module_path(tuple(occurrence.module_path)), set()).add(
            occurrence.name.casefold()
        )
    draft_by_module: dict[tuple[str, ...], set[str]] = {}
    for occurrence in draft.snapshot.call_signatures:
        draft_by_module.setdefault(_canonical_module_path(tuple(occurrence.module_path)), set()).add(
            occurrence.name.casefold()
        )
    display_paths = _module_display_paths(official) | _module_display_paths(draft)

    code_source = _code_source_by_path(official, draft)
    seen_sources: set[int] = set()
    changes: list[ChangeChange] = []
    model_paths = set(display_paths)
    for module_key in sorted((set(official_by_module) | set(draft_by_module)) & model_paths):
        source = code_source.get(module_key)
        if source is not None and module_key in official_by_module and module_key in draft_by_module:
            if source in seen_sources:
                continue
            seen_sources.add(source)
        official_calls = official_by_module.get(module_key, set())
        draft_calls = draft_by_module.get(module_key, set())
        module_path = display_paths.get(module_key, module_key)
        symbol = _module_symbol(module_path)
        for call_name in sorted(draft_calls - official_calls):
            changes.append(
                ChangeChange(
                    symbol=symbol,
                    module_path=module_path,
                    kind=ChangeKind.CALL_CHANGED,
                    detail=f"Call to {call_name!r} added",
                    draft=call_name,
                )
            )
        for call_name in sorted(official_calls - draft_calls):
            changes.append(
                ChangeChange(
                    symbol=symbol,
                    module_path=module_path,
                    kind=ChangeKind.CALL_CHANGED,
                    detail=f"Call to {call_name!r} removed",
                    official=call_name,
                )
            )
    return changes


def _diff_dependencies(
    official: VersionSnapshot,
    draft: VersionSnapshot,
) -> list[ChangeChange]:
    official_keys: dict[tuple[str, ...], frozenset[tuple[str, ...]]] = {
        _canonical_module_path(module.module_path): module.dependency_keys for module in official.code_model.modules
    }
    draft_keys: dict[tuple[str, ...], frozenset[tuple[str, ...]]] = {
        _canonical_module_path(module.module_path): module.dependency_keys for module in draft.code_model.modules
    }
    display_paths = _module_display_paths(official) | _module_display_paths(draft)

    code_source = _code_source_by_path(official, draft)
    seen_sources: set[int] = set()
    changes: list[ChangeChange] = []
    for module_key in sorted(set(official_keys) | set(draft_keys)):
        source = code_source.get(module_key)
        if source is not None and module_key in official_keys and module_key in draft_keys:
            if source in seen_sources:
                continue
            seen_sources.add(source)
        official_deps = official_keys.get(module_key, frozenset())
        draft_deps = draft_keys.get(module_key, frozenset())
        module_path = display_paths.get(module_key, module_key)
        symbol = _module_symbol(module_path)
        for dep_key in sorted(draft_deps - official_deps, key=".".join):
            changes.append(
                ChangeChange(
                    symbol=symbol,
                    module_path=module_path,
                    kind=ChangeKind.DEPENDENCY_CHANGED,
                    detail=f"Now depends on {'.'.join(dep_key)}",
                    draft=".".join(dep_key),
                )
            )
        for dep_key in sorted(official_deps - draft_deps, key=".".join):
            changes.append(
                ChangeChange(
                    symbol=symbol,
                    module_path=module_path,
                    kind=ChangeKind.DEPENDENCY_CHANGED,
                    detail=f"No longer depends on {'.'.join(dep_key)}",
                    official=".".join(dep_key),
                )
            )
    return changes


def compute_semantic_diff(
    official: VersionSnapshot,
    draft: VersionSnapshot,
    *,
    snippet_fn: SnippetProvider | None = None,
) -> list[ChangeChange]:
    """Compute all semantic changes between the official and draft versions."""
    changes: list[ChangeChange] = _DefinitionDiff(official, draft).changes()

    official_modules = {_canonical_module_path(module.module_path): module for module in official.code_model.modules}
    draft_modules = {_canonical_module_path(module.module_path): module for module in draft.code_model.modules}
    seen_code_sources: set[int] = set()

    for module_key in sorted(set(official_modules) | set(draft_modules)):
        official_module = official_modules.get(module_key)
        draft_module = draft_modules.get(module_key)
        if official_module is None or draft_module is None:
            if official_module is None and draft_module is not None:
                changes.append(
                    ChangeChange(
                        symbol=_module_symbol(draft_module.module_path),
                        module_path=draft_module.module_path,
                        kind=ChangeKind.ADDED,
                        detail="Module added",
                    )
                )
            elif draft_module is None and official_module is not None:
                changes.append(
                    ChangeChange(
                        symbol=_module_symbol(official_module.module_path),
                        module_path=official_module.module_path,
                        kind=ChangeKind.REMOVED,
                        detail="Module removed",
                    )
                )
            continue
        code_source = official_module.code_source_id
        if code_source in seen_code_sources:
            continue
        seen_code_sources.add(code_source)
        if normalize_ast_value(official_module) == normalize_ast_value(draft_module):
            continue
        changes.extend(
            _diff_module_statement_lists(
                official_module,
                draft_module,
                snippet_fn=snippet_fn,
            )
        )

    changes.extend(_diff_connections(official, draft))
    changes.extend(_diff_calls(official, draft))
    changes.extend(_diff_dependencies(official, draft))

    changes.sort(key=lambda change: (change.module_path, change.symbol, change.kind.value))
    return changes
