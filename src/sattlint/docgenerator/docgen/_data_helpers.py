from __future__ import annotations

import re
import typing as t

from sattline_parser.models.ast_model import ParameterMapping, Variable

from ..classification import DocumentationClassification, DocumentedModule, discover_documentation_unit_candidates
from ._core import DocumentUnit, SequenceRenderRow, _prettify_name, _sequence_render_rows, _value_text

_TAG_NAME_RE = re.compile(r"^[A-Z]{1,4}\d{3,4}$")
_DEVICE_PREFIX_RE = re.compile(r"^(?:V|TT|PT|FT|WT|AIT|LS|ZS|PC|LC|TC|PM|BM)\d{3,4}$", re.IGNORECASE)
_OPERATION_EXCLUDE_NAMES = {"mes_info", "mes_stop"}


def _mapping_target_name(mapping: ParameterMapping) -> str:
    target = mapping.target
    if isinstance(target, dict):
        typed_target = t.cast(dict[str, object], target)
        return str(typed_target.get("var_name", ""))
    return str(target)


def _mapping_source_text(mapping: ParameterMapping) -> str:
    source = mapping.source
    if isinstance(source, dict):
        typed_source = t.cast(dict[str, object], source)
        return str(typed_source.get("var_name", ""))
    if source is not None:
        return str(source)
    source_literal = mapping.source_literal
    if source_literal is None:
        return ""
    return str(source_literal)


def _mapping_value(entry: DocumentedModule, *target_names: str) -> str | None:
    for wanted_name in target_names:
        wanted_cf = wanted_name.casefold()
        for mapping in entry.parametermappings:
            target_name = _mapping_target_name(mapping).casefold()
            if target_name != wanted_cf:
                continue
            source_text = _mapping_source_text(mapping).strip()
            if source_text:
                return source_text
    return None


def _display_name(entry: DocumentedModule) -> str:
    return _mapping_value(entry, "HeaderName", "MediaName", "Name") or entry.name


def _module_title(entry: DocumentedModule) -> str:
    return _mapping_value(entry, "Name") or entry.name


def _module_description(entry: DocumentedModule) -> str:
    description = _mapping_value(entry, "Name")
    if description and description.casefold() != entry.name.casefold():
        return f"Configured as {description}."
    for variable in (*entry.moduleparameters, *entry.localvariables):
        if variable.description:
            return variable.description
    return f"Detected {_prettify_name(entry.moduletype_name or entry.kind)} instance."


def _moduletype_summary(entry: DocumentedModule) -> str:
    return entry.moduletype_label or entry.moduletype_name or entry.kind


def _build_units(classification: DocumentationClassification) -> list[DocumentUnit]:
    scope_roots = list(classification.scope.roots or []) if classification.scope else []
    roots = scope_roots or discover_documentation_unit_candidates(classification)
    units: list[DocumentUnit] = []
    for root in roots:
        units.append(
            DocumentUnit(
                root=root,
                unit_code=_mapping_value(root, "Name") or root.name,
                title=_display_name(root),
                unit_class=root.moduletype_name or root.moduletype_label or root.name,
                section_name=_mapping_value(root, "SectionName") or root.name,
                equipment_modules=_unit_category_descendants(root, classification, "em"),
                operations=_unit_category_descendants(root, classification, "ops"),
                recipe_parameters=_unit_category_descendants(root, classification, "rp", top_level_only=True),
                engineering_parameters=_unit_category_descendants(root, classification, "ep", top_level_only=True),
                user_parameters=_unit_category_descendants(root, classification, "up", top_level_only=True),
            )
        )
    return units


def _unit_category_descendants(
    root: DocumentedModule,
    classification: DocumentationClassification,
    category: str,
    *,
    top_level_only: bool = False,
) -> list[DocumentedModule]:
    entries = classification.descendants(root, category=category)
    if not top_level_only:
        return entries

    excluded_ancestors = classification.descendants(root, category="em") + classification.descendants(
        root, category="ops"
    )
    return [
        entry
        for entry in entries
        if not any(
            entry.path != ancestor.path and entry.path[: len(ancestor.path)] == ancestor.path
            for ancestor in excluded_ancestors
        )
    ]


def _descendants(root: DocumentedModule, classification: DocumentationClassification) -> list[DocumentedModule]:
    return classification.descendants(root)


def _support_entries(unit: DocumentUnit, classification: DocumentationClassification) -> list[DocumentedModule]:
    descendants = _descendants(unit.root, classification)
    excluded = [*unit.equipment_modules, *unit.operations]
    return [
        entry
        for entry in descendants
        if not any(
            entry.path != ancestor.path and entry.path[: len(ancestor.path)] == ancestor.path for ancestor in excluded
        )
    ]


def _parameter_catalog_rows(entries: list[DocumentedModule]) -> list[list[str]]:
    rows: list[list[str]] = []
    for entry in entries:
        rows.append([_module_title(entry), _moduletype_summary(entry), entry.short_path, _module_description(entry)])
    return rows


def _module_list_rows(entries: list[DocumentedModule]) -> list[list[str]]:
    rows: list[list[str]] = []
    for entry in entries:
        rows.append([_module_title(entry), _module_description(entry), f"See section {_module_title(entry)}"])
    return rows


def _metadata_value(entry: DocumentedModule, *target_names: str) -> str:
    return _mapping_value(entry, *target_names) or ""


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value.strip():
            return value
    return ""


def _entry_variable(entry: DocumentedModule, *names: str) -> Variable | None:
    wanted = {name.casefold() for name in names}
    for variable in (*entry.moduleparameters, *entry.localvariables):
        if variable.name.casefold() in wanted:
            return variable
    return None


def _entry_variable_text(entry: DocumentedModule, *names: str) -> str:
    variable = _entry_variable(entry, *names)
    if variable is None:
        return ""
    return _first_non_empty(_value_text(variable.init_value), variable.description or "")


def _configurable_parameter_rows(unit: DocumentUnit) -> list[list[str]]:
    rows: list[list[str]] = []
    ignored = {"p", "allow", "colours", "programname", "headernamecolour", "nextview"}
    descriptions = {variable.name.casefold(): variable.description or "" for variable in unit.root.moduleparameters}
    for mapping in unit.root.parametermappings:
        target_name = _mapping_target_name(mapping).strip()
        if not target_name or target_name.casefold() in ignored:
            continue
        source_text = _mapping_source_text(mapping).strip()
        if not source_text:
            continue
        rows.append([target_name, descriptions.get(target_name.casefold(), ""), unit.unit_code, source_text])
    return rows


def _measurement_rows(entries: list[DocumentedModule]) -> list[list[str]]:
    rows: list[list[str]] = []
    for entry in entries:
        rows.append(
            [
                _module_title(entry),
                entry.name,
                _entry_variable_text(entry, "min", "lowlimit", "range_min"),
                _entry_variable_text(entry, "max", "highlimit", "range_max"),
                _first_non_empty(
                    _metadata_value(entry, "EngUnit", "Unit", "EU"),
                    _entry_variable_text(entry, "engunit", "unit", "eu"),
                ),
                _first_non_empty(
                    _metadata_value(entry, "LogIntervalMax", "MaxLogInterval"),
                    _entry_variable_text(entry, "logintervalmax", "maxloginterval"),
                ),
                _first_non_empty(
                    _metadata_value(entry, "DeadbandRelative", "DeadBand"),
                    _entry_variable_text(entry, "deadbandrelative", "deadband"),
                ),
                _first_non_empty(
                    _metadata_value(entry, "LogIntervalMin", "MinLogInterval"),
                    _entry_variable_text(entry, "logintervalmin", "minloginterval"),
                ),
            ]
        )
    return rows


def _generic_section_rows(entries: list[DocumentedModule]) -> list[list[str]]:
    return [
        [_module_title(entry), _moduletype_summary(entry), entry.short_path, _module_description(entry)]
        for entry in entries
    ]


def _simple_name_tag_rows(entries: list[DocumentedModule], description_label: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for entry in entries:
        rows.append(
            [_module_description(entry) if description_label == "description" else _module_title(entry), entry.name]
        )
    return rows


def _event_table_rows(entries: list[DocumentedModule]) -> list[list[str]]:
    rows: list[list[str]] = []
    for entry in entries:
        rows.append(
            [
                entry.name,
                _module_description(entry),
                _metadata_value(entry, "Severity", "Sev"),
                _metadata_value(entry, "Activation", "Condition"),
            ]
        )
    return rows


def _interlock_rows(variables: list[Variable]) -> list[list[str]]:
    return [[variable.name, variable.description or "", _value_text(variable.init_value), ""] for variable in variables]


def _exception_rows(variables: list[Variable]) -> list[list[str]]:
    return [[variable.name, variable.description or ""] for variable in variables]


def _calculation_rows(entries: list[DocumentedModule]) -> list[list[str]]:
    rows: list[list[str]] = []
    for entry in entries:
        rows.append([entry.name, _module_description(entry), entry.short_path])
    return rows


def _communication_rows(unit: DocumentUnit, *, direction: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for mapping in unit.root.parametermappings:
        target_name = _mapping_target_name(mapping).strip()
        if not target_name:
            continue
        target_cf = target_name.casefold()
        if direction == "from" and not target_cf.startswith("inlet"):
            continue
        if direction == "to" and not target_cf.startswith("outlet"):
            continue
        connection = _mapping_source_text(mapping).strip() or target_name
        rows.append([connection, f"Mapped via {target_name}"])
    return rows


def _state_rows(entry: DocumentedModule, classification: DocumentationClassification) -> list[list[str]]:
    rows: list[list[str]] = []
    seen_paths: set[tuple[str, ...]] = set()
    for descendant in classification.descendants(entry):
        if descendant.path in seen_paths:
            continue
        if len(descendant.path) < 2:
            continue
        if descendant.path[-2].casefold() != "panel":
            continue
        if descendant.name.casefold().startswith("kahctoggle"):
            continue
        rows.append(
            [
                _module_title(descendant),
                _module_description(descendant),
                _state_logic_summary(descendant, classification),
            ]
        )
        seen_paths.add(descendant.path)
    return rows


def _state_logic_summary(entry: DocumentedModule, classification: DocumentationClassification) -> str:
    sequence_count = 0
    equation_count = 0
    state_logic_types = 0
    for descendant in classification.descendants(entry):
        if descendant.moduletype_name and descendant.moduletype_name.casefold() == "statelogic":
            state_logic_types += 1
        if descendant.modulecode is not None:
            sequence_count += len(descendant.modulecode.sequences or [])
            equation_count += len(descendant.modulecode.equations or [])
    parts: list[str] = []
    if state_logic_types:
        parts.append(f"{state_logic_types} state-logic modules")
    if sequence_count:
        parts.append(f"{sequence_count} sequences")
    if equation_count:
        parts.append(f"{equation_count} equation blocks")
    return ", ".join(parts) if parts else "Display-only state definition"


def _pid_controller_rows(entry: DocumentedModule, classification: DocumentationClassification) -> list[list[str]]:
    rows: list[list[str]] = []
    for descendant in classification.descendants(entry):
        name_cf = descendant.name.casefold()
        label_cf = _moduletype_summary(descendant).casefold()
        if not ("pid" in label_cf or label_cf.endswith("ctrl") or name_cf.startswith(("pc", "lc", "tc"))):
            continue
        rows.append(
            [descendant.name, _moduletype_summary(descendant), descendant.short_path, _module_description(descendant)]
        )
    return rows


def _sequence_rows(
    entry: DocumentedModule, classification: DocumentationClassification
) -> list[tuple[str, list[SequenceRenderRow]]]:
    rows: list[tuple[str, list[SequenceRenderRow]]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in [entry, *classification.descendants(entry)]:
        if candidate.modulecode is None:
            continue
        for sequence in candidate.modulecode.sequences or []:
            key = (candidate.short_path, sequence.name)
            if key in seen:
                continue
            rows.append((sequence.name, _sequence_render_rows(sequence)))
            seen.add(key)
    return rows


def _message_rows(entry: DocumentedModule, classification: DocumentationClassification) -> list[list[str]]:
    rows: list[list[str]] = []
    for descendant in classification.descendants(entry):
        name_cf = descendant.name.casefold()
        label_cf = _moduletype_summary(descendant).casefold()
        if "message" not in name_cf and "message" not in label_cf and "opmess" not in label_cf:
            continue
        rows.append(
            [descendant.name, _moduletype_summary(descendant), descendant.short_path, _module_description(descendant)]
        )
    return rows


def _event_rows(entry: DocumentedModule, classification: DocumentationClassification) -> list[list[str]]:
    rows: list[list[str]] = []
    for descendant in classification.descendants(entry):
        name_cf = descendant.name.casefold()
        label_cf = _moduletype_summary(descendant).casefold()
        if not (name_cf.startswith("event") or "journal" in label_cf or "event" in label_cf):
            continue
        rows.append(
            [descendant.name, _moduletype_summary(descendant), descendant.short_path, _module_description(descendant)]
        )
    return rows


def _special_logging_rows(entry: DocumentedModule, classification: DocumentationClassification) -> list[list[str]]:
    rows: list[list[str]] = []
    for descendant in classification.descendants(entry):
        label_cf = _moduletype_summary(descendant).casefold()
        name_cf = descendant.name.casefold()
        if "journal" not in label_cf and "log" not in name_cf and "journal" not in name_cf:
            continue
        rows.append(
            [descendant.name, _moduletype_summary(descendant), descendant.short_path, _module_description(descendant)]
        )
    return rows


def _variable_rows(variables: list[Variable]) -> list[list[str]]:
    return [
        [variable.name, variable.datatype_text, _value_text(variable.init_value), variable.description or ""]
        for variable in variables
    ]


def _is_within_any(entry: DocumentedModule, ancestors: list[DocumentedModule]) -> bool:
    return any(
        entry.path != ancestor.path and entry.path[: len(ancestor.path)] == ancestor.path for ancestor in ancestors
    )


def _is_measurement_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    return bool(
        _TAG_NAME_RE.match(entry.name)
        or _DEVICE_PREFIX_RE.match(entry.name)
        or any(token in label_cf for token in ("analog", "switch", "flow", "scale", "pressure"))
    )


def _is_special_logging_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    name_cf = entry.name.casefold()
    return "journal" in label_cf or ("log" in name_cf and "inletcons" not in name_cf)


def _is_inlet_consumption_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    name_cf = entry.name.casefold()
    return "inletcons" in name_cf or "incons" in label_cf


def _is_timer_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    return "timer" in entry.name.casefold() or "timer" in label_cf


def _is_event_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    name_cf = entry.name.casefold()
    return name_cf.startswith("event") or "event" in label_cf or "journal" in label_cf


def _is_graphics_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    return any(token in label_cf for token in ("icon", "view", "toggle", "header", "infotext", "transferdisplay"))


def _is_calculation_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    return any(token in label_cf for token in ("minmax", "pid", "realtoreal", "calc", "ctrl"))


def _is_cip_valve_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    name_cf = entry.name.casefold()
    return name_cf.startswith("v") and "cip" in label_cf


def _is_other_device_entry(entry: DocumentedModule) -> bool:
    if _is_measurement_entry(entry) or _is_graphics_entry(entry) or _is_special_logging_entry(entry):
        return False
    return _DEVICE_PREFIX_RE.match(entry.name) is not None


def _is_intervention_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    return "button" in label_cf or "manual" in label_cf


def _is_supervision_entry(entry: DocumentedModule) -> bool:
    label_cf = _moduletype_summary(entry).casefold()
    name_cf = entry.name.casefold()
    return any(token in label_cf or token in name_cf for token in ("warning", "alarm", "supervision"))
