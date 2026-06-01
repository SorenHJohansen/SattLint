#!/usr/bin/env python3
"""CLI entry points and interactive helpers for SattLint."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import _app_analysis_from_app as app_analysis_from_app_module
from . import _app_docs_from_app as app_docs_from_app_module
from . import _app_graphics_from_app as app_graphics_from_app_module
from . import _app_menus_from_app as app_menus_from_app_module
from . import _app_startup_from_app as app_startup_module
from . import app_analysis as app_analysis_module
from . import app_base as app_base_module
from . import app_cli_commands as app_cli_commands_module
from . import app_docs as app_docs_module
from . import app_graphics as app_graphics_module
from . import app_menus as app_menus_module
from . import app_support as app_support_module
from . import app_telemetry as app_telemetry_module
from . import cache as cache_module
from . import config as _config_module
from . import console as console_module
from . import engine as engine_module_impl
from . import telemetry_summary as telemetry_summary_module
from .analyzers.registry import get_default_analyzers, get_default_cli_analyzers
from .analyzers.shadowing import analyze_shadowing
from .analyzers.variables import (
    IssueKind,
    analyze_variables,
    filter_variable_report,
)
from .cache import ASTCache
from .core.semantic import load_workspace_snapshot
from .devtools import source_diff_report as source_diff_report_module
from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]
VariableAnalysisSelection = set[IssueKind] | None
VariableAnalysisMap = dict[str, tuple[str, VariableAnalysisSelection]]
GraphicsRulesConfig = dict[str, Any]
GraphicsRulesLoadResult = tuple[GraphicsRulesConfig, bool]
DocumentationSelection = dict[str, Any]
LoadedConfig = tuple[ConfigDict, bool]
ConfigValidationResult = _config_module.ConfigValidationResult

app_analysis = cast(Any, app_analysis_module)
app_base = cast(Any, app_base_module)
app_cli_commands = cast(Any, app_cli_commands_module)
app_docs = cast(Any, app_docs_module)
app_graphics = cast(Any, app_graphics_module)
app_menus = cast(Any, app_menus_module)
app_support = cast(Any, app_support_module)
app_telemetry = cast(Any, app_telemetry_module)
cache = cast(Any, cache_module)
engine_module: Any = engine_module_impl
telemetry_summary = cast(Any, telemetry_summary_module)

VARIABLE_ANALYSES: VariableAnalysisMap = app_analysis.VARIABLE_ANALYSES
HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = app_analysis.HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS: tuple[str, ...] = app_analysis.LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS
emit_output: Callable[..., None] = console_module.print_output  # type: ignore[assignment]


EXIT_SUCCESS: int = app_base.EXIT_SUCCESS
EXIT_FAILURE: int = app_base.EXIT_FAILURE
EXIT_USAGE_ERROR: int = app_base.EXIT_USAGE_ERROR

CONFIG_PATH: Path = app_base.CONFIG_PATH
DEFAULT_CONFIG: ConfigDict = app_base.DEFAULT_CONFIG


@dataclass(frozen=True)
class MenuOption:
    key: str
    label: str
    description: str = ""


TargetLoadError = app_support.TargetLoadError


def _print_validation_warnings(warnings: list[str], *, limit: int = 12) -> None:
    app_support.print_validation_warnings(warnings, print_fn=print, limit=limit)


def _target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return cast(list[str], app_support.target_validation_warnings(target_name, warnings))


def load_config(path: Path) -> LoadedConfig:
    return cast(LoadedConfig, app_base.load_config(path))


def get_cache_dir() -> Path:
    return cast(Path, cache.get_cache_dir())


def save_config(path: Path, cfg: ConfigDict) -> None:
    app_base.save_config(path, cfg)


def get_graphics_rules_path() -> Path:
    return cast(Path, app_graphics.get_graphics_rules_path(CONFIG_PATH))


def load_graphics_rules(path: Path | None = None) -> GraphicsRulesLoadResult:
    return cast(GraphicsRulesLoadResult, app_graphics.load_graphics_rules(CONFIG_PATH, path))


def save_graphics_rules(path: Path, rules: dict[str, Any]) -> None:
    app_graphics.save_graphics_rules(path, rules)
    emit_output("Graphics rules saved")


def self_check(cfg: ConfigDict) -> bool:
    return cast(bool, app_base.self_check(cfg))


def validate_effective_config(cfg: ConfigDict) -> ConfigValidationResult:
    return _config_module.validate_effective_config(cfg)


log: Any = app_base.log
_APP_MODULE: Any = cast(Any, sys.modules[__name__])


# ----------------------------
# Helpers
# ----------------------------
def _clear_windows_console() -> None:
    app_base.clear_windows_console()


def clear_screen() -> None:
    app_base.clear_screen(os_module=os, sys_module=sys, clear_windows_console=_clear_windows_console)


def pause() -> None:
    app_base.pause()


QuitAppError = app_base.QuitAppError


def quit_app() -> None:
    app_base.quit_app(clear_screen_fn=clear_screen)


def confirm(msg: str) -> bool:
    return cast(bool, app_base.confirm(msg))


def prompt(msg: str, default: str | None = None) -> str:
    return cast(str, app_base.prompt(msg, default))


def target_exists(target: str, cfg: ConfigDict) -> bool:
    return cast(bool, app_base.target_exists(target, cfg))


def apply_debug(cfg: ConfigDict) -> None:
    app_base.apply_debug(cfg)


def build_cli_parser() -> argparse.ArgumentParser:
    return cast(argparse.ArgumentParser, app_base.build_cli_parser())


def run_syntax_check_command(file_path: str) -> int:
    return cast(int, app_base.run_syntax_check_command(file_path))


def run_cli(argv: list[str]) -> int:
    return app_startup_module.run_cli_from_app(argv, app_module=_APP_MODULE)


def run_validate_config_command(cfg: ConfigDict, *, config_path: Path, default_used: bool) -> int:
    return app_startup_module.run_validate_config_command_from_app(
        cfg,
        config_path=config_path,
        default_used=default_used,
        app_module=_APP_MODULE,
    )


def run_analyze_command(cfg: ConfigDict, *, selected_keys: list[str] | None, use_cache: bool) -> int:
    return app_startup_module.run_analyze_command_from_app(
        cfg,
        selected_keys=selected_keys,
        use_cache=use_cache,
        app_module=_APP_MODULE,
    )


def _simulate_target(
    cfg: ConfigDict,
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    use_cache: bool,
) -> Any:
    from .simulation import simulate_snapshot_target

    del cfg, use_cache
    snapshot = load_workspace_snapshot(
        Path(target_path),
        collect_variable_diagnostics=False,
    )
    return simulate_snapshot_target(
        snapshot,
        module_name=module_name,
        mode=mode,
        max_scans=max_scans,
    )


def run_simulate_command(
    cfg: ConfigDict,
    *,
    target_path: str,
    module_name: str,
    mode: str,
    max_scans: int,
    output_format: str,
    output_path: str | None,
    use_cache: bool,
) -> int:
    return app_startup_module.run_simulate_command_from_app(
        cfg,
        target_path=target_path,
        module_name=module_name,
        mode=mode,
        max_scans=max_scans,
        output_format=output_format,
        output_path=output_path,
        use_cache=use_cache,
        app_module=_APP_MODULE,
    )


def run_docgen_command(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
    output_dir: str | None = None,
    output_path: str | None = None,
) -> int:
    return app_startup_module.run_docgen_command_from_app(
        cfg,
        use_cache=use_cache,
        output_dir=output_dir,
        output_path=output_path,
        app_module=_APP_MODULE,
    )


def run_telemetry_summary_command(
    cfg: ConfigDict,
    *,
    config_path: Path,
    output_format: str,
    output_path: str | None,
) -> int:
    return app_startup_module.run_telemetry_summary_command_from_app(
        cfg,
        config_path=config_path,
        output_format=output_format,
        output_path=output_path,
        app_module=_APP_MODULE,
    )


def _configured_icf_files(cfg: ConfigDict) -> tuple[Path | None, list[Path]]:
    return cast(tuple[Path | None, list[Path]], app_support.configured_icf_files(cfg))


def run_format_icf_command(cfg: ConfigDict, *, check: bool = False) -> int:
    return cast(
        int,
        app_support.run_format_icf_command(
            cfg,
            check=check,
            print_fn=print,
            exit_success=EXIT_SUCCESS,
            exit_usage_error=EXIT_USAGE_ERROR,
        ),
    )


def run_icf_formatter(cfg: ConfigDict) -> None:
    app_startup_module.run_icf_formatter_from_app(cfg, app_module=_APP_MODULE)


def show_config(cfg: ConfigDict) -> None:
    app_startup_module.show_config_from_app(cfg, app_module=_APP_MODULE)


def _print_menu(
    title: str,
    options: Sequence[MenuOption],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    app_startup_module.print_menu_from_app(title, options, intro=intro, note=note, app_module=_APP_MODULE)


def _menu_option(key: str, label: str, description: str) -> MenuOption:
    return MenuOption(key, label, description)


def _summarize_targets(cfg: ConfigDict) -> str:
    return app_startup_module.summarize_targets_from_app(cfg, app_module=_APP_MODULE)


def show_help(cfg: ConfigDict) -> None:
    app_startup_module.show_help_from_app(cfg, app_module=_APP_MODULE)


def _get_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return cast(list[str], app_support.get_analyzed_targets(cfg))


def _require_analyzed_targets(cfg: ConfigDict) -> list[str]:
    return cast(list[str], app_support.require_analyzed_targets(cfg))


def _has_analyzed_targets(cfg: ConfigDict) -> bool:
    return cast(bool, app_support.has_analyzed_targets(cfg, get_analyzed_targets_fn=_get_analyzed_targets))


def _require_targets_for_menu_action(cfg: ConfigDict, action: str) -> bool:
    return cast(
        bool,
        app_support.require_targets_for_menu_action(
            cfg,
            action,
            has_analyzed_targets_fn=_has_analyzed_targets,
            print_fn=print,
            pause_fn=pause,
        ),
    )


def _cache_key_for_target(cfg: ConfigDict, target_name: str) -> str:
    compute_cache_key_fn = cast(Callable[[ConfigDict], str], cache.compute_cache_key)
    return cast(str, app_support.cache_key_for_target(cfg, target_name, compute_cache_key_fn=compute_cache_key_fn))


def _split_csv_values(raw: str) -> list[str]:
    return cast(list[str], app_support.split_csv_values(raw))


_graphics_rule_label: Callable[[dict[str, Any]], str] = app_graphics.graphics_rule_label
_graphics_rule_config_line: Callable[[dict[str, Any]], str] = app_graphics.graphics_rule_config_line
_print_graphics_rules_summary: Callable[..., None] = app_graphics.print_graphics_rules_summary
config_module = _config_module
classify_documentation_structure: Callable[..., Any] = app_docs.classify_documentation_structure
discover_documentation_unit_candidates: Callable[..., list[Any]] = app_docs.discover_documentation_unit_candidates
validate_icf_entries_against_program: Callable[..., Any] = app_analysis.validate_icf_entries_against_program


def _discover_graphics_rule_selector_options(
    cfg: ConfigDict | None,
    *,
    selector_field: str,
    module_kind: str,
) -> list[dict[str, Any]]:
    return app_graphics_from_app_module.discover_graphics_rule_selector_options_from_app(
        cfg,
        selector_field=selector_field,
        module_kind=module_kind,
        app_module=_APP_MODULE,
    )


def _pick_or_prompt_graphics_rule_selector_value(
    selector_field: str,
    module_kind: str,
    *,
    cfg: ConfigDict | None = None,
) -> str:
    return app_graphics_from_app_module.pick_or_prompt_graphics_rule_selector_value_from_app(
        selector_field,
        module_kind,
        cfg=cfg,
        app_module=_APP_MODULE,
    )


def _annotate_graphics_entries_with_structure_paths(
    entries: list[dict[str, Any]],
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> list[dict[str, Any]]:
    return app_graphics_from_app_module.annotate_graphics_entries_with_structure_paths_from_app(
        entries,
        project_bp,
        graph,
        app_module=_APP_MODULE,
    )


def graphics_rules_menu(cfg: ConfigDict | None = None) -> None:
    app_graphics_from_app_module.graphics_rules_menu_from_app(cfg, app_module=_APP_MODULE)


def _prompt_graphics_rule_definition_with_config(cfg: ConfigDict | None) -> dict[str, Any] | None:
    return app_graphics_from_app_module.prompt_graphics_rule_definition_with_config_from_app(
        cfg,
        app_module=_APP_MODULE,
    )


def _collect_graphics_layout_entries_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> list[dict[str, Any]]:
    return app_graphics_from_app_module.collect_graphics_layout_entries_for_target_from_app(
        target_name,
        project_bp,
        graph,
        app_module=_APP_MODULE,
    )


def run_graphics_rules_validation(cfg: ConfigDict) -> None:
    app_graphics_from_app_module.run_graphics_rules_validation_from_app(cfg, app_module=_APP_MODULE)


def _get_documentation_unit_selection() -> DocumentationSelection:
    return app_docs_from_app_module.get_documentation_unit_selection_from_app(app_module=_APP_MODULE)


def preview_documentation_unit_candidates(cfg: ConfigDict) -> None:
    app_docs_from_app_module.preview_documentation_unit_candidates_from_app(cfg, app_module=_APP_MODULE)


def configure_documentation_scope_by_moduletype(cfg: ConfigDict) -> bool:
    del cfg
    return app_docs_from_app_module.configure_documentation_scope_by_moduletype_from_app(app_module=_APP_MODULE)


def configure_documentation_scope_by_instance_path(cfg: ConfigDict) -> bool:
    del cfg
    return app_docs_from_app_module.configure_documentation_scope_by_instance_path_from_app(app_module=_APP_MODULE)


def reset_documentation_scope(cfg: ConfigDict) -> bool:
    del cfg
    return app_docs_from_app_module.reset_documentation_scope_from_app(app_module=_APP_MODULE)


def run_generate_documentation(cfg: ConfigDict) -> None:
    app_docs_from_app_module.run_generate_documentation_from_app(cfg, app_module=_APP_MODULE)


def documentation_menu(cfg: ConfigDict) -> bool:
    return app_docs_from_app_module.documentation_menu_from_app(cfg, app_module=_APP_MODULE)


def _iter_loaded_projects(
    cfg: ConfigDict,
    *,
    use_cache: bool = True,
) -> Iterator[LoadedProject]:
    return cast(
        Iterator[LoadedProject],
        app_analysis.iter_loaded_projects(
            cfg,
            use_cache=use_cache,
            require_analyzed_targets_fn=_require_analyzed_targets,
            load_project_fn=load_project,
        ),
    )


def _source_paths_for_current_target(project_bp: BasePicture, graph: ProjectGraph) -> set[Path]:
    return cast(set[Path], app_analysis.source_paths_for_current_target(project_bp, graph))


def _target_is_library(cfg: ConfigDict, project_bp: BasePicture, graph: ProjectGraph) -> bool:
    return cast(bool, app_analysis.target_is_library(cfg, project_bp, graph))


def load_project(
    cfg: ConfigDict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
    refresh_mode: str = "full",
    collect_stage_timings: bool = False,
) -> tuple[BasePicture, ProjectGraph]:
    return cast(
        tuple[BasePicture, ProjectGraph],
        app_analysis.load_project(
            cfg,
            target_name=target_name,
            use_cache=use_cache,
            use_file_ast_cache=use_file_ast_cache,
            refresh_mode=refresh_mode,
            collect_stage_timings=collect_stage_timings,
            require_analyzed_targets_fn=_require_analyzed_targets,
            cache_key_for_target_fn=_cache_key_for_target,
            target_load_error_factory=TargetLoadError,
            get_cache_dir_fn=get_cache_dir,
        ),
    )


def load_program_ast(
    cfg: ConfigDict,
    program_name: str,
    *,
    force_dependency_resolution: bool = False,
) -> tuple[BasePicture, ProjectGraph]:
    return cast(
        tuple[BasePicture, ProjectGraph],
        app_analysis.load_program_ast(
            cfg,
            program_name,
            force_dependency_resolution=force_dependency_resolution,
        ),
    )


def force_refresh_ast(cfg: ConfigDict) -> tuple[BasePicture, ProjectGraph] | None:
    return cast(
        tuple[BasePicture, ProjectGraph] | None,
        app_analysis.force_refresh_ast(
            cfg,
            get_analyzed_targets_fn=_get_analyzed_targets,
            cache_key_for_target_fn=_cache_key_for_target,
            load_project_fn=load_project,
            ast_cache_cls=ASTCache,
            get_cache_dir_fn=get_cache_dir,
        ),
    )


def ensure_ast_cache(cfg: ConfigDict) -> bool:
    return cast(
        bool,
        app_analysis.ensure_ast_cache(
            cfg,
            get_analyzed_targets_fn=_get_analyzed_targets,
            cache_key_for_target_fn=_cache_key_for_target,
            load_project_fn=load_project,
            ast_cache_cls=ASTCache,
            get_cache_dir_fn=get_cache_dir,
        ),
    )


def run_variable_analysis(cfg: ConfigDict, kinds: set[IssueKind] | None) -> None:
    app_analysis.run_variable_analysis(
        cfg,
        kinds,
        iter_loaded_projects_fn=_iter_loaded_projects,
        target_is_library_fn=_target_is_library,
        analyze_variables_fn=analyze_variables,
        analyze_shadowing_fn=analyze_shadowing,
        filter_variable_report_fn=filter_variable_report,
        print_validation_warnings_fn=_print_validation_warnings,
        target_validation_warnings_fn=_target_validation_warnings,
        pause_fn=pause,
    )


def run_datatype_usage_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_datatype_usage_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def variable_usage_submenu(cfg: ConfigDict) -> None:
    app_analysis_from_app_module.variable_usage_submenu_from_app(cfg, app_module=_APP_MODULE)


def module_analysis_submenu(cfg: ConfigDict) -> None:
    app_analysis_from_app_module.module_analysis_submenu_from_app(cfg, app_module=_APP_MODULE)


def interface_communication_submenu(cfg: ConfigDict) -> None:
    app_analysis_from_app_module.interface_communication_submenu_from_app(cfg, app_module=_APP_MODULE)


def code_quality_submenu(cfg: ConfigDict) -> None:
    app_analysis_from_app_module.code_quality_submenu_from_app(cfg, app_module=_APP_MODULE)


def analyzer_catalog_menu(cfg: ConfigDict) -> None:
    app_analysis_from_app_module.analyzer_catalog_menu_from_app(cfg, app_module=_APP_MODULE)


def advanced_analysis_menu(cfg: ConfigDict) -> None:
    app_analysis_from_app_module.advanced_analysis_menu_from_app(cfg, app_module=_APP_MODULE)


def analysis_menu(cfg: ConfigDict) -> None:
    app_analysis_from_app_module.analysis_menu_from_app(cfg, app_module=_APP_MODULE)


def run_module_duplicates_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_module_duplicates_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_module_find_by_name(cfg: ConfigDict) -> None:
    app_analysis.run_module_find_by_name(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_module_tree_debug(cfg: ConfigDict) -> None:
    app_analysis.run_module_tree_debug(
        cfg,
        prompt_fn=prompt,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_analysis_menu(cfg: ConfigDict) -> None:
    app_analysis.run_analysis_menu(cfg, analysis_menu_fn=analysis_menu)


def variable_analysis_menu(cfg: ConfigDict) -> None:
    app_analysis.variable_analysis_menu(cfg, analysis_menu_fn=analysis_menu)


def run_module_localvar_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_module_localvar_analysis(
        cfg,
        load_project_fn=load_project,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def _get_enabled_analyzers() -> list[Any]:
    return cast(list[Any], get_default_cli_analyzers())


def _get_selectable_analyzers() -> list[Any]:
    return cast(list[Any], get_default_analyzers())


def _run_checks(cfg: ConfigDict, selected_keys: list[str] | None) -> None:
    app_analysis.run_checks(
        cfg,
        selected_keys,
        iter_loaded_projects_fn=_iter_loaded_projects,
        get_enabled_analyzers_fn=_get_selectable_analyzers if selected_keys else _get_enabled_analyzers,
        target_is_library_fn=_target_is_library,
        pause_fn=pause,
    )


def run_checks_menu(cfg: ConfigDict) -> None:
    app_analysis.run_checks_menu(cfg, run_checks_fn=_run_checks)


def run_mms_interface_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_mms_interface_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_icf_validation(cfg: ConfigDict) -> None:
    def _load_program_ast(local_cfg: ConfigDict, program_name: str) -> tuple[BasePicture, ProjectGraph]:
        return load_program_ast(local_cfg, program_name, force_dependency_resolution=True)

    app_analysis.run_icf_validation(
        cfg,
        configured_icf_files_fn=_configured_icf_files,
        load_program_ast_fn=_load_program_ast,
        validate_icf_entries_against_program_fn=validate_icf_entries_against_program,
        pause_fn=pause,
    )


def run_debug_variable_usage(cfg: ConfigDict) -> None:
    app_analysis.run_debug_variable_usage(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def run_comment_code_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_comment_code_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        source_paths_for_current_target_fn=_source_paths_for_current_target,
        pause_fn=pause,
    )


def run_advanced_datatype_analysis(cfg: ConfigDict) -> None:
    app_analysis.run_advanced_datatype_analysis(
        cfg,
        iter_loaded_projects_fn=_iter_loaded_projects,
        pause_fn=pause,
    )


def dump_menu(cfg: ConfigDict) -> None:
    app_menus_from_app_module.dump_menu_from_app(cfg, app_module=_APP_MODULE)


def _collect_source_diff_pairs_for_paths(source_paths: set[Path]) -> list[tuple[Path, Path]]:
    grouped: dict[tuple[Path, str], dict[str, Path]] = {}
    for source_path in source_paths:
        resolved = source_path.resolve()
        suffix = resolved.suffix.casefold()
        if suffix not in {".s", ".x"}:
            continue
        key = (resolved.parent, resolved.stem.casefold())
        pair = grouped.setdefault(key, {})

        if suffix == ".s":
            pair["draft"] = resolved
        elif suffix == ".x":
            pair["official"] = resolved

        sibling_draft = resolved.with_suffix(".s")
        sibling_official = resolved.with_suffix(".x")
        if sibling_draft.exists():
            pair["draft"] = sibling_draft.resolve()
        if sibling_official.exists():
            pair["official"] = sibling_official.resolve()

    pairs: list[tuple[Path, Path]] = []
    for pair in grouped.values():
        draft = pair.get("draft")
        official = pair.get("official")
        if draft is None or official is None:
            continue
        pairs.append((draft, official))
    return sorted(pairs, key=lambda item: (item[0].stem.casefold(), str(item[0]).casefold()))


def run_source_diff_report(cfg: ConfigDict) -> None:
    workspace_root = Path(cfg.get("program_dir") or ".").resolve()
    pair_reports: list[dict[str, Any]] = []
    selection_errors: list[dict[str, str]] = []
    seen_pairs: set[tuple[Path, Path]] = set()

    unique_pairs: list[tuple[Path, Path]] = []
    with console_module.live_status_line() as status_update_fn:
        status_update_fn("Source diff: resolving comparison pairs")
        for target_name, project_bp, graph in _iter_loaded_projects(cfg):
            status_update_fn(f"Source diff: collecting comparison pairs for {target_name}")
            source_paths = _source_paths_for_current_target(project_bp, graph)
            target_pairs = _collect_source_diff_pairs_for_paths(source_paths)
            if not target_pairs:
                selection_errors.append(
                    {
                        "draft_file": "",
                        "official_file": "",
                        "message": f"No same-basename .s/.x pair was found for analysis target '{target_name}'.",
                    }
                )
                continue

            for draft_file, official_file in target_pairs:
                pair_key = (draft_file.resolve(), official_file.resolve())
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                unique_pairs.append((draft_file, official_file))

        total_pairs = len(unique_pairs)
        for index, (draft_file, official_file) in enumerate(unique_pairs, start=1):
            status_update_fn(f"Source diff: comparing {index}/{total_pairs} {draft_file.name}")
            pair_reports.append(
                source_diff_report_module.build_pair_report(
                    draft_file,
                    official_file,
                    workspace_root=workspace_root,
                )
            )

    error_count = len(selection_errors) + sum(1 for report in pair_reports if report["status"] == "error")
    status = "ok"
    if error_count and not pair_reports:
        status = "error"
    elif error_count:
        status = "partial"

    report = {
        "generated_by": "sattlint.app.tools_menu",
        "report_kind": "source-diff-report",
        "status": status,
        "workspace_root": str(workspace_root),
        "summary": {
            "compared_pair_count": len(pair_reports),
            "changed_pair_count": sum(1 for report in pair_reports if report["changed"]),
            "identical_pair_count": sum(1 for report in pair_reports if report["classification"] == "identical"),
            "layout_only_pair_count": sum(1 for report in pair_reports if report["classification"] == "layout-only"),
            "structural_pair_count": sum(1 for report in pair_reports if report["classification"] == "structural"),
            "error_count": error_count,
        },
        "pairs": pair_reports,
        "selection_errors": selection_errors,
    }
    emit_output(source_diff_report_module.render_markdown(report))
    pause()


# ----------------------------
# Config submenu
# ----------------------------


def config_menu(cfg: ConfigDict) -> bool:
    return app_menus_from_app_module.config_menu_from_app(cfg, app_module=_APP_MODULE)


def tools_menu(cfg: ConfigDict) -> None:
    app_menus_from_app_module.tools_menu_from_app(cfg, app_module=_APP_MODULE)


# ----------------------------
# Main loop
# ----------------------------
_COMPATIBILITY_HELPERS = (
    _print_menu,
    _menu_option,
    _summarize_targets,
    _graphics_rule_label,
    _simulate_target,
    _require_targets_for_menu_action,
    _split_csv_values,
    _discover_graphics_rule_selector_options,
    _pick_or_prompt_graphics_rule_selector_value,
    _annotate_graphics_entries_with_structure_paths,
    _prompt_graphics_rule_definition_with_config,
    _collect_graphics_layout_entries_for_target,
    _get_documentation_unit_selection,
)


def main(argv: list[str] | None = None) -> int:
    return app_startup_module.main_from_app(argv, app_module=_APP_MODULE)


cli = cast(Callable[[], int], partial(app_startup_module.cli_from_app, app_module=_APP_MODULE))


if __name__ == "__main__":
    raise SystemExit(cli())
