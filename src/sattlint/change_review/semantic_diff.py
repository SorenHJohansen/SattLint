"""Semantic diff between an official and a draft project version.

The diff is driven entirely by the semantic model: ``SemanticSnapshot``
definitions, the per-module code model, and call signatures. Raw text is only
used as a presentation detail (source snippets attached by a provider). Parser
noise from formatting or layout never becomes a change because comparison uses
span-normalized fingerprints.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from ..core._semantic_snapshot import SymbolDefinition
from ._ast_normalize import normalize_ast_value, statement_shape
from ._code_model import ModuleModel, StatementModel
from .facts import ChangeSemanticContext
from .loader import VersionSnapshot

SnippetProvider = Callable[[str | None, object], str | None]


class ChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    DECLARATION_CHANGED = "declaration_changed"
    IMPLEMENTATION_CHANGED = "implementation_changed"
    EXPRESSION_CHANGED = "expression_changed"
    STATEMENT_CHANGED = "statement_changed"
    TRANSITION_CHANGED = "transition_changed"
    CALL_CHANGED = "call_changed"
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


def _declaration_repr(definition: SymbolDefinition) -> str | None:
    if definition.datatype is not None:
        return definition.datatype
    return definition.kind


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
            if (official_def.kind, official_def.datatype, official_def.field_path) == (
                draft_def.kind,
                draft_def.datatype,
                draft_def.field_path,
            ):
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


def _step_names(module: ModuleModel) -> dict[str, frozenset[str]]:
    steps: dict[str, set[str]] = {}
    for statement in module.statements:
        if statement.key[0] == "sequence" and statement.key[2] == "step":
            steps.setdefault(str(statement.key[1]), set()).add(str(statement.key[3]))
    return {name: frozenset(values) for name, values in steps.items()}


def _snippet(
    snippet_fn: SnippetProvider | None,
    statement: StatementModel,
) -> object | None:
    if snippet_fn is None:
        return None
    return snippet_fn(statement.source_file, statement.span)


def _read_keys(statement: StatementModel) -> tuple[tuple[str, ...], ...]:
    produced = frozenset(statement.produced_keys)
    return tuple(sorted(key for key in statement.referenced_keys if key not in produced))


def _block_identity(statement: StatementModel) -> tuple[str | None, str | None]:
    if not statement.key or statement.key[0] not in {"equation", "sequence"}:
        return None, None
    return str(statement.key[0]), str(statement.key[1])


def _diff_module_statement_lists(
    official_module: ModuleModel,
    draft_module: ModuleModel,
    *,
    snippet_fn: SnippetProvider | None,
) -> list[ChangeChange]:
    changes: list[ChangeChange] = []
    symbol = _module_symbol(official_module.module_path)

    official_by_key = {statement.key: statement for statement in official_module.statements}
    draft_by_key = {statement.key: statement for statement in draft_module.statements}

    official_counts = Counter(statement.fingerprint for statement in official_module.statements)
    draft_counts = Counter(statement.fingerprint for statement in draft_module.statements)
    added = draft_counts - official_counts
    removed = official_counts - draft_counts

    for fingerprint, count in added.items():
        for statement in draft_module.statements:
            if statement.fingerprint == fingerprint:
                if statement.key in official_by_key and official_by_key[statement.key].fingerprint != fingerprint:
                    continue
                changes.append(
                    _added_or_removed_change(
                        official_module,
                        statement,
                        kind=ChangeKind.ADDED,
                        detail="Statement added",
                        snippet_fn=snippet_fn,
                    )
                )
                count -= 1
                if count <= 0:
                    break

    for fingerprint, count in removed.items():
        for statement in official_module.statements:
            if statement.fingerprint == fingerprint:
                if statement.key in draft_by_key and draft_by_key[statement.key].fingerprint != fingerprint:
                    continue
                changes.append(
                    _added_or_removed_change(
                        official_module,
                        statement,
                        kind=ChangeKind.REMOVED,
                        detail="Statement removed",
                        snippet_fn=snippet_fn,
                    )
                )
                count -= 1
                if count <= 0:
                    break

    for key in sorted(official_by_key, key=str):
        official_statement = official_by_key[key]
        draft_statement = draft_by_key.get(key)
        if draft_statement is None:
            continue
        if official_statement.fingerprint == draft_statement.fingerprint:
            continue
        kind = _classify_statement_change(official_statement, draft_statement)
        sequence_name, previous_state, next_state, containing_state = _structural_context(draft_statement, draft_module)
        block_kind, block_name = _block_identity(draft_statement)
        changes.append(
            ChangeChange(
                symbol=symbol,
                module_path=official_module.module_path,
                kind=kind,
                detail=_statement_detail(official_statement, kind),
                official=_snippet(snippet_fn, official_statement),
                draft=_snippet(snippet_fn, draft_statement),
                location=_to_location(official_statement.source_file, official_statement.span),
                draft_location=_to_location(draft_statement.source_file, draft_statement.span),
                statement_context=_statement_context_label(official_statement.key),
                read_keys=_read_keys(draft_statement),
                produced_keys=draft_statement.produced_keys,
                sequence_name=sequence_name,
                previous_state=previous_state,
                next_state=next_state,
                containing_state=containing_state,
                block_kind=block_kind,
                block_name=block_name,
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
    for sequence_name in sorted(set(official_steps) | set(draft_steps)):
        official_names = official_steps.get(sequence_name, frozenset())
        draft_names = draft_steps.get(sequence_name, frozenset())
        for step_name in sorted(draft_names - official_names):
            changes.append(
                ChangeChange(
                    symbol=symbol,
                    module_path=official_module.module_path,
                    kind=ChangeKind.S88_CHANGED,
                    detail=f"Step {step_name!r} added to sequence {sequence_name!r}",
                    draft=step_name,
                )
            )
        for step_name in sorted(official_names - draft_names):
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
    if official_statement.node_type == "transition" or draft_statement.node_type == "transition":
        return ChangeKind.TRANSITION_CHANGED
    official_shape = statement_shape(official_statement.fingerprint)
    draft_shape = statement_shape(draft_statement.fingerprint)
    if official_shape == draft_shape:
        return ChangeKind.EXPRESSION_CHANGED
    return ChangeKind.STATEMENT_CHANGED


def _statement_detail(statement: StatementModel, kind: ChangeKind) -> str:
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
            mapping[module.module_path] = module.code_source_id
    return mapping


def _diff_calls(
    official: VersionSnapshot,
    draft: VersionSnapshot,
) -> list[ChangeChange]:
    official_by_module: dict[tuple[str, ...], set[str]] = {}
    for occurrence in official.snapshot.call_signatures:
        official_by_module.setdefault(tuple(occurrence.module_path), set()).add(occurrence.name.casefold())
    draft_by_module: dict[tuple[str, ...], set[str]] = {}
    for occurrence in draft.snapshot.call_signatures:
        draft_by_module.setdefault(tuple(occurrence.module_path), set()).add(occurrence.name.casefold())

    code_source = _code_source_by_path(official, draft)
    seen_sources: set[int] = set()
    changes: list[ChangeChange] = []
    for module_path in sorted(set(official_by_module) | set(draft_by_module)):
        source = code_source.get(module_path)
        if source is not None and module_path in official_by_module and module_path in draft_by_module:
            if source in seen_sources:
                continue
            seen_sources.add(source)
        official_calls = official_by_module.get(module_path, set())
        draft_calls = draft_by_module.get(module_path, set())
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
        module.module_path: module.dependency_keys for module in official.code_model.modules
    }
    draft_keys: dict[tuple[str, ...], frozenset[tuple[str, ...]]] = {
        module.module_path: module.dependency_keys for module in draft.code_model.modules
    }

    code_source = _code_source_by_path(official, draft)
    seen_sources: set[int] = set()
    changes: list[ChangeChange] = []
    for module_path in sorted(set(official_keys) | set(draft_keys)):
        source = code_source.get(module_path)
        if source is not None and module_path in official_keys and module_path in draft_keys:
            if source in seen_sources:
                continue
            seen_sources.add(source)
        official_deps = official_keys.get(module_path, frozenset())
        draft_deps = draft_keys.get(module_path, frozenset())
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

    official_modules = {module.module_path: module for module in official.code_model.modules}
    draft_modules = {module.module_path: module for module in draft.code_model.modules}
    seen_code_sources: set[int] = set()

    for module_path in sorted(set(official_modules) | set(draft_modules)):
        official_module = official_modules.get(module_path)
        draft_module = draft_modules.get(module_path)
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

    changes.extend(_diff_calls(official, draft))
    changes.extend(_diff_dependencies(official, draft))

    changes.sort(key=lambda change: (change.module_path, change.symbol, change.kind.value))
    return changes
