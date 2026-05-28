from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ._app_analysis_variable_analyses import (
    HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS,
    LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS,
    VARIABLE_ANALYSES,
)
from .analyzers.variables import IssueKind

ConfigDict = dict[str, Any]


def _run_analysis_menu_action(
    action_fn: Callable[[], None],
    *,
    pause_fn: Callable[[], None],
    emit_output_fn: Callable[..., None],
) -> None:
    try:
        action_fn()
    except KeyboardInterrupt:
        emit_output_fn("\nOperation canceled. Returning to the menu.")
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
    emit_output_fn: Callable[..., None],
) -> None:
    while True:
        clear_screen_fn()
        emit_output_fn("\n--- Variable issues ---")
        emit_output_fn("Run focused variable reports or open the investigation tools for deeper tracing.")
        emit_output_fn()
        emit_output_fn("High confidence:")
        emit_output_fn("1) All variable analyses (high confidence)")
        for key in HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS:
            name, _ = VARIABLE_ANALYSES[key]
            emit_output_fn(f"{key}) {name}")
        emit_output_fn("\nLow confidence:")
        for key in LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS:
            name, _ = VARIABLE_ANALYSES[key]
            emit_output_fn(f"{key}) {name}")
        emit_output_fn("\nInvestigation tools:")
        emit_output_fn("23) Datatype usage analysis           Trace field-level usage for one variable name")
        emit_output_fn("24) Variable usage trace              Show fields and locations for one variable name")
        emit_output_fn("25) Module local variable analysis    Inspect field usage inside one module path")
        emit_output_fn("b) Back")
        emit_output_fn("q) Quit")

        choice = input("> ").strip().lower()
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()
        if choice == "23":
            _run_analysis_menu_action(
                lambda: run_datatype_usage_analysis_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "24":
            _run_analysis_menu_action(
                lambda: run_debug_variable_usage_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "25":
            _run_analysis_menu_action(
                lambda: run_module_localvar_analysis_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice in VARIABLE_ANALYSES:
            _name, kinds = VARIABLE_ANALYSES[choice]
            _run_analysis_menu_action(
                lambda kinds=kinds: run_variable_analysis_fn(cfg, kinds),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        else:
            emit_output_fn("Invalid choice.")
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
    emit_output_fn: Callable[..., None],
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
            _run_analysis_menu_action(
                lambda: run_module_duplicates_analysis_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "2":
            _run_analysis_menu_action(
                lambda: run_module_find_by_name_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "3":
            _run_analysis_menu_action(
                lambda: run_module_tree_debug_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "4":
            _run_analysis_menu_action(
                lambda: run_graphics_rules_validation_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        else:
            emit_output_fn("Invalid choice.")
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
    emit_output_fn: Callable[..., None],
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
            _run_analysis_menu_action(
                lambda: run_mms_interface_analysis_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "2":
            _run_analysis_menu_action(
                lambda: run_icf_validation_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "3":
            _run_analysis_menu_action(
                lambda: run_icf_formatter_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        else:
            emit_output_fn("Invalid choice.")
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
    emit_output_fn: Callable[..., None],
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
            _run_analysis_menu_action(
                lambda: run_comment_code_analysis_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        else:
            emit_output_fn("Invalid choice.")
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
    emit_output_fn: Callable[..., None],
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
            _run_analysis_menu_action(
                lambda: run_checks_fn(cfg, None),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice.isdigit():
            index = int(choice) - 2
            if 0 <= index < len(analyzers):
                _run_analysis_menu_action(
                    lambda analyzers=analyzers, index=index: run_checks_fn(cfg, [analyzers[index].key]),
                    pause_fn=pause_fn,
                    emit_output_fn=emit_output_fn,
                )
            else:
                emit_output_fn("Invalid choice.")
                pause_fn()
        else:
            emit_output_fn("Invalid choice.")
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
    emit_output_fn: Callable[..., None],
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
            _run_analysis_menu_action(
                lambda: run_datatype_usage_analysis_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "2":
            _run_analysis_menu_action(
                lambda: run_debug_variable_usage_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "3":
            _run_analysis_menu_action(
                lambda: run_module_localvar_analysis_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        else:
            emit_output_fn("Invalid choice.")
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
    emit_output_fn: Callable[..., None],
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
            _run_analysis_menu_action(
                lambda: run_checks_fn(cfg, None),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "2":
            _run_analysis_menu_action(
                lambda: variable_usage_submenu_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "3":
            _run_analysis_menu_action(
                lambda: module_analysis_submenu_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "4":
            _run_analysis_menu_action(
                lambda: interface_communication_submenu_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "5":
            _run_analysis_menu_action(
                lambda: code_quality_submenu_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "6":
            _run_analysis_menu_action(
                lambda: analyzer_catalog_menu_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        elif choice == "7":
            _run_analysis_menu_action(
                lambda: advanced_analysis_menu_fn(cfg),
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
            )
        else:
            emit_output_fn("Invalid choice.")
            pause_fn()


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
