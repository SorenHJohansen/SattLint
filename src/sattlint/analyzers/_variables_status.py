"""Naming-role and procedure-status helpers for variable analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from sattline_parser.models.ast_model import Variable

from ..call_signatures import CallParameterSignature, resolve_call_signature
from ..grammar import constants as const
from ..models.usage import VariableUsage
from ..reporting.variables_report import IssueKind
from ..resolution.scope import ScopeContext
from .variable_issue_collection import _iter_variables_for_datatype_field_analysis

if TYPE_CHECKING:
    from .variables import VariablesAnalyzer


@dataclass(frozen=True)
class _NamingRolePatterns:
    prefixes: tuple[str, ...] = ()
    suffixes: tuple[str, ...] = ()


_DEFAULT_NAMING_ROLE_PATTERNS: dict[str, _NamingRolePatterns] = {
    "command": _NamingRolePatterns(suffixes=("cmd",)),
    "status": _NamingRolePatterns(suffixes=("status",)),
    "alarm": _NamingRolePatterns(suffixes=("alarm",)),
}


def _normalize_role_pattern_values(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return ()
    raw_values = cast(list[object], raw)
    values: list[str] = []
    seen: set[str] = set()
    for item in raw_values:
        if not isinstance(item, str):
            continue
        value = item.strip().casefold()
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return tuple(values)


def _as_string_object_mapping(raw: object) -> Mapping[str, object] | None:
    if not isinstance(raw, Mapping):
        return None
    return cast(Mapping[str, object], raw)


def _configured_naming_role_patterns(
    config: Mapping[str, object] | None,
) -> dict[str, _NamingRolePatterns]:
    patterns = dict(_DEFAULT_NAMING_ROLE_PATTERNS)
    if config is None:
        return patterns

    analysis = _as_string_object_mapping(config.get("analysis"))
    if analysis is None:
        return patterns

    naming = _as_string_object_mapping(analysis.get("naming"))
    if naming is None:
        return patterns

    raw_role_patterns = _as_string_object_mapping(naming.get("role_patterns"))
    if raw_role_patterns is None:
        return patterns

    for role_name, defaults in _DEFAULT_NAMING_ROLE_PATTERNS.items():
        raw_rule = _as_string_object_mapping(raw_role_patterns.get(role_name))
        if raw_rule is None:
            continue
        prefixes = tuple(
            dict.fromkeys((*defaults.prefixes, *_normalize_role_pattern_values(raw_rule.get("prefixes", []))))
        )
        suffixes = tuple(
            dict.fromkeys((*defaults.suffixes, *_normalize_role_pattern_values(raw_rule.get("suffixes", []))))
        )
        patterns[role_name] = _NamingRolePatterns(prefixes=prefixes, suffixes=suffixes)

    return patterns


@dataclass(frozen=True)
class _ProcedureStatusBinding:
    call_name: str
    parameter_name: str
    channel_kind: str
    field_path: str | None = None


def _bind_procedure_status(
    self: VariablesAnalyzer,
    full_ref: str,
    *,
    call_name: str,
    parameter: CallParameterSignature,
    context: ScopeContext,
) -> None:
    resolved_var, resolved_field_path, _decl_path, _decl_display = context.resolve_variable(full_ref)
    if resolved_var is None:
        return

    binding = _ProcedureStatusBinding(
        call_name=call_name,
        parameter_name=parameter.name,
        channel_kind=parameter.channel_kind or "status",
        field_path=resolved_field_path or None,
    )
    bindings = self.procedure_status_bindings[id(resolved_var)]
    if binding not in bindings:
        bindings.append(binding)


def _record_procedure_status_bindings(
    self: VariablesAnalyzer,
    fn_name: str,
    args: list[Any],
    context: ScopeContext,
) -> None:
    signature = resolve_call_signature(fn_name)
    if signature is None:
        return

    for index, parameter in enumerate(signature.parameters):
        if not parameter.is_status_channel or index >= len(args):
            continue
        argument = args[index]
        if not (isinstance(argument, dict) and const.KEY_VAR_NAME in argument):
            continue
        argument_dict = cast(dict[str, object], argument)
        full_ref = argument_dict.get(const.KEY_VAR_NAME)
        if not isinstance(full_ref, str):
            continue
        self.bind_procedure_status(
            full_ref,
            call_name=fn_name,
            parameter=parameter,
            context=context,
        )


def _propagate_procedure_status_bindings(self: VariablesAnalyzer) -> None:
    for source_var, target_var, mapping_name in self.alias_links:
        propagated: list[_ProcedureStatusBinding] = []
        for binding in self.procedure_status_bindings.get(id(target_var), []):
            field_path = binding.field_path
            if mapping_name and field_path:
                field_path = f"{mapping_name}.{field_path}"
            elif mapping_name:
                field_path = mapping_name
            propagated.append(
                _ProcedureStatusBinding(
                    call_name=binding.call_name,
                    parameter_name=binding.parameter_name,
                    channel_kind=binding.channel_kind,
                    field_path=field_path,
                )
            )

        if not propagated:
            continue

        source_bindings = self.procedure_status_bindings[id(source_var)]
        for binding in propagated:
            if binding not in source_bindings:
                source_bindings.append(binding)


def _procedure_status_issue(
    self: VariablesAnalyzer,
    variable: Variable,
    usage: VariableUsage,
) -> tuple[str, str | None] | None:
    bindings = self.procedure_status_bindings.get(id(variable), [])
    if not bindings or not usage.written:
        return None
    if usage.non_ui_read:
        return None

    binding = bindings[0]
    channel_label = (
        "procedure status output" if binding.channel_kind == "status" else "procedure async-operation handle"
    )
    if usage.ui_read:
        return (
            f"{channel_label} from {binding.call_name!r} parameter {binding.parameter_name!r} is only surfaced through UI wiring and is not checked in control logic.",
            binding.field_path,
        )
    return (
        f"{channel_label} from {binding.call_name!r} parameter {binding.parameter_name!r} is ignored after the procedure writes it.",
        binding.field_path,
    )


def _has_procedure_status_binding(self: VariablesAnalyzer, variable: Variable) -> bool:
    return bool(self.procedure_status_bindings.get(id(variable)))


def _naming_role_mismatch_reason(
    self: VariablesAnalyzer,
    variable: Variable,
    usage: VariableUsage,
    decl_path: list[str],
) -> str | None:
    name_key = variable.name.casefold()
    if self.matches_naming_role(name_key, "command"):
        if usage.read and usage.written and not self.has_output_effect(variable, decl_path):
            return "Cmd-suffixed variable behaves like internal state instead of a one-way command signal."
        return None
    if self.matches_naming_role(name_key, "status"):
        if usage.written and not self.has_procedure_status_binding(variable):
            return "Status-suffixed variable is written directly in logic instead of being treated as observed status."
        return None
    if self.matches_naming_role(name_key, "alarm"):
        if usage.non_ui_read:
            return "Alarm-suffixed variable is consumed in non-UI logic and behaves like a control input."
        return None
    return None


def _matches_naming_role(self: VariablesAnalyzer, name_key: str, role_name: str) -> bool:
    patterns = self.naming_role_patterns.get(role_name, _NamingRolePatterns())
    return any(name_key.startswith(prefix) for prefix in patterns.prefixes) or any(
        name_key.endswith(suffix) for suffix in patterns.suffixes
    )


def _add_naming_role_mismatch_issues(self: VariablesAnalyzer) -> None:
    for decl_path, variable, _decl_role in _iter_variables_for_datatype_field_analysis(self):
        usage = self.get_usage(variable)
        reason = self.naming_role_mismatch_reason(variable, usage, decl_path)
        if reason is None:
            continue
        self.add_issue(
            IssueKind.NAMING_ROLE_MISMATCH,
            decl_path,
            variable,
            role=reason,
        )


ProcedureStatusBinding = _ProcedureStatusBinding
add_naming_role_mismatch_issues = _add_naming_role_mismatch_issues
bind_procedure_status = _bind_procedure_status
configured_naming_role_patterns = _configured_naming_role_patterns
has_procedure_status_binding = _has_procedure_status_binding
matches_naming_role = _matches_naming_role
naming_role_mismatch_reason = _naming_role_mismatch_reason
procedure_status_issue = _procedure_status_issue
propagate_procedure_status_bindings = _propagate_procedure_status_bindings
record_procedure_status_bindings = _record_procedure_status_bindings

__all__ = [
    "ProcedureStatusBinding",
    "add_naming_role_mismatch_issues",
    "bind_procedure_status",
    "configured_naming_role_patterns",
    "has_procedure_status_binding",
    "matches_naming_role",
    "naming_role_mismatch_reason",
    "procedure_status_issue",
    "propagate_procedure_status_bindings",
    "record_procedure_status_bindings",
]
