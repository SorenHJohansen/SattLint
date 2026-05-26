"""Production code analysis helpers for real SattLine repositories."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sattlint.contracts import FindingCollection
from sattlint.core.workspace_discovery import discover_workspace_sources

PRODUCTION_SUMMARY_FILENAME = "production_summary.json"
PRODUCTION_SCHEMA_KIND = "sattlint.production_summary"
PRODUCTION_SCHEMA_VERSION = 1

# Allowlist of known public SattLine repository name patterns
KNOWN_REPO_PATTERNS = (
    "sattline",
    "sattline-lib",
    "sattline-examples",
    "sattline-templates",
)


def _empty_counts() -> dict[str, int]:
    return {}


def _empty_strings() -> list[str]:
    return []


@dataclass
class ProductionSummary:
    repo_name: str
    findings_per_kloc: float
    rule_frequency: dict[str, int] = field(default_factory=_empty_counts)
    ignored_vs_fixed: dict[str, int] = field(default_factory=_empty_counts)
    path_redactions: list[str] = field(default_factory=_empty_strings)
    trend_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": PRODUCTION_SCHEMA_KIND,
            "schema_version": PRODUCTION_SCHEMA_VERSION,
            "repo_name": self.repo_name,
            "summary": {
                "findings_per_kloc": self.findings_per_kloc,
                "rule_frequency": dict(self.rule_frequency),
                "ignored_vs_fixed": dict(self.ignored_vs_fixed),
                "path_redaction_count": len(self.path_redactions),
                "trend_available": self.trend_available,
            },
            "rule_frequency": dict(self.rule_frequency),
            "path_redactions": self.path_redactions,
        }


def _compute_kloc(source_files: list[Path]) -> int:
    """Compute thousands of lines of SattLine code."""
    total_lines = 0
    for path in source_files:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            total_lines += len(text.splitlines())
        except OSError:
            continue
    return max(total_lines // 1000, 1)


def build_production_summary(
    repo_root: Path,
    finding_collection: FindingCollection,
    *,
    repo_name: str | None = None,
    allowlist_patterns: tuple[str, ...] = KNOWN_REPO_PATTERNS,
) -> ProductionSummary | None:
    """Build production summary for a real SattLine repository."""
    resolved_root = Path(repo_root).resolve()
    detected_name = resolved_root.name.casefold()
    if not any(pattern in detected_name for pattern in allowlist_patterns):
        return None

    name = repo_name or detected_name

    discovery = discover_workspace_sources(resolved_root)
    source_files = [*discovery.program_files, *discovery.dependency_files]

    kloc = _compute_kloc(source_files)
    findings = finding_collection.findings
    findings_per_kloc = round(len(findings) / kloc, 2)

    freq: Counter[str] = Counter()
    for f in findings:
        freq[f.rule_id or "unknown"] += 1

    ignored = sum(1 for f in findings if "ignored" in (f.fingerprint or "").casefold())
    fixed = sum(1 for f in findings if "fixed" in (f.fingerprint or "").casefold())

    return ProductionSummary(
        repo_name=name,
        findings_per_kloc=findings_per_kloc,
        rule_frequency=dict(freq),
        ignored_vs_fixed={"ignored": ignored, "fixed": fixed},
        path_redactions=[],
        trend_available=False,
    )


__all__ = [
    "PRODUCTION_SUMMARY_FILENAME",
    "ProductionSummary",
    "build_production_summary",
]
