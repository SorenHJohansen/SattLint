"""Headless Change Review command tests: artifacts, exit codes, output directory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from sattlint.application import change_review as change_review_application
from sattlint.cli.entry import run_cli
from tests.helpers.change_review_support import (
    DRAFT_PROGRAM,
    OFFICIAL_PROGRAM,
    build_cfg,
    write_project,
)

pytestmark = pytest.mark.unit


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz: object = None) -> _FixedDateTime:
        return cls(2026, 11, 19, 10, 20, 30, 123456, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.config_path_location", lambda: tmp_path / "config.toml")


def _freeze_review_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sattlint.change_review.review.datetime", _FixedDateTime)


def _write_project(
    tmp_path: Path,
    *,
    program_dir: Path,
    targets: list[str] | None = None,
) -> Path:
    project = tmp_path / "demo.slproj"
    resolved_targets = ["Demo"] if targets is None else targets
    project.write_text(
        "\n".join(
            [
                "slproj_version = 2",
                f"analyzed_programs_and_libraries = {json.dumps(resolved_targets)}",
                "analyzers = []",
                'mode = "draft"',
                f"program_dir = {json.dumps(str(program_dir))}",
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
            ]
        ),
        encoding="utf-8",
    )
    return project


def _synthetic_project(tmp_path: Path, *, targets: list[str] | None = None) -> tuple[Path, Path]:
    program_dir = tmp_path / "programs"
    write_project(program_dir, name="Demo", official_text=OFFICIAL_PROGRAM, draft_text=DRAFT_PROGRAM)
    project = _write_project(tmp_path, program_dir=program_dir, targets=targets)
    return project, program_dir


def test_headless_review_matches_the_tui_application_artifacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, program_dir = _synthetic_project(tmp_path)
    _freeze_review_time(monkeypatch)

    cli_dir = tmp_path / "cli-review"
    code = run_cli(["review", "--project", str(project), "--output-dir", str(cli_dir), "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "review"
    assert payload["project"] == str(project)
    assert payload["output_dir"] == str(cli_dir.resolve())
    assert payload["generated_targets"] == 1
    assert payload["failed_targets"] == 0
    assert payload["failures"] == []
    assert len(payload["targets"]) == 1
    entry = payload["targets"][0]
    assert entry["target"] == "Demo"
    cli_json = Path(entry["json"]).read_bytes()
    cli_markdown = Path(entry["markdown"]).read_bytes()

    cfg = build_cfg(tmp_path, program_dir=program_dir)
    tui_dir = tmp_path / "tui-review"
    change_review_application.generate_change_review(cfg, ["Demo"], output_dir=tui_dir)

    tui_json = next(tui_dir.glob("*.json"))
    tui_markdown = next(tui_dir.glob("*.md"))
    assert cli_json == tui_json.read_bytes()
    assert cli_markdown == tui_markdown.read_bytes()


def test_review_creates_a_missing_output_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project, _program_dir = _synthetic_project(tmp_path)
    output_dir = tmp_path / "nested" / "change-review"

    code = run_cli(["review", "--project", str(project), "--output-dir", str(output_dir)])

    captured = capsys.readouterr()
    assert code == 0
    assert output_dir.is_dir()
    generated = sorted(output_dir.iterdir())
    assert len(generated) == 2
    assert {path.suffix for path in generated} == {".json", ".md"}
    assert str(output_dir.resolve()) in captured.out
    for path in generated:
        assert str(path.resolve()) in captured.out


def test_review_returns_one_for_a_partial_target_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project, _program_dir = _synthetic_project(tmp_path, targets=["Demo", "Missing"])

    code = run_cli(["review", "--project", str(project), "--output-dir", str(tmp_path / "out"), "--format", "json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["generated_targets"] == 1
    assert payload["failed_targets"] == 1
    assert [entry["target"] for entry in payload["targets"]] == ["Demo"]
    assert [failure["target"] for failure in payload["failures"]] == ["Missing"]
    assert payload["failures"][0]["message"]


def test_review_returns_two_when_no_artifacts_were_generated(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project, _program_dir = _synthetic_project(tmp_path, targets=["Missing"])

    code = run_cli(["review", "--project", str(project), "--output-dir", str(tmp_path / "out"), "--format", "json"])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error"]["code"] == "review_failed"
    assert error["error"]["details"]["failures"][0]["target"] == "Missing"


def test_review_returns_two_for_a_missing_project(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = run_cli(["review", "--project", str(tmp_path / "missing.slproj"), "--format", "json"])

    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error["error"]["code"] == "project_not_found"


def test_review_returns_two_when_no_targets_are_configured(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project, _program_dir = _synthetic_project(tmp_path, targets=[])

    code = run_cli(["review", "--project", str(project), "--format", "json"])

    captured = capsys.readouterr()
    assert code == 2
    error = json.loads(captured.err)
    assert error["error"]["code"] == "no_targets"


def test_review_returns_two_for_an_unusable_output_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project, _program_dir = _synthetic_project(tmp_path)
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")

    code = run_cli(["review", "--project", str(project), "--output-dir", str(blocked), "--format", "json"])

    captured = capsys.readouterr()
    assert code == 2
    error = json.loads(captured.err)
    assert error["error"]["code"] == "review_output_dir"


def test_review_rejects_an_unknown_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project, _program_dir = _synthetic_project(tmp_path)

    code = run_cli(["review", "--project", str(project), "--target", "Absent", "--format", "json"])

    captured = capsys.readouterr()
    assert code == 2
    error = json.loads(captured.err)
    assert error["error"]["code"] == "unknown_target"


def test_review_rejects_a_blank_target(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project, _program_dir = _synthetic_project(tmp_path)

    code = run_cli(["review", "--project", str(project), "--target", " ", "--format", "json"])

    captured = capsys.readouterr()
    assert code == 2
    error = json.loads(captured.err)
    assert error["error"]["code"] == "usage_error"
