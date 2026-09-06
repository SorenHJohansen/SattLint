"""Structured analyzer findings for the checks pipeline.

Analyzer reports expose heterogeneous ``issues`` shapes (framework ``Issue``,
``VariableIssue``, semantic rules, etc.). This module normalizes them into a
single typed, serializable :class:`AnalysisFinding` so the TUI tree, run
history, and CLI JSON output all consume one consistent shape.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast


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
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> AnalysisFinding:
        raw_module_path = cast(list[object] | tuple[object, ...] | None, payload.get("module_path"))
        module_path = tuple(str(segment) for segment in (raw_module_path or ()))
        return cls(
            kind=str(payload.get("kind") or ""),
            message=str(payload.get("message") or ""),
            module_path=module_path,
            severity=_optional_str(payload.get("severity")),
            confidence=_optional_str(payload.get("confidence")),
            rule_id=_optional_str(payload.get("rule_id")),
            explanation=_optional_str(payload.get("explanation")),
            suggestion=_optional_str(payload.get("suggestion")),
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
        findings.append(
            AnalysisFinding(
                kind=_kind_value(item),
                message=_message_value(item),
                module_path=module_path or (default_name,),
                severity=_issue_metadata_value(item, "severity"),
                confidence=_issue_metadata_value(item, "confidence"),
                rule_id=_issue_metadata_value(item, "rule_id"),
                explanation=_issue_metadata_value(item, "explanation"),
                suggestion=_issue_metadata_value(item, "suggestion"),
            )
        )
    return tuple(findings)


__all__ = ["AnalysisFinding", "extract_report_findings"]
