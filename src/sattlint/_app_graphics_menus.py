from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from sattline_parser.models.ast_model import BasePicture

from .models.project_graph import ProjectGraph

ConfigDict = dict[str, Any]
GraphicsRule = dict[str, Any]
LoadedProject = tuple[str, BasePicture, ProjectGraph]
LoadedProjectIterator = Callable[[ConfigDict], Sequence[LoadedProject] | Any]
CollectGraphicsLayoutEntriesForTargetFn = Callable[[str, BasePicture, ProjectGraph], list[GraphicsRule]]
ClassifyDocumentationStructureFn = Callable[..., Any]
DiscoverDocumentationUnitCandidatesFn = Callable[[Any], Sequence[Any]]


def prompt_graphics_rule_kind(*, emit_output_fn: Callable[..., None]) -> str:
    emit_output_fn("\nChoose graphics rule target kind:")
    emit_output_fn("  1) Frame")
    emit_output_fn("  2) Single module")
    emit_output_fn("  3) ModuleType")
    while True:
        choice = input("> ").strip().lower()
        if choice == "1":
            return "frame"
        if choice == "2":
            return "single"
        if choice == "3":
            return "moduletype"
        emit_output_fn("? Choose 1, 2, or 3")


def selector_prompt_text(selector_field: str) -> str:
    if selector_field == "relative_module_path":
        return "Relative module path"
    if selector_field == "unit_structure_path":
        return "Unit structure path"
    if selector_field == "equipment_module_structure_path":
        return "Equipment module structure path"
    return "Selector path"


def graphics_rule_target_kind_matches(module_kind: str, entry: dict[str, Any]) -> bool:
    entry_kind = str(entry.get("module_kind") or "").strip().casefold()
    if module_kind == "frame":
        return entry_kind == "frame"
    if module_kind == "single":
        return entry_kind in {"module", "moduletype-instance"}
    if module_kind == "moduletype":
        return entry_kind == "moduletype-instance"
    return False


def discover_graphics_rule_selector_options(
    cfg: ConfigDict | None,
    *,
    selector_field: str,
    module_kind: str,
    has_analyzed_targets_fn: Callable[[ConfigDict], bool],
    iter_loaded_projects_fn: Callable[[ConfigDict], Any],
    collect_graphics_layout_entries_for_target_fn: CollectGraphicsLayoutEntriesForTargetFn,
) -> list[GraphicsRule]:
    if cfg is None or not has_analyzed_targets_fn(cfg):
        return []

    discovered: dict[str, dict[str, Any]] = {}
    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        try:
            entries = collect_graphics_layout_entries_for_target_fn(
                target_name,
                project_bp,
                graph,
            )
        except Exception:
            entries = []

        for entry in entries:
            if not graphics_rule_target_kind_matches(module_kind, entry):
                continue
            selector_value = str(entry.get(selector_field) or "").strip()
            if not selector_value:
                continue
            if not str(entry.get("unit_root_path") or "").strip():
                continue

            key = selector_value.casefold()
            bucket = discovered.setdefault(
                key,
                {
                    "selector_value": selector_value,
                    "count": 0,
                    "targets": set(),
                    "sample_module_path": str(entry.get("module_path") or ""),
                },
            )
            bucket["count"] += 1
            cast(set[str], bucket["targets"]).add(target_name)

    return sorted(
        [
            {
                "selector_value": item["selector_value"],
                "count": item["count"],
                "target_count": len(cast(set[str], item["targets"])),
                "sample_module_path": item["sample_module_path"],
            }
            for item in discovered.values()
        ],
        key=lambda item: (str(item["selector_value"]).casefold(), str(item["sample_module_path"]).casefold()),
    )


def pick_or_prompt_graphics_rule_selector_value(
    selector_field: str,
    module_kind: str,
    *,
    cfg: ConfigDict | None,
    discover_graphics_rule_selector_options_fn: Callable[..., list[GraphicsRule]],
    emit_output_fn: Callable[..., None],
    required_prompt_validation_error: type[Exception],
) -> str:
    options = discover_graphics_rule_selector_options_fn(
        cfg,
        selector_field=selector_field,
        module_kind=module_kind,
    )
    prompt_text = selector_prompt_text(selector_field)

    if options:
        emit_output_fn(f"\nAvailable {prompt_text.lower()} values:")
        for index, option in enumerate(options, start=1):
            emit_output_fn(
                f"  {index}) {option['selector_value']} "
                f"[{option['count']} matches across {option['target_count']} targets]"
            )
        emit_output_fn("  m) Enter manually")

        while True:
            raw = input("> ").strip().lower()
            if raw == "m":
                break
            try:
                selected_index = int(raw) - 1
            except ValueError:
                emit_output_fn("? Choose an index or 'm'")
                continue
            if 0 <= selected_index < len(options):
                return str(options[selected_index]["selector_value"])
            emit_output_fn("? Invalid index")

    selector_value = input(f"{prompt_text}: ").strip()
    if not selector_value:
        emit_output_fn("? Selector path is required")
        raise required_prompt_validation_error("Selector path is required")
    return selector_value


def prompt_graphics_rule_selector(
    module_kind: str,
    *,
    cfg: ConfigDict | None,
    pick_or_prompt_graphics_rule_selector_value_fn: Callable[..., str],
    emit_output_fn: Callable[..., None],
) -> tuple[str, str]:
    if module_kind == "frame":
        selector_field = "relative_module_path"
    elif module_kind == "single":
        emit_output_fn("\nChoose selector scope:")
        emit_output_fn("  1) Relative module path")
        emit_output_fn("  2) Unit structure path")
        emit_output_fn("  3) Equipment module structure path")
        while True:
            choice = input("> ").strip().lower()
            if choice == "1":
                selector_field = "relative_module_path"
                break
            if choice == "2":
                selector_field = "unit_structure_path"
                break
            if choice == "3":
                selector_field = "equipment_module_structure_path"
                break
            emit_output_fn("? Choose 1, 2, or 3")
    else:
        emit_output_fn("\nChoose ModuleType selector scope:")
        emit_output_fn("  1) Relative module path")
        emit_output_fn("  2) Unit structure path")
        emit_output_fn("  3) Equipment module structure path")
        while True:
            choice = input("> ").strip().lower()
            if choice == "1":
                selector_field = "relative_module_path"
                break
            if choice == "2":
                selector_field = "unit_structure_path"
                break
            if choice == "3":
                selector_field = "equipment_module_structure_path"
                break
            emit_output_fn("? Choose 1, 2, or 3")

    selector_value = pick_or_prompt_graphics_rule_selector_value_fn(
        selector_field,
        module_kind,
        cfg=cfg,
    )
    return selector_field, selector_value


def path_startswith_casefold(path: Sequence[str], prefix: Sequence[str]) -> bool:
    if len(prefix) > len(path):
        return False
    return all(part.casefold() == other.casefold() for part, other in zip(path, prefix, strict=False))


def graphics_entry_canonical_segment(entry: dict[str, Any]) -> str:
    moduletype_name = str(
        entry.get("moduletype_name") or entry.get("resolved_moduletype", {}).get("name") or ""
    ).strip()
    if moduletype_name:
        return moduletype_name
    return str(entry.get("module_name") or "").strip()


def looks_like_graphics_unit_root(
    candidate_path: Sequence[str],
    entries: Sequence[dict[str, Any]],
) -> bool:
    for entry in entries:
        module_path = tuple(
            segment.strip() for segment in str(entry.get("module_path") or "").split(".") if segment.strip()
        )
        if not module_path or not path_startswith_casefold(module_path, candidate_path):
            continue
        relative_segments = module_path[len(candidate_path) :]
        if len(relative_segments) < 3:
            continue
        if (
            relative_segments[0].casefold() == "l1"
            and relative_segments[1].casefold() == "l2"
            and relative_segments[2].casefold() == "unitcontrol"
        ):
            return True
    return False


def annotate_graphics_entries_with_structure_paths(
    entries: list[GraphicsRule],
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    classify_documentation_structure_fn: ClassifyDocumentationStructureFn,
    discover_documentation_unit_candidates_fn: DiscoverDocumentationUnitCandidatesFn,
) -> list[GraphicsRule]:
    unavailable_libraries = cast(set[str], getattr(graph, "unavailable_libraries", cast(set[str], set())))
    classification = classify_documentation_structure_fn(
        project_bp,
        unavailable_libraries=unavailable_libraries,
    )
    unit_candidates = sorted(
        discover_documentation_unit_candidates_fn(classification),
        key=lambda entry: len(entry.path),
        reverse=True,
    )
    candidate_paths = [
        tuple(candidate.path)
        for candidate in unit_candidates
        if looks_like_graphics_unit_root(tuple(candidate.path), entries)
    ]

    for entry in entries:
        module_path = tuple(
            segment.strip() for segment in str(entry.get("module_path") or "").split(".") if segment.strip()
        )
        if not module_path:
            continue

        unit_root_path = next(
            (
                candidate_path
                for candidate_path in candidate_paths
                if path_startswith_casefold(module_path, candidate_path)
            ),
            None,
        )
        if unit_root_path is None:
            continue

        unit_segments = list(module_path[len(unit_root_path) :])
        if not unit_segments:
            continue

        canonical_segments = [*unit_segments[:-1], graphics_entry_canonical_segment(entry)]
        entry["unit_root_path"] = ".".join(unit_root_path)
        entry["unit_structure_path"] = ".".join(canonical_segments)

        if (
            len(canonical_segments) >= 5
            and canonical_segments[0].casefold() == "l1"
            and canonical_segments[1].casefold() == "l2"
            and canonical_segments[3].casefold() == "l1"
            and canonical_segments[4].casefold() == "l2"
        ):
            entry["equipment_module_name"] = unit_segments[2]
            entry["equipment_module_structure_path"] = ".".join(canonical_segments[3:])

    return entries


def prompt_graphics_rule_definition(
    *,
    prompt_graphics_rule_definition_with_config_fn: Callable[[ConfigDict | None], GraphicsRule | None],
) -> GraphicsRule | None:
    return prompt_graphics_rule_definition_with_config_fn(None)


def prompt_graphics_rule_definition_with_config(
    cfg: ConfigDict | None,
    *,
    prompt_fn: Callable[..., str],
    pause_fn: Callable[[], None],
    pick_or_prompt_graphics_rule_selector_value_fn: Callable[..., str],
    prompt_graphics_rule_kind_fn: Callable[[], str],
    prompt_graphics_rule_selector_fn: Callable[..., tuple[str, str]],
    optional_prompt_or_none_fn: Callable[[Callable[[], Any]], Any | None],
    prompt_optional_float_list_fn: Callable[..., list[float]],
    prompt_optional_text_list_fn: Callable[[str], list[str]],
    prompt_optional_bool_fn: Callable[[str], bool],
    emit_output_fn: Callable[..., None],
    required_prompt_validation_error: type[Exception],
) -> GraphicsRule | None:
    emit_output_fn("\nEnter graphics rule values. Leave optional fields blank to skip them.")
    module_kind = prompt_graphics_rule_kind_fn()

    module_name = ""
    relative_module_path = ""
    unit_structure_path = ""
    equipment_module_structure_path = ""
    moduletype_name = ""

    if module_kind == "moduletype":
        moduletype_name = prompt_fn("ModuleType name")
        if not moduletype_name:
            emit_output_fn("? ModuleType name is required")
            pause_fn()
            return None
        try:
            selector_field, selector_value = prompt_graphics_rule_selector_fn(
                module_kind,
                cfg=cfg,
                pick_or_prompt_graphics_rule_selector_value_fn=pick_or_prompt_graphics_rule_selector_value_fn,
            )
        except required_prompt_validation_error:
            pause_fn()
            return None
    else:
        try:
            selector_field, selector_value = prompt_graphics_rule_selector_fn(
                module_kind,
                cfg=cfg,
                pick_or_prompt_graphics_rule_selector_value_fn=pick_or_prompt_graphics_rule_selector_value_fn,
            )
        except required_prompt_validation_error:
            pause_fn()
            return None

    if selector_field == "relative_module_path":
        relative_module_path = selector_value
    elif selector_field == "unit_structure_path":
        unit_structure_path = selector_value
    elif selector_field == "equipment_module_structure_path":
        equipment_module_structure_path = selector_value

    selector_name = relative_module_path or unit_structure_path or equipment_module_structure_path
    if selector_name:
        module_name = selector_name.split(".")[-1].strip()

    description = input("Description (optional): ").strip()
    invocation: dict[str, Any] = {}
    moduledef: dict[str, Any] = {}

    invocation_coords = optional_prompt_or_none_fn(
        lambda: prompt_optional_float_list_fn("Invocation coords", 5, pause_fn=pause_fn)
    )
    if invocation_coords is not None:
        invocation["coords"] = invocation_coords

    invocation_arguments = optional_prompt_or_none_fn(lambda: prompt_optional_text_list_fn("Invocation arguments"))
    if invocation_arguments is not None:
        invocation["arguments"] = invocation_arguments

    invocation_layer = input("Invocation layer (blank to skip): ").strip()
    if invocation_layer:
        invocation["layer"] = invocation_layer

    invocation_zoom_limits = optional_prompt_or_none_fn(
        lambda: prompt_optional_float_list_fn(
            "Invocation zoom limits",
            2,
            pause_fn=pause_fn,
        )
    )
    if invocation_zoom_limits is not None:
        invocation["zoom_limits"] = invocation_zoom_limits

    invocation_zoomable = optional_prompt_or_none_fn(lambda: prompt_optional_bool_fn("Invocation zoomable"))
    if invocation_zoomable is not None:
        invocation["zoomable"] = invocation_zoomable

    clipping_origin = optional_prompt_or_none_fn(
        lambda: prompt_optional_float_list_fn("Clipping origin", 2, pause_fn=pause_fn)
    )
    if clipping_origin is not None:
        moduledef["clipping_origin"] = clipping_origin

    clipping_size = optional_prompt_or_none_fn(
        lambda: prompt_optional_float_list_fn("Clipping size", 2, pause_fn=pause_fn)
    )
    if clipping_size is not None:
        moduledef["clipping_size"] = clipping_size

    moduledef_zoom_limits = optional_prompt_or_none_fn(
        lambda: prompt_optional_float_list_fn("ModuleDef zoom limits", 2, pause_fn=pause_fn)
    )
    if moduledef_zoom_limits is not None:
        moduledef["zoom_limits"] = moduledef_zoom_limits

    moduledef_grid = input("ModuleDef grid (blank to skip): ").strip()
    if moduledef_grid:
        try:
            moduledef["grid"] = float(moduledef_grid)
        except ValueError:
            emit_output_fn("? ModuleDef grid must be numeric")
            pause_fn()
            return None

    moduledef_zoomable = optional_prompt_or_none_fn(lambda: prompt_optional_bool_fn("ModuleDef zoomable"))
    if moduledef_zoomable is not None:
        moduledef["zoomable"] = moduledef_zoomable

    expected: dict[str, Any] = {}
    if invocation:
        expected["invocation"] = invocation
    if moduledef:
        expected["moduledef"] = moduledef

    if not expected:
        emit_output_fn("? At least one expected graphics field is required")
        pause_fn()
        return None

    return {
        "module_name": module_name,
        "module_kind": module_kind,
        "relative_module_path": relative_module_path,
        "unit_structure_path": unit_structure_path,
        "equipment_module_structure_path": equipment_module_structure_path,
        "moduletype_name": moduletype_name,
        "description": description,
        "expected": expected,
    }


def graphics_rules_menu(
    cfg: dict[str, Any] | None,
    *,
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[..., tuple[dict[str, Any], bool]],
    save_graphics_rules_fn: Callable[[Path, dict[str, Any]], None],
    prompt_graphics_rule_definition_with_config_fn: Callable[[dict[str, Any] | None], dict[str, Any] | None],
    graphics_rule_label_fn: Callable[[dict[str, Any]], str],
    clear_screen_fn: Callable[[], None],
    print_menu_fn: Callable[..., None],
    menu_option_factory: Callable[[str, str, str], Any],
    confirm_fn: Callable[[str], bool],
    prompt_fn: Callable[..., str],
    quit_app_fn: Callable[[], None],
    pause_fn: Callable[[], None],
    print_graphics_rules_summary_fn: Callable[[Path, dict[str, Any]], None],
    emit_output_fn: Callable[..., None],
    upsert_graphics_rule_fn: Callable[[dict[str, Any], dict[str, Any]], bool],
    remove_graphics_rule_fn: Callable[[dict[str, Any], int], dict[str, Any]],
) -> None:
    rules_path = get_graphics_rules_path_fn()
    rules, _created = load_graphics_rules_fn(rules_path)
    dirty = False

    while True:
        clear_screen_fn()
        print_graphics_rules_summary_fn(rules_path, rules, dirty=dirty)
        emit_output_fn()
        print_menu_fn(
            "Graphics rules",
            [
                menu_option_factory("1", "Add or replace rule", "Prompt for one module graphics rule"),
                menu_option_factory("2", "Remove rule", "Delete one configured graphics rule by index"),
                menu_option_factory("3", "Save rules", "Write graphics rules to the JSON file"),
                menu_option_factory("b", "Back", ""),
                menu_option_factory("q", "Quit", ""),
            ],
            intro=(
                "Graphics rules are user-defined expected invocation and ModuleDef settings. "
                "Use unit structure paths, equipment module structure paths, exact relative module paths, "
                "or ModuleType names depending on the rule scope."
            ),
        )
        choice = input("> ").strip().lower()

        if choice == "b":
            if dirty and confirm_fn("Unsaved graphics rule changes. Save before leaving?"):
                save_graphics_rules_fn(rules_path, rules)
            return
        if choice == "q":
            if dirty and confirm_fn("Unsaved graphics rule changes. Save before quitting?"):
                save_graphics_rules_fn(rules_path, rules)
            quit_app_fn()

        if choice == "1":
            rule = prompt_graphics_rule_definition_with_config_fn(cfg)
            if rule is None:
                continue
            updated = upsert_graphics_rule_fn(rules, rule)
            emit_output_fn("Updated existing graphics rule" if updated else "Added graphics rule")
            dirty = True
            pause_fn()
        elif choice == "2":
            if not rules.get("rules"):
                emit_output_fn("? No graphics rules configured")
                pause_fn()
                continue
            idx_text = prompt_fn("Index to remove")
            try:
                idx = int(idx_text) - 1
                removed = remove_graphics_rule_fn(rules, idx)
            except (ValueError, IndexError):
                emit_output_fn("? Invalid index")
                pause_fn()
                continue
            emit_output_fn(f"Removed {graphics_rule_label_fn(removed)}")
            dirty = True
            pause_fn()
        elif choice == "3":
            save_graphics_rules_fn(rules_path, rules)
            dirty = False
            pause_fn()
        else:
            emit_output_fn("Invalid choice.")
            pause_fn()
