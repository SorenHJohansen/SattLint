import json
from pathlib import Path
from unittest.mock import patch

import pytest

from sattlint.devtools import coordination_lock_state, doc_gardener, repo_audit

_COVERAGE_XML_TEMPLATE = """
<?xml version="1.0" ?>
<coverage>
    <packages>
        <package>
            <classes>
                {classes}
            </classes>
        </package>
    </packages>
</coverage>
"""


def _write_coverage_xml(root: Path, classes_xml: str) -> None:
    (root / "coverage.xml").write_text(
        _COVERAGE_XML_TEMPLATE.format(classes=classes_xml).strip(),
        encoding="utf-8",
    )


def test_build_coverage_summary_report_returns_skipped_when_no_coverage_xml(tmp_path):
    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["skipped"] is True
    assert report["kind"] == "sattlint.coverage_summary"
    assert report["schema_version"] == 1
    assert report["modules"] == []
    assert report["findings"] == []
    assert report["summary"]["module_count"] == 0


def test_build_coverage_summary_report_emits_low_coverage_findings(tmp_path):
    _write_coverage_xml(
        tmp_path,
        '<class filename="src/sattlint/some_module.py" line-rate="0.05" lines-valid="100" />'
        '<class filename="src/sattlint/other_module.py" line-rate="0.35" lines-valid="50" />'
        '<class filename="src/sattlint/good_module.py" line-rate="0.80" lines-valid="200" />',
    )

    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["skipped"] is False
    assert report["summary"]["module_count"] == 3
    assert report["summary"]["low_coverage_count"] == 2

    severities = {f["severity"] for f in report["findings"]}
    assert "high" in severities
    assert "medium" in severities

    paths_in_findings = {f["path"] for f in report["findings"]}
    assert "src/sattlint/good_module.py" not in paths_in_findings


def test_build_coverage_summary_report_skips_non_src_modules(tmp_path):
    _write_coverage_xml(
        tmp_path,
        '<class filename="tests/test_something.py" line-rate="0.05" lines-valid="50" />'
        '<class filename="src/sattlint/real_module.py" line-rate="0.90" lines-valid="200" />',
    )

    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["summary"]["module_count"] == 1
    assert report["summary"]["low_coverage_count"] == 0
    assert all(m["path"].startswith("src/") for m in report["modules"])


def test_build_coverage_summary_report_includes_avg_line_rate(tmp_path):
    _write_coverage_xml(
        tmp_path,
        '<class filename="src/a.py" line-rate="0.20" lines-valid="100" />'
        '<class filename="src/b.py" line-rate="0.80" lines-valid="100" />',
    )

    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["summary"]["avg_line_rate"] == pytest.approx(0.5, abs=0.01)


def test_build_coverage_summary_report_skips_unreadable_coverage_xml(monkeypatch, tmp_path):
    coverage_path = tmp_path / "coverage.xml"
    coverage_path.write_text("placeholder", encoding="utf-8")

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == coverage_path:
            raise PermissionError("permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text)

    report = repo_audit.build_coverage_summary_report(tmp_path)

    assert report["skipped"] is True
    assert report["skip_reason"] == "coverage.xml unreadable"
    assert report["ratchet"]["error_type"] == "OSError"


def test_build_cli_consistency_report_has_required_schema_fields():
    report = repo_audit.build_cli_consistency_report()

    assert report["kind"] == "sattlint.cli_consistency"
    assert report["schema_version"] == 1
    assert "declared" in report
    assert "scripts" in report["declared"]
    assert "subcommands" in report["declared"]
    assert "gaps" in report
    assert "summary" in report
    assert "status" in report
    assert report["status"] in ("pass", "fail")


def test_build_cli_consistency_report_lists_declared_scripts_and_subcommands():
    report = repo_audit.build_cli_consistency_report()

    assert any("sattlint" in s for s in report["declared"]["scripts"])
    assert len(report["declared"]["subcommands"]) > 0


def test_build_cli_consistency_report_gap_counts_match_gap_lists():
    report = repo_audit.build_cli_consistency_report()

    gaps = report["gaps"]
    summary = report["summary"]

    assert summary["undeclared_subcommand_count"] == len(gaps["undeclared_subcommands"])
    assert summary["undeclared_script_count"] == len(gaps["undeclared_scripts"])
    assert summary["undocumented_subcommand_count"] == len(gaps["undocumented_subcommands"])
    assert summary["undocumented_script_count"] == len(gaps["undocumented_scripts"])
    expected_gap_count = summary["undeclared_subcommand_count"] + summary["undeclared_script_count"]
    assert summary["gap_count"] == expected_gap_count


def test_build_cli_consistency_report_detects_undeclared_subcommand(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text("Run `sattlint ghost-command` to do something.\n", encoding="utf-8")

    monkeypatch.setattr(
        repo_audit,
        "_collect_cli_metadata",
        lambda: ({"sattlint"}, {"syntax-check", "analyze"}),
    )

    report = repo_audit.build_cli_consistency_report(root=tmp_path)

    undeclared_names = [g["subcommand"] for g in report["gaps"]["undeclared_subcommands"]]
    assert "ghost-command" in undeclared_names
    assert report["summary"]["gap_count"] > 0
    assert report["status"] == "fail"


def test_build_cli_consistency_report_pass_when_all_documented_subcommands_are_declared(tmp_path, monkeypatch):
    readme = tmp_path / "README.md"
    readme.write_text("Run `sattlint syntax-check` to check syntax.\n", encoding="utf-8")

    monkeypatch.setattr(
        repo_audit,
        "_collect_cli_metadata",
        lambda: ({"sattlint"}, {"syntax-check"}),
    )

    report = repo_audit.build_cli_consistency_report(root=tmp_path)

    assert report["gaps"]["undeclared_subcommands"] == []
    assert report["summary"]["undeclared_subcommand_count"] == 0


def test_build_cli_consistency_report_ignores_exec_plan_markdown_noise(tmp_path, monkeypatch):
    cli_docs = tmp_path / "docs" / "references"
    cli_docs.mkdir(parents=True)
    (cli_docs / "cli-commands.md").write_text("Run `sattlint syntax-check` to validate syntax.\n", encoding="utf-8")

    exec_plan = tmp_path / "docs" / "exec-plans" / "active"
    exec_plan.mkdir(parents=True)
    (exec_plan / "plan.md").write_text(
        "Do not suppress the `sattlint-syntax-check` hook.\n"
        '    rg -n "sattlint|sattlint-repo-audit|sattlint-corpus-runner|sattlint-lsp" README.md docs\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        repo_audit,
        "_collect_cli_metadata",
        lambda: ({"sattlint", "sattlint-repo-audit"}, {"syntax-check"}),
    )

    report = repo_audit.build_cli_consistency_report(root=tmp_path)

    assert report["status"] == "pass"
    assert report["gaps"]["undeclared_scripts"] == []
    assert report["gaps"]["undeclared_subcommands"] == []


def test_cli_consistency_findings_preserve_report_script_and_path_fields():
    report = {
        "gaps": {
            "undeclared_subcommands": [
                {
                    "subcommand": "ghost-command",
                    "referenced_in": "docs/references/cli-commands.md",
                    "line": 12,
                }
            ],
            "undeclared_scripts": [
                {
                    "script": "sattlint-ghost",
                    "referenced_in": "docs/references/cli-commands.md",
                    "line": 24,
                }
            ],
        }
    }

    findings = repo_audit._repo_audit_entrypoints._cli_consistency_findings(report)

    assert [finding.id for finding in findings] == [
        "cli-consistency-undeclared-subcommand",
        "cli-consistency-undeclared-script",
    ]
    assert findings[0].path == "docs/references/cli-commands.md"
    assert findings[0].line == 12
    assert findings[1].path == "docs/references/cli-commands.md"
    assert findings[1].line == 24
    assert findings[1].message == "Documented CLI script 'sattlint-ghost' is not declared."


def test_doc_gardener_relative_path_returns_repo_relative():
    with patch.multiple(
        doc_gardener,
        REPO_ROOT=Path("/repo"),
    ):
        result = doc_gardener._relative_path(Path("/repo/src/sample.py"))

        assert result == "src/sample.py"


def test_doc_gardener_relative_path_falls_back_to_posix_when_not_relative():
    with patch.multiple(
        doc_gardener,
        REPO_ROOT=Path("/repo"),
    ):
        result = doc_gardener._relative_path(Path("/other/sample.py"))

        assert result == "/other/sample.py"


def test_doc_gardener_read_text_handles_utf8(tmp_path):
    sample_file = tmp_path / "sample.txt"
    text = "Normal ASCII text\n"
    sample_file.write_bytes(text.encode("utf-8"))

    result = doc_gardener._read_text(sample_file)

    assert result == text


def test_doc_gardener_should_skip_path_identifies_venv_dirs():
    assert doc_gardener._should_skip_path(Path("/repo/.venv/lib/sample.py")) is True
    assert doc_gardener._should_skip_path(Path("/repo/.venv-backup/lib/sample.py")) is True
    assert doc_gardener._should_skip_path(Path("/repo/__pycache__/sample.py")) is True
    assert doc_gardener._should_skip_path(Path("/repo/src/sample.py")) is False


def test_doc_gardener_normalize_workstream_id_parses_w_prefixed():
    assert doc_gardener._normalize_workstream_id("W1") == "W1"
    assert doc_gardener._normalize_workstream_id("w1") == "W1"
    assert doc_gardener._normalize_workstream_id("w1-something") == "W1"
    assert doc_gardener._normalize_workstream_id("B-W3") == "W3"
    assert doc_gardener._normalize_workstream_id("invalid") is None


def test_doc_gardener_normalize_status_maps_common_aliases():
    assert doc_gardener._normalize_status("active") == "In progress"
    assert doc_gardener._normalize_status("in progress") == "In progress"
    assert doc_gardener._normalize_status("open") == "Open"
    assert doc_gardener._normalize_status("planned") == "Open"
    assert doc_gardener._normalize_status("blocked") == "Blocked"
    assert doc_gardener._normalize_status("done") == "Done"


def test_doc_gardener_parse_markdown_table_extracts_rows():
    lines = [
        "## Section Header",
        "| Name | Value |",
        "| --- | --- |",
        "| Item1 | 100 |",
        "| Item2 | 200 |",
    ]

    result = doc_gardener._parse_markdown_table(lines, "## Section Header")

    assert len(result) == 2
    assert result[0][1]["Name"] == "Item1"
    assert result[0][1]["Value"] == "100"
    assert result[1][1]["Name"] == "Item2"


def test_doc_gardener_parse_markdown_table_stops_at_next_section():
    lines = [
        "## Section 1",
        "| Name | Value |",
        "| --- | --- |",
        "| Item1 | 100 |",
        "## Section 2",
        "| Name | Value |",
        "| --- | --- |",
        "| Item2 | 200 |",
    ]

    result = doc_gardener._parse_markdown_table(lines, "## Section 1")

    assert len(result) == 1
    assert result[0][1]["Name"] == "Item1"


def test_doc_gardener_load_active_workstream_statuses_extracts_status_from_lock_state(tmp_path):
    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True)
    (coordination_dir / "current_work_lock.json").write_text(
        json.dumps(
            {
                "workstreams": [
                    {
                        "workstream_id": "W1-something",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": ["src/demo.py"],
                        "updated_at": coordination_lock_state.utc_now_timestamp(),
                        "first_validation": "pytest tests/test_repo_audit_part1.py -x -q --tb=short",
                    },
                    {
                        "workstream_id": "W2",
                        "owner": "Copilot",
                        "status": "blocked",
                        "claimed_paths": ["src/other.py"],
                        "updated_at": coordination_lock_state.utc_now_timestamp(),
                        "first_validation": "pytest tests/test_repo_audit_part1.py -x -q --tb=short",
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = doc_gardener._load_active_workstream_statuses(tmp_path)

    assert result.get("W1") == "In progress"
    assert result.get("W2") == "Blocked"


def test_doc_gardener_source_sync_digest_is_deterministic():
    tmp_file = Path("/tmp/test_doc.txt")
    with patch.object(Path, "read_bytes", return_value=b"test content"):
        digest1 = doc_gardener._source_sync_digest(tmp_file)
        digest2 = doc_gardener._source_sync_digest(tmp_file)

    assert digest1 == digest2
    assert len(digest1) == 12
