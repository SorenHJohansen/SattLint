"""Local document parser adapters for LSP document state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lark.exceptions import VisitError
from lsprotocol.types import Diagnostic, DiagnosticSeverity, Position, Range

from sattline_parser.api import create_parser
from sattline_parser.transformer.sl_transformer import SLTransformer
from sattline_parser.utils.text_processing import strip_sl_comments
from sattlint.editor_api import SemanticSnapshot, build_source_snapshot_from_basepicture
from sattlint.engine import StructuralValidationError, parse_source_text, validate_transformed_basepicture
from sattlint.models.ast_model import BasePicture
from sattlint.utils.text_processing import find_disallowed_comments

_MAX_SYNTAX_DIAGNOSTICS = 8
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


def _diagnostic_from_message(message: str, line: int | None, column: int | None) -> Diagnostic:
    if line is None or column is None:
        range_ = Range(start=Position(line=0, character=0), end=Position(line=0, character=1))
    else:
        range_ = _range_from_position(line, column, 1)
    return Diagnostic(range=range_, message=message, severity=DiagnosticSeverity.Error, source="sattlint")


def _mask_line_for_reparse(text: str, line_number: int | None) -> str:
    if line_number is None or line_number < 1:
        return text

    lines = text.splitlines(keepends=True)
    if line_number > len(lines):
        return text

    original_line = lines[line_number - 1]
    line_body = original_line
    line_ending = ""
    if original_line.endswith("\r\n"):
        line_body = original_line[:-2]
        line_ending = "\r\n"
    elif original_line.endswith("\n") or original_line.endswith("\r"):
        line_body = original_line[:-1]
        line_ending = original_line[-1]

    if not line_body:
        return text

    lines[line_number - 1] = (" " * len(line_body)) + line_ending
    return "".join(lines)


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


def _collect_parse_diagnostics(text: str, *, limit: int = _MAX_SYNTAX_DIAGNOSTICS) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[int, int, str]] = set()
    candidate = text

    for _ in range(limit):
        should_continue = True
        try:
            parse_source_text(candidate)
            break
        except VisitError as exc:
            line, column = _extract_error_position(exc)
            message = str(exc.orig_exc) if exc.orig_exc is not None else str(exc)
        except StructuralValidationError as exc:
            line, column = _extract_error_position(exc)
            message = str(exc)
            should_continue = False
        except Exception as exc:
            line, column = _extract_error_position(exc)
            message = str(exc)

        diagnostic = _diagnostic_from_message(message, line, column)
        if not _append_unique_diagnostic(diagnostics, seen, diagnostic):
            break
        if not should_continue:
            break

        masked = _mask_line_for_reparse(candidate, line)
        if masked == candidate:
            break
        candidate = masked

    return diagnostics


def _line_start_offset(text: str, zero_based_line: int) -> int:
    if zero_based_line <= 0:
        return 0

    offset = 0
    for index, line in enumerate(text.splitlines(keepends=True)):
        if index >= zero_based_line:
            break
        offset += len(line)
    return min(offset, len(text))


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

    def _capture_checkpoint(self, cursor) -> _ParseCheckpoint:
        line_counter = cursor.lexer_state.state.line_ctr
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
        cursor.lexer_state.state.text = cleaned_text
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
            assert previous_state is not None
            checkpoint_index, checkpoint = selected
            cursor = self._resume_cursor(checkpoint, cleaned_text)
            checkpoints = list(previous_state.checkpoints[: checkpoint_index + 1])
            reused_prefix_char_pos = checkpoint.char_pos
            reused_prefix_line = checkpoint.line

        tokens_since_checkpoint = 0
        for token in cursor.lexer_state.lex(cursor.parser_state):
            cursor.feed_token(token)
            tokens_since_checkpoint += 1
            current_line = int(cursor.lexer_state.state.line_ctr.line)
            if current_line > checkpoints[-1].line:
                self._append_checkpoint_if_advanced(checkpoints, cursor)
                tokens_since_checkpoint = 0
                continue
            if tokens_since_checkpoint >= self._checkpoint_token_interval:
                self._append_checkpoint_if_advanced(checkpoints, cursor)
                tokens_since_checkpoint = 0

        parse_tree = cursor.feed_eof()
        base_picture = SLTransformer().transform(parse_tree)
        validate_transformed_basepicture(base_picture)
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
        except Exception:
            for diagnostic in _collect_parse_diagnostics(text):
                _append_unique_diagnostic(diagnostics, seen, diagnostic)
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)

        if not build_snapshot:
            return DocumentParseResult(
                syntax_diagnostics=tuple(diagnostics),
                local_snapshot=None,
                adapter_state=state,
            )

        try:
            snapshot = build_source_snapshot_from_basepicture(state.base_picture, document_path)
        except Exception:
            for diagnostic in _collect_parse_diagnostics(text):
                _append_unique_diagnostic(diagnostics, seen, diagnostic)
            return DocumentParseResult(syntax_diagnostics=tuple(diagnostics), local_snapshot=None)

        return DocumentParseResult(
            syntax_diagnostics=tuple(diagnostics),
            local_snapshot=snapshot,
            adapter_state=state,
        )


FullDocumentParserAdapter = IncrementalDocumentParserAdapter
