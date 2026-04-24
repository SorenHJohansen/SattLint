from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from . import config as config_module
from . import graphics_rules as graphics_rules_module
from .docgenerator.classification import (
    classify_documentation_structure,
    discover_documentation_unit_candidates,
)
from .models.ast_model import BasePicture
from .models.project_graph import ProjectGraph

LoadedProjectIterator = Callable[[dict[str, Any]], Iterator[tuple[str, BasePicture, ProjectGraph]]]


def get_graphics_rules_path(config_path: Path) -> Path:
    return graphics_rules_module.get_graphics_rules_path(config_path)


def load_graphics_rules(config_path: Path, path: Path | None = None):
    return graphics_rules_module.load_graphics_rules(path or get_graphics_rules_path(config_path))


def save_graphics_rules(path: Path, rules: dict[str, Any]) -> None:
    graphics_rules_module.save_graphics_rules(path, rules)


def _format_config_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value in (None, ""):
        return "(not set)"
    return str(value)


def _print_config_section(title: str, rows: list[tuple[str, object]]) -> None:
    print(title)
    if not rows:
        print("  (none)")
        return

    label_width = max(len(label) for label, _ in rows)
    for label, value in rows:
        print(f"  {label:<{label_width}}  {_format_config_scalar(value)}")


def _print_config_list(title: str, items: list[object]) -> None:
    print(title)
    if not items:
        print("  (none)")
        return

    for index, item in enumerate(items, 1):
        print(f"  [{index}] {_format_config_scalar(item)}")


def show_config(
    cfg: dict[str, Any],
    *,
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[..., tuple[dict[str, Any], bool]],
    graphics_rule_config_line_fn: Callable[[dict[str, Any]], str],
) -> None:
    documentation_cfg = config_module.get_documentation_config(cfg)
    graphics_rules_path = get_graphics_rules_path_fn()
    graphics_rule_count: object = 0
    graphics_rules_payload: dict[str, Any] | None = None
    if graphics_rules_path.exists():
        try:
            graphics_rules, _created = load_graphics_rules_fn(graphics_rules_path)
        except Exception as exc:
            graphics_rule_count = f"invalid ({exc})"
        else:
            graphics_rules_payload = graphics_rules
            graphics_rule_count = len(graphics_rules.get("rules", []))
    general_rows = [
        ("mode", cfg["mode"]),
        ("scan_root_only", cfg["scan_root_only"]),
        ("fast_cache_validation", cfg["fast_cache_validation"]),
        ("debug", cfg["debug"]),
    ]
    directory_rows = [
        ("program_dir", cfg["program_dir"]),
        ("ABB_lib_dir", cfg["ABB_lib_dir"]),
        ("icf_dir", cfg["icf_dir"]),
    ]

    print("\nCurrent Configuration")
    print("=" * 21)
    print()
    _print_config_list(
        "Analyzed Programs And Libraries",
        list(cfg["analyzed_programs_and_libraries"]),
    )
    print()
    _print_config_section("General", general_rows)
    print()
    _print_config_section("Directories", directory_rows)
    print()
    _print_config_list("Other Library Directories", list(cfg["other_lib_dirs"]))
    print()
    _print_config_section(
        "Graphics Rules",
        [
            ("graphics_rules_path", graphics_rules_path),
            ("graphics_rule_count", graphics_rule_count),
        ],
    )
    if graphics_rules_payload and graphics_rules_payload.get("rules"):
        print("Configured Graphics Rule Selectors")
        for index, rule in enumerate(graphics_rules_payload.get("rules", []), start=1):
            print(f"  [{index}] {graphics_rule_config_line_fn(rule)}")
    print()
    print("Documentation Classifications")
    for category, rule in documentation_cfg.get("classifications", {}).items():
        active_rules = [(key, ", ".join(str(value) for value in values)) for key, values in rule.items() if values]
        print(f"  {category}")
        if not active_rules:
            print("    (none)")
            continue
        label_width = max(len(key) for key, _ in active_rules)
        for key, value in active_rules:
            print(f"    {key:<{label_width}}  {value}")
    print()


def flatten_graphics_expected_fields(
    payload: dict[str, Any],
    *,
    prefix: str = "",
) -> list[str]:
    fields: list[str] = []
    for key, value in payload.items():
        field_name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            fields.extend(flatten_graphics_expected_fields(value, prefix=field_name))
        else:
            fields.append(field_name)
    return fields


def truncate_table_cell(value: object, width: int) -> str:
    text = str(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def graphics_rule_selector_text(rule: dict[str, Any]) -> str:
    module_kind = str(rule.get("module_kind") or "")
    relative_module_path = str(rule.get("relative_module_path") or "").strip()
    unit_structure_path = str(rule.get("unit_structure_path") or "").strip()
    equipment_module_structure_path = str(rule.get("equipment_module_structure_path") or "").strip()
    if unit_structure_path:
        return f"unit:{unit_structure_path}"
    if equipment_module_structure_path:
        return f"equipment:{equipment_module_structure_path}"
    if module_kind == "moduletype":
        moduletype_name = str(rule.get("moduletype_name") or "").strip()
        if relative_module_path:
            return f"{moduletype_name} @ path:{relative_module_path}"
        return moduletype_name or "(missing moduletype name)"
    if relative_module_path:
        return f"path:{relative_module_path}"
    return str(rule.get("module_name") or "(missing module name)")


def graphics_rule_label(rule: dict[str, Any]) -> str:
    return f"{rule['module_kind']}:{graphics_rule_selector_text(rule)}"


def graphics_rule_scope_text(rule: dict[str, Any]) -> str:
    if str(rule.get("unit_structure_path") or "").strip():
        return "unit"
    if str(rule.get("equipment_module_structure_path") or "").strip():
        return "equipment"
    if str(rule.get("relative_module_path") or "").strip():
        return "path"
    if str(rule.get("moduletype_name") or "").strip():
        return "moduletype"
    return "name"


def graphics_rule_config_line(rule: dict[str, Any]) -> str:
    parts = [
        str(rule.get("module_kind") or ""),
        f"scope={graphics_rule_scope_text(rule)}",
    ]
    unit_structure_path = str(rule.get("unit_structure_path") or "").strip()
    equipment_module_structure_path = str(rule.get("equipment_module_structure_path") or "").strip()
    relative_module_path = str(rule.get("relative_module_path") or "").strip()
    moduletype_name = str(rule.get("moduletype_name") or "").strip()
    description = str(rule.get("description") or "").strip()

    if unit_structure_path:
        parts.append(f"unit_structure_path={unit_structure_path}")
    if equipment_module_structure_path:
        parts.append(f"equipment_module_structure_path={equipment_module_structure_path}")
    if relative_module_path:
        parts.append(f"relative_module_path={relative_module_path}")
    if moduletype_name:
        parts.append(f"moduletype_name={moduletype_name}")
    if description:
        parts.append(f"description={description}")
    return " | ".join(part for part in parts if part)


def print_graphics_rules_summary(path: Path, rules: dict[str, Any], *, dirty: bool) -> None:
    print("Graphics Rules")
    print("=" * 14)
    print(f"Path: {path}")
    print(f"Status: {'unsaved changes' if dirty else 'saved'}")
    print()

    configured_rules = list(rules.get("rules", []))
    if not configured_rules:
        print("No graphics rules configured yet.")
        return

    headers = ("#", "Kind", "Scope", "Selector", "Fields", "Description")
    rows = []
    for index, rule in enumerate(configured_rules, start=1):
        expected = rule.get("expected")
        fields = ", ".join(flatten_graphics_expected_fields(expected)) if isinstance(expected, dict) else ""
        rows.append(
            (
                str(index),
                str(rule.get("module_kind") or ""),
                graphics_rule_scope_text(rule),
                graphics_rule_selector_text(rule),
                fields,
                str(rule.get("description") or ""),
            )
        )

    widths = []
    max_widths = [4, 12, 12, 48, 36, 28]
    for column_index, header in enumerate(headers):
        content_width = max((len(row[column_index]) for row in rows), default=0)
        widths.append(min(max(len(header), content_width), max_widths[column_index]))

    header_line = "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    separator_line = "  ".join("-" * widths[index] for index in range(len(headers)))
    print(header_line)
    print(separator_line)
    for row in rows:
        print(
            "  ".join(
                truncate_table_cell(value, widths[index]).ljust(widths[index])
                for index, value in enumerate(row)
            )
        )


def prompt_optional_float_list(label: str, expected_count: int, *, pause_fn: Callable[[], None]) -> list[float] | None:
    raw = input(f"{label} ({expected_count} comma-separated numbers, blank to skip): ").strip()
    if not raw:
        return None
    try:
        values = [float(part.strip()) for part in raw.split(",")]
    except ValueError:
        print("? Must be numeric")
        pause_fn()
        return None
    if len(values) != expected_count:
        print(f"? Expected {expected_count} values")
        pause_fn()
        return None
    return values


def prompt_optional_text_list(label: str) -> list[str] | None:
    raw = input(f"{label} (comma-separated, blank to skip): ").strip()
    if not raw:
        return None
    return [part.strip() for part in raw.split(",") if part.strip()]


def prompt_optional_bool(label: str) -> bool | None:
    raw = input(f"{label} [y/n, blank to skip]: ").strip().lower()
    if not raw:
        return None
    if raw in {"y", "yes", "true", "1"}:
        return True
    if raw in {"n", "no", "false", "0"}:
        return False
    print("? Enter y or n")
    return None


def prompt_graphics_rule_kind() -> str:
    print("\nChoose graphics rule target kind:")
    print("  1) Frame")
    print("  2) Single module")
    print("  3) ModuleType")
    while True:
        choice = input("> ").strip().lower()
        if choice == "1":
            return "frame"
        if choice == "2":
            return "single"
        if choice == "3":
            return "moduletype"
        print("? Choose 1, 2, or 3")


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
    cfg: dict[str, Any] | None,
    *,
    selector_field: str,
    module_kind: str,
    has_analyzed_targets_fn: Callable[[dict[str, Any]], bool],
    iter_loaded_projects_fn: LoadedProjectIterator,
    collect_graphics_layout_entries_for_target_fn: Callable[[str, BasePicture, ProjectGraph], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
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
    cfg: dict[str, Any] | None = None,
    discover_graphics_rule_selector_options_fn: Callable[..., list[dict[str, Any]]],
) -> str:
    options = discover_graphics_rule_selector_options_fn(
        cfg,
        selector_field=selector_field,
        module_kind=module_kind,
    )
    prompt_text = selector_prompt_text(selector_field)

    if options:
        print(f"\nAvailable {prompt_text.lower()} values:")
        for index, option in enumerate(options, start=1):
            print(
                f"  {index}) {option['selector_value']} "
                f"[{option['count']} matches across {option['target_count']} targets]"
            )
        print("  m) Enter manually")

        while True:
            raw = input("> ").strip().lower()
            if raw == "m":
                break
            try:
                selected_index = int(raw) - 1
            except ValueError:
                print("? Choose an index or 'm'")
                continue
            if 0 <= selected_index < len(options):
                return str(options[selected_index]["selector_value"])
            print("? Invalid index")

    selector_value = input(f"{prompt_text}: ").strip()
    if not selector_value:
        print("? Selector path is required")
    return selector_value


def prompt_graphics_rule_selector(
    module_kind: str,
    *,
    cfg: dict[str, Any] | None = None,
    pick_or_prompt_graphics_rule_selector_value_fn: Callable[..., str],
) -> tuple[str, str]:
    if module_kind == "frame":
        selector_field = "relative_module_path"
    elif module_kind == "single":
        print("\nChoose selector scope:")
        print("  1) Relative module path")
        print("  2) Unit structure path")
        print("  3) Equipment module structure path")
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
            print("? Choose 1, 2, or 3")
    else:
        print("\nChoose ModuleType selector scope:")
        print("  1) Relative module path")
        print("  2) Unit structure path")
        print("  3) Equipment module structure path")
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
            print("? Choose 1, 2, or 3")

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
    entries: list[dict[str, Any]],
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    classify_documentation_structure_fn: Callable[..., Any] = classify_documentation_structure,
    discover_documentation_unit_candidates_fn: Callable[[Any], Sequence[Any]] = discover_documentation_unit_candidates,
) -> list[dict[str, Any]]:
    classification = classify_documentation_structure_fn(
        project_bp,
        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
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
    prompt_graphics_rule_definition_with_config_fn: Callable[[dict[str, Any] | None], dict[str, Any] | None],
) -> dict[str, Any] | None:
    return prompt_graphics_rule_definition_with_config_fn(None)


def prompt_graphics_rule_definition_with_config(
    cfg: dict[str, Any] | None,
    *,
    prompt_fn: Callable[..., str],
    pause_fn: Callable[[], None],
    pick_or_prompt_graphics_rule_selector_value_fn: Callable[..., str],
) -> dict[str, Any] | None:
    print("\nEnter graphics rule values. Leave optional fields blank to skip them.")
    module_kind = prompt_graphics_rule_kind()

    module_name = ""
    relative_module_path = ""
    unit_structure_path = ""
    equipment_module_structure_path = ""
    moduletype_name = ""

    if module_kind == "moduletype":
        moduletype_name = prompt_fn("ModuleType name")
        if not moduletype_name:
            print("? ModuleType name is required")
            pause_fn()
            return None
        selector_field, selector_value = prompt_graphics_rule_selector(
            module_kind,
            cfg=cfg,
            pick_or_prompt_graphics_rule_selector_value_fn=pick_or_prompt_graphics_rule_selector_value_fn,
        )
    else:
        selector_field, selector_value = prompt_graphics_rule_selector(
            module_kind,
            cfg=cfg,
            pick_or_prompt_graphics_rule_selector_value_fn=pick_or_prompt_graphics_rule_selector_value_fn,
        )

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

    invocation_coords = prompt_optional_float_list("Invocation coords", 5, pause_fn=pause_fn)
    if invocation_coords is not None:
        invocation["coords"] = invocation_coords

    invocation_arguments = prompt_optional_text_list("Invocation arguments")
    if invocation_arguments is not None:
        invocation["arguments"] = invocation_arguments

    invocation_layer = input("Invocation layer (blank to skip): ").strip()
    if invocation_layer:
        invocation["layer"] = invocation_layer

    invocation_zoom_limits = prompt_optional_float_list(
        "Invocation zoom limits",
        2,
        pause_fn=pause_fn,
    )
    if invocation_zoom_limits is not None:
        invocation["zoom_limits"] = invocation_zoom_limits

    invocation_zoomable = prompt_optional_bool("Invocation zoomable")
    if invocation_zoomable is not None:
        invocation["zoomable"] = invocation_zoomable

    clipping_origin = prompt_optional_float_list("Clipping origin", 2, pause_fn=pause_fn)
    if clipping_origin is not None:
        moduledef["clipping_origin"] = clipping_origin

    clipping_size = prompt_optional_float_list("Clipping size", 2, pause_fn=pause_fn)
    if clipping_size is not None:
        moduledef["clipping_size"] = clipping_size

    moduledef_zoom_limits = prompt_optional_float_list("ModuleDef zoom limits", 2, pause_fn=pause_fn)
    if moduledef_zoom_limits is not None:
        moduledef["zoom_limits"] = moduledef_zoom_limits

    moduledef_grid = input("ModuleDef grid (blank to skip): ").strip()
    if moduledef_grid:
        try:
            moduledef["grid"] = float(moduledef_grid)
        except ValueError:
            print("? ModuleDef grid must be numeric")
            pause_fn()
            return None

    moduledef_zoomable = prompt_optional_bool("ModuleDef zoomable")
    if moduledef_zoomable is not None:
        moduledef["zoomable"] = moduledef_zoomable

    expected: dict[str, Any] = {}
    if invocation:
        expected["invocation"] = invocation
    if moduledef:
        expected["moduledef"] = moduledef

    if not expected:
        print("? At least one expected graphics field is required")
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


def collect_graphics_layout_entries_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
    *,
    annotate_graphics_entries_with_structure_paths_fn: Callable[[list[dict[str, Any]], BasePicture, ProjectGraph], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    from .devtools import structural_reports as structural_reports_module

    synthetic_entry_file = Path.cwd() / f"{target_name}.s"
    snapshot = SimpleNamespace(
        entry_file=synthetic_entry_file,
        base_picture=project_bp,
        project_graph=graph,
    )
    discovery = SimpleNamespace(
        program_files=(synthetic_entry_file,),
        dependency_files=(),
    )
    report = structural_reports_module.collect_graphics_layout_report(
        workspace_root=Path.cwd(),
        graph_inputs=(discovery, [snapshot], []),
    )
    return annotate_graphics_entries_with_structure_paths_fn(
        list(report.get("entries", [])),
        project_bp,
        graph,
    )


def graphics_rules_menu(
    cfg: dict[str, Any] | None = None,
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
) -> None:
    rules_path = get_graphics_rules_path_fn()
    rules, _created = load_graphics_rules_fn(rules_path)
    dirty = False

    while True:
        clear_screen_fn()
        print_graphics_rules_summary(rules_path, rules, dirty=dirty)
        print()
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
        c = input("> ").strip().lower()

        if c == "b":
            if dirty and confirm_fn("Unsaved graphics rule changes. Save before leaving?"):
                save_graphics_rules_fn(rules_path, rules)
            return
        if c == "q":
            if dirty and confirm_fn("Unsaved graphics rule changes. Save before quitting?"):
                save_graphics_rules_fn(rules_path, rules)
            quit_app_fn()

        if c == "1":
            rule = prompt_graphics_rule_definition_with_config_fn(cfg)
            if rule is None:
                continue
            updated = graphics_rules_module.upsert_graphics_rule(rules, rule)
            print("Updated existing graphics rule" if updated else "Added graphics rule")
            dirty = True
            pause_fn()
        elif c == "2":
            if not rules.get("rules"):
                print("? No graphics rules configured")
                pause_fn()
                continue
            idx_text = prompt_fn("Index to remove")
            try:
                idx = int(idx_text) - 1
                removed = graphics_rules_module.remove_graphics_rule(rules, idx)
            except (ValueError, IndexError):
                print("? Invalid index")
                pause_fn()
                continue
            print(f"Removed {graphics_rule_label_fn(removed)}")
            dirty = True
            pause_fn()
        elif c == "3":
            save_graphics_rules_fn(rules_path, rules)
            dirty = False
            pause_fn()
        else:
            print("Invalid choice.")
            pause_fn()


def run_graphics_rules_validation(
    cfg: dict[str, Any],
    *,
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[..., tuple[dict[str, Any], bool]],
    iter_loaded_projects_fn: LoadedProjectIterator,
    collect_graphics_layout_entries_for_target_fn: Callable[[str, BasePicture, ProjectGraph], list[dict[str, Any]]],
    pause_fn: Callable[[], None],
) -> None:
    print("\n--- Validate Graphics Rules ---")
    rules_path = get_graphics_rules_path_fn()
    rules, _created = load_graphics_rules_fn(rules_path)
    if not rules.get("rules"):
        print("? No graphics rules configured. Open Setup -> Edit graphics rules to add rules first.")
        pause_fn()
        return

    for target_name, project_bp, graph in iter_loaded_projects_fn(cfg):
        try:
            entries = collect_graphics_layout_entries_for_target_fn(
                target_name,
                project_bp,
                graph,
            )
            report = graphics_rules_module.validate_graphics_layout_entries(
                entries,
                rules,
                target_name=target_name,
                rules_path=rules_path,
            )
            print(f"\n=== Target: {target_name} ===")
            print(report.summary())
        except Exception as exc:
            print(f"? Error during graphics rules validation for {target_name}: {exc}")

    pause_fn()
