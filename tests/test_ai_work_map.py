import json
import sys
from pathlib import Path

import pytest

from sattlint.devtools import ai_work_map
from sattlint.devtools._semble_adapter import SembleMatch, SembleSearchResponse
from sattlint.devtools.ai_work_map import (
    DEFAULT_CHECK_CATALOG_OUTPUT_PATH,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_SESSION_CONTEXT_OUTPUT_PATH,
    build_ai_work_map,
    build_planning_context,
    build_session_context_map,
    render_ai_check_catalog,
    render_ai_work_map,
    render_session_context_map,
)


def test_build_ai_work_map_contains_validation_routes_and_catalogs():
    manifest = build_ai_work_map()

    assert manifest["kind"] == "sattlint.ai_work_map"
    assert manifest["schema_version"] == 1
    assert manifest["default_entrypoint"]["id"] == "planning-context"
    assert any(route["surface"].startswith("Parser, grammar") for route in manifest["validation_routes"])
    assert any(rule["id"] == "focused-validation-first" for rule in manifest["blocking_invariant_rules"])
    assert any(entry["name"] == "CLI App Instructions" for entry in manifest["instructions"])
    assert any(entry["name"] == "CLI App Menu" for entry in manifest["agents"])
    assert any(entry["name"] == "Planner" and entry["user_invocable"] is False for entry in manifest["agents"])
    assert any(entry["name"] == "Test Agent" and entry["user_invocable"] is False for entry in manifest["agents"])
    assert any(entry["name"] == "Reviewer Agent" and entry["user_invocable"] is False for entry in manifest["agents"])
    assert any(check["id"] == "ruff" for check in manifest["pipeline_checks"])
    assert any(check["id"] == "documented-commands" for check in manifest["repo_audit_checks"])
    assert any(check["id"] == "harness-freshness" for check in manifest["repo_audit_checks"])
    assert any(check["ai_summary"] for check in manifest["pipeline_checks"])
    assert any(check["ai_instruction_files"] for check in manifest["repo_audit_checks"])


def test_build_ai_work_map_collects_owner_suite_plans():
    manifest = build_ai_work_map()

    assert manifest["owner_suite_plans"] == []


def test_build_session_context_map_keeps_only_session_start_routing_fields():
    manifest = build_session_context_map(build_ai_work_map())

    assert manifest["kind"] == "sattlint.ai_session_context_map"
    assert manifest["schema_version"] == 1
    assert manifest["default_entrypoint"]["id"] == "planning-context"
    assert "pipeline_checks" not in manifest
    assert "repo_audit_checks" not in manifest
    assert "validation_routes" not in manifest
    assert any(entry["name"] == "CLI App Menu" for entry in manifest["agents"])


def test_checked_in_ai_work_map_matches_live_build():
    expected = json.loads(render_ai_work_map())
    actual = json.loads(DEFAULT_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert actual == expected


def test_checked_in_ai_session_context_map_matches_live_build():
    expected = json.loads(render_session_context_map())
    actual = json.loads(DEFAULT_SESSION_CONTEXT_OUTPUT_PATH.read_text(encoding="utf-8"))

    assert actual == expected


def test_checked_in_ai_check_catalog_matches_live_build():
    expected = render_ai_check_catalog()
    actual = DEFAULT_CHECK_CATALOG_OUTPUT_PATH.read_text(encoding="utf-8")

    assert actual == expected


def test_build_planning_context_returns_agent_instruction_and_owner_suite_matches():
    planning = build_planning_context(
        changed_files=["src/sattlint/app.py"],
        recommended_check_ids=["cli"],
        selected_surface="repo-audit",
        work_map=build_ai_work_map(),
    )

    assert planning["primary_agent"] == "CLI App Menu"
    assert planning["owner_surfaces"] == ["cli"]
    assert planning["relevant_checks"][0]["id"] == "cli"
    assert planning["relevant_checks"][0]["ai_instruction_files"] == [".github/instructions/cli-app.instructions.md"]
    assert planning["owner_test_targets"] == ["tests/test_repo_audit_part1.py"]
    assert any(item["name"] == "CLI App Instructions" for item in planning["instruction_files"])
    assert any("recommended-check:cli" in item["selection_reasons"] for item in planning["instruction_files"])
    assert planning["nearest_owner_suites"] == []
    assert planning["first_validation_commands"] == []
    assert planning["finish_gate_template"]["selected_surface"] == "repo-audit"
    assert any(rule["id"] == "focused-validation-first" for rule in planning["blocking_invariants"])
    assert any(rule["id"] == "cli-menu-tests-stay-in-sync" for rule in planning["blocking_invariants"])
    assert planning["semantic_owner_suggestions"]["status"] == "not_requested"


def test_build_planning_context_session_map_supports_session_start_without_full_catalogs():
    planning = build_planning_context(
        changed_files=["src/sattlint/app.py"],
        recommended_check_ids=None,
        selected_surface="session-start",
        work_map=build_session_context_map(build_ai_work_map()),
    )

    assert planning["primary_agent"] == "CLI App Menu"
    assert planning["nearest_owner_suites"] == []
    assert planning["first_validation_commands"] == []
    assert planning["finish_gate_template"] is None
    assert any(rule["id"] == "focused-validation-first" for rule in planning["blocking_invariants"])
    assert planning["semantic_owner_suggestions"]["status"] == "not_requested"


def test_build_planning_context_includes_semantic_owner_suggestions(monkeypatch):
    monkeypatch.setattr(
        ai_work_map,
        "search_local_repo",
        lambda query, *, repo_root, top_k: SembleSearchResponse(
            available=True,
            backend="python-library",
            query=query,
            repo_path=repo_root.as_posix(),
            top_k=top_k,
            results=(
                SembleMatch(
                    file_path="src/sattlint/app.py",
                    start_line=10,
                    end_line=20,
                    content="def cli(): ...",
                    score=0.91,
                ),
            ),
            explanation="ok",
        ),
    )

    planning = build_planning_context(
        changed_files=["docs/notes.md"],
        recommended_check_ids=["cli"],
        selected_surface="repo-audit",
        semantic_query="interactive cli menu numbering",
        work_map=build_ai_work_map(),
    )

    assert planning["semantic_owner_suggestions"] == {
        "status": "ok",
        "query": "interactive cli menu numbering",
        "backend": "python-library",
        "suggestions": [
            {
                "file_path": "src/sattlint/app.py",
                "start_line": 10,
                "end_line": 20,
                "score": 0.91,
                "matched_agent_names": ["CLI App Menu", "Documentation Generation", "Repo Audit"],
                "matched_instruction_names": [
                    "CLI App Instructions",
                    "Repo Map Instructions",
                    "SattLine Invariants",
                ],
                "matched_owner_surfaces": ["cli"],
            }
        ],
        "explanation": "ok",
    }


def test_ai_work_map_planning_helpers_cover_empty_paths_and_unmatched_rules():
    work_map = {
        "instructions": [
            {"file_path": "", "name": "ignored"},
            {"file_path": ".github/instructions/cli.instructions.md", "name": "CLI", "apply_to": ["src/app.py"]},
        ],
        "pipeline_checks": ["ignore-me", {"id": "ruff"}],
        "repo_audit_checks": [{"id": "cli"}],
        "agents": [{"name": "CLI Agent"}],
        "agent_routing": [
            "ignore-me",
            {"agent_name": "CLI Agent", "path_globs": ["docs/**"], "selected_surfaces": ["repo-audit"]},
        ],
        "finish_gate_templates": ["ignore-me", {"selected_surface": "repo-audit", "command": "run", "includes": []}],
    }

    instruction_lookup = ai_work_map._instruction_lookup(work_map)
    all_checks = ai_work_map._all_check_entries(work_map)
    merged_instructions = ai_work_map._merge_instruction_files_for_planning(
        work_map,
        ["src/app.py"],
        [{"id": "cli", "ai_instruction_files": ["", ".github/instructions/cli.instructions.md"]}],
    )
    owner_suites = ai_work_map._match_owner_suites(
        {
            "owner_suite_plans": [
                {
                    "plan_path": "plan.md",
                    "suites": [{"tests": ["tests/test_alpha.py"], "targets": ["src/pkg/alpha.py"]}],
                    "first_validation_commands": [],
                }
            ]
        },
        changed_files=["docs/readme.md"],
        owner_test_targets=["tests/test_other.py"],
    )
    matched_agents = ai_work_map._match_agents(work_map, ["src/app.py"], ["cli"], "repo-audit")
    finish_gate_template = ai_work_map._select_finish_gate_template(work_map, "repo-audit")

    assert instruction_lookup == {".github/instructions/cli.instructions.md": work_map["instructions"][1]}
    assert [entry["id"] for entry in all_checks] == ["ruff", "cli"]
    assert merged_instructions == [
        {
            "name": "CLI",
            "file_path": ".github/instructions/cli.instructions.md",
            "description": "",
            "matched_files": ["src/app.py"],
            "selection_reasons": ["changed-files", "recommended-check:cli"],
        }
    ]
    assert owner_suites == []
    assert matched_agents == [
        {
            "name": "CLI Agent",
            "file_path": "",
            "description": "",
            "matched_files": [],
            "matched_owner_surfaces": [],
            "score": 1,
        }
    ]
    assert finish_gate_template == {
        "selected_surface": "repo-audit",
        "command": "run",
        "description": "",
        "includes": [],
    }


def test_merge_instruction_files_for_planning_skips_blank_matched_file_paths(monkeypatch):
    monkeypatch.setattr(
        ai_work_map,
        "_match_instruction_files",
        lambda _work_map, _changed_files: [{"file_path": "", "matched_files": ["src/app.py"]}],
    )

    merged = ai_work_map._merge_instruction_files_for_planning({"instructions": []}, ["src/app.py"], [])

    assert merged == []


def test_write_ai_check_catalog_and_module_main(tmp_path, monkeypatch):
    import runpy

    catalog_path = tmp_path / "nested" / "ai-check-catalog.md"
    monkeypatch.setattr(ai_work_map, "render_ai_check_catalog", lambda work_map=None: "# Catalog\n")

    written_path = ai_work_map.write_ai_check_catalog(catalog_path)

    assert written_path == catalog_path
    assert catalog_path.read_text(encoding="utf-8") == "# Catalog\n"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ai_work_map",
            "--check",
            "--output",
            str(tmp_path / "missing-work.json"),
            "--session-output",
            str(tmp_path / "missing-session.json"),
            "--reference-output",
            str(tmp_path / "missing-reference.md"),
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("sattlint.devtools.ai_work_map", run_name="__main__")

    assert exit_info.value.code == 1


def test_load_and_write_work_maps_cover_fallback_and_persistence(tmp_path, monkeypatch):
    work_path = tmp_path / "work.json"
    session_path = tmp_path / "session.json"

    monkeypatch.setattr(ai_work_map, "build_ai_work_map", lambda: {"kind": "built-work"})
    monkeypatch.setattr(ai_work_map, "build_session_context_map", lambda: {"kind": "built-session"})

    assert ai_work_map.load_ai_work_map(work_path) == {"kind": "built-work"}
    assert ai_work_map.load_session_context_map(session_path) == {"kind": "built-session"}

    work_path.write_text('{"kind": "stored-work"}', encoding="utf-8")
    session_path.write_text('{"kind": "stored-session"}', encoding="utf-8")

    assert ai_work_map.load_ai_work_map(work_path) == {"kind": "stored-work"}
    assert ai_work_map.load_session_context_map(session_path) == {"kind": "stored-session"}

    work_path.write_text("{bad-json", encoding="utf-8")
    session_path.write_text("{bad-json", encoding="utf-8")

    assert ai_work_map.load_ai_work_map(work_path) == {"kind": "built-work"}
    assert ai_work_map.load_session_context_map(session_path) == {"kind": "built-session"}

    monkeypatch.setattr(ai_work_map, "render_ai_work_map", lambda: '{"kind": "written-work"}\n')
    monkeypatch.setattr(ai_work_map, "render_session_context_map", lambda: '{"kind": "written-session"}\n')

    written_work = ai_work_map.write_ai_work_map(tmp_path / "nested" / "written-work.json")
    written_session = ai_work_map.write_session_context_map(tmp_path / "nested" / "written-session.json")

    assert json.loads(written_work.read_text(encoding="utf-8")) == {"kind": "written-work"}
    assert json.loads(written_session.read_text(encoding="utf-8")) == {"kind": "written-session"}


def test_main_write_check_and_stdout_modes(tmp_path, monkeypatch, capsys):
    output_path = tmp_path / "ai-work-map.json"
    session_output_path = tmp_path / "ai-session-context-map.json"
    reference_output_path = tmp_path / "ai-check-catalog.md"
    archived_state = {"archived": False, "calls": 0}

    def fake_archive_completed_exec_plans():
        archived_state["archived"] = True
        archived_state["calls"] += 1
        return []

    monkeypatch.setattr(ai_work_map, "archive_completed_exec_plans", fake_archive_completed_exec_plans)
    monkeypatch.setattr(
        ai_work_map,
        "render_ai_work_map",
        lambda: json.dumps({"kind": "work", "archived": archived_state["archived"]}) + "\n",
    )
    monkeypatch.setattr(ai_work_map, "render_session_context_map", lambda: '{"kind": "session"}\n')
    monkeypatch.setattr(ai_work_map, "render_ai_check_catalog", lambda: "# Reference\n")

    assert (
        ai_work_map.main(
            [
                "--write",
                "--output",
                str(output_path),
                "--session-output",
                str(session_output_path),
                "--reference-output",
                str(reference_output_path),
            ]
        )
        == 0
    )
    assert json.loads(output_path.read_text(encoding="utf-8")) == {"kind": "work", "archived": True}
    assert json.loads(session_output_path.read_text(encoding="utf-8")) == {"kind": "session"}
    assert reference_output_path.read_text(encoding="utf-8") == "# Reference\n"
    assert output_path.read_bytes() == b'{"kind": "work", "archived": true}\n'
    assert session_output_path.read_bytes() == b'{"kind": "session"}\n'
    assert reference_output_path.read_bytes() == b"# Reference\n"
    assert archived_state["archived"] is True
    assert archived_state["calls"] == 1

    assert (
        ai_work_map.main(
            [
                "--check",
                "--output",
                str(output_path),
                "--session-output",
                str(session_output_path),
                "--reference-output",
                str(reference_output_path),
            ]
        )
        == 0
    )
    assert archived_state["calls"] == 1

    output_path.write_text('{"kind": "stale"}\n', encoding="utf-8")

    assert (
        ai_work_map.main(
            [
                "--check",
                "--output",
                str(output_path),
                "--session-output",
                str(session_output_path),
                "--reference-output",
                str(reference_output_path),
            ]
        )
        == 1
    )

    capsys.readouterr()

    assert (
        ai_work_map.main(
            [
                "--stdout",
                "--output",
                str(output_path),
                "--session-output",
                str(session_output_path),
                "--reference-output",
                str(reference_output_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"kind": "work", "archived": True}
    assert archived_state["calls"] == 1


def test_main_returns_failure_when_write_output_fails(tmp_path, monkeypatch, capsys):
    output_path = tmp_path / "ai-work-map.json"
    session_output_path = tmp_path / "ai-session-context-map.json"
    reference_output_path = tmp_path / "ai-check-catalog.md"

    monkeypatch.setattr(ai_work_map, "archive_completed_exec_plans", lambda: [])
    monkeypatch.setattr(ai_work_map, "render_ai_work_map", lambda: '{"kind": "work"}\n')
    monkeypatch.setattr(ai_work_map, "render_session_context_map", lambda: '{"kind": "session"}\n')
    monkeypatch.setattr(ai_work_map, "render_ai_check_catalog", lambda: "# Reference\n")

    original_write_text = Path.write_text

    def _write_text(self: Path, *args, **kwargs):
        if self == output_path:
            raise PermissionError("locked")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", _write_text)

    exit_code = ai_work_map.main(
        [
            "--write",
            "--output",
            str(output_path),
            "--session-output",
            str(session_output_path),
            "--reference-output",
            str(reference_output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "ai work map output error: locked" in captured.err


def test_build_planning_context_ignores_invalid_entries_and_matches_owner_surfaces():
    work_map = {
        "default_entrypoint": {"id": "planning-context"},
        "finish_gate_templates": [
            {
                "selected_surface": "repo-audit",
                "command": "repo-audit --finish-gate",
                "description": "repo",
                "includes": ["ruff"],
            }
        ],
        "blocking_invariant_rules": [
            {
                "id": "focused-validation-first",
                "summary": "focused",
                "details": "details",
                "selected_surfaces": ["repo-audit"],
                "path_globs": [],
            },
            "ignore-me",
        ],
        "pipeline_checks": ["ignore-me"],
        "repo_audit_checks": [
            {
                "id": "cli",
                "owner_surface": "cli",
                "owner_test_targets": ["tests/test_app.py"],
                "ai_summary": "cli summary",
                "ai_instruction_files": [".github/instructions/cli-app.instructions.md"],
            }
        ],
        "instructions": [
            7,
            {
                "name": "CLI App Instructions",
                "file_path": ".github/instructions/cli-app.instructions.md",
                "description": "cli",
                "apply_to": ["src/sattlint/app.py"],
            },
        ],
        "agents": [
            3,
            {
                "name": "CLI App Menu",
                "file_path": ".github/agents/cli-app-menu.agent.md",
                "description": "cli",
            },
        ],
        "agent_routing": [
            {},
            {
                "agent_name": "CLI App Menu",
                "path_globs": ["src/sattlint/app.py"],
                "owner_surface_keywords": ["cli"],
                "selected_surfaces": ["repo-audit"],
            },
        ],
        "owner_suite_plans": [
            "ignore-me",
            {
                "plan_path": "docs/exec-plans/completed/14-coverage-phase-2-app-devtools-core.md",
                "suites": [
                    {
                        "tests": ["tests/test_app.py"],
                        "targets": ["src/sattlint/app.py"],
                    },
                    "bad-suite",
                ],
                "first_validation_commands": ["pytest tests/test_app.py -x -q --tb=short"],
            },
        ],
    }

    planning = build_planning_context(
        changed_files=["src\\sattlint\\app.py"],
        recommended_check_ids=["cli", "missing"],
        selected_surface="repo-audit",
        work_map=work_map,
    )

    assert planning["primary_agent"] == "CLI App Menu"
    assert planning["default_entrypoint"] == {"id": "planning-context"}
    assert planning["relevant_checks"] == [
        {
            "id": "cli",
            "owner_surface": "cli",
            "owner_test_targets": ["tests/test_app.py"],
            "ai_summary": "cli summary",
            "ai_instruction_files": [".github/instructions/cli-app.instructions.md"],
        }
    ]
    assert planning["instruction_files"] == [
        {
            "name": "CLI App Instructions",
            "file_path": ".github/instructions/cli-app.instructions.md",
            "description": "cli",
            "matched_files": ["src/sattlint/app.py"],
            "selection_reasons": ["changed-files", "recommended-check:cli"],
        }
    ]
    assert planning["owner_surfaces"] == ["cli"]
    assert planning["owner_test_targets"] == ["tests/test_app.py"]
    assert planning["nearest_owner_suites"][0]["matched_targets"] == ["src/sattlint/app.py"]
    assert planning["first_validation_commands"] == ["pytest tests/test_app.py -x -q --tb=short"]
    assert planning["finish_gate_template"] == {
        "selected_surface": "repo-audit",
        "command": "repo-audit --finish-gate",
        "description": "repo",
        "includes": ["ruff"],
    }
    assert planning["blocking_invariants"] == [
        {
            "id": "focused-validation-first",
            "summary": "focused",
            "details": "details",
            "matched_files": [],
        }
    ]
    assert planning["semantic_owner_suggestions"]["status"] == "not_requested"
