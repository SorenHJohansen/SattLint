from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import app_support as app_support_module
from . import cache as cache_module
from . import console as console_module
from . import engine as engine_module
from ._app_analysis_variable_analyses import (
    HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS,
    LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS,
    VARIABLE_ANALYSES,
)
from .analyzers import variable_usage_reporting as variables_reporting_module
from .analyzers.comment_code import analyze_comment_code_files
from .analyzers.framework import AnalysisContext
from .analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from .analyzers.mms import analyze_mms_interface_variables
from .analyzers.modules import (
    analyze_module_duplicates,
    compare_modules,
    debug_module_structure,
    find_modules_by_name,
)
from .analyzers.registry import get_default_cli_analyzers
from .analyzers.rule_profiles import apply_rule_profile_to_report
from .analyzers.shadowing import analyze_shadowing
from .analyzers.variable_usage_reporting import debug_variable_usage
from .analyzers.variables import IssueKind, analyze_variables, filter_variable_report
from .cache import ASTCache
from .casefolding import casefold_equal, casefold_key
from .models.project_graph import ProjectGraph
from .reporting.variables_report import DEFAULT_VARIABLE_ANALYSIS_KINDS, VariablesReport

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]

app_support = cast(Any, app_support_module)
cache = cast(Any, cache_module)
engine = cast(Any, engine_module)
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]
compute_cache_key: Callable[[ConfigDict], str] = cache.compute_cache_key
get_cache_dir: Callable[[], Path] = cache.get_cache_dir


def _extract_warning_name(item: str) -> str | None:
    return cast(str | None, app_support.extract_warning_name(item))


def _target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return cast(list[str], app_support.target_validation_warnings(target_name, warnings))


def _print_validation_warnings(warnings: list[str], *, limit: int = 12) -> None:
    if not warnings:
        return

    emit_output(f"Validation warnings ({len(warnings)}):")
    for item in warnings[:limit]:
        _extract_warning_name(item)
        emit_output(f"  - {item}")
    if len(warnings) > limit:
        emit_output(f"  - ... (+{len(warnings) - limit} more)")


def _normalize_report_target_name(report: Any, target_name: str) -> Any:
    if not target_name:
        return report

    for attr_name in ("basepicture_name", "name"):
        if not hasattr(report, attr_name):
            continue
        try:
            setattr(report, attr_name, target_name)
        except AttributeError:
            continue
    return report


def _get_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return cast(list[str], app_support.get_analyzed_targets(cfg))


def _require_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return cast(list[str], app_support.require_analyzed_targets(cfg))


def _cache_key_for_target(cfg: ConfigDict, target_name: str) -> str:
    cache_cfg = cfg.copy()
    cache_cfg["analysis_target"] = target_name
    return compute_cache_key(cache_cfg)


def _iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] | None = None,
) -> Iterator[LoadedProject]:
    loader = load_project if load_project_fn is None else load_project_fn
    for target_name in require_analyzed_targets_fn(cfg):
        try:
            project_bp, graph = loader(
                cfg,
                target_name=target_name,
                use_cache=use_cache,
            )
        except Exception as exc:
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output("? Failed to load target:")
            emit_output(exc)
            continue
        yield target_name, project_bp, graph


def iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] | None = None,
) -> Iterator[LoadedProject]:
    return _iter_loaded_projects(
        cfg,
        use_cache=use_cache,
        require_analyzed_targets_fn=require_analyzed_targets_fn,
        load_project_fn=load_project_fn,
    )


def _source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    source_files: set[Path] = getattr(graph, "source_files", set())
    origin_file = getattr(project_bp, "origin_file", None)
    if origin_file:
        matches = {path for path in source_files if casefold_equal(path.name, origin_file)}
        if matches:
            return matches

    target_name = casefold_key(project_bp.header.name)
    return {path for path in source_files if casefold_key(path.stem) == target_name}


def source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    return _source_paths_for_current_target(project_bp, graph)


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    program_dir = cfg.get("program_dir")
    if not program_dir:
        return False

    source_paths = _source_paths_for_current_target(project_bp, graph)
    if not source_paths:
        return False

    program_path = Path(program_dir)
    return all(not engine._is_within_directory(path, program_path) for path in source_paths)


def target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return _target_is_library(cfg, project_bp, graph)


def load_project(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
    require_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _require_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    target_load_error_factory: Callable[..., Exception] | None = None,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
) -> tuple[BasePicture, ProjectGraph]:
    targets = require_analyzed_targets_fn(cfg)
    selected_target = target_name or targets[0]
    cache_dir = get_cache_dir_fn()
    cache = ASTCache(cache_dir)

    key = cache_key_for_target_fn(cfg, selected_target)
    cached = cache.load(key) if use_cache else None

    if cached:
        return cast(tuple[BasePicture, ProjectGraph], cached["project"])

    loader = engine.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(p) for p in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine.CodeMode(cfg["mode"]),
        scan_root_only=cfg["scan_root_only"],
        debug=cfg["debug"],
        use_file_ast_cache=use_file_ast_cache,
    )

    graph = loader.resolve(selected_target, strict=False)
    deps_path = loader._find_deps_with_context(
        selected_target,
        requester_dir=Path(cfg["program_dir"]),
    )
    direct_dependencies = cast(list[str], loader._read_deps(deps_path) if deps_path else [])

    root_bp = graph.ast_by_name.get(selected_target)
    if not root_bp:
        if target_load_error_factory is None:
            raise RuntimeError(f"Target {selected_target!r} was not parsed.")
        raise target_load_error_factory(
            selected_target,
            resolved=list(graph.ast_by_name.keys()),
            missing=graph.missing,
            warnings=graph.warnings,
            direct_dependencies=direct_dependencies,
        )

    project_bp = engine.merge_project_basepicture(root_bp, graph)
    used_files = set(graph.source_files)
    cache_backend = cast(Any, cache)
    cache_backend.save(
        key,
        project=(project_bp, graph),
        files=used_files,
    )
    return project_bp, graph


def load_program_ast(
    cfg: ConfigDict,
    program_name: str,
    *,
    force_dependency_resolution: bool = False,
) -> tuple[BasePicture, ProjectGraph]:
    loader = engine.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(p) for p in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine.CodeMode(cfg["mode"]),
        scan_root_only=False if force_dependency_resolution else cfg["scan_root_only"],
        debug=cfg["debug"],
    )

    graph = loader.resolve(program_name, strict=False)
    root_bp = graph.ast_by_name.get(program_name)
    if not root_bp:
        raise RuntimeError(f"Program '{program_name}' not parsed. Resolved: {list(graph.ast_by_name.keys())}")

    return root_bp, graph


def force_refresh_ast(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _get_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] = load_project,
    ast_cache_cls: type[ASTCache] = ASTCache,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
) -> tuple[BasePicture, ProjectGraph] | None:
    targets = get_analyzed_targets_fn(cfg)
    if not targets:
        return None

    cache = ast_cache_cls(get_cache_dir_fn())
    cache_backend = cast(Any, cache)
    result = None
    total_targets = len(targets)
    emit_output(f"Refreshing AST caches for {total_targets} target(s)...")
    for index, target_name in enumerate(targets, start=1):
        emit_output(f"\nRefreshing AST cache for {target_name}... ({index}/{total_targets})")
        cache_backend.clear(cache_key_for_target_fn(cfg, target_name))
        result = load_project_fn(
            cfg,
            target_name=target_name,
            use_cache=False,
            use_file_ast_cache=False,
        )
        emit_output("OK AST cache refreshed")
    return result


def ensure_ast_cache(
    cfg: ConfigDict,
    *,
    get_analyzed_targets_fn: Callable[[ConfigDict], list[str]] = _get_analyzed_targets,
    cache_key_for_target_fn: Callable[[ConfigDict, str], str] = _cache_key_for_target,
    load_project_fn: Callable[..., tuple[BasePicture, ProjectGraph]] = load_project,
    ast_cache_cls: type[ASTCache] = ASTCache,
    get_cache_dir_fn: Callable[[], Path] = get_cache_dir,
) -> bool:
    targets = get_analyzed_targets_fn(cfg)
    if not targets:
        return True

    cache = ast_cache_cls(get_cache_dir_fn())
    cache_backend = cast(Any, cache)
    fast = cfg.get("fast_cache_validation", False)
    ok = True
    total_targets = len(targets)
    emit_output(f"Refreshing AST caches for {total_targets} target(s)...")
    for index, target_name in enumerate(targets, start=1):
        emit_output(f"\nChecking AST cache for {target_name}... ({index}/{total_targets})")
        cached = cache_backend.load(cache_key_for_target_fn(cfg, target_name))
        if cached:
            has_manifest = bool(cached.get("files"))
            if fast and has_manifest:
                is_valid = cast(bool, cache_backend.validate(cached, fast=False))
            else:
                is_valid = cast(bool, cache_backend.validate(cached, fast=fast))
            if is_valid:
                emit_output("✔ AST cache OK")
                continue

            if has_manifest:
                emit_output("⚠ AST cache stale; rebuilding (this may take a while)...")
            else:
                emit_output("⚠ AST cache missing file manifest; rebuilding (this may take a while)...")
        else:
            emit_output("⚠ AST cache missing; building (this may take a while)...")

        try:
            load_project_fn(cfg, target_name=target_name, use_cache=False)
            emit_output("✔ AST cache updated")
        except Exception as exc:
            emit_output(f"❌ Failed to build AST cache for {target_name}: {exc}")
            ok = False

    return ok


def _debug_enabled(cfg: ConfigDict) -> bool:
    return bool(cfg.get("debug", False))


def _unavailable_libraries(graph: ProjectGraph) -> set[str]:
    return cast(set[str], getattr(graph, "unavailable_libraries", set[str]()))


def run_variable_analysis(
    cfg: ConfigDict,
    kinds: set[IssueKind] | None,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] | None = None,
    analyze_variables_fn: Callable[..., VariablesReport] | None = None,
    analyze_shadowing_fn: Callable[..., VariablesReport] | None = None,
    filter_variable_report_fn: Callable[[VariablesReport, set[IssueKind]], VariablesReport] | None = None,
    print_validation_warnings_fn: Callable[[list[str]], None] | None = None,
    target_validation_warnings_fn: Callable[[str, list[str]], list[str]] | None = None,
    pause_fn: Callable[[], None] | None = None,
):
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = _iter_loaded_projects
    if target_is_library_fn is None:
        target_is_library_fn = _target_is_library
    if analyze_variables_fn is None:
        analyze_variables_fn = analyze_variables
    if analyze_shadowing_fn is None:
        analyze_shadowing_fn = analyze_shadowing
    if filter_variable_report_fn is None:
        filter_variable_report_fn = filter_variable_report
    if print_validation_warnings_fn is None:
        print_validation_warnings_fn = _print_validation_warnings
    if target_validation_warnings_fn is None:
        target_validation_warnings_fn = _target_validation_warnings

    def _merge_reports(*reports: VariablesReport) -> VariablesReport:
        basepicture_name = reports[0].basepicture_name
        issues: list[Any] = []
        visible_kinds: set[IssueKind] = set()
        include_empty_sections = False

        for report in reports:
            issues.extend(report.issues)
            if report.visible_kinds is not None:
                visible_kinds.update(report.visible_kinds)
            include_empty_sections = include_empty_sections or report.include_empty_sections

        return VariablesReport(
            basepicture_name=basepicture_name,
            issues=issues,
            visible_kinds=frozenset(visible_kinds) if visible_kinds else None,
            include_empty_sections=include_empty_sections,
        )

    requested_kinds = set(DEFAULT_VARIABLE_ANALYSIS_KINDS) | {IssueKind.SHADOWING} if kinds is None else set(kinds)

    produced_output = False
    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        produced_output = True
        target_is_library = target_is_library_fn(cfg, project_bp, graph)
        report = analyze_variables_fn(
            project_bp,
            debug=_debug_enabled(cfg),
            unavailable_libraries=_unavailable_libraries(graph),
            analyzed_target_is_library=target_is_library,
            config=cfg,
        )

        include_shadowing = IssueKind.SHADOWING in requested_kinds
        standard_kinds = requested_kinds - {IssueKind.SHADOWING}

        if standard_kinds:
            report = filter_variable_report_fn(report, standard_kinds)
        else:
            report = VariablesReport(
                basepicture_name=report.basepicture_name,
                issues=[],
                visible_kinds=frozenset(),
                include_empty_sections=False,
            )

        if include_shadowing:
            shadowing_report = analyze_shadowing_fn(
                project_bp,
                debug=_debug_enabled(cfg),
                unavailable_libraries=_unavailable_libraries(graph),
            )
            if requested_kinds == {IssueKind.SHADOWING}:
                report = shadowing_report
            elif standard_kinds:
                report = _merge_reports(report, shadowing_report)

        report = _normalize_report_target_name(report, target_name)
        emit_output(f"\n=== Target: {target_name} ===")
        print_validation_warnings_fn(target_validation_warnings_fn(target_name, getattr(graph, "warnings", [])))
        emit_output(report.summary())
    if not produced_output:
        emit_output("\nNo variable analysis output was produced because no target loaded successfully.")

    if pause_fn is not None:
        pause_fn()


def run_datatype_usage_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = _iter_loaded_projects

    emit_output("\n--- Datatype Usage Analysis ---")
    emit_output("Enter the variable name to analyze:")
    var_name = input("> ").strip()

    if not var_name:
        emit_output("❌ No variable name provided")
        if pause_fn is not None:
            pause_fn()
        return

    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        try:
            report = variables_reporting_module.analyze_datatype_usage(
                project_bp,
                var_name,
                debug=_debug_enabled(cfg),
                unavailable_libraries=_unavailable_libraries(graph),
            )
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output(report)
        except Exception as exc:
            emit_output(f"❌ Error during analysis for {target_name}: {exc}")

    if pause_fn is not None:
        pause_fn()


def variable_usage_submenu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    quit_app_fn: Callable[[], None],
    run_variable_analysis_fn: Callable[[ConfigDict, set[IssueKind] | None], None],
    run_datatype_usage_analysis_fn: Callable[[ConfigDict], None],
    run_debug_variable_usage_fn: Callable[[ConfigDict], None],
    run_module_localvar_analysis_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    while True:
        clear_screen_fn()
        emit_output("\n--- Variable issues ---")
        emit_output("Run focused variable reports or open the investigation tools for deeper tracing.")
        emit_output()
        emit_output("High confidence:")
        emit_output("1) All variable analyses (high confidence)")
        for key in HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS:
            name, _ = VARIABLE_ANALYSES[key]
            emit_output(f"{key}) {name}")
        emit_output("\nLow confidence:")
        for key in LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS:
            name, _ = VARIABLE_ANALYSES[key]
            emit_output(f"{key}) {name}")
        emit_output("\nInvestigation tools:")
        emit_output("22) Datatype usage analysis           Trace field-level usage for one variable name")
        emit_output("23) Variable usage trace              Show fields and locations for one variable name")
        emit_output("24) Module local variable analysis    Inspect field usage inside one module path")
        emit_output("b) Back")
        emit_output("q) Quit")

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()
        if choice == "22":
            run_datatype_usage_analysis_fn(cfg)
        elif choice == "23":
            run_debug_variable_usage_fn(cfg)
        elif choice == "24":
            run_module_localvar_analysis_fn(cfg)
        elif choice in VARIABLE_ANALYSES:
            _name, kinds = VARIABLE_ANALYSES[choice]
            run_variable_analysis_fn(cfg, kinds)
        else:
            emit_output("Invalid choice.")
            pause_fn()


def module_analysis_submenu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_module_duplicates_analysis_fn: Callable[[ConfigDict], None],
    run_module_find_by_name_fn: Callable[[ConfigDict], None],
    run_module_tree_debug_fn: Callable[[ConfigDict], None],
    run_graphics_rules_validation_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    while True:
        clear_screen_fn()
        print_menu_fn(
            "Structure & modules",
            [
                menu_option_factory("1", "Compare module variants", "Compare matching module names across instances"),
                menu_option_factory("2", "Find module instances", "List where a module name appears in the target"),
                menu_option_factory("3", "Inspect module tree", "Print the module tree for debugging structure"),
                menu_option_factory(
                    "4", "Validate graphics rules", "Check configured graphics rules against loaded modules"
                ),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro="Use these tools when you need to inspect module layout, duplication, or structural drift.",
        )

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        if choice == "1":
            run_module_duplicates_analysis_fn(cfg)
        elif choice == "2":
            run_module_find_by_name_fn(cfg)
        elif choice == "3":
            run_module_tree_debug_fn(cfg)
        elif choice == "4":
            run_graphics_rules_validation_fn(cfg)
        else:
            emit_output("Invalid choice.")
            pause_fn()


def interface_communication_submenu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_mms_interface_analysis_fn: Callable[[ConfigDict], None],
    run_icf_validation_fn: Callable[[ConfigDict], None],
    run_icf_formatter_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    while True:
        clear_screen_fn()
        print_menu_fn(
            "Interfaces & communication",
            [
                menu_option_factory(
                    "1", "MMS interface variables", "Inventory MMSWriteVar or MMSReadVar usage and related checks"
                ),
                menu_option_factory("2", "Validate ICF paths", "Validate ICF entries against each program AST"),
                menu_option_factory(
                    "3",
                    "Format ICF files",
                    "Normalize Unit, Journal, Operation, and Group spacing in configured .icf files",
                ),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro="Check external interfaces and communication-related wiring for the current targets.",
        )

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        if choice == "1":
            run_mms_interface_analysis_fn(cfg)
        elif choice == "2":
            run_icf_validation_fn(cfg)
        elif choice == "3":
            run_icf_formatter_fn(cfg)
        else:
            emit_output("Invalid choice.")
            pause_fn()


def code_quality_submenu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_comment_code_analysis_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    while True:
        clear_screen_fn()
        print_menu_fn(
            "Code quality",
            [
                menu_option_factory("1", "Commented-out code", "Scan raw source comments for code-like content"),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro="Use these checks for readability and maintainability issues rather than runtime semantics.",
        )

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        if choice == "1":
            run_comment_code_analysis_fn(cfg)
        else:
            emit_output("Invalid choice.")
            pause_fn()


def analyzer_catalog_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    get_enabled_analyzers_fn: Callable[[], list[Any]],
    run_checks_fn: Callable[[ConfigDict, list[str] | None], None],
    pause_fn: Callable[[], None],
) -> None:
    while True:
        clear_screen_fn()
        analyzers = get_enabled_analyzers_fn()
        options = [
            menu_option_factory("1", "Run full analyzer suite", "Run every default analyzer in sequence"),
        ]
        options.extend(
            menu_option_factory(str(index), spec.name, spec.description)
            for index, spec in enumerate(analyzers, start=2)
        )
        options.extend([menu_option_factory("b", "Back", ""), menu_option_factory("q", "Quit", "")])
        print_menu_fn(
            "Analyzer catalog",
            options,
            intro=(
                "This view exposes the registry-backed analyzers directly. "
                "Only the default analyzer set is exposed here so low-confidence analyzers "
                "never run from the CLI suite."
            ),
        )

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        if choice == "1":
            run_checks_fn(cfg, None)
        elif choice.isdigit():
            index = int(choice) - 2
            if 0 <= index < len(analyzers):
                run_checks_fn(cfg, [analyzers[index].key])
            else:
                emit_output("Invalid choice.")
                pause_fn()
        else:
            emit_output("Invalid choice.")
            pause_fn()


def advanced_analysis_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_datatype_usage_analysis_fn: Callable[[ConfigDict], None],
    run_debug_variable_usage_fn: Callable[[ConfigDict], None],
    run_module_localvar_analysis_fn: Callable[[ConfigDict], None],
    pause_fn: Callable[[], None],
) -> None:
    while True:
        clear_screen_fn()
        print_menu_fn(
            "Advanced analysis & debug",
            [
                menu_option_factory(
                    "1", "Datatype usage analysis", "Trace field-level usage for a selected variable name"
                ),
                menu_option_factory(
                    "2", "Variable usage trace", "Show fields and locations for a selected variable name"
                ),
                menu_option_factory(
                    "3", "Module local variable analysis", "Inspect field usage inside one module path"
                ),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro="Use these tools when the summary reports are not specific enough and you need targeted tracing.",
        )

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        if choice == "1":
            run_datatype_usage_analysis_fn(cfg)
        elif choice == "2":
            run_debug_variable_usage_fn(cfg)
        elif choice == "3":
            run_module_localvar_analysis_fn(cfg)
        else:
            emit_output("Invalid choice.")
            pause_fn()


def analysis_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    run_checks_fn: Callable[[ConfigDict, list[str] | None], None],
    variable_usage_submenu_fn: Callable[[ConfigDict], None],
    module_analysis_submenu_fn: Callable[[ConfigDict], None],
    interface_communication_submenu_fn: Callable[[ConfigDict], None],
    code_quality_submenu_fn: Callable[[ConfigDict], None],
    analyzer_catalog_menu_fn: Callable[[ConfigDict], None],
    advanced_analysis_menu_fn: Callable[[ConfigDict], None],
    summarize_targets_fn: Callable[[ConfigDict], str],
    pause_fn: Callable[[], None],
) -> None:
    while True:
        clear_screen_fn()
        print_menu_fn(
            "Analyze",
            [
                menu_option_factory("1", "Full analyzer suite", "Run every enabled registry-backed analyzer"),
                menu_option_factory("2", "Variable issues", "Focused variable reports and investigation tools"),
                menu_option_factory(
                    "3", "Structure & modules", "Inspect module layout, duplication, and tree structure"
                ),
                menu_option_factory("4", "Interfaces & communication", "Check MMS mappings and validate ICF paths"),
                menu_option_factory("5", "Code quality", "Readability and maintainability checks"),
                menu_option_factory("6", "Analyzer catalog", "Choose one registry-backed analyzer by name"),
                menu_option_factory(
                    "7", "Advanced analysis & debug", "Targeted tracing for variables and module locals"
                ),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro=(
                "Run checks against the configured programs or libraries. "
                "Use the full analyzer suite for a broad pass, then drill into the focused menus if you need detail."
            ),
            note=summarize_targets_fn(cfg),
        )

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        if choice == "1":
            run_checks_fn(cfg, None)
        elif choice == "2":
            variable_usage_submenu_fn(cfg)
        elif choice == "3":
            module_analysis_submenu_fn(cfg)
        elif choice == "4":
            interface_communication_submenu_fn(cfg)
        elif choice == "5":
            code_quality_submenu_fn(cfg)
        elif choice == "6":
            analyzer_catalog_menu_fn(cfg)
        elif choice == "7":
            advanced_analysis_menu_fn(cfg)
        else:
            emit_output("Invalid choice.")
            pause_fn()


def _parse_index_selection(selection: str, max_index: int) -> list[int]:
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


def run_module_duplicates_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- Compare Module Variants ---")
    emit_output("Enter module name(s) to compare (comma-separated):")
    raw_names = input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        emit_output("❌ No module name provided")
        if pause_fn is not None:
            pause_fn()
        return

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        emit_output(f"\n=== Target: {target_name} ===")
        for module_name in module_names:
            try:
                matches = find_modules_by_name(project_bp, module_name, debug=_debug_enabled(cfg))
                if not matches:
                    emit_output(f"\n⚠ No modules found with name {module_name!r}.")
                    continue

                emit_output(f"\nFound {len(matches)} instance(s) for {module_name!r}:")
                for idx, (path, module) in enumerate(matches, 1):
                    datecode = getattr(module, "datecode", None)
                    datecode_txt = f" (DateCode: {datecode})" if datecode else ""
                    emit_output(f"  {idx}) {' -> '.join(path)}{datecode_txt}")

                emit_output("\nSelect instances to compare (e.g., 6,7).")
                emit_output("Press Enter to compare all instances.")
                selection = input("> ").strip()

                if selection:
                    indices = _parse_index_selection(selection, len(matches))
                    if len(indices) < 2:
                        emit_output("⚠ Need at least two instances to compare; skipping.")
                        continue
                    selected = [matches[i - 1] for i in indices]
                    result = compare_modules(selected)
                else:
                    result = analyze_module_duplicates(project_bp, module_name, debug=_debug_enabled(cfg))

                emit_output("\n" + result.summary())
            except Exception as exc:
                emit_output(f"❌ Error during analysis for {module_name!r}: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_module_find_by_name(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- Find Module Instances ---")
    emit_output("Enter module name(s) to search for (comma-separated):")
    raw_names = input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        emit_output("❌ No module name provided")
        if pause_fn is not None:
            pause_fn()
        return

    try:
        for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
            emit_output(f"\n=== Target: {target_name} ===")
            for module_name in module_names:
                matches = find_modules_by_name(project_bp, module_name, debug=_debug_enabled(cfg))
                if not matches:
                    emit_output(f"\nNo modules found with name {module_name!r}.")
                    continue
                emit_output(f"\nFound {len(matches)} module instance(s) for {module_name!r}:")
                for path, module in matches:
                    datecode = getattr(module, "datecode", None)
                    datecode_txt = f" (DateCode: {datecode})" if datecode else ""
                    emit_output(f"  - {' -> '.join(path)}{datecode_txt}")
    except Exception as exc:
        emit_output(f"❌ Error during search: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_module_tree_debug(
    cfg: ConfigDict,
    *,
    prompt_fn: Callable[[str, str | None], str],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- Debug Module Tree Structure ---")
    max_depth_txt = prompt_fn("Max depth", "10")
    try:
        max_depth = int(max_depth_txt)
    except ValueError:
        emit_output("❌ Invalid depth; using default 10")
        max_depth = 10

    try:
        for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
            emit_output(f"\n=== Target: {target_name} ===")
            debug_module_structure(project_bp, max_depth=max_depth)
    except Exception as exc:
        emit_output(f"❌ Error during debug: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_analysis_menu(cfg: ConfigDict, *, analysis_menu_fn: Callable[[ConfigDict], None]) -> None:
    analysis_menu_fn(cfg)


def variable_analysis_menu(cfg: ConfigDict, *, analysis_menu_fn: Callable[[ConfigDict], None]) -> None:
    analysis_menu_fn(cfg)


def run_module_localvar_analysis(
    cfg: ConfigDict,
    *,
    load_project_fn: Callable[[ConfigDict], tuple[BasePicture, ProjectGraph]],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- Module Local Variable Analysis ---")
    emit_output("Enter the module path (strict) relative to BasePicture.")
    emit_output("Example: StartMaster.KaHA251A")
    default_bp, _default_graph = load_project_fn(cfg)
    module_path = input(f"{default_bp.header.name}.").strip()

    if not module_path:
        emit_output("❌ No module path provided")
        if pause_fn is not None:
            pause_fn()
        return

    emit_output("Enter the local variable name (e.g., Dv):")
    var_name = input("> ").strip()

    if not var_name:
        emit_output("❌ No variable name provided")
        if pause_fn is not None:
            pause_fn()
        return

    from .analyzers.variable_usage_reporting import analyze_module_localvar_fields

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        try:
            report = analyze_module_localvar_fields(
                project_bp,
                module_path,
                var_name,
                debug=_debug_enabled(cfg),
            )
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output(report)
        except Exception as exc:
            emit_output(f"❌ Error during analysis for {target_name}: {exc}")

    if pause_fn is not None:
        pause_fn()


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], get_default_cli_analyzers())


def _run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    get_enabled_analyzers_fn: Callable[[], list[Any]] = _get_enabled_analyzers,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] = _target_is_library,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    analyzers = get_enabled_analyzers_fn()
    if selected_keys:
        selected = {key.casefold() for key in selected_keys}
        analyzers = [spec for spec in analyzers if spec.key.casefold() in selected]

    if not analyzers:
        emit_output("❌ No matching checks found")
        if pause_fn is not None:
            pause_fn()
        return

    emit_output("\n--- Running checks ---")
    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        context = AnalysisContext(
            base_picture=project_bp,
            graph=graph,
            debug=_debug_enabled(cfg),
            target_is_library=target_is_library_fn(cfg, project_bp, graph),
            config=cfg,
        )
        emit_output(f"\n=== Target: {target_name} ===")
        for spec in analyzers:
            emit_output(f"\n=== {spec.name} ({spec.key}) ===")
            report = spec.run(context)
            report = apply_rule_profile_to_report(spec.key, report, cfg)
            report = _normalize_report_target_name(report, target_name)
            emit_output(report.summary())

    if pause_fn is not None:
        pause_fn()


def run_checks(
    cfg: ConfigDict,
    selected_keys: list[str] | None,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    get_enabled_analyzers_fn: Callable[[], list[Any]] = _get_enabled_analyzers,
    target_is_library_fn: Callable[[ConfigDict, BasePicture, ProjectGraph], bool] = _target_is_library,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    _run_checks(
        cfg,
        selected_keys,
        iter_loaded_projects_fn=iter_loaded_projects_fn,
        get_enabled_analyzers_fn=get_enabled_analyzers_fn,
        target_is_library_fn=target_is_library_fn,
        pause_fn=pause_fn,
    )


def run_checks_menu(cfg: ConfigDict, *, run_checks_fn: Callable[[ConfigDict, list[str] | None], None]) -> None:
    run_checks_fn(cfg, None)


def parse_index_selection(selection: str, max_index: int) -> list[int]:
    return _parse_index_selection(selection, max_index)


def run_mms_interface_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- MMS Interface Variables ---")

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        try:
            report = analyze_mms_interface_variables(
                project_bp,
                debug=_debug_enabled(cfg),
                config=cfg,
            )
            report = _normalize_report_target_name(report, target_name)
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output(report.summary())
        except Exception as exc:
            emit_output(f"❌ Error during analysis for {target_name}: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_icf_validation(
    cfg: ConfigDict,
    *,
    configured_icf_files_fn: Callable[[ConfigDict], tuple[Path | None, list[Path]]],
    load_program_ast_fn: Callable[[ConfigDict, str], tuple[BasePicture, ProjectGraph]],
    validate_icf_entries_against_program_fn: Callable[..., Any] = validate_icf_entries_against_program,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    icf_dir, icf_files = configured_icf_files_fn(cfg)
    if icf_dir is None:
        emit_output("❌ icf_dir is not set in the config. Set it before running ICF validation.")
        if pause_fn is not None:
            pause_fn()
        return

    if not icf_dir.exists() or not icf_dir.is_dir():
        emit_output(f"❌ icf_dir does not exist or is not a directory: {icf_dir}")
        if pause_fn is not None:
            pause_fn()
        return

    if not icf_files:
        emit_output(f"⚠ No .icf files found in {icf_dir}")
        if pause_fn is not None:
            pause_fn()
        return

    total_entries = 0
    total_valid = 0
    total_invalid = 0
    total_skipped = 0
    files_failed = 0

    emit_output("\n--- ICF Validation (per program) ---")

    for icf_file in icf_files:
        program_name = icf_file.stem
        entries = parse_icf_file(icf_file)
        if not entries:
            emit_output(f"⚠ {icf_file.name}: no entries found")
            continue

        try:
            program_bp, graph = load_program_ast_fn(cfg, program_name)
            program_bp = engine_module.merge_project_basepicture(program_bp, graph)
        except Exception as exc:
            emit_output(f"❌ {icf_file.name}: failed to load program {program_name!r}: {exc}")
            files_failed += 1
            continue

        moduletype_index: dict[str, list[engine_module.ModuleTypeDef]] = {}
        for bp in graph.ast_by_name.values():
            for mt in bp.moduletype_defs or []:
                key = mt.name.casefold()
                moduletype_index.setdefault(key, []).append(mt)

        report = validate_icf_entries_against_program_fn(
            program_bp,
            entries,
            expected_program=program_name,
            debug=cfg.get("debug", False),
            moduletype_index=moduletype_index,
        )
        emit_output(report.summary())
        emit_output("")

        total_entries += report.total_entries
        total_valid += report.valid_entries
        total_invalid += len(report.issues)
        total_skipped += report.skipped_entries

    emit_output("Summary:")
    emit_output(f"  Files processed: {len(icf_files)}")
    emit_output(f"  Files failed: {files_failed}")
    emit_output(f"  Entries: {total_entries}")
    emit_output(f"  Valid: {total_valid}")
    emit_output(f"  Invalid: {total_invalid}")
    emit_output(f"  Skipped: {total_skipped}")

    if pause_fn is not None:
        pause_fn()


def run_debug_variable_usage(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- Variable Usage (Fields + Locations) ---")
    emit_output("Enter the variable name to analyze:")
    var_name = input("> ").strip()

    if not var_name:
        emit_output("❌ No variable name provided")
        if pause_fn is not None:
            pause_fn()
        return

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        try:
            report = debug_variable_usage(project_bp, var_name, debug=_debug_enabled(cfg))
            emit_output(f"\n=== Target: {target_name} ===")
            emit_output(report)
        except Exception as exc:
            emit_output(f"❌ Error during debug for {target_name}: {exc}")

    if pause_fn is not None:
        pause_fn()


def run_comment_code_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] = _iter_loaded_projects,
    source_paths_for_current_target_fn: Callable[
        [BasePicture, ProjectGraph], set[Path]
    ] = _source_paths_for_current_target,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    emit_output("\n--- Commented-out Code ---")
    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        paths = source_paths_for_current_target_fn(project_bp, graph)
        report = analyze_comment_code_files(paths, target_name)
        report = _normalize_report_target_name(report, target_name)
        emit_output(f"\n=== Target: {target_name} ===")
        emit_output(report.summary())

    if pause_fn is not None:
        pause_fn()


def run_advanced_datatype_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = _iter_loaded_projects

    emit_output("\n--- Advanced Datatype Analysis ---")
    emit_output("1) Analyze variable by name (field-level usage)")
    emit_output("2) Compare module variants by name")
    emit_output("3) Debug specific variable usage")
    emit_output("b) Back")

    choice = input("> ").strip()

    if choice == "1":
        var_name = input("Enter variable name: ").strip()
        if var_name:
            for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
                report = variables_reporting_module.analyze_datatype_usage(
                    project_bp,
                    var_name,
                    debug=_debug_enabled(cfg),
                    unavailable_libraries=_unavailable_libraries(graph),
                )
                emit_output(f"\n=== Target: {target_name} ===")
                emit_output(report)

    elif choice == "2":
        module_name = input("Enter module name to compare: ").strip()
        if module_name:
            emit_output("⚠ Module comparison analysis not yet implemented")

    elif choice == "3":
        var_name = input("Enter variable name to debug: ").strip()
        if var_name:
            for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
                report = variables_reporting_module.debug_variable_usage(
                    project_bp,
                    var_name,
                    debug=_debug_enabled(cfg),
                )
                emit_output(f"\n=== Target: {target_name} ===")
                emit_output(report)

    if pause_fn is not None:
        pause_fn()
