# ruff: noqa: F403, F405
from ._repo_audit_test_support import *


def test_print_cli_summary_includes_findings_schema(tmp_path):
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 30, 12, 0, tzinfo=UTC)

    quality_score = tmp_path / "docs" / "quality-score.md"
    quality_score.parent.mkdir(parents=True)
    quality_score.write_text(
        "## Trend\n| Date | Grade | Notes | Source |\n|---|---|---|---|\n",
        encoding="utf-8",
    )
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True, exist_ok=True)
    tech_debt.write_text(
        "## Scan Log\n| Date | Summary | Notes | Source |\n|---|---|---|---|\n",
        encoding="utf-8",
    )
    findings = [doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")]

    with _patch_doc_gardener_paths(tmp_path), patch.object(doc_gardener, "datetime", _FixedDateTime):
        doc_gardener.update_quality_score(findings)
        doc_gardener.update_tech_debt_scan_log(findings)

    assert "| 2026-04-30 | B | 1 findings | Scan |" in quality_score.read_text(encoding="utf-8")
    assert "| 2026-04-30 | 1 findings | Doc-gardening scan |" in tech_debt.read_text(encoding="utf-8")


def test_update_quality_score_creates_trend_section_from_pipeline_snapshot(tmp_path):
    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 4, 30, 12, 0, tzinfo=UTC)

    quality_score = tmp_path / "docs" / "quality-score.md"
    quality_score.parent.mkdir(parents=True)
    quality_score.write_text(
        """
# Quality Score

## Domain Scores

| Domain | Path | Grade | Coverage | Last Updated | Blocker |
| --- | --- | --- | --- | --- | --- |
| DevTools | src/sattlint/devtools/ | B | 18% | 2026-04-28 | TD-004 |

## Layer Scores

| Layer | Grade | Reason |
| --- | --- | --- |
| Docs/Process | B | Tracked |

## Grading Scale

- A
""".strip()
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "artifacts" / "analysis"
    output_dir.mkdir(parents=True)
    write_json_artifact(
        output_dir / "status.json",
        {
            "overall_status": "pass_with_notes",
            "status_report": "artifacts/analysis/status.json",
            "summary_report": "artifacts/analysis/summary.json",
        },
    )
    write_json_artifact(
        output_dir / "summary.json",
        {
            "profile": "full",
            "reports": {"coverage_summary": "coverage_summary.json"},
            "counts": {"normalized_findings": 2},
        },
    )
    write_json_artifact(
        output_dir / "coverage_summary.json",
        {
            "summary": {"total_line_rate": 0.88},
        },
    )
    findings = [doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")]

    with _patch_doc_gardener_paths(tmp_path), patch.object(doc_gardener, "datetime", _FixedDateTime):
        snapshot, message = doc_gardener.load_pipeline_snapshot(output_dir)
        assert message is None
        assert snapshot is not None
        doc_gardener.update_quality_score(findings, snapshot)

    content = quality_score.read_text(encoding="utf-8")
    assert "## Trend" in content
    assert (
        "| 2026-04-30 | B | pass_with_notes; 2 pipeline findings; 1 doc findings; 88.0% coverage | Pipeline |"
        in content
    )
    assert content.index("## Trend") < content.index("## Grading Scale")


def test_load_pipeline_snapshot_returns_message_when_artifacts_missing(tmp_path):
    snapshot, message = doc_gardener.load_pipeline_snapshot(tmp_path / "artifacts" / "analysis")

    assert snapshot is None
    assert message == "missing pipeline artifacts: status.json, summary.json"


def test_load_pipeline_snapshot_falls_back_to_findings_json_count(tmp_path):
    output_dir = tmp_path / "artifacts" / "analysis"
    output_dir.mkdir(parents=True)
    write_json_artifact(
        output_dir / "status.json",
        {
            "overall_status": "pass",
            "status_report": "artifacts/analysis/status.json",
            "summary_report": "artifacts/analysis/summary.json",
        },
    )
    write_json_artifact(
        output_dir / "summary.json",
        {
            "profile": "quick",
            "reports": {"coverage_summary": None},
            "counts": {},
        },
    )
    write_json_artifact(
        output_dir / "findings.json",
        {
            "finding_count": 3,
            "findings": [],
        },
    )

    snapshot, message = doc_gardener.load_pipeline_snapshot(output_dir)

    assert message is None
    assert snapshot is not None
    assert snapshot.normalized_findings == 3


def test_doc_gardener_main_updates_logs_without_exit_when_clean(monkeypatch, capsys):
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 0,
            "by_severity": dict.fromkeys(doc_gardener.SEVERITY_ORDER, 0),
            "by_category": dict.fromkeys(doc_gardener.CATEGORY_ORDER, 0),
            "findings": [],
        },
    )
    monkeypatch.setattr(doc_gardener, "update_quality_score", lambda findings, pipeline_snapshot=None: None)
    monkeypatch.setattr(doc_gardener, "update_tech_debt_scan_log", lambda findings: None)
    monkeypatch.setattr(doc_gardener, "open_fixup_pr", lambda findings: pytest.fail("PR should not open when clean"))

    assert doc_gardener.main() == 0

    out = capsys.readouterr().out
    assert "Doc-gardening scan complete: 0 findings" in out
    assert "Tracking files updated." in out


def test_doc_gardener_main_reports_findings_without_opening_pr_by_default(monkeypatch, capsys):
    finding = doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 1,
            "by_severity": {severity: (1 if severity == "Medium" else 0) for severity in doc_gardener.SEVERITY_ORDER},
            "by_category": {
                category: (1 if category == "dead_link" else 0) for category in doc_gardener.CATEGORY_ORDER
            },
            "findings": [finding._asdict()],
        },
    )
    monkeypatch.setattr(doc_gardener, "update_quality_score", lambda findings, pipeline_snapshot=None: None)
    monkeypatch.setattr(doc_gardener, "update_tech_debt_scan_log", lambda findings: None)
    monkeypatch.setattr(doc_gardener, "open_fixup_pr", lambda findings: pytest.fail("PR should be opt-in"))

    assert doc_gardener.main() == 1

    out = capsys.readouterr().out
    assert "[Medium] docs/index.md:2 - Broken link" in out
    assert "Tracking files updated." in out
    assert "Attempting to open fix-up PR..." not in out


def test_doc_gardener_main_check_only_does_not_update_logs_or_open_pr(monkeypatch, capsys):
    finding = doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 1,
            "by_severity": {severity: (1 if severity == "Medium" else 0) for severity in doc_gardener.SEVERITY_ORDER},
            "by_category": {
                category: (1 if category == "dead_link" else 0) for category in doc_gardener.CATEGORY_ORDER
            },
            "findings": [finding._asdict()],
        },
    )
    monkeypatch.setattr(
        doc_gardener,
        "update_quality_score",
        lambda findings, pipeline_snapshot=None: pytest.fail("check-only mode should not update quality score"),
    )
    monkeypatch.setattr(
        doc_gardener,
        "update_tech_debt_scan_log",
        lambda findings: pytest.fail("check-only mode should not update scan log"),
    )
    monkeypatch.setattr(
        doc_gardener, "open_fixup_pr", lambda findings: pytest.fail("check-only mode should not open PR")
    )

    assert doc_gardener.main(["--check-only"]) == 1

    out = capsys.readouterr().out
    assert "Check-only mode: tracking files not updated." in out
    assert "Attempting to open fix-up PR..." not in out


def test_doc_gardener_main_opens_pr_when_requested(monkeypatch, capsys):
    finding = doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")
    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 1,
            "by_severity": {severity: (1 if severity == "Medium" else 0) for severity in doc_gardener.SEVERITY_ORDER},
            "by_category": {
                category: (1 if category == "dead_link" else 0) for category in doc_gardener.CATEGORY_ORDER
            },
            "findings": [finding._asdict()],
        },
    )
    monkeypatch.setattr(doc_gardener, "update_quality_score", lambda findings, pipeline_snapshot=None: None)
    monkeypatch.setattr(doc_gardener, "update_tech_debt_scan_log", lambda findings: None)
    opened: list[tuple[doc_gardener.DocFinding, ...]] = []
    monkeypatch.setattr(doc_gardener, "open_fixup_pr", lambda findings: opened.append(tuple(findings)) or True)

    assert doc_gardener.main(["--open-fixup-pr"]) == 1

    out = capsys.readouterr().out
    assert "Attempting to open fix-up PR..." in out
    assert opened == [(finding,)]


def test_doc_gardener_flags_retired_source_file_reintroduced(tmp_path):
    debt_file = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    debt_file.parent.mkdir(parents=True)
    debt_file.write_text(
        """
## Consolidation Source Ledger

| Source | State | Snapshot | Sync Basis | Coverage | Notes |
|---|---|---|---|---|---|
| TODO_GUI.md | retired | 2026-04-29 | retired | Program E | Imported |
| TODO_REFACTOR.md | retired | 2026-04-29 | retired | Program B | Imported |
| TODO_SATTLINT.md | retired | 2026-04-29 | retired | Program C | Imported |
| TODO_TOOLS.md | retired | 2026-04-29 | retired | Program D | Imported |
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "TODO_GUI.md").write_text("restored backlog\n", encoding="utf-8")

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_source_drift()

    assert len(findings) == 1
    assert findings[0].category == "drift"
    assert "marks it retired" in findings[0].message


def test_doc_gardener_flags_refactor_status_mismatch(tmp_path):
    debt_file = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    debt_file.parent.mkdir(parents=True)
    debt_file.write_text(
        """
## Program B: Refactor And Architecture Debt

| Debt ID | Priority | Owner | Target Window | Source Lane | Item | Status | Notes |
|---|---|---|---|---|---|---|---|
| B-W6 | P0 | Parser core | 2026-Q2 | W6 | Parser structural split for SLTransformer | Open | Still underway |
""".strip(),
        encoding="utf-8",
    )
    coordination_dir = tmp_path / ".github" / "coordination"
    coordination_dir.mkdir(parents=True)
    (coordination_dir / "current_work_lock.json").write_text(
        json.dumps(
            {
                "workstreams": [
                    {
                        "workstream_id": "w6-parser-transformer-split-068",
                        "owner": "Copilot",
                        "status": "active",
                        "claimed_paths": ["src/sattlint/core/parser.py"],
                        "updated_at": coordination_lock_state.utc_now_timestamp(),
                        "first_validation": "pytest tests/test_repo_audit.py -x -q --tb=short",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_status_drift()

    assert len(findings) == 1
    assert findings[0].category == "stale_status"
    assert "B-W6" in findings[0].message


def test_doc_gardener_main_exits_nonzero_when_findings_exist():
    result = {
        "total_findings": 1,
        "by_severity": {"Critical": 0, "High": 0, "Medium": 1, "Low": 0},
        "by_category": {
            "stale": 0,
            "dead_link": 0,
            "too_long": 0,
            "missing": 0,
            "structure": 0,
            "encoding": 1,
            "drift": 0,
            "stale_status": 0,
        },
        "findings": [
            {
                "file": "docs/exec-plans/active/ai-first-repo-hardening.md",
                "line": 1,
                "severity": "Medium",
                "category": "encoding",
                "message": "Possible mojibake tokens in markdown content: �",
            }
        ],
    }

    with (
        patch.object(doc_gardener, "run_scan", return_value=result),
        patch.object(doc_gardener, "update_quality_score"),
        patch.object(doc_gardener, "update_tech_debt_scan_log"),
        patch.object(doc_gardener, "open_fixup_pr", return_value=False),
    ):
        assert doc_gardener.main() == 1


def test_doc_gardener_main_uses_pipeline_output_dir(monkeypatch, capsys, tmp_path):
    finding = doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link")
    pipeline_dir = tmp_path / "custom-analysis"
    pipeline_snapshot = doc_gardener.PipelineSnapshot(
        output_dir=pipeline_dir,
        profile="quick",
        overall_status="pass",
        normalized_findings=0,
        coverage_total_line_rate=None,
    )
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        doc_gardener,
        "run_scan",
        lambda: {
            "total_findings": 1,
            "by_severity": {severity: (1 if severity == "Medium" else 0) for severity in doc_gardener.SEVERITY_ORDER},
            "by_category": {
                category: (1 if category == "dead_link" else 0) for category in doc_gardener.CATEGORY_ORDER
            },
            "findings": [finding._asdict()],
        },
    )

    def fake_load_pipeline_snapshot(output_dir):
        observed["pipeline_dir"] = output_dir
        return pipeline_snapshot, None

    monkeypatch.setattr(doc_gardener, "load_pipeline_snapshot", fake_load_pipeline_snapshot)
    monkeypatch.setattr(
        doc_gardener,
        "update_quality_score",
        lambda findings, pipeline_snapshot=None: observed.setdefault(
            "quality_score_call",
            (tuple(findings), pipeline_snapshot),
        ),
    )
    monkeypatch.setattr(doc_gardener, "update_tech_debt_scan_log", lambda findings: None)
    monkeypatch.setattr(doc_gardener, "open_fixup_pr", lambda findings: False)

    assert doc_gardener.main(["--pipeline-output-dir", str(pipeline_dir)]) == 1

    _out = capsys.readouterr().out
    assert observed["pipeline_dir"] == pipeline_dir
    assert observed["quality_score_call"] == ((finding,), pipeline_snapshot)
