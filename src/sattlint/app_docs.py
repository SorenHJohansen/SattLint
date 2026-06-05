from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, TypedDict, cast

from sattline_parser.models.ast_model import BasePicture

from . import config as config_module
from . import console as console_module
from .app_interaction import MenuInteraction, build_menu_interaction
from .docgenerator import classification as documentation_classification_module
from .docgenerator import generate_docx
from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
DocumentationSelection = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]


class _DocumentationScopeState(TypedDict):
    mode: str
    instance_paths: list[str]
    moduletype_names: list[str]


_DOCUMENTATION_SCOPE_STATE: _DocumentationScopeState = {
    "mode": "all",
    "instance_paths": [],
    "moduletype_names": [],
}
_documentation_classification_module = cast(Any, documentation_classification_module)

classify_documentation_structure = cast(
    Callable[..., Any], _documentation_classification_module.classify_documentation_structure
)
discover_documentation_unit_candidates = cast(
    Callable[[Any], list[Any]], _documentation_classification_module.discover_documentation_unit_candidates
)
document_scope_summary = cast(
    Callable[[Any, Any], dict[str, Any]], _documentation_classification_module.document_scope_summary
)
emit_output = console_module.print_output  # type: ignore[assignment]


def get_documentation_unit_selection() -> DocumentationSelection:
    return {
        "mode": _DOCUMENTATION_SCOPE_STATE["mode"],
        "instance_paths": list(_DOCUMENTATION_SCOPE_STATE["instance_paths"]),
        "moduletype_names": list(_DOCUMENTATION_SCOPE_STATE["moduletype_names"]),
    }


def set_documentation_unit_selection(
    *,
    mode: str,
    instance_paths: list[str] | None = None,
    moduletype_names: list[str] | None = None,
) -> None:
    _DOCUMENTATION_SCOPE_STATE["mode"] = mode
    _DOCUMENTATION_SCOPE_STATE["instance_paths"] = list(instance_paths or [])
    _DOCUMENTATION_SCOPE_STATE["moduletype_names"] = list(moduletype_names or [])


def documentation_config_without_scope(cfg: ConfigDict) -> dict[str, Any]:
    documentation_cfg = config_module.get_documentation_config(cfg)
    documentation_cfg["units"] = {
        "mode": "all",
        "instance_paths": [],
        "moduletype_names": [],
    }
    return documentation_cfg


def preview_documentation_candidates_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
    cfg: ConfigDict,
) -> None:
    unavailable_libraries = cast(set[str], getattr(graph, "unavailable_libraries", cast(set[str], set())))
    classification = classify_documentation_structure(
        project_bp,
        documentation_config=documentation_config_without_scope(cfg),
        unavailable_libraries=unavailable_libraries,
    )
    candidates = discover_documentation_unit_candidates(classification)
    emit_output(f"\n=== Target: {target_name} ===")
    if not candidates:
        emit_output("⚠ No unit candidates detected.")
        return

    for index, entry in enumerate(candidates, 1):
        summary = document_scope_summary(entry, classification)
        emit_output(
            f"  {index}. {entry.short_path} | type={entry.moduletype_label or entry.kind} | "
            f"ops={summary['ops']} em={summary['em']} "
            f"rp={summary['rp']} ep={summary['ep']} up={summary['up']}"
        )


def preview_documentation_unit_candidates(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    pause_fn: Callable[[], None],
) -> None:
    emit_output("\n--- Documentation Unit Candidates ---")
    with console_module.live_status_line() as status_update_fn:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            status_update_fn(f"Documentation candidates: scanning {target_name}")
            preview_documentation_candidates_for_target(target_name, project_bp, graph, cfg)
    pause_fn()


def configure_documentation_scope_by_moduletype(
    *,
    split_csv_values_fn: Callable[[str], list[str]],
    pause_fn: Callable[[], None] | None = None,
    prompt_fn: Callable[[str, str | None], str] | None = None,
    interaction: MenuInteraction | None = None,
) -> bool:
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=lambda *_args, **_kwargs: None,
        prompt_fn=prompt_fn,
        pause_fn=pause_fn,
    )
    emit_output("\n--- Documentation Scope by Unit ModuleType ---")
    emit_output("Enter one or more unit moduletype names (comma-separated).")
    emit_output("Example: ApplTank, XDilute_221X251XY")
    raw = menu_interaction.prompt(">", None)
    values = split_csv_values_fn(raw)
    if not values:
        emit_output("❌ No moduletype names provided")
        menu_interaction.pause()
        return False
    set_documentation_unit_selection(
        mode="moduletype_names",
        moduletype_names=values,
    )
    emit_output("✔ Documentation scope updated")
    menu_interaction.pause()
    return True


def configure_documentation_scope_by_instance_path(
    *,
    split_csv_values_fn: Callable[[str], list[str]],
    pause_fn: Callable[[], None] | None = None,
    prompt_fn: Callable[[str, str | None], str] | None = None,
    interaction: MenuInteraction | None = None,
) -> bool:
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=lambda *_args, **_kwargs: None,
        prompt_fn=prompt_fn,
        pause_fn=pause_fn,
    )
    emit_output("\n--- Documentation Scope by Unit Instance Path ---")
    emit_output("Enter one or more unit instance paths (comma-separated).")
    emit_output("Use the candidate preview to find valid paths.")
    raw = menu_interaction.prompt(">", None)
    values = split_csv_values_fn(raw)
    if not values:
        emit_output("❌ No instance paths provided")
        menu_interaction.pause()
        return False
    set_documentation_unit_selection(
        mode="instance_paths",
        instance_paths=values,
    )
    emit_output("✔ Documentation scope updated")
    menu_interaction.pause()
    return True


def reset_documentation_scope(
    *, pause_fn: Callable[[], None] | None = None, interaction: MenuInteraction | None = None
) -> bool:
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=lambda *_args, **_kwargs: None,
        pause_fn=pause_fn,
    )
    set_documentation_unit_selection(mode="all")
    emit_output("✔ Documentation scope reset to all units")
    menu_interaction.pause()
    return True


def run_generate_documentation(
    cfg: ConfigDict,
    *,
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    prompt_fn: Callable[[str, str | None], str] | None = None,
    pause_fn: Callable[[], None] | None = None,
    interaction: MenuInteraction | None = None,
) -> None:
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=lambda *_args, **_kwargs: None,
        prompt_fn=prompt_fn,
        pause_fn=pause_fn,
    )
    emit_output("\n--- Generate Documentation ---")
    documentation_cfg = config_module.get_documentation_config(cfg)
    documentation_cfg["units"] = get_documentation_unit_selection()

    with console_module.live_status_line() as status_update_fn:
        for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
            unavailable_libraries = cast(set[str], getattr(graph, "unavailable_libraries", cast(set[str], set())))
            status_update_fn(f"Documentation: classifying {target_name}")
            classification = classify_documentation_structure(
                project_bp,
                documentation_config=documentation_cfg,
                unavailable_libraries=unavailable_libraries,
            )
            scope = classification.scope
            if scope and scope.mode != "all" and not (scope.roots or []):
                emit_output(f"\n=== Target: {target_name} ===")
                emit_output("⚠ No unit roots matched the configured documentation scope; skipping target.")
                if scope.unmatched_values:
                    emit_output("Unmatched scope filters: " + ", ".join(scope.unmatched_values))
                continue

            default_name = f"{target_name}_FS.docx"
            out_name = menu_interaction.prompt(f"Output DOCX for {target_name}", default_name)
            if scope and scope.roots:
                emit_output(
                    f"Selected units for {target_name}: " + ", ".join(entry.short_path for entry in scope.roots)
                )
            status_update_fn(f"Documentation: generating {target_name}")
            generate_docx(
                project_bp,
                out_name,
                documentation_config=documentation_cfg,
                unavailable_libraries=unavailable_libraries,
            )

    menu_interaction.pause()


def documentation_menu(
    cfg: ConfigDict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    pause_fn: Callable[[], None] | None,
    split_csv_values_fn: Callable[[str], list[str]],
    iter_loaded_projects_fn: Callable[[ConfigDict], Iterator[LoadedProject]],
    prompt_fn: Callable[[str, str | None], str] | None,
    choose_menu_option_fn: Callable[..., str] | None = None,
    interaction: MenuInteraction | None = None,
) -> bool:
    menu_interaction = interaction or build_menu_interaction(
        print_menu_fn=print_menu_fn,
        choose_menu_option_fn=choose_menu_option_fn,
        prompt_fn=prompt_fn,
        pause_fn=pause_fn,
    )
    dirty = False

    def _run_documentation_action(action_fn: Callable[[], Any], *, default: bool = False) -> bool:
        try:
            return cast(bool, action_fn())
        except KeyboardInterrupt:
            emit_output("\nOperation canceled. Returning to the menu.")
            menu_interaction.pause()
            return default

    while True:
        clear_screen_fn()
        selection = get_documentation_unit_selection()
        current_scope = (
            "all units"
            if selection["mode"] == "all"
            else f"{selection['mode']} -> " + ", ".join(selection["instance_paths"] or selection["moduletype_names"])
        )
        c = menu_interaction.choose_menu_option(
            "Documentation",
            [
                menu_option_factory("1", "Generate documentation", "Create DOCX output for each configured target"),
                menu_option_factory(
                    "2", "Preview unit candidates", "List the detected unit roots before choosing scope"
                ),
                menu_option_factory("3", "Use all detected units", "Reset scoping and include every detected unit"),
                menu_option_factory("4", "Scope by moduletype", "Filter units by moduletype name"),
                menu_option_factory("5", "Scope by instance path", "Filter units by instance path"),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro=(
                "Generate FS-style DOCX documentation for the configured targets. "
                "Preview candidates first if you want to scope the output to specific units."
            ),
            note="Current scope: " + current_scope,
        )
        if c == "b":
            return dirty
        if c == "q":
            quit_app_fn()

        if c == "1":
            _run_documentation_action(
                lambda: run_generate_documentation(
                    cfg,
                    iter_loaded_projects_fn=iter_loaded_projects_fn,
                    interaction=menu_interaction,
                )
            )
        elif c == "2":
            _run_documentation_action(
                lambda: preview_documentation_unit_candidates(
                    cfg,
                    iter_loaded_projects_fn=iter_loaded_projects_fn,
                    pause_fn=menu_interaction.pause,
                )
            )
        elif c == "3":
            dirty |= _run_documentation_action(
                lambda: reset_documentation_scope(interaction=menu_interaction),
                default=False,
            )
        elif c == "4":
            dirty |= _run_documentation_action(
                lambda: configure_documentation_scope_by_moduletype(
                    split_csv_values_fn=split_csv_values_fn,
                    interaction=menu_interaction,
                ),
                default=False,
            )
        elif c == "5":
            dirty |= _run_documentation_action(
                lambda: configure_documentation_scope_by_instance_path(
                    split_csv_values_fn=split_csv_values_fn,
                    interaction=menu_interaction,
                ),
                default=False,
            )
        else:
            emit_output("Invalid choice.")
            menu_interaction.pause()
