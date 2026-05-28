from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from . import console as console_module
from . import engine as engine_module
from .casefolding import casefold_equal
from .models.project_graph import ProjectGraph

emit_output = console_module.print_output  # type: ignore[assignment]

ConfigDict = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


def _build_config_menu_options(menu_option_factory: Callable[[str, str, str], Any]) -> list[Any]:
    return [
        menu_option_factory("1", "Add analysis target", "Add a program or library name without file extension"),
        menu_option_factory("2", "Remove analysis target", "Remove one configured analysis target"),
        menu_option_factory("3", "Toggle mode", "Switch between official and draft file mode"),
        menu_option_factory("4", "Toggle scan_root_only", "Restrict dependency scanning to the root directory"),
        menu_option_factory("5", "Toggle fast_cache_validation", "Use faster but lighter AST cache checks"),
        menu_option_factory("6", "Change program_dir", "Set the main SattLine program directory"),
        menu_option_factory("7", "Change ABB_lib_dir", "Set the ABB or shared library directory"),
        menu_option_factory("8", "Edit other_lib_dirs", "Add or remove additional library directories"),
        menu_option_factory("9", "Save configuration", "Write the current configuration to disk"),
        menu_option_factory("10", "Change icf_dir", "Set the directory used for ICF validation"),
        menu_option_factory("11", "Toggle debug", "Show extra debugging output while running"),
        menu_option_factory("12", "Edit graphics rules", "Manage the JSON graphics rules used by the graphics check"),
        menu_option_factory("b", "Back", ""),
        menu_option_factory("q", "Quit", ""),
    ]


def _add_analysis_target(
    cfg: ConfigDict,
    *,
    prompt_fn: Callable[..., str],
    target_exists_fn: Callable[[str, ConfigDict], bool],
    confirm_fn: Callable[[str], bool],
    pause_fn: Callable[[], None],
) -> bool:
    targets = cfg["analyzed_programs_and_libraries"]
    new = prompt_fn("Program/library name to add", None)
    if not target_exists_fn(new, cfg):
        emit_output("❌ Target not found in configured directories")
        pause_fn()
        return False
    if any(casefold_equal(existing, new) for existing in targets):
        emit_output("⚠ Target already listed")
        pause_fn()
        return False
    if not confirm_fn(f"Add '{new}' to analyzed_programs_and_libraries?"):
        return False
    targets.append(new)
    return True


def _remove_analysis_target(
    cfg: ConfigDict,
    *,
    prompt_fn: Callable[..., str],
    confirm_fn: Callable[[str], bool],
    pause_fn: Callable[[], None],
) -> bool:
    targets = cfg["analyzed_programs_and_libraries"]
    if not targets:
        emit_output("⚠ No analyzed targets configured")
        pause_fn()
        return False

    emit_output("\nCurrent analyzed_programs_and_libraries:")
    for index, target in enumerate(targets, 1):
        emit_output(f"{index}. {target}")

    idx_txt = prompt_fn("Index to remove", None)
    try:
        idx = int(idx_txt) - 1
    except ValueError:
        emit_output("❌ Invalid index")
        pause_fn()
        return False

    if 0 <= idx < len(targets) and confirm_fn(f"Remove '{targets[idx]}' from analyzed_programs_and_libraries?"):
        targets.pop(idx)
        return True
    return False


def _toggle_config_value(
    cfg: ConfigDict,
    key: str,
    *,
    confirm_message: str,
    confirm_fn: Callable[[str], bool],
    on_change_fn: Callable[[ConfigDict], None] | None = None,
) -> bool:
    if not confirm_fn(confirm_message):
        return False
    cfg[key] = not cfg[key]
    if on_change_fn is not None:
        on_change_fn(cfg)
    return True


def _update_config_value(
    cfg: ConfigDict,
    key: str,
    *,
    prompt_message: str,
    confirm_message: str,
    prompt_fn: Callable[..., str],
    confirm_fn: Callable[[str], bool],
) -> bool:
    new_value = prompt_fn(prompt_message, cfg[key])
    if not confirm_fn(confirm_message):
        return False
    cfg[key] = new_value
    return True


def _edit_other_lib_dirs(
    cfg: ConfigDict,
    *,
    prompt_fn: Callable[..., str],
    confirm_fn: Callable[[str], bool],
) -> bool:
    libs = cfg["other_lib_dirs"]
    emit_output("\nCurrent other_lib_dirs:")
    for index, path in enumerate(libs, 1):
        emit_output(f"{index}. {path}")
    if confirm_fn("Add new entry?"):
        libs.append(prompt_fn("Path", None))
        return True
    if confirm_fn("Remove entry?"):
        idx = int(prompt_fn("Index", None)) - 1
        if 0 <= idx < len(libs):
            libs.pop(idx)
            return True
    return False


def _save_configuration(
    cfg: ConfigDict,
    *,
    dirty: bool,
    config_path: Path,
    save_config_fn: Callable[[Path, ConfigDict], None],
    confirm_fn: Callable[[str], bool],
) -> bool:
    if confirm_fn("Save config to disk?"):
        try:
            save_config_fn(config_path, cfg)
        except OSError as exc:
            emit_output(f"Failed to save config to {config_path}: {exc}")
            return True
        return False
    return dirty


def _handle_config_menu_exit(
    cfg: ConfigDict,
    *,
    dirty: bool,
    config_path: Path,
    save_config_fn: Callable[[Path, ConfigDict], None],
    confirm_fn: Callable[[str], bool],
    quit_app_fn: Callable[[], None],
) -> None:
    if dirty and confirm_fn("Unsaved config changes. Save before quitting?"):
        try:
            save_config_fn(config_path, cfg)
        except OSError as exc:
            emit_output(f"Failed to save config to {config_path}: {exc}")
            return
    quit_app_fn()
    sys.exit(0)


def dump_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    confirm_fn: Callable[[str], bool],
    iter_loaded_projects_fn: Callable[..., Iterator[LoadedProject]],
    analyze_variables_fn: Callable[..., Any],
) -> None:
    while True:
        clear_screen_fn()
        print_menu_fn(
            "Diagnostics & dumps",
            [
                menu_option_factory("1", "Dump parse tree", "Write the parser tree for each loaded target"),
                menu_option_factory("2", "Dump AST", "Write the merged AST for each loaded target"),
                menu_option_factory(
                    "3", "Dump dependency graph", "Write dependency graph output for each loaded target"
                ),
                menu_option_factory(
                    "4", "Print variable report", "Print the full variable summary without entering the variable menu"
                ),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro="Use these tools when you need raw diagnostics or want to inspect parser and dependency artifacts.",
        )
        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        if choice == "1" and confirm_fn("Dump parse tree?"):
            for _target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
                engine_module.dump_parse_tree((project_bp, graph))
        elif choice == "2" and confirm_fn("Dump AST?"):
            for _target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
                engine_module.dump_ast((project_bp, graph))
        elif choice == "3" and confirm_fn("Dump dependency graph?"):
            for _target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
                engine_module.dump_dependency_graph((project_bp, graph))
        elif choice == "4" and confirm_fn("Dump variable report?"):
            for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
                unavailable_libraries = cast(set[str], getattr(graph, "unavailable_libraries", cast(set[str], set())))
                emit_output(f"\n=== Target: {target_name} ===")
                emit_output(
                    analyze_variables_fn(
                        project_bp,
                        debug=cfg.get("debug", False),
                        unavailable_libraries=unavailable_libraries,
                        config=cfg,
                    ).summary()
                )
        else:
            emit_output("Invalid choice.")


def config_menu(
    cfg: ConfigDict,
    *,
    config_path: Path,
    clear_screen_fn: Callable[[], None],
    show_config_fn: Callable[[ConfigDict], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    prompt_fn: Callable[..., str],
    pause_fn: Callable[[], None],
    confirm_fn: Callable[[str], bool],
    target_exists_fn: Callable[[str, ConfigDict], bool],
    save_config_fn: Callable[[Path, ConfigDict], None],
    apply_debug_fn: Callable[[ConfigDict], None],
    graphics_rules_menu_fn: Callable[[ConfigDict], None],
    quit_app_fn: Callable[[], None],
) -> bool:
    dirty = False
    while True:
        clear_screen_fn()
        show_config_fn(cfg)
        print_menu_fn(
            "Setup",
            _build_config_menu_options(menu_option_factory),
            intro=(
                "Setup controls what SattLint loads and analyzes. "
                "Start here on first run, then save and use Tools -> Self-check diagnostics to confirm the paths."
            ),
        )
        choice = input("> ").strip().lower()

        if choice == "b":
            return dirty
        if choice == "q":
            _handle_config_menu_exit(
                cfg,
                dirty=dirty,
                config_path=config_path,
                save_config_fn=save_config_fn,
                confirm_fn=confirm_fn,
                quit_app_fn=quit_app_fn,
            )

        if choice == "1":
            dirty = (
                _add_analysis_target(
                    cfg,
                    prompt_fn=prompt_fn,
                    target_exists_fn=target_exists_fn,
                    confirm_fn=confirm_fn,
                    pause_fn=pause_fn,
                )
                or dirty
            )

        elif choice == "2":
            dirty = (
                _remove_analysis_target(
                    cfg,
                    prompt_fn=prompt_fn,
                    confirm_fn=confirm_fn,
                    pause_fn=pause_fn,
                )
                or dirty
            )

        elif choice == "3":
            new = "draft" if cfg["mode"] == "official" else "official"
            if confirm_fn(f"Switch mode to '{new}'?"):
                cfg["mode"] = new
                dirty = True

        elif choice == "4":
            dirty = (
                _toggle_config_value(
                    cfg,
                    "scan_root_only",
                    confirm_message="Toggle scan_root_only?",
                    confirm_fn=confirm_fn,
                )
                or dirty
            )

        elif choice == "5":
            dirty = (
                _toggle_config_value(
                    cfg,
                    "fast_cache_validation",
                    confirm_message="Toggle fast_cache_validation?",
                    confirm_fn=confirm_fn,
                )
                or dirty
            )

        elif choice == "6":
            dirty = (
                _update_config_value(
                    cfg,
                    "program_dir",
                    prompt_message="New program_dir",
                    confirm_message="Change program_dir?",
                    prompt_fn=prompt_fn,
                    confirm_fn=confirm_fn,
                )
                or dirty
            )

        elif choice == "7":
            dirty = (
                _update_config_value(
                    cfg,
                    "ABB_lib_dir",
                    prompt_message="New ABB_lib_dir",
                    confirm_message="Change ABB_lib_dir?",
                    prompt_fn=prompt_fn,
                    confirm_fn=confirm_fn,
                )
                or dirty
            )

        elif choice == "8":
            dirty = (
                _edit_other_lib_dirs(
                    cfg,
                    prompt_fn=prompt_fn,
                    confirm_fn=confirm_fn,
                )
                or dirty
            )
        elif choice == "9":
            dirty = _save_configuration(
                cfg,
                dirty=dirty,
                config_path=config_path,
                save_config_fn=save_config_fn,
                confirm_fn=confirm_fn,
            )
        elif choice == "10":
            dirty = (
                _update_config_value(
                    cfg,
                    "icf_dir",
                    prompt_message="New ICF_dir",
                    confirm_message="Change ICF_dir?",
                    prompt_fn=prompt_fn,
                    confirm_fn=confirm_fn,
                )
                or dirty
            )
        elif choice == "11":
            dirty = (
                _toggle_config_value(
                    cfg,
                    "debug",
                    confirm_message="Toggle debug?",
                    confirm_fn=confirm_fn,
                    on_change_fn=apply_debug_fn,
                )
                or dirty
            )
        elif choice == "12":
            graphics_rules_menu_fn(cfg)
        else:
            emit_output("Invalid choice.", flush=True)
            pause_fn()


def tools_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    self_check_fn: Callable[[ConfigDict], bool],
    pause_fn: Callable[[], None],
    require_targets_for_menu_action_fn: Callable[[ConfigDict, str], bool],
    dump_menu_fn: Callable[[ConfigDict], None],
    confirm_fn: Callable[[str], bool],
    force_refresh_ast_fn: Callable[[ConfigDict], Any],
) -> None:
    while True:
        clear_screen_fn()
        print_menu_fn(
            "Tools",
            [
                menu_option_factory("1", "Self-check diagnostics", "Verify configuration and path setup"),
                menu_option_factory("2", "Diagnostics & dumps", "Inspect parser, AST, and dependency output"),
                menu_option_factory("3", "Refresh cached ASTs", "Rebuild cached ASTs when results look stale"),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro=(
                "These tools are mainly for setup validation and troubleshooting. "
                "Most users only need them when paths change or results look stale."
            ),
        )

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        if choice == "1":
            clear_screen_fn()
            self_check_fn(cfg)
            pause_fn()
        elif choice == "2":
            if require_targets_for_menu_action_fn(cfg, "using diagnostics and dumps"):
                dump_menu_fn(cfg)
        elif choice == "3":
            if require_targets_for_menu_action_fn(cfg, "refreshing cached ASTs") and confirm_fn(
                "Force refresh cached AST?"
            ):
                force_refresh_ast_fn(cfg)
                pause_fn()
        else:
            emit_output("Invalid choice.")
            pause_fn()


def run_main_loop(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    summarize_targets_fn: Callable[[ConfigDict], str],
    require_targets_for_menu_action_fn: Callable[[ConfigDict, str], bool],
    analysis_menu_fn: Callable[[ConfigDict], None],
    documentation_menu_fn: Callable[[ConfigDict], bool],
    config_menu_fn: Callable[[ConfigDict], bool],
    tools_menu_fn: Callable[[ConfigDict], None],
    show_help_fn: Callable[[ConfigDict], None],
    confirm_fn: Callable[[str], bool],
    save_config_fn: Callable[[Path, ConfigDict], None],
    config_path: Path,
    quit_app_fn: Callable[[], None],
) -> None:
    dirty = False
    while True:
        clear_screen_fn()
        print_menu_fn(
            "SattLint",
            [
                menu_option_factory("1", "Analyze", "Run checks and reports for configured targets"),
                menu_option_factory("2", "Documentation", "Preview unit scope and generate DOCX output"),
                menu_option_factory("3", "Setup", "Configure directories, targets, mode, and cache settings"),
                menu_option_factory("4", "Tools", "Diagnostics, dumps, and cache refresh"),
                menu_option_factory("5", "Help", "First-time guidance and workflow explanations"),
                menu_option_factory("q", "Quit", ""),
            ],
            intro=(
                "Analyze SattLine targets, generate documentation, and troubleshoot parser state from one place. "
                "Start with Setup on first run."
            ),
            note=(summarize_targets_fn(cfg) + "\nChanges are not saved until you choose Save configuration in Setup."),
        )
        choice = input("> ").strip().lower()

        if choice == "1":
            if require_targets_for_menu_action_fn(cfg, "running analyses"):
                analysis_menu_fn(cfg)

        elif choice == "2":
            if require_targets_for_menu_action_fn(cfg, "using documentation tools"):
                dirty |= documentation_menu_fn(cfg)

        elif choice == "3":
            dirty |= config_menu_fn(cfg)

        elif choice == "4":
            tools_menu_fn(cfg)

        elif choice == "5":
            show_help_fn(cfg)

        elif choice == "q":
            if dirty and confirm_fn("Unsaved config changes. Save before quitting?"):
                try:
                    save_config_fn(config_path, cfg)
                except OSError as exc:
                    emit_output(f"Failed to save config to {config_path}: {exc}")
                    continue
            quit_app_fn()

        else:
            emit_output("Invalid choice.", flush=True)
