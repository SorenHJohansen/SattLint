"""Structured analyzer findings for the checks pipeline.

Analyzer reports expose heterogeneous ``issues`` shapes (framework ``Issue``,
``VariableIssue``, semantic rules, etc.). This module normalizes them into a
single typed, serializable :class:`AnalysisFinding` so the TUI tree, run
history, and CLI JSON output all consume one consistent shape.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from ..models._variable_issues import (
    DECLARATION_ROLE_LOCAL_VARIABLE,
    DECLARATION_ROLE_MODULE_PARAMETER,
    FieldPathVariableIssue,
    IssueKind,
    UnusedDatatypeFieldIssue,
    VariableTargetIssue,
    variable_issue_metadata,
)
from ..models.severity import SEVERITIES, Severity
from ..reporting.variables_report import VariablesReport

type FindingDataValue = str | int | float | bool | list[FindingDataValue] | dict[str, FindingDataValue] | None


def _empty_data() -> dict[str, FindingDataValue]:
    return {}


@dataclass(frozen=True, slots=True)
class AnalysisFinding:
    kind: str
    message: str
    module_path: tuple[str, ...] = ()
    rule_id: str | None = None
    severity: Severity | None = None
    explanation: str | None = None
    suggestion: str | None = None
    file: str | None = None
    line: int | None = None
    column: int | None = None
    end_line: int | None = None
    data: Mapping[str, FindingDataValue] = field(default_factory=_empty_data)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "message": self.message,
            "module_path": list(self.module_path),
            "rule_id": self.rule_id,
            "severity": self.severity,
            "explanation": self.explanation,
            "suggestion": self.suggestion,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> AnalysisFinding:
        raw_module_path = cast(list[object] | tuple[object, ...] | None, payload.get("module_path"))
        module_path = tuple(str(segment) for segment in (raw_module_path or ()))
        raw_data = payload.get("data")
        data: dict[str, FindingDataValue] = {}
        if isinstance(raw_data, Mapping):
            mapping = cast(Mapping[str, object], raw_data)
            data = {str(key): cast(FindingDataValue, value) for key, value in mapping.items()}
        return cls(
            kind=str(payload.get("kind") or ""),
            message=str(payload.get("message") or ""),
            module_path=module_path,
            rule_id=optional_text(payload.get("rule_id")),
            severity=_severity_value(payload.get("severity")),
            explanation=optional_text(payload.get("explanation")),
            suggestion=optional_text(payload.get("suggestion")),
            file=optional_text(payload.get("file")),
            line=_positive_int(payload.get("line")),
            column=_positive_int(payload.get("column")),
            end_line=_positive_int(payload.get("end_line")),
            data=data,
        )


def _stable_data_repr(value: object) -> str:
    """A repr that never includes a memory address."""
    return f"<{type(value).__name__}>"


def finding_data_key(finding: AnalysisFinding) -> str:
    """A stable fingerprint of the finding payload.

    Two findings can share a message and site but carry different detail (for
    example different previous writes). Collapsing them would keep only the
    first payload, so the data payload is part of finding identity in both the
    CLI and the Results pane.
    """
    try:
        return json.dumps(finding.data, sort_keys=True, default=_stable_data_repr, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(finding.data)


def optional_text(value: object) -> str | None:
    """A stripped string, or ``None`` when the value carries no text."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _positive_int(value: object) -> int | None:
    """A one-based position, or ``None`` when the value is absent or unusable."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value > 0 else None


def _severity_value(value: object) -> Severity | None:
    """A known severity, or ``None`` when the stored value is absent or unusable."""
    if isinstance(value, str) and value in SEVERITIES:
        return cast(Severity, value)
    return None


_SOURCE_FILE_SUFFIXES = frozenset({".s", ".x", ".sattline"})


def _looks_like_source_path(text: str) -> bool:
    """Whether a ``path`` payload value names a source file rather than a UI path.

    Some analyzers use ``path`` for a display path inside a picture. Those
    values carry no directory separator and no source-file suffix, so they must
    not become the finding's file.
    """
    if "/" in text or "\\" in text:
        return True
    suffix = text.rsplit(".", 1)[-1].casefold() if "." in text else ""
    return f".{suffix}" in _SOURCE_FILE_SUFFIXES


def format_source_location(
    *,
    file: str | None,
    line: int | None,
    column: int | None = None,
    end_line: int | None = None,
) -> str | None:
    """A compact one-based source location, or ``None`` when nothing is known."""
    has_range = line is not None and end_line is not None and end_line > line
    if file:
        location = file
        if line is not None:
            location = f"{location}:{line}"
            if has_range:
                location = f"{location}-{end_line}"
            if column is not None:
                location = f"{location}:{column}"
        return location
    if line is None:
        return None
    location = f"line {line}"
    if has_range:
        location = f"line {line}-{end_line}"
    if column is not None:
        location = f"{location}, column {column}"
    return location


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


def _sanitize_data_value(value: object) -> FindingDataValue:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        mapping = cast(Mapping[str, object], value)
        return {str(key): _sanitize_data_value(item) for key, item in mapping.items()}
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return [_sanitize_data_value(item) for item in sequence]
    return str(value)


_DECLARATION_ROLES = frozenset({DECLARATION_ROLE_LOCAL_VARIABLE, DECLARATION_ROLE_MODULE_PARAMETER})


def _declaration_role_value(item: object) -> str | None:
    """The declaration kind an issue is about, when the issue knows it.

    ``role`` is overloaded: it holds the declaration kind for the plain
    variable issues but descriptive text for procedure status, shadowing,
    read-before-write, and the unsafe-default check. ``declaration_role`` is
    the unambiguous field; fall back to ``role`` only when it already holds a
    declaration kind.
    """
    explicit = getattr(item, "declaration_role", None)
    if explicit in _DECLARATION_ROLES:
        return str(explicit)
    role = getattr(item, "role", None)
    return str(role) if role in _DECLARATION_ROLES else None


def _raw_issue_data(item: object) -> Mapping[str, object] | None:
    raw_data = getattr(item, "data", None)
    if not isinstance(raw_data, Mapping):
        return None
    return cast(Mapping[str, object], raw_data)


def _issue_data_value(item: object) -> dict[str, FindingDataValue]:
    raw_data = _raw_issue_data(item)
    data: dict[str, FindingDataValue] = {}
    if raw_data is not None:
        for key, value in raw_data.items():
            data[str(key)] = _sanitize_data_value(value)
    if isinstance(item, FieldPathVariableIssue | UnusedDatatypeFieldIssue) and item.field_path:
        data.setdefault("field_path", item.field_path)
        if isinstance(item, VariableTargetIssue):
            data.setdefault("variable_name", item.variable.name)
    declaration_role = _declaration_role_value(item)
    if declaration_role is not None:
        data.setdefault("declaration_role", declaration_role)
    _merge_synthesized_context(item, data)
    return data


def _merge_synthesized_context(item: object, data: dict[str, FindingDataValue]) -> None:
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
    if "relation" not in data:
        relation = _synthesized_relation(item)
        if relation:
            data["relation"] = relation


def _synthesized_site(item: object) -> str | None:
    sequence_name = getattr(item, "sequence_name", None)
    if isinstance(sequence_name, str) and sequence_name.strip():
        return f"SQ:{sequence_name.strip()}"
    site = getattr(item, "site", None)
    if isinstance(site, str) and site.strip():
        return site.strip()
    return None


def _synthesized_context(item: object) -> str | None:
    """The scope or location a finding belongs to."""
    explicit_context = getattr(item, "context", None)
    if isinstance(explicit_context, str) and explicit_context.strip():
        return explicit_context.strip()
    role = getattr(item, "role", None)
    if isinstance(role, str) and role.strip() and " " in role.strip():
        return role.strip()
    variable = getattr(item, "variable", None)
    variable_name = getattr(variable, "name", None)
    if isinstance(variable_name, str) and variable_name.strip():
        return variable_name.strip()
    return None


def _synthesized_relation(item: object) -> str | None:
    """The mapping relation a finding sits on, kept apart from its scope."""
    target = getattr(item, "target_display_name", None)
    source = getattr(item, "source_display_name", None)
    if isinstance(target, str) and target.strip() and isinstance(source, str) and source.strip():
        return f"{target.strip()} => {source.strip()}"
    return None


@dataclass(frozen=True, slots=True)
class _IssueLocation:
    """The source location an issue already carries, if any."""

    file: str | None = None
    line: int | None = None
    column: int | None = None
    end_line: int | None = None


def _data_text(data: Mapping[str, object], key: str) -> str | None:
    return optional_text(data.get(key))


def _data_int(data: Mapping[str, object], *keys: str) -> int | None:
    for key in keys:
        value = _positive_int(data.get(key))
        if value is not None:
            return value
    return None


def _literal_span_int(item: object, name: str) -> int | None:
    span = getattr(item, "literal_span", None)
    if span is None:
        return None
    return _positive_int(getattr(span, name, None))


def _issue_location(item: object) -> _IssueLocation:
    """Read the source location an issue carries, without inventing positions.

    Sources are the issue's ``data`` mapping (``file``/``path``,
    ``line``/``start_line``, ``column``/``start_col``, ``end_line``) and the
    ``literal_span`` a magic-number issue carries. A value the issue does not
    report stays ``None``.
    """
    data = _raw_issue_data(item) or {}
    file = _data_text(data, "file")
    if file is None:
        path_text = _data_text(data, "path")
        if path_text is not None and _looks_like_source_path(path_text):
            file = path_text
    line = _data_int(data, "line", "start_line")
    if line is None:
        line = _literal_span_int(item, "line")
    column = _data_int(data, "column", "start_col")
    if column is None:
        column = _literal_span_int(item, "column")
    end_line = _data_int(data, "end_line")
    return _IssueLocation(file=file, line=line, column=column, end_line=end_line)


#: Severity policy: this answers one CI question, whether a finding is certain
#: enough to fail a build. It is keyed by finding kind, never by analyzer
#: category, because one analyzer can report both defects and advice. ``error``
#: is reserved for defects the tool can prove from the parsed structure.
#: Uncertain heuristics and risky patterns are ``warning``. Naming, comment,
#: complexity, and design advice is ``info``. A kind that is not listed here
#: stays unknown at extraction time so the analyzer's delivery default applies.
_FINDING_SEVERITY: dict[str, Severity] = {
    # Proven defects.
    "dataflow.dead_overwrite": "error",
    "dataflow.conflicting_constants": "error",
    "sfc_parallel_write_race": "error",
    "sfc_unreachable_transition": "error",
    "sfc_duplicate_transition_guard": "error",
    "sfc_missing_initial_step": "error",
    "sfc_self_fork": "error",
    "sfc_cross_sequence_fork": "error",
    "string_capacity.literal_overflow": "error",
    "string_capacity.assignment_overflow": "error",
    "string_capacity.procedure_overflow": "error",
    "reset_contamination": "error",
    "icf.unresolved_path": "error",
    "icf.invalid_field_path": "error",
    # Risky patterns and uncertain heuristics.
    "unused": "warning",
    "field_read_only": "warning",
    "read_only_non_const": "warning",
    "procedure_status": "warning",
    "field_never_read": "warning",
    "never_read": "warning",
    "record_component_order_dependence": "warning",
    "write_without_effect": "warning",
    "unknown_parameter_target": "warning",
    "string_mapping_mismatch": "warning",
    "min_max_mapping_mismatch": "warning",
    "shadowing": "warning",
    "unsafe_boolean_default": "warning",
    "read_before_write": "warning",
    "implicit_latch": "warning",
    "secure_candidate": "warning",
    "alarm.duplicate_tag": "warning",
    "alarm.duplicate_condition": "warning",
    "alarm.never_cleared": "warning",
    "module_layout.invalid_clipping": "warning",
    "module_layout.origo_not_centered_or_corner": "warning",
    "module_layout.size_off_grid": "warning",
    "module_layout.position_off_grid": "warning",
    "module_layout.object_outside_clipping": "warning",
    "picture_display_paths.unresolved": "warning",
    "picture_display_paths.above_base": "warning",
    "module.version_drift": "warning",
    "module.unused_type": "warning",
    "same_cycle_parallel_read_write_hazard": "warning",
    "dataflow.condition_always_true": "warning",
    "dataflow.condition_always_false": "warning",
    "dataflow.unreachable_branch": "warning",
    "dataflow.self_compare_condition": "warning",
    "dataflow.scan_cycle_stale_read": "warning",
    "dataflow.scan_cycle_implicit_new": "warning",
    "dataflow.non_state_multi_site": "warning",
    "sfc_unreachable_sequence_node": "warning",
    "icf.program_mismatch": "warning",
    "icf.reference_case_mismatch": "warning",
    "icf.unit_tag_mismatch": "warning",
    "icf.group_tag_mismatch": "warning",
    "icf.missing_journal_field": "warning",
    "icf.unit_structure_drift": "warning",
    "icf.value_prefix_inconsistency": "warning",
    "icf.program_load_failed": "warning",
    "icf.issue": "warning",
    # Naming, comment, complexity, and design advice.
    "magic_number": "info",
    "comment_code": "info",
    "module.cyclomatic_complexity": "info",
    "step.cyclomatic_complexity": "info",
    "equation.cyclomatic_complexity": "info",
    "spec.sequence_step_prefix": "info",
    "spec.transition_name_missing": "info",
    "spec.transition_prefix": "info",
    "spec.sequence_name_prefix": "info",
    "spec.equation_block_prefix": "info",
    "string_style.narrower_datatype": "info",
    "string_style.generic_copy": "info",
    "unused_datatype": "info",
    "unused_datatype_field": "info",
    "datatype_duplication": "info",
    "global_scope_minimization": "info",
    "hidden_global_coupling": "info",
    "high_fan_in_out": "info",
}


def finding_severity(kind: str) -> Severity | None:
    """The curated severity for a finding kind, or ``None`` when it is unknown."""
    return _FINDING_SEVERITY.get(kind)


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
    visible_kinds = (
        {kind.value for kind in report.visible_kinds}
        if isinstance(report, VariablesReport) and report.visible_kinds is not None
        else None
    )
    for item in cast(list[object], issues):
        kind = _kind_value(item)
        if visible_kinds is not None and kind not in visible_kinds:
            continue
        module_path = _module_path_value(item)
        metadata = variable_issue_metadata(_kind_object(item))
        explanation = _issue_metadata_value(item, "explanation") or metadata.explanation
        suggestion = _issue_metadata_value(item, "suggestion") or metadata.suggestion
        location = _issue_location(item)
        findings.append(
            AnalysisFinding(
                kind=kind,
                message=_message_value(item),
                module_path=module_path or (default_name,),
                rule_id=_issue_metadata_value(item, "rule_id"),
                severity=finding_severity(kind),
                explanation=explanation,
                suggestion=suggestion,
                file=location.file,
                line=location.line,
                column=location.column,
                end_line=location.end_line,
                data=_issue_data_value(item),
            )
        )
    return tuple(findings)


def _kind_object(item: object) -> IssueKind | str | None:
    """The raw issue kind of a heterogeneous report model, if it carries one."""
    kind = getattr(item, "kind", None)
    if isinstance(kind, IssueKind | str):
        return kind
    return None


_KIND_HUMAN_LABELS: dict[str, str] = {
    "magic_number": "Magic number",
    "unused": "Unused variable",
    "unused_datatype": "Unused datatype",
    "unused_datatype_field": "Unused datatype field",
    "field_read_only": "Field read only",
    "read_only_non_const": "Read-only non-const",
    "never_read": "Never read",
    "write_without_effect": "Write without effect",
    "implicit_latch": "Implicit latch",
    "reset_contamination": "Reset contamination",
    "secure_candidate": "Secure candidate",
    "global_scope_minimization": "Global scope minimization",
    "hidden_global_coupling": "Hidden global coupling",
    "high_fan_in_out": "High fan-in/out",
    "datatype_duplication": "Extractable nested record",
    "min_max_mapping_mismatch": "Min/Max mapping mismatch",
    "unknown_parameter_target": "Unknown parameter target",
    "string_mapping_mismatch": "String mapping mismatch",
    "string_capacity.literal_overflow": "String literal overflow",
    "string_capacity.assignment_overflow": "String assignment overflow",
    "string_capacity.procedure_overflow": "String procedure overflow",
    "string_style.narrower_datatype": "String datatype wider than needed",
    "string_style.generic_copy": "Generic variable copy on strings",
    "procedure_status": "Procedure status",
    "shadowing": "Variable shadowing",
    "record_component_order_dependence": "Record component order dependence",
    "sfc_parallel_write_race": "Parallel write race",
    "sfc_unreachable_transition": "Unreachable transition",
    "sfc_duplicate_transition_guard": "Duplicate transition guard",
    "dataflow.dead_overwrite": "Dead overwrite",
    "dataflow.conflicting_constants": "Conflicting constants",
    "dataflow.condition_always_true": "Condition always true",
    "dataflow.condition_always_false": "Condition always false",
    "dataflow.unreachable_branch": "Unreachable branch",
    "dataflow.self_compare_condition": "Self-compare condition",
    "dataflow.scan_cycle_stale_read": "Stale :OLD read",
    "dataflow.scan_cycle_implicit_new": "Implicit :NEW read",
    "read_before_write": "Read before write",
    "module.version_drift": "Version drift",
    "module.unused_type": "Unused module type",
    "module.cyclomatic_complexity": "High cyclomatic complexity",
    "module_layout.invalid_clipping": "Invalid clipping bounds",
    "module_layout.origo_not_centered_or_corner": "Module origin not centered or at the bottom-left",
    "module_layout.size_off_grid": "Module size off grid",
    "module_layout.position_off_grid": "Module placement off grid",
    "module_layout.object_outside_clipping": "Object outside clipping bounds",
    "step.cyclomatic_complexity": "High step complexity",
    "equation.cyclomatic_complexity": "High equation block complexity",
    "alarm.duplicate_tag": "Duplicate alarm tag",
    "alarm.duplicate_condition": "Duplicate alarm condition",
    "alarm.never_cleared": "Alarm never cleared",
    "comment_code": "Commented-out code",
    "spec.sequence_step_prefix": "Sequence step prefix",
    "spec.transition_name_missing": "Transition name missing",
    "spec.transition_prefix": "Transition prefix",
    "spec.sequence_name_prefix": "Sequence name prefix",
    "spec.equation_block_prefix": "Equation block name prefix",
    "unsafe_boolean_default": "Unsafe boolean default",
    "sfc_missing_initial_step": "Missing initial step at sequence start",
    "sfc_unreachable_sequence_node": "Unreachable sequence node",
    "sfc_self_fork": "Self fork",
    "sfc_cross_sequence_fork": "Cross-sequence fork",
    "same_cycle_parallel_read_write_hazard": "Parallel read/write hazard",
    "dataflow.non_state_multi_site": "Non-State multi-site write",
    "picture_display_paths.unresolved": "Unresolved PictureDisplay path",
    "picture_display_paths.above_base": "PictureDisplay path above base picture",
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


__all__ = [
    "AnalysisFinding",
    "Severity",
    "extract_report_findings",
    "finding_data_key",
    "finding_severity",
    "format_source_location",
    "kind_human_label",
]
