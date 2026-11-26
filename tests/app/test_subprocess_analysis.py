# pyright: reportPrivateUsage=false
"""The interactive analysis path runs in a child process.

The child returns the run to history; the long-lived app never holds the
parsed project graphs or analyzer indexes that produced it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import cast

import pytest

from sattlint.application import cancellation as cancellation_module
from sattlint.application import subprocess_analysis as subprocess_analysis_module
from sattlint.application.cancellation import AnalysisCancellation
from sattlint.application.checks_results import ChecksRunResult
from sattlint.application.subprocess_analysis import run_checks_result_in_subprocess
from sattlint.config.defaults import DEFAULT_CONFIG
from sattlint.config.types import ConfigDict
from sattlint.core.progress import ProgressPhase
from sattlint.runs import load_run


def test_subprocess_run_streams_output_and_returns_a_saved_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name == "nt":
        cache_base = tmp_path / "appdata"
        monkeypatch.setenv("APPDATA", str(cache_base))
        runs_dir = cache_base / "sattlint" / "cache" / "runs"
    else:
        cache_base = tmp_path / "cache"
        monkeypatch.setenv("XDG_CACHE_HOME", str(cache_base))
        runs_dir = cache_base / "sattlint" / "runs"
    cfg = _valid_corpus_cfg()

    lines: list[str] = []
    result = run_checks_result_in_subprocess(cfg, ["comment-code"], emit_output=lines.append)

    assert result.cancelled is False
    assert result.failures == ()
    assert result.run_id is not None
    assert any("MinimalProgram" in line for line in lines)

    # The child resolves the platform cache base itself; the test fixture
    # patches the parent's resolver to a different path, so point at the
    # child's directory.
    record = load_run(result.run_id, runs_dir=runs_dir)
    assert record is not None
    assert [target.target_name for target in record.targets] == ["MinimalProgram"]


def test_subprocess_run_forwards_progress_records_and_keeps_them_out_of_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def progress_line(payload: Mapping[str, object]) -> str:
        return "sattlint-progress " + json.dumps(payload, separators=(",", ":"))

    start = {
        "schema_version": 1,
        "record_type": "progress",
        "phase": "start",
        "target_total": 1,
        "analyzer_total": 1,
        "project_wide_total": 0,
        "target_index": 0,
        "target_name": "",
        "analyzer_index": 0,
        "analyzer_name": "",
        "analyzer_key": "",
        "project_wide": False,
    }
    loading = {
        **start,
        "phase": "loading",
        "target_index": 1,
        "target_name": "TargetA",
    }
    script = (
        "import sys\n"
        f"sys.stderr.write({progress_line(start)!r} + '\\n')\n"
        "sys.stderr.write('human line\\n')\n"
        f"sys.stderr.write({progress_line(loading)!r} + '\\n')\n"
        "sys.stderr.flush()\n"
    )

    def command(**_kwargs: object) -> list[str]:
        return [sys.executable, "-c", script]

    monkeypatch.setattr(subprocess_analysis_module, "_analyze_command", command)

    emitted: list[str] = []
    events: list[object] = []
    result = run_checks_result_in_subprocess(
        _analysis_cfg(),
        ["comment-code"],
        project_path=str(tmp_path / "project.slproj"),
        emit_output=emitted.append,
        progress=events.append,
    )

    assert emitted == ["human line"]
    assert list(result.output_lines) == ["human line"]
    assert [getattr(event, "phase", None) for event in events] == [
        ProgressPhase.START,
        ProgressPhase.LOADING,
    ]
    assert getattr(events[1], "target_name", "") == "TargetA"
    assert not any("sattlint-progress" in line for line in result.output_lines)


def _analysis_cfg() -> ConfigDict:
    return cast(ConfigDict, deepcopy(DEFAULT_CONFIG))


def _valid_corpus_cfg() -> ConfigDict:
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures" / "corpus" / "valid"
    return cast(
        ConfigDict,
        {
            **deepcopy(DEFAULT_CONFIG),
            "analyzed_programs_and_libraries": ["MinimalProgram"],
            "program_dir": str(fixture_dir),
            "ABB_lib_dir": str(fixture_dir),
            "icf_dir": "",
            "other_lib_dirs": [],
            "mode": "draft",
        },
    )


def _shadow_module_source(marker: Path) -> str:
    """Python source that proves it ran by creating ``marker``."""
    return f"from pathlib import Path\n\nPath({str(marker)!r}).touch()\n"


def test_cancelled_subprocess_run_stops_promptly_with_its_worker_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancel must reach the forked workers too, not only the child process.

    The child below starts a grandchild that keeps the shared stderr pipe open
    and then sleeps. Killing only the child would leave that pipe open, so the
    output reader would block; a passing test therefore proves the process group
    was signalled.
    """
    script = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "sys.stderr.write('analysis started\\n')\n"
        "sys.stderr.flush()\n"
        "time.sleep(60)\n"
    )

    def command(**_kwargs: object) -> list[str]:
        return [sys.executable, "-c", script]

    monkeypatch.setattr(subprocess_analysis_module, "_analyze_command", command)

    started = threading.Event()
    cancellation = AnalysisCancellation()
    results: list[ChecksRunResult] = []

    def emit_output(_text: str) -> None:
        started.set()

    def run() -> None:
        results.append(
            run_checks_result_in_subprocess(
                _analysis_cfg(),
                ["comment-code"],
                project_path=str(tmp_path / "project.slproj"),
                emit_output=emit_output,
                cancellation=cancellation,
            )
        )

    worker = threading.Thread(target=run, daemon=True)
    try:
        worker.start()
        assert started.wait(10)
        started_at = time.monotonic()
        cancellation.cancel()
        worker.join(5)

        assert not worker.is_alive()
        assert time.monotonic() - started_at < 5
        assert results[0].cancelled is True
    finally:
        cancellation.cancel(force=True)
        worker.join(5)


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal semantics")
def test_cancel_escalates_to_a_kill_when_sigint_is_ignored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The watchdog is the only thing that can stop a SIGINT-ignoring tree."""
    script = (
        "import signal, subprocess, sys, time\n"
        "signal.signal(signal.SIGINT, signal.SIG_IGN)\n"
        "subprocess.Popen([sys.executable, '-c', "
        "'import signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); time.sleep(60)'])\n"
        "sys.stderr.write('analysis started\\n')\n"
        "sys.stderr.flush()\n"
        "time.sleep(60)\n"
    )

    def command(**_kwargs: object) -> list[str]:
        return [sys.executable, "-c", script]

    monkeypatch.setattr(subprocess_analysis_module, "_analyze_command", command)

    started = threading.Event()
    cancellation = AnalysisCancellation()
    results: list[ChecksRunResult] = []

    def run() -> None:
        results.append(
            run_checks_result_in_subprocess(
                _analysis_cfg(),
                ["comment-code"],
                project_path=str(tmp_path / "project.slproj"),
                emit_output=lambda _text: started.set(),
                cancellation=cancellation,
            )
        )

    worker = threading.Thread(target=run, daemon=True)
    try:
        worker.start()
        assert started.wait(10)
        cancellation.cancel()
        worker.join(6)

        assert not worker.is_alive()
        assert results[0].cancelled is True
    finally:
        cancellation.cancel(force=True)
        worker.join(6)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group semantics")
def test_cancel_kills_the_group_after_the_direct_child_already_exited(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead child must not make Cancel skip the live worker that holds stderr."""
    script = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "sys.stderr.write('analysis started\\n')\n"
        "sys.stderr.flush()\n"
        "time.sleep(1)\n"
        "raise SystemExit(3)\n"
    )

    def command(**_kwargs: object) -> list[str]:
        return [sys.executable, "-c", script]

    monkeypatch.setattr(subprocess_analysis_module, "_analyze_command", command)

    started = threading.Event()
    cancellation = AnalysisCancellation()
    results: list[ChecksRunResult] = []

    def run() -> None:
        results.append(
            run_checks_result_in_subprocess(
                _analysis_cfg(),
                ["comment-code"],
                project_path=str(tmp_path / "project.slproj"),
                emit_output=lambda _text: started.set(),
                cancellation=cancellation,
            )
        )

    worker = threading.Thread(target=run, daemon=True)
    try:
        worker.start()
        assert started.wait(10)
        time.sleep(1.5)  # the direct child exits; its grandchild keeps the pipe open
        cancellation.cancel()
        worker.join(5)

        assert not worker.is_alive()
        assert results[0].cancelled is True
    finally:
        cancellation.cancel(force=True)
        worker.join(5)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group semantics")
def test_atexit_hook_stops_a_tracked_process_group() -> None:
    cancellation = AnalysisCancellation()
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
        text=True,
    )
    try:
        cancellation.attach(process)
        cancellation_module._stop_tracked_processes()
        process.wait(timeout=5)
        assert process.poll() is not None
    finally:
        cancellation.detach(process)
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_cancel_requested_before_spawn_never_starts_a_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "child-ran"
    script = f"import time; time.sleep(5); open({str(marker)!r}, 'w').close()\n"
    commands: list[object] = []

    def command(**_kwargs: object) -> list[str]:
        commands.append(_kwargs)
        return [sys.executable, "-c", script]

    monkeypatch.setattr(subprocess_analysis_module, "_analyze_command", command)
    cancellation = AnalysisCancellation()
    cancellation.cancel()

    result = run_checks_result_in_subprocess(
        _analysis_cfg(),
        ["comment-code"],
        project_path=str(tmp_path / "project.slproj"),
        cancellation=cancellation,
    )

    assert result.cancelled is True
    assert marker.exists() is False
    assert commands == []


def test_analyze_command_keeps_the_project_directory_off_sys_path(tmp_path: Path) -> None:
    command = subprocess_analysis_module._analyze_command(
        project_path=tmp_path / "project.slproj",
        output_path=tmp_path / "run.ndjson",
        selected_keys=["comment-code"],
    )

    assert command[:4] == [sys.executable, "-P", "-m", subprocess_analysis_module.ANALYZE_MODULE]


def test_child_environment_blocks_cwd_imports_even_without_the_flag(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The environment form must hold on its own, not only through ``-P``."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    marker = project_dir / "shadow-imported"
    (project_dir / "shadow_module.py").write_text(_shadow_module_source(marker), encoding="utf-8")
    monkeypatch.chdir(project_dir)

    def command(**_kwargs: object) -> list[str]:
        # No ``-P`` here: the import can only fail because of the child's
        # environment.
        return [sys.executable, "-c", "import shadow_module"]

    monkeypatch.setattr(subprocess_analysis_module, "_analyze_command", command)

    result = run_checks_result_in_subprocess(
        _analysis_cfg(),
        ["comment-code"],
        project_path=str(project_dir / "project.slproj"),
    )

    assert marker.exists() is False
    assert any("ModuleNotFoundError" in line for line in result.output_lines)


def test_subprocess_run_never_imports_a_shadowing_project_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A project file named like the package must not run inside the child.

    The child inherits the working directory, which can be the analyzed project
    itself. A control run without the isolation proves that such a file really
    is imported when the working directory stays on ``sys.path``.
    """
    if os.name == "nt":
        monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    else:
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    project_dir = tmp_path / "shadow-project"
    project_dir.mkdir()
    marker = project_dir / "shadow-imported"
    (project_dir / "sattlint.py").write_text(_shadow_module_source(marker), encoding="utf-8")

    control_env = {key: value for key, value in os.environ.items() if key != "PYTHONSAFEPATH"}
    control = subprocess.run(
        [sys.executable, "-m", "sattlint", "--version"],
        cwd=project_dir,
        env=control_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert marker.exists() is True, control.stderr
    marker.unlink()

    monkeypatch.chdir(project_dir)
    result = run_checks_result_in_subprocess(_valid_corpus_cfg(), ["comment-code"])

    # Checked first: a shadow import replaces the analysis entirely.
    assert marker.exists() is False
    assert result.failures == ()
    assert result.run_id is not None
