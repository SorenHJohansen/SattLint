"""Checks runner for the application layer.

Runs the selected analyzers across every loaded target and folds the per-target
and per-analyzer results into a ``ChecksRunResult``.  Elevated from the old flat
``app_analysis`` / ``_app_analysis_checks`` modules as part of the Phase 2
layered refactor.
"""

from __future__ import annotations

import io
from collections.abc import Callable, Iterator
from contextlib import redirect_stdout
from dataclasses import replace
from time import perf_counter
from typing import Any, cast

from sattlint.parser_api import BasePicture

from .. import config as config_module
from ..analyzers import dispatch as analysis_dispatch_module
from ..analyzers.framework import AnalyzerSpec
from ..cache import AnalysisReportCache, compute_analysis_report_cache_key, get_cache_dir_or_none
from ..config.types import ConfigDict
from ..core import profiling as profiling_module
from ..core.debug import debug_enabled
from ..core.terminal import flush_stdout
from ..models.project_graph import ProjectGraph
from ..project import cache as report_cache_module
from . import checks_execution, checks_records
from . import output as output_module
from . import project as project_application
from .checks_execution import TargetExecution, execute_target, partition_analyzers, run_per_run_analyzer
from .checks_records import build_run_record
from .checks_results import (
    AnalyzerFailure,
    ChecksAnalyzerResult,
    ChecksRunResult,
    ChecksTargetResult,
    LoadFailureLog,
    TargetLoadFailure,
    build_run_result,
)

__all__ = [
    "AnalyzerFailure",
    "ChecksAnalyzerResult",
    "ChecksRunResult",
    "ChecksTargetResult",
    "TargetLoadFailure",
    "_iter_loaded_projects",
    "build_run_record",
    "collect_run_checks_result",
    "run_checks",
    "run_checks_result",
]

LoadedProject = project_application.LoadedProject


def _iter_loaded_projects(
    cfg: ConfigDict,
    *,
    refresh_ast: bool = False,
    failure_sink: Callable[[str, str], None] | None = None,
    emit_output_fn: Callable[..., None] | None = None,
) -> Iterator[LoadedProject]:
    return project_application.iter_loaded_projects(
        cfg,
        refresh_ast=refresh_ast,
        failure_sink=failure_sink,
        emit_output_fn=project_application.emit_output if emit_output_fn is None else emit_output_fn,
    )


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return project_application.target_is_library(cfg, project_bp, graph)


def _run_self_check_preflight(
    cfg: ConfigDict,
    *,
    self_check_fn: Callable[[ConfigDict], bool] | None,
) -> tuple[bool, list[str]]:
    if self_check_fn is None:
        return True, []
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        ok = self_check_fn(cfg)
    lines = [line for line in buffer.getvalue().splitlines() if line.strip()]
    return ok, lines


def _emit_self_check_failure(
    lines: list[str],
    emit_line: Callable[[str], None],
) -> None:
    for self_check_line in lines:
        emit_line(self_check_line)
    emit_line("❌ Self-check failed. Analysis aborted before the checks pipeline started.")
    emit_line("Fix the reported issues and rerun.")
    flush_stdout()


def _iter_per_run_analyzer_results(
    analyzers: list[AnalyzerSpec],
    cfg: ConfigDict,
    emit_line: Callable[[str], None],
) -> Iterator[ChecksTargetResult]:
    """Yield each per-run result as soon as it finishes.

    A cancellation in a later analyzer must keep the results already produced,
    so the caller appends as it iterates instead of receiving one final tuple.
    """
    for per_run_spec in analyzers:
        per_run_result = run_per_run_analyzer(per_run_spec, cfg)
        emit_line(f"\n=== {per_run_result.name} ({per_run_result.key}) ===")
        if per_run_result.summary:
            emit_line(per_run_result.summary)
        yield ChecksTargetResult(
            target_name=str(getattr(per_run_spec, "name", per_run_spec.key)),
            is_library=False,
            analyzers=(per_run_result,),
            is_pseudo=True,
        )


def collect_run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    refresh_ast: bool = False,
    persist_run: bool = False,
    project_path: str = "",
    jobs: int | None = None,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    self_check_fn: Callable[[ConfigDict], bool] | None = None,
    emit_output: Callable[[str], None] | None = None,
) -> ChecksRunResult:
    resolved_iter_loaded_projects = (
        _iter_loaded_projects if iter_loaded_projects_fn is None else iter_loaded_projects_fn
    )
    resolved_enabled_analyzers = (
        checks_execution.get_enabled_analyzers if get_enabled_analyzers_fn is None else get_enabled_analyzers_fn
    )
    resolved_target_is_library = _target_is_library if target_is_library_fn is None else target_is_library_fn
    resolved_self_check = config_module.self_check if self_check_fn is None else self_check_fn

    run_started_at = checks_records.utc_now_iso()
    output_lines: list[str] = []
    target_results: list[ChecksTargetResult] = []
    load_failures = LoadFailureLog()

    def emit_line(message: object) -> None:
        text = str(message)
        output_lines.append(text)
        if emit_output is not None:
            emit_output(text)

    analysis_settings = cfg.get("analysis")

    def report_cache_key(project_key: str, analyzer_key: str) -> str:
        return compute_analysis_report_cache_key(
            project_key,
            analyzer_key,
            analysis_settings=analysis_settings,
        )

    analyzers = list(
        cast(
            list[AnalyzerSpec],
            analysis_dispatch_module.get_cli_dispatch_analyzers(
                selected_keys=selected_keys,
                get_enabled_analyzers_fn=resolved_enabled_analyzers,
            ),
        )
    )
    selected_analyzer_keys = tuple(spec.key for spec in analyzers)

    if not analyzers:
        emit_line("❌ No matching checks found")
        return build_run_result(
            output_lines=output_lines,
            targets=(),
            selected_analyzers=selected_analyzer_keys,
        )

    per_target_analyzers, per_run_analyzers = partition_analyzers(analyzers)

    self_check_ok, self_check_lines = _run_self_check_preflight(cfg, self_check_fn=resolved_self_check)
    if not self_check_ok:
        _emit_self_check_failure(self_check_lines, emit_line)
        return build_run_result(
            output_lines=output_lines,
            targets=(),
            selected_analyzers=selected_analyzer_keys,
        )

    emit_line("\n--- Running checks ---")
    flush_stdout()
    report_cache = report_cache_module.create_analysis_report_cache(
        cfg,
        use_cache=use_cache,
        debug_enabled_fn=debug_enabled,
        analysis_report_cache_cls=AnalysisReportCache,
        get_cache_dir_fn=get_cache_dir_or_none,
    )
    profiler = profiling_module.create_profiler()
    # A per-run-only selection has no per-target analyzer, so loading the
    # project would pay the full parse cost for nothing.
    loaded_projects = (
        resolved_iter_loaded_projects(
            cfg,
            refresh_ast=refresh_ast,
            failure_sink=load_failures.record,
            emit_output_fn=emit_line,
        )
        if per_target_analyzers
        else ()
    )
    execution = TargetExecution(
        cfg=cfg,
        analyzers=tuple(analyzers),
        per_target_analyzers=tuple(per_target_analyzers),
        report_cache=report_cache,
        report_cache_key=report_cache_key,
        profiler=profiler,
        target_is_library_fn=resolved_target_is_library,
        emit_line=emit_line,
        build_module_tree=persist_run,
        jobs=jobs,
    )
    try:
        load_started_at = perf_counter()
        for target_name, project_bp, graph in loaded_projects:
            load_duration_ms = round((perf_counter() - load_started_at) * 1000, 3)
            outcome = execute_target(
                target_name,
                project_bp,
                graph,
                execution=execution,
                load_duration_ms=load_duration_ms,
            )
            target_results.append(outcome.target)
            # Drop the graph before the iterator loads the next target. The
            # loader generator clears its own reference as well, so the next
            # load does not hold two full project graphs at once.
            del project_bp, graph
            if outcome.cancelled:
                return build_run_result(
                    output_lines=output_lines,
                    targets=target_results,
                    selected_analyzers=selected_analyzer_keys,
                    cancelled=True,
                    failures=load_failures.snapshot(),
                )
            load_started_at = perf_counter()
        for per_run_result in _iter_per_run_analyzer_results(per_run_analyzers, cfg, emit_line):
            target_results.append(per_run_result)
    except KeyboardInterrupt:
        return build_run_result(
            output_lines=output_lines,
            targets=target_results,
            selected_analyzers=selected_analyzer_keys,
            cancelled=True,
            failures=load_failures.snapshot(),
        )

    result = build_run_result(
        output_lines=output_lines,
        targets=target_results,
        selected_analyzers=selected_analyzer_keys,
        failures=load_failures.snapshot(),
    )
    if persist_run:
        stored = checks_records.persist_run_result(
            result,
            cfg,
            started_at=run_started_at,
            project_path=project_path,
        )
        if stored is not None:
            result = replace(result, run_id=stored.run_id)
    return result


def run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    refresh_ast: bool = False,
    persist_run: bool = True,
    project_path: str = "",
    jobs: int | None = None,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    self_check_fn: Callable[[ConfigDict], bool] | None = None,
    emit_output: Callable[[str], None] | None = None,
) -> ChecksRunResult:
    emit = output_module.emit_output if emit_output is None else emit_output
    return collect_run_checks_result(
        cfg,
        selected_keys,
        use_cache=use_cache,
        refresh_ast=refresh_ast,
        persist_run=persist_run,
        project_path=project_path,
        jobs=jobs,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
        self_check_fn=self_check_fn,
        emit_output=emit,
    )


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    refresh_ast: bool = False,
    project_path: str = "",
    jobs: int | None = None,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    pause_fn: Callable[[], None] | None = None,
    self_check_fn: Callable[[ConfigDict], bool] | None = None,
    emit_output: Callable[[str], None] | None = None,
) -> None:
    result = run_checks_result(
        cfg,
        selected_keys,
        use_cache=use_cache,
        refresh_ast=refresh_ast,
        persist_run=True,
        project_path=project_path,
        jobs=jobs,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
        self_check_fn=self_check_fn,
        emit_output=emit_output,
    )
    if result.cancelled:
        output_module.handle_analysis_cancellation(pause_fn=pause_fn)
        return
    if pause_fn is not None:
        pause_fn()
