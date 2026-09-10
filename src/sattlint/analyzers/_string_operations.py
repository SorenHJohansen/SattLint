"""Cursor-aware string builtin semantics for exact string inference.

Pure result transformations: concatenation, insertion, trim/cut, extraction,
national-case transforms, copy, and the cursor position setters. These take
`StringInferenceResult` values as input and return new ones; they never touch
the module context or scope machinery (see `string_inference.py`).
"""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false, reportUnnecessaryIsInstance=false

from __future__ import annotations

from collections.abc import Callable, Iterable

from sattline_parser.models.ast_model import Simple_DataType

from ._string_models import (
    _MAX_CURSOR_POSITIONS,
    _MAX_OVERFLOW_EXAMPLES,
    _MAX_STRING_CANDIDATES,
    StringCandidate,
    StringInferenceResult,
    StringProvenanceSegment,
    _AbstractState,
    _IntResult,
    _ResolvedSlot,
    _string_capacity_for_datatype,
)


def _read_string_result(state: _AbstractState, slot: _ResolvedSlot) -> StringInferenceResult:
    return state.string_values.get(
        slot.key,
        _unknown_string_result(max_length=_string_capacity_for_datatype(slot.variable.datatype)),
    )


def _merge_state_into(target: _AbstractState, source: _AbstractState) -> None:
    for key, value in source.string_values.items():
        target.string_values[key] = _merge_string_results(target.string_values.get(key, StringInferenceResult()), value)
    for key, value in source.int_values.items():
        target.int_values[key] = _merge_int_results(target.int_values.get(key, _IntResult()), value)


def _merge_string_results(left: StringInferenceResult, right: StringInferenceResult) -> StringInferenceResult:
    candidates = _normalize_candidates([*left.candidates, *right.candidates])
    cursor_positions, cursor_overflow = _normalize_cursor_positions([*left.cursor_positions, *right.cursor_positions])
    return StringInferenceResult(
        candidates=candidates,
        cursor_positions=cursor_positions,
        max_length=_merge_max_lengths(left.max_length, right.max_length),
        unknown_text=left.unknown_text or right.unknown_text or len(candidates) >= _MAX_STRING_CANDIDATES,
        unknown_cursor=left.unknown_cursor or right.unknown_cursor or cursor_overflow,
        unknown_max_length=left.unknown_max_length or right.unknown_max_length,
        overflow_operations=_merge_overflow_operations(left.overflow_operations, right.overflow_operations),
        overflow_examples=_merge_overflow_examples(left.overflow_examples, right.overflow_examples),
    )


def _normalize_candidates(candidates: Iterable[StringCandidate]) -> tuple[StringCandidate, ...]:
    unique = {candidate: None for candidate in candidates if isinstance(candidate, StringCandidate)}
    ordered = sorted(unique.keys(), key=repr)
    return tuple(ordered[:_MAX_STRING_CANDIDATES])


def _normalize_cursor_positions(values: Iterable[int]) -> tuple[tuple[int, ...], bool]:
    unique = sorted({max(value, 1) for value in values if isinstance(value, int)})
    overflow = len(unique) > _MAX_CURSOR_POSITIONS
    return tuple(unique[:_MAX_CURSOR_POSITIONS]), overflow


def _normalize_int_result(result: _IntResult) -> _IntResult:
    values = tuple(sorted({value for value in result.values if isinstance(value, int)}))
    return _IntResult(
        values=values[:_MAX_CURSOR_POSITIONS], unknown=result.unknown or len(values) > _MAX_CURSOR_POSITIONS
    )


def _merge_int_results(left: _IntResult, right: _IntResult) -> _IntResult:
    return _normalize_int_result(
        _IntResult(values=(*left.values, *right.values), unknown=left.unknown or right.unknown)
    )


def _apply_int_operator(left: _IntResult, operator: str, right: _IntResult) -> _IntResult:
    if not left.values or not right.values:
        return _IntResult(unknown=left.unknown or right.unknown)
    values: list[int] = []
    for left_value in left.values:
        for right_value in right.values:
            if operator == "+":
                values.append(left_value + right_value)
            elif operator == "-":
                values.append(left_value - right_value)
            else:
                return _IntResult(unknown=True)
    return _normalize_int_result(_IntResult(tuple(values), left.unknown or right.unknown))


def _result_for_literal(
    text: str,
    *,
    source_kind: str,
    source_label: str | None,
    source_module_path: tuple[str, ...],
    max_length: int | None,
) -> StringInferenceResult:
    segment = StringProvenanceSegment(
        text=text,
        source_kind=source_kind,
        source_label=source_label,
        source_module_path=source_module_path,
    )
    return _with_end_cursor(
        StringInferenceResult(
            candidates=(StringCandidate(text=text, segments=(segment,)),),
            max_length=max_length,
            unknown_max_length=max_length is None,
        )
    )


def _with_end_cursor(result: StringInferenceResult) -> StringInferenceResult:
    cursor_positions, cursor_overflow = _normalize_cursor_positions(
        len(candidate.text) + 1 for candidate in result.candidates
    )
    return StringInferenceResult(
        candidates=result.candidates,
        cursor_positions=cursor_positions,
        max_length=result.max_length,
        unknown_text=result.unknown_text,
        unknown_cursor=result.unknown_cursor or result.unknown_text or cursor_overflow,
        unknown_max_length=result.unknown_max_length,
        overflow_operations=result.overflow_operations,
        overflow_examples=result.overflow_examples,
    )


def _retarget_string_result(
    source_result: StringInferenceResult,
    *,
    target_result: StringInferenceResult,
) -> StringInferenceResult:
    return StringInferenceResult(
        candidates=source_result.candidates,
        cursor_positions=source_result.cursor_positions,
        max_length=source_result.max_length,
        unknown_text=source_result.unknown_text,
        unknown_cursor=source_result.unknown_cursor,
        unknown_max_length=source_result.unknown_max_length,
        overflow_operations=target_result.overflow_operations,
        overflow_examples=target_result.overflow_examples,
    )


def _set_cursor_positions(result: StringInferenceResult, positions: _IntResult) -> StringInferenceResult:
    valid_positions = positions.values
    if result.max_length is not None:
        valid_positions = tuple(value for value in positions.values if 1 <= value <= result.max_length)
        if not valid_positions:
            return _preserve_unchanged(
                result,
                unknown_text=result.unknown_text,
                unknown_cursor=result.unknown_cursor or positions.unknown,
            )
    cursor_positions, cursor_overflow = _normalize_cursor_positions(valid_positions)
    return StringInferenceResult(
        candidates=result.candidates,
        cursor_positions=cursor_positions,
        max_length=result.max_length,
        unknown_text=result.unknown_text,
        unknown_cursor=result.unknown_cursor or positions.unknown or cursor_overflow,
        unknown_max_length=result.unknown_max_length,
        overflow_operations=result.overflow_operations,
        overflow_examples=result.overflow_examples,
    )


def _concatenate_results(
    left: StringInferenceResult,
    right: StringInferenceResult,
    *,
    target_result: StringInferenceResult,
    target_datatype: Simple_DataType | str | None,
) -> StringInferenceResult:
    candidates: list[StringCandidate] = []
    cursor_positions: list[int] = []
    overflow_examples: list[str] = []
    overflowed = False
    target_capacity = _string_capacity_for_datatype(target_datatype)
    for left_candidate in left.candidates:
        for right_candidate in right.candidates:
            moved_left = _substring_from_cursor(left_candidate, left.cursor_positions)
            moved_right = _substring_from_cursor(right_candidate, right.cursor_positions)
            for target_position in target_result.cursor_positions or (1,):
                write_start = max(target_position, 1) - 1
                inserted_segments = _merge_adjacent_segments((*moved_left[1], *moved_right[1]))
                fill_count = max(write_start, 0)
                prefix_text = "" if fill_count == 0 else " " * fill_count
                prefix_segments = () if fill_count == 0 else (_blank_segment(fill_count),)
                combined_text = prefix_text + moved_left[0] + moved_right[0]
                if target_capacity is not None and len(combined_text) > target_capacity:
                    overflowed = True
                    overflow_examples.append(combined_text)
                    continue
                candidates.append(
                    StringCandidate(
                        text=combined_text,
                        segments=_merge_adjacent_segments((*prefix_segments, *inserted_segments)),
                    )
                )
                cursor_positions.append(len(combined_text) + 1)

    if not candidates:
        return _preserve_unchanged(
            target_result,
            max_length=target_capacity,
            unknown_text=left.unknown_text or right.unknown_text,
            unknown_cursor=left.unknown_cursor or right.unknown_cursor or target_result.unknown_cursor,
            overflow_operations=("Concatenate",) if overflowed else (),
            overflow_examples=tuple(overflow_examples),
        )

    normalized_positions, cursor_overflow = _normalize_cursor_positions(cursor_positions)
    carried_operations, carried_examples = _carried_overflow_state(
        target_result,
        operations=("Concatenate",) if overflowed else (),
        examples=tuple(overflow_examples),
    )
    return StringInferenceResult(
        candidates=_normalize_candidates(candidates),
        cursor_positions=normalized_positions,
        max_length=target_capacity,
        unknown_text=left.unknown_text or right.unknown_text,
        unknown_cursor=left.unknown_cursor or right.unknown_cursor or target_result.unknown_cursor or cursor_overflow,
        unknown_max_length=target_capacity is None,
        overflow_operations=carried_operations,
        overflow_examples=carried_examples,
    )


def _insert_string_result(
    target: StringInferenceResult,
    source: StringInferenceResult,
    length_result: _IntResult,
    *,
    target_datatype: Simple_DataType | str | None,
    operation_name: str = "InsertString",
) -> StringInferenceResult:
    if not target.candidates or not source.candidates or not target.cursor_positions or not length_result.values:
        return _preserve_unchanged(
            target,
            max_length=_string_capacity_for_datatype(target_datatype),
            unknown_text=target.unknown_text or source.unknown_text or True,
            unknown_cursor=target.unknown_cursor or source.unknown_cursor or length_result.unknown or True,
        )

    candidates: list[StringCandidate] = []
    cursor_positions: list[int] = []
    overflow_examples: list[str] = []
    overflowed = False
    target_capacity = _string_capacity_for_datatype(target_datatype)
    for target_candidate in target.candidates:
        for cursor_position in target.cursor_positions:
            safe_position = min(max(cursor_position, 1), (target_capacity or len(target_candidate.text) + 1) + 1)
            insert_at = safe_position - 1
            for source_candidate in source.candidates:
                for requested_length in length_result.values:
                    insert_text = source_candidate.text[: max(requested_length, 0)]
                    if target_capacity is not None and insert_at > target_capacity:
                        overflowed = True
                        continue
                    padded_target = target_candidate.text
                    padded_segments = target_candidate.segments
                    if insert_at > len(target_candidate.text):
                        blank_count = insert_at - len(target_candidate.text)
                        if target_capacity is not None and len(target_candidate.text) + blank_count > target_capacity:
                            overflowed = True
                            continue
                        padded_target = target_candidate.text + (" " * blank_count)
                        padded_segments = _merge_adjacent_segments(
                            (*target_candidate.segments, _blank_segment(blank_count))
                        )
                    if target_capacity is not None and len(padded_target) + len(insert_text) > target_capacity:
                        overflowed = True
                        overflow_examples.append(padded_target[:insert_at] + insert_text + padded_target[insert_at:])
                        continue
                    inserted_segments = _slice_segments(source_candidate.segments, 0, len(insert_text))
                    new_segments = _merge_adjacent_segments(
                        (
                            *_slice_segments(padded_segments, 0, insert_at),
                            *inserted_segments,
                            *_slice_segments(padded_segments, insert_at, len(padded_target)),
                        )
                    )
                    new_text = padded_target[:insert_at] + insert_text + padded_target[insert_at:]
                    candidates.append(
                        StringCandidate(
                            text=new_text,
                            segments=new_segments,
                        )
                    )
                    cursor_positions.append(insert_at + len(insert_text) + 1)

    if not candidates:
        return _preserve_unchanged(
            target,
            max_length=target_capacity,
            unknown_text=target.unknown_text or source.unknown_text,
            unknown_cursor=target.unknown_cursor or source.unknown_cursor or length_result.unknown,
            overflow_operations=(operation_name,) if overflowed else (),
            overflow_examples=tuple(overflow_examples),
        )

    normalized_positions, cursor_overflow = _normalize_cursor_positions(cursor_positions)
    carried_operations, carried_examples = _carried_overflow_state(
        target,
        operations=(operation_name,) if overflowed else (),
        examples=tuple(overflow_examples),
    )
    return StringInferenceResult(
        candidates=_normalize_candidates(candidates),
        cursor_positions=normalized_positions,
        max_length=target_capacity,
        unknown_text=target.unknown_text or source.unknown_text,
        unknown_cursor=target.unknown_cursor or source.unknown_cursor or length_result.unknown or cursor_overflow,
        unknown_max_length=target_capacity is None,
        overflow_operations=carried_operations,
        overflow_examples=carried_examples,
    )


def _cut_string_result(target: StringInferenceResult, length_result: _IntResult) -> StringInferenceResult:
    if not target.candidates or not target.cursor_positions or not length_result.values:
        return _preserve_unchanged(
            target,
            unknown_text=target.unknown_text or True,
            unknown_cursor=target.unknown_cursor or length_result.unknown or True,
        )

    candidates: list[StringCandidate] = []
    for target_candidate in target.candidates:
        for cursor_position in target.cursor_positions:
            start = min(max(cursor_position, 1), len(target_candidate.text) + 1) - 1
            for requested_length in length_result.values:
                length = max(requested_length, 0)
                end = min(start + length, len(target_candidate.text))
                candidates.append(
                    StringCandidate(
                        text=target_candidate.text[:start] + target_candidate.text[end:],
                        segments=_merge_adjacent_segments(
                            (
                                *_slice_segments(target_candidate.segments, 0, start),
                                *_slice_segments(target_candidate.segments, end, len(target_candidate.text)),
                            )
                        ),
                    )
                )

    return StringInferenceResult(
        candidates=_normalize_candidates(candidates),
        cursor_positions=target.cursor_positions,
        max_length=target.max_length,
        unknown_text=target.unknown_text,
        unknown_cursor=target.unknown_cursor or length_result.unknown,
        unknown_max_length=target.unknown_max_length,
        overflow_operations=target.overflow_operations,
        overflow_examples=target.overflow_examples,
    )


def _put_blanks_result(
    target: StringInferenceResult,
    length_result: _IntResult,
    *,
    target_datatype: Simple_DataType | str | None,
) -> StringInferenceResult:
    if not length_result.values:
        return _preserve_unchanged(
            target,
            max_length=_string_capacity_for_datatype(target_datatype),
            unknown_text=target.unknown_text or True,
            unknown_cursor=target.unknown_cursor or length_result.unknown or True,
        )
    blank_source = _result_for_literal(
        " " * max(max(length_result.values), 0),
        source_kind="builtin",
        source_label="PutBlanks",
        source_module_path=(),
        max_length=max(max(length_result.values), 0),
    )
    return _insert_string_result(
        target,
        blank_source,
        length_result,
        target_datatype=target_datatype,
        operation_name="PutBlanks",
    )


def _extract_string_result(
    source: StringInferenceResult,
    length_result: _IntResult,
    *,
    target_result: StringInferenceResult,
    target_datatype: Simple_DataType | str | None,
    operation_name: str = "ExtractString",
) -> StringInferenceResult:
    if not source.candidates or not source.cursor_positions or not length_result.values:
        return _preserve_unchanged(
            target_result,
            max_length=_string_capacity_for_datatype(target_datatype),
            unknown_text=source.unknown_text or True,
            unknown_cursor=source.unknown_cursor or length_result.unknown or True,
        )
    target_capacity = _string_capacity_for_datatype(target_datatype)
    candidates: list[StringCandidate] = []
    overflow_examples: list[str] = []
    overflowed = False
    for source_candidate in source.candidates:
        for cursor_position in source.cursor_positions:
            start = min(max(cursor_position, 1), len(source_candidate.text) + 1) - 1
            for requested_length in length_result.values:
                length = max(requested_length, 0)
                end = min(start + length, len(source_candidate.text))
                new_text = source_candidate.text[start:end]
                if target_capacity is not None and len(new_text) > target_capacity:
                    overflowed = True
                    overflow_examples.append(new_text)
                    continue
                candidates.append(
                    StringCandidate(
                        text=new_text,
                        segments=_merge_adjacent_segments(_slice_segments(source_candidate.segments, start, end)),
                    )
                )
    if not candidates:
        return _preserve_unchanged(
            target_result,
            max_length=target_capacity,
            unknown_text=source.unknown_text,
            unknown_cursor=source.unknown_cursor or length_result.unknown,
            overflow_operations=(operation_name,) if overflowed else (),
            overflow_examples=tuple(overflow_examples),
        )

    carried_operations, carried_examples = _carried_overflow_state(
        target_result,
        operations=(operation_name,) if overflowed else (),
        examples=tuple(overflow_examples),
    )
    return StringInferenceResult(
        candidates=_normalize_candidates(candidates),
        cursor_positions=(1,),
        max_length=target_capacity,
        unknown_text=source.unknown_text,
        unknown_cursor=source.unknown_cursor or length_result.unknown,
        unknown_max_length=target_capacity is None,
        overflow_operations=carried_operations,
        overflow_examples=carried_examples,
    )


def _transform_string_result(
    source: StringInferenceResult,
    transform: Callable[[str], str],
    target_capacity: int | None,
    *,
    operation_name: str,
    target_result: StringInferenceResult,
) -> StringInferenceResult:
    candidates: list[StringCandidate] = []
    overflow_examples: list[str] = []
    overflowed = False
    for candidate in source.candidates:
        transformed_text = transform(candidate.text)
        if target_capacity is not None and len(transformed_text) > target_capacity:
            overflowed = True
            overflow_examples.append(transformed_text)
            continue
        candidates.append(
            StringCandidate(
                text=transformed_text,
                segments=(
                    StringProvenanceSegment(
                        text=transformed_text,
                        source_kind="builtin",
                        source_label="transform",
                        source_module_path=(),
                    ),
                ),
            )
        )
    if not candidates:
        return _preserve_unchanged(
            target_result,
            max_length=target_capacity,
            unknown_text=source.unknown_text,
            unknown_cursor=source.unknown_cursor,
            overflow_operations=(operation_name,) if overflowed else (),
            overflow_examples=tuple(overflow_examples),
        )

    carried_operations, carried_examples = _carried_overflow_state(
        target_result,
        operations=(operation_name,) if overflowed else (),
        examples=tuple(overflow_examples),
    )
    return _with_end_cursor(
        StringInferenceResult(
            candidates=_normalize_candidates(candidates),
            max_length=target_capacity,
            unknown_text=source.unknown_text,
            unknown_cursor=source.unknown_cursor,
            unknown_max_length=target_capacity is None,
            overflow_operations=carried_operations,
            overflow_examples=carried_examples,
        )
    )


def _copy_into_target(
    source_result: StringInferenceResult,
    target_datatype: Simple_DataType | str | None,
    *,
    operation_name: str = "CopyString",
    target_result: StringInferenceResult,
) -> StringInferenceResult:
    target_capacity = _string_capacity_for_datatype(target_datatype)
    overflow_examples = [
        candidate.text
        for candidate in source_result.candidates
        if target_capacity is not None and len(candidate.text) > target_capacity
    ]
    candidates = [
        candidate
        for candidate in source_result.candidates
        if target_capacity is None or len(candidate.text) <= target_capacity
    ]
    if not candidates:
        return _preserve_unchanged(
            target_result,
            max_length=target_capacity,
            unknown_text=source_result.unknown_text,
            unknown_cursor=source_result.unknown_cursor,
            overflow_operations=(operation_name,) if overflow_examples else (),
            overflow_examples=tuple(overflow_examples),
        )

    carried_operations, carried_examples = _carried_overflow_state(
        target_result,
        operations=(operation_name,) if overflow_examples else (),
        examples=tuple(overflow_examples),
    )
    return _with_end_cursor(
        StringInferenceResult(
            candidates=_normalize_candidates(candidates),
            max_length=target_capacity,
            unknown_text=source_result.unknown_text,
            unknown_cursor=source_result.unknown_cursor,
            unknown_max_length=target_capacity is None,
            overflow_operations=carried_operations,
            overflow_examples=carried_examples,
        )
    )


def _unknown_string_result(
    *,
    max_length: int | None = None,
    unknown_text: bool = True,
    unknown_cursor: bool = True,
) -> StringInferenceResult:
    return StringInferenceResult(
        max_length=max_length,
        unknown_text=unknown_text,
        unknown_cursor=unknown_cursor,
        unknown_max_length=max_length is None,
    )


def _preserve_unchanged(
    result: StringInferenceResult,
    *,
    max_length: int | None = None,
    unknown_text: bool,
    unknown_cursor: bool,
    overflow_operations: Iterable[str] = (),
    overflow_examples: Iterable[str] = (),
) -> StringInferenceResult:
    carried_operations, carried_examples = _carried_overflow_state(
        result,
        operations=tuple(overflow_operations),
        examples=tuple(overflow_examples),
    )
    return StringInferenceResult(
        candidates=result.candidates,
        cursor_positions=result.cursor_positions,
        max_length=result.max_length if max_length is None else max_length,
        unknown_text=unknown_text,
        unknown_cursor=unknown_cursor,
        unknown_max_length=result.unknown_max_length if max_length is None else False,
        overflow_operations=carried_operations,
        overflow_examples=carried_examples,
    )


def _merge_max_lengths(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _merge_overflow_operations(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for operation in group:
            key = operation.casefold()
            if not operation or key in seen:
                continue
            seen.add(key)
            merged.append(operation)
    return tuple(merged)


def _merge_overflow_examples(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for example in group:
            if not example or example in seen:
                continue
            seen.add(example)
            merged.append(example)
            if len(merged) >= _MAX_OVERFLOW_EXAMPLES:
                return tuple(merged)
    return tuple(merged)


def _carried_overflow_state(
    result: StringInferenceResult,
    *,
    operations: tuple[str, ...] = (),
    examples: tuple[str, ...] = (),
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        _merge_overflow_operations(result.overflow_operations, operations),
        _merge_overflow_examples(result.overflow_examples, examples),
    )


def _blank_segment(blank_count: int) -> StringProvenanceSegment:
    return StringProvenanceSegment(text=" " * blank_count, source_kind="builtin", source_label="blank_fill")


def _substring_from_cursor(
    candidate: StringCandidate,
    cursor_positions: tuple[int, ...],
) -> tuple[str, tuple[StringProvenanceSegment, ...]]:
    if not cursor_positions:
        return "", ()
    start = min(max(cursor_positions[0], 1), len(candidate.text) + 1) - 1
    return candidate.text[start:], _slice_segments(candidate.segments, start, len(candidate.text))


def _slice_segments(
    segments: tuple[StringProvenanceSegment, ...],
    start: int,
    end: int,
) -> tuple[StringProvenanceSegment, ...]:
    if start >= end:
        return ()
    index = 0
    sliced: list[StringProvenanceSegment] = []
    for segment in segments:
        next_index = index + len(segment.text)
        if next_index <= start:
            index = next_index
            continue
        if index >= end:
            break
        take_start = max(start - index, 0)
        take_end = min(end - index, len(segment.text))
        if take_start < take_end:
            sliced.append(
                StringProvenanceSegment(
                    text=segment.text[take_start:take_end],
                    source_kind=segment.source_kind,
                    source_label=segment.source_label,
                    source_module_path=segment.source_module_path,
                )
            )
        index = next_index
    return tuple(sliced)


def _merge_adjacent_segments(segments: tuple[StringProvenanceSegment, ...]) -> tuple[StringProvenanceSegment, ...]:
    merged: list[StringProvenanceSegment] = []
    for segment in segments:
        if not segment.text:
            continue
        if merged and _same_segment_origin(merged[-1], segment):
            previous = merged[-1]
            merged[-1] = StringProvenanceSegment(
                text=previous.text + segment.text,
                source_kind=previous.source_kind,
                source_label=previous.source_label,
                source_module_path=previous.source_module_path,
            )
            continue
        merged.append(segment)
    return tuple(merged)


def _same_segment_origin(left: StringProvenanceSegment, right: StringProvenanceSegment) -> bool:
    return (
        left.source_kind == right.source_kind
        and left.source_label == right.source_label
        and left.source_module_path == right.source_module_path
    )
