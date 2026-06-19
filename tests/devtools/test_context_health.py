# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_context_health_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "context_health.py"
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
    _write_text(tmp_path / "docs" / "maintainers" / "repo-map.md", "# Repo Map\n")
    _write_text(tmp_path / "docs" / "public" / "architecture.md", "# Architecture\n")
    _write_text(tmp_path / "docs" / "maintainers" / "quality-gates.md", "# Quality Gates\n")
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
                "auto_loaded": ["AGENTS.md"],
                "scoped_globs": [".github/instructions/*.md"],
            },
            "required_paths": {
                "docs": [
                    "docs/maintainers/repo-map.md",
                    "docs/public/architecture.md",
                    "docs/maintainers/quality-gates.md",
                ],
                "vscode": [".vscode/settings.json", ".vscode/extensions.json"],
            },
            "context_optimizer": {"extension_id": "wanderleyferreiradealbuquerque.context-optimizer"},
        },
    )
    return tmp_path / "metrics" / "ratchet.json"


def test_build_report_passes_without_legacy_ai_contract_paths(monkeypatch, tmp_path):
    ratchet_path = _write_repo_fixture(tmp_path)

    monkeypatch.setattr(context_health, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(context_health, "RATCHET_PATH", ratchet_path)
    monkeypatch.setattr(context_health, "SETTINGS_PATH", tmp_path / ".vscode" / "settings.json")
    monkeypatch.setattr(context_health, "EXTENSIONS_PATH", tmp_path / ".vscode" / "extensions.json")

    report = context_health.build_report()

    assert report["status"] == "pass"
    assert report["issues"] == []


def test_build_report_fails_for_missing_required_path(monkeypatch, tmp_path):
    ratchet_path = _write_repo_fixture(tmp_path)
    (tmp_path / "docs" / "maintainers" / "repo-map.md").unlink()

    monkeypatch.setattr(context_health, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(context_health, "RATCHET_PATH", ratchet_path)
    monkeypatch.setattr(context_health, "SETTINGS_PATH", tmp_path / ".vscode" / "settings.json")
    monkeypatch.setattr(context_health, "EXTENSIONS_PATH", tmp_path / ".vscode" / "extensions.json")

    report = context_health.build_report()

    assert report["status"] == "fail"
    assert any(issue["id"] == "missing-required-path" for issue in report["issues"])
