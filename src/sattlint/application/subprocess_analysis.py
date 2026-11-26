"""Run an analysis in a short-lived child process.

The project graphs and analyzer indexes of a large SattLine project are much
larger than the findings they produce, and CPython keeps the freed arenas
resident after a run. The interactive app is long-lived, so an in-process run
leaves it holding hundreds of megabytes it no longer uses. A child process
returns all of that memory to the OS when it exits, while the saved run record
gives the app the same result it would have produced in-process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from copy import deepcopy
from pathlib import Path
from typing import cast

from ..config.string_capacities import StringCapacitiesDict, standard_string_capacities_dict
from ..config.types import AnalysisConfig, ConfigDict, ConfigMode
from ..core.progress import ProgressCallback, parse_progress_line
from ..project.io import save_project
from ..project.types import DEFAULT_PROJECT_DICT, ProjectDict
from .cancellation import (
    AnalysisCancellation,
    process_group_spawn_kwargs,
    terminate_process_tree,
)
from .checks_results import ChecksRunResult, TargetLoadFailure

ANALYZE_MODULE = "sattlint"
_RUN_ID_RECORD_TYPE = "envelope"


def _ignore_output(_message: str) -> None:
    return None


def _absolute_path(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return str(Path(text).expanduser().resolve())


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [str(item) for item in cast(Sequence[object], value) if str(item).strip()]


def _project_data_from_config(cfg: ConfigDict, selected_keys: Sequence[str]) -> ProjectDict:
    """Build a standalone project file for a child run from an in-memory config."""
    data = deepcopy(dict(DEFAULT_PROJECT_DICT))
    data["analyzed_programs_and_libraries"] = _string_list(cfg.get("analyzed_programs_and_libraries"))
    data["analyzers"] = [str(key) for key in selected_keys]
    data["mode"] = cast(ConfigMode, str(cfg.get("mode") or "official"))
    data["program_dir"] = _absolute_path(cfg.get("program_dir"))
    data["ABB_lib_dir"] = _absolute_path(cfg.get("ABB_lib_dir"))
    data["icf_dir"] = _absolute_path(cfg.get("icf_dir"))
    data["other_lib_dirs"] = [_absolute_path(value) for value in _string_list(cfg.get("other_lib_dirs"))]
    capacities = cast(Mapping[str, object], cfg.get("string_capacities"))
    overrides: dict[str, int] = {
        name: value
        for name, value in capacities.items()
        if isinstance(value, int) and not isinstance(value, bool) and value > 0
    }
    data["string_capacities"] = cast(
        StringCapacitiesDict,
        {**standard_string_capacities_dict(), **overrides},
    )
    data["analysis"] = cast(AnalysisConfig, deepcopy(dict(cfg.get("analysis"))))
    return cast(ProjectDict, data)


def _analyze_command(
    *,
    project_path: Path,
    output_path: Path,
    selected_keys: Sequence[str],
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        ANALYZE_MODULE,
        "analyze",
        "--project",
        str(project_path),
        "--format",
        "ndjson",
        "--output",
        str(output_path),
        "--fail-on",
        "none",
        "--progress",
    ]
    for key in selected_keys:
        command.extend(("--analyzer", str(key)))
    return command


def _read_run_id(output_path: Path) -> str | None:
    """Read the run id from the ndjson envelope, ignoring the finding records."""
    try:
        with output_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                payload: object = json.loads(text)
                if not isinstance(payload, Mapping):
                    return None
                mapping = cast(Mapping[object, object], payload)
                if mapping.get("record_type") != _RUN_ID_RECORD_TYPE:
                    return None
                run_id = mapping.get("run_id")
                if isinstance(run_id, str) and run_id.strip():
                    return run_id.strip()
                return None
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _temporary_project(cfg: ConfigDict, selected_keys: Sequence[str]) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    directory: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory(prefix="sattlint-analysis-")
    project_path = Path(directory.name) / ".slproj"
    save_project(project_path, _project_data_from_config(cfg, selected_keys))
    return directory, project_path


def run_checks_result_in_subprocess(
    cfg: ConfigDict,
    selected_keys: Sequence[str],
    *,
    project_path: str = "",
    emit_output: Callable[[str], None] | None = None,
    progress: ProgressCallback | None = None,
    cancellation: AnalysisCancellation | None = None,
) -> ChecksRunResult:
    """Run the checks pipeline in a child process and return its run id.

    The child writes the same run-history record an in-process run would, so
    the Results view needs no separate result shape. Output lines are streamed
    from the child's stderr as they arrive; the child's progress records are
    parsed out of that stream, forwarded to ``progress``, and never shown as
    diagnostics.

    ``cancellation`` stops the child (and the analyzer workers it forked) as
    soon as it is set. The reader keeps draining the stream to EOF so a child
    that is still writing cannot block on a full pipe; the collected lines are
    kept for diagnostics, but no line or progress event is emitted after
    cancellation.
    """
    if cancellation is not None and cancellation.cancelled:
        # A quit can land between starting the action and this spawn; do not
        # create a child nobody is left to track.
        return ChecksRunResult(output_lines=(), cancelled=True)
    emit: Callable[[str], None] = _ignore_output if emit_output is None else emit_output
    temporary: tempfile.TemporaryDirectory[str] | None = None
    output_fd, output_name = tempfile.mkstemp(prefix="sattlint-analyze-", suffix=".ndjson")
    os.close(output_fd)
    output_path = Path(output_name)
    process: subprocess.Popen[str] | None = None
    try:
        resolved_project = Path(project_path).expanduser().resolve() if project_path.strip() else None
        if resolved_project is None:
            temporary, resolved_project = _temporary_project(cfg, selected_keys)
        # The child's status text and findings are Unicode. Force both ends to
        # UTF-8 so Windows console code pages cannot corrupt the stream.
        environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        process = subprocess.Popen(
            _analyze_command(
                project_path=resolved_project,
                output_path=output_path,
                selected_keys=selected_keys,
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=environment,
            **process_group_spawn_kwargs(),
        )
        if cancellation is not None:
            cancellation.attach(process)
        lines: list[str] = []
        if process.stderr is not None:
            for raw_line in process.stderr:
                text = raw_line.rstrip("\r\n")
                if not text:
                    continue
                event = parse_progress_line(text)
                if event is not None:
                    if progress is not None and (cancellation is None or not cancellation.cancelled):
                        progress(event)
                    continue
                lines.append(text)
                if cancellation is None or not cancellation.cancelled:
                    emit(text)
        return_code = process.wait()
        if return_code == 0:
            # A cancel that arrives after the child saved the run loses the race:
            # the run is complete, so report it instead of discarding it.
            return ChecksRunResult(output_lines=tuple(lines), run_id=_read_run_id(output_path))
        if (cancellation is not None and cancellation.cancelled) or return_code == 130:
            return ChecksRunResult(output_lines=tuple(lines), cancelled=True)
        return ChecksRunResult(
            output_lines=tuple(lines),
            failures=(TargetLoadFailure(target_name="analysis", message=f"Child process exited with {return_code}."),),
        )
    finally:
        if process is not None:
            if cancellation is not None:
                cancellation.detach(process)
            if process.poll() is None:
                terminate_process_tree(process, force=True)
                with suppress(OSError, subprocess.TimeoutExpired):
                    process.wait(timeout=2)
        with suppress(OSError):
            output_path.unlink()
        if temporary is not None:
            temporary.cleanup()


__all__ = ["run_checks_result_in_subprocess"]
