# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportUnnecessaryCast=false
from __future__ import annotations

import builtins
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from sattlint.contracts.findings import FindingCollection, FindingLocation, FindingRecord
from sattlint.devtools import (
    accuracy_metrics,
    ai_templates,
    differential,
    mutation_engine,
    parser_properties,
    production_summary,
)


def _finding(
    rule_id: str,
    *,
    severity: str = "medium",
    path: str = "src/demo.py",
    message: str | None = None,
    fingerprint: str | None = None,
) -> FindingRecord:
    return FindingRecord(
        id=rule_id,
        rule_id=rule_id,
        category="demo",
        severity=severity,
        confidence="high",
        message=message or rule_id,
        source="tests",
        analyzer="demo",
        artifact="findings",
        location=FindingLocation(path=path),
        fingerprint=fingerprint,
    )


def test_accuracy_metrics_load_and_build_summary(tmp_path: Path) -> None:
    missing = accuracy_metrics.load_annotations(tmp_path / "missing.json")

    annotations_path = tmp_path / "annotations.json"
    annotations_path.write_text(
        '{"annotations": ['
        '{"finding_fingerprint": "fp-medium", "annotation": "false_positive", "rule_id": "rule.medium", '
        '"annotated_by": "qa", "note": "noise"}, '
        '{"finding_fingerprint": "fp-explicit", "annotation": "correct"}'
        "]}",
        encoding="utf-8",
    )

    annotations = accuracy_metrics.load_annotations(annotations_path)
    findings = FindingCollection(
        (
            _finding("rule.medium", fingerprint="fp-medium"),
            _finding("rule.high", severity="high", fingerprint="fp-high"),
            _finding("rule.low", severity="low", fingerprint="fp-low"),
        )
    )
    metrics = accuracy_metrics.build_accuracy_metrics(findings, annotations)
    payload = metrics.to_dict()

    assert missing == []
    assert [annotation.annotation for annotation in metrics.annotations] == [
        "false_positive",
        "missed_issue",
        "correct",
    ]
    assert payload["summary"] == {
        "total_annotations": 3,
        "correct": 1,
        "false_positives": 1,
        "missed_issues": 1,
        "precision": 0.3333,
    }
    assert payload["by_rule"]["rule.medium"]["false_positive"] == 1
    assert payload["annotations"][0]["annotated_by"] == "qa"


def test_accuracy_metrics_write_report(tmp_path: Path) -> None:
    findings = FindingCollection((_finding("rule.medium", fingerprint="fp-medium"),))

    output_path = accuracy_metrics.write_accuracy_metrics(
        tmp_path,
        accuracy_metrics.build_accuracy_metrics(findings, []),
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert output_path.name == accuracy_metrics.ACCURACY_METRICS_FILENAME
    assert payload["kind"] == accuracy_metrics.ACCURACY_SCHEMA_KIND
    assert payload["summary"] == {
        "total_annotations": 1,
        "correct": 1,
        "false_positives": 0,
        "missed_issues": 0,
        "precision": 1.0,
    }


def test_ai_templates_builds_summary_from_catalog_and_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = SimpleNamespace(
        rules=[
            SimpleNamespace(id="alarm.integrity"),
            SimpleNamespace(id="safety.path"),
            SimpleNamespace(id="naming.rule"),
        ]
    )
    findings = FindingCollection(tuple(_finding(f"rule-{index}", fingerprint=f"fp-{index}") for index in range(6)))
    monkeypatch.setattr(ai_templates, "get_default_analyzer_catalog", lambda: catalog)

    summary = ai_templates.build_ai_task_templates(findings)
    payload = summary.to_dict()

    assert [template.template_id for template in summary.templates] == [
        "analyzer-coverage-review",
        "false-positive-triage",
        "migration-safety-check",
    ]
    assert summary.templates[0].related_rules == [
        "alarm.integrity",
        "safety.path",
        "naming.rule",
    ]
    assert summary.templates[1].example_findings == [f"fp-{index}" for index in range(5)]
    assert summary.templates[2].related_rules == ["alarm.integrity", "safety.path"]
    assert payload["summary"] == {"template_count": 3, "rules_covered": 3}


def test_differential_report_tracks_added_removed_surviving_and_config_drift() -> None:
    baseline = FindingCollection(
        (
            _finding("shared", severity="medium", fingerprint="shared-fp"),
            _finding("removed", severity="low", fingerprint="removed-fp"),
        )
    )
    current = FindingCollection(
        (
            _finding("shared", severity="high", fingerprint="shared-fp"),
            _finding("added", severity="medium", fingerprint="added-fp"),
        )
    )

    result = differential.build_differential_report(
        baseline,
        current,
        baseline_label="before",
        current_label="after",
        config_keys=["severity"],
    )
    payload = result.to_dict()

    assert [finding.rule_id for finding in result.added] == ["added"]
    assert [finding.rule_id for finding in result.removed] == ["removed"]
    assert [finding.rule_id for finding in result.surviving] == ["shared"]
    assert set(result.config_drift) == {"added", "removed", "shared"}
    assert payload["summary"] == {
        "baseline": "before",
        "current": "after",
        "added_count": 1,
        "removed_count": 1,
        "surviving_count": 1,
        "config_drift_count": 3,
    }


def test_mutation_helpers_cover_literal_flips_counts_and_file_output(tmp_path: Path) -> None:
    bool_mutations = list(mutation_engine._mutate_literal("TRUE\nFALSE\n", literal_type="bool"))
    numeric_mutations = list(mutation_engine._mutate_literal("Value\n10\n", literal_type="numeric"))
    float_mutations = list(mutation_engine._mutate_literal("7.5\n", literal_type="numeric"))

    results = mutation_engine.MutationResults(
        [
            mutation_engine.MutationRecord("bool-flip", "a", "TRUE", "FALSE", True),
            mutation_engine.MutationRecord("numeric-bump", "b", "1", "2", False),
        ]
    )
    mutation_engine.write_mutation_results(tmp_path, results)

    assert bool_mutations == ["FALSE\nFALSE\n", "TRUE\nTRUE\n"]
    assert numeric_mutations == ["Value\n11\n"]
    assert float_mutations == ["8.5\n"]
    assert results.killed_count == 1
    assert results.alive_count == 1
    assert results.to_dict()["summary"] == {"total_mutations": 2, "killed": 1, "alive": 1}
    assert (tmp_path / mutation_engine.MUTATION_RESULTS_FILENAME).exists()


def test_numeric_mutation_keeps_original_value_when_float_conversion_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    original_float = builtins.float

    def broken_float(value: object) -> float:
        raise ValueError(f"cannot parse {value}")

    monkeypatch.setattr(builtins, "float", broken_float)

    assert list(mutation_engine._mutate_literal("7.5\n", literal_type="numeric")) == []

    monkeypatch.setattr(builtins, "float", original_float)


def test_run_mutation_analysis_marks_killed_and_skips_parse_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "Program.s"
    source_file.write_text("TRUE\n10\n", encoding="utf-8")
    findings = FindingCollection((_finding("unused", path=source_file.as_posix()),))

    monkeypatch.setattr(mutation_engine, "parser_core_parse_source_text", lambda _source: cast(Any, object()))
    results = mutation_engine.run_mutation_analysis(source_file, findings)

    assert len(results.records) == 2
    assert all(record.killed for record in results.records)
    assert {record.mutation_kind for record in results.records} == {"bool-flip", "numeric-bump"}
    assert {record.killing_rule_id for record in results.records} == {"unused"}

    monkeypatch.setattr(
        mutation_engine,
        "parser_core_parse_source_text",
        lambda _source: (_ for _ in ()).throw(ValueError("bad parse")),
    )
    skipped = mutation_engine.run_mutation_analysis(source_file, findings, mutation_kinds=("bool-flip",))

    assert skipped.records == []


def test_run_mutation_analysis_skips_none_results_and_keeps_unmatched_findings_alive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_file = tmp_path / "Program.s"
    source_file.write_text("TRUE\n10\n", encoding="utf-8")
    findings = FindingCollection((_finding("unused", path="src/other.py"),))
    parse_results = iter([None, cast(Any, object())])
    monkeypatch.setattr(mutation_engine, "parser_core_parse_source_text", lambda _source: next(parse_results))

    results = mutation_engine.run_mutation_analysis(source_file, findings)

    assert len(results.records) == 1
    assert results.records[0].mutation_kind == "numeric-bump"
    assert results.records[0].killed is False


def test_parser_property_helpers_cover_generation_iteration_and_failure_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parser_properties.random, "choice", lambda items: items[-1])

    assert 'name: MainProg"' in parser_properties.generate_simple_program()
    assert "flag: integer := 3;" in parser_properties.generate_simple_program()
    assert "WorkerType = MODULEDEFINITION" in parser_properties.generate_simple_module()
    assert "cnt: integer := 3;" in parser_properties.generate_simple_module()

    parse_calls = iter(
        [
            SimpleNamespace(header=SimpleNamespace(name="Program"), submodules=[1, 2]),
            SimpleNamespace(header=SimpleNamespace(name="Program"), submodules=[3, 4]),
        ]
    )
    monkeypatch.setattr(parser_properties, "parser_core_parse_source_text", lambda _source: next(parse_calls))
    parser_properties.assert_parser_deterministic("SOURCE")

    monkeypatch.setattr(parser_properties, "parser_core_parse_source_text", lambda _source: cast(Any, object()))
    assert parser_properties.assert_valid_program_has_no_crash("SOURCE") is True
    monkeypatch.setattr(
        parser_properties,
        "parser_core_parse_source_text",
        lambda _source: (_ for _ in ()).throw(SyntaxError("bad")),
    )
    assert parser_properties.assert_valid_program_has_no_crash("SOURCE") is False

    seeded_values: list[int] = []
    monkeypatch.setattr(parser_properties.random, "seed", lambda value: seeded_values.append(value))
    program_values = iter(["prog-1", "prog-2"])
    module_values = iter(["mod-1", "mod-2"])
    monkeypatch.setattr(parser_properties, "generate_simple_program", lambda: next(program_values))
    monkeypatch.setattr(parser_properties, "generate_simple_module", lambda: next(module_values))

    assert list(parser_properties.iter_generated_programs(count=2, seed=7)) == ["prog-1", "prog-2"]
    assert list(parser_properties.iter_generated_modules(count=2, seed=9)) == ["mod-1", "mod-2"]
    assert seeded_values == [7, 9]

    generated = iter(["source-a", "source-b", "source-c"])
    monkeypatch.setattr(parser_properties, "generate_simple_program", lambda: next(generated))

    def property_fn(source: str) -> bool:
        if source.endswith("a"):
            return True
        if source.endswith("b"):
            return False
        raise RuntimeError("boom")

    failures = parser_properties.check_parser_property(property_fn, count=3, seed=42)

    assert failures[0] == ("source-b", None)
    assert failures[1][0] == "source-c"
    assert isinstance(failures[1][1], RuntimeError)


def test_production_summary_helpers_cover_kloc_filtering_and_repo_allowlist(tmp_path: Path) -> None:
    source_file = tmp_path / "large.s"
    source_file.write_text("line\n" * 2000, encoding="utf-8")

    assert production_summary._compute_kloc([source_file, tmp_path / "missing.s"]) == 2
    assert production_summary._compute_kloc([tmp_path / "missing.s"]) == 1

    unrelated_root = tmp_path / "demo-repo"
    unrelated_root.mkdir()
    findings = FindingCollection((_finding("unused", fingerprint="ignored-case"),))
    assert production_summary.build_production_summary(unrelated_root, findings) is None

    repo_root = tmp_path / "sattline-demo"
    repo_root.mkdir()
    (repo_root / "Program.s").write_text("line\n" * 2000, encoding="utf-8")
    (repo_root / "Library.x").write_text("line\n" * 5, encoding="utf-8")
    (repo_root / "artifacts").mkdir()
    (repo_root / "artifacts" / "Generated.s").write_text("line\n" * 3000, encoding="utf-8")
    (repo_root / "node_modules").mkdir()
    (repo_root / "node_modules" / "Vendor.x").write_text("line\n" * 3000, encoding="utf-8")
    collection = FindingCollection(
        (
            _finding("unused", fingerprint="ignored-case"),
            _finding("unused", fingerprint="fixed-case"),
            _finding("contract", fingerprint="plain-case"),
        )
    )

    summary = production_summary.build_production_summary(repo_root, collection, repo_name="RepoName")

    assert summary is not None
    assert summary.repo_name == "RepoName"
    assert summary.findings_per_kloc == 1.5
    assert summary.rule_frequency == {"unused": 2, "contract": 1}
    assert summary.ignored_vs_fixed == {"ignored": 1, "fixed": 1}
    assert summary.to_dict()["summary"]["path_redaction_count"] == 0


def test_production_summary_uses_detected_name_and_skips_oserror_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "sattline-sample"
    repo_root.mkdir()
    ok_file = repo_root / "Program.s"
    bad_file = repo_root / "Program.x"
    ok_file.write_text("line\n" * 10, encoding="utf-8")
    bad_file.write_text("line\n", encoding="utf-8")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args: Any, **kwargs: Any) -> str:
        if self == bad_file:
            raise OSError("locked")
        return cast(str, original_read_text(self, *args, **kwargs))

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    assert production_summary._compute_kloc([ok_file, bad_file]) == 1

    summary = production_summary.build_production_summary(
        repo_root,
        FindingCollection((_finding("unused", fingerprint="plain"),)),
    )

    assert summary is not None
    assert summary.repo_name == "sattline-sample"
