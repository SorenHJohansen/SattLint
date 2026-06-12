"""Finding validation feedback loop helpers."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sattlint.contracts import FindingCollection

from .artifact_registry import ACCURACY_METRICS_FILENAME, ACCURACY_SCHEMA_KIND, ACCURACY_SCHEMA_VERSION

VALIDATION_ANNOTATIONS_FILENAME = "finding_validation_annotations.json"


def _empty_validation_annotations() -> list[ValidationAnnotation]:
    return []


@dataclass
class ValidationAnnotation:
    finding_fingerprint: str
    annotation: str  # "correct", "false_positive", "missed_issue"
    rule_id: str | None = None
    annotated_by: str | None = None
    note: str | None = None


@dataclass
class AccuracyMetrics:
    annotations: list[ValidationAnnotation] = field(default_factory=_empty_validation_annotations)

    def to_dict(self) -> dict[str, Any]:
        total = len(self.annotations)
        by_annotation: Counter[str] = Counter(a.annotation for a in self.annotations)
        by_rule: dict[str, dict[str, int]] = {}
        for a in self.annotations:
            rule = a.rule_id or "unknown"
            by_rule.setdefault(rule, {"correct": 0, "false_positive": 0, "missed_issue": 0})
            by_rule[rule][a.annotation] = by_rule[rule].get(a.annotation, 0) + 1

        return {
            "kind": ACCURACY_SCHEMA_KIND,
            "schema_version": ACCURACY_SCHEMA_VERSION,
            "summary": {
                "total_annotations": total,
                "correct": by_annotation.get("correct", 0),
                "false_positives": by_annotation.get("false_positive", 0),
                "missed_issues": by_annotation.get("missed_issue", 0),
                "precision": round(by_annotation.get("correct", 0) / total, 4) if total > 0 else None,
            },
            "by_rule": by_rule,
            "annotations": [
                {
                    "finding_fingerprint": a.finding_fingerprint,
                    "annotation": a.annotation,
                    "rule_id": a.rule_id,
                    "annotated_by": a.annotated_by,
                    "note": a.note,
                }
                for a in self.annotations
            ],
        }


def load_annotations(path: Path) -> list[ValidationAnnotation]:
    """Load validation annotations from a JSON file."""
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    annotations: list[ValidationAnnotation] = []
    for item in payload.get("annotations", []):
        annotations.append(
            ValidationAnnotation(
                finding_fingerprint=item.get("finding_fingerprint", ""),
                annotation=item.get("annotation", "correct"),
                rule_id=item.get("rule_id"),
                annotated_by=item.get("annotated_by"),
                note=item.get("note"),
            )
        )
    return annotations


def build_accuracy_metrics(
    finding_collection: FindingCollection,
    annotations: list[ValidationAnnotation],
) -> AccuracyMetrics:
    """Build accuracy metrics from findings and annotations."""
    metrics = AccuracyMetrics()
    annotation_by_fingerprint: dict[str, ValidationAnnotation] = {a.finding_fingerprint: a for a in annotations}

    for finding in finding_collection.findings:
        fp = finding.fingerprint or ""
        if fp in annotation_by_fingerprint:
            metrics.annotations.append(annotation_by_fingerprint[fp])
        else:
            default_annotation = "correct" if finding.severity not in ("high", "critical") else "missed_issue"
            metrics.annotations.append(
                ValidationAnnotation(
                    finding_fingerprint=fp,
                    annotation=default_annotation,
                    rule_id=finding.rule_id,
                )
            )

    return metrics


def write_accuracy_metrics(output_dir: Path, metrics: AccuracyMetrics) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / ACCURACY_METRICS_FILENAME
    output_path.write_text(json.dumps(metrics.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return output_path


__all__ = [
    "ACCURACY_METRICS_FILENAME",
    "ACCURACY_SCHEMA_KIND",
    "ACCURACY_SCHEMA_VERSION",
    "VALIDATION_ANNOTATIONS_FILENAME",
    "AccuracyMetrics",
    "ValidationAnnotation",
    "build_accuracy_metrics",
    "load_annotations",
    "write_accuracy_metrics",
]
