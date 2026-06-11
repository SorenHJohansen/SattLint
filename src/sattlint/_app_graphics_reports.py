from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from .app_telemetry import telemetry_output_path

ConfigDict = dict[str, Any]
GraphicsRule = dict[str, Any]
GraphicsRulesConfig = dict[str, Any]


def format_config_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value in (None, ""):
        return "(not set)"
    return str(value)


def print_config_section(
    title: str,
    rows: list[tuple[str, object]],
    *,
    emit_output_fn: Callable[..., None],
    format_config_scalar_fn: Callable[[object], str],
) -> None:
    emit_output_fn(title)
    if not rows:
        emit_output_fn("  (none)")
        return

    label_width = max(len(label) for label, _ in rows)
    for label, value in rows:
        emit_output_fn(f"  {label:<{label_width}}  {format_config_scalar_fn(value)}")


def print_config_list(
    title: str,
    items: list[object],
    *,
    emit_output_fn: Callable[..., None],
    format_config_scalar_fn: Callable[[object], str],
) -> None:
    emit_output_fn(title)
    if not items:
        emit_output_fn("  (none)")
        return

    for index, item in enumerate(items, 1):
        emit_output_fn(f"  [{index}] {format_config_scalar_fn(item)}")


def show_config(
    cfg: ConfigDict,
    *,
    get_documentation_config_fn: Callable[[dict[str, Any] | None], dict[str, Any]],
    get_graphics_rules_path_fn: Callable[[], Path],
    load_graphics_rules_fn: Callable[..., tuple[GraphicsRulesConfig, bool]],
    graphics_rule_config_line_fn: Callable[[GraphicsRule], str],
    emit_output_fn: Callable[..., None],
    print_config_list_fn: Callable[[str, list[object]], None],
    print_config_section_fn: Callable[[str, list[tuple[str, object]]], None],
) -> None:
    documentation_cfg = get_documentation_config_fn(cfg)
    graphics_rules_path = get_graphics_rules_path_fn()
    graphics_rule_count: object = 0
    graphics_rules_payload: GraphicsRulesConfig | None = None
    if graphics_rules_path.exists():
        try:
            graphics_rules, _created = load_graphics_rules_fn(graphics_rules_path)
        except Exception as exc:  # noqa: BLE001
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
    telemetry_cfg = cast(dict[str, object], cfg.get("telemetry", {}))
    telemetry_rows = [
        ("enabled", telemetry_cfg.get("enabled", False)),
        ("path", telemetry_output_path()),
    ]
    directory_rows = [
        ("program_dir", cfg["program_dir"]),
        ("ABB_lib_dir", cfg["ABB_lib_dir"]),
        ("icf_dir", cfg["icf_dir"]),
    ]

    emit_output_fn("\nCurrent Configuration")
    emit_output_fn("=" * 21)
    emit_output_fn()
    print_config_list_fn("Analyzed Programs And Libraries", list(cfg["analyzed_programs_and_libraries"]))
    emit_output_fn()
    print_config_section_fn("General", general_rows)
    emit_output_fn()
    print_config_section_fn("Telemetry", telemetry_rows)
    emit_output_fn()
    print_config_section_fn("Directories", directory_rows)
    emit_output_fn()
    print_config_list_fn("Other Library Directories", list(cfg["other_lib_dirs"]))
    emit_output_fn()
    print_config_section_fn(
        "Graphics Rules",
        [
            ("graphics_rules_path", graphics_rules_path),
            ("graphics_rule_count", graphics_rule_count),
        ],
    )
    if graphics_rules_payload and graphics_rules_payload.get("rules"):
        emit_output_fn("Configured Graphics Rule Selectors")
        configured_rules = cast(list[GraphicsRule], list(graphics_rules_payload.get("rules", [])))
        for index, rule in enumerate(configured_rules, start=1):
            emit_output_fn(f"  [{index}] {graphics_rule_config_line_fn(rule)}")
    emit_output_fn()
    emit_output_fn("Documentation Classifications")
    classifications = cast(dict[str, dict[str, list[object]]], documentation_cfg.get("classifications", {}))
    for category, rule in classifications.items():
        active_rules = [(key, ", ".join(str(value) for value in values)) for key, values in rule.items() if values]
        emit_output_fn(f"  {category}")
        if not active_rules:
            emit_output_fn("    (none)")
            continue
        label_width = max(len(key) for key, _ in active_rules)
        for key, value in active_rules:
            emit_output_fn(f"    {key:<{label_width}}  {value}")
    emit_output_fn()


def flatten_graphics_expected_fields(
    payload: dict[str, Any],
    *,
    prefix: str = "",
) -> list[str]:
    fields: list[str] = []
    for key, value in payload.items():
        field_name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            fields.extend(flatten_graphics_expected_fields(cast(dict[str, Any], value), prefix=field_name))
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


def print_graphics_rules_summary(
    path: Path,
    rules: dict[str, Any],
    *,
    dirty: bool,
    emit_output_fn: Callable[..., None],
) -> None:
    emit_output_fn("Graphics Rules")
    emit_output_fn("=" * 14)
    emit_output_fn(f"Path: {path}")
    emit_output_fn(f"Status: {'unsaved changes' if dirty else 'saved'}")
    emit_output_fn()

    configured_rules = cast(list[GraphicsRule], list(rules.get("rules", [])))
    if not configured_rules:
        emit_output_fn("No graphics rules configured yet.")
        return

    headers = ("#", "Kind", "Scope", "Selector", "Fields", "Description")
    rows: list[tuple[str, str, str, str, str, str]] = []
    for index, rule in enumerate(configured_rules, start=1):
        expected = rule.get("expected")
        expected_payload = cast(dict[str, Any], expected) if isinstance(expected, dict) else None
        fields = ", ".join(flatten_graphics_expected_fields(expected_payload)) if expected_payload else ""
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

    widths: list[int] = []
    max_widths = [4, 12, 12, 48, 36, 28]
    for column_index, header in enumerate(headers):
        content_width = max((len(row[column_index]) for row in rows), default=0)
        widths.append(min(max(len(header), content_width), max_widths[column_index]))

    header_line = "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    separator_line = "  ".join("-" * widths[index] for index in range(len(headers)))
    emit_output_fn(header_line)
    emit_output_fn(separator_line)
    for row in rows:
        emit_output_fn(
            "  ".join(truncate_table_cell(value, widths[index]).ljust(widths[index]) for index, value in enumerate(row))
        )
