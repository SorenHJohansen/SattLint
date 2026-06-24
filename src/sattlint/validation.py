"""Post-transform structural validation for SattLine ASTs."""

from __future__ import annotations

import re
from collections.abc import Sequence as AbcSequence
from dataclasses import dataclass
from typing import cast

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)

from . import _validation_sequences as validation_sequences_module
from ._validation_expression import (
    is_variable_ref_node as _is_variable_ref_node,
)
from ._validation_shared import (
    RawSourceValidationError,
    StructuralValidationError,
    ValidationWarning,
    ValidationWarningSink,
    ref_span,
    span_kwargs,
    warn_or_raise,
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
from .types import VariableRef

LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION = "2026-06-01-local-structure-v1"

_MAX_IDENTIFIER_LENGTH = 20
_TYPO_SUGGESTION_MAX_DISTANCE = 2
_RESERVED_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_SIMPLE_BUILTIN_DATATYPE_NAMES = tuple(datatype.value for datatype in Simple_DataType)
_ALLOWED_IDENTIFIER_KEYWORDS = frozenset(
    {
        const.GRAMMAR_VALUE_COLOUR.casefold(),
        const.GRAMMAR_VALUE_NEWWINDOW.casefold(),
    }
)


def _discard_validation_warning(_warning: ValidationWarning) -> None:
    return None


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
            suggestion_candidates = (
                _SIMPLE_BUILTIN_DATATYPE_NAMES if allow_unresolved_external_datatypes else known_datatypes
            )
            suggestion = _suggest_datatype_name(variable.datatype, suggestion_candidates)
            if suggestion is not None:
                raise StructuralValidationError(
                    f"{context} variable {variable.name!r} uses unknown datatype {variable.datatype_text!r}; did you mean {suggestion!r}?",
                    **span_kwargs(variable.declaration_span),
                )
            if not allow_unresolved_external_datatypes:
                raise StructuralValidationError(
                    f"{context} variable {variable.name!r} uses unknown datatype {variable.datatype_text!r}",
                    **span_kwargs(variable.declaration_span),
                )

    if variable.init_value is None:
        return

    if getattr(variable, "init_is_duration", False) and not _is_valid_duration_literal(variable.init_value):
        raise StructuralValidationError(
            f"{context} variable {variable.name!r} has invalid duration literal {variable.init_value!r}",
            **span_kwargs(variable.declaration_span),
        )

    if _has_time_literal_marker(variable.init_value) and not _is_valid_time_literal(
        _extract_time_literal(variable.init_value)
    ):
        raise StructuralValidationError(
            f"{context} variable {variable.name!r} has invalid time literal {_extract_time_literal(variable.init_value)!r}",
            **span_kwargs(variable.declaration_span),
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
        **span_kwargs(variable.declaration_span),
    )


def _ensure_unique_names(names: list[str], context: str, kind: str) -> None:
    seen: dict[str, str] = {}
    for name in names:
        folded = name.casefold()
        if folded in seen:
            raise StructuralValidationError(f"{context} has duplicate {kind} names {seen[folded]!r} and {name!r}")
        seen[folded] = name


_iter_nested_sequence_nodes = validation_sequences_module.iter_nested_sequence_nodes
_collect_sequence_labels = validation_sequences_module.collect_sequence_labels
_collect_sequence_label_counts = validation_sequences_module.collect_sequence_label_counts
_collect_label_names = validation_sequences_module.collect_label_names
_collect_sequence_step_features = validation_sequences_module.collect_sequence_step_features
_collect_sequence_scope_features = validation_sequences_module.collect_sequence_scope_features
_iter_sequence_node_refs = validation_sequences_module.iter_sequence_node_refs
_validate_step_auto_variable_refs = validation_sequences_module.validate_step_auto_variable_refs
_parallel_branch_trailer = validation_sequences_module.parallel_branch_trailer
_iter_variable_refs = validation_sequences_module.iter_variable_refs
_validate_variable_refs = validation_sequences_module.validate_variable_refs
_validate_statement_list = validation_sequences_module.validate_statement_list
_validate_code_blocks = validation_sequences_module.validate_code_blocks


def _validate_sequence_nodes(
    nodes: list[object],
    context: str,
    *,
    labels: dict[str, str],
    label_counts: dict[str, int],
    env: dict[str, Variable],
    type_graph: TypeGraph,
    require_init_step: bool,
    module_labels: frozenset[str] = frozenset(),
    module_label_counts: dict[str, int] | None = None,
    warning_sink: ValidationWarningSink | None = None,
    allow_old_state_assignment: bool = True,
    suppress_semantic_errors: bool = False,
    module_code_policy: validation_sequences_module.ModuleCodeValidationPolicy | None = None,
) -> None:
    validation_sequences_module.validate_sequence_nodes(
        nodes,
        context,
        validate_identifier=_validate_identifier,
        labels=labels,
        label_counts=label_counts,
        module_labels=module_labels,
        module_label_counts=module_label_counts,
        env=env,
        type_graph=type_graph,
        require_init_step=require_init_step,
        warning_sink=warning_sink,
        allow_old_state_assignment=allow_old_state_assignment,
        suppress_semantic_errors=suppress_semantic_errors,
        module_code_policy=module_code_policy,
    )


def _validate_module_code(
    modulecode: ModuleCode | None,
    context: str,
    env: dict[str, Variable],
    type_graph: TypeGraph,
    *,
    warning_sink: ValidationWarningSink | None = None,
    allow_old_state_assignment: bool = True,
    suppress_semantic_errors: bool = False,
    module_code_policy: validation_sequences_module.ModuleCodeValidationPolicy | None = None,
) -> None:
    validation_sequences_module.validate_module_code(
        modulecode,
        context,
        env,
        type_graph,
        validate_identifier=_validate_identifier,
        warning_sink=warning_sink,
        allow_old_state_assignment=allow_old_state_assignment,
        suppress_semantic_errors=suppress_semantic_errors,
        module_code_policy=module_code_policy,
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
                **span_kwargs(datatype.declaration_span),
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
                **span_kwargs(module.header.declaration_span),
            )
        seen[key] = name


@dataclass(frozen=True)
class _ModuleValidationPolicy:
    allow_parameterless_module_mappings: bool = False
    warn_unknown_parameter_targets: bool = False
    warn_incompatible_parameter_mappings: bool = False
    warning_sink: ValidationWarningSink | None = None
    allow_old_state_assignment: bool = True
    suppress_module_code_semantic_errors: bool = False


def _module_code_policy(
    policy: _ModuleValidationPolicy,
) -> validation_sequences_module.ModuleCodeValidationPolicy:
    return validation_sequences_module.ModuleCodeValidationPolicy(
        warning_sink=policy.warning_sink,
        allow_old_state_assignment=policy.allow_old_state_assignment,
        suppress_semantic_errors=policy.suppress_module_code_semantic_errors,
    )


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
        target_name, target_span = str(target_ref.get(const.KEY_VAR_NAME)), ref_span(target_ref)
        target_key = target_name.casefold()
        if target_key in seen:
            raise StructuralValidationError(
                f"{context} has duplicate parameter mapping targets {seen[target_key]!r} and {target_name!r}",
                **span_kwargs(target_span),
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
                    **span_kwargs(target_span),
                    length=max(len(target_name), 1),
                )
            if type_graph.has_record(str(target_variable.datatype)):
                raise StructuralValidationError(
                    f"{context} parameter mapping target {target_name!r} does not exist",
                    **span_kwargs(target_span),
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
                    **span_kwargs(target_span),
                )
            if _has_time_literal_marker(source_literal) and not _is_valid_time_literal(
                _extract_time_literal(source_literal)
            ):
                raise StructuralValidationError(
                    f"{context} maps invalid time literal {_extract_time_literal(source_literal)!r} to parameter target {target_name!r}",
                    **span_kwargs(target_span),
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

        warn_or_raise(
            f"{context} maps {source_description or 'value'!r} with datatype {_format_datatype(actual_datatype)!r} "
            f"to parameter target {target_name!r} with datatype {_format_datatype(target_datatype)!r}",
            warning_sink=policy.warning_sink if policy.warn_incompatible_parameter_mappings else None,
            **span_kwargs(target_span),
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
            module_code_policy=_module_code_policy(active_policy),
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
            module_code_policy=_module_code_policy(active_policy),
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


def _validate_module_dependency_context(
    module: object,
    context: str,
    parent_env: dict[str, Variable],
    type_graph: TypeGraph,
    moduletype_index: dict[str, list[ModuleTypeDef]],
    *,
    policy: _ModuleValidationPolicy | None = None,
) -> None:
    active_policy = policy or _ModuleValidationPolicy()

    if isinstance(module, SingleModule):
        module_context = f"{context} module {module.header.name!r}"
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
        for submodule in module.submodules or []:
            _validate_module_dependency_context(
                submodule,
                module_context,
                env,
                type_graph,
                moduletype_index,
                policy=active_policy,
            )
        return

    if isinstance(module, FrameModule):
        module_context = f"{context} frame {module.header.name!r}"
        for submodule in module.submodules or []:
            _validate_module_dependency_context(
                submodule,
                module_context,
                parent_env,
                type_graph,
                moduletype_index,
                policy=active_policy,
            )
        return

    if isinstance(module, ModuleTypeInstance):
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


def validate_transformed_basepicture_locally(
    basepic: BasePicture,
    *,
    allow_unresolved_external_datatypes: bool = True,
    enforce_unique_submodule_names: bool = True,
    allow_parameterless_module_mappings: bool = False,
    allow_old_state_assignment: bool = True,
    warning_sink: ValidationWarningSink | None = None,
) -> None:
    """Validate a transformed BasePicture for local/editor flows.

    Local validation intentionally downgrades module-code semantic
    StructuralValidationError failures into ValidationNotice warnings routed to
    warning_sink. If no warning sink is provided, those downgraded notices are
    discarded. Other structural validation failures still raise.
    """
    effective_warning_sink: ValidationWarningSink = warning_sink or _discard_validation_warning

    validate_transformed_basepicture(
        basepic,
        allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
        enforce_unique_submodule_names=enforce_unique_submodule_names,
        allow_parameterless_module_mappings=allow_parameterless_module_mappings,
        allow_old_state_assignment=allow_old_state_assignment,
        warn_incompatible_parameter_mappings=True,
        suppress_module_code_semantic_errors=True,
        warning_sink=effective_warning_sink,
    )


def validate_transformed_basepicture_dependency_context(
    basepic: BasePicture,
    *,
    external_datatypes: AbcSequence[DataType] | None = None,
    external_moduletype_defs: AbcSequence[ModuleTypeDef] | None = None,
    allow_parameterless_module_mappings: bool = False,
    warn_unknown_parameter_targets: bool = False,
    warn_incompatible_parameter_mappings: bool = False,
    warning_sink: ValidationWarningSink | None = None,
) -> None:
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
    available_datatypes = [*(basepic.datatype_defs or []), *(external_datatypes or [])]
    available_moduletype_defs = [*base_moduletype_defs, *available_external_moduletype_defs]
    type_graph = TypeGraph.from_datatypes(available_datatypes)
    moduletype_index: dict[str, list[ModuleTypeDef]] = {}
    for moduletype in available_moduletype_defs:
        moduletype_index.setdefault(moduletype.name.casefold(), []).append(moduletype)

    policy = _ModuleValidationPolicy(
        allow_parameterless_module_mappings=allow_parameterless_module_mappings,
        warn_unknown_parameter_targets=warn_unknown_parameter_targets,
        warn_incompatible_parameter_mappings=warn_incompatible_parameter_mappings,
        warning_sink=warning_sink,
    )

    base_env = _merge_env({}, basepic.localvariables)

    for moduletype in base_moduletype_defs:
        moduletype_context = f"BasePicture moduletype {moduletype.name!r}"
        env = _merge_env(base_env, moduletype.moduleparameters)
        env = _merge_env(env, moduletype.localvariables)
        for submodule in moduletype.submodules or []:
            _validate_module_dependency_context(
                submodule,
                moduletype_context,
                env,
                type_graph,
                moduletype_index,
                policy=policy,
            )

    for submodule in basepic.submodules or []:
        _validate_module_dependency_context(
            submodule,
            "BasePicture",
            base_env,
            type_graph,
            moduletype_index,
            policy=policy,
        )


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
    suppress_module_code_semantic_errors: bool = False,
    warning_sink: ValidationWarningSink | None = None,
) -> None:
    """Validate a transformed BasePicture.

    Module-code semantic StructuralValidationError failures are fatal by
    default. Set suppress_module_code_semantic_errors=True to downgrade only
    those failures into ValidationNotice warnings routed to warning_sink
    instead of raising them.
    """
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
        dict.fromkeys([*_BUILTIN_DATATYPE_NAMES, *[datatype.name for datatype in available_datatypes]])
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
        suppress_module_code_semantic_errors=suppress_module_code_semantic_errors,
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
            module_code_policy=_module_code_policy(policy),
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
        module_code_policy=_module_code_policy(policy),
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
assignment_type_matches = _assignment_type_matches
extract_time_literal = _extract_time_literal
has_time_literal_marker = _has_time_literal_marker
infer_literal_datatype = _infer_literal_datatype
is_valid_time_literal = _is_valid_time_literal
literal_matches_expected_datatype = _literal_matches_expected_datatype
resolve_variable_field_datatype = _resolve_variable_field_datatype
split_dotted_name = _split_dotted_name

__all__ = [
    "RawSourceValidationError",
    "StructuralValidationError",
    "_validate_sequence_nodes",
    # Type helpers exported to analyzers.validators
    "assignment_type_matches",
    "extract_time_literal",
    "has_time_literal_marker",
    "infer_literal_datatype",
    "is_valid_time_literal",
    "literal_matches_expected_datatype",
    "resolve_variable_field_datatype",
    "split_dotted_name",
    "validate_transformed_basepicture",
]
