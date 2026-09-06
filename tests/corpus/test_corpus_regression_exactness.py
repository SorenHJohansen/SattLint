# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false, reportAttributeAccessIssue=false
"""Corpus regression exactness tests (Phase 20).

Canonical corpus cases enforce exact expectations: total finding count, rule
counts, expected finding identities, and no forbidden findings.  Corpus
metadata lives under ``tests/fixtures/corpus`` and production code never
imports test/corpus modules.
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from pathlib import Path

import pytest
from sattline_parser import parse_source_file as parser_core_parse_source_file

from sattlint.analyzers.dispatch import get_registry_analyzer_spec, run_registry_analyzer
from sattlint.analyzers.framework import build_analysis_context
from sattlint.analyzers.registry import deterministic_dependency_order
from sattlint.analyzers.sattline_semantics import analyze_sattline_semantics
from sattlint.engine import CodeMode, SattLineProjectLoader, SattLineProjectLoaderConfig, merge_project_basepicture

CORPUS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "corpus"
MANIFEST_DIR = CORPUS_DIR / "manifests"


def _iter_analyzer_manifests() -> list[tuple[Path, dict[str, object]]]:
    manifests: list[tuple[Path, dict[str, object]]] = []
    for manifest_path in sorted(MANIFEST_DIR.glob("analyzer-*.json")):
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        mode = str(payload.get("mode") or "")
        if not mode.startswith("analyzer-"):
            continue
        manifests.append((manifest_path, payload))
    return manifests


def _resolve_target(manifest: dict[str, object]) -> Path:
    target_file = str(manifest["target_file"])
    return (MANIFEST_DIR / target_file).resolve()


def _uses_semantic_runner(payload: dict[str, object]) -> bool:
    if str(payload.get("mode") or "") == "analyzer-sattline-semantics":
        return True
    expectation = payload.get("expectation")
    if not isinstance(expectation, dict):
        return True
    expected_ids = expectation.get("expected_finding_ids", [])
    return all(str(finding_id).startswith("semantic.") for finding_id in expected_ids)


def _spec_closure(spec: object) -> tuple[object, ...]:
    seen: dict[str, object] = {}
    stack: list[object] = [spec]
    while stack:
        current = stack.pop()
        if current.key in seen:
            continue
        seen[current.key] = current
        for dep_key in getattr(current, "requires", ()):
            if dep_key not in seen:
                stack.append(get_registry_analyzer_spec(dep_key))
    return tuple(seen.values())


def _run_raw_analyzer(target_path: Path, payload: dict[str, object]) -> object:
    shared_dir = target_path.parent.parent / "shared"
    loader = SattLineProjectLoader(
        SattLineProjectLoaderConfig(
            program_dir=target_path.parent,
            other_lib_dirs=[],
            abb_lib_dir=str(shared_dir) if shared_dir.is_dir() else str(target_path.parent),
            mode=CodeMode.DRAFT,
            debug=False,
            use_file_ast_cache=False,
        )
    )
    graph = loader.resolve(target_path.stem, strict=False)
    base_picture = merge_project_basepicture(graph.ast_by_name[target_path.stem], graph)
    context = build_analysis_context(base_picture, graph=graph, debug=False, create_shared_artifacts=True)

    mode = str(payload.get("mode") or "")
    analyzer_key = str(payload.get("analyzer_key") or "").strip() or mode.removeprefix("analyzer-")
    target_spec = get_registry_analyzer_spec(analyzer_key)

    report: object = None
    for spec in deterministic_dependency_order(_spec_closure(target_spec)):
        report = run_registry_analyzer(spec, context, use_shared_artifacts=True)
        if context.shared_artifacts is not None:
            context.shared_artifacts.reports_by_analyzer_key[spec.key] = report
    return report


def _run_analyzer(target_path: Path, payload: dict[str, object]) -> object:
    if _uses_semantic_runner(payload):
        base_picture = parser_core_parse_source_file(target_path)
        return analyze_sattline_semantics(base_picture, debug=True)
    return _run_raw_analyzer(target_path, payload)


def _finding_ids(report: object) -> list[str]:
    ids: list[str] = []
    for item in getattr(report, "issues", ()) or ():
        rule = getattr(item, "rule", None)
        if rule is not None:
            ids.append(str(getattr(rule, "id", "")))
            continue
        kind = getattr(item, "kind", None)
        if kind is not None:
            ids.append(str(getattr(kind, "value", kind)))
    for item in getattr(report, "hits", ()) or ():
        kind = getattr(item, "kind", None)
        if kind is not None:
            ids.append(str(getattr(kind, "value", kind)))
    return [finding_id for finding_id in ids if finding_id]


@pytest.mark.parametrize(
    "manifest_name",
    [manifest_path.name for manifest_path, _payload in _iter_analyzer_manifests()],
)
def test_corpus_manifest_exact_findings(manifest_name: str) -> None:
    manifest_path = MANIFEST_DIR / manifest_name
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    target_path = _resolve_target(payload)
    expectation = payload.get("expectation")
    assert isinstance(expectation, dict), f"manifest {manifest_name} missing expectation"

    if not target_path.exists():
        pytest.skip(f"manifest {manifest_name} target not present: {target_path}")

    report = _run_analyzer(target_path, payload)
    finding_ids = _finding_ids(report)

    expected_finding_ids = set(expectation.get("expected_finding_ids", []))
    forbidden_finding_ids = set(expectation.get("forbidden_finding_ids", []))

    actual_ids = set(finding_ids)
    missing = expected_finding_ids - actual_ids
    assert not missing, f"{manifest_name}: expected findings missing: {sorted(missing)}"

    unexpected = actual_ids & forbidden_finding_ids
    assert not unexpected, f"{manifest_name}: forbidden findings present: {sorted(unexpected)}"

    summary = expectation.get("artifact_fragments", {}).get("summary.json", {})
    if "finding_count" in summary:
        scoped_finding_ids = [finding_id for finding_id in finding_ids if finding_id in expected_finding_ids]
        assert len(scoped_finding_ids) == summary["finding_count"], (
            f"{manifest_name}: finding count {len(scoped_finding_ids)} != expected {summary['finding_count']}"
        )

    rule_counts = summary.get("rule_counts")
    if isinstance(rule_counts, dict):
        actual_counts = Counter(finding_ids)
        for rule_id, expected_count in rule_counts.items():
            assert actual_counts[rule_id] == expected_count, (
                f"{manifest_name}: rule {rule_id} count {actual_counts[rule_id]} != {expected_count}"
            )


def test_production_code_does_not_import_tests_or_corpus() -> None:
    src_dir = Path(__file__).resolve().parents[2] / "src" / "sattlint"
    violations: list[str] = []
    for path in sorted(src_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "tests" or node.module.startswith("tests."):
                    violations.append(f"{path}: imports {node.module}")
                    break
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "tests" or alias.name.startswith("tests."):
                        violations.append(f"{path}: imports {alias.name}")
                        break
    assert violations == [], f"production modules import tests/corpus: {violations}"
