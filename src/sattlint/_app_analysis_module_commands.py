from __future__ import annotations

from collections.abc import Callable, Iterator

from sattline_parser.models.ast_model import BasePicture

from . import _app_analysis_menus as analysis_menus_module
from . import app_analysis as shared
from .analyzers import variable_usage_reporting as variables_reporting_module
from .app_interaction import MenuInteraction
from .config_types import ConfigDict
from .models.project_graph import ProjectGraph

LoadedProject = shared.LoadedProject


def parse_index_selection(selection: str, max_index: int) -> list[int]:
    return analysis_menus_module.parse_index_selection(selection, max_index)


def run_module_duplicates_analysis(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = shared.iter_loaded_projects

    shared.emit_output("\n--- Compare Module Variants ---")
    shared.emit_output("Enter module name(s) to compare (comma-separated):")
    raw_names = interaction.prompt("Module name(s)", None).strip() if interaction is not None else input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        shared.emit_output("❌ No module name provided")
        if pause_fn is not None:
            pause_fn()
        return

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        shared.emit_output(f"\n=== Target: {target_name} ===")
        for module_name in module_names:
            succeeded, result = shared.run_logged_cli_action(
                cfg,
                action=lambda target_name=target_name, project_bp=project_bp, module_name=module_name, interaction=interaction: (
                    shared.run_module_duplicates_for_name(
                        cfg,
                        target_name=target_name,
                        project_bp=project_bp,
                        module_name=module_name,
                        interaction=interaction,
                    )
                ),
                debug_message=f"Module duplicate analysis failed for target {target_name!r} and module {module_name!r}",
                user_message=f"❌ Error during analysis for {module_name!r}: {{error}}",
            )
            if not succeeded or result is None:
                continue
            shared.emit_output("\n" + result.summary())

    if pause_fn is not None:
        pause_fn()


def run_module_find_by_name(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = shared.iter_loaded_projects

    shared.emit_output("\n--- Find Module Instances ---")
    shared.emit_output("Enter module name(s) to search for (comma-separated):")
    raw_names = interaction.prompt("Module name(s)", None).strip() if interaction is not None else input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        shared.emit_output("❌ No module name provided")
        if pause_fn is not None:
            pause_fn()
        return

    def _emit_module_find_results() -> None:
        for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
            shared.emit_output(f"\n=== Target: {target_name} ===")
            for module_name in module_names:
                matches = shared.run_with_live_status(
                    f"Finding module instances in {target_name}: {module_name}",
                    lambda project_bp=project_bp, module_name=module_name: shared.find_modules_by_name(
                        project_bp,
                        module_name,
                        debug=shared.debug_enabled(cfg),
                    ),
                )
                if not matches:
                    shared.emit_output(f"\nNo modules found with name {module_name!r}.")
                    continue
                shared.emit_output(f"\nFound {len(matches)} module instance(s) for {module_name!r}:")
                for path, module in matches:
                    datecode = getattr(module, "datecode", None)
                    datecode_txt = f" (DateCode: {datecode})" if datecode else ""
                    shared.emit_output(f"  - {' -> '.join(path)}{datecode_txt}")

    shared.run_logged_cli_action(
        cfg,
        action=_emit_module_find_results,
        debug_message=f"Module search failed for names {module_names!r}",
        user_message="❌ Error during search: {error}",
    )

    if pause_fn is not None:
        pause_fn()


def run_module_tree_debug(
    cfg: ConfigDict,
    *,
    prompt_fn: Callable[[str, str | None], str],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = shared.iter_loaded_projects

    shared.emit_output("\n--- Debug Module Tree Structure ---")
    max_depth_txt = prompt_fn("Max depth", "10")
    try:
        max_depth = int(max_depth_txt)
    except ValueError:
        shared.emit_output("❌ Invalid depth; using default 10")
        max_depth = 10

    def _emit_module_tree_debug() -> None:
        for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
            shared.emit_output(f"\n=== Target: {target_name} ===")
            shared.run_with_live_status(
                f"Inspecting module tree for {target_name}",
                lambda project_bp=project_bp: shared.debug_module_structure(project_bp, max_depth=max_depth),
            )

    shared.run_logged_cli_action(
        cfg,
        action=_emit_module_tree_debug,
        debug_message=f"Module tree debug failed with max_depth={max_depth}",
        user_message="❌ Error during debug: {error}",
    )

    if pause_fn is not None:
        pause_fn()


def run_module_localvar_analysis(
    cfg: ConfigDict,
    *,
    load_project_fn: Callable[[ConfigDict], tuple[BasePicture, ProjectGraph]],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]] | None = None,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    if iter_loaded_projects_fn is None:
        iter_loaded_projects_fn = shared.iter_loaded_projects

    shared.emit_output("\n--- Module Local Variable Analysis ---")
    shared.emit_output("Enter the module path (strict) relative to BasePicture.")
    shared.emit_output("Example: StartMaster.KaHA251A")
    default_bp, _default_graph = load_project_fn(cfg)
    module_path = (
        interaction.prompt(f"{default_bp.header.name}.", None).strip()
        if interaction is not None
        else input(f"{default_bp.header.name}.").strip()
    )

    if not module_path:
        shared.emit_output("❌ No module path provided")
        if pause_fn is not None:
            pause_fn()
        return

    shared.emit_output("Enter the local variable name (e.g., Dv):")
    var_name = interaction.prompt("Variable name", None).strip() if interaction is not None else input("> ").strip()

    if not var_name:
        shared.emit_output("❌ No variable name provided")
        if pause_fn is not None:
            pause_fn()
        return

    for target_name, project_bp, _graph in iter_loaded_projects_fn(cfg):
        succeeded, report = shared.run_logged_cli_action(
            cfg,
            action=lambda target_name=target_name, module_path=module_path, var_name=var_name, project_bp=project_bp: (
                shared.run_with_live_status(
                    f"Analyzing module local variable in {target_name}: {module_path}.{var_name}",
                    lambda project_bp=project_bp: variables_reporting_module.report_module_localvar_fields(
                        project_bp,
                        module_path,
                        var_name,
                        debug=shared.debug_enabled(cfg),
                    ),
                )
            ),
            debug_message=(
                f"Module local variable analysis failed for target {target_name!r}, "
                f"module {module_path!r}, variable {var_name!r}"
            ),
            user_message=f"❌ Error during analysis for {target_name}: {{error}}",
        )
        if not succeeded or report is None:
            continue
        shared.emit_output(f"\n=== Target: {target_name} ===")
        shared.emit_output(report)

    if pause_fn is not None:
        pause_fn()
