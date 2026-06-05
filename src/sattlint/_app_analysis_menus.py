from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from . import _app_analysis_catalog as analysis_catalog
from .analyzers.variables import IssueKind
from .app_interaction import MenuInteraction, build_menu_interaction

ConfigDict = dict[str, Any]


def _default_menu_option_factory(key: str, label: str, description: str) -> Any:
    return SimpleNamespace(key=key, label=label, description=description)


def _catalog_entries_by_menu_key(
    entries: tuple[analysis_catalog.AnalysisCatalogEntry, ...],
) -> dict[str, analysis_catalog.AnalysisCatalogEntry]:
    return {str(entry.classic_menu_key): entry for entry in entries if entry.classic_menu_key is not None}


def _catalog_menu_options(
    entries: tuple[analysis_catalog.AnalysisCatalogEntry, ...],
    *,
    menu_option_factory: Callable[[str, str, str], Any],
    include_back_quit: bool = True,
) -> list[Any]:
    options = [
        menu_option_factory(str(entry.classic_menu_key), entry.label, entry.description)
        for entry in entries
        if entry.classic_menu_key is not None
    ]
    if include_back_quit:
        options.extend([menu_option_factory("b", "Back", ""), menu_option_factory("q", "Quit", "")])
    return options


def _run_catalog_entry(
    entry: analysis_catalog.AnalysisCatalogEntry,
    *,
    cfg: ConfigDict,
    pause_fn: Callable[[], None],
    emit_output_fn: Callable[..., None],
    run_checks_fn: Callable[[ConfigDict, list[str] | None], None] | None = None,
    run_variable_analysis_fn: Callable[[ConfigDict, set[IssueKind] | None], None] | None = None,
    handler_fns: dict[str, Callable[[ConfigDict], None]] | None = None,
) -> None:
    execution = entry.execution
    if execution.kind == "run_variable_analysis":
        if run_variable_analysis_fn is None:
            emit_output_fn(f"{entry.label} is unavailable in the current menu.")
            pause_fn()
            return
        issue_kinds = None if execution.variable_issue_kinds is None else set(execution.variable_issue_kinds)
        _run_analysis_menu_action(
            lambda: run_variable_analysis_fn(cfg, issue_kinds),
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
        )
        return

    if execution.kind == "run_checks":
        if run_checks_fn is None:
            emit_output_fn(f"{entry.label} is unavailable in the current menu.")
            pause_fn()
            return
        selected_keys = None if execution.selected_analyzer_keys is None else list(execution.selected_analyzer_keys)
        _run_analysis_menu_action(
            lambda: run_checks_fn(cfg, selected_keys),
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
        )
        return

    if handler_fns is None:
        emit_output_fn(f"{entry.label} is unavailable in the current menu.")
        pause_fn()
        return

    handler_fn = handler_fns.get(execution.handler_name)
    if handler_fn is None:
        emit_output_fn(f"{entry.label} is unavailable in the current menu.")
        pause_fn()
        return
    _run_analysis_menu_action(
        lambda: handler_fn(cfg),
        pause_fn=pause_fn,
        emit_output_fn=emit_output_fn,
    )


def _build_variable_usage_options() -> list[Any]:
    entries = analysis_catalog.analysis_entries_for_family(analysis_catalog.FAMILY_VARIABLE_ISSUES)
    options = [
        _default_menu_option_factory(str(entry.classic_menu_key), entry.label, entry.description)
        for entry in entries
        if entry.classic_menu_key is not None
    ]
    options.extend(
        [
            _default_menu_option_factory("b", "Back", "Return to Analyze"),
            _default_menu_option_factory("q", "Quit", "Exit SattLint"),
        ]
    )
    return options


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


def _build_variable_usage_menu_interaction(
    *,
    emit_output_fn: Callable[..., None],
    pause_fn: Callable[[], None],
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> MenuInteraction:
    if interaction is not None:
        return interaction

    if choose_menu_option_fn is None:

        def _default_choose_menu_option(
            _title: str,
            _options: list[Any],
            *,
            intro: str | None = None,
            note: str | None = None,
        ) -> str:
            entries = analysis_catalog.analysis_entries_for_family(analysis_catalog.FAMILY_VARIABLE_ISSUES)
            options = _build_variable_usage_options()
            suite_entries = [
                entry
                for entry in entries
                if entry.section_id
                in {analysis_catalog.SECTION_VARIABLE_SUITE, analysis_catalog.SECTION_VARIABLE_HIGH_CONFIDENCE}
            ]
            low_entries = [
                entry for entry in entries if entry.section_id == analysis_catalog.SECTION_VARIABLE_LOW_CONFIDENCE
            ]
            investigation_entries = [
                entry for entry in entries if entry.section_id == analysis_catalog.SECTION_INVESTIGATION
            ]
            if intro:
                emit_output_fn(intro)
            emit_output_fn()
            emit_output_fn("High confidence:")
            for entry in suite_entries:
                emit_output_fn(f"{entry.classic_menu_key}) {entry.label}")
            emit_output_fn("\nLow confidence:")
            for entry in low_entries:
                emit_output_fn(f"{entry.classic_menu_key}) {entry.label}")
            emit_output_fn("\nInvestigation tools:")
            for entry in investigation_entries:
                line = f"{entry.classic_menu_key}) {entry.label}"
                description = entry.description
                if description:
                    line = f"{line:<40} {description}"
                emit_output_fn(line)
            for option in options:
                key = str(getattr(option, "key", ""))
                if key not in {"b", "q"}:
                    continue
                line = f"{key}) {getattr(option, 'label', '')}"
                description = str(getattr(option, "description", "") or "")
                if description:
                    line = f"{line:<40} {description}"
                emit_output_fn(line)
            if note:
                emit_output_fn()
                emit_output_fn(note)
            return input("> ").strip().lower()

        choose_menu_option_fn = _default_choose_menu_option

    return build_menu_interaction(
        print_menu_fn=lambda *_args, **_kwargs: None,
        choose_menu_option_fn=choose_menu_option_fn,
        pause_fn=pause_fn,
    )


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
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    entries = analysis_catalog.analysis_entries_for_family(analysis_catalog.FAMILY_VARIABLE_ISSUES)
    entries_by_key = _catalog_entries_by_menu_key(entries)
    menu_interaction = _build_variable_usage_menu_interaction(
        emit_output_fn=emit_output_fn,
        pause_fn=pause_fn,
        choose_menu_option_fn=choose_menu_option_fn,
        interaction=interaction,
    )
    while True:
        clear_screen_fn()
        emit_output_fn("\n--- Variable issues ---")
        choice = menu_interaction.choose_menu_option(
            "Variable issues",
            _build_variable_usage_options(),
            intro="Run focused variable reports or open the investigation tools for deeper tracing.",
        )
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()
        entry = entries_by_key.get(choice)
        if entry is None:
            emit_output_fn("Invalid choice.")
            menu_interaction.pause()
            continue
        _run_catalog_entry(
            entry,
            cfg=cfg,
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
            run_variable_analysis_fn=run_variable_analysis_fn,
            handler_fns={
                "run_datatype_usage_analysis": run_datatype_usage_analysis_fn,
                "run_debug_variable_usage": run_debug_variable_usage_fn,
                "run_module_localvar_analysis": run_module_localvar_analysis_fn,
            },
        )


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
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    entries = analysis_catalog.analysis_entries_for_family(analysis_catalog.FAMILY_STRUCTURE_MODULES)
    entries_by_key = _catalog_entries_by_menu_key(entries)
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=print_menu_fn,
        choose_menu_option_fn=choose_menu_option_fn,
        pause_fn=pause_fn,
    )
    while True:
        clear_screen_fn()
        choice = menu_interaction.choose_menu_option(
            "Structure & modules",
            _catalog_menu_options(entries, menu_option_factory=menu_option_factory),
            intro="Use these tools when you need to inspect module layout, duplication, or structural drift.",
        )
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        entry = entries_by_key.get(choice)
        if entry is None:
            emit_output_fn("Invalid choice.")
            menu_interaction.pause()
            continue
        _run_catalog_entry(
            entry,
            cfg=cfg,
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
            handler_fns={
                "run_module_duplicates_analysis": run_module_duplicates_analysis_fn,
                "run_module_find_by_name": run_module_find_by_name_fn,
                "run_module_tree_debug": run_module_tree_debug_fn,
                "run_graphics_rules_validation": run_graphics_rules_validation_fn,
            },
        )


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
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    entries = analysis_catalog.analysis_entries_for_family(analysis_catalog.FAMILY_INTERFACES)
    entries_by_key = _catalog_entries_by_menu_key(entries)
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=print_menu_fn,
        choose_menu_option_fn=choose_menu_option_fn,
        pause_fn=pause_fn,
    )
    while True:
        clear_screen_fn()
        choice = menu_interaction.choose_menu_option(
            "Interfaces & communication",
            _catalog_menu_options(entries, menu_option_factory=menu_option_factory),
            intro="Check external interfaces and communication-related wiring for the current targets.",
        )
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        entry = entries_by_key.get(choice)
        if entry is None:
            emit_output_fn("Invalid choice.")
            menu_interaction.pause()
            continue
        _run_catalog_entry(
            entry,
            cfg=cfg,
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
            handler_fns={
                "run_mms_interface_analysis": run_mms_interface_analysis_fn,
                "run_icf_validation": run_icf_validation_fn,
                "run_icf_formatter": run_icf_formatter_fn,
            },
        )


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
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    entries = analysis_catalog.analysis_entries_for_family(analysis_catalog.FAMILY_CODE_QUALITY)
    entries_by_key = _catalog_entries_by_menu_key(entries)
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=print_menu_fn,
        choose_menu_option_fn=choose_menu_option_fn,
        pause_fn=pause_fn,
    )
    while True:
        clear_screen_fn()
        choice = menu_interaction.choose_menu_option(
            "Code quality",
            _catalog_menu_options(entries, menu_option_factory=menu_option_factory),
            intro="Use these checks for readability and maintainability issues rather than runtime semantics.",
        )
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        entry = entries_by_key.get(choice)
        if entry is None:
            emit_output_fn("Invalid choice.")
            menu_interaction.pause()
            continue
        _run_catalog_entry(
            entry,
            cfg=cfg,
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
            handler_fns={"run_comment_code_analysis": run_comment_code_analysis_fn},
        )


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
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=print_menu_fn,
        choose_menu_option_fn=choose_menu_option_fn,
        pause_fn=pause_fn,
    )
    while True:
        clear_screen_fn()
        analyzers = get_enabled_analyzers_fn()
        entries = analysis_catalog.analysis_entries_for_family(
            analysis_catalog.FAMILY_ANALYZER_CATALOG,
            analyzer_specs=analyzers,
        )
        entries_by_key = _catalog_entries_by_menu_key(entries)
        choice = menu_interaction.choose_menu_option(
            "Analyzer catalog",
            _catalog_menu_options(entries, menu_option_factory=menu_option_factory),
            intro=(
                "This view exposes the registry-backed analyzers directly. "
                "Only the default analyzer set is exposed here so low-confidence analyzers "
                "never run from the CLI suite."
            ),
        )
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        entry = entries_by_key.get(choice)
        if entry is None:
            emit_output_fn("Invalid choice.")
            menu_interaction.pause()
            continue
        _run_catalog_entry(
            entry,
            cfg=cfg,
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
            run_checks_fn=run_checks_fn,
        )


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
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    entries = analysis_catalog.analysis_entries_for_family(analysis_catalog.FAMILY_INVESTIGATION)
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=print_menu_fn,
        choose_menu_option_fn=choose_menu_option_fn,
        pause_fn=pause_fn,
    )
    while True:
        clear_screen_fn()
        choice = menu_interaction.choose_menu_option(
            "Advanced analysis & debug",
            [
                menu_option_factory(str(index), entry.label, entry.description)
                for index, entry in enumerate(entries, start=1)
            ]
            + [menu_option_factory("b", "Back", ""), menu_option_factory("q", "Quit", "")],
            intro="Use these tools when the summary reports are not specific enough and you need targeted tracing.",
        )
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        entry: analysis_catalog.AnalysisCatalogEntry | None = None
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(entries):
                entry = entries[index]
        if entry is None:
            emit_output_fn("Invalid choice.")
            menu_interaction.pause()
            continue
        _run_catalog_entry(
            entry,
            cfg=cfg,
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
            handler_fns={
                "run_datatype_usage_analysis": run_datatype_usage_analysis_fn,
                "run_debug_variable_usage": run_debug_variable_usage_fn,
                "run_module_localvar_analysis": run_module_localvar_analysis_fn,
            },
        )


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
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    family_by_key = {family.classic_menu_key: family for family in analysis_catalog.TOP_LEVEL_ANALYSIS_FAMILIES}
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=print_menu_fn,
        choose_menu_option_fn=choose_menu_option_fn,
        pause_fn=pause_fn,
    )
    while True:
        clear_screen_fn()
        choice = menu_interaction.choose_menu_option(
            "Analyze",
            [
                menu_option_factory(family.classic_menu_key, family.label, family.description)
                for family in analysis_catalog.TOP_LEVEL_ANALYSIS_FAMILIES
            ]
            + [menu_option_factory("b", "Back", ""), menu_option_factory("q", "Quit", "")],
            intro=(
                "Run checks against the configured programs or libraries. "
                "Use the full analyzer suite for a broad pass, then drill into the focused menus if you need detail."
            ),
            note=summarize_targets_fn(cfg),
        )
        if choice == "b":
            return
        if choice == "q":
            quit_app_fn()

        family = family_by_key.get(choice)
        if family is None:
            emit_output_fn("Invalid choice.")
            menu_interaction.pause()
            continue

        if family.entry_id is not None:
            entry = analysis_catalog.analysis_catalog_entry(family.entry_id)
            if entry is None:
                emit_output_fn("Invalid choice.")
                menu_interaction.pause()
                continue
            _run_catalog_entry(
                entry,
                cfg=cfg,
                pause_fn=pause_fn,
                emit_output_fn=emit_output_fn,
                run_checks_fn=run_checks_fn,
            )
            continue

        submenu_map: dict[str, Callable[[ConfigDict], None]] = {
            analysis_catalog.FAMILY_VARIABLE_ISSUES: variable_usage_submenu_fn,
            analysis_catalog.FAMILY_STRUCTURE_MODULES: module_analysis_submenu_fn,
            analysis_catalog.FAMILY_INTERFACES: interface_communication_submenu_fn,
            analysis_catalog.FAMILY_CODE_QUALITY: code_quality_submenu_fn,
            analysis_catalog.FAMILY_ANALYZER_CATALOG: analyzer_catalog_menu_fn,
            analysis_catalog.FAMILY_INVESTIGATION: advanced_analysis_menu_fn,
        }
        submenu_fn = submenu_map.get(family.family_id)
        if submenu_fn is None:
            emit_output_fn("Invalid choice.")
            menu_interaction.pause()
            continue
        resolved_submenu_fn = submenu_fn
        _run_analysis_menu_action(
            lambda resolved_submenu_fn=resolved_submenu_fn: resolved_submenu_fn(cfg),
            pause_fn=pause_fn,
            emit_output_fn=emit_output_fn,
        )


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
