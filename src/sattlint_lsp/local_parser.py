"""Local document parser adapters for LSP document state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lark.exceptions import UnexpectedInput, VisitError
from lsprotocol.types import Diagnostic, DiagnosticSeverity, Position, Range

from sattline_parser.api import create_parser, describe_parse_error
from sattline_parser.transformer.sl_transformer import SLTransformer
from sattline_parser.utils.text_processing import strip_sl_comments
from sattlint.core.ast_tools import iter_variable_refs
from sattlint.core.document import LineIndex
from sattlint.editor_api import SemanticSnapshot, build_source_snapshot_from_basepicture
from sattlint.graphics_validation import validate_graphics_text
from sattlint.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    Sequence,
    SFCAlternative,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransitionSub,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattlint.utils.text_processing import find_disallowed_comments

_CHECKPOINT_TOKEN_INTERVAL = 64


def _extract_error_position(exc: Exception) -> tuple[int | None, int | None]:
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if isinstance(exc, VisitError) and exc.orig_exc is not None:
        line = line if line is not None else getattr(exc.orig_exc, "line", None)
        column = column if column is not None else getattr(exc.orig_exc, "column", None)
    return line, column


def _range_from_position(line: int, column: int, length: int) -> Range:
    start = Position(line=max(line - 1, 0), character=max(column - 1, 0))
    end = Position(line=max(line - 1, 0), character=max(column - 1 + max(length, 1), 0))
    return Range(start=start, end=end)


def _diagnostic_from_message(
    message: str,
    line: int | None,
    column: int | None,
    length: int = 1,
    *,
    severity: DiagnosticSeverity = DiagnosticSeverity.Error,
) -> Diagnostic:
    if line is None or column is None:
        range_ = Range(start=Position(line=0, character=0), end=Position(line=0, character=1))
    else:
        range_ = _range_from_position(line, column, length)
    return Diagnostic(range=range_, message=message, severity=severity, source="sattlint")


def _append_unique_diagnostic(
    diagnostics: list[Diagnostic],
    seen: set[tuple[int, int, str]],
    diagnostic: Diagnostic,
) -> bool:
    key = (
        diagnostic.range.start.line,
        diagnostic.range.start.character,
        diagnostic.message,
    )
    if key in seen:
        return False
    seen.add(key)
    diagnostics.append(diagnostic)
    return True


def _merge_env(parent_env: dict[str, Variable], variables: list[Variable] | None) -> dict[str, Variable]:
    merged = dict(parent_env)
    for variable in variables or []:
        merged[variable.name.casefold()] = variable
    return merged


def _split_dotted_name(name: str) -> tuple[str, tuple[str, ...]]:
    parts = tuple(part for part in str(name).split(".") if part)
    if not parts:
        return "", ()
    return parts[0], parts[1:]


def _collect_sequence_step_features(
    nodes: list[object],
    *,
    seqcontrol: bool,
    seqtimer: bool,
    known_steps: dict[str, str],
    available_features: dict[str, set[str]],
) -> None:
    for node in nodes or []:
        if isinstance(node, SFCStep):
            key = node.name.casefold()
            known_steps.setdefault(key, node.name)
            feature_set = available_features.setdefault(key, set())
            feature_set.add("x")
            if seqcontrol:
                feature_set.add("hold")
                feature_set.add("reset")
            if seqtimer:
                feature_set.add("t")
            continue

        if isinstance(node, SFCAlternative | SFCParallel):
            for branch in node.branches or []:
                _collect_sequence_step_features(
                    branch,
                    seqcontrol=seqcontrol,
                    seqtimer=seqtimer,
                    known_steps=known_steps,
                    available_features=available_features,
                )
            continue

        if isinstance(node, SFCSubsequence | SFCTransitionSub):
            _collect_sequence_step_features(
                node.body,
                seqcontrol=seqcontrol,
                seqtimer=seqtimer,
                known_steps=known_steps,
                available_features=available_features,
            )


def _collect_step_auto_variable_diagnostics_for_modulecode(
    modulecode: ModuleCode | None,
    env: dict[str, Variable],
    diagnostics: list[Diagnostic],
    seen: set[tuple[int, int, str]],
) -> None:
    if modulecode is None:
        return

    known_steps: dict[str, str] = {}
    available_features: dict[str, set[str]] = {}
    for sequence in modulecode.sequences or []:
        if not isinstance(sequence, Sequence):
            continue
        _collect_sequence_step_features(
            sequence.code or [],
            seqcontrol=bool(sequence.seqcontrol),
            seqtimer=bool(sequence.seqtimer),
            known_steps=known_steps,
            available_features=available_features,
        )

    if not known_steps:
        return

    for ref in iter_variable_refs(modulecode):
        full_name = ref.get("var_name")
        span = ref.get("span")
        if not isinstance(full_name, str) or not isinstance(span, SourceSpan):
            continue

        base_name, field_path = _split_dotted_name(full_name)
        if not base_name or len(field_path) != 1:
            continue

        suffix = field_path[0].casefold()
        if suffix not in {"hold", "reset", "t", "x"}:
            continue

        if base_name.casefold() in env:
            continue

        step_name = known_steps.get(base_name.casefold())
        if step_name is None:
            message = f"{full_name!r} is not available: no sequence step named {base_name!r} exists in this module"
        else:
            feature_set = available_features.get(base_name.casefold(), set())
            if suffix == "hold" and "hold" not in feature_set:
                message = f"{full_name!r} is not available: step {step_name!r} only exposes .Hold when its sequence enables SeqControl"
            elif suffix == "reset" and "reset" not in feature_set:
                message = f"{full_name!r} is not available: step {step_name!r} only exposes .Reset when its sequence enables SeqControl"
            elif suffix == "t" and "t" not in feature_set:
                message = f"{full_name!r} is not available: step {step_name!r} only exposes .T when its sequence enables SeqTimer"
            else:
                continue

        _append_unique_diagnostic(
            diagnostics,
            seen,
            _diagnostic_from_message(message, span.line, span.column, len(full_name)),
        )


def _collect_step_auto_variable_diagnostics_for_single(
    module: SingleModule,
    parent_env: dict[str, Variable],
    diagnostics: list[Diagnostic],
    seen: set[tuple[int, int, str]],
) -> None:
    env = _merge_env(parent_env, module.moduleparameters)
    env = _merge_env(env, module.localvariables)
    _collect_step_auto_variable_diagnostics_for_modulecode(module.modulecode, env, diagnostics, seen)
    for child in module.submodules or []:
        _collect_step_auto_variable_diagnostics_for_module(child, env, diagnostics, seen)


def _collect_step_auto_variable_diagnostics_for_typedef(
    moduletype: ModuleTypeDef,
    parent_env: dict[str, Variable],
    diagnostics: list[Diagnostic],
    seen: set[tuple[int, int, str]],
) -> None:
    env = _merge_env(parent_env, moduletype.moduleparameters)
    env = _merge_env(env, moduletype.localvariables)
    _collect_step_auto_variable_diagnostics_for_modulecode(moduletype.modulecode, env, diagnostics, seen)
    for child in moduletype.submodules or []:
        _collect_step_auto_variable_diagnostics_for_module(child, env, diagnostics, seen)


def _collect_step_auto_variable_diagnostics_for_module(
    module: SingleModule | FrameModule | ModuleTypeInstance,
    parent_env: dict[str, Variable],
    diagnostics: list[Diagnostic],
    seen: set[tuple[int, int, str]],
) -> None:
    if isinstance(module, SingleModule):
        _collect_step_auto_variable_diagnostics_for_single(module, parent_env, diagnostics, seen)
        return

    if isinstance(module, FrameModule):
        _collect_step_auto_variable_diagnostics_for_modulecode(module.modulecode, parent_env, diagnostics, seen)
        for child in module.submodules or []:
            _collect_step_auto_variable_diagnostics_for_module(child, parent_env, diagnostics, seen)


def _collect_step_auto_variable_diagnostics(base_picture: BasePicture) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[int, int, str]] = set()
    root_env = {variable.name.casefold(): variable for variable in (base_picture.localvariables or [])}

    _collect_step_auto_variable_diagnostics_for_modulecode(
        base_picture.modulecode,
        root_env,
        diagnostics,
        seen,
    )

    for moduletype in base_picture.moduletype_defs or []:
        _collect_step_auto_variable_diagnostics_for_typedef(
            moduletype,
            root_env,
            diagnostics,
            seen,
        )

    for module in base_picture.submodules or []:
        _collect_step_auto_variable_diagnostics_for_module(module, root_env, diagnostics, seen)

    return tuple(diagnostics)


def _line_start_offset(text: str, zero_based_line: int) -> int:
    return LineIndex.from_text(text).line_start_offset(zero_based_line)


@dataclass(frozen=True, slots=True)
class _ParseCheckpoint:
    char_pos: int
    line: int
    column: int
    cursor: Any


@dataclass(frozen=True, slots=True)
class IncrementalParseState:
    cleaned_text: str
    checkpoints: tuple[_ParseCheckpoint, ...]
    base_picture: BasePicture
    reused_prefix_char_pos: int = 0
    reused_prefix_line: int = 1


@dataclass(frozen=True, slots=True)
class DocumentParseResult:
    syntax_diagnostics: tuple[Diagnostic, ...]
    local_snapshot: SemanticSnapshot | None = None
    adapter_state: object | None = None


class IncrementalDocumentParserAdapter:
    def __init__(self, *, checkpoint_token_interval: int = _CHECKPOINT_TOKEN_INTERVAL) -> None:
        self._parser = create_parser()
        self._checkpoint_token_interval = max(1, int(checkpoint_token_interval))

    def _cursor_lexer(self, cursor):
        lexer = getattr(cursor, "lexer_thread", None)
        if lexer is not None:
            return lexer
        return cursor.lexer_state

    def _capture_checkpoint(self, cursor) -> _ParseCheckpoint:
        line_counter = self._cursor_lexer(cursor).state.line_ctr
        return _ParseCheckpoint(
            char_pos=int(line_counter.char_pos),
            line=int(line_counter.line),
            column=int(line_counter.column),
            cursor=cursor.as_immutable(),
        )

    def _state_from_result(self, previous_result: DocumentParseResult | None) -> IncrementalParseState | None:
        if previous_result is None or not isinstance(previous_result.adapter_state, IncrementalParseState):
            return None
        return previous_result.adapter_state

    def _select_resume_checkpoint(
        self,
        state: IncrementalParseState,
        cleaned_text: str,
        changed_line_ranges: tuple[tuple[int, int], ...],
    ) -> tuple[int, _ParseCheckpoint] | None:
        if not changed_line_ranges:
            return None

        earliest_changed_line = min(start for start, _ in changed_line_ranges)
        resume_offset = _line_start_offset(cleaned_text, earliest_changed_line)
        selected_index = 0
        selected = state.checkpoints[0]
        for index, checkpoint in enumerate(state.checkpoints):
            if checkpoint.char_pos > resume_offset:
                break
            selected_index = index
            selected = checkpoint
        return selected_index, selected

    def _resume_cursor(self, checkpoint: _ParseCheckpoint, cleaned_text: str):
        cursor = checkpoint.cursor.as_mutable()
        lexer = self._cursor_lexer(cursor)
        text_slice_type = type(lexer.state.text)
        lexer.state.text = text_slice_type.cast_from(cleaned_text)
        return cursor

    def _append_checkpoint_if_advanced(self, checkpoints: list[_ParseCheckpoint], cursor) -> None:
        checkpoint = self._capture_checkpoint(cursor)
        previous = checkpoints[-1]
        if checkpoint.char_pos <= previous.char_pos:
            return
        checkpoints.append(checkpoint)

    def _parse_incrementally(
        self,
        cleaned_text: str,
        previous_state: IncrementalParseState | None,
        changed_line_ranges: tuple[tuple[int, int], ...],
    ) -> IncrementalParseState:
        reused_prefix_char_pos = 0
        reused_prefix_line = 1
        checkpoints: list[_ParseCheckpoint]

        if previous_state is not None and previous_state.checkpoints:
            selected = self._select_resume_checkpoint(previous_state, cleaned_text, changed_line_ranges)
        else:
            selected = None

        if selected is None:
            cursor = self._parser.parse_interactive(cleaned_text)
            checkpoints = [self._capture_checkpoint(cursor)]
        else:
            if previous_state is None:
                raise RuntimeError("missing previous parser state for checkpoint resume")
            checkpoint_index, checkpoint = selected
            cursor = self._resume_cursor(checkpoint, cleaned_text)
            checkpoints = list(previous_state.checkpoints[: checkpoint_index + 1])
            reused_prefix_char_pos = checkpoint.char_pos
            reused_prefix_line = checkpoint.line

        # Adaptive checkpoint interval: cap total checkpoints to ~10 regardless of file size.
        # Each checkpoint deep-copies Lark's value_stack (which grows as the file is parsed),
        # making per-line checkpointing prohibitively expensive for files >1000 lines.
        max_desired_checkpoints = 10
        clean_lines = cleaned_text.count("\n") + 1
        checkpoint_line_interval = max(1, clean_lines // max_desired_checkpoints)
        lexer = self._cursor_lexer(cursor)

        for token in lexer.lex(cursor.parser_state):
            cursor.feed_token(token)
            current_line = int(lexer.state.line_ctr.line)
            if current_line >= checkpoints[-1].line + checkpoint_line_interval:
                self._append_checkpoint_if_advanced(checkpoints, cursor)

        parse_tree = cursor.feed_eof()
        base_picture = SLTransformer().transform(parse_tree)
        return IncrementalParseState(
            cleaned_text=cleaned_text,
            checkpoints=tuple(checkpoints),
            base_picture=base_picture,
            reused_prefix_char_pos=reused_prefix_char_pos,
            reused_prefix_line=reused_prefix_line,
        )

    def analyze(
        self,
        document_path: Path,
        text: str,
        *,
        include_comment_validation: bool = True,
        build_snapshot: bool = True,
        previous_result: DocumentParseResult | None = None,
        changed_line_ranges: tuple[tuple[int, int], ...] = (),
    ) -> DocumentParseResult:
        diagnostics: list[Diagnostic] = []
        seen: set[tuple[int, int, str]] = set()

        if document_path.suffix.lower() == ".g":
            result = validate_graphics_text(text, document_path)
            for message in result.messages:
                _append_unique_diagnostic(
                    diagnostics,
                    seen,
                    _diagnostic_from_message(
                        message.message,
                        message.line,
                        message.column,
                        message.length,
                        severity=(
                            DiagnosticSeverity.Warning if message.severity == "warning" else DiagnosticSeverity.Error
                        ),
                    ),
                )
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)

        if include_comment_validation:
            violations = find_disallowed_comments(text)
            for violation in violations:
                diagnostic = _diagnostic_from_message(
                    "comment is only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks",
                    violation.start_line,
                    violation.start_col,
                )
                _append_unique_diagnostic(diagnostics, seen, diagnostic)

        if diagnostics:
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)

        cleaned_text = strip_sl_comments(text)
        previous_state = self._state_from_result(previous_result)

        try:
            if previous_state is not None and previous_state.cleaned_text == cleaned_text and not changed_line_ranges:
                state = previous_state
            else:
                state = self._parse_incrementally(cleaned_text, previous_state, changed_line_ranges)
        except UnexpectedInput as exc:
            details = describe_parse_error(exc, cleaned_text)
            _append_unique_diagnostic(
                diagnostics,
                seen,
                _diagnostic_from_message(details.message, details.line, details.column),
            )
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)
        except VisitError as exc:
            line, column = _extract_error_position(exc)
            message = str(exc.orig_exc) if exc.orig_exc is not None else str(exc)
            _append_unique_diagnostic(diagnostics, seen, _diagnostic_from_message(message, line, column))
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)
        except Exception as exc:
            line, column = _extract_error_position(exc)
            _append_unique_diagnostic(diagnostics, seen, _diagnostic_from_message(str(exc), line, column))
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)

        for diagnostic in _collect_step_auto_variable_diagnostics(state.base_picture):
            _append_unique_diagnostic(diagnostics, seen, diagnostic)

        # Structural validation (validate_transformed_basepicture) is intentionally
        # omitted here: it requires full library context to be accurate and its
        # builtin-call walk is too slow for large library files. It still runs
        # in engine.parse_source_text / parse_source_file (CLI) and when the full
        # workspace snapshot is built on save.

        if not build_snapshot:
            return DocumentParseResult(
                syntax_diagnostics=tuple(diagnostics),
                local_snapshot=None,
                adapter_state=state,
            )

        try:
            snapshot = build_source_snapshot_from_basepicture(state.base_picture, document_path)
        except VisitError as exc:
            line, column = _extract_error_position(exc)
            message = str(exc.orig_exc) if exc.orig_exc is not None else str(exc)
            _append_unique_diagnostic(diagnostics, seen, _diagnostic_from_message(message, line, column))
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)
        except Exception as exc:
            line, column = _extract_error_position(exc)
            _append_unique_diagnostic(diagnostics, seen, _diagnostic_from_message(str(exc), line, column))
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)

        return DocumentParseResult(
            syntax_diagnostics=tuple(diagnostics),
            local_snapshot=snapshot,
            adapter_state=state,
        )


FullDocumentParserAdapter = IncrementalDocumentParserAdapter
