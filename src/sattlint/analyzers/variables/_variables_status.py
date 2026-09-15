"""Procedure-status helpers for variable analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from sattline_parser.models.ast_model import Variable
from sattline_parser.models.expressions import VarRef

from ...core.call_signatures import CallParameterSignature, resolve_call_signature
from ...grammar import constants as const
from ...models.usage import VariableUsage
from ...resolution.scope import ScopeContext

if TYPE_CHECKING:
    from . import VariablesAnalyzer


_IGNORABLE_OUTPUT_PARAMETERS: dict[str, frozenset[str]] = {
    # SearchRecComponent returns the boolean success signal directly.
    # The FoundRec out slot is required by the builtin signature, but callers
    # commonly use it as a scratch sink when they only care whether a match exists.
    "searchreccomponent": frozenset({"foundrec"}),
}


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


def _bind_ignorable_output(
    self: VariablesAnalyzer,
    full_ref: str,
    *,
    context: ScopeContext,
) -> None:
    resolved_var, _resolved_field_path, _decl_path, _decl_display = context.resolve_variable(full_ref)
    if resolved_var is None:
        return

    self.ignorable_output_variable_ids.add(id(resolved_var))


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
        if isinstance(argument, VarRef):
            full_ref = argument.name
        elif isinstance(argument, dict) and const.KEY_VAR_NAME in argument:
            argument_dict = cast(dict[str, object], argument)
            full_ref = argument_dict.get(const.KEY_VAR_NAME)
            if not isinstance(full_ref, str):
                continue
        else:
            continue
        self.bind_procedure_status(
            full_ref,
            call_name=fn_name,
            parameter=parameter,
            context=context,
        )


def _record_ignorable_output_bindings(
    self: VariablesAnalyzer,
    fn_name: str,
    args: list[Any],
    context: ScopeContext,
) -> None:
    signature = resolve_call_signature(fn_name)
    if signature is None:
        return

    ignorable_parameters = _IGNORABLE_OUTPUT_PARAMETERS.get(fn_name.casefold())
    if not ignorable_parameters:
        return

    for index, parameter in enumerate(signature.parameters):
        if index >= len(args):
            continue
        if parameter.direction not in {"out", "inout"}:
            continue
        if parameter.name.casefold() not in ignorable_parameters:
            continue

        argument = args[index]
        if isinstance(argument, VarRef):
            full_ref = argument.name
        elif isinstance(argument, dict) and const.KEY_VAR_NAME in argument:
            argument_dict = cast(dict[str, object], argument)
            full_ref = argument_dict.get(const.KEY_VAR_NAME)
            if not isinstance(full_ref, str):
                continue
        else:
            continue
        self.bind_ignorable_output(full_ref, context=context)


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


def _has_ignorable_output_binding(self: VariablesAnalyzer, variable: Variable) -> bool:
    return id(variable) in self.ignorable_output_variable_ids


class VariablesStatusMixin:
    def _bind_procedure_status(
        self: Any,
        full_ref: str,
        *,
        call_name: str,
        parameter: CallParameterSignature,
        context: ScopeContext,
    ) -> None:
        _bind_procedure_status(self, full_ref, call_name=call_name, parameter=parameter, context=context)

    def _bind_ignorable_output(
        self: Any,
        full_ref: str,
        *,
        context: ScopeContext,
    ) -> None:
        _bind_ignorable_output(self, full_ref, context=context)

    def _record_procedure_status_bindings(
        self: Any,
        fn_name: str,
        args: list[Any],
        context: ScopeContext,
    ) -> None:
        _record_procedure_status_bindings(self, fn_name, args, context)

    def _record_ignorable_output_bindings(
        self: Any,
        fn_name: str,
        args: list[Any],
        context: ScopeContext,
    ) -> None:
        _record_ignorable_output_bindings(self, fn_name, args, context)

    def _propagate_procedure_status_bindings(self: Any) -> None:
        _propagate_procedure_status_bindings(self)

    def _procedure_status_issue(
        self: Any,
        variable: Variable,
        usage: VariableUsage,
    ) -> tuple[str, str | None] | None:
        return _procedure_status_issue(self, variable, usage)

    def _has_procedure_status_binding(self: Any, variable: Variable) -> bool:
        return _has_procedure_status_binding(self, variable)

    def _has_ignorable_output_binding(self: Any, variable: Variable) -> bool:
        return _has_ignorable_output_binding(self, variable)


ProcedureStatusBinding = _ProcedureStatusBinding
bind_ignorable_output = _bind_ignorable_output
bind_procedure_status = _bind_procedure_status
has_ignorable_output_binding = _has_ignorable_output_binding
has_procedure_status_binding = _has_procedure_status_binding
procedure_status_issue = _procedure_status_issue
propagate_procedure_status_bindings = _propagate_procedure_status_bindings
record_ignorable_output_bindings = _record_ignorable_output_bindings
record_procedure_status_bindings = _record_procedure_status_bindings

__all__ = [
    "ProcedureStatusBinding",
    "VariablesStatusMixin",
    "bind_ignorable_output",
    "bind_procedure_status",
    "has_ignorable_output_binding",
    "has_procedure_status_binding",
    "procedure_status_issue",
    "propagate_procedure_status_bindings",
    "record_ignorable_output_bindings",
    "record_procedure_status_bindings",
]
