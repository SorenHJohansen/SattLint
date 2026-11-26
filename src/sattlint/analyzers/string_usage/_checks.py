"""Static and range-based string checks over a module tree."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from sattlint.parser_api import Assignment, FuncCallStmt, ScalarDatatype

from ...config.string_capacities import StringCapacities
from .._string_models import StringSlot, StringSlotKey
from ..shared._string_capacity import capacity_for_datatype, is_string_datatype
from ..shared.statement_sites import iter_nested_statement_sites
from ..string_contexts import (
    StringModuleContext,
    declared_variables,
    module_code,
    resolve_string_slot,
    resolve_string_target,
)
from ._literal_flow import LiteralFlowResult
from ._model import SlotTypes, StringUsageFinding, dedupe_findings, display_path, statement_path

_DATATYPE_LABELS: tuple[tuple[ScalarDatatype, str], ...] = (
    (ScalarDatatype.IDENTSTRING, "identstring"),
    (ScalarDatatype.TAGSTRING, "tagstring"),
    (ScalarDatatype.STRING, "string"),
    (ScalarDatatype.LINESTRING, "linestring"),
    (ScalarDatatype.MAXSTRING, "maxstring"),
)


@dataclass(frozen=True, slots=True)
class Declaration:
    slot: StringSlot
    role: str
    const: bool


def datatype_label(datatype: ScalarDatatype | str | None) -> str:
    if isinstance(datatype, ScalarDatatype):
        return datatype.value
    return str(datatype) if datatype is not None else "unknown"


def collect_declarations(
    contexts: tuple[StringModuleContext, ...],
    *,
    types: SlotTypes,
) -> dict[StringSlotKey, Declaration]:
    declarations: dict[StringSlotKey, Declaration] = {}
    for context in sorted(contexts, key=lambda item: item.path):
        aliases = frozenset(context.scope.param_mappings)
        for variable in declared_variables(context.node):
            if variable.name.casefold() in aliases:
                continue
            slot = resolve_string_slot(context.scope, variable.name)
            if slot is None or not types.is_string(slot):
                continue
            key = slot.key
            if key.module_path != tuple(segment.casefold() for segment in context.path):
                continue
            if key.field_path:
                continue
            role = (
                "moduleparameter" if variable.name.casefold() in context.scope.moduleparameter_keys else "localvariable"
            )
            declarations.setdefault(key, Declaration(slot=slot, role=role, const=bool(variable.const)))
    return declarations


def iter_statement_sites(context: StringModuleContext) -> Iterator[tuple[object, str]]:
    """Yield every statement with a human-readable location."""
    code = module_code(context.node)
    if code is None:
        return
    for event in iter_nested_statement_sites(code):
        yield event.node, event.site


def collect_literal_findings(
    contexts: tuple[StringModuleContext, ...],
    *,
    types: SlotTypes,
) -> list[StringUsageFinding]:
    findings: list[StringUsageFinding] = []
    seen_declarations: set[int] = set()
    for context in sorted(contexts, key=lambda item: item.path):
        for variable in declared_variables(context.node):
            if not is_string_datatype(variable.datatype) or id(variable) in seen_declarations:
                continue
            seen_declarations.add(id(variable))
            if variable.name.casefold() in context.scope.param_mappings:
                continue
            init_value = variable.init_value
            capacity = capacity_for_datatype(types.capacities, variable.datatype)
            if not isinstance(init_value, str) or capacity is None or len(init_value) <= capacity:
                continue
            findings.append(
                _literal_finding(
                    variable_name=variable.name,
                    datatype=datatype_label(variable.datatype),
                    capacity=capacity,
                    length=len(init_value),
                    module_path=display_path(context.path),
                    site="initializer",
                    is_initializer=True,
                )
            )

    for context in contexts:
        for statement, site in iter_statement_sites(context):
            if not isinstance(statement, Assignment):
                continue
            target = resolve_string_target(context.scope, statement.target)
            if target is None or not types.is_string(target):
                continue
            capacity = types.capacity(target)
            if capacity is None or not isinstance(statement.value, str) or len(statement.value) <= capacity:
                continue
            findings.append(
                _literal_finding(
                    variable_name=target.display_name,
                    datatype=datatype_label(types.datatype(target)),
                    capacity=capacity,
                    length=len(statement.value),
                    module_path=statement_path(context),
                    site=site,
                    is_initializer=False,
                )
            )
    return dedupe_findings(findings)


def _literal_finding(
    *,
    variable_name: str,
    datatype: str,
    capacity: int,
    length: int,
    module_path: tuple[str, ...],
    site: str,
    is_initializer: bool,
) -> StringUsageFinding:
    return StringUsageFinding(
        kind="string_capacity.literal_overflow",
        message=(
            f"{'Initializer' if is_initializer else 'Assignment'} for "
            f"'{variable_name}' uses {length} characters, but its {datatype} capacity is {capacity}."
        ),
        module_path=module_path,
        site=site,
        details=(
            ("variable_name", variable_name),
            ("datatype", datatype),
            ("capacity", capacity),
            ("length", length),
            ("site", site),
        ),
        explanation="A value longer than the declared capacity is truncated or loses characters.",
        suggestion="Shorten the value, or declare the target with a string datatype that fits it.",
    )


def collect_copy_findings(
    contexts: tuple[StringModuleContext, ...],
    *,
    types: SlotTypes,
) -> list[StringUsageFinding]:
    findings: list[StringUsageFinding] = []
    for context in contexts:
        for statement, site in iter_statement_sites(context):
            if not isinstance(statement, FuncCallStmt):
                continue
            name = statement.call.name.casefold()
            if name not in {"copyvariable", "copyvarnosort"} or len(statement.call.args) < 2:
                continue
            source = resolve_string_target(context.scope, statement.call.args[0])
            target = resolve_string_target(context.scope, statement.call.args[1])
            if source is None or target is None or not types.is_string(source) or not types.is_string(target):
                continue
            if name == "copyvarnosort":
                replacement = "CopyStringNoSort"
                message = (
                    f"{statement.call.name} copies between string variables; "
                    f"{replacement} is the string-specific no-sort copy."
                )
                explanation = "A generic copy hides that both operands are strings."
                suggestion = "Use CopyStringNoSort when both operands are strings."
                argument_change = None
            else:
                replacement = "CopyString"
                message = (
                    f"{statement.call.name} copies between string variables; "
                    "CopyString is the string-specific copy and takes a Boolean case-sensitivity argument."
                )
                explanation = (
                    "CopyVariable already sorts, but its third argument is a status output. "
                    "CopyString takes a Boolean that selects case sensitivity instead."
                )
                suggestion = "Use CopyString with a Boolean case-sensitivity argument when both operands are strings."
                argument_change = "third argument becomes a Boolean case-sensitivity choice"
            findings.append(
                StringUsageFinding(
                    kind="string_style.generic_copy",
                    message=message,
                    module_path=statement_path(context),
                    site=site,
                    details=(
                        ("operation", statement.call.name),
                        ("suggested_operation", replacement),
                        ("source", source.display_name),
                        ("target", target.display_name),
                        ("source_datatype", datatype_label(types.datatype(source))),
                        ("target_datatype", datatype_label(types.datatype(target))),
                        ("argument_change", argument_change),
                        ("site", site),
                    ),
                    explanation=explanation,
                    suggestion=suggestion,
                )
            )
    return dedupe_findings(findings)


def collect_rightsizing_findings(
    contexts: tuple[StringModuleContext, ...],
    *,
    types: SlotTypes,
    declarations: dict[StringSlotKey, Declaration],
    flow: LiteralFlowResult,
) -> list[StringUsageFinding]:
    findings: list[StringUsageFinding] = []
    for key, declaration in declarations.items():
        if declaration.role != "localvariable" or declaration.const:
            continue
        module_path = key.module_path
        if len(module_path) <= 1:
            continue
        # Only a slot whose every write is a known literal can be narrowed: a
        # value this pass could not read might not fit the smaller datatype.
        if key in flow.tainted:
            continue
        observed = flow.observed.get(key)
        if observed is None or observed <= 0:
            continue
        declared = types.datatype(declaration.slot)
        declared_capacity = types.capacity(declaration.slot)
        if declared_capacity is None:
            continue
        candidate = _smallest_fitting_datatype(types.capacities, observed, declared_capacity)
        if candidate is None:
            continue
        candidate_label, candidate_capacity = candidate
        findings.append(
            StringUsageFinding(
                kind="string_style.narrower_datatype",
                message=(
                    f"'{declaration.slot.display_name}' is declared "
                    f"{datatype_label(declared)} ({declared_capacity} characters) but its values use "
                    f"at most {observed}, which fits {candidate_label} ({candidate_capacity} characters)."
                ),
                module_path=display_path(tuple(module_path)),
                site="declaration",
                details=(
                    ("variable_name", declaration.slot.display_name),
                    ("datatype", datatype_label(declared)),
                    ("capacity", declared_capacity),
                    ("observed_length", observed),
                    ("suggested_datatype", candidate_label),
                    ("suggested_capacity", candidate_capacity),
                ),
                explanation=("A wider datatype than the stored values need makes the capacity contract less precise."),
                suggestion="Declare the variable with the smaller string datatype that already fits every value.",
            )
        )
    return dedupe_findings(findings)


def _smallest_fitting_datatype(
    capacities: StringCapacities,
    observed: int,
    declared_capacity: int,
) -> tuple[str, int] | None:
    candidates: list[tuple[int, str]] = []
    for datatype, label in _DATATYPE_LABELS:
        capacity = capacity_for_datatype(capacities, datatype)
        if capacity is None or capacity < observed or capacity >= declared_capacity:
            continue
        candidates.append((capacity, label))
    if not candidates:
        return None
    capacity, label = min(candidates, key=lambda item: item[0])
    return label, capacity


__all__ = [
    "Declaration",
    "collect_copy_findings",
    "collect_declarations",
    "collect_literal_findings",
    "collect_rightsizing_findings",
    "datatype_label",
    "iter_statement_sites",
]
