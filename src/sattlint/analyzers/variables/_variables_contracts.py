"""Contract, mapping, and index helpers for variable analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from sattline_parser.models.ast_model import (
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    SingleModule,
    Variable,
)

from ..._validation_type_helpers import assignment_type_matches as _assignment_type_matches
from ..._validation_type_helpers import is_string_simple_type as _is_string_simple_type
from ..._validation_type_helpers import resolve_variable_field_datatype as _resolve_variable_field_datatype
from ...casefolding import casefold_key, is_anytype_name
from ...reporting.variables_report import IssueKind, VariableIssue
from ...resolution.common import resolve_moduletype_def_strict, varname_base, varname_full
from ...resolution.scope import ScopeContext
from ..shared._validators import AnyTypeFieldContract
from ..shared._walk_utils import iter_nested_modules
from ..shared.variable_utils import mapping_target_name

if TYPE_CHECKING:
    from . import VariablesAnalyzer


_PARAM_MAPPING_VALIDATION_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.REQUIRED_PARAMETER_CONNECTION,
        IssueKind.CONTRACT_MISMATCH,
        IssueKind.STRING_MAPPING_MISMATCH,
        IssueKind.MIN_MAX_MAPPING_MISMATCH,
    }
)
_PARAM_MAPPING_CHECK_ISSUE_KINDS: frozenset[IssueKind] = frozenset(
    {
        IssueKind.CONTRACT_MISMATCH,
        IssueKind.STRING_MAPPING_MISMATCH,
        IssueKind.MIN_MAX_MAPPING_MISMATCH,
    }
)


def _selected_issue_kinds(self: object) -> frozenset[IssueKind] | set[IssueKind] | None:
    return getattr(self, "_selected_issue_kinds", None)


def _should_collect_issue_kind(self: object, kind: IssueKind) -> bool:
    selected_kinds = _selected_issue_kinds(self)
    return selected_kinds is None or kind in selected_kinds


def _should_collect_any_issue_kinds(self: object, kinds: frozenset[IssueKind]) -> bool:
    selected_kinds = _selected_issue_kinds(self)
    return selected_kinds is None or bool(selected_kinds & kinds)


def _collect_module_vars(
    mods: list[SingleModule | FrameModule | ModuleTypeInstance],
    index: dict[str, list[Variable]],
) -> None:
    for module, _module_path in iter_nested_modules(mods, parent_path=[]):
        if not isinstance(module, SingleModule):
            continue
        for variable in module.moduleparameters or []:
            index.setdefault(casefold_key(variable.name), []).append(variable)
        for variable in module.localvariables or []:
            index.setdefault(casefold_key(variable.name), []).append(variable)


def _iter_anytype_typedefs(self: VariablesAnalyzer) -> list[ModuleTypeDef]:
    return [
        typedef
        for typedef in (self.bp.moduletype_defs or [])
        if any(is_anytype_name(variable.datatype) for variable in (typedef.moduleparameters or []))
    ]


def _mapping_source_ref(mapping: ParameterMapping) -> object:
    return getattr(mapping, "source", None)


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
        required_names[casefold_key(variable.name)] = variable.name

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
        selected_issue_kinds=None,
        trace_recorder=None,
        build_anytype_contracts=False,
    )
    extractor_any: Any = extractor
    extractor_any._required_parameter_names_by_owner = self.required_parameter_names_by_owner
    extractor_any._analyzing_typedefs = self.analyzing_typedefs
    return extractor


def _check_param_mappings_for_single(
    self: VariablesAnalyzer,
    mod: SingleModule,
    child_env: dict[str, Variable],
    parent_env: dict[str, Variable],
    parent_context: ScopeContext,
    parent_path: list[str],
) -> None:
    if getattr(self, "_suppress_param_mapping_validation_depth", 0) > 0:
        return

    if not _should_collect_any_issue_kinds(self, _PARAM_MAPPING_VALIDATION_ISSUE_KINDS):
        return

    params_by_name = {casefold_key(v.name): v for v in (mod.moduleparameters or [])}
    if _should_collect_issue_kind(self, IssueKind.REQUIRED_PARAMETER_CONNECTION):
        mapped_target_keys = {
            casefold_key(target_name)
            for pm in mod.parametermappings or []
            for target_name in [mapping_target_name(pm)]
            if target_name and casefold_key(target_name) in params_by_name
        }

        for parameter in mod.moduleparameters or []:
            if casefold_key(parameter.name) in mapped_target_keys:
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

    if not _should_collect_any_issue_kinds(self, _PARAM_MAPPING_CHECK_ISSUE_KINDS):
        return

    for pm in mod.parametermappings or []:
        tgt_name = mapping_target_name(pm)
        tgt_var = params_by_name.get(tgt_name) if tgt_name else None
        self.check_param_mapping(pm, tgt_var, parent_env, parent_context, parent_path)


def _check_param_mappings_for_type_instance(
    self: VariablesAnalyzer,
    inst: ModuleTypeInstance,
    parent_env: dict[str, Variable],
    parent_context: ScopeContext,
    parent_path: list[str],
    current_library: str | None = None,
) -> None:
    if getattr(self, "_suppress_param_mapping_validation_depth", 0) > 0:
        return

    if not _should_collect_any_issue_kinds(self, _PARAM_MAPPING_VALIDATION_ISSUE_KINDS):
        return

    try:
        mt = resolve_moduletype_def_strict(
            self.bp,
            inst.moduletype_name,
            current_library=current_library,
            unavailable_libraries=self.unavailable_libraries,
        )
    except ValueError:
        return
    params_by_name = {casefold_key(v.name): v for v in (mt.moduleparameters or [])}
    if _should_collect_issue_kind(self, IssueKind.REQUIRED_PARAMETER_CONNECTION):
        mapped_target_keys = {
            casefold_key(target_name)
            for pm in inst.parametermappings or []
            for target_name in [mapping_target_name(pm)]
            if target_name and casefold_key(target_name) in params_by_name
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

    if not _should_collect_any_issue_kinds(self, _PARAM_MAPPING_CHECK_ISSUE_KINDS):
        return

    for pm in inst.parametermappings or []:
        tgt_name = mapping_target_name(pm)
        tgt_var = params_by_name.get(tgt_name) if tgt_name else None
        self.check_param_mapping(
            pm,
            tgt_var,
            parent_env,
            parent_context,
            parent_path,
            owner_contract_id=id(mt),
        )


def _source_issue_metadata(
    self: VariablesAnalyzer,
    source_context: ScopeContext | None,
    source_ref: object,
    source_var: Variable | None,
) -> tuple[Variable | None, list[str] | None, str | None, str | None]:
    def _issue_variable(variable: Variable, field_path: str) -> Variable:
        if not field_path:
            return variable

        field_segments = tuple(segment for segment in field_path.split(".") if segment)
        datatype = _resolve_variable_field_datatype(variable, field_segments, self.type_graph)
        return Variable(
            name=f"{variable.name}.{field_path}",
            datatype=datatype or variable.datatype,
        )

    if source_context is None:
        if source_var is not None:
            full_source_name = varname_full(source_ref)
            if isinstance(full_source_name, str) and "." in full_source_name:
                issue_var = _issue_variable(source_var, full_source_name.split(".", 1)[1])
                return issue_var, None, None, issue_var.name
        return source_var, None, None, source_var.name if source_var is not None else None

    full_source_name = varname_full(source_ref)
    if not full_source_name:
        return source_var, None, None, source_var.name if source_var is not None else None

    resolved_var, field_prefix, decl_path, _decl_display_path = source_context.resolve_variable(full_source_name)
    effective_var = resolved_var or source_var
    if effective_var is None:
        return None, None, None, None

    declaring_context = self.contexts_by_module_path.get(tuple(decl_path))
    if declaring_context is None and decl_path == source_context.module_path:
        declaring_context = source_context

    source_role: str | None = None
    if declaring_context is not None:
        source_key = casefold_key(effective_var.name)
        source_role = "moduleparameter" if source_key in declaring_context.moduleparameter_keys else "localvariable"

    issue_var = _issue_variable(effective_var, field_prefix)
    return issue_var, list(decl_path), source_role, issue_var.name


def _validation_source_metadata(
    self: VariablesAnalyzer,
    source_context: ScopeContext | None,
    source_ref: object,
    source_var: Variable | None,
) -> tuple[Variable | None, list[str] | None]:
    root_name = getattr(getattr(getattr(self, "bp", None), "header", None), "name", None)
    root_module_path = [root_name] if isinstance(root_name, str) else None

    if source_var is None:
        return None, None

    full_source_name = varname_full(source_ref)
    if not full_source_name:
        return source_var, list(source_context.module_path) if source_context is not None else root_module_path

    if source_context is None:
        return source_var, root_module_path

    base_name = varname_base(full_source_name)
    if base_name and base_name.casefold() in source_context.env:
        return source_var, list(source_context.module_path)

    root_var = self.root_env.get(base_name) if base_name is not None else None
    if root_var is source_var:
        return source_var, [self.bp.header.name]

    return source_var, list(source_context.module_path)


def _check_param_mapping(
    self: VariablesAnalyzer,
    pm: ParameterMapping,
    tgt_var: Variable | None,
    parent_env: dict[str, Variable],
    source_context: ScopeContext | None,
    path: list[str],
    *,
    owner_contract_id: int | None = None,
) -> None:
    if not _should_collect_any_issue_kinds(self, _PARAM_MAPPING_CHECK_ISSUE_KINDS):
        return

    if tgt_var is None:
        return
    if pm.is_source_global:
        return

    source_ref = _mapping_source_ref(pm)
    src_var = self.lookup_env_var_from_varname_dict(source_ref, parent_env)
    if src_var is None:
        source_base = varname_base(source_ref)
        src_var = self.root_env.get(source_base) if source_base is not None else None

    for issue in self.contract_validator.check_contract_mapping(
        pm,
        tgt_var,
        src_var,
        path,
        owner_contract_id=owner_contract_id,
    ):
        self.append_param_mapping_issue(pm, issue)

    target_name = varname_full(getattr(pm, "target", None)) or tgt_var.name
    target_datatype: Simple_DataType | str | None = None
    target_field_path: str | None = None
    resolve_target_datatype = getattr(self.contract_validator, "resolve_target_datatype", None)
    if callable(resolve_target_datatype):
        resolved_target = cast(
            tuple[Simple_DataType | str | None, str | None],
            resolve_target_datatype(target_name, tgt_var),
        )
        target_datatype, target_field_path = resolved_target
    target_issue_var = (
        Variable(name=target_name, datatype=target_datatype)
        if target_field_path and target_datatype is not None
        else tgt_var
    )

    if src_var is None:
        if pm.source_literal is not None:
            for issue in self.string_validator.check_string_literal_mapping(
                target_issue_var,
                pm.source_literal,
                path,
                is_duration=bool(pm.is_duration),
            ):
                issue.source_decl_module_path = list(path)
                issue.source_role = "literal"
                issue.target_display_name = target_name
                self.append_param_mapping_issue(pm, issue)
        return

    current_source_datatype: Simple_DataType | str | None = None
    current_source_name: str | None = src_var.name
    resolve_source_datatype = getattr(self.contract_validator, "resolve_source_datatype", None)
    if callable(resolve_source_datatype):
        resolved_source = cast(
            tuple[Simple_DataType | str | None, str | None],
            resolve_source_datatype(pm, src_var),
        )
        current_source_datatype, current_source_name = resolved_source
    current_source_var = (
        Variable(
            name=current_source_name,
            datatype=src_var.datatype if current_source_datatype is None else current_source_datatype,
        )
        if current_source_name is not None
        and (current_source_name != src_var.name or current_source_datatype not in {None, src_var.datatype})
        else src_var
    )

    source_issue_var, source_decl_module_path, source_role, source_display_name = _source_issue_metadata(
        self, source_context, source_ref, src_var
    )
    validation_source_var, validation_source_module_path = _validation_source_metadata(
        self,
        source_context,
        source_ref,
        current_source_var,
    )
    preferred_source_issue_var = source_issue_var or current_source_var
    if "." in current_source_var.name and (
        source_issue_var is None
        or "." not in source_issue_var.name
        or source_issue_var.datatype_text == src_var.datatype_text
    ):
        preferred_source_issue_var = current_source_var
        source_display_name = current_source_var.name

    for issue in self.string_validator.check_string_mapping(target_issue_var, current_source_var, path):
        issue.source_variable = preferred_source_issue_var
        issue.source_decl_module_path = source_decl_module_path
        issue.source_role = source_role
        issue.source_display_name = source_display_name
        issue.target_display_name = target_name
        issue.validation_source_variable = validation_source_var
        issue.validation_source_module_path = validation_source_module_path
        self.append_param_mapping_issue(pm, issue)
    for issue in self.min_max_validator.check_min_max_mapping(pm, tgt_var, src_var, path):
        self.append_param_mapping_issue(pm, issue)


def _array_contract_key_for_ref(
    self: VariablesAnalyzer,
    array_ref: str,
    context: ScopeContext,
) -> tuple[tuple[str, ...], Variable, str] | None:
    array_var, _field_path, decl_path, _decl_display = context.resolve_variable(array_ref)
    if array_var is None:
        return None
    display_name = ".".join([*decl_path, array_var.name])
    key = tuple(segment.casefold() for segment in [*decl_path, array_var.name])
    return key, array_var, display_name


def _resolve_reference_datatype(
    self: VariablesAnalyzer,
    full_ref: str,
    context: ScopeContext,
) -> tuple[Variable | None, Simple_DataType | str | None, str]:
    variable, field_path, _decl_path, _decl_display = context.resolve_variable(full_ref)
    if variable is None:
        return None, None, full_ref
    if not field_path:
        return variable, variable.datatype, full_ref
    datatype = _resolve_variable_field_datatype(
        variable,
        tuple(segment for segment in field_path.split(".") if segment),
        self.type_graph,
    )
    return variable, datatype, full_ref


def _format_datatype_text(datatype: Simple_DataType | str | None) -> str:
    if datatype is None:
        return "unknown"
    if isinstance(datatype, Simple_DataType):
        return datatype.value
    return str(datatype)


def _datatype_key(datatype: Simple_DataType | str | None) -> str | None:
    if datatype is None:
        return None
    if isinstance(datatype, Simple_DataType):
        return datatype.value.casefold()
    return str(datatype).casefold()


def _append_array_contract_mismatch(
    self: VariablesAnalyzer,
    *,
    source_name: str,
    source_datatype: Simple_DataType | str | None,
    source_variable: Variable | None,
    target_name: str,
    target_datatype: Simple_DataType | str | None,
    target_variable: Variable | None,
    path: list[str],
) -> None:
    issue = VariableIssue(
        kind=IssueKind.CONTRACT_MISMATCH,
        module_path=list(path),
        variable=(
            target_variable
            if target_variable is not None
            else Variable(name=target_name, datatype=target_datatype or Simple_DataType.STRING)
        ),
        role=(
            "dynamic array element mismatch: "
            f"{source_name} ({_format_datatype_text(source_datatype)}) => "
            f"{target_name} ({_format_datatype_text(target_datatype)})"
        ),
        source_variable=(
            source_variable
            if source_variable is not None
            else Variable(name=source_name, datatype=source_datatype or Simple_DataType.STRING)
        ),
    )
    issue.source_display_name = source_name
    issue.target_display_name = target_name
    self.append_issue(issue)


def _check_array_contract_assignment(
    self: VariablesAnalyzer,
    *,
    source_name: str,
    source_datatype: Simple_DataType | str | None,
    source_variable: Variable | None,
    target_name: str,
    target_datatype: Simple_DataType | str | None,
    target_variable: Variable | None,
    path: list[str],
) -> None:
    source_key = _datatype_key(source_datatype)
    target_key = _datatype_key(target_datatype)
    if source_key is None or target_key is None or source_key == target_key:
        return
    if is_anytype_name(source_key) or is_anytype_name(target_key):
        return
    if _is_string_simple_type(source_datatype) and _is_string_simple_type(target_datatype):
        issues = self.string_validator.check_string_mapping(
            Variable(name=target_name, datatype=target_datatype or Simple_DataType.STRING),
            Variable(name=source_name, datatype=source_datatype or Simple_DataType.STRING),
            path,
        )
        if not issues:
            return
    elif _assignment_type_matches(source_datatype, target_datatype):
        return

    _append_array_contract_mismatch(
        self,
        source_name=source_name,
        source_datatype=source_datatype,
        source_variable=source_variable,
        target_name=target_name,
        target_datatype=target_datatype,
        target_variable=target_variable,
        path=path,
    )


def _bind_dynamic_array_contract(
    self: VariablesAnalyzer,
    array_ref: str,
    element_ref: str,
    context: ScopeContext,
    path: list[str],
) -> Simple_DataType | str | None:
    array_key_data = _array_contract_key_for_ref(self, array_ref, context)
    if array_key_data is None:
        return None
    array_key, array_var, array_display_name = array_key_data
    element_var, element_datatype, element_display_name = _resolve_reference_datatype(self, element_ref, context)
    if element_datatype is None:
        return self.array_element_datatypes_by_key.get(array_key)

    existing_datatype = self.array_element_datatypes_by_key.get(array_key)
    if existing_datatype is None:
        self.array_element_datatypes_by_key[array_key] = element_datatype
        return element_datatype

    _check_array_contract_assignment(
        self,
        source_name=element_display_name,
        source_datatype=element_datatype,
        source_variable=element_var,
        target_name=f"{array_display_name}[element]",
        target_datatype=existing_datatype,
        target_variable=array_var,
        path=path,
    )
    return existing_datatype


def _validate_dynamic_array_get(
    self: VariablesAnalyzer,
    array_ref: str,
    element_ref: str,
    context: ScopeContext,
    path: list[str],
) -> Simple_DataType | str | None:
    array_key_data = _array_contract_key_for_ref(self, array_ref, context)
    if array_key_data is None:
        return None
    array_key, _array_var, array_display_name = array_key_data
    existing_datatype = self.array_element_datatypes_by_key.get(array_key)
    if existing_datatype is None:
        return None

    element_var, element_datatype, element_display_name = _resolve_reference_datatype(self, element_ref, context)
    _check_array_contract_assignment(
        self,
        source_name=f"{array_display_name}[element]",
        source_datatype=existing_datatype,
        source_variable=Variable(name=f"{array_display_name}[element]", datatype=existing_datatype),
        target_name=element_display_name,
        target_datatype=element_datatype,
        target_variable=element_var,
        path=path,
    )
    return existing_datatype


def _index_all_variables(self: VariablesAnalyzer) -> None:
    index = self.any_var_index

    for variable in self.bp.localvariables or []:
        index.setdefault(casefold_key(variable.name), []).append(variable)

    _collect_module_vars(self.bp.submodules or [], index)

    for moduletype in self.bp.moduletype_defs or []:
        for variable in moduletype.moduleparameters or []:
            index.setdefault(casefold_key(variable.name), []).append(variable)
        for variable in moduletype.localvariables or []:
            index.setdefault(casefold_key(variable.name), []).append(variable)


class VariablesContractsMixin:
    def _iter_anytype_typedefs(self: Any) -> list[ModuleTypeDef]:
        return _iter_anytype_typedefs(self)

    def _build_anytype_parameter_contract(
        self: Any,
        extractor: VariablesAnalyzer,
        variable: Variable,
    ) -> AnyTypeFieldContract | None:
        return _build_anytype_parameter_contract(self, extractor, variable)

    def _build_anytype_field_contracts(self: Any) -> dict[int, dict[str, AnyTypeFieldContract]]:
        return _build_anytype_field_contracts(self)

    def _get_required_parameter_names_for_typedef(
        self: Any,
        moduletype: ModuleTypeDef,
    ) -> dict[str, str]:
        return _get_required_parameter_names_for_typedef(self, moduletype)

    def _check_param_mappings_for_single(
        self: Any,
        mod: SingleModule,
        child_env: dict[str, Variable],
        parent_env: dict[str, Variable],
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None:
        _check_param_mappings_for_single(self, mod, child_env, parent_env, parent_context, parent_path)

    def _check_param_mappings_for_type_instance(
        self: Any,
        inst: ModuleTypeInstance,
        parent_env: dict[str, Variable],
        parent_context: ScopeContext,
        parent_path: list[str],
        current_library: str | None = None,
    ) -> None:
        _check_param_mappings_for_type_instance(
            self,
            inst,
            parent_env,
            parent_context,
            parent_path,
            current_library=current_library,
        )

    def _check_param_mapping(
        self: Any,
        pm: ParameterMapping,
        tgt_var: Variable | None,
        parent_env: dict[str, Variable],
        source_context: ScopeContext | None,
        path: list[str],
        *,
        owner_contract_id: int | None = None,
    ) -> None:
        _check_param_mapping(
            self,
            pm,
            tgt_var,
            parent_env,
            source_context,
            path,
            owner_contract_id=owner_contract_id,
        )

    def _bind_dynamic_array_contract(
        self: Any,
        array_ref: str,
        element_ref: str,
        context: ScopeContext,
        path: list[str],
    ) -> Simple_DataType | str | None:
        return _bind_dynamic_array_contract(self, array_ref, element_ref, context, path)

    def _validate_dynamic_array_get(
        self: Any,
        array_ref: str,
        element_ref: str,
        context: ScopeContext,
        path: list[str],
    ) -> Simple_DataType | str | None:
        return _validate_dynamic_array_get(self, array_ref, element_ref, context, path)

    def _index_all_variables(self: Any) -> None:
        _index_all_variables(self)


build_anytype_field_contracts = _build_anytype_field_contracts
build_anytype_parameter_contract = _build_anytype_parameter_contract
bind_dynamic_array_contract = _bind_dynamic_array_contract
check_param_mapping = _check_param_mapping
check_param_mappings_for_single = _check_param_mappings_for_single
check_param_mappings_for_type_instance = _check_param_mappings_for_type_instance
get_required_parameter_names_for_typedef = _get_required_parameter_names_for_typedef
index_all_variables = _index_all_variables
iter_anytype_typedefs = _iter_anytype_typedefs
make_nested_contract_extractor = _make_nested_contract_extractor
validate_dynamic_array_get = _validate_dynamic_array_get

__all__ = [
    "VariablesContractsMixin",
    "bind_dynamic_array_contract",
    "build_anytype_field_contracts",
    "build_anytype_parameter_contract",
    "check_param_mapping",
    "check_param_mappings_for_single",
    "check_param_mappings_for_type_instance",
    "get_required_parameter_names_for_typedef",
    "index_all_variables",
    "iter_anytype_typedefs",
    "make_nested_contract_extractor",
    "validate_dynamic_array_get",
]
