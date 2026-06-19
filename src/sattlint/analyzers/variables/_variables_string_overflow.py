"""String operation overflow issue collection for variable analysis."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sattline_parser.models.ast_model import Simple_DataType, Variable

from ..._validation_type_helpers import is_string_simple_type
from ...reporting.variables_report import IssueKind, VariableIssue
from ...string_inference import ExactStringInferenceEngine, StringInferenceResult

if TYPE_CHECKING:
    from . import VariablesAnalyzer


def _overflow_source_name(result: StringInferenceResult) -> str:
    operation_name = result.overflow_operations[0] if len(result.overflow_operations) == 1 else "string operation"
    base_name = f"{operation_name} result"
    if not result.overflow_examples:
        return base_name
    example = result.overflow_examples[0]
    if len(example) > 32:
        example = f"{example[:29]}..."
    return f"{base_name} {example!r}"


def collect_string_operation_overflow_issues(self: VariablesAnalyzer) -> None:
    string_engine = ExactStringInferenceEngine(self.bp)
    seen_slots: set[tuple[tuple[str, ...], str]] = set()
    added_issue_count = 0

    for context in self.contexts_by_module_path.values():
        for variable in context.env.values():
            resolved_var, field_path, decl_path, _decl_display = context.resolve_variable(variable.name)
            if resolved_var is None or field_path:
                continue
            if not is_string_simple_type(resolved_var.datatype):
                continue

            slot_key = (tuple(segment.casefold() for segment in decl_path), resolved_var.name.casefold())
            if slot_key in seen_slots:
                continue
            seen_slots.add(slot_key)

            result = string_engine.infer(variable.name, module_path=context.module_path)
            if not result.overflowed:
                continue

            source_name = _overflow_source_name(result)
            source_variable = Variable(name=source_name, datatype=Simple_DataType.STRING)
            issue = VariableIssue(
                kind=IssueKind.STRING_MAPPING_MISMATCH,
                module_path=list(decl_path),
                variable=resolved_var,
                role="string operation overflow",
                source_variable=source_variable,
                source_decl_module_path=list(decl_path),
                source_role="builtin result",
                source_display_name=source_name,
                target_display_name=resolved_var.name,
                validation_source_variable=source_variable,
                validation_source_module_path=list(decl_path),
            )
            self.append_issue(issue)
            added_issue_count += 1

    self._trace("string-operation-overflow-scan", added_issue_count=added_issue_count)
