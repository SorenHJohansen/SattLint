"""Menu commands for the application layer.

The terminal-independent analysis workflows behind the interactive menus:
variable analysis, commented-out code, MMS interface variables, and ICF
validation.  This is the menu-oriented counterpart to the CLI command handlers
in :mod:`sattlint.cli.commands`; the roles are distinct and the name reflects
that split.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from time import perf_counter
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef

from .. import console as console_module
from ..analyzers.comment_code import analyze_comment_code_files
from ..analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from ..analyzers.mms import analyze_mms_interface_variables
from ..analyzers.shadowing import analyze_shadowing
from ..analyzers.variables import IssueKind, analyze_variables, filter_variable_report
from ..cache import AnalysisReportCache, compute_analysis_report_cache_key, get_cache_dir
from ..config.types import ConfigDict
from ..core import profiling as profiling_module
from ..core.debug import debug_enabled
from ..core.syntax import CodeMode, code_ext, deps_ext
from ..models.project_graph import ProjectGraph, merge_project_basepicture
from ..project import cache as report_cache_module
from ..project import support as support_module
from ..project.support import is_picture_display_warning
from ..reporting import target_report as report_metadata_module
from ..reporting.variables_report import (
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    VariablesReport,
)
from ..utils.casefolding import casefold_equal
from . import output as output_module
from . import project as project_application

LoadedProject = project_application.LoadedProject

DRAFT_SOURCE_SUFFIXES = frozenset({code_ext(CodeMode.DRAFT), deps_ext(CodeMode.DRAFT)})
OFFICIAL_SOURCE_SUFFIXES = frozenset({code_ext(CodeMode.OFFICIAL), deps_ext(CodeMode.OFFICIAL)})


def parse_index_selection(selection: str, max_index: int) -> list[int]:
    tokens = [token.strip() for token in selection.replace(" ", ",").split(",") if token.strip()]
    indices: set[int] = set()

    for token in tokens:
        if "-" in token:
            parts = [part.strip() for part in token.split("-", 1)]
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                continue
            start = int(parts[0])
            end = int(parts[1])
            if start > end:
                start, end = end, start
            for idx in range(start, end + 1):
                if 1 <= idx <= max_index:
                    indices.add(idx)
        elif token.isdigit():
            idx = int(token)
            if 1 <= idx <= max_index:
                indices.add(idx)

    return sorted(indices)


def run_variable_analysis(  # noqa: PLR0915
    cfg: ConfigDict,
    kinds: set[IssueKind] | None,
    *,
    use_cache: bool = True,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    analyze_variables_fn: Callable[..., VariablesReport] | None = None,
    analyze_shadowing_fn: Callable[..., VariablesReport] | None = None,
    filter_variable_report_fn: Callable[[VariablesReport, set[IssueKind]], VariablesReport] | None = None,
    print_validation_warnings_fn: Callable[[list[str]], None] | None = None,
    target_validation_warnings_fn: Callable[[str, list[str]], list[str]] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = project_application.iter_loaded_projects
    if target_is_library_fn is None:
        target_is_library_fn = project_application.target_is_library
    if analyze_variables_fn is None:
        analyze_variables_fn = analyze_variables
    if analyze_shadowing_fn is None:
        analyze_shadowing_fn = analyze_shadowing
    if filter_variable_report_fn is None:
        filter_variable_report_fn = filter_variable_report
    if print_validation_warnings_fn is None:
        print_validation_warnings_fn = project_application.print_validation_warnings
    if target_validation_warnings_fn is None:
        target_validation_warnings_fn = support_module.target_validation_warnings

    if analyze_variables_fn is None:
        raise RuntimeError("Variable analysis function is unavailable")
    if analyze_shadowing_fn is None:
        raise RuntimeError("Shadowing analysis function is unavailable")
    if filter_variable_report_fn is None:
        raise RuntimeError("Variable report filter is unavailable")
    if print_validation_warnings_fn is None:
        raise RuntimeError("Validation warning printer is unavailable")
    if target_validation_warnings_fn is None:
        raise RuntimeError("Target validation warning helper is unavailable")

    def _merge_reports(*reports: VariablesReport) -> VariablesReport:
        basepicture_name = reports[0].basepicture_name
        issues: list[Any] = []
        visible_kinds: set[IssueKind] = set()
        include_empty_sections = False
        phase_timings: list[dict[str, str | float]] = []

        for report in reports:
            issues.extend(report.issues)
            if report.visible_kinds is not None:
                visible_kinds.update(report.visible_kinds)
            include_empty_sections = include_empty_sections or report.include_empty_sections
            phase_timings.extend(getattr(report, "phase_timings", []))

        return VariablesReport(
            basepicture_name=basepicture_name,
            issues=issues,
            selected_issue_kinds=(frozenset(visible_kinds) if kinds is not None and visible_kinds else None),
            visible_kinds=frozenset(visible_kinds) if visible_kinds else None,
            include_empty_sections=include_empty_sections,
            phase_timings=phase_timings,
        )

    requested_kinds = set(DEFAULT_VARIABLE_ANALYSIS_KINDS) | {IssueKind.SHADOWING} if kinds is None else set(kinds)
    cfg = cast(
        ConfigDict,
        cfg
        | {
            "include_reverse_library_consumers": (
                IssueKind.UNUSED_DATATYPE_FIELD in requested_kinds
                or IssueKind.FIELD_READ_ONLY in requested_kinds
                or IssueKind.FIELD_NEVER_READ in requested_kinds
            )
        },
    )
    report_cache = report_cache_module.create_analysis_report_cache(
        cfg,
        use_cache=use_cache,
        debug_enabled_fn=debug_enabled,
        analysis_report_cache_cls=AnalysisReportCache,
        get_cache_dir_fn=get_cache_dir,
    )
    profiler = profiling_module.create_profiler()

    produced_output = False
    try:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            produced_output = True
            started_at = perf_counter()
            target_is_library = target_is_library_fn(cfg, project_bp, graph)
            include_shadowing = IssueKind.SHADOWING in requested_kinds
            standard_kinds = requested_kinds - {IssueKind.SHADOWING}

            if standard_kinds:
                with console_module.live_status_line() as status_update_fn:
                    status_update_fn(f"Analyzing variable issues for {target_name}")
                    report = report_cache_module.run_with_analysis_report_cache(
                        graph,
                        report_cache=report_cache,
                        analyzer_cache_key=(
                            f"variables:{report_cache_module.variable_issue_kinds_cache_key(standard_kinds)}"
                        ),
                        run_fn=lambda project_bp=project_bp, graph=graph, status_update_fn=status_update_fn, target_is_library=target_is_library, standard_kinds=standard_kinds: (
                            analyze_variables_fn(
                                project_bp,
                                debug=debug_enabled(cfg),
                                unavailable_libraries=report_cache_module.unavailable_libraries(graph),
                                analyzed_target_is_library=target_is_library,
                                selected_issue_kinds=standard_kinds,
                                config=cfg,
                                status_update_fn=status_update_fn,
                            )
                        ),
                        compute_analysis_report_cache_key_fn=compute_analysis_report_cache_key,
                    )
            else:
                report = VariablesReport(
                    basepicture_name=getattr(getattr(project_bp, "header", None), "name", target_name),
                    issues=[],
                    selected_issue_kinds=frozenset(standard_kinds) if kinds is not None else None,
                    visible_kinds=frozenset(),
                    include_empty_sections=False,
                )

            if standard_kinds:
                report = filter_variable_report_fn(report, standard_kinds)

            if include_shadowing:
                shadowing_report = output_module.run_with_live_status(
                    f"Analyzing variable shadowing for {target_name}",
                    lambda project_bp=project_bp, graph=graph: report_cache_module.run_with_analysis_report_cache(
                        graph,
                        report_cache=report_cache,
                        analyzer_cache_key="variables:shadowing",
                        run_fn=lambda project_bp=project_bp, graph=graph: analyze_shadowing_fn(
                            project_bp,
                            debug=debug_enabled(cfg),
                            unavailable_libraries=report_cache_module.unavailable_libraries(graph),
                        ),
                        compute_analysis_report_cache_key_fn=compute_analysis_report_cache_key,
                    ),
                )
                if requested_kinds == {IssueKind.SHADOWING}:
                    report = shadowing_report
                elif standard_kinds:
                    report = _merge_reports(report, shadowing_report)

            report = report_metadata_module.normalize_report_target_name(report, target_name)
            report = report_metadata_module.attach_variable_report_metadata(
                report,
                project_bp,
                graph,
                select_report_source_path_fn=lambda project_bp, graph: report_metadata_module.select_report_source_path(
                    project_bp,
                    graph,
                    source_paths_for_current_target_fn=project_application.source_paths_for_current_target,
                    casefold_equal_fn=casefold_equal,
                ),
                source_version_label_fn=lambda project_bp, graph, source_path: (
                    report_metadata_module.source_version_label(
                        project_bp,
                        graph,
                        source_path,
                        draft_source_suffixes=DRAFT_SOURCE_SUFFIXES,
                        official_source_suffixes=OFFICIAL_SOURCE_SUFFIXES,
                    )
                ),
                source_last_changed_fn=report_metadata_module.source_last_changed,
            )
            output_module.emit_output(f"\n=== Target: {target_name} ===")
            validation_warnings = target_validation_warnings_fn(target_name, getattr(graph, "warnings", []))
            if target_is_library:
                validation_warnings = [item for item in validation_warnings if not is_picture_display_warning(item)]
            print_validation_warnings_fn(validation_warnings)
            output_module.emit_output(report.summary())
            phase_timings_ms = profiling_module.normalize_phase_timings_ms(getattr(report, "phase_timings", None))
            phase_bottleneck = profiling_module.bottleneck_from_phase_timings(phase_timings_ms, kind="phase")
            stage_timings_ms = profiling_module.normalize_named_timings_ms(
                getattr(graph, "load_stage_timings", None), scale=1000.0
            )
            graphics_timings_ms = profiling_module.normalize_named_timings_ms(
                getattr(graph, "graphics_load_timings", None),
                scale=1000.0,
            )
            payload: dict[str, object] = {
                "requested_issue_kinds": sorted(kind.value for kind in requested_kinds),
                "issue_count": len(getattr(report, "issues", [])),
                "shadowing_requested": include_shadowing,
            }
            if stage_timings_ms:
                payload["stage_timings_ms"] = stage_timings_ms
            if graphics_timings_ms:
                payload["graphics_timings_ms"] = graphics_timings_ms
            if phase_timings_ms:
                payload["phase_timings_ms"] = phase_timings_ms
            if phase_bottleneck is not None:
                payload["phase_bottleneck"] = phase_bottleneck
                payload["bottleneck_kind"] = "phase"
                payload["bottleneck"] = phase_bottleneck
            profiler.emit(
                operation="variable-analysis",
                target_name=target_name,
                duration_ms=(perf_counter() - started_at) * 1000,
                success=True,
                payload=payload,
            )
    except KeyboardInterrupt:
        output_module.handle_analysis_cancellation(pause_fn=pause_fn)
        return
    if not produced_output:
        output_module.emit_output("\nNo variable analysis output was produced because no target loaded successfully.")

    if pause_fn is not None:
        pause_fn()


def run_comment_code_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    source_paths_for_current_target_fn: Callable[[BasePicture, ProjectGraph], set[Any]] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = project_application.iter_loaded_projects
    if source_paths_for_current_target_fn is None:
        source_paths_for_current_target_fn = project_application.source_paths_for_current_target

    output_module.emit_output("\n--- Commented-out Code ---")
    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        paths = source_paths_for_current_target_fn(project_bp, graph)
        report = output_module.run_with_live_status(
            f"Analyzing commented-out code for {target_name}",
            lambda paths=paths, target_name=target_name: analyze_comment_code_files(paths, target_name),
        )
        report = report_metadata_module.normalize_report_target_name(report, target_name)
        output_module.emit_output(f"\n=== Target: {target_name} ===")
        output_module.emit_output(report.summary())

    if pause_fn is not None:
        pause_fn()


def run_mms_interface_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = project_application.iter_loaded_projects

    output_module.emit_output("\n--- MMS Interface Variables ---")

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        succeeded, report = output_module.run_logged_cli_action(
            cfg,
            action=lambda target_name=target_name, project_bp=project_bp: output_module.run_with_live_status(
                f"Analyzing MMS interface variables for {target_name}",
                lambda project_bp=project_bp: analyze_mms_interface_variables(
                    project_bp,
                    debug=debug_enabled(cfg),
                    config=cast(dict[str, Any], cfg),
                ),
            ),
            debug_message=f"MMS interface analysis failed for target {target_name!r}",
            user_message=f"❌ Error during analysis for {target_name}: {{error}}",
        )
        if not succeeded or report is None:
            continue
        report = report_metadata_module.normalize_report_target_name(report, target_name)
        output_module.emit_output(f"\n=== Target: {target_name} ===")
        output_module.emit_output(report.summary())

    if pause_fn is not None:
        pause_fn()


def run_icf_validation(
    cfg: ConfigDict,
    *,
    configured_icf_files_fn: Callable[[ConfigDict], tuple[Any, list[Any]]],
    load_program_ast_fn: Callable[[ConfigDict, str], tuple[BasePicture, ProjectGraph]],
    validate_icf_entries_against_program_fn: Callable[..., Any] = validate_icf_entries_against_program,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    icf_dir, icf_files = configured_icf_files_fn(cfg)
    if icf_dir is None:
        output_module.emit_output("❌ icf_dir is not set in the config. Set it before running ICF validation.")
        if pause_fn is not None:
            pause_fn()
        return

    if not icf_dir.exists() or not icf_dir.is_dir():
        output_module.emit_output(f"❌ icf_dir does not exist or is not a directory: {icf_dir}")
        if pause_fn is not None:
            pause_fn()
        return

    if not icf_files:
        output_module.emit_output(f"⚠ No .icf files found in {icf_dir}")
        if pause_fn is not None:
            pause_fn()
        return

    total_entries = 0
    total_valid = 0
    total_invalid = 0
    total_skipped = 0
    files_failed = 0

    output_module.emit_output("\n--- ICF Validation (per program) ---")

    for icf_file in icf_files:
        program_name = icf_file.stem
        entries = parse_icf_file(icf_file)
        if not entries:
            output_module.emit_output(f"⚠ {icf_file.name}: no entries found")
            continue

        succeeded, loaded_program = output_module.run_logged_cli_action(
            cfg,
            action=lambda program_name=program_name: load_program_ast_fn(cfg, program_name),
            debug_message=f"ICF validation failed while loading program {program_name!r} from {icf_file}",
            user_message=f"❌ {icf_file.name}: failed to load program {program_name!r}: {{error}}",
        )
        if not succeeded or loaded_program is None:
            files_failed += 1
            continue
        program_bp, graph = loaded_program
        program_bp = merge_project_basepicture(program_bp, graph)

        moduletype_index: dict[str, list[ModuleTypeDef]] = {}
        for bp in cast(dict[str, BasePicture], graph.ast_by_name).values():
            for mt in cast(list[ModuleTypeDef] | None, bp.moduletype_defs) or []:
                key = mt.name.casefold()
                moduletype_index.setdefault(key, []).append(mt)

        report = output_module.run_with_live_status(
            f"Validating ICF entries for {program_name}",
            lambda program_bp=program_bp, entries=entries, program_name=program_name, moduletype_index=moduletype_index: (
                validate_icf_entries_against_program_fn(
                    program_bp,
                    entries,
                    expected_program=program_name,
                    debug=cfg.get("debug", False),
                    moduletype_index=moduletype_index,
                )
            ),
        )
        output_module.emit_output(report.summary())
        output_module.emit_output("")

        total_entries += report.total_entries
        total_valid += report.valid_entries
        total_invalid += len(report.issues)
        total_skipped += report.skipped_entries

    output_module.emit_output("Summary:")
    output_module.emit_output(f"  Files processed: {len(icf_files)}")
    output_module.emit_output(f"  Files failed: {files_failed}")
    output_module.emit_output(f"  Entries: {total_entries}")
    output_module.emit_output(f"  Valid: {total_valid}")
    output_module.emit_output(f"  Invalid: {total_invalid}")
    output_module.emit_output(f"  Skipped: {total_skipped}")

    if pause_fn is not None:
        pause_fn()
