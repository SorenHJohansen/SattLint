"""`project show` renders the merged effective analysis settings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sattlint.cli.entry import run_cli


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.config_path_location", lambda: tmp_path / "config.toml")


def _write_project(root: Path) -> Path:
    project = root / "app.slproj"
    project.write_text(
        "\n".join(
            [
                "slproj_version = 2",
                'analyzed_programs_and_libraries = ["Demo"]',
                'analyzers = ["variables"]',
                'mode = "official"',
                'program_dir = "."',
                'ABB_lib_dir = ""',
                'icf_dir = ""',
                "other_lib_dirs = []",
                "",
                "[string_capacities]",
                "identstring = 15",
                "tagstring = 30",
                "string = 40",
                "linestring = 80",
                "maxstring = 140",
                "",
                "[analysis]",
                "cyclomatic_module_threshold = 7",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project


def test_project_show_reports_effective_analysis_settings(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = _write_project(tmp_path)

    code = run_cli(["project", "show", "--project", str(project), "--format", "json"])

    assert code == 0
    analysis = json.loads(capsys.readouterr().out)["project"]["analysis"]
    assert analysis["cyclomatic_module_threshold"] == 7
    assert analysis["source_byte_limit"] == 8 * 1024 * 1024
    assert analysis["module_grid"] == 0.02
    assert analysis["unsafe_default_tokens"] == ["bypass", "enable"]


def test_project_show_text_names_the_effective_defaults(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = _write_project(tmp_path)

    code = run_cli(["project", "show", "--project", str(project)])

    assert code == 0
    output = capsys.readouterr().out
    assert "cyclomatic_module_threshold: 7" in output
    assert "source_byte_limit: 8388608" in output
