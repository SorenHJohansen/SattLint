"""Analyzer reference documentation generator with example fixtures.

Generates machine-readable and rendered analyzer reference documentation
with example fixtures and expected findings.
"""

from __future__ import annotations

import json
import pathlib
import typing as t

from ..analyzers.framework import AnalyzerSpec
from ..analyzers.registry import AnalyzerCatalog, get_default_analyzer_catalog
from ..repo_paths import repo_root_from

if t.TYPE_CHECKING:
    pass

REPO_ROOT = repo_root_from(pathlib.Path(__file__))
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SAMPLE_FILES_DIR = FIXTURES_DIR / "sample_sattline_files"
CORPUS_DIR = FIXTURES_DIR / "corpus"


_ANALYZER_EXAMPLE_FIXTURES: dict[str, list[dict[str, t.Any]]] = {
    "variables": [
        {
            "fixture": "sample_sattline_files/CommonQualityIssues.s",
            "description": "Variable lifecycle issues including unused and read-only variables",
            "expected_rule_ids": ["semantic.unused-variable", "semantic.read-only-non-const"],
        },
    ],
    "sfc": [
        {
            "fixture": "corpus/valid/SequenceBasic.s",
            "description": "Basic SFC sequence structure",
            "expected_rule_ids": [],
        },
        {
            "fixture": "corpus/semantic/ParallelWriteRace.s",
            "description": "Parallel branches writing to same variable",
            "expected_rule_ids": ["semantic.parallel-write-race"],
        },
    ],
    "shadowing": [
        {
            "fixture": "corpus/semantic/ShadowingVariable.s",
            "description": "Local variables shadowing outer scope",
            "expected_rule_ids": ["semantic.shadowing"],
        },
    ],
    "spec-compliance": [
        {
            "fixture": "sample_sattline_files/CommonQualityIssues.s",
            "description": "Engineering spec compliance issues",
            "expected_rule_ids": ["semantic.naming-role-mismatch"],
        },
    ],
    "dataflow": [
        {
            "fixture": "corpus/semantic/NeverReadVariable.s",
            "description": "Variables written but never read",
            "expected_rule_ids": ["semantic.never-read-write"],
        },
        {
            "fixture": "corpus/semantic/ReadBeforeWrite.s",
            "description": "Variables read before being written",
            "expected_rule_ids": ["semantic.read-before-write"],
        },
    ],
    "signal-lifecycle": [
        {
            "fixture": "corpus/semantic/SignalLifecycle.s",
            "description": "Signals consumed before a definite write and writes that are never consumed",
            "expected_rule_ids": [
                "semantic.signal-lifecycle-read-before-write",
                "semantic.signal-lifecycle-unconsumed-write",
            ],
        },
    ],
    "loop-stability": [
        {
            "fixture": "corpus/semantic/LoopStability.s",
            "description": "Conflicting literal setpoint assignments in the same control scope",
            "expected_rule_ids": ["semantic.loop-conflicting-setpoint"],
        },
    ],
    "fault-handling": [
        {
            "fixture": "corpus/semantic/FaultHandling.s",
            "description": "Fault paths that are raised without clear recovery or handling logic",
            "expected_rule_ids": ["semantic.fault-missing-recovery", "semantic.fault-unhandled-path"],
        },
    ],
    "numeric-constraints": [
        {
            "fixture": "corpus/semantic/NumericConstraints.s",
            "description": "Assignments that exceed visible Min_/Max_ bounds",
            "expected_rule_ids": ["semantic.numeric-limit-violation"],
        },
    ],
    "config-drift": [
        {
            "fixture": "corpus/semantic/ConfigDrift.s",
            "description": "Instances of the same moduletype drifting on mapped parameter values",
            "expected_rule_ids": ["semantic.instance-configuration-drift"],
        },
    ],
    "safety-paths": [
        {
            "fixture": "sample_sattline_files/CommonQualityIssues.s",
            "description": "Safety signal propagation paths",
            "expected_rule_ids": [],
        },
    ],
    "taint-paths": [
        {
            "fixture": "sample_sattline_files/CommonQualityIssues.s",
            "description": "Taint propagation from external inputs to safety sinks",
            "expected_rule_ids": [],
        },
    ],
}


def get_example_fixtures_for_analyzer(analyzer_key: str) -> list[dict[str, t.Any]]:
    return list(_ANALYZER_EXAMPLE_FIXTURES.get(analyzer_key, []))


def resolve_fixture_path(fixture_path: str) -> pathlib.Path:
    return FIXTURES_DIR / fixture_path


def build_analyzer_reference_entry(
    analyzer: AnalyzerSpec,
    catalog: AnalyzerCatalog | None = None,
) -> dict[str, t.Any]:
    if catalog is None:
        catalog = get_default_analyzer_catalog()

    analyzer_meta = next((a for a in catalog.analyzers if a.spec.key == analyzer.key), None)
    if analyzer_meta is None:
        return {"key": analyzer.key, "error": "Analyzer not found in catalog"}

    rules = [rule for rule in catalog.rules if analyzer.key in rule.analyzers]
    examples = get_example_fixtures_for_analyzer(analyzer.key)

    return {
        "key": analyzer.key,
        "name": analyzer.name,
        "description": analyzer.description,
        "enabled": analyzer.enabled,
        "supports_live_diagnostics": analyzer.supports_live_diagnostics,
        "delivery": analyzer_meta.delivery.to_dict() if analyzer_meta else {},
        "rules": [rule.to_dict() for rule in rules],
        "examples": examples,
        "example_count": len(examples),
    }


def build_full_analyzer_reference(
    catalog: AnalyzerCatalog | None = None,
) -> dict[str, t.Any]:
    if catalog is None:
        catalog = get_default_analyzer_catalog()

    return {
        "generated_by": "sattlint-analyzer-ref",
        "schema_version": 1,
        "analyzers": [build_analyzer_reference_entry(spec, catalog) for spec in catalog.enabled_specs()],
        "total_analyzers": len(catalog.analyzers),
        "total_rules": len(catalog.rules),
    }


def render_analyzer_reference_markdown(
    reference: dict[str, t.Any] | None = None,
) -> str:
    if reference is None:
        reference = build_full_analyzer_reference()

    lines: list[str] = []
    lines.append("# SattLint Analyzer Reference")
    lines.append("")
    lines.append(f"Generated by: {reference.get('generated_by', 'unknown')}")
    lines.append(f"Schema version: {reference.get('schema_version', 1)}")
    lines.append(f"Total analyzers: {reference.get('total_analyzers', 0)}")
    lines.append(f"Total rules: {reference.get('total_rules', 0)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for analyzer in reference.get("analyzers", []):
        lines.append(f"## {analyzer['name']} (`{analyzer['key']}`)")
        lines.append("")
        lines.append(f"**Description:** {analyzer['description']}")
        lines.append(f"**Enabled:** {analyzer['enabled']}")
        lines.append(f"**Live diagnostics:** {analyzer['supports_live_diagnostics']}")
        lines.append("")

        delivery = analyzer.get("delivery", {})
        if delivery:
            lines.append("### Delivery Metadata")
            lines.append("")
            lines.append(f"- **Scope:** {delivery.get('scope', 'unknown')}")
            lines.append(f"- **Bucket:** {delivery.get('implementation_bucket', 'unknown')}")
            lines.append(f"- **CLI exposed:** {delivery.get('cli_exposed', False)}")
            lines.append(f"- **LSP exposed:** {delivery.get('lsp_exposed', False)}")
            lines.append(f"- **Supports incremental:** {delivery.get('supports_incremental', False)}")
            lines.append("")

        rules = analyzer.get("rules", [])
        if rules:
            lines.append("### Rules")
            lines.append("")
            lines.append("| Rule ID | Category | Severity | Confidence |")
            lines.append("|---------|----------|----------|------------|")
            for rule in rules:
                lines.append(
                    f"| `{rule['id']}` | {rule.get('category', 'unknown')} | "
                    f"{rule.get('severity', 'unknown')} | {rule.get('confidence', 'unknown')} |"
                )
            lines.append("")

        examples = analyzer.get("examples", [])
        if examples:
            lines.append("### Examples")
            lines.append("")
            for i, example in enumerate(examples, 1):
                fixture_path = example.get("fixture", "unknown")
                lines.append(f"#### Example {i}: {example.get('description', fixture_path)}")
                lines.append("")
                lines.append(f"**Fixture:** `{fixture_path}`")
                expected_rules = example.get("expected_rule_ids", [])
                if expected_rules:
                    lines.append(f"**Expected rules:** {', '.join(f'`{r}`' for r in expected_rules)}")
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def save_analyzer_reference_json(
    output_path: str | pathlib.Path,
    catalog: AnalyzerCatalog | None = None,
) -> None:
    reference = build_full_analyzer_reference(catalog)
    path = pathlib.Path(output_path)
    path.write_text(json.dumps(reference, indent=2, default=str), encoding="utf-8")


def save_analyzer_reference_markdown(
    output_path: str | pathlib.Path,
    reference: dict[str, t.Any] | None = None,
) -> None:
    if reference is None:
        reference = build_full_analyzer_reference()
    markdown = render_analyzer_reference_markdown(reference)
    path = pathlib.Path(output_path)
    path.write_text(markdown, encoding="utf-8")
