# pyright: reportPrivateUsage=false
"""Load-failure reporting: bounded messages, read errors, and partial results."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn, cast

import pytest

from sattlint.application.checks import (
    ChecksAnalyzerResult,
    ChecksRunResult,
    ChecksTargetResult,
    LoadFailureLog,
    TargetLoadFailure,
)
from sattlint.application.findings import AnalysisFinding
from sattlint.cli.entry import run_cli
from sattlint.config.types import ConfigDict
from sattlint.core.debug import log_load_failure
from sattlint.project.loading import iter_loaded_projects
from sattlint.project.support import TARGET_FAILURE_DETAIL_LIMIT, LoadFailureDetail, TargetLoadError
from sattlint.runs.io import runs_dir_location

_PROGRAM = """"Syntax version 2.23, date: 2026-02-02-11:05:04.749 N"
"Original file date: ---"
"Program date: 2026-02-02-11:05:04.749, name: {name}"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1

LOCALVARIABLES
   vUnused: integer;

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )

ENDDEF (*BasePicture*);
"""

_CAPACITIES = {"identstring": 15, "tagstring": 30, "string": 40, "linestring": 80, "maxstring": 140}


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Keep config and run history inside the test."""
    cache_home = tmp_path / "xdg-cache"
    config_home = tmp_path / "xdg-config"
    cache_home.mkdir()
    config_home.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    return cache_home


def _write_program(directory: Path, name: str, *, body: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.s"
    path.write_text(_PROGRAM.format(name=name) if body is None else body, encoding="utf-8")
    return path


def _write_project(
    root: Path,
    *,
    targets: list[str],
    programs_dir: str = "programs",
    extra_lines: tuple[str, ...] = (),
) -> Path:
    project = root / "demo.slproj"
    project.write_text(
        "\n".join(
            [
                "slproj_version = 2",
                f"analyzed_programs_and_libraries = {json.dumps(targets)}",
                'analyzers = ["variables"]',
                'mode = "draft"',
                f'program_dir = "{programs_dir}"',
                'ABB_lib_dir = ""',
                'icf_dir = ""',
                "other_lib_dirs = []",
                *extra_lines,
                "",
                "[string_capacities]",
                *(f"{key} = {value}" for key, value in _CAPACITIES.items()),
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project


def _missing_dependency(programs: Path, name: str) -> None:
    _write_program(programs, name)
    (programs / f"{name}.l").write_text("Missing\n", encoding="utf-8")


def _checks_result(
    *,
    targets: tuple[ChecksTargetResult, ...] = (),
    failures: tuple[TargetLoadFailure, ...] = (),
) -> ChecksRunResult:
    return ChecksRunResult(
        output_lines=(),
        targets=targets,
        selected_analyzers=("variables",),
        failures=failures,
    )


def _good_target(name: str = "Good") -> ChecksTargetResult:
    return ChecksTargetResult(
        target_name=name,
        is_library=False,
        analyzers=(
            ChecksAnalyzerResult(
                key="variables",
                name="Variable issues",
                status="completed",
                findings=(
                    AnalysisFinding(
                        kind="unused",
                        message="declared but never read",
                        module_path=(name, "BasePicture"),
                    ),
                ),
            ),
        ),
    )


def test_load_failure_logs_a_traceback_only_in_debug(caplog: pytest.LogCaptureFixture) -> None:
    logger_name = "sattlint.test.load-failure"
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        try:
            raise PermissionError(13, "Permission denied", "/tmp/Bad.s")
        except PermissionError as exc:
            log_load_failure("Failed to load", exc=exc, logger=logging.getLogger(logger_name), debug=False)
            log_load_failure("Failed to load", exc=exc, logger=logging.getLogger(logger_name), debug=True)

    records = [record for record in caplog.records if record.name == logger_name]
    assert [record.levelno for record in records] == [logging.DEBUG, logging.ERROR]
    assert records[0].exc_info is None
    assert records[1].exc_info is not None


def _fake_collect(result: ChecksRunResult) -> Callable[..., ChecksRunResult]:
    def collect(*_args: object, **_kwargs: object) -> ChecksRunResult:
        return result

    return collect


def test_failure_report_caps_every_list_and_states_the_remainder() -> None:
    missing = [f"Missing{index}" for index in range(TARGET_FAILURE_DETAIL_LIMIT + 5)]
    error = TargetLoadError(
        "Root",
        resolved=[f"Resolved{index}" for index in range(TARGET_FAILURE_DETAIL_LIMIT + 5)],
        missing=missing,
        direct_dependencies=[f"Dependency{index}" for index in range(TARGET_FAILURE_DETAIL_LIMIT + 5)],
    )

    message = str(error)

    assert message.startswith("Target 'Root' could not be loaded.")
    assert "was not parsed" not in message
    assert f"  - Missing{TARGET_FAILURE_DETAIL_LIMIT - 1}" in message
    assert f"  - Missing{TARGET_FAILURE_DETAIL_LIMIT}" not in message
    assert "  - ... and 5 more" in message
    assert len(message.splitlines()) < 60


def test_mixed_targets_keep_the_successful_findings_and_leave_no_run(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    programs = tmp_path / "programs"
    _write_program(programs, "Good")
    _missing_dependency(programs, "Bad")
    project = _write_project(tmp_path, targets=["Good", "Bad"])

    code = run_cli(["analyze", "--project", str(project), "--format", "text", "--fail-on", "none"])

    out, err = capsys.readouterr()
    assert code == 2
    assert "Run: (not saved)" in out
    assert "Unused variable" in out
    assert "Failed targets (1):" in out
    assert "  - Bad (load): " in out
    assert "Fix the failed targets, then rerun." in out
    assert "=== Target: Bad ===" in err
    assert "Bad: missing code file for 'Missing'" in err
    assert not runs_dir_location().exists()

    # The failed run is not the newest stored run, because it was never stored.
    code = run_cli(["findings", "--run", "latest", "--project", str(project), "--format", "json"])
    assert code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"]["code"] == "no_runs"


def test_mixed_targets_json_adds_typed_failures_with_a_parser_position(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    programs = tmp_path / "programs"
    _write_program(programs, "Good")
    _write_program(
        programs,
        "Broken",
        body=_PROGRAM.format(name="Broken").replace(
            "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )",
            "THIS IS NOT VALID @@@",
        ),
    )
    project = _write_project(tmp_path, targets=["Good", "Broken"])

    code = run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["run_id"] is None
    assert payload["summary"]["findings"] == 1
    assert len(payload["findings"]) == 1
    assert payload["failed_targets"] == 1
    failure = payload["failures"][0]
    assert set(failure) == {"target", "kind", "message", "path", "line", "column"}
    assert failure["target"] == "Broken"
    assert failure["kind"] == "parse"
    assert failure["path"].endswith("Broken.s")
    assert isinstance(failure["line"], int)
    assert isinstance(failure["column"], int)


def test_successful_json_keeps_the_analyze_shape_without_failure_fields(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    programs = tmp_path / "programs"
    _write_program(programs, "Good")
    project = _write_project(tmp_path, targets=["Good"])

    code = run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert "failures" not in payload
    assert "failed_targets" not in payload


def test_unreadable_target_is_reported_as_a_read_error(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    geteuid = cast(Callable[[], int] | None, getattr(os, "geteuid", None))
    if geteuid is None:
        pytest.skip("the platform does not expose file modes this way")
    if geteuid() == 0:
        pytest.skip("root can read a file with mode 000")
    programs = tmp_path / "programs"
    _write_program(programs, "Good")
    unreadable = _write_program(programs, "Unreadable")
    unreadable.chmod(0o000)
    try:
        if os.access(unreadable, os.R_OK):
            pytest.skip("the platform does not enforce mode 000 for this user")
        project = _write_project(tmp_path, targets=["Good", "Unreadable"])

        code = run_cli(["analyze", "--project", str(project), "--format", "json", "--fail-on", "none"])

        payload = json.loads(capsys.readouterr().out)
        assert code == 2
        assert payload["summary"]["findings"] == 1
        failure = payload["failures"][0]
        assert failure["target"] == "Unreadable"
        assert failure["kind"] == "read"
        assert "Could not read" in failure["message"]
        assert "Permission denied" in failure["message"]
        assert "was not parsed" not in failure["message"]
        assert "failed to parse" not in failure["message"]
        assert cast(str, failure["path"]).endswith("Unreadable.s")
    finally:
        unreadable.chmod(0o644)


def test_quiet_keeps_the_final_error_and_drops_the_project_warning(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    programs = tmp_path / "programs"
    _missing_dependency(programs, "One")
    _missing_dependency(programs, "Two")
    project = _write_project(
        tmp_path,
        targets=["One", "Two"],
        extra_lines=("mystery_key = 1",),
    )

    code = run_cli(["analyze", "--project", str(project), "--format", "text", "--fail-on", "none", "--quiet"])

    out, err = capsys.readouterr()
    assert code == 2
    assert out == ""
    assert "sattlint: Analysis stopped because 2 target(s) could not be loaded" in err
    assert "  One: " in err
    assert "  Two: " in err
    assert "Ignoring unknown .slproj key" not in err
    assert "Running checks" not in err


def test_all_failed_error_caps_the_reported_targets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(tmp_path, targets=["Good"])
    failures = tuple(
        TargetLoadFailure(target_name=f"Target{index}", message="could not be loaded")
        for index in range(TARGET_FAILURE_DETAIL_LIMIT + 8)
    )
    monkeypatch.setattr(
        "sattlint.cli.commands.collect_checks_result",
        _fake_collect(_checks_result(failures=failures)),
    )

    code = run_cli(["analyze", "--project", str(project), "--format", "json"])

    payload = json.loads(capsys.readouterr().err)
    assert code == 2
    assert payload["error"]["code"] == "target_load_failed"
    assert "... and 8 more. Fix the reported problems, then rerun." in payload["error"]["message"]
    details = cast(dict[str, object], payload["error"]["details"])
    assert len(details) == TARGET_FAILURE_DETAIL_LIMIT + 1
    assert details["omitted"] == "8 more target(s)"


def test_partial_text_output_caps_the_failed_target_block(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    (tmp_path / "programs").mkdir()
    project = _write_project(
        tmp_path,
        targets=["Good", *(f"Target{index}" for index in range(TARGET_FAILURE_DETAIL_LIMIT + 8))],
    )
    failures = tuple(
        TargetLoadFailure(target_name=f"Target{index}", message="could not be loaded")
        for index in range(TARGET_FAILURE_DETAIL_LIMIT + 8)
    )
    monkeypatch.setattr(
        "sattlint.cli.commands.collect_checks_result",
        _fake_collect(_checks_result(targets=(_good_target(),), failures=failures)),
    )

    code = run_cli(["analyze", "--project", str(project), "--format", "text", "--fail-on", "none"])

    out = capsys.readouterr().out
    assert code == 2
    assert "Failed targets (20):" in out
    assert out.count("  - Target") == TARGET_FAILURE_DETAIL_LIMIT
    assert "  - ... and 8 more" in out


def test_failure_record_fields_are_typed_and_optional() -> None:
    failure = TargetLoadFailure(
        target_name="Bad",
        message="could not be loaded",
        kind="read",
        path="/tmp/Bad.s",
        line=3,
        column=4,
    )

    assert failure.kind == "read"
    assert failure.path == "/tmp/Bad.s"
    assert failure.line == 3
    assert failure.column == 4
    assert TargetLoadFailure(target_name="Bad", message="m").kind == "load"


class _ParserPositionError(RuntimeError):
    path = "/tmp/Bad.s"
    line = 7
    column = 3


def test_typed_failure_detail_reaches_the_sink_and_keeps_its_fields() -> None:
    received: list[tuple[str, LoadFailureDetail]] = []
    emitted: list[str] = []

    def load_project(*_args: object, **_kwargs: object) -> NoReturn:
        raise _ParserPositionError("unexpected token")

    def emit_output(line: object) -> None:
        emitted.append(str(line))

    projects = list(
        iter_loaded_projects(
            cast(ConfigDict, {"analyzed_programs_and_libraries": ["Bad"]}),
            refresh_ast=False,
            require_analyzed_targets_fn=lambda _cfg: ["Bad"],
            load_project_fn=load_project,
            emit_output_fn=emit_output,
            failure_sink=lambda name, detail: received.append((name, detail)),
        )
    )

    assert projects == []
    assert emitted[-1] == "unexpected token"
    assert not any("LoadFailureDetail(" in line for line in emitted)
    assert [name for name, _detail in received] == ["Bad"]
    detail = received[0][1]
    assert isinstance(detail, LoadFailureDetail)
    assert detail.message == "unexpected token"
    assert detail.kind == "parse"
    assert detail.path == "/tmp/Bad.s"
    assert detail.line == 7
    assert detail.column == 3

    log = LoadFailureLog()
    log.record("Bad", detail)
    failure = log.snapshot()[0]
    assert failure == TargetLoadFailure(
        target_name="Bad",
        message="unexpected token",
        kind="parse",
        path="/tmp/Bad.s",
        line=7,
        column=3,
    )
