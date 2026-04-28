from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from . import config as config_module
from . import console as console_module
from .docgenerator import generate_docx
from .docgenerator.classification import (
    classify_documentation_structure,
    discover_documentation_unit_candidates,
    document_scope_summary,
)
from sattline_parser.models.ast_model import BasePicture
from .models.project_graph import ProjectGraph

_DOCUMENTATION_SCOPE_STATE = {
    "mode": "all",
    "instance_paths": [],
    "moduletype_names": [],
}
print = console_module.print_output  # type: ignore[assignment]


def get_documentation_unit_selection() -> dict:
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


def documentation_config_without_scope(cfg: dict) -> dict:
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
    cfg: dict,
) -> None:
    classification = classify_documentation_structure(
        project_bp,
        documentation_config=documentation_config_without_scope(cfg),
        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
    )
    candidates = discover_documentation_unit_candidates(classification)
    print(f"\n=== Target: {target_name} ===")
    if not candidates:
        print("⚠ No unit candidates detected.")
        return

    for index, entry in enumerate(candidates, 1):
        summary = document_scope_summary(entry, classification)
        print(
            f"  {index}. {entry.short_path} | type={entry.moduletype_label or entry.kind} | "
            f"ops={summary['ops']} em={summary['em']} "
            f"rp={summary['rp']} ep={summary['ep']} up={summary['up']}"
        )


def preview_documentation_unit_candidates(
    cfg: dict,
    *,
    iter_loaded_projects_fn: Callable[[dict], Iterator[tuple[str, BasePicture, ProjectGraph]]],
    pause_fn: Callable[[], None],
) -> None:
    print("\n--- Documentation Unit Candidates ---")
    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        preview_documentation_candidates_for_target(target_name, project_bp, graph, cfg)
    pause_fn()


def configure_documentation_scope_by_moduletype(
    *,
    split_csv_values_fn: Callable[[str], list[str]],
    pause_fn: Callable[[], None],
) -> bool:
    print("\n--- Documentation Scope by Unit ModuleType ---")
    print("Enter one or more unit moduletype names (comma-separated).")
    print("Example: ApplTank, XDilute_221X251XY")
    raw = input("> ").strip()
    values = split_csv_values_fn(raw)
    if not values:
        print("❌ No moduletype names provided")
        pause_fn()
        return False
    set_documentation_unit_selection(
        mode="moduletype_names",
        moduletype_names=values,
    )
    print("✔ Documentation scope updated")
    pause_fn()
    return True


def configure_documentation_scope_by_instance_path(
    *,
    split_csv_values_fn: Callable[[str], list[str]],
    pause_fn: Callable[[], None],
) -> bool:
    print("\n--- Documentation Scope by Unit Instance Path ---")
    print("Enter one or more unit instance paths (comma-separated).")
    print("Use the candidate preview to find valid paths.")
    raw = input("> ").strip()
    values = split_csv_values_fn(raw)
    if not values:
        print("❌ No instance paths provided")
        pause_fn()
        return False
    set_documentation_unit_selection(
        mode="instance_paths",
        instance_paths=values,
    )
    print("✔ Documentation scope updated")
    pause_fn()
    return True


def reset_documentation_scope(*, pause_fn: Callable[[], None]) -> bool:
    set_documentation_unit_selection(mode="all")
    print("✔ Documentation scope reset to all units")
    pause_fn()
    return True


def run_generate_documentation(
    cfg: dict,
    *,
    iter_loaded_projects_fn: Callable[[dict], Iterator[tuple[str, BasePicture, ProjectGraph]]],
    prompt_fn: Callable[[str, str | None], str],
    pause_fn: Callable[[], None],
) -> None:
    print("\n--- Generate Documentation ---")
    documentation_cfg = config_module.get_documentation_config(cfg)
    documentation_cfg["units"] = get_documentation_unit_selection()

    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        classification = classify_documentation_structure(
            project_bp,
            documentation_config=documentation_cfg,
            unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
        )
        scope = classification.scope
        if scope and scope.mode != "all" and not (scope.roots or []):
            print(f"\n=== Target: {target_name} ===")
            print("⚠ No unit roots matched the configured documentation scope; skipping target.")
            if scope.unmatched_values:
                print("Unmatched scope filters: " + ", ".join(scope.unmatched_values))
            continue

        default_name = f"{target_name}_FS.docx"
        out_name = prompt_fn(f"Output DOCX for {target_name}", default_name)
        if scope and scope.roots:
            print(f"Selected units for {target_name}: " + ", ".join(entry.short_path for entry in scope.roots))
        generate_docx(
            project_bp,
            out_name,
            documentation_config=documentation_cfg,
            unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
        )

    pause_fn()


def documentation_menu(
    cfg: dict,
    *,
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    quit_app_fn: Callable[[], None],
    pause_fn: Callable[[], None],
    split_csv_values_fn: Callable[[str], list[str]],
    iter_loaded_projects_fn: Callable[[dict], Iterator[tuple[str, BasePicture, ProjectGraph]]],
    prompt_fn: Callable[[str, str | None], str],
) -> bool:
    dirty = False
    while True:
        clear_screen_fn()
        selection = get_documentation_unit_selection()
        print_menu_fn(
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
        )
        print(
            "\nCurrent scope: "
            + (
                "all units"
                if selection["mode"] == "all"
                else f"{selection['mode']} -> "
                + ", ".join(selection["instance_paths"] or selection["moduletype_names"])
            )
        )
        c = input("> ").strip().lower()
        if c == "b":
            return dirty
        if c == "q":
            quit_app_fn()

        if c == "1":
            run_generate_documentation(
                cfg,
                iter_loaded_projects_fn=iter_loaded_projects_fn,
                prompt_fn=prompt_fn,
                pause_fn=pause_fn,
            )
        elif c == "2":
            preview_documentation_unit_candidates(
                cfg,
                iter_loaded_projects_fn=iter_loaded_projects_fn,
                pause_fn=pause_fn,
            )
        elif c == "3":
            dirty |= reset_documentation_scope(pause_fn=pause_fn)
        elif c == "4":
            dirty |= configure_documentation_scope_by_moduletype(
                split_csv_values_fn=split_csv_values_fn,
                pause_fn=pause_fn,
            )
        elif c == "5":
            dirty |= configure_documentation_scope_by_instance_path(
                split_csv_values_fn=split_csv_values_fn,
                pause_fn=pause_fn,
            )
        else:
            print("Invalid choice.")
            pause_fn()
