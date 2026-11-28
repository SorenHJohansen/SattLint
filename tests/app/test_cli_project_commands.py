"""Project discovery commands: init, targets, and check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sattlint.cli.entry import run_cli


@pytest.fixture(autouse=True)
def _isolate_user_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("sattlint.cli._project.config_path_location", lambda: tmp_path / "config.toml")


def _write_program(root: Path, name: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{name}.x"
    path.write_text("(* module *)\n", encoding="utf-8")
    return path


def _write_project(
    root: Path,
    targets: list[str],
    *,
    abb: Path | None = None,
    analyzers: list[str] | None = None,
    icf_dir: str = "",
) -> Path:
    programs = root / "programs"
    programs.mkdir(parents=True, exist_ok=True)
    project = root / ".slproj"
    project.write_text(
        "\n".join(
            [
                "slproj_version = 2",
                f"analyzed_programs_and_libraries = {json.dumps(targets)}",
                f"analyzers = {json.dumps(analyzers or ['variables'])}",
                'mode = "official"',
                'program_dir = "programs"',
                f'ABB_lib_dir = "{abb or ""}"',
                f'icf_dir = "{icf_dir}"',
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


def test_project_init_creates_a_minimal_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_program(tmp_path, "Demo")

    code = run_cli(["project", "init"])

    assert code == 0
    project = tmp_path / ".slproj"
    assert project.is_file()
    assert 'program_dir = "."' in project.read_text(encoding="utf-8")
    assert "Created project" in capsys.readouterr().out
    assert run_cli(["project", "check"]) == 0
    capsys.readouterr()

    code = run_cli(["project", "targets", "--format", "json"])

    assert code == 0
    assert [target["name"] for target in json.loads(capsys.readouterr().out)["targets"]] == ["Demo"]


def test_project_init_refuses_an_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    run_cli(["project", "init"])
    capsys.readouterr()

    code = run_cli(["project", "init", "--format", "json"])

    assert code == 2
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "project_exists"


def test_project_targets_reports_kind_and_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    programs = tmp_path / "programs"
    libraries = tmp_path / "libraries"
    _write_program(programs, "Demo")
    _write_program(libraries, "Shared")
    _write_project(tmp_path, ["Demo", "Shared"], abb=libraries)

    code = run_cli(["project", "targets", "--format", "json"])

    assert code == 0
    targets = json.loads(capsys.readouterr().out)["targets"]
    assert [(target["name"], target["kind"]) for target in targets] == [
        ("Demo", "program"),
        ("Shared", "library"),
    ]


def test_project_targets_reports_an_ambiguous_stem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    programs = tmp_path / "programs"
    libraries = tmp_path / "libraries"
    _write_program(programs, "Demo")
    _write_program(libraries, "Demo")
    _write_project(tmp_path, [], abb=libraries)

    code = run_cli(["project", "targets", "--format", "json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert any("provided by both" in error for error in payload["errors"])


def test_project_check_fails_when_a_target_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_project(tmp_path, ["Missing"])

    code = run_cli(["project", "check", "--format", "json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any("Missing" in error for error in payload["errors"])


def test_project_check_accepts_a_valid_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_program(tmp_path / "programs", "Demo")
    _write_project(tmp_path, ["Demo"])

    code = run_cli(["project", "check"])

    assert code == 0
    assert "Result:  ok" in capsys.readouterr().out


def test_project_check_requires_icf_dir_when_the_analyzer_is_selected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_program(tmp_path / "programs", "Demo")
    _write_project(
        tmp_path,
        ["Demo"],
        analyzers=["icf"],
        icf_dir="missing-icf",
    )

    code = run_cli(["project", "check", "--format", "json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert any("icf_dir" in error for error in payload["errors"])
