"""Contract, mapping, and index helpers for variable analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
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

    usage = extractor._get_usage(variable)
    field_paths = sorted(set((usage.field_reads or {}).keys()) | set((usage.field_writes or {}).keys()))
    if not field_paths:
        return None

    return AnyTypeFieldContract(field_paths=tuple(field_paths))


def _build_anytype_field_contracts(self: VariablesAnalyzer) -> dict[int, dict[str, AnyTypeFieldContract]]:
    typedefs_with_anytype = self._iter_anytype_typedefs()
    if not typedefs_with_anytype:
        return {}

    extractor = type(self)(
        self.bp,
        debug=False,
        fail_loudly=False,
        unavailable_libraries=self._unavailable_libraries,
        analyzed_target_is_library=self._analyzed_target_is_library,
        include_dependency_moduletype_usage=self._include_dependency_moduletype_usage,
        trace_recorder=None,
        build_anytype_contracts=False,
    )
    contracts: dict[int, dict[str, AnyTypeFieldContract]] = {}

    for typedef in typedefs_with_anytype:
        extractor._analyze_typedef(
            typedef,
            path=[self.bp.header.name, f"TypeDef:{typedef.name}"],
        )

        parameter_contracts: dict[str, AnyTypeFieldContract] = {}
        for variable in typedef.moduleparameters or []:
            contract = self._build_anytype_parameter_contract(extractor, variable)
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
    cached = self._required_parameter_names_by_owner.get(owner_id)
    if cached is not None:
        return cached

    extractor = type(self)(
        self.bp,
        debug=False,
        fail_loudly=False,
        unavailable_libraries=self._unavailable_libraries,
        analyzed_target_is_library=self._analyzed_target_is_library,
        include_dependency_moduletype_usage=self._include_dependency_moduletype_usage,
        trace_recorder=None,
        build_anytype_contracts=False,
    )
    extractor._analyze_typedef(
        moduletype,
        path=[self.bp.header.name, f"TypeDef:{moduletype.name}"],
    )

    required_names: dict[str, str] = {}
    for variable in moduletype.moduleparameters or []:
        usage = extractor._get_usage(variable)
        if not (usage.read or usage.written):
            continue
        if usage.is_display_only:
            continue
        required_names[variable.name.casefold()] = variable.name

    self._required_parameter_names_by_owner[owner_id] = required_names
    return required_names


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
        for target_name in [varname_base(pm.target)]
        if target_name and target_name.casefold() in params_by_name
    }

    for parameter in mod.moduleparameters or []:
        if parameter.name.casefold() in mapped_target_keys:
            continue
        usage = self._get_usage(parameter)
        if not (usage.read or usage.written):
            continue
        if usage.is_display_only:
            continue
        self._append_issue(
            VariableIssue(
                kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
                module_path=list(parent_path),
                variable=parameter,
                role=(f"required parameter connection missing for {parameter.name!r}"),
            )
        )

    for pm in mod.parametermappings or []:
        tgt_name = varname_base(pm.target)
        tgt_var = params_by_name.get(tgt_name) if tgt_name else None
        self._check_param_mapping(pm, tgt_var, parent_env, parent_path)


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
            unavailable_libraries=self._unavailable_libraries,
        )
    except ValueError:
        return
    params_by_name = {v.name.casefold(): v for v in (mt.moduleparameters or [])}
    mapped_target_keys = {
        target_name.casefold()
        for pm in inst.parametermappings or []
        for target_name in [varname_base(pm.target)]
        if target_name and target_name.casefold() in params_by_name
    }
    required_parameter_names = self._get_required_parameter_names_for_typedef(mt)
    for required_key in sorted(required_parameter_names):
        if required_key in mapped_target_keys:
            continue
        required_variable = params_by_name.get(required_key)
        if required_variable is None:
            continue
        self._append_issue(
            VariableIssue(
                kind=IssueKind.REQUIRED_PARAMETER_CONNECTION,
                module_path=list(parent_path),
                variable=required_variable,
                role=(f"required parameter connection missing for {required_variable.name!r}"),
            )
        )
    for pm in inst.parametermappings or []:
        tgt_name = varname_base(pm.target)
        tgt_var = params_by_name.get(tgt_name) if tgt_name else None
        self._check_param_mapping(
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

    src_var = self._lookup_env_var_from_varname_dict(pm.source, parent_env)
    if src_var is None:
        src_var = self._lookup_global_variable(varname_base(pm.source))

    self._issues.extend(
        self._contract_validator.check_contract_mapping(
            pm,
            tgt_var,
            src_var,
            path,
            owner_contract_id=owner_contract_id,
        )
    )

    if src_var is None:
        return

    self._issues.extend(self._string_validator.check_string_mapping(tgt_var, src_var, path))
    self._issues.extend(self._min_max_validator.check_min_max_mapping(pm, tgt_var, src_var, path))


def _index_all_variables(self: VariablesAnalyzer) -> None:
    index = self._any_var_index

    for variable in self.bp.localvariables or []:
        index.setdefault(variable.name.lower(), []).append(variable)

    _collect_module_vars(self.bp.submodules or [], index)

    for moduletype in self.bp.moduletype_defs or []:
        for variable in moduletype.moduleparameters or []:
            index.setdefault(variable.name.lower(), []).append(variable)
        for variable in moduletype.localvariables or []:
            index.setdefault(variable.name.lower(), []).append(variable)


def _is_const_candidate(self: VariablesAnalyzer, variable: Variable) -> bool:
    return isinstance(variable.datatype, Simple_DataType)
