# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportPrivateUsage=false
import json
from pathlib import Path

import pytest

from sattlint.devtools import corpus
from sattlint.devtools.corpus import (
    discover_corpus_manifests,
    execute_corpus_case,
    load_corpus_manifest,
    run_corpus_suite,
)


def test_print_cli_summary_includes_findings_schema(capsys):
    print(
        corpus.format_cli_summary(
            {
                "case_count": 2,
                "failed_count": 1,
                "findings_schema": {
                    "kind": "sattlint.findings",
                    "schema_version": 1,
                },
                "corpus_results_report": "<external>/analysis/corpus_results.json",
            }
        )
    )

    output = capsys.readouterr().out

    assert "Findings schema: sattlint.findings v1" in output
    assert "Corpus cases: 2" in output
    assert "Failed cases: 1" in output
    assert "Corpus results: <external>/analysis/corpus_results.json" in output


def test_load_corpus_manifest_raises_on_malformed_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_corpus_manifest(bad)


def test_load_corpus_manifest_raises_when_root_is_not_object(tmp_path):
    bad = tmp_path / "array.json"
    bad.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected JSON object"):
        load_corpus_manifest(bad)


def test_load_corpus_manifest_raises_when_case_id_missing(tmp_path):
    bad = tmp_path / "no-id.json"
    bad.write_text(
        json.dumps({"target_file": "tests/fixtures/corpus/valid/UnusedVariable.s"}),
        encoding="utf-8",
    )

    with pytest.raises(KeyError):
        load_corpus_manifest(bad)


def test_load_corpus_manifest_raises_when_target_file_missing(tmp_path):
    bad = tmp_path / "no-target.json"
    bad.write_text(json.dumps({"case_id": "no-target"}), encoding="utf-8")

    with pytest.raises(KeyError):
        load_corpus_manifest(bad)


def test_execute_corpus_case_captures_unsupported_mode_as_execution_error(tmp_path):
    manifest_path = tmp_path / "bad-mode.json"
    source = tmp_path / "Program.s"
    source.write_text("placeholder", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "bad-mode-case",
                "target_file": "Program.s",
                "mode": "turbo",
                "expectation": {"expected_finding_ids": []},
            }
        ),
        encoding="utf-8",
    )

    result = execute_corpus_case(manifest_path, tmp_path / "artifacts", repo_root=tmp_path)

    assert result.execution_error is not None
    assert "Unsupported corpus mode" in result.execution_error
    assert result.passed is False


def test_execute_corpus_case_captures_unknown_analyzer_mode_as_execution_error(tmp_path):
    manifest_path = tmp_path / "unknown-analyzer.json"
    source = tmp_path / "Program.s"
    source.write_text("placeholder", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "unknown-analyzer-case",
                "target_file": "Program.s",
                "mode": "analyzer-does-not-exist",
                "expectation": {"expected_finding_ids": []},
            }
        ),
        encoding="utf-8",
    )

    result = execute_corpus_case(manifest_path, tmp_path / "artifacts", repo_root=tmp_path)

    assert result.execution_error is not None
    assert "Unknown analyzer corpus mode" in result.execution_error
    assert result.passed is False


def test_discover_corpus_manifests_returns_empty_when_directory_missing(tmp_path):
    result = discover_corpus_manifests(tmp_path / "nonexistent")

    assert result == ()


def test_discover_corpus_manifests_returns_sorted_json_files(tmp_path):
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    (manifests_dir / "b-case.json").write_text("{}", encoding="utf-8")
    (manifests_dir / "a-case.json").write_text("{}", encoding="utf-8")
    (manifests_dir / "not-a-manifest.txt").write_text("ignored", encoding="utf-8")

    result = discover_corpus_manifests(manifests_dir)

    assert [p.name for p in result] == ["a-case.json", "b-case.json"]


def test_checked_in_corpus_manifests_pass_against_repo_fixtures(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    manifest_dir = repo_root / "tests" / "fixtures" / "corpus" / "manifests"

    suite = run_corpus_suite(
        tmp_path,
        manifest_dir=manifest_dir,
        repo_root=repo_root,
        write_results=False,
    )

    case_ids = {case.manifest.case_id for case in suite.cases}
    assert "strict-invalid" in case_ids
    assert "workspace-common-quality-issues" in case_ids

    new_edge_cases = {
        "edge-sub-sequence-transition",
        "edge-sequence-alternative",
        "edge-sequence-parallel",
        "edge-sub-sequence-definition",
        "edge-seq-break",
        "edge-elsif-expression",
        "edge-terminal-seq-step",
        "edge-frame-module-invocation",
        "edge-scan-group-clause",
        "edge-time-value-init",
        "edge-module-options",
        "edge-simple-module-type-invocation",
        "edge-coordinate-invar-tail",
        "edge-empty-record-type",
        "edge-unicode-identifiers",
    }
    assert new_edge_cases.issubset(case_ids), f"Missing edge case manifests: {new_edge_cases - case_ids}"

    new_semantic_cases = {
        "semantic-sequence-unreachable",
        "semantic-step-contract",
        "semantic-illegal-state-combination",
        "semantic-unreachable-sequence-dataflow",
        "semantic-invalid-state-access",
        "semantic-parallel-hazard",
        "semantic-alarm-integrity",
        "semantic-safety-signal",
        "semantic-resource-lifecycle",
        "semantic-mms-tag",
        "semantic-data-dependency",
        "semantic-code-quality",
        "semantic-scan-cycle",
        "semantic-fault-and-config",
        "semantic-duplicate-sibling-name",
        "semantic-spec-compliance",
        "semantic-module-version-drift",
        "semantic-power-up",
        "workspace-state-inference",
        "semantic-timing",
        "semantic-icf-program",
    }
    assert new_semantic_cases.issubset(case_ids), f"Missing semantic manifests: {new_semantic_cases - case_ids}"

    existing_semantic_manifests = {
        "semantic-dead-overwrite",
        "semantic-implicit-latch",
        "semantic-magic-number",
        "semantic-never-read-variable",
        "semantic-parallel-write-race",
        "semantic-read-before-write",
        "semantic-read-only-non-const",
        "semantic-shadowing-variable",
        "semantic-unused-datatype-field",
        "semantic-unused-variable",
    }
    assert existing_semantic_manifests.issubset(case_ids), (
        f"Missing existing semantic manifests: {existing_semantic_manifests - case_ids}"
    )

    analyzer_cases = {
        "analyzer-comment-code",
        "analyzer-picture-display-unresolved",
        "analyzer-state-inference-impossible-branch",
        "analyzer-loop-output-refactor",
        "analyzer-naming-inconsistent-style",
        "analyzer-cyclomatic-complexity-high",
        "analyzer-parameter-drift",
        "analyzer-scan-loop-resource-usage",
        "analyzer-data-dependency",
        "analyzer-mms-interface",
        "analyzer-resource-usage",
        "analyzer-version-drift",
    }
    assert analyzer_cases.issubset(case_ids), f"Missing analyzer manifests: {analyzer_cases - case_ids}"

    assert suite.passed is True, f"Failed cases: {[c.manifest.case_id for c in suite.cases if not c.passed]}"
    assert all(case.execution_error is None for case in suite.cases)
