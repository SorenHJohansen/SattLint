import json

from sattlint.devtools.ai_work_map import render_ai_check_catalog, verify_ai_harness_freshness


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


def test_verify_ai_harness_freshness_covers_missing_outputs_and_backslash_metadata(tmp_path):
    (tmp_path / "src" / "sattlint").mkdir(parents=True)
    (tmp_path / "src" / "sattlint" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    output_path = tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-work-map.json"
    session_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-session-context-map.json"
    )
    check_catalog_output_path = (
        tmp_path / ".github" / "skills" / "validation-routing" / "references" / "ai-check-catalog.md"
    )

    work_map = {
        "instructions": [
            {
                "name": "Windows Style Instruction",
                "file_path": ".github/instructions/windows.instructions.md",
                "apply_to": [r"src\\sattlint\\app.py"],
            }
        ],
        "agents": [
            {
                "name": "Live Agent",
                "file_path": ".github/agents/live.agent.md",
                "user_invocable": True,
            }
        ],
        "agent_routing": [
            "ignored",
            {"agent_name": "   ", "path_globs": ["src/sattlint/app.py"]},
            {"agent_name": "Live Agent", "path_globs": []},
            {"agent_name": "Live Agent", "path_globs": [r"src\\sattlint\\app.py"]},
        ],
        "pipeline_checks": [
            "ignored",
            {"id": "   ", "ai_summary": "ignored", "ai_instruction_files": [".github/instructions/live.md"]},
            {
                "id": "ruff",
                "source": "pipeline",
                "ai_summary": "lint summary",
                "ai_instruction_files": [r".github\\instructions\\windows.instructions.md"],
            },
        ],
        "repo_audit_checks": [],
    }

    report = verify_ai_harness_freshness(
        work_map=work_map,
        session_context_map={"kind": "session-map", "instructions": [], "agents": []},
        repo_root=tmp_path,
        output_path=output_path,
        session_output_path=session_output_path,
        check_catalog_output_path=check_catalog_output_path,
    )

    assert report["status"] == "fail"
    assert {issue["issue_id"] for issue in report["issues"]} == {
        "missing-generated-ai-work-map",
        "missing-generated-ai-session-context-map",
        "missing-generated-ai-check-catalog",
        "backslash-instruction-applyto-glob",
        "orphaned-agent-routing",
        "backslash-agent-routing-glob",
        "backslash-check-instruction-path",
    }
