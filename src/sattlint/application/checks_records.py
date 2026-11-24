"""Run-record assembly and persistence for the checks pipeline."""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from sattlint.parser_api import BasePicture, FrameModule, ModuleTypeDef, ModuleTypeInstance, SingleModule

from ..config.types import ConfigDict
from ..models.project_graph import ProjectGraph
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
from .checks_results import ChecksAnalyzerResult, ChecksRunResult, ChecksTargetResult

__all__ = ["build_run_record", "persist_run_result", "snapshot_module_tree", "utc_now_iso"]


def utc_now_iso() -> str:
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
        load_duration_ms=result.load_duration_ms,
    )


def snapshot_module_tree(base_picture: BasePicture, graph: ProjectGraph, target_name: str) -> RunModuleRecord:
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
        started_at=started_at or utc_now_iso(),
        finished_at=utc_now_iso(),
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


def persist_run_result(
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
