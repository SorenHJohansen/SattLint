"""Re-execute analyzer corpus manifests to verify analyzer correctness.

SattLint keeps a corpus of per-analyzer manifests under
``tests/fixtures/corpus/manifests/analyzer-*.json``. Each manifest pins a
target ``.s`` fixture plus the finding ids an analyzer is expected to emit (and
the ids it must never emit), together with the summary counts a stored run would
report. This harness loads every manifest, runs the matching analyzer over its
target, and asserts the findings agree with the manifest expectations.

This is the only harness that executes the analyzer family. The semantic,
valid, edge, and workspace manifests are schema-checked by
``tests/corpus/test_manifest_schema.py`` but have no runner yet.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from sattlint.analyzers.dispatch import (
    get_registry_analyzer_spec,
    run_registry_analyzer,
)
from sattlint.analyzers.framework import (
    AnalysisContext,
    AnalysisSharedArtifacts,
    build_analysis_context,
)
from sattlint.models._variable_issues import VariableIssue
from tests.helpers.project_loading import load_target_project

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


def _target_path(manifest: dict[str, Any]) -> Path:
    return (MANIFESTS_DIR / str(manifest["target_file"])).resolve()


def _analyzer_key(manifest: dict[str, Any]) -> str:
    """The analyzer key the manifest pins.

    Analyzer manifests carry it on the ``status`` artifact; fall back to a
    top-level key or the analyzer-prefixed mode so a manifest cannot silently
    run the wrong analyzer.
    """
    expectation = manifest["expectation"]
    fragments = expectation.get("artifact_fragments", {})
    status = fragments.get("status.json", {})
    key = status.get("analyzer_key")
    if not key:
        key = manifest.get("analyzer_key")
    if not key:
        key = str(manifest.get("mode", "")).removeprefix("analyzer-")
    return str(key)


def _load_target(manifest: dict[str, Any]) -> tuple[Any, Any]:
    """Load the manifest's target fixture into ``(base_picture, graph)``."""
    target_path = _target_path(manifest)
    assert target_path.is_file(), f"{manifest['case_id']}: target fixture missing: {target_path}"

    shared_dir = target_path.parent.parent / "shared"
    return load_target_project(
        target_path,
        abb_lib_dir=shared_dir if shared_dir.is_dir() else target_path.parent,
    )


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


def _ordered_finding_ids(issue: Any) -> list[str]:
    """All canonical ids an issue may be asserted against, in priority order.

    Analyzers report findings under different conventions: some expose a
    ``rule_id``, some a ``rule.id`` (for rule-shaped issues), and the
    ``variables`` analyzer emits ``VariableIssue`` enums. Collect the union so
    manifest expectations can use either convention; the first entry is the id
    used for counting, so one issue never counts twice.
    """
    ids: list[str] = []

    rule = getattr(issue, "rule", None)
    if rule is not None and getattr(rule, "id", None):
        ids.append(str(rule.id))

    rule_id = getattr(issue, "rule_id", None)
    if rule_id:
        ids.append(str(rule_id))

    if isinstance(issue, VariableIssue):
        kind_value = getattr(issue.kind, "value", None)
        if isinstance(kind_value, str):
            ids.append(kind_value)

    kind = getattr(issue, "kind", None)
    if isinstance(kind, str):
        ids.append(kind)

    ordered: list[str] = []
    for finding_id in ids:
        if finding_id not in _IGNORED_FINDING_IDS and finding_id not in ordered:
            ordered.append(finding_id)
    return ordered


def _collect_findings(report: Any, case_id: str) -> tuple[set[str], list[str]]:
    """Return every emitted id plus one counted id per finding."""
    emitted: set[str] = set()
    counted: list[str] = []

    for issue in getattr(report, "issues", ()) or ():
        ids = _ordered_finding_ids(issue)
        assert ids, f"{case_id}: finding has no rule id or kind: {issue!r}"
        emitted.update(ids)
        counted.append(ids[0])

    # Raw analyzer hits are evidence, not findings, so they contribute ids for
    # expectation matching but never to the finding count.
    for hit in getattr(report, "hits", ()) or ():
        emitted.update(_ordered_finding_ids(hit))

    return emitted, counted


def _run_analyzer(manifest: dict[str, Any]) -> tuple[set[str], list[str]]:
    """Run the manifest's analyzer and return the emitted and counted ids."""
    base_picture, graph = _load_target(manifest)
    shared = AnalysisSharedArtifacts()
    spec = get_registry_analyzer_spec(_analyzer_key(manifest))

    context = _build_context(base_picture, graph, shared)
    report = run_registry_analyzer(spec, context)
    return _collect_findings(report, str(manifest["case_id"]))


@pytest.mark.parametrize(
    "case_id,manifest",
    [pytest.param(case_id, manifest, id=case_id) for case_id, manifest in _MANIFESTS],
)
def test_corpus_manifest_analyzer_run(case_id: str, manifest: dict[str, Any]) -> None:
    """The analyzer matches the manifest's finding ids and summary counts."""
    expectation = manifest["expectation"]
    expected = set(expectation.get("expected_finding_ids", [])) - _IGNORED_FINDING_IDS
    forbidden = set(expectation.get("forbidden_finding_ids", []))

    emitted, counted = _run_analyzer(manifest)

    assert not (expected - emitted), f"{case_id}: expected finding ids not emitted: {sorted(expected - emitted)}"
    assert not (forbidden & emitted), f"{case_id}: forbidden finding ids emitted: {sorted(forbidden & emitted)}"

    summary = expectation.get("artifact_fragments", {}).get("summary.json", {})

    if "finding_count" in summary:
        assert len(counted) == summary["finding_count"], (
            f"{case_id}: finding count {len(counted)} != expected {summary['finding_count']}: {sorted(counted)}"
        )

    rule_counts = summary.get("rule_counts")
    if isinstance(rule_counts, dict):
        actual_counts = Counter(counted)
        assert dict(actual_counts) == rule_counts, (
            f"{case_id}: rule counts {dict(actual_counts)} != expected {rule_counts}"
        )
