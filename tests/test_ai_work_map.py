import json

from sattlint.devtools import ai_work_map
from sattlint.devtools.ai_work_map import (
    DEFAULT_OUTPUT_PATH,
    DEFAULT_SESSION_CONTEXT_OUTPUT_PATH,
    build_ai_work_map,
    build_planning_context,
    build_session_context_map,
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
    assert any(check["id"] == "ruff" for check in manifest["pipeline_checks"])
    assert any(check["id"] == "documented-commands" for check in manifest["repo_audit_checks"])
    assert any(check["id"] == "harness-freshness" for check in manifest["repo_audit_checks"])


def test_build_ai_work_map_collects_owner_suite_plans():
    manifest = build_ai_work_map()
    plan = next(
        entry
        for entry in manifest["owner_suite_plans"]
        if entry["plan_path"].endswith("14-coverage-phase-2-app-devtools-core.md")
    )

    assert any("tests/test_repo_audit.py" in suite["tests"] for suite in plan["suites"])
    assert any(
        command.endswith("tests/test_repo_audit.py -x -q --tb=short") for command in plan["first_validation_commands"]
    )


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


def test_build_planning_context_returns_agent_instruction_and_owner_suite_matches():
    planning = build_planning_context(
        changed_files=["src/sattlint/app.py"],
        recommended_check_ids=["cli"],
        selected_surface="repo-audit",
        work_map=build_ai_work_map(),
    )

    assert planning["primary_agent"] == "CLI App Menu"
    assert planning["owner_surfaces"] == ["cli"]
    assert planning["owner_test_targets"] == ["tests/test_repo_audit.py"]
    assert any(item["name"] == "CLI App Instructions" for item in planning["instruction_files"])
    assert any("tests/test_app.py" in suite["tests"] for suite in planning["nearest_owner_suites"])
    assert any("tests/test_app.py" in command for command in planning["first_validation_commands"])
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
    assert any("tests/test_app.py" in suite["tests"] for suite in planning["nearest_owner_suites"])
    assert planning["first_validation_commands"]
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

    monkeypatch.setattr(ai_work_map, "render_ai_work_map", lambda: '{"kind": "work"}\n')
    monkeypatch.setattr(ai_work_map, "render_session_context_map", lambda: '{"kind": "session"}\n')

    assert (
        ai_work_map.main(
            [
                "--write",
                "--output",
                str(output_path),
                "--session-output",
                str(session_output_path),
            ]
        )
        == 0
    )
    assert json.loads(output_path.read_text(encoding="utf-8")) == {"kind": "work"}
    assert json.loads(session_output_path.read_text(encoding="utf-8")) == {"kind": "session"}
    assert (
        ai_work_map.main(["--check", "--output", str(output_path), "--session-output", str(session_output_path)]) == 0
    )

    output_path.write_text('{"kind": "stale"}\n', encoding="utf-8")

    assert (
        ai_work_map.main(["--check", "--output", str(output_path), "--session-output", str(session_output_path)]) == 1
    )

    capsys.readouterr()

    assert (
        ai_work_map.main(["--stdout", "--output", str(output_path), "--session-output", str(session_output_path)]) == 0
    )
    assert json.loads(capsys.readouterr().out) == {"kind": "work"}


def test_verify_ai_harness_freshness_reports_generated_map_and_metadata_drift(tmp_path):
    (tmp_path / "src" / "sattlint").mkdir(parents=True)
    (tmp_path / "src" / "sattlint" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    output_path = tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json"
    session_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-session-context-map.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    session_output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('{"kind": "stale"}\n', encoding="utf-8")
    session_output_path.write_text('{"kind": "stale-session"}\n', encoding="utf-8")

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
    }
    session_context_map = {"kind": "session-map", "instructions": [], "agents": []}

    report = verify_ai_harness_freshness(
        work_map=work_map,
        session_context_map=session_context_map,
        repo_root=tmp_path,
        output_path=output_path,
        session_output_path=session_output_path,
    )

    assert report["status"] == "fail"
    assert {issue["issue_id"] for issue in report["issues"]} == {
        "generated-ai-work-map-drift",
        "generated-ai-session-context-map-drift",
        "stale-instruction-applyto-glob",
        "orphaned-instruction",
        "stale-agent-routing-glob",
        "dangling-agent-routing",
        "orphaned-agent",
    }


def test_verify_ai_harness_freshness_passes_for_live_metadata(tmp_path):
    (tmp_path / "src" / "sattlint").mkdir(parents=True)
    (tmp_path / "src" / "sattlint" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    output_path = tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json"
    session_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-session-context-map.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    session_output_path.parent.mkdir(parents=True, exist_ok=True)

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
    }
    session_context_map = {"kind": "session-map", "instructions": [], "agents": []}
    output_path.write_text(json.dumps(work_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    session_output_path.write_text(json.dumps(session_context_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = verify_ai_harness_freshness(
        work_map=work_map,
        session_context_map=session_context_map,
        repo_root=tmp_path,
        output_path=output_path,
        session_output_path=session_output_path,
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
                "plan_path": "docs/exec-plans/active/14-coverage-phase-2-app-devtools-core.md",
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
    assert planning["instruction_files"] == [
        {
            "name": "CLI App Instructions",
            "file_path": ".github/instructions/cli-app.instructions.md",
            "description": "cli",
            "matched_files": ["src/sattlint/app.py"],
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
