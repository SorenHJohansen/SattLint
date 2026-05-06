import json
import sys
from typing import Any, cast

import pytest

from sattlint.devtools import ai_work_map
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
    verify_ai_harness_freshness,
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
    assert planning["owner_test_targets"] == ["tests/test_repo_audit.py"]
    assert any(item["name"] == "CLI App Instructions" for item in planning["instruction_files"])
    assert any("recommended-check:cli" in item["selection_reasons"] for item in planning["instruction_files"])
    assert planning["nearest_owner_suites"] == []
    assert planning["first_validation_commands"] == []
    assert planning["finish_gate_template"]["selected_surface"] == "repo-audit"
    assert any(rule["id"] == "focused-validation-first" for rule in planning["blocking_invariants"])
    assert any(rule["id"] == "cli-menu-tests-stay-in-sync" for rule in planning["blocking_invariants"])


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


def test_parse_frontmatter_handles_plain_files_lists_and_booleans(tmp_path):
    plain = tmp_path / "plain.md"
    plain.write_text("body\n", encoding="utf-8")

    assert ai_work_map._parse_frontmatter(plain) == {}

    frontmatter = tmp_path / "agent.agent.md"
    frontmatter.write_text(
        "\n".join(
            [
                "---",
                'name: "Repo Audit"',
                "user-invocable: true",
                "enabled: false",
                'applyTo: ["src/sattlint/devtools/**", "tests/test_repo_audit.py"]',
                "globs: [src/sattlint/devtools/**, tests/test_repo_audit.py]",
                'owners: ["Copilot", "Human"]',
                "empty: []",
                "---",
                "body",
            ]
        ),
        encoding="utf-8",
    )

    payload = ai_work_map._parse_frontmatter(frontmatter)

    assert payload == {
        "name": "Repo Audit",
        "user-invocable": True,
        "enabled": False,
        "applyTo": ["src/sattlint/devtools/**", "tests/test_repo_audit.py"],
        "globs": ["src/sattlint/devtools/**", "tests/test_repo_audit.py"],
        "owners": ["Copilot", "Human"],
        "empty": [],
    }


def test_parse_plan_helpers_extract_routes_owner_suites_and_first_validations(tmp_path):
    routes_file = tmp_path / "routes.md"
    routes_file.write_text(
        "\n".join(
            [
                "Intro",
                "- Parser surface:",
                "  use `cmd one` first",
                "  then inspect nearby helpers",
                "- Repo audit:",
                "  `cmd two`",
            ]
        ),
        encoding="utf-8",
    )
    plan = tmp_path / "plan.md"
    plan.write_text(
        "\n".join(
            [
                "Primary owner suites for this plan:",
                "- `tests/test_alpha.py` -> `src/pkg/alpha.py`",
                "- `tests/test_beta.py`",
                "Per-slice first validations:",
                "    pytest tests/test_alpha.py -x -q --tb=short",
                "    pytest tests/test_beta.py -x -q --tb=short",
                "",
                "Tail",
            ]
        ),
        encoding="utf-8",
    )

    routes = ai_work_map._parse_validation_routes(routes_file)
    suites = ai_work_map._parse_owner_suites(plan)
    first_validation_commands = ai_work_map._parse_first_validation_commands(plan)

    assert routes == [
        {
            "surface": "Parser surface",
            "commands": ["cmd one"],
            "notes": ["use  first", "then inspect nearby helpers"],
        },
        {
            "surface": "Repo audit",
            "commands": ["cmd two"],
            "notes": [],
        },
    ]
    assert suites == [
        {
            "tests": ["tests/test_alpha.py"],
            "targets": ["src/pkg/alpha.py"],
            "target_summary": "`src/pkg/alpha.py`",
        },
        {
            "tests": ["tests/test_beta.py"],
            "targets": [],
            "target_summary": "`tests/test_beta.py`",
        },
    ]
    assert first_validation_commands == [
        "pytest tests/test_alpha.py -x -q --tb=short",
        "pytest tests/test_beta.py -x -q --tb=short",
    ]


def test_parse_progress_checkbox_states_stops_after_progress_section(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "\n".join(
            [
                "# Example Plan",
                "",
                "## Progress",
                "",
                "- [x] first done step",
                "- [ ] remaining step",
                "",
                "## Surprises & Discoveries",
                "",
                "- [ ] not a progress checkbox",
            ]
        ),
        encoding="utf-8",
    )

    assert ai_work_map._parse_progress_checkbox_states(plan) == [True, False]
    assert ai_work_map._is_completed_exec_plan(plan) is False


def test_archive_completed_exec_plans_moves_only_fully_checked_plans(tmp_path):
    repo_root = tmp_path
    active_dir = tmp_path / "docs" / "exec-plans" / "active"
    completed_dir = tmp_path / "docs" / "exec-plans" / "completed"
    active_dir.mkdir(parents=True)

    completed_plan = active_dir / "done.md"
    completed_plan.write_text(
        "\n".join(
            [
                "# Done",
                "",
                "## Progress",
                "",
                "- [x] step one",
                "- [x] step two",
                "",
                "## Outcomes & Retrospective",
                "",
                "See docs/exec-plans/active/done.md for the original path.",
                "",
                "Closed.",
            ]
        ),
        encoding="utf-8",
    )
    note_file = repo_root / "notes.md"
    note_file.write_text("Reference: docs/exec-plans/active/done.md\n", encoding="utf-8")
    active_plan = active_dir / "active.md"
    active_plan.write_text(
        "\n".join(
            [
                "# Active",
                "",
                "## Progress",
                "",
                "- [x] first step",
                "- [ ] remaining step",
            ]
        ),
        encoding="utf-8",
    )

    archived = ai_work_map.archive_completed_exec_plans(active_dir=active_dir, completed_dir=completed_dir)

    assert archived == [{"from": "docs/exec-plans/active/done.md", "to": "docs/exec-plans/completed/done.md"}]
    assert not completed_plan.exists()
    moved_plan = completed_dir / "done.md"
    assert moved_plan.exists()
    assert "docs/exec-plans/completed/done.md" in moved_plan.read_text(encoding="utf-8")
    assert note_file.read_text(encoding="utf-8") == "Reference: docs/exec-plans/completed/done.md\n"
    assert active_plan.exists()


def test_ai_work_map_reference_update_helpers_cover_skip_and_decode_edges(tmp_path, monkeypatch):
    class _FakePath:
        def __init__(self, *, suffix: str, relative_parts: tuple[str, ...] | None = None, fail_relative: bool = False):
            self.suffix = suffix
            self._relative_parts = relative_parts
            self._fail_relative = fail_relative

        def is_file(self) -> bool:
            return True

        def relative_to(self, _repo_root):
            if self._fail_relative:
                raise ValueError("outside root")
            assert self._relative_parts is not None
            return type("RelativePath", (), {"parts": self._relative_parts})()

    class _FakeRepoRoot:
        def __init__(self, paths: list[_FakePath]):
            self._paths = paths

        def rglob(self, _pattern: str) -> list[_FakePath]:
            return self._paths

    invalid_path = _FakePath(suffix=".md", fail_relative=True)
    skipped_path = _FakePath(suffix=".md", relative_parts=(".venv-cache", "ignored.md"))
    kept_path = _FakePath(suffix=".md", relative_parts=("docs", "plan.md"))

    files = ai_work_map._iter_reference_update_files(cast(Any, _FakeRepoRoot([invalid_path, skipped_path, kept_path])))
    ai_work_map._rewrite_exec_plan_references([], repo_root=tmp_path)

    undecodable = tmp_path / "notes.md"
    undecodable.write_bytes(b"\xff")
    monkeypatch.setattr(ai_work_map, "_iter_reference_update_files", lambda _repo_root: [undecodable])
    ai_work_map._rewrite_exec_plan_references(
        [{"from": "docs/exec-plans/active/one.md", "to": "docs/exec-plans/completed/one.md"}],
        repo_root=tmp_path,
    )

    assert files == [kept_path]
    assert undecodable.read_bytes() == b"\xff"


def test_archive_completed_exec_plans_raises_when_destination_already_exists(tmp_path):
    active_dir = tmp_path / "docs" / "exec-plans" / "active"
    completed_dir = tmp_path / "docs" / "exec-plans" / "completed"
    active_dir.mkdir(parents=True)
    completed_dir.mkdir(parents=True)

    plan = active_dir / "done.md"
    plan.write_text("## Progress\n\n- [x] done\n", encoding="utf-8")
    (completed_dir / "done.md").write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Completed exec plan already exists"):
        ai_work_map.archive_completed_exec_plans(active_dir=active_dir, completed_dir=completed_dir)


def test_ai_work_map_parsers_cover_ignored_lines_and_plan_collection(tmp_path, monkeypatch):
    frontmatter = tmp_path / "agent.instructions.md"
    frontmatter.write_text("---\nname: Demo\nnot-a-field\n---\nbody\n", encoding="utf-8")
    routes_file = tmp_path / "routes.md"
    routes_file.write_text(
        "\n".join(
            [
                "Intro",
                "- Parser:",
                "  ",
                "  `cmd one`",
                "  note",
            ]
        ),
        encoding="utf-8",
    )
    plan = tmp_path / "plan.md"
    plan.write_text(
        "\n".join(
            [
                "Primary owner suites for this plan:",
                "note before suites",
                "- `tests/test_alpha.py` -> `src/pkg/alpha.py`",
                "",
                "Per-slice first validations:",
                "",
                "    pytest tests/test_alpha.py -x -q --tb=short",
                "Tail",
            ]
        ),
        encoding="utf-8",
    )
    exec_plans_dir = tmp_path / "plans"
    exec_plans_dir.mkdir()
    collected_plan = exec_plans_dir / "alpha.md"
    collected_plan.write_text(plan.read_text(encoding="utf-8"), encoding="utf-8")

    payload = ai_work_map._parse_frontmatter(frontmatter)
    routes = ai_work_map._parse_validation_routes(routes_file)
    suites = ai_work_map._parse_owner_suites(plan)
    commands = ai_work_map._parse_first_validation_commands(plan)
    monkeypatch.setattr(ai_work_map, "REPO_ROOT", tmp_path)

    collected = ai_work_map._collect_owner_suite_plans(exec_plans_dir)

    assert payload == {"name": "Demo"}
    assert routes == [{"surface": "Parser", "commands": ["cmd one"], "notes": ["note"]}]
    assert suites == [
        {
            "tests": ["tests/test_alpha.py"],
            "targets": ["src/pkg/alpha.py"],
            "target_summary": "`src/pkg/alpha.py`",
        }
    ]
    assert commands == ["pytest tests/test_alpha.py -x -q --tb=short"]
    assert collected[0]["plan_path"].endswith("alpha.md")


def test_ai_work_map_parsers_skip_blank_and_non_command_lines_before_collecting(tmp_path):
    owner_suites_plan = tmp_path / "owner-suites.md"
    owner_suites_plan.write_text(
        "\n".join(
            [
                "Primary owner suites for this plan:",
                "",
                "note before suites",
                "- `tests/test_alpha.py` -> `src/pkg/alpha.py`",
            ]
        ),
        encoding="utf-8",
    )
    first_validations_plan = tmp_path / "first-validations.md"
    first_validations_plan.write_text(
        "\n".join(
            [
                "Per-slice first validations:",
                "misc note",
                "    pytest tests/test_alpha.py -x -q --tb=short",
            ]
        ),
        encoding="utf-8",
    )

    suites = ai_work_map._parse_owner_suites(owner_suites_plan)
    commands = ai_work_map._parse_first_validation_commands(first_validations_plan)

    assert suites == [
        {
            "tests": ["tests/test_alpha.py"],
            "targets": ["src/pkg/alpha.py"],
            "target_summary": "`src/pkg/alpha.py`",
        }
    ]
    assert commands == ["pytest tests/test_alpha.py -x -q --tb=short"]


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


def test_verify_ai_harness_freshness_reports_generated_map_and_metadata_drift(tmp_path):
    (tmp_path / "src" / "sattlint").mkdir(parents=True)
    (tmp_path / "src" / "sattlint" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    output_path = tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json"
    session_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-session-context-map.json"
    )
    check_catalog_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-check-catalog.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    session_output_path.parent.mkdir(parents=True, exist_ok=True)
    check_catalog_output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('{"kind": "stale"}\n', encoding="utf-8")
    session_output_path.write_text('{"kind": "stale-session"}\n', encoding="utf-8")
    check_catalog_output_path.write_text("stale\n", encoding="utf-8")

    work_map = {
        "instructions": [
            {
                "name": "Live Instruction",
                "file_path": ".github/instructions/live.instructions.md",
                "apply_to": ["src/sattlint/app.py", "docs/missing/**"],
            },
            {
                "name": "Broken Instruction",
                "file_path": ".github/instructions/broken.instructions.md",
                "apply_to": [],
            },
        ],
        "agents": [
            {
                "name": "Live Agent",
                "file_path": ".github/agents/live.agent.md",
                "user_invocable": True,
            },
            {
                "name": "Orphan Agent",
                "file_path": ".github/agents/orphan.agent.md",
                "user_invocable": True,
            },
            {
                "name": "Internal Agent",
                "file_path": ".github/agents/internal.agent.md",
                "user_invocable": False,
            },
        ],
        "agent_routing": [
            {
                "agent_name": "Live Agent",
                "path_globs": ["src/sattlint/app.py", "docs/ghost/**"],
                "owner_surface_keywords": ["cli"],
                "selected_surfaces": ["repo-audit"],
            },
            {
                "agent_name": "Missing Agent",
                "path_globs": ["src/sattlint/app.py"],
                "owner_surface_keywords": ["cli"],
                "selected_surfaces": ["repo-audit"],
            },
        ],
        "pipeline_checks": [
            {
                "id": "ruff",
                "source": "pipeline",
                "ai_summary": "",
                "ai_instruction_files": [],
            }
        ],
        "repo_audit_checks": [
            {
                "id": "cli",
                "source": "repo-audit",
                "ai_summary": "cli summary",
                "ai_instruction_files": [".github/instructions/missing.instructions.md"],
            }
        ],
    }
    session_context_map = {"kind": "session-map", "instructions": [], "agents": []}

    report = verify_ai_harness_freshness(
        work_map=work_map,
        session_context_map=session_context_map,
        repo_root=tmp_path,
        output_path=output_path,
        session_output_path=session_output_path,
        check_catalog_output_path=check_catalog_output_path,
    )

    assert report["status"] == "fail"
    assert {issue["issue_id"] for issue in report["issues"]} == {
        "generated-ai-work-map-drift",
        "generated-ai-session-context-map-drift",
        "generated-ai-check-catalog-drift",
        "stale-instruction-applyto-glob",
        "orphaned-instruction",
        "stale-agent-routing-glob",
        "dangling-agent-routing",
        "orphaned-agent",
        "undocumented-check",
        "unmapped-check",
        "dangling-check-instruction",
    }


def test_verify_ai_harness_freshness_passes_for_live_metadata(tmp_path):
    (tmp_path / "src" / "sattlint").mkdir(parents=True)
    (tmp_path / "src" / "sattlint" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    instruction_path = tmp_path / ".github" / "instructions" / "cli-app.instructions.md"
    instruction_path.parent.mkdir(parents=True, exist_ok=True)
    instruction_path.write_text(
        '---\nname: "CLI App Instructions"\napplyTo: ["src/sattlint/app.py"]\n---\n', encoding="utf-8"
    )
    output_path = tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json"
    session_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-session-context-map.json"
    )
    check_catalog_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-check-catalog.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    session_output_path.parent.mkdir(parents=True, exist_ok=True)
    check_catalog_output_path.parent.mkdir(parents=True, exist_ok=True)

    work_map = {
        "instructions": [
            {
                "name": "CLI App Instructions",
                "file_path": ".github/instructions/cli-app.instructions.md",
                "apply_to": ["src/sattlint/app.py"],
            }
        ],
        "agents": [
            {
                "name": "CLI App Menu",
                "file_path": ".github/agents/cli-app-menu.agent.md",
                "user_invocable": True,
            }
        ],
        "agent_routing": [
            {
                "agent_name": "CLI App Menu",
                "path_globs": ["src/sattlint/app.py"],
                "owner_surface_keywords": ["cli"],
                "selected_surfaces": ["repo-audit"],
            }
        ],
        "pipeline_checks": [],
        "repo_audit_checks": [
            {
                "id": "cli",
                "source": "repo-audit",
                "label": "CLI",
                "owner_surface": "cli",
                "estimated_cost": "low",
                "owner_test_targets": ["tests/test_repo_audit.py"],
                "ai_summary": "cli summary",
                "ai_instruction_files": [".github/instructions/cli-app.instructions.md"],
                "command": "repo-audit --check cli",
            }
        ],
    }
    session_context_map = {"kind": "session-map", "instructions": [], "agents": []}
    output_path.write_text(json.dumps(work_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    session_output_path.write_text(json.dumps(session_context_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    check_catalog_output_path.write_text(render_ai_check_catalog(work_map), encoding="utf-8")

    report = verify_ai_harness_freshness(
        work_map=work_map,
        session_context_map=session_context_map,
        repo_root=tmp_path,
        output_path=output_path,
        session_output_path=session_output_path,
        check_catalog_output_path=check_catalog_output_path,
    )

    assert report["status"] == "pass"
    assert report["issues"] == []


def test_verify_ai_harness_freshness_allows_virtual_git_lock_glob(tmp_path):
    agent_path = tmp_path / ".github" / "agents" / "sattlint-orchestrator.agent.md"
    output_path = tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json"
    session_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-session-context-map.json"
    )
    check_catalog_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-check-catalog.md"
    )
    agent_path.parent.mkdir(parents=True, exist_ok=True)
    agent_path.write_text("# Orchestrator\n", encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    session_output_path.parent.mkdir(parents=True, exist_ok=True)
    check_catalog_output_path.parent.mkdir(parents=True, exist_ok=True)

    work_map = {
        "instructions": [],
        "agents": [
            {
                "name": "SattLint Orchestrator",
                "file_path": ".github/agents/sattlint-orchestrator.agent.md",
                "user_invocable": True,
            }
        ],
        "agent_routing": [
            {
                "agent_name": "SattLint Orchestrator",
                "path_globs": [".git/sattlint-ai-coordination/current_work_lock.json"],
                "owner_surface_keywords": ["structural"],
                "selected_surfaces": ["repo-audit"],
            }
        ],
        "pipeline_checks": [],
        "repo_audit_checks": [],
    }
    session_context_map = {"kind": "session-map", "instructions": [], "agents": []}
    output_path.write_text(json.dumps(work_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    session_output_path.write_text(json.dumps(session_context_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    check_catalog_output_path.write_text(render_ai_check_catalog(work_map), encoding="utf-8")

    report = verify_ai_harness_freshness(
        work_map=work_map,
        session_context_map=session_context_map,
        repo_root=tmp_path,
        output_path=output_path,
        session_output_path=session_output_path,
        check_catalog_output_path=check_catalog_output_path,
    )

    assert report["status"] == "pass"
    assert report["issues"] == []


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
