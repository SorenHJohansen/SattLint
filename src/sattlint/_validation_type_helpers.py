"""Pure datatype predicates, type inference, and type-matching helpers for SattLine validation."""

from __future__ import annotations

import re
from collections.abc import Sequence as AbcSequence

from sattline_parser.models.ast_model import (
    FloatLiteral,
    IntLiteral,
    Simple_DataType,
    Variable,
)

from .casefolding import is_anytype_name
from .grammar import constants as const
from .resolution.type_graph import TypeGraph

_PLAIN_DURATION_LITERAL_RE = re.compile(r"\d+(?:\.\d+)?")
_DURATION_COMPONENT_PATTERNS = (
    re.compile(r"\d+d", re.IGNORECASE),
    re.compile(r"\d+h", re.IGNORECASE),
    re.compile(r"\d+m(?!s)", re.IGNORECASE),
    re.compile(r"\d+(?:\.\d+)?s", re.IGNORECASE),
    re.compile(r"\d+ms", re.IGNORECASE),
)
_TIME_LITERAL_RE = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}\.\d{3}")
_TYPO_SUGGESTION_MAX_DISTANCE = 2


def _is_duration_datatype(datatype: Simple_DataType | str | None) -> bool:
    if isinstance(datatype, Simple_DataType):
        return datatype == Simple_DataType.DURATION
    return isinstance(datatype, str) and datatype.casefold() == Simple_DataType.DURATION.value


def _is_time_datatype(datatype: Simple_DataType | str | None) -> bool:
    if isinstance(datatype, Simple_DataType):
        return datatype == Simple_DataType.TIME
    return isinstance(datatype, str) and datatype.casefold() == Simple_DataType.TIME.value


def _is_valid_duration_literal(value: object) -> bool:
    if not isinstance(value, str):
        return False

    text = value.strip()
    if not text:
        return False

    if text[0] in "+-":
        text = text[1:]
    if not text:
        return False

    if _PLAIN_DURATION_LITERAL_RE.fullmatch(text):
        return True

    position = 0
    matched_component = False
    for pattern in _DURATION_COMPONENT_PATTERNS:
        match = pattern.match(text, position)
        if match is None:
            continue
        matched_component = True
        position = match.end()

    return matched_component and position == len(text)


def _has_time_literal_marker(value: object) -> bool:
    return isinstance(value, dict) and const.GRAMMAR_VALUE_TIME_VALUE in value


def _extract_time_literal(value: object) -> str | None:
    if not isinstance(value, dict) or const.GRAMMAR_VALUE_TIME_VALUE not in value:
        return None
    literal = value.get(const.GRAMMAR_VALUE_TIME_VALUE)
    return literal if isinstance(literal, str) else None


def _is_valid_time_literal(value: object) -> bool:
    return isinstance(value, str) and _TIME_LITERAL_RE.fullmatch(value.strip()) is not None


def _bounded_levenshtein(left: str, right: str, *, max_distance: int = _TYPO_SUGGESTION_MAX_DISTANCE) -> int | None:
    left_cf = left.casefold()
    right_cf = right.casefold()

    if left_cf == right_cf:
        return 0
    if abs(len(left_cf) - len(right_cf)) > max_distance:
        return None

    previous = list(range(len(right_cf) + 1))
    for row_index, left_char in enumerate(left_cf, start=1):
        current = [row_index]
        row_min = current[0]
        for col_index, right_char in enumerate(right_cf, start=1):
            cost = 0 if left_char == right_char else 1
            current_value = min(
                previous[col_index] + 1,
                current[col_index - 1] + 1,
                previous[col_index - 1] + cost,
            )
            current.append(current_value)
            row_min = min(row_min, current_value)
        if row_min > max_distance:
            return None
        previous = current

    distance = previous[-1]
    return distance if distance <= max_distance else None


def _suggest_datatype_name(name: str, known_datatypes: AbcSequence[str]) -> str | None:
    best_match: str | None = None
    best_distance: int | None = None
    name_cf = name.casefold()
    for candidate in known_datatypes:
        distance = _bounded_levenshtein(name, candidate, max_distance=_TYPO_SUGGESTION_MAX_DISTANCE)
        if distance is None:
            continue
        # Skip candidates that are a strict prefix of the unknown name.
        # Such names are extensions of the candidate (e.g. 'Timer' extends 'time'),
        # not misspellings of it.
        candidate_cf = candidate.casefold()
        if name_cf.startswith(candidate_cf):
            continue
        if best_distance is None or distance < best_distance:
            best_match = candidate
            best_distance = distance
    return best_match


_BUILTIN_DATATYPE_NAMES = tuple(datatype.value for datatype in Simple_DataType)


def _is_anytype_datatype(datatype: Simple_DataType | str | None) -> bool:
    return is_anytype_name(datatype)


def _split_dotted_name(name: str) -> tuple[str, tuple[str, ...]]:
    parts = tuple(part for part in str(name).split(".") if part)
    if not parts:
        return "", ()
    return parts[0], parts[1:]


def _resolve_variable_field_datatype(
    variable: Variable,
    field_path: tuple[str, ...],
    type_graph: TypeGraph,
) -> Simple_DataType | str | None:
    current: Simple_DataType | str = variable.datatype
    for field_name in field_path:
        if isinstance(current, Simple_DataType):
            return None
        field = type_graph.field(str(current), field_name)
        if field is None:
            return None
        current = field.datatype
    return current


def _infer_literal_datatype(
    value: object,
    *,
    is_duration: bool = False,
) -> Simple_DataType | str | None:
    if isinstance(value, bool):
        return Simple_DataType.BOOLEAN
    if isinstance(value, IntLiteral | int) and not isinstance(value, bool):
        return Simple_DataType.INTEGER
    if isinstance(value, FloatLiteral | float):
        return Simple_DataType.REAL
    if is_duration and isinstance(value, str) and _is_valid_duration_literal(value):
        return Simple_DataType.DURATION
    if isinstance(value, str):
        return Simple_DataType.STRING
    if isinstance(value, dict) and const.GRAMMAR_VALUE_TIME_VALUE in value:
        return const.GRAMMAR_VALUE_TIME_VALUE
    return None


def _literal_matches_expected_datatype(
    literal: object,
    expected: Simple_DataType | str | None,
    *,
    is_duration: bool = False,
) -> bool:
    if _has_time_literal_marker(literal) and not _is_valid_time_literal(_extract_time_literal(literal)):
        return False

    actual = _infer_literal_datatype(literal, is_duration=is_duration)
    if _assignment_type_matches(actual, expected):
        return True

    return (isinstance(literal, str) and _is_duration_datatype(expected) and _is_valid_duration_literal(literal)) or (
        isinstance(literal, str) and _is_time_datatype(expected) and _is_valid_time_literal(literal)
    )


_STRING_SIMPLE_TYPES = {
    Simple_DataType.IDENTSTRING,
    Simple_DataType.TAGSTRING,
    Simple_DataType.STRING,
    Simple_DataType.LINESTRING,
    Simple_DataType.MAXSTRING,
}


def _format_datatype(datatype: Simple_DataType | str | None) -> str:
    if datatype is None:
        return "unknown"
    if isinstance(datatype, Simple_DataType):
        return datatype.value
    return str(datatype)


def _is_string_simple_type(datatype: Simple_DataType | str | None) -> bool:
    return isinstance(datatype, Simple_DataType) and datatype in _STRING_SIMPLE_TYPES


def _normalize_builtin_datatype(datatype: str) -> Simple_DataType | str:
    try:
        return Simple_DataType.from_any(datatype)
    except ValueError:
        return datatype


def _resolve_ref_datatype(
    ref: dict[str, object],
    env: dict[str, Variable],
    type_graph: TypeGraph,
) -> Simple_DataType | str | None:
    full_name = str(ref[const.KEY_VAR_NAME])
    parts = [part for part in full_name.split(".") if part]
    if not parts:
        return None

    variable = env.get(parts[0].casefold())
    if variable is None:
        return None

    current: Simple_DataType | str = variable.datatype
    for field_name in parts[1:]:
        if isinstance(current, Simple_DataType):
            return None

        field = type_graph.field(str(current), field_name)
        if field is None:
            return None
        current = field.datatype

    return current


def _resolve_root_variable(ref: dict[str, object], env: dict[str, Variable]) -> Variable | None:
    full_name = str(ref.get(const.KEY_VAR_NAME, ""))
    base_name, _field_path = _split_dotted_name(full_name)
    if not base_name:
        return None
    return env.get(base_name.casefold())


def _merge_numeric_types(
    datatypes: AbcSequence[Simple_DataType | str | None],
) -> Simple_DataType | None:
    numeric_types = {Simple_DataType.INTEGER, Simple_DataType.REAL}
    if not datatypes or any(dt not in numeric_types for dt in datatypes):
        return None
    if Simple_DataType.REAL in datatypes:
        return Simple_DataType.REAL
    return Simple_DataType.INTEGER


def _is_numeric_datatype(datatype: Simple_DataType | str | None) -> bool:
    return datatype in {Simple_DataType.INTEGER, Simple_DataType.REAL}


def _is_boolean_datatype(datatype: Simple_DataType | str | None) -> bool:
    return datatype == Simple_DataType.BOOLEAN


def _merge_compatible_types(
    datatypes: AbcSequence[Simple_DataType | str | None],
) -> Simple_DataType | str | None:
    filtered = [dt for dt in datatypes if dt is not None]
    if not filtered:
        return None

    first = filtered[0]
    if all(dt == first for dt in filtered[1:]):
        return first

    numeric = _merge_numeric_types(filtered)
    if numeric is not None:
        return numeric

    if all(_is_string_simple_type(dt) for dt in filtered):
        return Simple_DataType.STRING

    return None


def _expression_is_zero_literal(node: object) -> bool:
    if isinstance(node, IntLiteral | int) and not isinstance(node, bool):
        return int(node) == 0
    if isinstance(node, FloatLiteral | float):
        return float(node) == 0.0
    if isinstance(node, tuple) and len(node) == 2 and node[0] in {const.KEY_PLUS, const.KEY_MINUS}:
        return _expression_is_zero_literal(node[1])
    return False


def _builtin_type_matches(
    actual: Simple_DataType | str,
    expected: Simple_DataType | str,
    *,
    direction: str,
) -> bool:
    if is_anytype_name(expected):
        return True

    if isinstance(expected, Simple_DataType):
        if not isinstance(actual, Simple_DataType):
            return False

        if actual == expected:
            return True

        if _is_string_simple_type(actual) and _is_string_simple_type(expected):
            return True

        return bool(direction == "in" and expected == Simple_DataType.REAL and actual == Simple_DataType.INTEGER)

    if isinstance(actual, str):
        return actual.casefold() == expected.casefold()

    return False


def _assignment_type_matches(
    actual: Simple_DataType | str | None,
    expected: Simple_DataType | str | None,
) -> bool:
    if actual is None or expected is None:
        return True

    if is_anytype_name(expected):
        return True

    if actual == const.GRAMMAR_VALUE_TIME_VALUE:
        return expected in {Simple_DataType.TIME, Simple_DataType.DURATION}

    if isinstance(expected, Simple_DataType):
        if not isinstance(actual, Simple_DataType):
            return False
        return _builtin_type_matches(actual, expected, direction="in")

    if isinstance(actual, Simple_DataType):
        return False

    return str(actual).casefold() == str(expected).casefold()
