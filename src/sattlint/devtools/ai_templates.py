"""AI task template helpers for documentation and automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sattlint.analyzers.registry import get_default_analyzer_catalog
from sattlint.contracts import FindingCollection

from .artifact_registry import AI_TEMPLATE_SCHEMA_KIND, AI_TEMPLATE_SCHEMA_VERSION, AI_TEMPLATE_SUMMARY_FILENAME


def _empty_strings() -> list[str]:
    return []


def _empty_templates() -> list[TaskTemplate]:
    return []


@dataclass
class TaskTemplate:
    template_id: str
    description: str
    prompt: str
    example_findings: list[str] = field(default_factory=_empty_strings)
    related_rules: list[str] = field(default_factory=_empty_strings)


@dataclass
class AITemplateSummary:
    templates: list[TaskTemplate] = field(default_factory=_empty_templates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": AI_TEMPLATE_SCHEMA_KIND,
            "schema_version": AI_TEMPLATE_SCHEMA_VERSION,
            "summary": {
                "template_count": len(self.templates),
                "rules_covered": len({rule for t in self.templates for rule in t.related_rules}),
            },
            "templates": [
                {
                    "template_id": t.template_id,
                    "description": t.description,
                    "prompt": t.prompt,
                    "example_findings": list(t.example_findings),
                    "related_rules": list(t.related_rules),
                }
                for t in self.templates
            ],
        }


def build_ai_task_templates(
    finding_collection: FindingCollection | None = None,
) -> AITemplateSummary:
    """Build reusable AI task templates from analyzer registry and findings."""
    catalog = get_default_analyzer_catalog()
    summary = AITemplateSummary()

    # Template: Analyzer coverage review
    summary.templates.append(
        TaskTemplate(
            template_id="analyzer-coverage-review",
            description="Review analyzer coverage for a SattLine workspace",
            prompt=(
                "Review the following findings from a SattLine workspace. "
                "For each analyzer, summarize what was checked, "
                "identify any gaps in coverage, and suggest additional checks that could be added."
            ),
            related_rules=[r.id for r in catalog.rules],
        )
    )

    # Template: False-positive triage
    summary.templates.append(
        TaskTemplate(
            template_id="false-positive-triage",
            description="Triage potential false-positive findings",
            prompt=(
                "Review each finding below. For each one, decide if it is a true issue, "
                "a false positive, or a limitation of the current analyzer. "
                "If false positive, explain why and suggest suppression or rule improvement."
            ),
            example_findings=(
                [f.fingerprint for f in finding_collection.findings[:5] if f.fingerprint] if finding_collection else []
            ),
        )
    )

    # Template: Migration safety check
    summary.templates.append(
        TaskTemplate(
            template_id="migration-safety-check",
            description="Check safety of a SattLine program migration or refactor",
            prompt=(
                "Analyze the changes between two versions of a SattLine program. "
                "Focus on safety-critical paths, alarm integrity, "
                "and semantic contract changes. Report any increased risk."
            ),
            related_rules=[r.id for r in catalog.rules if "safety" in r.id or "alarm" in r.id],
        )
    )

    return summary


__all__ = [
    "AI_TEMPLATE_SUMMARY_FILENAME",
    "AITemplateSummary",
    "TaskTemplate",
    "build_ai_task_templates",
]
