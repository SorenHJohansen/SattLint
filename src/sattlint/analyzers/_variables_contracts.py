"""Contract, mapping, and index helpers for variable analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SingleModule,
    Variable,
)

from ..casefolding import casefold_key, is_anytype_name
from ..reporting.variables_report import IssueKind, VariableIssue
from ..resolution.common import resolve_moduletype_def_strict, varname_base
from .validators import AnyTypeFieldContract

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


def _collect_module_vars(
    mods: list[SingleModule | FrameModule | ModuleTypeInstance],
    index: dict[str, list[Variable]],
) -> None:
    for module in mods or []:
        if isinstance(module, SingleModule):
            for variable in module.moduleparameters or []:
                index.setdefault(variable.name.lower(), []).append(variable)
            for variable in module.localvariables or []:
                index.setdefault(variable.name.lower(), []).append(variable)
            _collect_module_vars(module.submodules or [], index)
        elif isinstance(module, FrameModule):
            _collect_module_vars(module.submodules or [], index)


def _iter_anytype_typedefs(self: VariablesAnalyzer) -> list[ModuleTypeDef]:
    return [
        typedef
        for typedef in (self.bp.moduletype_defs or [])
        if any(is_anytype_name(variable.datatype) for variable in (typedef.moduleparameters or []))
    ]


def _build_anytype_parameter_contract(
    self: VariablesAnalyzer,
    extractor: VariablesAnalyzer,
    variable: Variable,
) -> AnyTypeFieldContract | None:
    if not is_anytype_name(variable.datatype):
        return None

    usage = extractor.get_usage(variable)
    field_paths = sorted(set((usage.field_reads or {}).keys()) | set((usage.field_writes or {}).keys()))
    if not field_paths:
        return None

    return AnyTypeFieldContract(field_paths=tuple(field_paths))


def _build_anytype_field_contracts(self: VariablesAnalyzer) -> dict[int, dict[str, AnyTypeFieldContract]]:
    typedefs_with_anytype = self.iter_anytype_typedefs()
    if not typedefs_with_anytype:
        return {}

    extractor = _make_nested_contract_extractor(self)
    contracts: dict[int, dict[str, AnyTypeFieldContract]] = {}

    for typedef in typedefs_with_anytype:
        extractor.analyze_typedef(
            typedef,
            path=[self.bp.header.name, f"TypeDef:{typedef.name}"],
        )

        parameter_contracts: dict[str, AnyTypeFieldContract] = {}
        for variable in typedef.moduleparameters or []:
            contract = self.build_anytype_parameter_contract(extractor, variable)
            if contract is None:
                continue

            parameter_contracts[casefold_key(variable.name)] = contract

        if parameter_contracts:
            contracts[id(typedef)] = parameter_contracts

    return contracts


def _get_required_parameter_names_for_typedef(
    self: VariablesAnalyzer,
    moduletype: ModuleTypeDef,
) -> dict[str, str]:
    owner_id = id(moduletype)
    cached = self.required_parameter_names_by_owner.get(owner_id)
    if cached is not None:
        return cached

    # Share recursion-sensitive state across nested extractors so typedef cycles
    # short-circuit to an in-progress placeholder instead of expanding forever.
    self.required_parameter_names_by_owner[owner_id] = {}

    extractor = _make_nested_contract_extractor(self)
    extractor.analyze_typedef(
        moduletype,
        path=[self.bp.header.name, f"TypeDef:{moduletype.name}"],
    )

    required_names: dict[str, str] = {}
    for variable in moduletype.moduleparameters or []:
        usage = extractor.get_usage(variable)
        if not (usage.read or usage.written):
            continue
        if usage.is_display_only:
            continue
        required_names[variable.name.casefold()] = variable.name

    self.required_parameter_names_by_owner[owner_id] = required_names
    return required_names


def _make_nested_contract_extractor(self: VariablesAnalyzer) -> VariablesAnalyzer:
    extractor = type(self)(
        self.bp,
        debug=False,
        fail_loudly=False,
        unavailable_libraries=self.unavailable_libraries,
        analyzed_target_is_library=self.analyzed_target_is_library,
        include_dependency_moduletype_usage=self.include_dependency_moduletype_usage,
        trace_recorder=None,
        build_anytype_contracts=False,
    )
    cast(Any, extractor)._required_parameter_names_by_owner = self.required_parameter_names_by_owner
    cast(Any, extractor)._analyzing_typedefs = self.analyzing_typedefs
    return extractor


def _check_param_mappings_for_single(
    self: VariablesAnalyzer,
    mod: SingleModule,
    child_env: dict[str, Variable],
    parent_env: dict[str, Variable],
    parent_path: list[str],
) -> None:
    params_by_name = {v.name.casefold(): v for v in (mod.moduleparameters or [])}
    mapped_target_keys = {
        target_name.casefold()
        for pm in mod.parametermappings or []
        for target_name in [varname_base(cast(Any, pm).target)]
        if target_name and target_name.casefold() in params_by_name
    }

    for parameter in mod.moduleparameters or []:
        if parameter.name.casefold() in mapped_target_keys:
            continue
        usage = self.get_usage(parameter)
        if not (usage.read or usage.written):
            continue
        if usage.is_display_only:
            continue
        self.append_issue(
            VariableIssue(
                kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
                module_path=list(parent_path),
                variable=parameter,
                role=(f"required parameter connection missing for {parameter.name!r}"),
            )
        )

    for pm in mod.parametermappings or []:
        tgt_name = varname_base(cast(Any, pm).target)
        tgt_var = params_by_name.get(tgt_name) if tgt_name else None
        self.check_param_mapping(pm, tgt_var, parent_env, parent_path)


def _check_param_mappings_for_type_instance(
    self: VariablesAnalyzer,
    inst: ModuleTypeInstance,
    parent_env: dict[str, Variable],
    parent_path: list[str],
    current_library: str | None = None,
) -> None:
    try:
        mt = resolve_moduletype_def_strict(
            self.bp,
            inst.moduletype_name,
            current_library=current_library,
            unavailable_libraries=self.unavailable_libraries,
        )
    except ValueError:
        return
    params_by_name = {v.name.casefold(): v for v in (mt.moduleparameters or [])}
    mapped_target_keys = {
        target_name.casefold()
        for pm in inst.parametermappings or []
        for target_name in [varname_base(cast(Any, pm).target)]
        if target_name and target_name.casefold() in params_by_name
    }
    required_parameter_names = self.get_required_parameter_names_for_typedef(mt)
    for required_key in sorted(required_parameter_names):
        if required_key in mapped_target_keys:
            continue
        required_variable = params_by_name.get(required_key)
        if required_variable is None:
            continue
        self.append_issue(
            VariableIssue(
                kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
                module_path=list(parent_path),
                variable=required_variable,
                role=(f"required parameter connection missing for {required_variable.name!r}"),
            )
        )
    for pm in inst.parametermappings or []:
        tgt_name = varname_base(cast(Any, pm).target)
        tgt_var = params_by_name.get(tgt_name) if tgt_name else None
        self.check_param_mapping(
            pm,
            tgt_var,
            parent_env,
            parent_path,
            owner_contract_id=id(mt),
        )


def _check_param_mapping(
    self: VariablesAnalyzer,
    pm: ParameterMapping,
    tgt_var: Variable | None,
    parent_env: dict[str, Variable],
    path: list[str],
    *,
    owner_contract_id: int | None = None,
) -> None:
    if tgt_var is None:
        return
    if pm.is_source_global:
        return

    source_ref = cast(Any, pm).source
    src_var = self.lookup_env_var_from_varname_dict(source_ref, parent_env)
    if src_var is None:
        src_var = self.lookup_global_variable(varname_base(source_ref))

    for issue in self.contract_validator.check_contract_mapping(
        pm,
        tgt_var,
        src_var,
        path,
        owner_contract_id=owner_contract_id,
    ):
        self.append_param_mapping_issue(pm, issue)

    if src_var is None:
        return

    for issue in self.string_validator.check_string_mapping(tgt_var, src_var, path):
        self.append_param_mapping_issue(pm, issue)
    for issue in self.min_max_validator.check_min_max_mapping(pm, tgt_var, src_var, path):
        self.append_param_mapping_issue(pm, issue)


def _index_all_variables(self: VariablesAnalyzer) -> None:
    index = self.any_var_index

    for variable in self.bp.localvariables or []:
        index.setdefault(variable.name.lower(), []).append(variable)

    _collect_module_vars(self.bp.submodules or [], index)

    for moduletype in self.bp.moduletype_defs or []:
        for variable in moduletype.moduleparameters or []:
            index.setdefault(variable.name.lower(), []).append(variable)
        for variable in moduletype.localvariables or []:
            index.setdefault(variable.name.lower(), []).append(variable)


build_anytype_field_contracts = _build_anytype_field_contracts
build_anytype_parameter_contract = _build_anytype_parameter_contract
check_param_mapping = _check_param_mapping
check_param_mappings_for_single = _check_param_mappings_for_single
check_param_mappings_for_type_instance = _check_param_mappings_for_type_instance
get_required_parameter_names_for_typedef = _get_required_parameter_names_for_typedef
index_all_variables = _index_all_variables
iter_anytype_typedefs = _iter_anytype_typedefs
make_nested_contract_extractor = _make_nested_contract_extractor

__all__ = [
    "build_anytype_field_contracts",
    "build_anytype_parameter_contract",
    "check_param_mapping",
    "check_param_mappings_for_single",
    "check_param_mappings_for_type_instance",
    "get_required_parameter_names_for_typedef",
    "index_all_variables",
    "iter_anytype_typedefs",
    "make_nested_contract_extractor",
]
