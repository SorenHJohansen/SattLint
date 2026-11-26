"""String capacity and string style analyzers.

The capacity analyzer reports values and procedure writes that exceed a
declared string capacity. The style analyzer suggests a narrower datatype when
every observed value fits, and names the string-specific copy procedure when a
generic copy is used between strings. Both are opt-in: a project selects the
analyzer key it wants.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sattlint.parser_api import BasePicture

from ...config.string_capacities import StringCapacities
from ...resolution import TypeGraph
from ..framework import Issue, SimpleReport
from ..string_inference import ExactStringInferenceEngine
from ._checks import (
    collect_copy_findings,
    collect_declarations,
    collect_literal_findings,
    collect_rightsizing_findings,
)
from ._literal_flow import analyze_literal_flow
from ._model import OverflowFact, SlotTypes, StringUsageFinding, dedupe_findings

if TYPE_CHECKING:
    from ...models.project_graph import ProjectGraph

__all__ = ["analyze_string_capacity", "analyze_string_style"]


def _types(base_picture: BasePicture, capacities: StringCapacities) -> SlotTypes:
    return SlotTypes(capacities=capacities, type_graph=TypeGraph.from_basepicture(base_picture))


def _engine(
    base_picture: BasePicture,
    *,
    capacities: StringCapacities,
    graph: ProjectGraph | None,
) -> ExactStringInferenceEngine:
    return ExactStringInferenceEngine(base_picture, capacities=capacities, graph=graph)


def analyze_string_capacity(
    base_picture: BasePicture,
    *,
    string_capacities: StringCapacities,
    graph: ProjectGraph | None = None,
) -> SimpleReport:
    types = _types(base_picture, string_capacities)
    engine = _engine(base_picture, capacities=string_capacities, graph=graph)
    contexts = engine.module_contexts()
    flow = analyze_literal_flow(contexts, types=types)
    findings = [
        *collect_literal_findings(contexts, types=types),
        *[_overflow_finding(fact) for fact in flow.facts],
    ]
    return _report(base_picture, findings)


def analyze_string_style(
    base_picture: BasePicture,
    *,
    string_capacities: StringCapacities,
    graph: ProjectGraph | None = None,
) -> SimpleReport:
    types = _types(base_picture, string_capacities)
    engine = _engine(base_picture, capacities=string_capacities, graph=graph)
    contexts = engine.module_contexts()
    declarations = collect_declarations(contexts, types=types)
    flow = analyze_literal_flow(contexts, types=types)
    findings = [
        *collect_copy_findings(engine.execution_contexts(), types=types),
        *collect_rightsizing_findings(
            contexts,
            types=types,
            declarations=declarations,
            flow=flow,
        ),
    ]
    return _report(base_picture, findings)


def _overflow_finding(fact: OverflowFact) -> StringUsageFinding:
    source_text = f" from '{fact.source}'" if fact.source else ""
    if fact.operation == "Assignment":
        kind = "string_capacity.assignment_overflow"
        explanation = "The source string is longer than the target can hold, so the stored value loses characters."
        suggestion = "Shorten the source, or use a larger string datatype for the target."
    else:
        kind = "string_capacity.procedure_overflow"
        explanation = (
            "The procedure writes more characters than the target can hold, so the stored result is truncated."
        )
        suggestion = "Shorten an input, move the cursor, or use a larger string datatype for the target."
    return StringUsageFinding(
        kind=kind,
        message=(
            f"{fact.operation} can write {fact.length} characters into '{fact.target}'{source_text}, "
            f"but its capacity is {fact.capacity}."
        ),
        module_path=fact.module_path,
        site=fact.site,
        details=(
            ("operation", fact.operation),
            ("target", fact.target),
            ("source", fact.source),
            ("capacity", fact.capacity),
            ("length", fact.length),
            ("site", fact.site),
        ),
        explanation=explanation,
        suggestion=suggestion,
    )


def _report(
    base_picture: BasePicture,
    findings: list[StringUsageFinding],
) -> SimpleReport:
    issues = [
        Issue(
            kind=finding.kind,
            message=finding.message,
            module_path=list(finding.module_path),
            data=dict(finding.details),
            explanation=finding.explanation,
            suggestion=finding.suggestion,
        )
        for finding in dedupe_findings(findings)
    ]
    return SimpleReport(name=base_picture.header.name, issues=issues)
