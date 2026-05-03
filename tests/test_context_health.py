from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_context_health_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "context_health.py"
    spec = importlib.util.spec_from_file_location("context_health", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


context_health = _load_context_health_module()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> None:
    _write_text(path, json.dumps(payload, indent=2) + "\n")


def _write_repo_fixture(tmp_path: Path) -> Path:
    _write_text(tmp_path / "AGENTS.md", "# AGENTS\n")
    _write_text(tmp_path / "docs" / "context-loading-order.md", "# Context\n")
    _write_text(tmp_path / "docs" / "repo-map.md", "# Repo Map\n")
    _write_json(
        tmp_path / ".vscode" / "settings.json",
        {"contextOptimizer.autoLoadedLineThreshold": 80},
    )
    _write_json(
        tmp_path / ".vscode" / "extensions.json",
        {"recommendations": ["wanderleyferreiradealbuquerque.context-optimizer"]},
    )
    _write_json(
        tmp_path / "metrics" / "ratchet.json",
        {
            "thresholds": {
                "agents_max_lines": 100,
                "repo_map_max_lines": 220,
                "auto_loaded_context_max_lines": 180,
                "context_optimizer_auto_loaded_line_threshold": 80,
            },
            "context_files": {
                "auto_loaded": ["AGENTS.md", "docs/context-loading-order.md"],
                "scoped_globs": [".github/agents/*.agent.md"],
            },
            "required_paths": {
                "docs": ["docs/repo-map.md"],
                "vscode": [".vscode/settings.json", ".vscode/extensions.json"],
                "ai": [".ai/tasks/task-contract.schema.json", ".ai/handoffs/handoff.schema.json"],
            },
            "context_optimizer": {"extension_id": "wanderleyferreiradealbuquerque.context-optimizer"},
        },
    )
    _write_json(
        tmp_path / ".ai" / "tasks" / "task-contract.schema.json",
        {
            "type": "object",
            "required": ["task_id", "files"],
            "properties": {
                "task_id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
                "files": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "uniqueItems": True,
                },
            },
            "additionalProperties": False,
        },
    )
    _write_json(
        tmp_path / ".ai" / "handoffs" / "handoff.schema.json",
        {
            "type": "object",
            "required": ["task_id", "validation_status"],
            "properties": {
                "task_id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$"},
                "validation_status": {
                    "type": "object",
                    "required": ["state", "commands"],
                    "properties": {
                        "state": {"type": "string", "enum": ["pending", "failed", "passed"]},
                        "commands": {
                            "type": "array",
                            "items": {"type": "string", "minLength": 1},
                            "minItems": 1,
                        },
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
    )
    _write_json(
        tmp_path / ".ai" / "tasks" / "task-contract.example.json",
        {"task_id": "t-001-demo", "files": ["src/demo.py"]},
    )
    _write_json(
        tmp_path / ".ai" / "handoffs" / "handoff.example.json",
        {"task_id": "t-001-demo", "validation_status": {"state": "pending", "commands": ["pytest"]}},
    )
    return tmp_path / "metrics" / "ratchet.json"


def test_build_report_passes_for_schema_valid_ai_artifacts(monkeypatch, tmp_path):
    ratchet_path = _write_repo_fixture(tmp_path)

    monkeypatch.setattr(context_health, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(context_health, "RATCHET_PATH", ratchet_path)
    monkeypatch.setattr(context_health, "SETTINGS_PATH", tmp_path / ".vscode" / "settings.json")
    monkeypatch.setattr(context_health, "EXTENSIONS_PATH", tmp_path / ".vscode" / "extensions.json")

    report = context_health.build_report()

    assert report["status"] == "pass"
    assert report["metrics"]["validated_ai_artifact_count"] == 2
    assert report["issues"] == []


def test_build_report_fails_for_schema_invalid_ai_artifact(monkeypatch, tmp_path):
    ratchet_path = _write_repo_fixture(tmp_path)
    _write_json(tmp_path / ".ai" / "tasks" / "broken.json", {"task_id": "bad"})

    monkeypatch.setattr(context_health, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(context_health, "RATCHET_PATH", ratchet_path)
    monkeypatch.setattr(context_health, "SETTINGS_PATH", tmp_path / ".vscode" / "settings.json")
    monkeypatch.setattr(context_health, "EXTENSIONS_PATH", tmp_path / ".vscode" / "extensions.json")

    report = context_health.build_report()

    assert report["status"] == "fail"
    assert any(issue["id"] == "invalid-ai-artifact-schema" for issue in report["issues"])
