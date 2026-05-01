"""Shared machine-readable finding contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

FINDING_SCHEMA_KIND = "sattlint.findings"
FINDING_SCHEMA_VERSION = 1

_COMMAND_PREFIXES = (
    "python ",
    "pyright ",
    "ruff ",
    "sattlint ",
    "sattlint-repo-audit ",
)
_OWNER_SURFACE_BY_ANALYZER = {
    "architecture": "architecture",
    "bandit": "security",
    "mypy": "python-types",
    "pyright": "python-types",
    "pytest": "python-tests",
    "repo-audit": "repo-audit",
    "ruff": "python-style",
    "sattline-semantics": "semantic",
    "syntax-check": "syntax-check",
    "vulture": "dead-code",
}


@dataclass(frozen=True, slots=True)
class FindingLocation:
    path: str | None = None
    line: int | None = None
    column: int | None = None
    symbol: str | None = None
    module_path: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "symbol": self.symbol,
            "module_path": list(self.module_path),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> FindingLocation:
        payload = payload or {}
        return cls(
            path=_coerce_str(payload.get("path") or payload.get("file")),
            line=_coerce_int(payload.get("line")),
            column=_coerce_int(payload.get("column")),
            symbol=_coerce_str(payload.get("symbol")),
            module_path=_coerce_module_path(payload.get("module_path")),
        )


@dataclass(frozen=True, slots=True)
class FindingRecord:
    id: str
    rule_id: str
    category: str
    severity: str
    confidence: str
    message: str
    source: str
    analyzer: str | None = None
    artifact: str | None = None
    location: FindingLocation = field(default_factory=FindingLocation)
    fingerprint: str | None = None
    detail: str | None = None
    suggestion: str | None = None
    owner_surface: str | None = None
    minimal_reproducer: str | None = None
    suggested_next_command: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.fingerprint is None:
            object.__setattr__(self, "fingerprint", self._default_fingerprint())
        if self.owner_surface is None:
            object.__setattr__(self, "owner_surface", self._default_owner_surface())
        if self.minimal_reproducer is None:
            object.__setattr__(self, "minimal_reproducer", self._default_minimal_reproducer())
        if self.suggested_next_command is None:
            object.__setattr__(self, "suggested_next_command", self._default_suggested_next_command())

    def _default_fingerprint(self) -> str:
        parts = [
            self.rule_id,
            self.location.path or "",
            str(self.location.line or ""),
            self.location.symbol or "",
            self.message,
        ]
        return "|".join(parts)

    def _default_owner_surface(self) -> str | None:
        explicit = _coerce_str(self.data.get("owner_surface"))
        if explicit:
            return explicit
        analyzer = (self.analyzer or "").casefold()
        mapped_surface = _OWNER_SURFACE_BY_ANALYZER.get(analyzer)
        if mapped_surface:
            if analyzer == "repo-audit" and self.source and self.source != "custom":
                return self.source
            return mapped_surface
        source = (self.source or "").casefold()
        mapped_surface = _OWNER_SURFACE_BY_ANALYZER.get(source)
        if mapped_surface:
            return mapped_surface
        category = _coerce_str(self.category)
        if category and category != "unknown":
            return category
        return None

    def _default_minimal_reproducer(self) -> str | None:
        explicit = _coerce_str(self.data.get("minimal_reproducer"))
        if explicit:
            return explicit
        analyzer = (self.analyzer or "").casefold()
        source = (self.source or "").casefold()
        tool = analyzer or source
        path = self.location.path
        nodeid = _coerce_str(self.data.get("nodeid"))
        if tool == "ruff":
            return f"ruff check {path}" if path else "ruff check src tests"
        if tool in {"mypy", "pyright"}:
            return f"{tool} {path}" if path else f"{tool} src tests"
        if tool == "pytest":
            if nodeid:
                return f"python -m pytest {nodeid} -x -q --tb=short"
            if path:
                return f"python -m pytest {path} -x -q --tb=short"
            return "python -m pytest -x -q --tb=short"
        if tool == "syntax-check":
            return f"sattlint syntax-check {path}" if path else None
        if tool == "repo-audit":
            if self.source and self.source not in {"", "custom", "pipeline"}:
                return (
                    "sattlint-repo-audit --profile full --check "
                    f"{self.source} --skip-pipeline --output-dir artifacts/audit"
                )
            return "sattlint-repo-audit --profile full --output-dir artifacts/audit"
        return None

    def _default_suggested_next_command(self) -> str | None:
        explicit = _coerce_str(self.data.get("suggested_next_command"))
        if explicit:
            return explicit
        suggestion = _coerce_str(self.suggestion)
        if suggestion and suggestion.lstrip().startswith(_COMMAND_PREFIXES):
            return suggestion.strip()
        return self.minimal_reproducer

    @property
    def file(self) -> str | None:
        return self.location.path

    @property
    def line(self) -> int | None:
        return self.location.line

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "confidence": self.confidence,
            "message": self.message,
            "source": self.source,
            "analyzer": self.analyzer,
            "artifact": self.artifact,
            "file": self.location.path,
            "line": self.location.line,
            "location": self.location.to_dict(),
            "fingerprint": self.fingerprint,
            "detail": self.detail,
            "suggestion": self.suggestion,
            "owner_surface": self.owner_surface,
            "minimal_reproducer": self.minimal_reproducer,
            "suggested_next_command": self.suggested_next_command,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FindingRecord:
        location_payload = payload.get("location")
        location = FindingLocation.from_mapping(location_payload if isinstance(location_payload, Mapping) else payload)
        rule_id = _coerce_str(payload.get("rule_id") or payload.get("id")) or "unknown"
        return cls(
            id=_coerce_str(payload.get("id")) or rule_id,
            rule_id=rule_id,
            category=_coerce_str(payload.get("category")) or "unknown",
            severity=_coerce_str(payload.get("severity")) or "unknown",
            confidence=_coerce_str(payload.get("confidence")) or "unknown",
            message=_coerce_str(payload.get("message")) or "",
            source=_coerce_str(payload.get("source")) or "unknown",
            analyzer=_coerce_str(payload.get("analyzer")),
            artifact=_coerce_str(payload.get("artifact")),
            location=location,
            fingerprint=_coerce_str(payload.get("fingerprint")),
            detail=_coerce_str(payload.get("detail")),
            suggestion=_coerce_str(payload.get("suggestion")),
            owner_surface=_coerce_str(payload.get("owner_surface")),
            minimal_reproducer=_coerce_str(payload.get("minimal_reproducer")),
            suggested_next_command=_coerce_str(payload.get("suggested_next_command")),
            data=dict(payload.get("data") or {}),
        )

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        source: str,
        analyzer: str | None = None,
        artifact: str | None = None,
    ) -> FindingRecord:
        location_payload = payload.get("location")
        location = FindingLocation.from_mapping(location_payload if isinstance(location_payload, Mapping) else payload)
        rule_id = _coerce_str(payload.get("rule_id") or payload.get("id")) or "unknown"
        return cls(
            id=_coerce_str(payload.get("id")) or rule_id,
            rule_id=rule_id,
            category=_coerce_str(payload.get("category")) or "unknown",
            severity=_coerce_str(payload.get("severity")) or "unknown",
            confidence=_coerce_str(payload.get("confidence")) or "unknown",
            message=_coerce_str(payload.get("message")) or "",
            source=source,
            analyzer=analyzer,
            artifact=artifact,
            location=location,
            detail=_coerce_str(payload.get("detail")),
            suggestion=_coerce_str(payload.get("suggestion")),
            owner_surface=_coerce_str(payload.get("owner_surface")),
            minimal_reproducer=_coerce_str(payload.get("minimal_reproducer")),
            suggested_next_command=_coerce_str(payload.get("suggested_next_command")),
            data=dict(payload.get("data") or {}),
        )


@dataclass(frozen=True, slots=True)
class FindingCollection:
    findings: tuple[FindingRecord, ...]
    schema_kind: str = FINDING_SCHEMA_KIND
    schema_version: int = FINDING_SCHEMA_VERSION

    @property
    def schema_metadata(self) -> dict[str, Any]:
        return {
            "kind": self.schema_kind,
            "schema_version": self.schema_version,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.schema_kind,
            "schema_version": self.schema_version,
            "finding_count": len(self.findings),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FindingCollection:
        findings_payload = payload.get("findings") or []
        return cls(
            findings=tuple(FindingRecord.from_dict(item) for item in findings_payload),
            schema_kind=_coerce_str(payload.get("kind")) or FINDING_SCHEMA_KIND,
            schema_version=_coerce_int(payload.get("schema_version")) or FINDING_SCHEMA_VERSION,
        )


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_module_path(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return (str(value),)
