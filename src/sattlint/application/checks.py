"""Checks runner for the application layer.

Runs the selected analyzers across every loaded target and folds the per-target
and per-analyzer results into a ``ChecksRunResult``.  Elevated from the old flat
``app_analysis`` / ``_app_analysis_checks`` modules as part of the Phase 2
layered refactor.
"""

from __future__ import annotations

import io
import os
from collections.abc import Callable, Iterator
from contextlib import redirect_stdout, suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from sattlint.parser_api import BasePicture, FrameModule, ModuleTypeDef, ModuleTypeInstance, SingleModule

from .. import config as config_module
from ..analyzers import catalog as analysis_catalog_module
from ..analyzers import dispatch as analysis_dispatch_module
from ..analyzers.framework import (
    AnalysisSharedArtifacts,
    AnalyzerSpec,
    SimpleReport,
    build_analysis_context,
)
from ..analyzers.shared.instance_paths import rewrite_typedef_paths
from ..cache import AnalysisReportCache, compute_analysis_report_cache_key, get_cache_dir_or_none
from ..config.types import ConfigDict
from ..core import profiling as profiling_module
from ..core.debug import debug_enabled
from ..core.terminal import flush_stdout
from ..models.project_graph import ProjectGraph
from ..project import cache as report_cache_module
from ..reporting.target_report import normalize_report_target_name
from ..resolution.common import resolve_moduletype_def_strict
from ..runs import (
    DEFAULT_RUN_HISTORY_LIMIT,
    RunAnalyzerRecord,
    RunModuleRecord,
    RunRecord,
    RunTargetRecord,
    get_runs_dir_or_none,
    prune_runs,
    save_run,
)
from . import output as output_module
from . import project as project_application
from .findings import AnalysisFinding, extract_report_findings

LoadedProject = project_application.LoadedProject


@dataclass(frozen=True, slots=True)
class ChecksAnalyzerResult:
    key: str
    name: str
    status: str
    summary: str | None = None
    report_kind: str | None = None
    issue_count: int | None = None
    findings: tuple[AnalysisFinding, ...] = ()
    duration_ms: float | None = None
    phase_timings_ms: tuple[dict[str, object], ...] = ()
    skip_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ChecksTargetResult:
    target_name: str
    is_library: bool
    analyzers: tuple[ChecksAnalyzerResult, ...]
    stage_timings_ms: dict[str, float] | None = None
    graphics_timings_ms: dict[str, float] | None = None
    analyzer_bottleneck: dict[str, object] | None = None
    analyzer_phase_bottleneck: dict[str, object] | None = None
    shared_artifact_profile: str | None = None
    is_pseudo: bool = False
    module: RunModuleRecord | None = None


@dataclass(frozen=True, slots=True)
class TargetLoadFailure:
    target_name: str
    message: str


@dataclass(frozen=True, slots=True)
class AnalyzerFailure:
    analyzer_name: str
    target_name: str
    message: str


@dataclass(frozen=True, slots=True)
class ChecksRunResult:
    output_lines: tuple[str, ...]
    targets: tuple[ChecksTargetResult, ...] = ()
    selected_analyzers: tuple[str, ...] = ()
    cancelled: bool = False
    run_id: str | None = None
    failures: tuple[TargetLoadFailure, ...] = ()

    @property
    def analyzer_failures(self) -> tuple[AnalyzerFailure, ...]:
        """Analyzers that raised during this run, across loaded targets and per-run analyzers."""
        return tuple(
            AnalyzerFailure(
                analyzer_name=analyzer.name,
                target_name=target.target_name,
                message=analyzer.summary or "Analyzer failed without a message.",
            )
            for target in self.targets
            for analyzer in target.analyzers
            if analyzer.status == "failed"
        )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _run_history_enabled(cfg: ConfigDict) -> bool:
    run_history = cast(object, cfg.get("run_history"))
    if isinstance(run_history, dict):
        mapping = cast(dict[str, object], run_history)
        return bool(mapping.get("enabled", True))
    return True


def _run_history_limit(cfg: ConfigDict) -> int:
    run_history = cast(object, cfg.get("run_history"))
    if isinstance(run_history, dict):
        mapping = cast(dict[str, object], run_history)
        limit = mapping.get("limit", DEFAULT_RUN_HISTORY_LIMIT)
        if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0:
            return limit
    return DEFAULT_RUN_HISTORY_LIMIT


def _project_tag(cfg: ConfigDict) -> str:
    targets = cast(object, cfg.get("analyzed_programs_and_libraries", []))
    if isinstance(targets, list):
        return ", ".join(str(target) for target in cast(list[object], targets) if str(target).strip())
    return ""


def _run_analyzer_record(result: ChecksAnalyzerResult) -> RunAnalyzerRecord:
    return RunAnalyzerRecord(
        key=result.key,
        name=result.name,
        status=result.status,
        summary=result.summary,
        report_kind=result.report_kind,
        issue_count=result.issue_count,
        findings=result.findings,
        duration_ms=result.duration_ms,
        phase_timings_ms=result.phase_timings_ms,
        skip_reason=result.skip_reason,
    )


def _run_target_record(result: ChecksTargetResult) -> RunTargetRecord:
    return RunTargetRecord(
        target_name=result.target_name,
        is_library=result.is_library,
        analyzers=tuple(_run_analyzer_record(analyzer) for analyzer in result.analyzers),
        stage_timings_ms=result.stage_timings_ms,
        graphics_timings_ms=result.graphics_timings_ms,
        module=result.module,
    )


def _snapshot_module_tree(base_picture: BasePicture, graph: ProjectGraph, target_name: str) -> RunModuleRecord:
    definitions: dict[str, list[ModuleTypeDef]] = {}
    for definition in (*(base_picture.moduletype_defs or []), *graph.moduletype_defs.values()):
        bucket = definitions.setdefault(definition.name.casefold(), [])
        if all(definition is not existing for existing in bucket):
            bucket.append(definition)

    def children_of(
        modules: list[SingleModule | FrameModule | ModuleTypeInstance],
        library: str | None,
        source_file: str | None,
        active_types: frozenset[tuple[str, str, str]],
    ) -> tuple[RunModuleRecord, ...]:
        children: list[RunModuleRecord] = []
        for module in modules:
            if isinstance(module, ModuleTypeInstance):
                definition = None
                with suppress(ValueError):
                    definition = resolve_moduletype_def_strict(
                        base_picture,
                        module.moduletype_name,
                        current_library=library,
                        current_file=source_file,
                        moduletype_index=definitions,
                    )
                nested: tuple[RunModuleRecord, ...] = ()
                type_label = module.moduletype_name
                if definition is not None:
                    if (
                        definition.origin_file
                        and Path(definition.origin_file).stem.casefold()
                        != Path(base_picture.origin_file or "").stem.casefold()
                    ):
                        type_label = f"{Path(definition.origin_file).stem}:{type_label}"
                    key = (
                        (definition.origin_lib or "").casefold(),
                        definition.name.casefold(),
                        (definition.origin_file or "").casefold(),
                    )
                    if key not in active_types:
                        nested = children_of(
                            definition.submodules or [],
                            definition.origin_lib or library,
                            definition.origin_file or source_file,
                            active_types | {key},
                        )
                children.append(RunModuleRecord(name=module.header.name, moduletype_name=type_label, children=nested))
            else:
                children.append(
                    RunModuleRecord(
                        name=module.header.name,
                        kind=type(module).__name__,
                        children=children_of(module.submodules or [], library, source_file, active_types),
                    )
                )
        return tuple(children)

    root_name = base_picture.header.name
    if target_name.casefold() != root_name.casefold():
        root_name = f"{target_name}:{root_name}"
    return RunModuleRecord(
        name=root_name,
        kind="SingleModule",
        children=children_of(
            base_picture.submodules or [], base_picture.origin_lib, base_picture.origin_file, frozenset()
        ),
    )


def build_run_record(
    result: ChecksRunResult,
    cfg: ConfigDict,
    *,
    started_at: str | None = None,
    project_path: str = "",
) -> RunRecord:
    """Convert a checks run result into a persisted run record."""
    return RunRecord(
        run_id="",
        started_at=started_at or _utc_now_iso(),
        finished_at=_utc_now_iso(),
        project_tag=_project_tag(cfg),
        project_path=project_path,
        selected_analyzers=result.selected_analyzers,
        targets=tuple(_run_target_record(target) for target in result.targets if not target.is_pseudo),
        project_analyzers=tuple(
            _run_analyzer_record(analyzer)
            for target in result.targets
            if target.is_pseudo
            for analyzer in target.analyzers
        ),
        output_lines=result.output_lines,
    )


def _persist_run_result(
    result: ChecksRunResult,
    cfg: ConfigDict,
    *,
    started_at: str,
    project_path: str = "",
) -> RunRecord | None:
    # A failing analyzer leaves the other analyzers' results intact, and the
    # record carries its failed status, so the run is still worth keeping.
    # Cancelled runs and runs with unloaded targets have no complete result set.
    if result.cancelled or result.failures:
        return None
    runs_dir = get_runs_dir_or_none()
    if runs_dir is None:
        return None
    if not _run_history_enabled(cfg):
        # Recording is off, but retention still applies: otherwise turning the
        # history off silently stops pruning the records already on disk.
        prune_runs(runs_dir, limit=_run_history_limit(cfg))
        return None
    record = build_run_record(result, cfg, started_at=started_at, project_path=project_path)
    try:
        stored = save_run(record, runs_dir=runs_dir)
    except OSError:
        return None
    prune_runs(runs_dir, limit=_run_history_limit(cfg))
    return stored


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], analysis_catalog_module.get_default_cli_analyzers())


def _analysis_status_text(target_name: str, spec: Any) -> str:
    return f"Analyzing {target_name}: {spec.name} ({spec.key})"


def _profile_analyzers_enabled() -> bool:
    return os.environ.get("SATTLINT_PROFILE_ANALYZERS", "").strip().casefold() in {"1", "true", "yes", "on"}


def _shared_artifact_profile_text(target_name: str, shared_artifacts: AnalysisSharedArtifacts) -> str:
    counters = shared_artifacts.counters
    return (
        "Analyzer reuse profile for "
        f"{target_name}: shared-artifact-holders={counters.shared_artifact_holders_created}, "
        f"variable-foundation-builds={counters.variable_foundation_builds}, "
        f"variable-root-traversals={counters.variable_root_traversals}, "
        f"local-env-builds={counters.local_env_builds}"
    )


def _iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    failure_sink: Callable[[str, str], None] | None = None,
    emit_output_fn: Callable[..., None] | None = None,
) -> Iterator[LoadedProject]:
    return project_application.iter_loaded_projects(
        cfg,
        use_cache=use_cache,
        failure_sink=failure_sink,
        emit_output_fn=project_application.emit_output if emit_output_fn is None else emit_output_fn,
    )


def _run_per_run_analyzer(
    spec: AnalyzerSpec,
    cfg: ConfigDict,
) -> ChecksAnalyzerResult:
    started_at = perf_counter()
    try:
        context = build_analysis_context(
            cast(BasePicture, None),
            debug=debug_enabled(cfg),
            config=cfg,
            create_shared_artifacts=True,
        )
        report = analysis_dispatch_module.run_registry_analyzer(spec, context)
    except Exception as exc:  # noqa: BLE001 - a per-run failure should not abort the run
        return ChecksAnalyzerResult(
            key=spec.key,
            name=spec.name,
            status="failed",
            summary=f"{spec.name} failed: {exc}",
            issue_count=0,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
        )
    typed_report = cast(SimpleReport, report)
    summary_text = typed_report.summary()
    findings = extract_report_findings(typed_report, default_name=spec.name)
    return ChecksAnalyzerResult(
        key=spec.key,
        name=spec.name,
        status="completed",
        summary=summary_text,
        report_kind=type(report).__name__,
        issue_count=len(findings),
        findings=findings,
        duration_ms=round((perf_counter() - started_at) * 1000, 3),
    )


def _partition_analyzers(analyzers: list[AnalyzerSpec]) -> tuple[list[AnalyzerSpec], list[AnalyzerSpec]]:
    per_target: list[AnalyzerSpec] = []
    per_run: list[AnalyzerSpec] = []
    for spec in analyzers:
        # ``AnalyzerSpec.scope`` defaults to per-target; a dispatch double may
        # omit it. Any other value is a wiring error, not a reason to drop the
        # analyzer from both passes without a word.
        scope = getattr(spec, "scope", "per-target")
        if scope == "per-target":
            per_target.append(spec)
        elif scope == "per-run":
            per_run.append(spec)
        else:
            raise ValueError(f"Analyzer {spec.key!r} declares an unsupported scope {scope!r}")
    return per_target, per_run


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return project_application.target_is_library(cfg, project_bp, graph)


def _rewrite_typedef_issue_paths(report: object, base_picture: BasePicture) -> None:
    for attr in ("issues", "hits"):
        items = getattr(report, attr, None)
        if isinstance(items, list):
            setattr(report, attr, rewrite_typedef_paths(cast(list[object], items), base_picture))


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


def collect_run_checks_result(  # noqa: PLR0915
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    persist_run: bool = False,
    project_path: str = "",
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    get_enabled_analyzers_fn: Callable[[], list[Any]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    self_check_fn: Callable[[ConfigDict], bool] | None = None,
    emit_output: Callable[[str], None] | None = None,
) -> ChecksRunResult:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = _iter_loaded_projects
    if get_enabled_analyzers_fn is None:
        get_enabled_analyzers_fn = _get_enabled_analyzers
    if target_is_library_fn is None:
        target_is_library_fn = _target_is_library

    run_started_at = _utc_now_iso()
    output_lines: list[str] = []
    target_results: list[ChecksTargetResult] = []
    load_failures: list[TargetLoadFailure] = []

    def emit_line(message: object) -> None:
        text = str(message)
        output_lines.append(text)
        if emit_output is not None:
            emit_output(text)

    def record_load_failure(target_name: str, message: str) -> None:
        load_failures.append(TargetLoadFailure(target_name=target_name, message=message))

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
                get_enabled_analyzers_fn=get_enabled_analyzers_fn,
            ),
        )
    )
    selected_analyzer_keys = tuple(spec.key for spec in analyzers)

    if not analyzers:
        emit_line("❌ No matching checks found")
        return ChecksRunResult(
            output_lines=tuple(output_lines),
            selected_analyzers=selected_analyzer_keys,
        )

    per_target_analyzers, per_run_analyzers = _partition_analyzers(analyzers)

    if self_check_fn is None:
        self_check_fn = config_module.self_check
    self_check_ok, self_check_lines = _run_self_check_preflight(cfg, self_check_fn=self_check_fn)
    if not self_check_ok:
        for self_check_line in self_check_lines:
            emit_line(self_check_line)
        emit_line("❌ Self-check failed. Analysis aborted before the checks pipeline started.")
        emit_line("Fix the reported issues and rerun.")
        flush_stdout()
        return ChecksRunResult(
            output_lines=tuple(output_lines),
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
        iter_loaded_projects_fn(
            cfg,
            use_cache=use_cache,
            failure_sink=record_load_failure,
            emit_output_fn=emit_line,
        )
        if per_target_analyzers
        else ()
    )
    try:
        for target_name, project_bp, graph in loaded_projects:
            target_analyzers: list[ChecksAnalyzerResult] = []
            target_started_at = perf_counter()
            analyzer_timings_ms: dict[str, float] = {}
            analyzer_phase_timings_ms: dict[str, list[dict[str, object]]] = {}
            stage_timings_ms = profiling_module.normalize_named_timings_ms(
                getattr(graph, "load_stage_timings", None), scale=1000.0
            )
            graphics_timings_ms = profiling_module.normalize_named_timings_ms(
                getattr(graph, "graphics_load_timings", None),
                scale=1000.0,
            )
            is_library = target_is_library_fn(cfg, project_bp, graph)
            module_tree = (
                _snapshot_module_tree(project_bp, graph, target_name)
                if isinstance(cast(object, project_bp), BasePicture)
                else None
            )
            context = build_analysis_context(
                project_bp,
                graph=graph,
                debug=debug_enabled(cfg),
                target_is_library=is_library,
                config=cfg,
                create_shared_artifacts=True,
            )
            emit_line(f"\n=== Target: {target_name} ===")
            flush_stdout()
            for spec in per_target_analyzers:
                emit_line(f"\n=== {spec.name} ({spec.key}) ===")
                flush_stdout()
                analyzer_started_at = perf_counter()
                try:
                    report = output_module.run_with_live_status(
                        _analysis_status_text(target_name, spec),
                        lambda spec=spec, context=context, graph=graph: (
                            report_cache_module.run_with_analysis_report_cache(
                                graph,
                                report_cache=report_cache,
                                analyzer_cache_key=spec.key,
                                run_fn=lambda spec=spec, context=context: (
                                    analysis_dispatch_module.run_registry_analyzer(spec, context)
                                ),
                                compute_analysis_report_cache_key_fn=report_cache_key,
                            )
                        ),
                    )
                except Exception as exc:  # noqa: BLE001 - report and keep the run going
                    analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
                    message = f"{spec.name} failed: {exc}"
                    emit_line(f"❌ {message}")
                    target_analyzers.append(
                        ChecksAnalyzerResult(
                            key=spec.key,
                            name=str(spec.name),
                            status="failed",
                            summary=message,
                            issue_count=0,
                            duration_ms=analyzer_timings_ms[spec.key],
                        )
                    )
                    continue
                except KeyboardInterrupt:
                    analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
                    target_analyzers.append(
                        ChecksAnalyzerResult(
                            key=spec.key,
                            name=str(spec.name),
                            status="cancelled",
                            duration_ms=analyzer_timings_ms[spec.key],
                        )
                    )
                    profiler.emit(
                        operation="checks",
                        target_name=target_name,
                        duration_ms=(perf_counter() - target_started_at) * 1000,
                        cancelled=True,
                        payload={
                            "selected_analyzers": [selected.key for selected in analyzers],
                            "analyzer_timings_ms": dict(analyzer_timings_ms),
                        },
                    )
                    target_results.append(
                        ChecksTargetResult(
                            target_name=target_name,
                            is_library=is_library,
                            analyzers=tuple(target_analyzers),
                            module=module_tree,
                            stage_timings_ms=stage_timings_ms or None,
                            graphics_timings_ms=graphics_timings_ms or None,
                        )
                    )
                    return ChecksRunResult(
                        output_lines=tuple(output_lines),
                        targets=tuple(target_results),
                        selected_analyzers=selected_analyzer_keys,
                        cancelled=True,
                        failures=tuple(load_failures),
                    )
                analyzer_timings_ms[spec.key] = round((perf_counter() - analyzer_started_at) * 1000, 3)
                _rewrite_typedef_issue_paths(report, context.base_picture)
                phase_timings_ms = profiling_module.normalize_phase_timings_ms(getattr(report, "phase_timings", None))
                if phase_timings_ms:
                    analyzer_phase_timings_ms[spec.key] = phase_timings_ms
                report = normalize_report_target_name(report, target_name)
                summary_text = report.summary()
                findings = extract_report_findings(report, default_name=target_name)
                emit_line(summary_text)
                target_analyzers.append(
                    ChecksAnalyzerResult(
                        key=spec.key,
                        name=str(spec.name),
                        status="completed",
                        summary=summary_text,
                        report_kind=type(report).__name__,
                        issue_count=len(findings),
                        findings=findings,
                        duration_ms=analyzer_timings_ms[spec.key],
                        phase_timings_ms=tuple(analyzer_phase_timings_ms.get(spec.key, [])),
                    )
                )
            analyzer_bottleneck = profiling_module.bottleneck_from_named_timings(analyzer_timings_ms, kind="analyzer")
            analyzer_phase_bottleneck: dict[str, object] | None = None
            for analyzer_key, phase_timings in analyzer_phase_timings_ms.items():
                candidate = profiling_module.bottleneck_from_phase_timings(
                    phase_timings,
                    kind="analyzer-phase",
                    extra_fields={"analyzer_key": analyzer_key},
                )
                if candidate is None:
                    continue
                if analyzer_phase_bottleneck is None or (
                    cast(float, candidate["duration_ms"]) > cast(float, analyzer_phase_bottleneck["duration_ms"])
                ):
                    analyzer_phase_bottleneck = candidate
            payload: dict[str, object] = {
                "selected_analyzers": [spec.key for spec in analyzers],
                "analyzer_timings_ms": dict(analyzer_timings_ms),
            }
            if stage_timings_ms:
                payload["stage_timings_ms"] = stage_timings_ms
            if graphics_timings_ms:
                payload["graphics_timings_ms"] = graphics_timings_ms
            if analyzer_phase_timings_ms:
                payload["analyzer_phase_timings_ms"] = dict(analyzer_phase_timings_ms)
            if analyzer_bottleneck is not None:
                payload["analyzer_bottleneck"] = analyzer_bottleneck
                payload["bottleneck_kind"] = "analyzer"
                payload["bottleneck"] = analyzer_bottleneck
            if analyzer_phase_bottleneck is not None:
                payload["analyzer_phase_bottleneck"] = analyzer_phase_bottleneck
                payload["bottleneck_kind"] = "analyzer-phase"
                payload["bottleneck"] = analyzer_phase_bottleneck
            profiler.emit(
                operation="checks",
                target_name=target_name,
                duration_ms=(perf_counter() - target_started_at) * 1000,
                success=True,
                payload=payload,
            )
            shared_artifact_profile: str | None = None
            if _profile_analyzers_enabled() and context.shared_artifacts is not None:
                shared_artifact_profile = _shared_artifact_profile_text(target_name, context.shared_artifacts)
                emit_line(shared_artifact_profile)
            target_results.append(
                ChecksTargetResult(
                    target_name=target_name,
                    is_library=is_library,
                    analyzers=tuple(target_analyzers),
                    module=module_tree,
                    stage_timings_ms=stage_timings_ms or None,
                    graphics_timings_ms=graphics_timings_ms or None,
                    analyzer_bottleneck=analyzer_bottleneck,
                    analyzer_phase_bottleneck=analyzer_phase_bottleneck,
                    shared_artifact_profile=shared_artifact_profile,
                )
            )
        for per_run_spec in per_run_analyzers:
            per_run_result = _run_per_run_analyzer(per_run_spec, cfg)
            emit_line(f"\n=== {per_run_result.name} ({per_run_result.key}) ===")
            if per_run_result.summary:
                emit_line(per_run_result.summary)
            target_results.append(
                ChecksTargetResult(
                    target_name=str(getattr(per_run_spec, "name", per_run_spec.key)),
                    is_library=False,
                    analyzers=(per_run_result,),
                    is_pseudo=True,
                )
            )
    except KeyboardInterrupt:
        return ChecksRunResult(
            output_lines=tuple(output_lines),
            targets=tuple(target_results),
            selected_analyzers=selected_analyzer_keys,
            cancelled=True,
            failures=tuple(load_failures),
        )

    result = ChecksRunResult(
        output_lines=tuple(output_lines),
        targets=tuple(target_results),
        selected_analyzers=selected_analyzer_keys,
        failures=tuple(load_failures),
    )
    if persist_run:
        stored = _persist_run_result(result, cfg, started_at=run_started_at, project_path=project_path)
        if stored is not None:
            result = replace(result, run_id=stored.run_id)
    return result


def run_checks_result(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    use_cache: bool = True,
    persist_run: bool = True,
    project_path: str = "",
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
        persist_run=persist_run,
        project_path=project_path,
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
    project_path: str = "",
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
        persist_run=True,
        project_path=project_path,
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
