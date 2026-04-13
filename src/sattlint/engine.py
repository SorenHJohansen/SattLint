"""Parsing and project-loading engine for SattLine sources."""
from dataclasses import dataclass
from pathlib import Path
from lark import Lark, Tree
from lark.exceptions import VisitError
from sattline_parser import create_parser as parser_core_create_parser
from sattline_parser import parse_source_file as parser_core_parse_source_file
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser import strip_sl_comments
from .grammar import constants as const
from .transformer.sl_transformer import SLTransformer
from .grammar.parser_decode import is_compressed, preprocess_sl_text
from .models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FrameModule,
    FloatLiteral,
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
from .analyzers.sattline_builtins import SATTLINE_BUILTINS
from .utils.text_processing import find_disallowed_comments
from collections.abc import Callable, Iterable, Sequence as AbcSequence
from enum import Enum
from .models.project_graph import ProjectGraph
from .cache import FileLookupCache, FileASTCache, get_cache_dir
import logging

# Create a module-level logger consistent with the CLI output.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",  # Just the message, no prefixes
    force=True,
)
log = logging.getLogger("SattLint")


class StructuralValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
    ):
        super().__init__(message)
        self.line = line
        self.column = column


class RawSourceValidationError(StructuralValidationError):
    def __init__(self, message: str, *, line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.line = line
        self.column = column


@dataclass(frozen=True)
class SyntaxValidationResult:
    file_path: Path
    ok: bool
    stage: str
    message: str | None = None
    line: int | None = None
    column: int | None = None


class CodeMode(Enum):
    OFFICIAL = "official"  # .x code, .z deps
    DRAFT = "draft"  # .s code, .l deps


def code_ext(mode: CodeMode) -> str:
    return ".x" if mode is CodeMode.OFFICIAL else ".s"


def deps_ext(mode: CodeMode) -> str:
    return ".z" if mode is CodeMode.OFFICIAL else ".l"


BASE_DIR = Path(__file__).resolve().parent


class DebugMixin:
    debug: bool = False

    def dbg(self, msg: str) -> None:
        if self.debug:
            log.debug(f"[DEBUG] {msg}")


def create_sl_parser() -> Lark:
    """Compatibility wrapper that delegates parser creation to parser-core."""
    return parser_core_create_parser()


def _read_text_simple(path: Path) -> str:
    # If utf-8 fails, try cp1252 (covers characters like 'ø' / 0xF8)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp1252")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")


def _load_source_text(
    code_path: Path,
    *,
    debug: Callable[[str], None] | None = None,
) -> str:
    source_path = Path(code_path)
    if debug is not None:
        debug(f"Parsing file: {source_path}")

    src = _read_text_simple(source_path)
    if is_compressed(src):
        if debug is not None:
            debug("Compressed format detected; decoding before parsing")
        src, _ = preprocess_sl_text(src)
    return src


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
    for candidate in known_datatypes:
        distance = _bounded_levenshtein(name, candidate, max_distance=2)
        if distance is None:
            continue
        if best_distance is None or distance < best_distance:
            best_match = candidate
            best_distance = distance
    return best_match


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


def _infer_literal_datatype(value: object) -> Simple_DataType | str | None:
    if isinstance(value, bool):
        return Simple_DataType.BOOLEAN
    if isinstance(value, (IntLiteral, int)) and not isinstance(value, bool):
        return Simple_DataType.INTEGER
    if isinstance(value, (FloatLiteral, float)):
        return Simple_DataType.REAL
    if isinstance(value, str):
        return Simple_DataType.STRING
    if isinstance(value, dict) and const.GRAMMAR_VALUE_TIME_VALUE in value:
        return const.GRAMMAR_VALUE_TIME_VALUE
    return None


def _assignment_type_matches(
    actual: Simple_DataType | str | None,
    expected: Simple_DataType | str | None,
) -> bool:
    if actual is None or expected is None:
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
) -> None:
    if isinstance(variable.datatype, str) and not type_graph.has_record(variable.datatype):
        suggestion = _suggest_datatype_name(variable.datatype, known_datatypes)
        if suggestion is not None:
            raise StructuralValidationError(
                f"{context} variable {variable.name!r} uses unknown datatype {variable.datatype_text!r}; did you mean {suggestion!r}?",
                **_span_kwargs(variable.declaration_span),
            )

    if variable.init_value is None:
        return

    init_datatype = _infer_literal_datatype(variable.init_value)
    if init_datatype is None:
        return

    if isinstance(variable.datatype, str) and not type_graph.has_record(variable.datatype):
        return

    if _assignment_type_matches(init_datatype, variable.datatype):
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
        if isinstance(node, SFCStep):
            label = node.name
        elif isinstance(node, SFCTransition) and node.name:
            label = node.name
        elif isinstance(node, SFCSubsequence):
            label = node.name
        elif isinstance(node, SFCTransitionSub):
            label = node.name

        if label:
            folded = label.casefold()
            if folded in labels:
                raise StructuralValidationError(
                    f"{context} has duplicate sequence labels {labels[folded]!r} and {label!r}"
                )
            labels[folded] = label

        if isinstance(node, SFCAlternative):
            for branch in node.branches:
                _collect_sequence_labels(branch, labels, context)
        elif isinstance(node, SFCParallel):
            for branch in node.branches:
                _collect_sequence_labels(branch, labels, context)
        elif isinstance(node, SFCSubsequence):
            _collect_sequence_labels(node.body, labels, context)
        elif isinstance(node, SFCTransitionSub):
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
    context: str,
) -> None:
    for ref in _iter_variable_refs(node):
        state = ref.get("state")
        if not state:
            continue

        full_name = ref[const.KEY_VAR_NAME]
        base_name = str(full_name).split(".", 1)[0]
        variable = env.get(base_name.casefold())
        if variable is not None and not variable.state:
            raise StructuralValidationError(
                f"{context} uses {state.upper()} on non-STATE variable {base_name!r}"
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

        if (
            direction == "in"
            and expected == Simple_DataType.REAL
            and actual == Simple_DataType.INTEGER
        ):
            return True

        return False

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
        _validate_variable_refs(statement, env, context)
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
) -> None:
    previous_step: str | None = None
    init_steps = 0

    if require_init_step:
        if not nodes or not isinstance(nodes[0], SFCStep) or nodes[0].kind != "init":
            raise StructuralValidationError(
                f"{context} must start with exactly one SEQINITSTEP"
            )

    for index, node in enumerate(nodes):
        if isinstance(node, SFCStep):
            _validate_identifier(node.name, f"{context} step")
            if node.kind == "init":
                init_steps += 1
                if index != 0:
                    raise StructuralValidationError(
                        f"{context} has SEQINITSTEP {node.name!r} outside the first position"
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
                )
        elif isinstance(node, SFCFork):
            _validate_identifier(node.target, f"{context} fork target")
            if node.target.casefold() not in labels:
                raise StructuralValidationError(
                    f"{context} has SEQFORK target {node.target!r} that does not exist in the sequence"
                )
        elif isinstance(node, SFCBreak):
            continue

    if require_init_step and init_steps != 1:
        raise StructuralValidationError(
            f"{context} must contain exactly one SEQINITSTEP"
        )


def _validate_module_code(
    modulecode: ModuleCode | None,
    context: str,
    env: dict[str, Variable],
    type_graph: TypeGraph,
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
            )


def _validate_variable_list(
    variables: list[Variable] | None,
    context: str,
    *,
    type_graph: TypeGraph | None = None,
    known_datatypes: AbcSequence[str] = (),
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
            )


def _validate_datatypes(
    datatypes: list[DataType] | None,
    context: str,
    *,
    type_graph: TypeGraph,
    known_datatypes: AbcSequence[str],
) -> None:
    _ensure_unique_names([datatype.name for datatype in datatypes or []], context, "datatype")
    for datatype in datatypes or []:
        _validate_identifier(datatype.name, f"{context} datatype")
        _validate_variable_list(
            datatype.var_list,
            f"{context} datatype {datatype.name!r}",
            type_graph=type_graph,
            known_datatypes=known_datatypes,
        )


def _validate_unique_submodule_names(
    modules: list[SingleModule | FrameModule | ModuleTypeInstance] | None,
    context: str,
) -> None:
    seen: dict[str, str] = {}
    for module in modules or []:
        name = module.header.name
        folded = name.casefold()
        if folded in seen:
            raise StructuralValidationError(
                f"{context} has duplicate submodule names {seen[folded]!r} and {name!r}",
                **_span_kwargs(module.header.declaration_span),
            )
        seen[folded] = name


def _validate_parameter_mappings(
    parametermappings: AbcSequence[ParameterMapping] | None,
    context: str,
    *,
    type_graph: TypeGraph,
    expected_parameters: dict[str, Variable] | None = None,
    source_env: dict[str, Variable] | None = None,
) -> None:
    seen: dict[str, str] = {}

    for mapping in parametermappings or []:
        if not hasattr(mapping, "target"):
            continue

        target = getattr(mapping, "target")
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
            )
        seen[target_key] = target_name

        if expected_parameters is None:
            continue

        base_name, field_path = _split_dotted_name(target_name)
        target_variable = expected_parameters.get(base_name.casefold())
        if target_variable is None:
            raise StructuralValidationError(
                f"{context} maps unknown parameter target {target_name!r}",
                **_span_kwargs(target_span),
            )

        target_datatype = _resolve_variable_field_datatype(target_variable, field_path, type_graph)
        if field_path and target_datatype is None:
            if isinstance(target_variable.datatype, Simple_DataType):
                raise StructuralValidationError(
                    f"{context} parameter mapping target {target_name!r} uses field access on non-record parameter {target_variable.name!r}",
                    **_span_kwargs(target_span),
                )
            if type_graph.has_record(str(target_variable.datatype)):
                raise StructuralValidationError(
                    f"{context} parameter mapping target {target_name!r} does not exist",
                    **_span_kwargs(target_span),
                )
            continue

        if target_datatype is None:
            target_datatype = target_variable.datatype

        actual_datatype: Simple_DataType | str | None = None
        source_description: str | None = None
        source_literal = getattr(mapping, "source_literal", None)
        source = getattr(mapping, "source", None)
        if source_literal is not None:
            actual_datatype = _infer_literal_datatype(source_literal)
            source_description = repr(source_literal)
        elif isinstance(source, dict) and source_env is not None:
            actual_datatype = _resolve_ref_datatype(source, source_env, type_graph)
            source_description = str(source.get(const.KEY_VAR_NAME))

        if actual_datatype is None or _assignment_type_matches(actual_datatype, target_datatype):
            continue

        raise StructuralValidationError(
            f"{context} maps {source_description or 'value'!r} with datatype {_format_datatype(actual_datatype)!r} "
            f"to parameter target {target_name!r} with datatype {_format_datatype(target_datatype)!r}",
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
) -> None:
    if isinstance(module, SingleModule):
        _validate_identifier(module.header.name, f"{context} module")
        module_context = f"{context} module {module.header.name!r}"
        _validate_variable_list(
            module.moduleparameters,
            module_context,
            type_graph=type_graph,
            known_datatypes=known_datatypes,
        )
        _validate_variable_list(
            module.localvariables,
            module_context,
            type_graph=type_graph,
            known_datatypes=known_datatypes,
        )
        env = _merge_env(parent_env, module.moduleparameters)
        env = _merge_env(env, module.localvariables)
        _validate_parameter_mappings(
            module.parametermappings,
            module_context,
            type_graph=type_graph,
            expected_parameters={variable.name.casefold(): variable for variable in module.moduleparameters or []},
            source_env=parent_env,
        )
        _validate_module_code(module.modulecode, module_context, env, type_graph)
        _validate_unique_submodule_names(module.submodules, module_context)
        for submodule in module.submodules or []:
            _validate_module(
                submodule,
                module_context,
                env,
                type_graph,
                known_datatypes,
                moduletype_index,
            )
        return

    if isinstance(module, FrameModule):
        _validate_identifier(module.header.name, f"{context} frame")
        module_context = f"{context} frame {module.header.name!r}"
        _validate_module_code(module.modulecode, module_context, parent_env, type_graph)
        _validate_unique_submodule_names(module.submodules, module_context)
        for submodule in module.submodules or []:
            _validate_module(
                submodule,
                module_context,
                parent_env,
                type_graph,
                known_datatypes,
                moduletype_index,
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
        )
        return


def validate_transformed_basepicture(basepic: BasePicture) -> None:
    _validate_identifier(basepic.header.name, "BasePicture")
    _ensure_unique_names(
        [moduletype.name for moduletype in basepic.moduletype_defs or []],
        "BasePicture",
        "moduletype",
    )

    type_graph = TypeGraph.from_basepicture(basepic)
    known_datatypes = tuple([datatype.value for datatype in Simple_DataType] + [datatype.name for datatype in basepic.datatype_defs or []])
    moduletype_index: dict[str, list[ModuleTypeDef]] = {}
    for moduletype in basepic.moduletype_defs or []:
        moduletype_index.setdefault(moduletype.name.casefold(), []).append(moduletype)

    _validate_variable_list(
        basepic.localvariables,
        "BasePicture",
        type_graph=type_graph,
        known_datatypes=known_datatypes,
    )
    _validate_datatypes(
        basepic.datatype_defs,
        "BasePicture",
        type_graph=type_graph,
        known_datatypes=known_datatypes,
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
            )
            _validate_variable_list(
                moduletype.localvariables,
                moduletype_context,
                type_graph=type_graph,
                known_datatypes=known_datatypes,
            )
            env = _merge_env(base_env, moduletype.moduleparameters)
            env = _merge_env(env, moduletype.localvariables)
            _validate_module_code(moduletype.modulecode, moduletype_context, env, type_graph)
            _validate_unique_submodule_names(moduletype.submodules, moduletype_context)
            for submodule in moduletype.submodules or []:
                _validate_module(
                    submodule,
                    moduletype_context,
                    env,
                    type_graph,
                    known_datatypes,
                    moduletype_index,
                )

    _validate_module_code(basepic.modulecode, "BasePicture", base_env, type_graph)
    _validate_unique_submodule_names(basepic.submodules, "BasePicture")

    for submodule in basepic.submodules or []:
        _validate_module(
            submodule,
            "BasePicture",
            base_env,
            type_graph,
            known_datatypes,
            moduletype_index,
        )


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    basepic = parser_core_parse_source_text(
        src,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture(basepic)

    return basepic


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    basepic = parser_core_parse_source_file(
        code_path,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture(basepic)
    return basepic


def _extract_error_position(exc: Exception) -> tuple[int | None, int | None]:
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if isinstance(exc, VisitError) and exc.orig_exc is not None:
        line = line if line is not None else getattr(exc.orig_exc, "line", None)
        column = column if column is not None else getattr(exc.orig_exc, "column", None)
    return line, column


def validate_single_file_syntax(code_path: Path) -> SyntaxValidationResult:
    target_path = Path(code_path)
    try:
        src = _load_source_text(target_path)
        violations = find_disallowed_comments(src)
        if violations:
            first = violations[0]
            raise RawSourceValidationError(
                "comment is only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks",
                line=first.start_line,
                column=first.start_col,
            )
        parse_source_text(src)
    except VisitError as exc:
        line, column = _extract_error_position(exc)
        message = str(exc.orig_exc) if exc.orig_exc is not None else str(exc)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="transform",
            message=message,
            line=line,
            column=column,
        )
    except StructuralValidationError as exc:
        line, column = _extract_error_position(exc)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="validation",
            message=str(exc),
            line=line,
            column=column,
        )
    except Exception as exc:
        line, column = _extract_error_position(exc)
        stage = "parse" if line is not None or column is not None else "validation"
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage=stage,
            message=str(exc),
            line=line,
            column=column,
        )

    return SyntaxValidationResult(file_path=target_path, ok=True, stage="ok")


# ---------- Loader with recursive resolution ----------
class SattLineProjectLoader(DebugMixin):
    def __init__(
        self,
        program_dir: Path,
        other_lib_dirs: Iterable[Path],
        abb_lib_dir: Path,
        mode: CodeMode,
        scan_root_only: bool,
        debug: bool,
    ):
        self.program_dir = program_dir
        self.other_lib_dirs = list(other_lib_dirs)
        self.abb_lib_dir = abb_lib_dir
        self.mode = mode
        self.scan_root_only = scan_root_only
        self.debug = debug
        self.parser = create_sl_parser()  # reuse your grammar setup
        self.transformer = SLTransformer()  # reuse your transformer
        self._visited: set[str] = set()
        self._stack: set[str] = set()  # cycle protection
        self._ignored_dirs: set[Path] = set()
        self._lookup_cache = FileLookupCache(get_cache_dir())
        self._ast_cache = FileASTCache(get_cache_dir())
        self._base_indexes: dict[Path, dict[str, dict[str, Path]]] = {}
        self._lib_by_name: dict[str, str] = {}
        self.dbg(
            f"Selected mode={mode.value}, code_ext={code_ext(mode)}, deps_ext={deps_ext(mode)}"
        )
        self.dbg(f"Programs dir: {self.program_dir}")
        for i, ld in enumerate(self.other_lib_dirs, start=1):
            self.dbg(f"Lib {i}: {ld}")
        self.dbg(f"ABB lib dir: {self.abb_lib_dir}")

    def _is_ignored_base(self, base: Path) -> bool:
        try:
            base_r = base.resolve()
        except Exception:
            base_r = base
        return any(base_r == ign for ign in self._ignored_dirs)

    def _is_allowed_base(self, base: Path) -> bool:
        allowed = [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]
        try:
            base_r = base.resolve()
        except Exception:
            base_r = base
        for candidate in allowed:
            try:
                cand_r = candidate.resolve()
            except Exception:
                cand_r = candidate
            if base_r == cand_r:
                return True
        return False

    def _get_base_index(self, base: Path) -> dict[str, dict[str, Path]]:
        if base in self._base_indexes:
            return self._base_indexes[base]
        index: dict[str, dict[str, Path]] = {}
        if not base.exists() or not base.is_dir():
            self._base_indexes[base] = index
            return index

        for entry in base.iterdir():
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext not in {".s", ".x", ".l", ".z"}:
                continue
            stem = entry.stem.casefold()
            index.setdefault(stem, {})[ext] = entry

        self._base_indexes[base] = index
        return index

    def _find_in_index(
        self,
        *,
        base: Path,
        name: str,
        extensions: list[str],
    ) -> Path | None:
        index = self._get_base_index(base)
        entries = index.get(name.casefold())
        if not entries:
            return None
        for ext in extensions:
            p = entries.get(ext)
            if p is not None:
                return p
        return None

    def _add_to_index(self, base: Path, name: str, path: Path) -> None:
        index = self._get_base_index(base)
        index.setdefault(name.casefold(), {})[path.suffix.lower()] = path

    def _find_in_cached_base(
        self,
        *,
        kind: str,
        name: str,
        extensions: list[str],
    ) -> Path | None:
        cached = self._lookup_cache.get(kind, name, self.mode.value)
        if not cached:
            return None

        base = Path(cached.get("base_dir", ""))
        if not base or self._is_ignored_base(base):
            return None
        if not self._is_allowed_base(base):
            self._lookup_cache.forget(kind, name, self.mode.value)
            return None

        cached_ext = cached.get("ext")
        ordered_exts = [cached_ext] if cached_ext in extensions else []
        ordered_exts.extend(ext for ext in extensions if ext != cached_ext)

        for ext in ordered_exts:
            p = base / f"{name}{ext}"
            self.dbg(f"Checking cached {kind} file: {p} (exists={p.exists()})")
            if p.exists():
                self.dbg(f"Using cached {kind} file: {p}")
                return p

        self._lookup_cache.forget(kind, name, self.mode.value)
        return None

    def _find_code(self, name: str) -> Path | None:
        """
        Find code file with fallback support.
        In draft mode: try .s first, fallback to .x
        In official mode: only use .x
        """
        extensions = [".s", ".x"] if self.mode == CodeMode.DRAFT else [".x"]

        cached = self._find_in_cached_base(
            kind="code",
            name=name,
            extensions=extensions,
        )
        if cached is not None:
            return cached

        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            indexed = self._find_in_index(
                base=base,
                name=name,
                extensions=extensions,
            )
            if indexed is not None:
                self.dbg(f"Using code file: {indexed}")
                self._lookup_cache.set(
                    "code", name, self.mode.value, base, indexed.suffix.lower()
                )
                return indexed

            for ext in extensions:
                p = base / f"{name}{ext}"
                self.dbg(f"Checking code file: {p} (exists={p.exists()})")
                if p.exists():
                    self.dbg(f"Using code file: {p}")
                    self._lookup_cache.set("code", name, self.mode.value, base, ext)
                    self._add_to_index(base, name, p)
                    return p

        self.dbg(f"No code file found for '{name}' in mode={self.mode.value}")
        return None

    def _find_deps(self, name: str) -> Path | None:
        """
        Find deps file with fallback support.
        In draft mode: try .l first, fallback to .z
        In official mode: only use .z
        """
        extensions = [".l", ".z"] if self.mode == CodeMode.DRAFT else [".z"]

        cached = self._find_in_cached_base(
            kind="deps",
            name=name,
            extensions=extensions,
        )
        if cached is not None:
            return cached

        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            indexed = self._find_in_index(
                base=base,
                name=name,
                extensions=extensions,
            )
            if indexed is not None:
                self.dbg(f"Using deps file: {indexed}")
                self._lookup_cache.set(
                    "deps", name, self.mode.value, base, indexed.suffix.lower()
                )
                return indexed

            for ext in extensions:
                p = base / f"{name}{ext}"
                self.dbg(f"Checking deps file: {p} (exists={p.exists()})")
                if p.exists():
                    self.dbg(f"Using deps file: {p}")
                    self._lookup_cache.set("deps", name, self.mode.value, base, ext)
                    self._add_to_index(base, name, p)
                    return p

        self.dbg(f"No deps file found for '{name}' in mode={self.mode.value}")
        return None

    def _find_vendor_code(self, name: str) -> Path | None:
        """Find code file in vendor directories with fallback."""
        extensions = [".s", ".x"] if self.mode == CodeMode.DRAFT else [".x"]

        for ign in self._ignored_dirs:
            for ext in extensions:
                p = ign / f"{name}{ext}"
                if p.exists():
                    return p
        return None

    def _find_vendor_deps(self, name: str) -> Path | None:
        """Find deps file in vendor directories with fallback."""
        extensions = [".l", ".z"] if self.mode == CodeMode.DRAFT else [".z"]

        for ign in self._ignored_dirs:
            for ext in extensions:
                p = ign / f"{name}{ext}"
                if p.exists():
                    return p
        return None

    def _read_deps(self, deps_path: Path) -> list[str]:
        # If utf-8 fails, try cp1252 (covers characters like 'ø' / 0xF8)
        try:
            text = deps_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = deps_path.read_text(encoding="cp1252")

        lines = text.splitlines()
        names = [ln.strip() for ln in lines if ln.strip()]
        self.dbg(f"Deps from {deps_path.name}: {names}")
        return names

    def _read_text_simple(self, path: Path) -> str:
        return _read_text_simple(path)

    def _library_name_for_path(self, code_path: Path) -> str:
        """
        Return the top-level root directory name this file belongs to
        (e.g., 'unitlib', 'nnelib', 'projectlib', 'SL_Library').
        """
        rp = code_path.resolve()
        try:
            pr = self.program_dir.resolve()
        except Exception:
            pr = self.program_dir
        if rp.is_relative_to(pr):
            return pr.name
        for ld in self.other_lib_dirs:
            try:
                lr = ld.resolve()
            except Exception:
                lr = ld
            if rp.is_relative_to(lr):
                return lr.name
        try:
            ar = self.abb_lib_dir.resolve()
        except Exception:
            ar = self.abb_lib_dir
        if rp.is_relative_to(ar):
            return ar.name
        # Fallback: parent directory name
        return rp.parent.name

    def _record_library_name(self, name: str, code_path: Path) -> str:
        lib_name = self._library_name_for_path(code_path)
        self._lib_by_name[name.casefold()] = lib_name
        return lib_name

    def _parse_one(self, code_path: Path) -> BasePicture:
        return parse_source_file(
            code_path,
            parser=self.parser,
            transformer=self.transformer,
            debug=self.dbg,
        )

    def _load_or_parse(self, code_path: Path) -> BasePicture:
        cached = self._ast_cache.load(code_path, self.mode.value)
        if cached is not None:
            self.dbg(f"Using cached AST for: {code_path}")
            return cached

        bp = self._parse_one(code_path)
        self._ast_cache.save(code_path, self.mode.value, bp)
        return bp

    def resolve(self, root_name: str, strict: bool = False) -> ProjectGraph:
        if self.scan_root_only:
            return self._resolve_root_only(root_name, strict)
        self.dbg(f"Resolving root: {root_name}")
        graph = ProjectGraph()
        self._visit(root_name, graph, strict)
        self.dbg(f"Resolved ASTs: {list(graph.ast_by_name.keys())}")
        if graph.missing:
            self.dbg(f"Missing/failed: {graph.missing}")
        return graph

    def _resolve_root_only(self, root_name: str, strict: bool) -> ProjectGraph:
        graph = ProjectGraph()
        code_path = self._find_code(root_name)
        if not code_path:
            msg = f"Missing code file for '{root_name}' in mode={self.mode.value}"
            if strict:
                raise FileNotFoundError(msg)
            graph.missing.append(msg)
            return graph

        try:
            bp = self._load_or_parse(code_path)
            if bp is None:
                msg = f"{root_name} transformed to no BasePicture (parse/transform issue?)"
                if strict:
                    raise RuntimeError(msg)
                graph.missing.append(msg)
                return graph
            graph.ast_by_name[root_name] = bp
            lib_name = self._library_name_for_path(code_path)
            graph.index_from_basepic(
                bp, source_path=code_path, library_name=lib_name
            )  # collect any defs emitted in this files
            return graph
        except Exception as ex:
            if strict:
                raise
            graph.missing.append(f"{root_name} parse/transform error: {ex}")
            return graph

    def _visit(self, name: str, graph: ProjectGraph, strict: bool) -> None:
        key = name.lower()
        if key in self._visited or key in self._stack:
            return
        self._stack.add(key)

        # Resolve dependencies first (from non-vendor dirs only)
        deps_path = self._find_deps(name)
        dep_names = self._read_deps(deps_path) if deps_path else []

        # Visit each dep
        for dep in dep_names:
            self._visit(dep, graph, strict)

        dep_libs: list[str] = []
        for dep in dep_names:
            dep_bp = graph.ast_by_name.get(dep)
            if dep_bp:
                origin_lib = getattr(dep_bp, "origin_lib", None)
                if origin_lib:
                    dep_libs.append(origin_lib)
                    continue
            cached_lib = self._lib_by_name.get(dep.casefold())
            if cached_lib:
                dep_libs.append(cached_lib)

        # Determine code path
        code_path = self._find_code(name)
        if code_path is not None:
            try:
                bp = self._load_or_parse(code_path)
                if bp is not None:
                    graph.ast_by_name[name] = bp
                    lib_name = self._record_library_name(name, code_path)
                    graph.add_library_dependencies(lib_name, dep_libs)
                    graph.index_from_basepic(
                        bp, source_path=code_path, library_name=lib_name
                    )  # aggregate defs for global analysis [2]
                else:
                    msg = f"{name} transform produced no BasePicture (skipped)"
                    graph.missing.append(msg)
            except Exception as ex:
                if strict:
                    raise
                graph.missing.append(f"{name} parse/transform error: {ex}")
        else:
            # If we skipped vendor dir and the file exists there, mark as ignored vendor
            v_code = self._find_vendor_code(name)
            v_deps = self._find_vendor_deps(name)
            if v_code or v_deps:
                graph.ignored_vendor.append(f"{name} (vendor: {v_code or v_deps})")
                # Track as unavailable library for better error messages
                graph.unavailable_libraries.add(name.lower())
            else:
                msg = f"Missing code file for '{name}' ({self.mode.value})"
                if strict:
                    raise FileNotFoundError(msg)
                graph.missing.append(msg)
                # Track as unavailable library
                graph.unavailable_libraries.add(name.lower())

        self._stack.remove(key)
        self._visited.add(key)


# ---------- Merge: build a synthetic “project” BasePicture ----------
def merge_project_basepicture(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
    """
    Create a single BasePicture that contains all DataType and ModuleTypeDef
    definitions from the root and its dependencies, so analyzers can resolve
    types across files without changing SLTransformer.
    """
    # Moduletype defs are keyed by (library, name) so same-name types from different
    # libraries are preserved in the merged BasePicture.
    merged_datatypes: list[DataType] = list(graph.datatype_defs.values())
    merged_modtypes: list[ModuleTypeDef] = list(graph.moduletype_defs.values())

    lib_deps = {
        lib: sorted(deps)
        for lib, deps in (graph.library_dependencies or {}).items()
    }

    return BasePicture(
        header=root_bp.header,
        name=root_bp.name,
        position=root_bp.position,
        datatype_defs=merged_datatypes,
        moduletype_defs=merged_modtypes,
        localvariables=root_bp.localvariables,
        submodules=root_bp.submodules,
        moduledef=root_bp.moduledef,
        modulecode=root_bp.modulecode,
        origin_file=root_bp.origin_file,
        origin_lib=root_bp.origin_lib,
        library_dependencies=lib_deps,
    )


# ---------- Dump functions ----------
def _get_dump_dir() -> Path:
    """Get or create the dump directory."""
    from datetime import datetime
    dump_dir = Path.home() / ".sattlint" / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    return dump_dir


def dump_parse_tree(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the parse tree from the root BasePicture to a file."""
    from datetime import datetime
    project_bp, graph = project

    if project_bp.parse_tree is None:
        print("❌ No parse tree available for the root program.")
        return

    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"parse_tree_{project_bp.header.name}_{timestamp}.txt"

    output = project_bp.parse_tree.pretty()
    filename.write_text(output, encoding="utf-8")

    print(f"\n✔ Parse tree saved to: {filename}")
    print()


def dump_ast(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the AST (BasePicture) structure to a file."""
    from datetime import datetime
    project_bp, graph = project

    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"ast_{project_bp.header.name}_{timestamp}.txt"

    output = str(project_bp)
    filename.write_text(output, encoding="utf-8")

    print(f"\n✔ AST saved to: {filename}")
    print()


def dump_dependency_graph(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the dependency graph to a file."""
    from datetime import datetime
    project_bp, graph = project

    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"dependency_graph_{project_bp.header.name}_{timestamp}.txt"

    lines = ["--- Dependency Graph ---"]
    lines.append(f"Programs/Libraries parsed: {len(graph.ast_by_name)}")
    for name in sorted(graph.ast_by_name.keys()):
        bp = graph.ast_by_name[name]
        origin_info = f" (from {bp.origin_lib}/{bp.origin_file})" if bp.origin_lib or bp.origin_file else ""
        lines.append(f"  • {name}{origin_info}")

    if graph.datatype_defs:
        lines.append(f"\nDataType Definitions: {len(graph.datatype_defs)}")
        for name in sorted(graph.datatype_defs.keys()):
            dt = graph.datatype_defs[name]
            origin_info = f" (from {dt.origin_lib}/{dt.origin_file})" if dt.origin_lib or dt.origin_file else ""
            lines.append(f"  • {name}{origin_info}")

    if graph.moduletype_defs:
        lines.append(f"\nModuleType Definitions: {len(graph.moduletype_defs)}")
        for (_lib_key, _name_key, _file_key), mt in sorted(graph.moduletype_defs.items()):
            display = f"{mt.origin_lib}:{mt.name}" if mt.origin_lib else mt.name
            origin_info = f" (from {mt.origin_lib}/{mt.origin_file})" if mt.origin_lib or mt.origin_file else ""
            lines.append(f"  • {display}{origin_info}")

    if graph.library_dependencies:
        lines.append("\nLibrary dependencies:")
        for lib, deps in sorted(graph.library_dependencies.items()):
            dep_list = ", ".join(sorted(deps)) if deps else "<none>"
            lines.append(f"  • {lib} -> {dep_list}")

    if graph.missing:
        lines.append(f"\nMissing/Unresolved: {len(graph.missing)}")
        for msg in graph.missing:
            lines.append(f"  ⚠ {msg}")

    if graph.ignored_vendor:
        lines.append(f"\nIgnored Vendor: {len(graph.ignored_vendor)}")
        for msg in graph.ignored_vendor:
            lines.append(f"  ⓘ {msg}")

    output = "\n".join(lines)
    filename.write_text(output, encoding="utf-8")

    print(f"\n✔ Dependency graph saved to: {filename}")
    print()
