# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
# ruff: noqa: F403, F405
from ._repo_audit_test_support import *


def test_doc_gardener_updates_quality_score_and_scan_log(tmp_path):
    docs_dir = tmp_path / "docs" / "exec-plans" / "active"
    docs_dir.mkdir(parents=True)
    markdown_file = docs_dir / "ai-first-repo-hardening.md"
    markdown_file.write_text(f"Broken sequence {doc_gardener.MOJIBAKE_TOKENS[1]} here\n", encoding="utf-8")

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_markdown_encoding_artifacts()

    assert len(findings) == 1
    assert findings[0].category == "encoding"
    assert findings[0].file == "docs/exec-plans/active/ai-first-repo-hardening.md"


def test_doc_gardener_read_text_falls_back_to_cp1252(tmp_path):
    sample = tmp_path / "notes.md"
    sample.write_bytes("Author: S\xf8ren\n".encode("cp1252"))

    assert doc_gardener._read_text(sample) == "Author: S\xf8ren\n"


def test_doc_gardener_iter_markdown_files_skips_venv_and_non_markdown(tmp_path):
    markdown = tmp_path / "docs" / "guide.md"
    markdown.parent.mkdir(parents=True)
    markdown.write_text("guide\n", encoding="utf-8")
    text_file = tmp_path / "notes.txt"
    text_file.write_text("notes\n", encoding="utf-8")
    python_file = tmp_path / "script.py"
    python_file.write_text("print('nope')\n", encoding="utf-8")
    skipped = tmp_path / ".venv-docs" / "skip.md"
    skipped.parent.mkdir(parents=True)
    skipped.write_text("skip\n", encoding="utf-8")

    with patch.object(doc_gardener, "REPO_ROOT", tmp_path):
        files = {path.relative_to(tmp_path).as_posix() for path in doc_gardener._iter_markdown_files()}

    assert files == {"docs/guide.md", "notes.txt"}


def test_doc_gardener_parse_markdown_table_handles_invalid_rows_and_section_breaks():
    rows = doc_gardener._parse_markdown_table(
        [
            "ignored intro",
            "## Target Section",
            "",
            "| Col A | Col B |",
            "|---|---|",
            "| keep | row |",
            "| too | many | cells |",
            "not a table row",
            "| skipped | after break |",
        ],
        "## Target Section",
    )

    assert rows == [(6, {"Col A": "keep", "Col B": "row"})]


def test_doc_gardener_scan_agents_md_reports_missing_and_structure_findings(tmp_path):
    with _patch_doc_gardener_paths(tmp_path):
        missing_findings = doc_gardener.scan_agents_md()

    assert missing_findings == [doc_gardener.DocFinding("AGENTS.md", 0, "Critical", "missing", "AGENTS.md not found")]

    agents = tmp_path / "AGENTS.md"
    agents.write_text("line\n" * 101, encoding="utf-8")

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_agents_md()

    assert any(finding.category == "too_long" for finding in findings)
    assert {finding.message for finding in findings if finding.category == "structure"} == {
        "Missing section: Quick Reference",
        "Missing section: Repo Map",
        "Missing section: Key Docs",
        "Missing section: Critical Invariants",
    }


def test_doc_gardener_scan_dead_links_and_structure_findings(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True)
    valid_target = docs_dir / "existing.md"
    valid_target.write_text("exists\n", encoding="utf-8")
    readme = docs_dir / "index.md"
    readme.write_text(
        "[good](existing.md)\n[bad](missing.md)\n[ext](https://example.com)\n[anchor](#here)\n[mail](mailto:test@example.com)\n",
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        dead_link_findings = doc_gardener.scan_dead_links()
        structure_findings = doc_gardener.scan_docs_structure()

    assert dead_link_findings == [
        doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "Broken link: missing.md")
    ]
    assert structure_findings == [
        doc_gardener.DocFinding("docs/", 0, "High", "structure", "Missing directory: docs/design-docs"),
        doc_gardener.DocFinding("docs/", 0, "High", "structure", "Missing directory: docs/references"),
        doc_gardener.DocFinding("docs/", 0, "High", "missing", "Missing file: docs/quality-score.md"),
        doc_gardener.DocFinding("docs/", 0, "High", "missing", "Missing file: docs/design-docs/core-beliefs.md"),
        doc_gardener.DocFinding("docs/", 0, "High", "missing", "Missing file: docs/design-docs/index.md"),
    ]


def test_doc_gardener_scan_completed_exec_plans_still_active(tmp_path):
    active_dir = tmp_path / "docs" / "exec-plans" / "active"
    active_dir.mkdir(parents=True)
    (active_dir / "done.md").write_text(
        "\n".join(
            [
                "# Done",
                "",
                "## Progress",
                "",
                "- [x] one",
                "- [x] two",
            ]
        ),
        encoding="utf-8",
    )
    (active_dir / "active.md").write_text(
        "\n".join(
            [
                "# Active",
                "",
                "## Progress",
                "",
                "- [x] one",
                "- [ ] two",
            ]
        ),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_completed_exec_plans_still_active()

    assert findings == [
        doc_gardener.DocFinding(
            "docs/exec-plans/active/done.md",
            1,
            "High",
            "stale",
            "ExecPlan Progress is fully complete but the file still lives under docs/exec-plans/active/. Move it to docs/exec-plans/completed/.",
        )
    ]


def test_doc_gardener_scan_ai_first_source_drift_reports_missing_ledger_section(tmp_path):
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True)
    tech_debt.write_text("# Tracker\n", encoding="utf-8")

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_source_drift()

    assert findings == [
        doc_gardener.DocFinding(
            "docs/exec-plans/tech-debt-tracker.md",
            1,
            "High",
            "structure",
            "Missing consolidation source ledger in the canonical tech debt tracker.",
        )
    ]


def test_doc_gardener_scan_ai_first_source_drift_reports_row_and_digest_issues(tmp_path):
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True)
    (tmp_path / "TODO_GUI.md").write_text("gui drift\n", encoding="utf-8")
    (tmp_path / "TODO_REFACTOR.md").write_text("retired but present\n", encoding="utf-8")

    tech_debt.write_text(
        "\n".join(
            [
                "## Consolidation Source Ledger",
                "| Source | State | Sync Basis |",
                "| --- | --- | --- |",
                "| TODO_GUI.md | active | sha1:deadbeefdead |",
                "| TODO_REFACTOR.md | retired | sha1:ignored |",
                "| TODO_SATTLINT.md |  | retired |",
                "| TODO_TOOLS.md | active | manual-sync |",
            ]
        ),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_source_drift()

    messages = {finding.message for finding in findings}
    assert any(
        message.startswith("TODO_GUI.md drifted from the source-ledger sync basis (sha1:deadbeefdead != sha1:")
        for message in messages
    )
    assert "TODO_REFACTOR.md exists but the source ledger marks it retired." in messages
    assert "Source-ledger row for TODO_SATTLINT.md is missing a State value." in messages
    assert "TODO_TOOLS.md is marked active in the source ledger but the file is missing." in messages


def test_doc_gardener_scan_ai_first_status_drift_reports_mismatch(tmp_path):
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
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True)
    tech_debt.write_text(
        "\n".join(
            [
                "## Program B: Refactor And Architecture Debt",
                "| Debt ID | Status |",
                "| --- | --- |",
                "| W1 | Done |",
                "| W2 | blocked |",
            ]
        ),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_status_drift()

    assert findings == [
        doc_gardener.DocFinding(
            "docs/exec-plans/tech-debt-tracker.md",
            4,
            "Medium",
            "stale_status",
            "W1 status is 'Done' but the active coordination lock state tracks 'In progress'.",
        )
    ]


def test_doc_gardener_scan_ai_first_status_drift_falls_back_to_template_when_local_ledger_missing(tmp_path):
    template = tmp_path / ".github" / "coordination" / "current-work.template.md"
    template.parent.mkdir(parents=True)
    template.write_text(
        "\n".join(
            [
                "### Workstream W1-something",
                "- Status: active",
                "- Claims: `src/demo.py`",
            ]
        ),
        encoding="utf-8",
    )
    tech_debt = tmp_path / "docs" / "exec-plans" / "tech-debt-tracker.md"
    tech_debt.parent.mkdir(parents=True)
    tech_debt.write_text(
        "\n".join(
            [
                "## Program B: Refactor And Architecture Debt",
                "| Debt ID | Status |",
                "| --- | --- |",
                "| W1 | Done |",
            ]
        ),
        encoding="utf-8",
    )

    with _patch_doc_gardener_paths(tmp_path):
        findings = doc_gardener.scan_ai_first_status_drift()

    assert findings == []


def test_doc_gardener_run_scan_aggregates_findings(monkeypatch):
    monkeypatch.setattr(
        doc_gardener,
        "scan_agents_md",
        lambda: [doc_gardener.DocFinding("AGENTS.md", 1, "High", "missing", "missing")],
    )
    monkeypatch.setattr(
        doc_gardener,
        "scan_dead_links",
        lambda: [doc_gardener.DocFinding("docs/index.md", 2, "Medium", "dead_link", "dead")],
    )
    monkeypatch.setattr(doc_gardener, "scan_docs_structure", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_markdown_encoding_artifacts", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_ai_first_source_drift", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_ai_first_status_drift", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_completed_exec_plans_still_active", lambda: [])
    monkeypatch.setattr(doc_gardener, "scan_stale_docs", lambda: [])

    result = doc_gardener.run_scan()

    assert result["total_findings"] == 2
    assert result["by_severity"]["High"] == 1
    assert result["by_severity"]["Medium"] == 1
    assert result["by_category"]["missing"] == 1
    assert result["by_category"]["dead_link"] == 1
    assert len(result["findings"]) == 2


def test_run_harness_freshness_check_translates_ai_and_doc_findings(monkeypatch, tmp_path):
    captured_kwargs: dict[str, Any] = {}

    def _verify_ai_harness_freshness(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "issues": [
                {
                    "issue_id": "generated-ai-work-map-drift",
                    "severity": "high",
                    "message": "ai map drift",
                    "path": "docs/maintainers/ai/ai-work-map.json",
                }
            ]
        }

    monkeypatch.setattr(
        repo_audit._ai_work_map_module,
        "verify_ai_harness_freshness",
        _verify_ai_harness_freshness,
    )
    monkeypatch.setattr(repo_audit, "_patch_doc_gardener_paths", lambda root: nullcontext())
    monkeypatch.setattr(
        repo_audit._doc_gardener_module,
        "scan_agents_md",
        lambda: [doc_gardener.DocFinding("AGENTS.md", 101, "High", "too_long", "AGENTS too long")],
    )
    monkeypatch.setattr(
        repo_audit._doc_gardener_module,
        "scan_dead_links",
        lambda: [doc_gardener.DocFinding("docs/index.md", 4, "Medium", "dead_link", "Broken link")],
    )
    monkeypatch.setattr(
        repo_audit._doc_gardener_module,
        "scan_completed_exec_plans_still_active",
        lambda: [
            doc_gardener.DocFinding(
                "docs/exec-plans/active/done.md",
                1,
                "High",
                "stale",
                "completed plan still active",
            )
        ],
    )
    monkeypatch.setattr(repo_audit._doc_gardener_module, "scan_stale_docs", lambda: [])

    findings = repo_audit.run_harness_freshness_check(cast(Any, SimpleNamespace(root=tmp_path)))

    assert captured_kwargs["output_path"] == repo_audit._ai_work_map_module.DEFAULT_OUTPUT_PATH
    assert captured_kwargs["session_output_path"] == repo_audit._ai_work_map_module.DEFAULT_SESSION_CONTEXT_OUTPUT_PATH
    assert (
        captured_kwargs["check_catalog_output_path"] == repo_audit._ai_work_map_module.DEFAULT_CHECK_CATALOG_OUTPUT_PATH
    )
    assert {(finding.id, finding.path) for finding in findings} == {
        (
            "harness-generated-ai-work-map-drift",
            "docs/maintainers/ai/ai-work-map.json",
        ),
        ("harness-too-long", "AGENTS.md"),
        ("harness-dead-link", "docs/index.md"),
        ("harness-stale", "docs/exec-plans/active/done.md"),
    }
    assert {finding.category for finding in findings} == {"harness-freshness"}


def test_progress_active_stage_key_returns_none_for_non_mapping_payload() -> None:
    progress = SimpleNamespace(to_dict=lambda: [])

    result = repo_audit._audit_orchestration_module._progress_active_stage_key(progress)

    assert result is None


def test_progress_active_stage_key_returns_none_for_missing_active_stage_mapping() -> None:
    progress = SimpleNamespace(to_dict=lambda: {"active_stage": []})

    result = repo_audit._audit_orchestration_module._progress_active_stage_key(progress)

    assert result is None
