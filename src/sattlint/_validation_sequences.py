"""Sequence and module-code validation helpers for validation.py."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from collections.abc import Sequence as AbcSequence
from dataclasses import dataclass
from typing import Any, cast

from lark import Tree

from sattline_parser.models.ast_model import (
    Equation,
    ModuleCode,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Variable,
)

from ._validation_expression import infer_expression_datatype as _infer_expression_datatype
from ._validation_expression import is_variable_ref_node as _is_variable_ref_node
from ._validation_expression import validate_builtin_call_types as _validate_builtin_call_types
from ._validation_expression import validate_expression_semantics as _validate_expression_semantics
from ._validation_expression import validate_no_string_literals_in_calls as _validate_no_string_literals_in_calls
from ._validation_shared import (
    StructuralValidationError,
    ValidationNotice,
    ValidationWarningSink,
    ref_span,
    span_kwargs,
    warn_or_raise,
)
from ._validation_type_helpers import (
    assignment_type_matches as _assignment_type_matches,
)
from ._validation_type_helpers import (
    format_datatype as _format_datatype,
)
from ._validation_type_helpers import (
    is_string_simple_type as _is_string_simple_type,
)
from ._validation_type_helpers import (
    resolve_ref_datatype as _resolve_ref_datatype,
)
from ._validation_type_helpers import (
    resolve_root_variable as _resolve_root_variable,
)
from ._validation_type_helpers import (
    split_dotted_name as _split_dotted_name,
)
from .grammar import constants as const
from .resolution.type_graph import TypeGraph
from .types import VariableRef

_SUPPRESSED_SEMANTIC_ERROR_PREFIX = (
    "Module-code semantic validation downgraded from error to warning by active policy: "
)


@dataclass(frozen=True)
class ModuleCodeValidationPolicy:
    warning_sink: ValidationWarningSink | None = None
    allow_old_state_assignment: bool = True
    suppress_semantic_errors: bool = False


def _handle_statement_validation_error(
    exc: StructuralValidationError,
    *,
    policy: ModuleCodeValidationPolicy,
) -> None:
    if not policy.suppress_semantic_errors:
        raise exc
    if policy.warning_sink is not None:
        policy.warning_sink(
            ValidationNotice(
                message=f"{_SUPPRESSED_SEMANTIC_ERROR_PREFIX}{exc}",
                line=exc.line,
                column=exc.column,
                length=exc.length,
            )
        )


def iter_nested_sequence_nodes(nodes: AbcSequence[object] | None) -> Iterator[object]:
    for node in nodes or ():
        yield node
        if isinstance(node, SFCAlternative | SFCParallel):
            for branch in node.branches or ():
                yield from iter_nested_sequence_nodes(branch)
        elif isinstance(node, SFCSubsequence | SFCTransitionSub):
            yield from iter_nested_sequence_nodes(node.body)


def collect_sequence_labels(nodes: list[object], labels: dict[str, str], _context: str) -> None:
    for node in iter_nested_sequence_nodes(nodes):
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


def collect_sequence_label_counts(nodes: list[object], counts: dict[str, int]) -> None:
    for node in iter_nested_sequence_nodes(nodes):
        if isinstance(node, SFCStep | SFCTransition | SFCSubsequence | SFCTransitionSub):
            label_name = getattr(node, "name", None)
            if isinstance(label_name, str) and label_name:
                folded = label_name.casefold()
                counts[folded] = counts.get(folded, 0) + 1


def collect_label_names(nodes: list[object], names: set[str]) -> None:
    for node in iter_nested_sequence_nodes(nodes):
        if isinstance(node, SFCStep | SFCTransition | SFCSubsequence | SFCTransitionSub):
            label_name = getattr(node, "name", None)
            if isinstance(label_name, str) and label_name:
                names.add(label_name.casefold())


def collect_sequence_step_features(
    nodes: list[object],
    *,
    seqcontrol: bool,
    seqtimer: bool,
    known_steps: dict[str, str],
    available_features: dict[str, set[str]],
) -> None:
    for node in iter_nested_sequence_nodes(nodes):
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


def collect_sequence_scope_features(
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


def iter_sequence_node_refs(nodes: list[object]) -> AbcSequence[dict[str, object]]:
    refs: list[dict[str, object]] = []
    for node in iter_nested_sequence_nodes(nodes):
        if isinstance(node, SFCStep):
            for statements in (node.code.enter, node.code.active, node.code.exit):
                for statement in statements or []:
                    for ref in iter_variable_refs(statement):
                        refs.append(ref)
            continue

        if isinstance(node, SFCTransition):
            for ref in iter_variable_refs(node.condition):
                refs.append(ref)

    return refs


def validate_step_auto_variable_refs(  # noqa: PLR0915
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
        collect_sequence_scope_features(
            sequence,
            known_sequences=known_sequences,
            available_sequence_features=available_sequence_features,
        )
        collect_sequence_step_features(
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
            for ref in iter_variable_refs(statement):
                refs.append(ref)
    for sequence in cast(list[object], modulecode.sequences or []):
        if not isinstance(sequence, Sequence):
            continue
        refs.extend(iter_sequence_node_refs(sequence.code or []))

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
            **span_kwargs(ref_span(ref)),
            length=max(len(full_name), 1),
        )


def parallel_branch_trailer(node: object) -> str | None:
    if isinstance(node, SFCTransition):
        return "SEQTRANSITION"
    if isinstance(node, SFCTransitionSub):
        return "SUBSEQTRANSITION"
    if isinstance(node, SFCFork):
        return "SEQFORK"
    if isinstance(node, SFCBreak):
        return "SEQBREAK"
    return None


def iter_variable_refs(node: object) -> Iterator[VariableRef]:
    if _is_variable_ref_node(node):
        yield node
        return

    if isinstance(node, Tree):
        tree_node = cast(Tree[object], node)
        tree_children = cast(list[object], tree_node.children)
        for child in tree_children:
            yield from iter_variable_refs(child)
        return

    if isinstance(node, tuple):
        for item in cast(tuple[object, ...], node):
            yield from iter_variable_refs(item)
        return

    if isinstance(node, list):
        for item in cast(list[object], node):
            yield from iter_variable_refs(item)


def validate_variable_refs(
    node: object,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
) -> None:
    for ref in iter_variable_refs(node):
        state = ref.get("state")
        if not isinstance(state, str) or not state:
            continue

        full_name = ref[const.KEY_VAR_NAME]
        base_name, field_path = _split_dotted_name(str(full_name))
        variable = env.get(base_name.casefold())
        if variable is None:
            continue

        resolved_state = variable.state
        current_datatype = variable.datatype
        for field_name in field_path:
            if isinstance(current_datatype, str):
                field = type_graph.field(current_datatype, field_name)
                if field is None:
                    resolved_state = None
                    break
                current_datatype = field.datatype
                resolved_state = field.state
                continue
            resolved_state = None
            break

        if resolved_state is not None and not resolved_state:
            raise StructuralValidationError(
                f"{context} uses {state.upper()} on non-STATE variable {str(full_name)!r}",
                **span_kwargs(ref_span(ref)),
                length=max(len(str(full_name)), 1),
            )


def validate_statement_list(
    statements: list[object],
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
    *,
    policy: ModuleCodeValidationPolicy,
) -> None:
    for statement in statements:
        try:
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
                        not policy.allow_old_state_assignment
                        and isinstance(target_state, str)
                        and target_state.casefold() == const.GRAMMAR_VALUE_OLD.casefold()
                    ):
                        raise StructuralValidationError(
                            f"{context} assignment target {target_name!r} must not use OLD state access",
                            **span_kwargs(ref_span(target_ref)),
                            length=max(len(target_name), 1),
                        )
                    variable = _resolve_root_variable(target_ref, env)
                    if variable is not None and variable.const:
                        raise StructuralValidationError(
                            f"{context} assignment writes to CONST variable {variable.name!r}",
                            **span_kwargs(ref_span(target_ref)),
                        )
                    if variable is not None and _is_string_simple_type(variable.datatype):
                        raise StructuralValidationError(
                            f"{context} assignment to string variable {variable.name!r} is not allowed;"
                            " use CopyString() or CopyVar() to copy strings",
                            **span_kwargs(ref_span(target_ref)),
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
                            **span_kwargs(ref_span(target_ref)),
                        )
            statement_node = cast(object, statement)
            validate_variable_refs(statement_node, env, type_graph, context)
            _validate_no_string_literals_in_calls(statement_node, context)
            _validate_builtin_call_types(statement_node, env, type_graph, context)
        except StructuralValidationError as exc:
            _handle_statement_validation_error(exc, policy=policy)


def validate_code_blocks(
    code: Any,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    context: str,
    *,
    policy: ModuleCodeValidationPolicy,
) -> None:
    validate_statement_list(
        code.enter,
        env,
        type_graph,
        f"{context} ENTERCODE",
        policy=policy,
    )
    validate_statement_list(
        code.active,
        env,
        type_graph,
        f"{context} ACTIVECODE",
        policy=policy,
    )
    validate_statement_list(
        code.exit,
        env,
        type_graph,
        f"{context} EXITCODE",
        policy=policy,
    )


def validate_sequence_nodes(  # noqa: PLR0915
    nodes: list[object],
    context: str,
    *,
    validate_identifier: Callable[[str | None, str], None],
    labels: dict[str, str],
    label_counts: dict[str, int],
    module_labels: frozenset[str] = frozenset(),
    module_label_counts: dict[str, int] | None = None,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    require_init_step: bool,
    warning_sink: ValidationWarningSink | None = None,
    allow_old_state_assignment: bool = True,
    suppress_semantic_errors: bool = False,
    module_code_policy: ModuleCodeValidationPolicy | None = None,
) -> None:
    active_module_code_policy = module_code_policy or ModuleCodeValidationPolicy(
        warning_sink=warning_sink,
        allow_old_state_assignment=allow_old_state_assignment,
        suppress_semantic_errors=suppress_semantic_errors,
    )
    effective_warning_sink = active_module_code_policy.warning_sink
    previous_unit_name: str | None = None
    previous_unit_kind: str | None = None
    previous_transition_name: str | None = None
    init_steps = 0
    missing_initial_init_step = False

    if require_init_step and (not nodes or not isinstance(nodes[0], SFCStep) or nodes[0].kind != "init"):
        missing_initial_init_step = True
        warn_or_raise(
            f"{context} must start with exactly one SEQINITSTEP",
            warning_sink=effective_warning_sink,
        )

    def recurse(branch_nodes: list[object] | None, nested_context: str) -> None:
        validate_sequence_nodes(
            branch_nodes or [],
            nested_context,
            validate_identifier=validate_identifier,
            labels=labels,
            label_counts=label_counts,
            module_labels=module_labels,
            module_label_counts=module_label_counts,
            env=env,
            type_graph=type_graph,
            require_init_step=False,
            module_code_policy=active_module_code_policy,
        )

    for index, node in enumerate(nodes):
        if isinstance(node, SFCStep):
            validate_identifier(node.name, f"{context} step")
            if node.kind == "init":
                init_steps += 1
                if index != 0:
                    warn_or_raise(
                        f"{context} has SEQINITSTEP {node.name!r} outside the first position",
                        warning_sink=effective_warning_sink,
                    )
            if previous_unit_name is not None:
                raise StructuralValidationError(
                    f"{context} has step {node.name!r} immediately after "
                    f"{previous_unit_kind} {previous_unit_name!r} without an intervening transition"
                )
            validate_code_blocks(
                node.code,
                env,
                type_graph,
                f"{context} step {node.name!r}",
                policy=active_module_code_policy,
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
            validate_identifier(node.name, f"{context} transition")
        elif isinstance(node, SFCTransitionSub):
            validate_identifier(node.name, f"{context} transition-sub")
            if node.body and isinstance(node.body[0], SFCStep):
                raise StructuralValidationError(
                    f"{context} transition-sub {node.name!r} must not start with SEQSTEP; "
                    f"SUBSEQTRANSITION bodies must enter through a transition"
                )
            recurse(node.body, f"{context} transition-sub {node.name!r}")
        elif isinstance(node, SFCSubsequence):
            validate_identifier(node.name, f"{context} subsequence")
            recurse(node.body, f"{context} subsequence {node.name!r}")
        elif isinstance(node, SFCAlternative):
            for branch_index, branch in enumerate(node.branches, start=1):
                recurse(branch, f"{context} alternative branch {branch_index}")
        elif isinstance(node, SFCParallel):
            for branch_index, branch in enumerate(node.branches, start=1):
                recurse(branch, f"{context} parallel branch {branch_index}")
                if branch:
                    trailer = parallel_branch_trailer(branch[-1])
                    if trailer is not None:
                        raise StructuralValidationError(
                            f"{context} parallel branch {branch_index} ends with {trailer}; "
                            f"PARALLELBRANCH/ENDPARALLEL must follow a completed sequence unit"
                        )
            previous_unit_name = "ENDPARALLEL"
            previous_unit_kind = "parallel block"
        elif isinstance(node, SFCFork):
            for target in node.targets:
                validate_identifier(target, f"{context} fork target")
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
        warn_or_raise(
            f"{context} must contain exactly one SEQINITSTEP",
            warning_sink=effective_warning_sink,
        )


def validate_module_code(
    modulecode: ModuleCode | None,
    context: str,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    *,
    validate_identifier: Callable[[str | None, str], None],
    warning_sink: ValidationWarningSink | None = None,
    allow_old_state_assignment: bool = True,
    suppress_semantic_errors: bool = False,
    module_code_policy: ModuleCodeValidationPolicy | None = None,
) -> None:
    if modulecode is None:
        return

    active_module_code_policy = module_code_policy or ModuleCodeValidationPolicy(
        warning_sink=warning_sink,
        allow_old_state_assignment=allow_old_state_assignment,
        suppress_semantic_errors=suppress_semantic_errors,
    )

    validate_step_auto_variable_refs(modulecode, env, context)

    for equation in cast(list[object], modulecode.equations or []):
        if not isinstance(equation, Equation):
            continue
        validate_identifier(equation.name, f"{context} equation")
        validate_statement_list(
            equation.code or [],
            env,
            type_graph,
            f"{context} equation {equation.name!r}",
            policy=active_module_code_policy,
        )

    module_label_set: set[str] = set()
    module_label_counts: dict[str, int] = {}
    for sequence in cast(list[object], modulecode.sequences or []):
        if not isinstance(sequence, Sequence):
            continue
        collect_label_names(sequence.code or [], module_label_set)
        collect_sequence_label_counts(sequence.code or [], module_label_counts)
    module_labels = frozenset(module_label_set)

    for sequence in cast(list[object], modulecode.sequences or []):
        if not isinstance(sequence, Sequence):
            continue
        validate_identifier(sequence.name, f"{context} sequence")
        labels: dict[str, str] = {}
        label_counts: dict[str, int] = {}
        collect_sequence_labels(sequence.code or [], labels, f"{context} sequence {sequence.name!r}")
        collect_sequence_label_counts(sequence.code or [], label_counts)
        validate_sequence_nodes(
            sequence.code or [],
            f"{context} sequence {sequence.name!r}",
            validate_identifier=validate_identifier,
            labels=labels,
            label_counts=label_counts,
            module_labels=module_labels,
            module_label_counts=module_label_counts,
            env=env,
            type_graph=type_graph,
            require_init_step=True,
            module_code_policy=active_module_code_policy,
        )
