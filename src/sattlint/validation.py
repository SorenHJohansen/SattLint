"""Post-transform structural validation for SattLine ASTs."""
from __future__ import annotations

import re
from collections.abc import Callable
from collections.abc import Sequence as AbcSequence

from lark import Tree

from .analyzers.sattline_builtins import SATTLINE_BUILTINS
from .grammar import constants as const
from .models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FloatLiteral,
    FrameModule,
    IntLiteral,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from .resolution.type_graph import TypeGraph


class StructuralValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        length: int | None = None,
    ):
        super().__init__(message)
        self.line = line
        self.column = column
        self.length = length


class RawSourceValidationError(StructuralValidationError):
    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        length: int | None = None,
    ):
        super().__init__(message)
        self.line = line
        self.column = column
        self.length = length


_PLAIN_DURATION_LITERAL_RE = re.compile(r"\d+(?:\.\d+)?")
_DURATION_COMPONENT_PATTERNS = (
    re.compile(r"\d+d", re.IGNORECASE),
    re.compile(r"\d+h", re.IGNORECASE),
    re.compile(r"\d+m(?!s)", re.IGNORECASE),
    re.compile(r"\d+(?:\.\d+)?s", re.IGNORECASE),
    re.compile(r"\d+ms", re.IGNORECASE),
)
_TIME_LITERAL_RE = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}\.\d{3}")


def _identifier_length(name: str) -> int:
    if len(name) >= 2 and name.startswith("'") and name.endswith("'"):
        return len(name[1:-1])
    return len(name)


def _validate_identifier(name: str | None, context: str) -> None:
    if not name:
        return
    if _identifier_length(name) > 20:
        raise StructuralValidationError(
            f"{context} name {name!r} exceeds 20 characters"
        )


def _span_kwargs(span: SourceSpan | None) -> dict[str, int]:
    if span is None:
        return {}
    return {"line": span.line, "column": span.column}


def _warn_or_raise(
    message: str,
    *,
    warning_sink: Callable[[str], None] | None = None,
    line: int | None = None,
    column: int | None = None,
    length: int | None = None,
) -> None:
    if warning_sink is not None:
        warning_sink(message)
        return
    raise StructuralValidationError(
        message,
        line=line,
        column=column,
        length=length,
    )


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


def _ref_span(ref: dict[str, object] | str | None) -> SourceSpan | None:
    if not isinstance(ref, dict):
        return None
    span = ref.get("span")
    return span if isinstance(span, SourceSpan) else None


def _bounded_levenshtein(left: str, right: str, *, max_distance: int = 2) -> int | None:
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
        distance = _bounded_levenshtein(name, candidate, max_distance=2)
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
    return isinstance(datatype, str) and datatype.casefold() == "anytype"


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
    if isinstance(value, (IntLiteral, int)) and not isinstance(value, bool):
        return Simple_DataType.INTEGER
    if isinstance(value, (FloatLiteral, float)):
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

    return (
        isinstance(literal, str)
        and _is_duration_datatype(expected)
        and _is_valid_duration_literal(literal)
    ) or (
        isinstance(literal, str)
        and _is_time_datatype(expected)
        and _is_valid_time_literal(literal)
    )


def _assignment_type_matches(
    actual: Simple_DataType | str | None,
    expected: Simple_DataType | str | None,
) -> bool:
    if actual is None or expected is None:
        return True

    if isinstance(expected, str) and expected.casefold() == "anytype":
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


def _validate_declared_variable(
    variable: Variable,
    context: str,
    *,
    type_graph: TypeGraph,
    known_datatypes: AbcSequence[str],
    allow_unresolved_external_datatypes: bool = False,
) -> None:
    if isinstance(variable.datatype, str):
        if _is_anytype_datatype(variable.datatype):
            pass
        elif not type_graph.has_record(variable.datatype):
            suggestion_candidates = (
                _BUILTIN_DATATYPE_NAMES
                if allow_unresolved_external_datatypes
                else known_datatypes
            )
            suggestion = _suggest_datatype_name(variable.datatype, suggestion_candidates)
            if suggestion is not None:
                raise StructuralValidationError(
                    f"{context} variable {variable.name!r} uses unknown datatype {variable.datatype_text!r}; did you mean {suggestion!r}?",
                    **_span_kwargs(variable.declaration_span),
                )

    if variable.init_value is None:
        return

    if getattr(variable, "init_is_duration", False) and not _is_valid_duration_literal(variable.init_value):
        raise StructuralValidationError(
            f"{context} variable {variable.name!r} has invalid duration literal {variable.init_value!r}",
            **_span_kwargs(variable.declaration_span),
        )

    if _has_time_literal_marker(variable.init_value) and not _is_valid_time_literal(
        _extract_time_literal(variable.init_value)
    ):
        raise StructuralValidationError(
            f"{context} variable {variable.name!r} has invalid time literal {_extract_time_literal(variable.init_value)!r}",
            **_span_kwargs(variable.declaration_span),
        )

    init_datatype = _infer_literal_datatype(
        variable.init_value,
        is_duration=getattr(variable, "init_is_duration", False),
    )
    if init_datatype is None:
        return

    if (
        isinstance(variable.datatype, str)
        and not _is_anytype_datatype(variable.datatype)
        and not type_graph.has_record(variable.datatype)
    ):
        return

    if _literal_matches_expected_datatype(
        variable.init_value,
        variable.datatype,
        is_duration=getattr(variable, "init_is_duration", False),
    ):
        return

    raise StructuralValidationError(
        f"{context} variable {variable.name!r} has init value {variable.init_value!r} with datatype {_format_datatype(init_datatype)!r} "
        f"but declared datatype is {_format_datatype(variable.datatype)!r}",
        **_span_kwargs(variable.declaration_span),
    )


def _ensure_unique_names(names: list[str], context: str, kind: str) -> None:
    seen: dict[str, str] = {}
    for name in names:
        folded = name.casefold()
        if folded in seen:
            raise StructuralValidationError(
                f"{context} has duplicate {kind} names {seen[folded]!r} and {name!r}"
            )
        seen[folded] = name


def _collect_sequence_labels(nodes: list[object], labels: dict[str, str], context: str) -> None:
    for node in nodes:
        label: str | None = None
        if isinstance(node, SFCStep) or (isinstance(node, SFCTransition) and node.name) or isinstance(node, (SFCSubsequence, SFCTransitionSub)):
            label = node.name

        if label:
            folded = label.casefold()
            if folded in labels:
                raise StructuralValidationError(
                    f"{context} has duplicate sequence labels {labels[folded]!r} and {label!r}"
                )
            labels[folded] = label

        if isinstance(node, (SFCAlternative, SFCParallel)):
            for branch in node.branches:
                _collect_sequence_labels(branch, labels, context)
        elif isinstance(node, (SFCSubsequence, SFCTransitionSub)):
            _collect_sequence_labels(node.body, labels, context)


def _iter_variable_refs(node: object):
    if isinstance(node, dict) and const.KEY_VAR_NAME in node:
        yield node
        return

    if isinstance(node, Tree):
        for child in node.children:
            yield from _iter_variable_refs(child)
        return

    if isinstance(node, tuple):
        for item in node:
            yield from _iter_variable_refs(item)
        return

    if isinstance(node, list):
        for item in node:
            yield from _iter_variable_refs(item)


def _validate_variable_refs(
    node: object,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    for ref in _iter_variable_refs(node):
        state = ref.get("state")
        if not state:
            continue

        full_name = ref[const.KEY_VAR_NAME]
        base_name, field_path = _split_dotted_name(str(full_name))
        variable = env.get(base_name.casefold())
        if variable is None:
            continue

        resolved_state = variable.state
        current_datatype: Simple_DataType | str = variable.datatype
        for field_name in field_path:
            if isinstance(current_datatype, Simple_DataType):
                resolved_state = None
                break
            field = type_graph.field(str(current_datatype), field_name)
            if field is None:
                resolved_state = None
                break
            current_datatype = field.datatype
            resolved_state = field.state

        if resolved_state is not None and not resolved_state:
            raise StructuralValidationError(
                f"{context} uses {state.upper()} on non-STATE variable {str(full_name)!r}",
                **_span_kwargs(_ref_span(ref)),
                length=max(len(str(full_name)), 1),
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


def _merge_compatible_types(
    datatypes: list[Simple_DataType | str | None],
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


def _infer_expression_datatype(
    node: object,
    env: dict[str, Variable],
    type_graph: TypeGraph,
) -> Simple_DataType | str | None:
    if isinstance(node, bool):
        return Simple_DataType.BOOLEAN
    if isinstance(node, (IntLiteral, int)) and not isinstance(node, bool):
        return Simple_DataType.INTEGER
    if isinstance(node, (FloatLiteral, float)):
        return Simple_DataType.REAL
    if isinstance(node, str):
        return Simple_DataType.STRING

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return _resolve_ref_datatype(node, env, type_graph)
        return None

    if not isinstance(node, tuple) or not node:
        return None

    tag = node[0]
    if tag == const.KEY_FUNCTION_CALL and len(node) == 3:
        builtin = SATTLINE_BUILTINS.get(str(node[1]).casefold())
        if builtin is None or builtin.return_type is None:
            return None
        return _normalize_builtin_datatype(builtin.return_type)

    if tag in (const.KEY_COMPARE, const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND, const.GRAMMAR_VALUE_NOT):
        return Simple_DataType.BOOLEAN

    if tag in (const.KEY_ADD, const.KEY_MUL) and len(node) == 3:
        datatypes = [_infer_expression_datatype(node[1], env, type_graph)]
        datatypes.extend(
            _infer_expression_datatype(item[1], env, type_graph)
            for item in node[2]
            if isinstance(item, tuple) and len(item) == 2
        )
        return _merge_numeric_types(datatypes)

    if tag in (const.KEY_PLUS, const.KEY_MINUS) and len(node) == 2:
        dtype = _infer_expression_datatype(node[1], env, type_graph)
        return _merge_numeric_types([dtype])

    if tag == const.KEY_TERNARY and len(node) == 3:
        branch_types = [
            _infer_expression_datatype(branch[1], env, type_graph)
            for branch in node[1]
            if isinstance(branch, tuple) and len(branch) == 2
        ]
        branch_types.append(_infer_expression_datatype(node[2], env, type_graph))
        return _merge_compatible_types(branch_types)

    return None


def _builtin_type_matches(
    actual: Simple_DataType | str,
    expected: Simple_DataType | str,
    *,
    direction: str,
) -> bool:
    if isinstance(expected, str) and expected.casefold() == "anytype":
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


def _is_variable_ref_node(node: object) -> bool:
    return isinstance(node, dict) and const.KEY_VAR_NAME in node


def _validate_builtin_call_signature(
    fn_name: str | None,
    args: list[object],
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    if not fn_name:
        return

    builtin = SATTLINE_BUILTINS.get(fn_name.casefold())
    if builtin is None:
        return

    expected_arg_count = len(builtin.parameters)
    actual_arg_count = len(args)
    if actual_arg_count != expected_arg_count:
        raise StructuralValidationError(
            f"{context} call {fn_name!r} has {actual_arg_count} arguments but builtin expects {expected_arg_count}"
        )

    for index, parameter in enumerate(builtin.parameters, start=1):
        argument = args[index - 1]

        if parameter.direction in {"in var", "out", "inout"} and not _is_variable_ref_node(argument):
            raise StructuralValidationError(
                f"{context} call {fn_name!r} argument {index} must be a variable reference because builtin parameter {parameter.name!r} is {parameter.direction!r}"
            )

        if parameter.direction in {"out", "inout"} and isinstance(argument, dict) and _is_variable_ref_node(argument):
            variable = _resolve_root_variable(argument, env)
            if variable is not None and variable.const:
                if fn_name.casefold() in {"setstringpos", "getstringpos"} and index == 1:
                    continue
                raise StructuralValidationError(
                    f"{context} call {fn_name!r} argument {index} writes to CONST variable {variable.name!r}",
                    **_span_kwargs(_ref_span(argument)),
                )

        actual = _infer_expression_datatype(argument, env, type_graph)
        if actual is None:
            continue

        expected = _normalize_builtin_datatype(parameter.datatype)
        if _builtin_type_matches(actual, expected, direction=parameter.direction):
            continue

        raise StructuralValidationError(
            f"{context} call {fn_name!r} argument {index} has datatype {_format_datatype(actual)!r} "
            f"but builtin parameter {parameter.name!r} expects {_format_datatype(expected)!r}"
        )


def _validate_call_arg_node(node: object, context: str) -> None:
    if isinstance(node, str):
        raise StructuralValidationError(
            f"{context} uses string literal {node!r}; string literals are only allowed in parameter connections"
        )

    if isinstance(node, Tree):
        for child in node.children:
            _validate_call_arg_node(child, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_call_arg_node(item, context)
        return

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return

        for value in node.values():
            _validate_call_arg_node(value, context)
        return

    if isinstance(node, tuple):
        if len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
            fn_name = node[1]
            args = node[2] or []
            for index, arg in enumerate(args, start=1):
                _validate_call_arg_node(
                    arg,
                    f"{context} call {fn_name!r} argument {index}",
                )
            return

        items = node[1:] if node and isinstance(node[0], str) else node
        for item in items:
            _validate_call_arg_node(item, context)


def _validate_no_string_literals_in_calls(node: object, context: str) -> None:
    if isinstance(node, Tree):
        for child in node.children:
            _validate_no_string_literals_in_calls(child, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_no_string_literals_in_calls(item, context)
        return

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return

        for value in node.values():
            _validate_no_string_literals_in_calls(value, context)
        return

    if isinstance(node, tuple):
        if len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
            fn_name = node[1]
            args = node[2] or []
            for index, arg in enumerate(args, start=1):
                _validate_call_arg_node(
                    arg,
                    f"{context} call {fn_name!r} argument {index}",
                )
            return

        for item in node:
            _validate_no_string_literals_in_calls(item, context)


def _validate_builtin_call_types(
    node: object,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    if isinstance(node, Tree):
        for child in node.children:
            _validate_builtin_call_types(child, env, type_graph, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_builtin_call_types(item, env, type_graph, context)
        return

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return

        for value in node.values():
            _validate_builtin_call_types(value, env, type_graph, context)
        return

    if isinstance(node, tuple):
        if len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
            fn_name = node[1]
            args = node[2] or []
            _validate_builtin_call_signature(fn_name, args, env, type_graph, context)
            for arg in args:
                _validate_builtin_call_types(arg, env, type_graph, context)
            return

        for item in node:
            _validate_builtin_call_types(item, env, type_graph, context)


def _validate_statement_list(
    statements: list[object],
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    for statement in statements:
        if (
            isinstance(statement, tuple)
            and len(statement) == 3
            and statement[0] == const.KEY_ASSIGN
            and _is_variable_ref_node(statement[1])
        ):
            variable = _resolve_root_variable(statement[1], env)
            if variable is not None and variable.const:
                raise StructuralValidationError(
                    f"{context} assignment writes to CONST variable {variable.name!r}",
                    **_span_kwargs(_ref_span(statement[1])),
                )
        _validate_variable_refs(statement, env, type_graph, context)
        _validate_no_string_literals_in_calls(statement, context)
        _validate_builtin_call_types(statement, env, type_graph, context)


def _validate_code_blocks(code, env: dict[str, Variable], type_graph: TypeGraph, context: str) -> None:
    _validate_statement_list(code.enter, env, type_graph, f"{context} ENTERCODE")
    _validate_statement_list(code.active, env, type_graph, f"{context} ACTIVECODE")
    _validate_statement_list(code.exit, env, type_graph, f"{context} EXITCODE")


def _validate_sequence_nodes(
    nodes: list[object],
    context: str,
    *,
    labels: dict[str, str],
    env: dict[str, Variable],
    type_graph: TypeGraph,
    require_init_step: bool,
    warning_sink: Callable[[str], None] | None = None,
) -> None:
    previous_step: str | None = None
    init_steps = 0
    missing_initial_init_step = False

    if require_init_step and (not nodes or not isinstance(nodes[0], SFCStep) or nodes[0].kind != "init"):
        missing_initial_init_step = True
        _warn_or_raise(
            f"{context} must start with exactly one SEQINITSTEP",
            warning_sink=warning_sink,
        )

    for index, node in enumerate(nodes):
        if isinstance(node, SFCStep):
            _validate_identifier(node.name, f"{context} step")
            if node.kind == "init":
                init_steps += 1
                if index != 0:
                    _warn_or_raise(
                        f"{context} has SEQINITSTEP {node.name!r} outside the first position",
                        warning_sink=warning_sink,
                    )
            if previous_step is not None:
                raise StructuralValidationError(
                    f"{context} has step {node.name!r} immediately after step "
                    f"{previous_step!r} without an intervening transition"
                )
            _validate_code_blocks(node.code, env, type_graph, f"{context} step {node.name!r}")
            previous_step = node.name
            continue

        previous_step = None

        if isinstance(node, SFCTransition):
            _validate_identifier(node.name, f"{context} transition")
        elif isinstance(node, SFCTransitionSub):
            _validate_identifier(node.name, f"{context} transition-sub")
            _validate_sequence_nodes(
                node.body,
                f"{context} transition-sub {node.name!r}",
                labels=labels,
                env=env,
                type_graph=type_graph,
                require_init_step=False,
                warning_sink=warning_sink,
            )
        elif isinstance(node, SFCSubsequence):
            _validate_identifier(node.name, f"{context} subsequence")
            _validate_sequence_nodes(
                node.body,
                f"{context} subsequence {node.name!r}",
                labels=labels,
                env=env,
                type_graph=type_graph,
                require_init_step=False,
                warning_sink=warning_sink,
            )
        elif isinstance(node, SFCAlternative):
            for index, branch in enumerate(node.branches, start=1):
                _validate_sequence_nodes(
                    branch,
                    f"{context} alternative branch {index}",
                    labels=labels,
                    env=env,
                    type_graph=type_graph,
                    require_init_step=False,
                    warning_sink=warning_sink,
                )
        elif isinstance(node, SFCParallel):
            for index, branch in enumerate(node.branches, start=1):
                _validate_sequence_nodes(
                    branch,
                    f"{context} parallel branch {index}",
                    labels=labels,
                    env=env,
                    type_graph=type_graph,
                    require_init_step=False,
                    warning_sink=warning_sink,
                )
        elif isinstance(node, SFCFork):
            _validate_identifier(node.target, f"{context} fork target")
            if node.target.casefold() not in labels:
                raise StructuralValidationError(
                    f"{context} has SEQFORK target {node.target!r} that does not exist in the sequence"
                )
        elif isinstance(node, SFCBreak):
            continue

    if require_init_step and init_steps != 1 and not (missing_initial_init_step and init_steps == 0):
        _warn_or_raise(
            f"{context} must contain exactly one SEQINITSTEP",
            warning_sink=warning_sink,
        )


def _validate_module_code(
    modulecode: ModuleCode | None,
    context: str,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    warning_sink: Callable[[str], None] | None = None,
) -> None:
    if modulecode is None:
        return

    for equation in modulecode.equations or []:
        if isinstance(equation, Equation):
            _validate_identifier(equation.name, f"{context} equation")
            _validate_statement_list(
                equation.code or [],
                env,
                type_graph,
                f"{context} equation {equation.name!r}",
            )

    for sequence in modulecode.sequences or []:
        if isinstance(sequence, Sequence):
            _validate_identifier(sequence.name, f"{context} sequence")
            labels: dict[str, str] = {}
            _collect_sequence_labels(sequence.code or [], labels, f"{context} sequence {sequence.name!r}")
            _validate_sequence_nodes(
                sequence.code or [],
                f"{context} sequence {sequence.name!r}",
                labels=labels,
                env=env,
                type_graph=type_graph,
                require_init_step=True,
                warning_sink=warning_sink,
            )


def _validate_variable_list(
    variables: list[Variable] | None,
    context: str,
    *,
    type_graph: TypeGraph | None = None,
    known_datatypes: AbcSequence[str] = (),
    allow_unresolved_external_datatypes: bool = False,
) -> None:
    names = [variable.name for variable in variables or []]
    _ensure_unique_names(names, context, "variable")
    for variable in variables or []:
        _validate_identifier(variable.name, f"{context} variable")
        if type_graph is not None:
            _validate_declared_variable(
                variable,
                context,
                type_graph=type_graph,
                known_datatypes=known_datatypes,
                allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
            )


def _validate_datatypes(
    datatypes: list[DataType] | None,
    context: str,
    *,
    type_graph: TypeGraph,
    known_datatypes: AbcSequence[str],
    allow_unresolved_external_datatypes: bool = False,
) -> None:
    _ensure_unique_names([datatype.name for datatype in datatypes or []], context, "datatype")
    for datatype in datatypes or []:
        _validate_identifier(datatype.name, f"{context} datatype")
        _validate_variable_list(
            datatype.var_list,
            f"{context} datatype {datatype.name!r}",
            type_graph=type_graph,
            known_datatypes=known_datatypes,
            allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
        )


def _validate_unique_submodule_names(
    modules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
    context: str,
    *,
    enforce_unique_names: bool = True,
) -> None:
    if not enforce_unique_names:
        return

    seen: dict[tuple[str, str | None], str] = {}
    for module in modules or []:
        name = module.header.name
        moduletype_name = module.moduletype_name if isinstance(module, ModuleTypeInstance) else None
        key = (name.casefold(), moduletype_name.casefold() if moduletype_name is not None else None)
        if key in seen:
            raise StructuralValidationError(
                f"{context} has duplicate submodule names {seen[key]!r} and {name!r}",
                **_span_kwargs(module.header.declaration_span),
            )
        seen[key] = name


def _validate_parameter_mappings(
    parametermappings: AbcSequence[ParameterMapping] | None,
    context: str,
    *,
    type_graph: TypeGraph,
    expected_parameters: dict[str, Variable] | None = None,
    source_env: dict[str, Variable] | None = None,
    allow_parameterless_module_mappings: bool = False,
    warn_unknown_parameter_targets: bool = False,
    warn_incompatible_parameter_mappings: bool = False,
    warning_sink: Callable[[str], None] | None = None,
) -> None:
    seen: dict[str, str] = {}

    for mapping in parametermappings or []:
        if not hasattr(mapping, "target"):
            continue

        target = mapping.target
        target_name = (
            str(target.get(const.KEY_VAR_NAME))
            if isinstance(target, dict) and const.KEY_VAR_NAME in target
            else str(target)
        )
        target_span = _ref_span(target)
        target_key = target_name.casefold()
        if target_key in seen:
            raise StructuralValidationError(
                f"{context} has duplicate parameter mapping targets {seen[target_key]!r} and {target_name!r}",
                **_span_kwargs(target_span),
                length=max(len(target_name), 1),
            )
        seen[target_key] = target_name

        if expected_parameters is None:
            continue

        base_name, field_path = _split_dotted_name(target_name)
        target_variable = expected_parameters.get(base_name.casefold())
        if target_variable is None:
            if allow_parameterless_module_mappings and not expected_parameters:
                continue
            continue

        target_datatype = _resolve_variable_field_datatype(target_variable, field_path, type_graph)
        if field_path and target_datatype is None:
            if isinstance(target_variable.datatype, Simple_DataType):
                raise StructuralValidationError(
                    f"{context} parameter mapping target {target_name!r} uses field access on non-record parameter {target_variable.name!r}",
                    **_span_kwargs(target_span),
                    length=max(len(target_name), 1),
                )
            if type_graph.has_record(str(target_variable.datatype)):
                raise StructuralValidationError(
                    f"{context} parameter mapping target {target_name!r} does not exist",
                    **_span_kwargs(target_span),
                    length=max(len(target_name), 1),
                )
            continue

        if target_datatype is None:
            target_datatype = target_variable.datatype

        actual_datatype: Simple_DataType | str | None = None
        source_description: str | None = None
        source_literal = getattr(mapping, "source_literal", None)
        source = getattr(mapping, "source", None)
        if source_literal is not None:
            if bool(getattr(mapping, "is_duration", False)) and not _is_valid_duration_literal(source_literal):
                raise StructuralValidationError(
                    f"{context} maps invalid duration literal {source_literal!r} to parameter target {target_name!r}",
                    **_span_kwargs(target_span),
                )
            if _has_time_literal_marker(source_literal) and not _is_valid_time_literal(
                _extract_time_literal(source_literal)
            ):
                raise StructuralValidationError(
                    f"{context} maps invalid time literal {_extract_time_literal(source_literal)!r} to parameter target {target_name!r}",
                    **_span_kwargs(target_span),
                )
            actual_datatype = _infer_literal_datatype(
                source_literal,
                is_duration=bool(getattr(mapping, "is_duration", False)),
            )
            source_description = repr(source_literal)
        elif isinstance(source, dict) and source_env is not None:
            actual_datatype = _resolve_ref_datatype(source, source_env, type_graph)
            source_description = str(source.get(const.KEY_VAR_NAME))

        if actual_datatype is None:
            continue

        if source_literal is not None and _literal_matches_expected_datatype(
            source_literal,
            target_datatype,
            is_duration=bool(getattr(mapping, "is_duration", False)),
        ):
            continue

        if _assignment_type_matches(actual_datatype, target_datatype):
            continue

        _warn_or_raise(
            f"{context} maps {source_description or 'value'!r} with datatype {_format_datatype(actual_datatype)!r} "
            f"to parameter target {target_name!r} with datatype {_format_datatype(target_datatype)!r}",
            warning_sink=warning_sink if warn_incompatible_parameter_mappings else None,
            **_span_kwargs(target_span),
        )


def _merge_env(parent_env: dict[str, Variable], variables: list[Variable] | None) -> dict[str, Variable]:
    merged = dict(parent_env)
    for variable in variables or []:
        merged[variable.name.casefold()] = variable
    return merged


def _validate_module(
    module: object,
    context: str,
    parent_env: dict[str, Variable],
    type_graph: TypeGraph,
    known_datatypes: AbcSequence[str],
    moduletype_index: dict[str, list[ModuleTypeDef]],
    allow_unresolved_external_datatypes: bool = False,
    enforce_unique_submodule_names: bool = True,
    allow_parameterless_module_mappings: bool = False,
    warn_unknown_parameter_targets: bool = False,
    warn_incompatible_parameter_mappings: bool = False,
    warning_sink: Callable[[str], None] | None = None,
) -> None:
    if isinstance(module, SingleModule):
        _validate_identifier(module.header.name, f"{context} module")
        module_context = f"{context} module {module.header.name!r}"
        _validate_variable_list(
            module.moduleparameters,
            module_context,
            type_graph=type_graph,
            known_datatypes=known_datatypes,
            allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
        )
        _validate_variable_list(
            module.localvariables,
            module_context,
            type_graph=type_graph,
            known_datatypes=known_datatypes,
            allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
        )
        env = _merge_env(parent_env, module.moduleparameters)
        env = _merge_env(env, module.localvariables)
        _validate_parameter_mappings(
            module.parametermappings,
            module_context,
            type_graph=type_graph,
            expected_parameters={variable.name.casefold(): variable for variable in module.moduleparameters or []},
            source_env=parent_env,
            allow_parameterless_module_mappings=allow_parameterless_module_mappings,
            warn_unknown_parameter_targets=warn_unknown_parameter_targets,
            warn_incompatible_parameter_mappings=warn_incompatible_parameter_mappings,
            warning_sink=warning_sink,
        )
        _validate_module_code(
            module.modulecode,
            module_context,
            env,
            type_graph,
            warning_sink=warning_sink,
        )
        _validate_unique_submodule_names(
            module.submodules,
            module_context,
            enforce_unique_names=enforce_unique_submodule_names,
        )
        for submodule in module.submodules or []:
            _validate_module(
                submodule,
                module_context,
                env,
                type_graph,
                known_datatypes,
                moduletype_index,
                allow_unresolved_external_datatypes,
                enforce_unique_submodule_names,
                allow_parameterless_module_mappings,
                warn_unknown_parameter_targets,
                warn_incompatible_parameter_mappings,
                warning_sink,
            )
        return

    if isinstance(module, FrameModule):
        _validate_identifier(module.header.name, f"{context} frame")
        module_context = f"{context} frame {module.header.name!r}"
        _validate_module_code(
            module.modulecode,
            module_context,
            parent_env,
            type_graph,
            warning_sink=warning_sink,
        )
        _validate_unique_submodule_names(
            module.submodules,
            module_context,
            enforce_unique_names=enforce_unique_submodule_names,
        )
        for submodule in module.submodules or []:
            _validate_module(
                submodule,
                module_context,
                parent_env,
                type_graph,
                known_datatypes,
                moduletype_index,
                allow_unresolved_external_datatypes,
                enforce_unique_submodule_names,
                allow_parameterless_module_mappings,
                warn_unknown_parameter_targets,
                warn_incompatible_parameter_mappings,
                warning_sink,
            )
        return

    if isinstance(module, ModuleTypeInstance):
        _validate_identifier(module.header.name, f"{context} module instance")
        _validate_identifier(module.moduletype_name, f"{context} module type reference")
        matches = moduletype_index.get(module.moduletype_name.casefold(), [])
        expected_parameters = None
        if len(matches) == 1:
            expected_parameters = {
                variable.name.casefold(): variable
                for variable in matches[0].moduleparameters or []
            }
        _validate_parameter_mappings(
            module.parametermappings,
            f"{context} module instance {module.header.name!r}",
            type_graph=type_graph,
            expected_parameters=expected_parameters,
            source_env=parent_env,
            allow_parameterless_module_mappings=allow_parameterless_module_mappings,
            warn_unknown_parameter_targets=warn_unknown_parameter_targets,
            warn_incompatible_parameter_mappings=warn_incompatible_parameter_mappings,
            warning_sink=warning_sink,
        )
        return


def validate_transformed_basepicture(
    basepic: BasePicture,
    *,
    external_datatypes: AbcSequence[DataType] | None = None,
    external_moduletype_defs: AbcSequence[ModuleTypeDef] | None = None,
    allow_unresolved_external_datatypes: bool = False,
    enforce_unique_submodule_names: bool = True,
    allow_parameterless_module_mappings: bool = False,
    warn_unknown_parameter_targets: bool = False,
    warn_incompatible_parameter_mappings: bool = False,
    warning_sink: Callable[[str], None] | None = None,
) -> None:
    _validate_identifier(basepic.header.name, "BasePicture")
    _ensure_unique_names(
        [moduletype.name for moduletype in basepic.moduletype_defs or []],
        "BasePicture",
        "moduletype",
    )

    available_datatypes = [*(basepic.datatype_defs or []), *(external_datatypes or [])]
    available_moduletype_defs = [
        *(basepic.moduletype_defs or []),
        *(external_moduletype_defs or []),
    ]

    type_graph = TypeGraph.from_datatypes(available_datatypes)
    known_datatypes = tuple(
        [datatype.value for datatype in Simple_DataType]
        + [datatype.name for datatype in available_datatypes]
    )
    moduletype_index: dict[str, list[ModuleTypeDef]] = {}
    for moduletype in available_moduletype_defs:
        moduletype_index.setdefault(moduletype.name.casefold(), []).append(moduletype)

    _validate_variable_list(
        basepic.localvariables,
        "BasePicture",
        type_graph=type_graph,
        known_datatypes=known_datatypes,
        allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
    )
    _validate_datatypes(
        basepic.datatype_defs,
        "BasePicture",
        type_graph=type_graph,
        known_datatypes=known_datatypes,
        allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
    )

    base_env = _merge_env({}, basepic.localvariables)

    for moduletype in basepic.moduletype_defs or []:
        if isinstance(moduletype, ModuleTypeDef):
            _validate_identifier(moduletype.name, "BasePicture moduletype")
            moduletype_context = f"BasePicture moduletype {moduletype.name!r}"
            _validate_variable_list(
                moduletype.moduleparameters,
                moduletype_context,
                type_graph=type_graph,
                known_datatypes=known_datatypes,
                allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
            )
            _validate_variable_list(
                moduletype.localvariables,
                moduletype_context,
                type_graph=type_graph,
                known_datatypes=known_datatypes,
                allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
            )
            env = _merge_env(base_env, moduletype.moduleparameters)
            env = _merge_env(env, moduletype.localvariables)
            _validate_module_code(
                moduletype.modulecode,
                moduletype_context,
                env,
                type_graph,
                warning_sink=warning_sink,
            )
            _validate_unique_submodule_names(
                moduletype.submodules,
                moduletype_context,
                enforce_unique_names=enforce_unique_submodule_names,
            )
            for submodule in moduletype.submodules or []:
                _validate_module(
                    submodule,
                    moduletype_context,
                    env,
                    type_graph,
                    known_datatypes,
                    moduletype_index,
                    allow_unresolved_external_datatypes,
                    enforce_unique_submodule_names,
                    allow_parameterless_module_mappings,
                    warn_unknown_parameter_targets,
                    warn_incompatible_parameter_mappings,
                    warning_sink,
                )

    _validate_module_code(
        basepic.modulecode,
        "BasePicture",
        base_env,
        type_graph,
        warning_sink=warning_sink,
    )
    _validate_unique_submodule_names(
        basepic.submodules,
        "BasePicture",
        enforce_unique_names=enforce_unique_submodule_names,
    )

    for submodule in basepic.submodules or []:
        _validate_module(
            submodule,
            "BasePicture",
            base_env,
            type_graph,
            known_datatypes,
            moduletype_index,
            allow_unresolved_external_datatypes,
            enforce_unique_submodule_names,
            allow_parameterless_module_mappings,
            warn_unknown_parameter_targets,
            warn_incompatible_parameter_mappings,
            warning_sink,
        )
