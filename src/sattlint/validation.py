"""Post-transform structural validation for SattLine ASTs."""

from __future__ import annotations

import re
from collections.abc import Iterator
from collections.abc import Sequence as AbcSequence
from dataclasses import dataclass
from typing import Any, cast

from lark import Tree

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FrameModule,
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
    Variable,
)

from ._validation_expression import (
    infer_expression_datatype as _infer_expression_datatype,
)
from ._validation_expression import (
    is_variable_ref_node as _is_variable_ref_node,
)
from ._validation_expression import (
    validate_builtin_call_types as _validate_builtin_call_types,
)
from ._validation_expression import (
    validate_expression_semantics as _validate_expression_semantics,
)
from ._validation_expression import (
    validate_no_string_literals_in_calls as _validate_no_string_literals_in_calls,
)
from ._validation_shared import (
    RawSourceValidationError,
    StructuralValidationError,
    ValidationWarningSink,
    _ref_span,
    _span_kwargs,
    _warn_or_raise,
)
from ._validation_type_helpers import (
    BUILTIN_DATATYPE_NAMES as _BUILTIN_DATATYPE_NAMES,
)
from ._validation_type_helpers import (
    assignment_type_matches as _assignment_type_matches,
)
from ._validation_type_helpers import (
    extract_time_literal as _extract_time_literal,
)
from ._validation_type_helpers import (
    format_datatype as _format_datatype,
)
from ._validation_type_helpers import (
    has_time_literal_marker as _has_time_literal_marker,
)
from ._validation_type_helpers import (
    infer_literal_datatype as _infer_literal_datatype,
)
from ._validation_type_helpers import (
    is_anytype_datatype as _is_anytype_datatype,
)
from ._validation_type_helpers import (
    is_string_simple_type as _is_string_simple_type,
)
from ._validation_type_helpers import (
    is_valid_duration_literal as _is_valid_duration_literal,
)
from ._validation_type_helpers import (
    is_valid_time_literal as _is_valid_time_literal,
)
from ._validation_type_helpers import (
    literal_matches_expected_datatype as _literal_matches_expected_datatype,
)
from ._validation_type_helpers import (
    resolve_ref_datatype as _resolve_ref_datatype,
)
from ._validation_type_helpers import (
    resolve_root_variable as _resolve_root_variable,
)
from ._validation_type_helpers import (
    resolve_variable_field_datatype as _resolve_variable_field_datatype,
)
from ._validation_type_helpers import (
    split_dotted_name as _split_dotted_name,
)
from ._validation_type_helpers import (
    suggest_datatype_name as _suggest_datatype_name,
)
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
_MAX_IDENTIFIER_LENGTH = 20
_TYPO_SUGGESTION_MAX_DISTANCE = 2
_RESERVED_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_ALLOWED_IDENTIFIER_KEYWORDS = frozenset(
    {
        const.GRAMMAR_VALUE_COLOUR.casefold(),
        const.GRAMMAR_VALUE_NEWWINDOW.casefold(),
    }
)

type VariableRef = dict[str, object]


def _build_reserved_identifier_keywords() -> frozenset[str]:
    reserved: set[str] = set()
    for name in dir(const):
        if not name.startswith("GRAMMAR_VALUE_"):
            continue
        value = getattr(const, name)
        if not isinstance(value, str) or _RESERVED_IDENTIFIER_RE.fullmatch(value) is None:
            continue
        if value.casefold() in _ALLOWED_IDENTIFIER_KEYWORDS:
            continue
        reserved.add(value.casefold())
    return frozenset(reserved)


_RESERVED_IDENTIFIER_KEYWORDS = _build_reserved_identifier_keywords()


def _identifier_length(name: str) -> int:
    if len(name) >= 2 and name.startswith("'") and name.endswith("'"):
        return len(name[1:-1])
    return len(name)


def _validate_identifier(
    name: str | None,
    context: str,
    *,
    check_reserved_keywords: bool = True,
) -> None:
    if not name:
        return
    if _identifier_length(name) > _MAX_IDENTIFIER_LENGTH:
        raise StructuralValidationError(f"{context} name {name!r} exceeds {_MAX_IDENTIFIER_LENGTH} characters")
    if (
        check_reserved_keywords
        and not (len(name) >= 2 and name.startswith("'") and name.endswith("'"))
        and name.casefold() in _RESERVED_IDENTIFIER_KEYWORDS
    ):
        raise StructuralValidationError(f"{context} name {name!r} is a reserved SattLine keyword")


def _validate_declared_variable(
    variable: Variable,
    context: str,
    *,
    type_graph: TypeGraph,
    known_datatypes: AbcSequence[str],
    allow_unresolved_external_datatypes: bool = False,
    is_record_field: bool = False,
    is_parameter: bool = False,
) -> None:
    if isinstance(variable.datatype, str):
        if _is_anytype_datatype(variable.datatype):
            pass
        elif not type_graph.has_record(variable.datatype):
            suggestion_candidates = _BUILTIN_DATATYPE_NAMES if allow_unresolved_external_datatypes else known_datatypes
            suggestion = _suggest_datatype_name(variable.datatype, suggestion_candidates)
            if suggestion is not None:
                raise StructuralValidationError(
                    f"{context} variable {variable.name!r} uses unknown datatype {variable.datatype_text!r}; did you mean {suggestion!r}?",
                    **_span_kwargs(variable.declaration_span),
                )
            if not allow_unresolved_external_datatypes:
                raise StructuralValidationError(
                    f"{context} variable {variable.name!r} uses unknown datatype {variable.datatype_text!r}",
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
            raise StructuralValidationError(f"{context} has duplicate {kind} names {seen[folded]!r} and {name!r}")
        seen[folded] = name


def _iter_nested_sequence_nodes(nodes: AbcSequence[object] | None) -> Iterator[object]:
    for node in nodes or ():
        yield node
        if isinstance(node, SFCAlternative | SFCParallel):
            for branch in node.branches or ():
                yield from _iter_nested_sequence_nodes(branch)
        elif isinstance(node, SFCSubsequence | SFCTransitionSub):
            yield from _iter_nested_sequence_nodes(node.body)


def _collect_sequence_labels(nodes: list[object], labels: dict[str, str], _context: str) -> None:
    for node in _iter_nested_sequence_nodes(nodes):
        label: str | None = None
        if (
            isinstance(node, SFCStep)
            or (isinstance(node, SFCTransition) and node.name)
            or isinstance(node, SFCSubsequence | SFCTransitionSub)
        ):
            label = node.name

        if label:
            folded = label.casefold()
            labels.setdefault(folded, label)


def _collect_sequence_label_counts(nodes: list[object], counts: dict[str, int]) -> None:
    for node in _iter_nested_sequence_nodes(nodes):
        if isinstance(node, SFCStep | SFCTransition | SFCSubsequence | SFCTransitionSub):
            label_name = getattr(node, "name", None)
            if isinstance(label_name, str) and label_name:
                folded = label_name.casefold()
                counts[folded] = counts.get(folded, 0) + 1


def _collect_label_names(nodes: list[object], names: set[str]) -> None:
    """Collect all step/transition/subsequence label names (case-folded) without duplicate checks."""
    for node in _iter_nested_sequence_nodes(nodes):
        if isinstance(node, SFCStep | SFCTransition | SFCSubsequence | SFCTransitionSub):
            label_name = getattr(node, "name", None)
            if isinstance(label_name, str) and label_name:
                names.add(label_name.casefold())


def _collect_sequence_step_features(
    nodes: list[object],
    *,
    seqcontrol: bool,
    seqtimer: bool,
    known_steps: dict[str, str],
    available_features: dict[str, set[str]],
) -> None:
    for node in _iter_nested_sequence_nodes(nodes):
        if isinstance(node, SFCStep):
            key = node.name.casefold()
            known_steps.setdefault(key, node.name)
            features = available_features.setdefault(key, set())
            features.add("x")
            if seqcontrol:
                features.add("hold")
                features.add("reset")
            if seqtimer:
                features.add("t")


def _collect_sequence_scope_features(
    sequence: Sequence,
    *,
    known_sequences: dict[str, str],
    available_sequence_features: dict[str, set[str]],
) -> None:
    key = sequence.name.casefold()
    known_sequences.setdefault(key, sequence.name)
    features = available_sequence_features.setdefault(key, set())
    if sequence.seqcontrol:
        features.add("hold")
        features.add("reset")


def _iter_sequence_node_refs(nodes: list[object]) -> AbcSequence[dict[str, object]]:
    refs: list[dict[str, object]] = []
    for node in _iter_nested_sequence_nodes(nodes):
        if isinstance(node, SFCStep):
            for statements in (node.code.enter, node.code.active, node.code.exit):
                for statement in statements or []:
                    for ref in _iter_variable_refs(statement):
                        refs.append(ref)
            continue

        if isinstance(node, SFCTransition):
            for ref in _iter_variable_refs(node.condition):
                refs.append(ref)

    return refs


def _validate_step_auto_variable_refs(
    modulecode: ModuleCode | None,
    env: dict[str, Variable],
    context: str,
) -> None:
    if modulecode is None:
        return

    known_steps: dict[str, str] = {}
    available_features: dict[str, set[str]] = {}
    known_sequences: dict[str, str] = {}
    available_sequence_features: dict[str, set[str]] = {}

    for sequence in cast(list[object], modulecode.sequences or []):
        if not isinstance(sequence, Sequence):
            continue
        _collect_sequence_scope_features(
            sequence,
            known_sequences=known_sequences,
            available_sequence_features=available_sequence_features,
        )
        _collect_sequence_step_features(
            sequence.code or [],
            seqcontrol=bool(sequence.seqcontrol),
            seqtimer=bool(sequence.seqtimer),
            known_steps=known_steps,
            available_features=available_features,
        )

    if not known_steps and not known_sequences:
        return

    refs: list[dict[str, object]] = []
    for equation in cast(list[object], modulecode.equations or []):
        if not isinstance(equation, Equation):
            continue
        for statement in equation.code or []:
            for ref in _iter_variable_refs(statement):
                refs.append(ref)
    for sequence in cast(list[object], modulecode.sequences or []):
        if not isinstance(sequence, Sequence):
            continue
        refs.extend(_iter_sequence_node_refs(sequence.code or []))

    for ref in refs:
        full_name = ref.get(const.KEY_VAR_NAME)
        if not isinstance(full_name, str):
            continue

        base_name, field_path = _split_dotted_name(full_name)
        if not base_name or len(field_path) != 1:
            continue

        suffix = field_path[0].casefold()
        if suffix not in {"x", "hold", "reset", "t"}:
            continue

        if base_name.casefold() in env:
            continue

        base_key = base_name.casefold()
        step_name = known_steps.get(base_key)
        if step_name is None:
            sequence_name = known_sequences.get(base_key)
            if sequence_name is not None and suffix in {"hold", "reset"}:
                sequence_features = available_sequence_features.get(base_key, set())
                if suffix == "hold" and "hold" not in sequence_features:
                    message = (
                        f"{context} variable reference {full_name!r} is not available: "
                        f"sequence {sequence_name!r} only exposes .Hold when it enables SeqControl"
                    )
                elif suffix == "reset" and "reset" not in sequence_features:
                    message = (
                        f"{context} variable reference {full_name!r} is not available: "
                        f"sequence {sequence_name!r} only exposes .Reset when it enables SeqControl"
                    )
                else:
                    continue
            else:
                message = (
                    f"{context} variable reference {full_name!r} is not available: "
                    f"no sequence step named {base_name!r} exists in this module"
                )
        else:
            features = available_features.get(base_key, set())
            if suffix == "hold" and "hold" not in features:
                message = (
                    f"{context} variable reference {full_name!r} is not available: "
                    f"step {step_name!r} only exposes .Hold when its sequence enables SeqControl"
                )
            elif suffix == "reset" and "reset" not in features:
                message = (
                    f"{context} variable reference {full_name!r} is not available: "
                    f"step {step_name!r} only exposes .Reset when its sequence enables SeqControl"
                )
            elif suffix == "t" and "t" not in features:
                message = (
                    f"{context} variable reference {full_name!r} is not available: "
                    f"step {step_name!r} only exposes .T when its sequence enables SeqTimer"
                )
            else:
                continue

        raise StructuralValidationError(
            message,
            **_span_kwargs(_ref_span(ref)),
            length=max(len(full_name), 1),
        )


def _parallel_branch_trailer(node: object) -> str | None:
    if isinstance(node, SFCTransition):
        return "SEQTRANSITION"
    if isinstance(node, SFCTransitionSub):
        return "SUBSEQTRANSITION"
    if isinstance(node, SFCFork):
        return "SEQFORK"
    if isinstance(node, SFCBreak):
        return "SEQBREAK"
    return None


def _iter_variable_refs(node: object) -> Iterator[VariableRef]:
    if _is_variable_ref_node(node):
        yield node
        return

    if isinstance(node, Tree):
        for child in cast(list[object], cast(Any, node).children):
            yield from _iter_variable_refs(child)
        return

    if isinstance(node, tuple):
        for item in cast(tuple[object, ...], node):
            yield from _iter_variable_refs(item)
        return

    if isinstance(node, list):
        for item in cast(list[object], node):
            yield from _iter_variable_refs(item)


def _validate_variable_refs(
    node: object,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    for ref in _iter_variable_refs(node):
        state = ref.get("state")
        if not isinstance(state, str) or not state:
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


def _validate_statement_list(
    statements: list[object],
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
    *,
    allow_old_state_assignment: bool,
) -> None:
    for statement in statements:
        _validate_expression_semantics(statement, env, type_graph, context)
        if isinstance(statement, tuple):
            tuple_statement = cast(tuple[object, ...], statement)
            if (
                len(tuple_statement) == 3
                and tuple_statement[0] == const.KEY_ASSIGN
                and _is_variable_ref_node(tuple_statement[1])
            ):
                assign_statement = cast(tuple[str, VariableRef, object], tuple_statement)
                target_ref = assign_statement[1]
                target_name = str(target_ref.get(const.KEY_VAR_NAME, "<unknown>"))
                target_state = target_ref.get("state")
                if (
                    not allow_old_state_assignment
                    and isinstance(target_state, str)
                    and target_state.casefold() == const.GRAMMAR_VALUE_OLD.casefold()
                ):
                    raise StructuralValidationError(
                        f"{context} assignment target {target_name!r} must not use OLD state access",
                        **_span_kwargs(_ref_span(target_ref)),
                        length=max(len(target_name), 1),
                    )
                variable = _resolve_root_variable(target_ref, env)
                if variable is not None and variable.const:
                    raise StructuralValidationError(
                        f"{context} assignment writes to CONST variable {variable.name!r}",
                        **_span_kwargs(_ref_span(target_ref)),
                    )
                if variable is not None and _is_string_simple_type(variable.datatype):
                    raise StructuralValidationError(
                        f"{context} assignment to string variable {variable.name!r} is not allowed;"
                        " use CopyString() or CopyVar() to copy strings",
                        **_span_kwargs(_ref_span(target_ref)),
                    )
                target_datatype = _resolve_ref_datatype(target_ref, env, type_graph)
                actual_datatype = _infer_expression_datatype(assign_statement[2], env, type_graph)
                if (
                    target_datatype is not None
                    and actual_datatype is not None
                    and not _assignment_type_matches(actual_datatype, target_datatype)
                ):
                    source_description = "expression"
                    if _is_variable_ref_node(assign_statement[2]):
                        source_description = str(assign_statement[2][const.KEY_VAR_NAME])
                    raise StructuralValidationError(
                        f"{context} assigns {source_description!r} with datatype {_format_datatype(actual_datatype)!r} "
                        f"to target {str(target_ref[const.KEY_VAR_NAME])!r} with datatype {_format_datatype(target_datatype)!r}",
                        **_span_kwargs(_ref_span(target_ref)),
                    )
        statement_node = cast(object, statement)
        _validate_variable_refs(statement_node, env, type_graph, context)
        _validate_no_string_literals_in_calls(statement_node, context)
        _validate_builtin_call_types(statement_node, env, type_graph, context)


def _validate_code_blocks(
    code: Any,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
    *,
    allow_old_state_assignment: bool,
) -> None:
    _validate_statement_list(
        code.enter,
        env,
        type_graph,
        f"{context} ENTERCODE",
        allow_old_state_assignment=allow_old_state_assignment,
    )
    _validate_statement_list(
        code.active,
        env,
        type_graph,
        f"{context} ACTIVECODE",
        allow_old_state_assignment=allow_old_state_assignment,
    )
    _validate_statement_list(
        code.exit,
        env,
        type_graph,
        f"{context} EXITCODE",
        allow_old_state_assignment=allow_old_state_assignment,
    )


def _validate_sequence_nodes(
    nodes: list[object],
    context: str,
    *,
    labels: dict[str, str],
    label_counts: dict[str, int],
    module_labels: frozenset[str] = frozenset(),
    module_label_counts: dict[str, int] | None = None,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    require_init_step: bool,
    warning_sink: ValidationWarningSink | None = None,
    allow_old_state_assignment: bool = True,
) -> None:
    previous_unit_name: str | None = None
    previous_unit_kind: str | None = None
    previous_transition_name: str | None = None
    init_steps = 0
    missing_initial_init_step = False

    if require_init_step and (not nodes or not isinstance(nodes[0], SFCStep) or nodes[0].kind != "init"):
        missing_initial_init_step = True
        _warn_or_raise(
            f"{context} must start with exactly one SEQINITSTEP",
            warning_sink=warning_sink,
        )

    def recurse(branch_nodes: list[object] | None, nested_context: str) -> None:
        _validate_sequence_nodes(
            branch_nodes or [],
            nested_context,
            labels=labels,
            label_counts=label_counts,
            module_labels=module_labels,
            module_label_counts=module_label_counts,
            env=env,
            type_graph=type_graph,
            require_init_step=False,
            warning_sink=warning_sink,
            allow_old_state_assignment=allow_old_state_assignment,
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
            if previous_unit_name is not None:
                raise StructuralValidationError(
                    f"{context} has step {node.name!r} immediately after "
                    f"{previous_unit_kind} {previous_unit_name!r} without an intervening transition"
                )
            _validate_code_blocks(
                node.code,
                env,
                type_graph,
                f"{context} step {node.name!r}",
                allow_old_state_assignment=allow_old_state_assignment,
            )
            previous_unit_name = node.name
            previous_unit_kind = "step"
            previous_transition_name = None
            continue

        previous_unit_name = None
        previous_unit_kind = None

        if isinstance(node, SFCTransition | SFCTransitionSub):
            transition_name = node.name if isinstance(node.name, str) and node.name else "<unnamed>"
            if previous_transition_name is not None:
                raise StructuralValidationError(
                    f"{context} has transition {transition_name!r} immediately after transition "
                    f"{previous_transition_name!r}; only one transition may execute per cycle in the same sequence path"
                )
            previous_transition_name = transition_name
        else:
            previous_transition_name = None

        if isinstance(node, SFCTransition):
            _validate_identifier(node.name, f"{context} transition")
        elif isinstance(node, SFCTransitionSub):
            _validate_identifier(node.name, f"{context} transition-sub")
            if node.body and isinstance(node.body[0], SFCStep):
                raise StructuralValidationError(
                    f"{context} transition-sub {node.name!r} must not start with SEQSTEP; "
                    f"SUBSEQTRANSITION bodies must enter through a transition"
                )
            recurse(node.body, f"{context} transition-sub {node.name!r}")
        elif isinstance(node, SFCSubsequence):
            _validate_identifier(node.name, f"{context} subsequence")
            recurse(node.body, f"{context} subsequence {node.name!r}")
        elif isinstance(node, SFCAlternative):
            for index, branch in enumerate(node.branches, start=1):
                recurse(branch, f"{context} alternative branch {index}")
        elif isinstance(node, SFCParallel):
            for index, branch in enumerate(node.branches, start=1):
                recurse(branch, f"{context} parallel branch {index}")
                if branch:
                    trailer = _parallel_branch_trailer(branch[-1])
                    if trailer is not None:
                        raise StructuralValidationError(
                            f"{context} parallel branch {index} ends with {trailer}; "
                            f"PARALLELBRANCH/ENDPARALLEL must follow a completed sequence unit"
                        )
            previous_unit_name = "ENDPARALLEL"
            previous_unit_kind = "parallel block"
        elif isinstance(node, SFCFork):
            for target in node.targets:
                _validate_identifier(target, f"{context} fork target")
                target_key = target.casefold()
                if target_key not in labels and target_key not in module_labels:
                    raise StructuralValidationError(
                        f"{context} has SEQFORK target {target!r} that does not exist in the sequence or module"
                    )
                if label_counts.get(target_key, 0) > 1 or (module_label_counts or {}).get(target_key, 0) > 1:
                    raise StructuralValidationError(
                        f"{context} has ambiguous SEQFORK target {target!r}; "
                        "that label is declared multiple times in the sequence or module"
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
    warning_sink: ValidationWarningSink | None = None,
    allow_old_state_assignment: bool = True,
) -> None:
    if modulecode is None:
        return

    _validate_step_auto_variable_refs(modulecode, env, context)

    for equation in cast(list[object], modulecode.equations or []):
        if not isinstance(equation, Equation):
            continue
        _validate_identifier(equation.name, f"{context} equation")
        _validate_statement_list(
            equation.code or [],
            env,
            type_graph,
            f"{context} equation {equation.name!r}",
            allow_old_state_assignment=allow_old_state_assignment,
        )

    module_label_set: set[str] = set()
    module_label_counts: dict[str, int] = {}
    for sequence in cast(list[object], modulecode.sequences or []):
        if not isinstance(sequence, Sequence):
            continue
        _collect_label_names(sequence.code or [], module_label_set)
        _collect_sequence_label_counts(sequence.code or [], module_label_counts)
    module_labels = frozenset(module_label_set)

    for sequence in cast(list[object], modulecode.sequences or []):
        if not isinstance(sequence, Sequence):
            continue
        _validate_identifier(sequence.name, f"{context} sequence")
        labels: dict[str, str] = {}
        label_counts: dict[str, int] = {}
        _collect_sequence_labels(sequence.code or [], labels, f"{context} sequence {sequence.name!r}")
        _collect_sequence_label_counts(sequence.code or [], label_counts)
        _validate_sequence_nodes(
            sequence.code or [],
            f"{context} sequence {sequence.name!r}",
            labels=labels,
            label_counts=label_counts,
            module_labels=module_labels,
            module_label_counts=module_label_counts,
            env=env,
            type_graph=type_graph,
            require_init_step=True,
            warning_sink=warning_sink,
            allow_old_state_assignment=allow_old_state_assignment,
        )


def _validate_variable_list(
    variables: list[Variable] | None,
    context: str,
    *,
    type_graph: TypeGraph | None = None,
    known_datatypes: AbcSequence[str] = (),
    allow_unresolved_external_datatypes: bool = False,
    is_record_field: bool = False,
    is_parameter: bool = False,
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
                is_record_field=is_record_field,
                is_parameter=is_parameter,
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
        if len(datatype.var_list or []) == 1:
            raise StructuralValidationError(
                f"{context} datatype {datatype.name!r} must declare at least 2 fields",
                **_span_kwargs(datatype.declaration_span),
            )
        _validate_variable_list(
            datatype.var_list,
            f"{context} datatype {datatype.name!r}",
            type_graph=type_graph,
            known_datatypes=known_datatypes,
            allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
            is_record_field=True,
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


@dataclass(frozen=True)
class _ModuleValidationPolicy:
    allow_parameterless_module_mappings: bool = False
    warn_unknown_parameter_targets: bool = False
    warn_incompatible_parameter_mappings: bool = False
    warning_sink: ValidationWarningSink | None = None
    allow_old_state_assignment: bool = True


def _validate_parameter_mappings(
    parametermappings: AbcSequence[ParameterMapping] | None,
    context: str,
    *,
    type_graph: TypeGraph,
    expected_parameters: dict[str, Variable] | None = None,
    source_env: dict[str, Variable] | None = None,
    policy: _ModuleValidationPolicy,
) -> None:
    seen: dict[str, str] = {}
    for mapping in parametermappings or []:
        if not hasattr(mapping, "target"):
            continue

        target_ref = cast(VariableRef | None, getattr(mapping, "target", None))
        if not _is_variable_ref_node(target_ref):
            continue
        target_name, target_span = str(target_ref.get(const.KEY_VAR_NAME)), _ref_span(target_ref)
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
            if policy.allow_parameterless_module_mappings and not expected_parameters:
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
        source = cast(object, getattr(mapping, "source", None))
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
        elif _is_variable_ref_node(source) and source_env is not None:
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
            warning_sink=policy.warning_sink if policy.warn_incompatible_parameter_mappings else None,
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
    policy: _ModuleValidationPolicy | None = None,
) -> None:
    active_policy = policy or _ModuleValidationPolicy()

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
            policy=active_policy,
        )
        _validate_module_code(
            module.modulecode,
            module_context,
            env,
            type_graph,
            warning_sink=active_policy.warning_sink,
            allow_old_state_assignment=active_policy.allow_old_state_assignment,
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
                policy=active_policy,
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
            warning_sink=active_policy.warning_sink,
            allow_old_state_assignment=active_policy.allow_old_state_assignment,
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
                policy=active_policy,
            )
        return

    if isinstance(module, ModuleTypeInstance):
        _validate_identifier(module.header.name, f"{context} module instance")
        _validate_identifier(module.moduletype_name, f"{context} module type reference")
        matches = moduletype_index.get(module.moduletype_name.casefold(), [])
        expected_parameters = None
        if len(matches) == 1:
            expected_parameters = {variable.name.casefold(): variable for variable in matches[0].moduleparameters or []}
        _validate_parameter_mappings(
            module.parametermappings,
            f"{context} module instance {module.header.name!r}",
            type_graph=type_graph,
            expected_parameters=expected_parameters,
            source_env=parent_env,
            policy=active_policy,
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
    allow_old_state_assignment: bool = True,
    warn_unknown_parameter_targets: bool = False,
    warn_incompatible_parameter_mappings: bool = False,
    warning_sink: ValidationWarningSink | None = None,
) -> None:
    _validate_identifier(basepic.header.name, "BasePicture", check_reserved_keywords=False)
    if basepic.program_name is not None:
        _validate_identifier(basepic.program_name, "BasePicture program name")
    base_moduletype_defs = [
        moduletype
        for moduletype in cast(AbcSequence[object], basepic.moduletype_defs or [])
        if isinstance(moduletype, ModuleTypeDef)
    ]
    available_external_moduletype_defs = [
        moduletype
        for moduletype in cast(AbcSequence[object], external_moduletype_defs or [])
        if isinstance(moduletype, ModuleTypeDef)
    ]
    _ensure_unique_names([moduletype.name for moduletype in base_moduletype_defs], "BasePicture", "moduletype")
    available_datatypes = [*(basepic.datatype_defs or []), *(external_datatypes or [])]
    available_moduletype_defs = [*base_moduletype_defs, *available_external_moduletype_defs]

    type_graph = TypeGraph.from_datatypes(available_datatypes)
    known_datatypes = tuple(
        [datatype.value for datatype in Simple_DataType] + [datatype.name for datatype in available_datatypes]
    )
    moduletype_index: dict[str, list[ModuleTypeDef]] = {}
    for moduletype in available_moduletype_defs:
        moduletype_index.setdefault(moduletype.name.casefold(), []).append(moduletype)

    policy = _ModuleValidationPolicy(
        allow_parameterless_module_mappings=allow_parameterless_module_mappings,
        warn_unknown_parameter_targets=warn_unknown_parameter_targets,
        warn_incompatible_parameter_mappings=warn_incompatible_parameter_mappings,
        warning_sink=warning_sink,
        allow_old_state_assignment=allow_old_state_assignment,
    )

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

    for moduletype in base_moduletype_defs:
        _validate_identifier(moduletype.name, "BasePicture moduletype")
        moduletype_context = f"BasePicture moduletype {moduletype.name!r}"
        _validate_variable_list(
            moduletype.moduleparameters,
            moduletype_context,
            type_graph=type_graph,
            known_datatypes=known_datatypes,
            allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
            is_parameter=True,
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
            warning_sink=policy.warning_sink,
            allow_old_state_assignment=policy.allow_old_state_assignment,
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
                policy=policy,
            )

    _validate_module_code(
        basepic.modulecode,
        "BasePicture",
        base_env,
        type_graph,
        warning_sink=policy.warning_sink,
        allow_old_state_assignment=policy.allow_old_state_assignment,
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
            policy=policy,
        )


# Re-exports for backward compatibility with external imports
__all__ = [
    "RawSourceValidationError",
    "StructuralValidationError",
    # Type helpers exported to analyzers.validators
    "_assignment_type_matches",
    "_extract_time_literal",
    "_has_time_literal_marker",
    "_infer_literal_datatype",
    "_is_valid_time_literal",
    "_literal_matches_expected_datatype",
    "_resolve_variable_field_datatype",
    "_split_dotted_name",
    "validate_transformed_basepicture",
]
