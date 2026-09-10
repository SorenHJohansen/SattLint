"""Re-execute analyzer corpus manifests to verify analyzer correctness.

SattLint keeps a corpus of per-analyzer manifests under
``tests/fixtures/corpus/manifests/analyzer-*.json``. Each manifest pins a
target ``.s`` fixture plus the finding ids an analyzer is expected to emit (and
the ids it must never emit). This harness loads every manifest, runs the
matching analyzer over its target, and asserts the findings agree with the
manifest expectations.

The old parser corpus runner (``sattlint/devtools/corpus.py``) was removed; this
file restores the *analyzer* corpus coverage, driven directly by the manifest
files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sattlint.analyzers._registry_dispatch import (
    get_registry_analyzer_spec,
    run_registry_analyzer,
)
from sattlint.analyzers._sattline_semantic_rules import VARIABLE_RULES
from sattlint.analyzers.framework import (
    AnalysisContext,
    AnalysisSharedArtifacts,
    Issue,
    build_analysis_context,
)
from sattlint.analyzers.rule_profiles import materialize_issue_metadata
from sattlint.analyzers.variables import analyze_variables
from sattlint.engine import (
    CodeMode,
    SattLineProjectLoader,
    SattLineProjectLoaderConfig,
    merge_project_basepicture,
)
from sattlint.models._variable_issues import VariableIssue

MANIFESTS_DIR = Path(__file__).resolve().parent / "fixtures" / "corpus" / "manifests"

# Some manifests carry a degenerate trace-finding marker that is not a real rule id.
_IGNORED_FINDING_IDS = frozenset({"unknown"})


def _load_manifests() -> list[tuple[str, dict[str, Any]]]:
    manifests: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(MANIFESTS_DIR.glob("analyzer-*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifests.append((str(manifest["case_id"]), manifest))
    return manifests


_MANIFESTS = _load_manifests()


def _load_target(manifest: dict[str, Any]) -> tuple[Any, Any]:
    """Load the manifest's target fixture into ``(base_picture, graph)``."""
    target_path = (MANIFESTS_DIR / str(manifest["target_file"])).resolve()
    loader = SattLineProjectLoader(
        SattLineProjectLoaderConfig(
            program_dir=target_path.parent,
            other_lib_dirs=[],
            abb_lib_dir=target_path.parent,
            mode=CodeMode.DRAFT,
            debug=False,
            use_file_ast_cache=False,
        )
    )
    stem = target_path.stem
    graph = loader.resolve(stem, strict=False)
    base_picture = merge_project_basepicture(graph.ast_by_name[stem], graph)
    return base_picture, graph


def _build_context(
    base_picture: Any,
    graph: Any,
    shared_artifacts: AnalysisSharedArtifacts,
) -> AnalysisContext:
    return build_analysis_context(
        base_picture,
        graph=graph,
        debug=False,
        shared_artifacts=shared_artifacts,
        create_shared_artifacts=True,
    )


def _candidate_finding_ids(issue: Any) -> set[str]:
    """All canonical ids an issue may be asserted against.

    Different analyzers report findings under different conventions: some expose a
    semantic rule id (``SemanticIssue.rule.id``), some a raw ``kind`` string, and
    the ``variables`` analyzer emits ``VariableIssue`` enums mapped through
    ``VARIABLE_RULES``. Collect the union so manifest expectations can use either
    convention.
    """
    ids: set[str] = set()

    rule_id = getattr(issue, "rule_id", None)
    if rule_id:
        ids.add(rule_id)

    rule = getattr(issue, "rule", None)
    if rule is not None and getattr(rule, "id", None):
        ids.add(rule.id)

    if isinstance(issue, VariableIssue):
        mapped = VARIABLE_RULES.get(issue.kind)
        if mapped is not None and getattr(mapped, "id", None):
            ids.add(mapped.id)
        kind_value = getattr(issue.kind, "value", None)
        if isinstance(kind_value, str):
            ids.add(kind_value)

    if isinstance(issue, Issue):
        materialized = materialize_issue_metadata(issue)
        materialized_id = getattr(materialized, "rule_id", None)
        if materialized_id:
            ids.add(materialized_id)

    kind = getattr(issue, "kind", None)
    if isinstance(kind, str):
        ids.add(kind)

    return ids - _IGNORED_FINDING_IDS


def _run_analyzer(manifest: dict[str, Any]) -> set[str]:
    """Run the manifest's analyzer and return the set of emitted finding ids."""
    base_picture, graph = _load_target(manifest)
    shared = AnalysisSharedArtifacts()
    analyzer_key = str(manifest["expectation"]["artifact_fragments"]["status.json"]["analyzer_key"])
    spec = get_registry_analyzer_spec(analyzer_key)

    if "variables" in (spec.requires or ()):
        variables_context = _build_context(base_picture, graph, shared)
        analyze_variables(base_picture, analysis_context=variables_context)

    context = _build_context(base_picture, graph, shared)
    report = run_registry_analyzer(spec, context)

    emitted: set[str] = set()
    for issue in getattr(report, "issues", ()) or ():
        emitted |= _candidate_finding_ids(issue)
    return emitted


@pytest.mark.parametrize(
    "case_id,manifest",
    [pytest.param(case_id, manifest, id=case_id) for case_id, manifest in _MANIFESTS],
)
def test_corpus_manifest_analyzer_run(case_id: str, manifest: dict[str, Any]) -> None:
    """The analyzer emits all expected finding ids and none of the forbidden ones."""
    expectation = manifest["expectation"]
    expected = set(expectation.get("expected_finding_ids", [])) - _IGNORED_FINDING_IDS
    forbidden = set(expectation.get("forbidden_finding_ids", []))

    emitted = _run_analyzer(manifest)

    assert not (expected - emitted), f"{case_id}: expected finding ids not emitted: {sorted(expected - emitted)}"
    assert not (forbidden & emitted), f"{case_id}: forbidden finding ids emitted: {sorted(forbidden & emitted)}"
