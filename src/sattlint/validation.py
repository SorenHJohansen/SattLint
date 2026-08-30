# pyright: reportPrivateUsage=false
"""Post-transform structural validation for SattLine ASTs."""

from __future__ import annotations

from collections.abc import Sequence as AbcSequence
from typing import cast

from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    ModuleTypeDef,
)

from ._validation_sequences import (
    collect_sequence_labels as _collect_sequence_labels,
)
from ._validation_sequences import (
    iter_sequence_node_refs as _iter_sequence_node_refs,
)
from ._validation_sequences import (
    parallel_branch_trailer as _parallel_branch_trailer,
)
from ._validation_sequences import (
    validate_step_auto_variable_refs as _validate_step_auto_variable_refs,
)
from ._validation_sequences import (
    validate_variable_refs as _validate_variable_refs,
)
from ._validation_shared import (
    RawSourceValidationError,
    StructuralValidationError,
    ValidationWarningSink,
)
from ._validation_structure_core import (
    _build_reserved_identifier_keywords,
    _discard_validation_warning,
    _ensure_unique_names,
    _merge_env,
    _module_code_policy,
    _ModuleValidationPolicy,
    _validate_datatypes,
    _validate_declared_variable,
    _validate_identifier,
    _validate_module_code,
    _validate_parameter_mappings,
    _validate_sequence_nodes,
    _validate_unique_submodule_names,
    _validate_variable_list,
)
from ._validation_structure_modules import _validate_module, _validate_module_dependency_context
from ._validation_type_helpers import _BUILTIN_DATATYPE_NAMES
from ._validation_type_helpers import (
    assignment_type_matches as _assignment_type_matches,
)
from ._validation_type_helpers import (
    extract_time_literal as _extract_time_literal,
)
from ._validation_type_helpers import (
    has_time_literal_marker as _has_time_literal_marker,
)
from ._validation_type_helpers import (
    infer_literal_datatype as _infer_literal_datatype,
)
from ._validation_type_helpers import (
    is_valid_time_literal as _is_valid_time_literal,
)
from ._validation_type_helpers import (
    literal_matches_expected_datatype as _literal_matches_expected_datatype,
)
from ._validation_type_helpers import (
    resolve_variable_field_datatype as _resolve_variable_field_datatype,
)
from ._validation_type_helpers import (
    split_dotted_name as _split_dotted_name,
)
from .grammar import constants as const
from .resolution.type_graph import TypeGraph

LOCAL_STRUCTURE_VALIDATION_SCHEMA_VERSION = "2026-06-01-local-structure-v1"


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
    "_build_reserved_identifier_keywords",
    "_collect_sequence_labels",
    "_iter_sequence_node_refs",
    "_parallel_branch_trailer",
    "_validate_declared_variable",
    "_validate_parameter_mappings",
    "_validate_sequence_nodes",
    "_validate_step_auto_variable_refs",
    "_validate_variable_refs",
    # Type helpers exported to analyzers.validators
    "assignment_type_matches",
    "const",
    "extract_time_literal",
    "has_time_literal_marker",
    "infer_literal_datatype",
    "is_valid_time_literal",
    "literal_matches_expected_datatype",
    "resolve_variable_field_datatype",
    "split_dotted_name",
    "validate_transformed_basepicture",
]
