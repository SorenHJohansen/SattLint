"""Structured analyzer findings for the checks pipeline.

Analyzer reports expose heterogeneous ``issues`` shapes (framework ``Issue``,
``VariableIssue``, semantic rules, etc.). This module normalizes them into a
single typed, serializable :class:`AnalysisFinding` so the TUI tree, run
history, and CLI JSON output all consume one consistent shape.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from ..models._variable_issues import materialize_variable_issue_metadata


def _empty_data() -> dict[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class AnalysisFinding:
    kind: str
    message: str
    module_path: tuple[str, ...] = ()
    severity: str | None = None
    confidence: str | None = None
    rule_id: str | None = None
    explanation: str | None = None
    suggestion: str | None = None
    data: dict[str, Any] = field(default_factory=_empty_data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "module_path": list(self.module_path),
            "severity": self.severity,
            "confidence": self.confidence,
            "rule_id": self.rule_id,
            "explanation": self.explanation,
            "suggestion": self.suggestion,
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> AnalysisFinding:
        raw_module_path = cast(list[object] | tuple[object, ...] | None, payload.get("module_path"))
        module_path = tuple(str(segment) for segment in (raw_module_path or ()))
        raw_data = payload.get("data")
        data: dict[str, Any] = {}
        if isinstance(raw_data, Mapping):
            mapping = cast(Mapping[str, object], raw_data)
            data = {str(key): cast(Any, value) for key, value in mapping.items()}
        return cls(
            kind=str(payload.get("kind") or ""),
            message=str(payload.get("message") or ""),
            module_path=module_path,
            severity=_optional_str(payload.get("severity")),
            confidence=_optional_str(payload.get("confidence")),
            rule_id=_optional_str(payload.get("rule_id")),
            explanation=_optional_str(payload.get("explanation")),
            suggestion=_optional_str(payload.get("suggestion")),
            data=data,
        )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _kind_value(item: object) -> str:
    kind = getattr(item, "kind", None)
    if kind is not None:
        value = getattr(kind, "value", kind)
        text = str(value).strip()
        if text:
            return text
    rule = getattr(item, "rule", None)
    rule_id = getattr(rule, "id", None)
    if rule_id is not None:
        return str(rule_id).strip()
    return ""


def _message_value(item: object) -> str:
    message = getattr(item, "message", None)
    if message is not None:
        text = str(message).strip()
        if text:
            return text
    return str(item).strip()


def _module_path_value(item: object) -> tuple[str, ...]:
    raw_path = getattr(item, "module_path", None)
    if not isinstance(raw_path, (list, tuple)):
        return ()
    return tuple(str(segment) for segment in cast(list[object] | tuple[object, ...], raw_path) if segment)


def _issue_metadata_value(item: object, attr_name: str) -> str | None:
    value = getattr(item, attr_name, None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _sanitize_data_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        return {str(key): _sanitize_data_value(item) for key, item in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return [_sanitize_data_value(item) for item in sequence]
    return str(value)


def _issue_data_value(item: object) -> dict[str, Any]:
    raw_data = getattr(item, "data", None)
    data: dict[str, Any] = {}
    if isinstance(raw_data, Mapping):
        mapping = cast(Mapping[str, object], raw_data)
        for key, value in mapping.items():
            data[str(key)] = _sanitize_data_value(value)
    _merge_synthesized_context(item, data)
    return data


def _merge_synthesized_context(item: object, data: dict[str, Any]) -> None:
    """Fill ``site``/``context`` for issue models that have no ``data`` dict.

    ``VariableIssue`` and friends carry ``site`` / ``sequence_name`` /
    ``source_display_name`` / ``target_display_name`` attributes instead of a
    ``data`` mapping; surface them under the same keys the results tree reads.
    Existing ``data`` values always win.
    """
    if "site" not in data:
        site = _synthesized_site(item)
        if site:
            data["site"] = site
    if "context" not in data:
        context = _synthesized_context(item)
        if context:
            data["context"] = context


def _synthesized_site(item: object) -> str | None:
    sequence_name = getattr(item, "sequence_name", None)
    if isinstance(sequence_name, str) and sequence_name.strip():
        return f"SQ:{sequence_name.strip()}"
    site = getattr(item, "site", None)
    if isinstance(site, str) and site.strip():
        return site.strip()
    return None


def _synthesized_context(item: object) -> str | None:
    explicit_context = getattr(item, "context", None)
    if isinstance(explicit_context, str) and explicit_context.strip():
        return explicit_context.strip()
    target = getattr(item, "target_display_name", None)
    source = getattr(item, "source_display_name", None)
    if isinstance(target, str) and target.strip() and isinstance(source, str) and source.strip():
        return f"{target.strip()} => {source.strip()}"
    role = getattr(item, "role", None)
    if isinstance(role, str) and role.strip() and " " in role.strip():
        return role.strip()
    variable = getattr(item, "variable", None)
    variable_name = getattr(variable, "name", None)
    if isinstance(variable_name, str) and variable_name.strip():
        return variable_name.strip()
    return None


def extract_report_findings(report: object, *, default_name: str) -> tuple[AnalysisFinding, ...]:
    """Normalize a report's ``issues`` into structured findings.

    Reports without a list-like ``issues`` attribute yield no findings.
    """
    issues = getattr(report, "issues", None)
    if not isinstance(issues, list):
        return ()
    if not issues:
        return ()

    findings: list[AnalysisFinding] = []
    for item in cast(list[object], issues):
        module_path = _module_path_value(item)
        explanation = _issue_metadata_value(item, "explanation")
        if explanation is None:
            explanation = _variable_issue_text(item, "explanation")
        suggestion = _issue_metadata_value(item, "suggestion")
        if suggestion is None:
            suggestion = _variable_issue_text(item, "suggestion")
        findings.append(
            AnalysisFinding(
                kind=_kind_value(item),
                message=_message_value(item),
                module_path=module_path or (default_name,),
                severity=_issue_metadata_value(item, "severity"),
                confidence=_issue_metadata_value(item, "confidence"),
                rule_id=_issue_metadata_value(item, "rule_id"),
                explanation=explanation,
                suggestion=suggestion,
                data=_issue_data_value(item),
            )
        )
    return tuple(findings)


def _variable_issue_text(item: object, field_name: str) -> str | None:
    try:
        metadata = materialize_variable_issue_metadata(item)
    except Exception:  # noqa: BLE001 - best-effort enrichment for heterogeneous issue models
        return None
    value = getattr(metadata, field_name, None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


_KIND_HUMAN_LABELS: dict[str, str] = {
    "magic_number": "Magic number",
    "unused": "Unused variable",
    "unused_datatype_field": "Unused datatype field",
    "field_read_only": "Field read only",
    "read_only_non_const": "Read-only non-const",
    "never_read": "Never read",
    "write_without_effect": "Write without effect",
    "ui_only": "UI only",
    "implicit_latch": "Implicit latch",
    "reset_contamination": "Reset contamination",
    "naming_role_mismatch": "Naming role mismatch",
    "global_scope_minimization": "Global scope minimization",
    "hidden_global_coupling": "Hidden global coupling",
    "high_fan_in_out": "High fan-in/out",
    "datatype_duplication": "Datatype duplication",
    "name_collision": "Name collision",
    "layout_overlap": "Layout overlap",
    "min_max_mapping_mismatch": "Min/Max mapping mismatch",
    "unknown_parameter_target": "Unknown parameter target",
    "required_parameter_connection": "Required parameter connection",
    "contract_mismatch": "Contract mismatch",
    "string_mapping_mismatch": "String mapping mismatch",
    "procedure_status": "Procedure status",
    "shadowing": "Variable shadowing",
    "record_component_order_dependence": "Record component order dependence",
    "sfc_parallel_write_race": "Parallel write race",
    "sfc_unreachable_sequence_node": "Unreachable sequence node",
    "sfc_unreachable_transition": "Unreachable transition",
    "sfc_transition_always_true": "Transition always true",
    "sfc_transition_always_false": "Transition always false",
    "sfc_duplicate_transition_guard": "Duplicate transition guard",
    "sfc_illegal_state_combination": "Illegal state combination",
    "sfc_missing_step_enter_contract": "Missing step enter contract",
    "sfc_missing_step_exit_contract": "Missing step exit contract",
    "sfc_step_state_leakage": "Step state leakage",
    "dataflow.read_before_write": "Read before write",
    "dataflow.dead_overwrite": "Dead overwrite",
    "dataflow.condition_always_true": "Condition always true",
    "dataflow.condition_always_false": "Condition always false",
    "dataflow.unreachable_branch": "Unreachable branch",
    "dataflow.unreachable_sequence_node": "Unreachable sequence node",
    "dataflow.self_compare_condition": "Self-compare condition",
    "dataflow.scan_cycle_stale_read": "Stale :OLD read",
    "dataflow.scan_cycle_implicit_new": "Implicit :NEW read",
    "dataflow.scan_cycle_temporal_misuse": ":OLD misuse",
    "dataflow.invalid_state_access": "Invalid state access",
    "state_inference.condition_always_true": "Condition always true",
    "state_inference.condition_always_false": "Condition always false",
    "state_inference.unreachable_branch": "Unreachable branch",
    "signal_lifecycle.read_before_write": "Read before write",
    "signal_lifecycle.unconsumed_write": "Unconsumed write",
    "loop_stability.conflicting_setpoint": "Conflicting setpoint",
    "numeric_constraints.limit_violation": "Limit violation",
    "data_dependency.path": "Dependency path",
    "data_dependency.initialization_order": "Initialization order",
    "resource_usage.acquire_without_release": "Acquire without release",
    "resource_usage.release_without_acquire": "Release without acquire",
    "resource_usage.leaked_resource": "Leaked resource",
    "scan_cycle.resource_usage": "Scan-cycle resource usage",
    "fault_handling.missing_recovery": "Missing fault recovery",
    "fault_handling.unhandled_fault": "Unhandled fault",
    "config_drift.instance_configuration": "Instance configuration drift",
    "module.parameter_drift": "Parameter drift",
    "module.version_drift": "Version drift",
    "naming.inconsistent_style": "Inconsistent naming style",
    "module.cyclomatic_complexity": "High cyclomatic complexity",
    "step.cyclomatic_complexity": "High step complexity",
    "alarm.duplicate_tag": "Duplicate alarm tag",
    "alarm.duplicate_condition": "Duplicate alarm condition",
    "alarm.conflicting_priority": "Conflicting alarm priority",
    "alarm.never_cleared": "Alarm never cleared",
    "mms.duplicate_tag": "Duplicate MMS tag",
    "mms.datatype_mismatch": "MMS datatype mismatch",
    "mms.naming_drift": "MMS naming drift",
    "mms.dead_tag": "Dead MMS tag",
    "comment_code": "Commented-out code",
    "comment_code_read_error": "Comment read error",
    "spec.basepicture_direct_code": "BasePicture direct code",
    "spec.sequence_step_prefix": "Sequence step prefix",
    "spec.transition_name_missing": "Transition name missing",
    "spec.transition_prefix": "Transition prefix",
    "spec.opmessage_use_signature": "OPMessage UseSignature",
    "spec.mes_batch_control_name": "MES_BatchControl name",
    "spec.mes_batch_control_max_try": "MES_BatchControl Max_TRY",
    "spec.mes_batch_control_repeat_try": "MES_BatchControl Repeat_TRY",
    "safety-path.unconsumed_signal": "Unconsumed safety signal",
    "taint-path.external_input_to_critical_sink": "External input to critical sink",
    "unsafe_defaults.true_boolean_default": "Unsafe boolean default",
    "same_cycle_shared_access_hazard": "Same-cycle shared access",
    "same_cycle_parallel_read_write_hazard": "Parallel read/write hazard",
    "same_cycle_non_state_multi_site_hazard": "Non-state multi-site access",
    "picture_display_paths.unresolved": "Unresolved PictureDisplay path",
    "icf.program_mismatch": "ICF program mismatch",
    "icf.unresolved_path": "ICF unresolved path",
    "icf.invalid_field_path": "ICF invalid field path",
    "icf.reference_case_mismatch": "ICF reference case mismatch",
    "icf.unit_tag_mismatch": "ICF unit tag mismatch",
    "icf.group_tag_mismatch": "ICF group tag mismatch",
    "icf.missing_journal_field": "ICF missing journal field",
    "icf.unit_structure_drift": "ICF unit structure drift",
    "icf.value_prefix_inconsistency": "ICF value prefix inconsistency",
    "icf.program_load_failed": "ICF program load failed",
    "duplicate_sibling_name": "Duplicate sibling name",
    "unexpected_submodule_type": "Unexpected submodule type",
    "unreachable_sequence_node": "Unreachable sequence node",
    "scan_cycle_shared_access_hazard": "Same-cycle shared access",
    "scan_cycle_parallel_read_write_hazard": "Parallel read/write hazard",
    "scan_cycle_non_state_multi_site_hazard": "Non-state multi-site access",
}


def kind_human_label(kind: str) -> str:
    """Return a short human-readable label for an issue kind.

    Uses a curated map for the known kinds; anything else is humanized by
    dropping the ``analyzer.`` prefix, splitting underscores, and title-casing.
    """
    label = _KIND_HUMAN_LABELS.get(kind)
    if label:
        return label
    text = kind.split(".", 1)[-1]
    words = [word for word in re.split(r"[_\s]+", text) if word]
    if not words:
        return kind
    return " ".join(word[:1].upper() + word[1:] for word in words)


__all__ = ["AnalysisFinding", "extract_report_findings", "kind_human_label"]
