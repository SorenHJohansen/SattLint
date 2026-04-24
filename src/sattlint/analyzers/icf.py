from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    Simple_DataType,
    SingleModule,
    Variable,
)
from ..reporting.icf_report import (
    ICFEntry,
    ICFResolvedEntry,
    ICFValidationIssue,
    ICFValidationReport,
)
from ..resolution.common import (
    ResolvedModulePath,
    resolve_module_by_strict_path,
    resolve_moduletype_def_strict,
)
from ..resolution.type_graph import TypeGraph

_ICF_REF_RE = re.compile(r"(?:^|.*?)(?:[A-Za-z]::)?(?P<program>[^:]+):(?P<path>.+)$")
_ICF_HEADER_RE = re.compile(r"^\[(?P<tag>[^\]\s]+)(?:\s+(?P<label>.+?))?\]$")

_GROUP_SUFFIX_RULES: dict[str, dict[str, tuple[tuple[str, ...], ...]]] = {
    "journaldata_dcstomes": {
        "opr_id": (("T", "OPR_ID"),),
        "cr_id": (("T", "CR_ID"),),
        "cycle": (("T", "CYCLE"),),
        "seq": (("T", "SEQ"),),
        "try": (("T", "TRY"),),
        "time": (("T", "TIME"),),
        "journal_type": (("J",),),
    },
    "journaldata_mestodcs": {
        "result_code": (("S", "RESULT_CODE"),),
        "result_text": (("S", "RESULT_TEXT"),),
        "lmes_ret_val": (("S", "RET_VAL"),),
        "lmes_ret_text": (("S", "RET_TEXT"),),
    },
    "statechange_dcstomes": {
        "opr_id": (("T", "OPR_ID"),),
        "cr_id": (("T", "CR_ID"),),
        "cycle": (("T", "CYCLE"),),
        "seq": (("T", "SEQ"),),
        "try": (("T", "TRY"),),
        "time": (("T", "TIME"),),
        "state_no": (("STATE_NO",), ("T", "STATE_NO")),
    },
    "statechange_mestodcs": {
        "result_code": (("S", "RESULT_CODE"),),
        "result_text": (("S", "RESULT_TEXT"),),
        "lmes_ret_val": (("S", "RET_VAL"),),
        "lmes_ret_text": (("S", "RET_TEXT"),),
    },
    "recipe_mestodcs": {
        "opr_id": (("C", "OPR_ID"),),
        "cr_id": (("C", "CR_ID"),),
        "cycle": (("C", "CYCLE"),),
    },
    "recipe_dcstomes": {
        "result_code": (("C", "RESULT_CODE"),),
    },
}

_OPTIONAL_PARAMETER_RECORD_FIELDS: dict[str, set[str]] = {
    "acssignofftype": {"meaning"},
}


def _cf(value: str) -> str:
    return value.casefold()


def _split_path(path: str) -> list[str]:
    return [segment.strip() for segment in path.split(".") if segment.strip()]


def _normalize_group_name(group: str | None) -> str | None:
    if not group:
        return None
    return _cf(group)


def _path_has_token(path_segments: list[str], token: str) -> bool:
    wanted = _cf(token)
    return any(_cf(segment) == wanted for segment in path_segments)


def _segment_matches_suffix(actual: str, expected: str) -> bool:
    actual_cf = _cf(actual)
    expected_cf = _cf(expected)
    return actual_cf == expected_cf or actual_cf.endswith(f"_{expected_cf}")


def _path_endswith(path_segments: list[str], suffix: tuple[str, ...]) -> bool:
    if len(path_segments) < len(suffix):
        return False
    tail = path_segments[-len(suffix) :]
    return all(_segment_matches_suffix(actual, expected) for actual, expected in zip(tail, suffix, strict=False))


def _unit_family(unit_name: str) -> str:
    trimmed = re.sub(r"[A-Za-z]+$", "", unit_name)
    return trimmed or unit_name


def _resolve_unit_type_label(
    base_picture: BasePicture,
    unit_name: str,
    entries: list[ICFEntry],
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
) -> tuple[str, str]:
    family = _unit_family(unit_name)
    fallback = (f"family:{_cf(family)}", f"family {family}")

    for entry in entries:
        _program, path = _extract_icf_sattline_ref(entry.value)
        if path is None:
            continue
        path_segments = _split_path(path)
        for index, segment in enumerate(path_segments):
            if _cf(segment) != _cf(unit_name):
                continue
            try:
                resolved = resolve_module_by_strict_path(
                    base_picture,
                    ".".join(path_segments[: index + 1]),
                    moduletype_index=moduletype_index,
                )
            except ValueError:
                continue

            if isinstance(resolved.node, ModuleTypeInstance):
                label = resolved.node.moduletype_name
                return (f"moduletype:{_cf(label)}", label)
            if isinstance(resolved.node, SingleModule | FrameModule):
                return (f"family:{_cf(family)}", f"family {family}")

    return fallback


def _summarize_signature_diff(
    reference: tuple[tuple[str, str, str, str], ...], current: tuple[tuple[str, str, str, str], ...]
) -> str:
    reference_set = set(reference)
    current_set = set(current)
    parts: list[str] = []
    missing = reference_set - current_set
    extra = current_set - reference_set
    if missing:
        parts.append(f"missing {len(missing)} entries")
    if extra:
        parts.append(f"extra {len(extra)} entries")
    if not parts and len(reference) != len(current):
        parts.append(f"entry count {len(current)} != {len(reference)}")
    return "; ".join(parts) or "entry ordering differs"


def parse_icf_file(file_path: Path) -> list[ICFEntry]:
    """Parse a .icf file into key/value entries with section and line number info."""
    entries: list[ICFEntry] = []
    section: str | None = None
    unit: str | None = None
    journal: str | None = None
    group: str | None = None

    raw_bytes = file_path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = raw_bytes.decode("cp1252")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1", errors="replace")

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue

        header_match = _ICF_HEADER_RE.match(line)
        if header_match:
            tag = header_match.group("tag").strip()
            label = (header_match.group("label") or "").strip() or None
            section = f"{tag} {label}".strip() if label else tag
            tag_key = _cf(tag)
            if tag_key == "unit":
                unit = label
                journal = None
                group = None
            elif tag_key == "journal":
                journal = label
                group = None
            elif tag_key == "group":
                group = label
            else:
                journal = None
                group = None
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        entries.append(
            ICFEntry(
                file_path=file_path,
                line_no=idx,
                section=section,
                key=key.strip(),
                value=value.strip(),
                unit=unit,
                journal=journal,
                group=group,
            )
        )

    return entries


def _extract_icf_sattline_ref(value: str) -> tuple[str | None, str | None]:
    """Extract (program, path) from an ICF value string."""
    match = _ICF_REF_RE.match(value.strip())
    if not match:
        return None, None
    program = match.group("program").strip()
    path = match.group("path").strip()
    if not program or not path:
        return None, None
    return program, path


def _find_variable_in_module_scope(
    module_def: Any,
    base_picture: BasePicture,
    var_name: str,
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
    *,
    current_library: str | None = None,
    current_file: str | None = None,
) -> Variable | None:
    var_key = var_name.casefold()

    if isinstance(module_def, SingleModule):
        for v in module_def.localvariables or []:
            if v.name.casefold() == var_key:
                return v
        for v in module_def.moduleparameters or []:
            if v.name.casefold() == var_key:
                return v
        return None

    if isinstance(module_def, ModuleTypeInstance):
        mt: ModuleTypeDef | None = None
        if moduletype_index is not None:
            matches = moduletype_index.get(module_def.moduletype_name.casefold(), [])
            if len(matches) == 1:
                mt = matches[0]
        if mt is None:
            try:
                mt = resolve_moduletype_def_strict(
                    base_picture,
                    module_def.moduletype_name,
                    current_library=current_library,
                    current_file=current_file,
                )
            except ValueError:
                return None
        for v in mt.localvariables or []:
            if v.name.casefold() == var_key:
                return v
        for v in mt.moduleparameters or []:
            if v.name.casefold() == var_key:
                return v
        return None

    if isinstance(module_def, ModuleTypeDef):
        for v in module_def.localvariables or []:
            if v.name.casefold() == var_key:
                return v
        for v in module_def.moduleparameters or []:
            if v.name.casefold() == var_key:
                return v
        return None

    return None


def _resolve_icf_path(
    base_picture: BasePicture,
    path: str,
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
) -> tuple[ResolvedModulePath | None, Variable | None, list[str]]:
    segments = [s for s in path.split(".") if s]
    if not segments:
        return None, None, []

    for i in range(len(segments), 0, -1):
        module_path = ".".join(segments[:i])
        resolved: ResolvedModulePath | None
        try:
            resolved = resolve_module_by_strict_path(
                base_picture,
                module_path,
                moduletype_index=moduletype_index,
            )
        except ValueError:
            resolved = None

        if resolved is None:
            continue

        if i >= len(segments):
            continue

        var_name = segments[i]
        field_segments = segments[i + 1 :]
        var = _find_variable_in_module_scope(
            resolved.node,
            base_picture,
            var_name,
            moduletype_index=moduletype_index,
            current_library=resolved.current_library,
            current_file=resolved.current_file,
        )
        if var is not None:
            return resolved, var, field_segments

    return None, None, []


def _mark_path_segment(path_segments: list[str], segment_index: int) -> str:
    marked_segments = list(path_segments)
    marked_segments[segment_index] = f">>{marked_segments[segment_index]}<<"
    return ".".join(marked_segments)


def _describe_unresolved_icf_path(
    base_picture: BasePicture,
    path: str,
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
) -> str:
    path_segments = _split_path(path)
    if not path_segments:
        return path

    for prefix_length in range(len(path_segments), 0, -1):
        module_prefix = ".".join(path_segments[:prefix_length])
        try:
            resolved = resolve_module_by_strict_path(
                base_picture,
                module_prefix,
                moduletype_index=moduletype_index,
            )
        except ValueError:
            continue

        if prefix_length >= len(path_segments):
            return f"{_mark_path_segment(path_segments, len(path_segments) - 1)}; resolved to module path {resolved.display_path_str}"

        failing_segment = path_segments[prefix_length]
        variable = _find_variable_in_module_scope(
            resolved.node,
            base_picture,
            failing_segment,
            moduletype_index=moduletype_index,
            current_library=resolved.current_library,
            current_file=resolved.current_file,
        )
        if variable is None:
            marked_path = _mark_path_segment(path_segments, prefix_length)
            try:
                resolve_module_by_strict_path(
                    base_picture,
                    ".".join(path_segments[: prefix_length + 1]),
                    moduletype_index=moduletype_index,
                )
            except ValueError as exc:
                return f"{marked_path}; {exc}"
            return f"{marked_path}; variable {failing_segment!r} not found under module {resolved.display_path_str}"

        marked_index = min(prefix_length + 1, len(path_segments) - 1)
        return (
            f"{_mark_path_segment(path_segments, marked_index)}; unresolved after variable {variable.name!r} "
            f"under module {resolved.display_path_str}"
        )

    for prefix_length in range(1, len(path_segments) + 1):
        try:
            resolve_module_by_strict_path(
                base_picture,
                ".".join(path_segments[:prefix_length]),
                moduletype_index=moduletype_index,
            )
        except ValueError as exc:
            return f"{_mark_path_segment(path_segments, prefix_length - 1)}; {exc}"

    return path


def _validate_field_path(
    type_graph: TypeGraph,
    root_var: Variable,
    field_segments: list[str],
) -> tuple[bool, str | None]:
    if not field_segments:
        if isinstance(root_var.datatype, Simple_DataType):
            return True, None
        return (
            False,
            f"non-simple datatype {root_var.datatype} referenced without field path",
        )

    current_type: Simple_DataType | str | None = root_var.datatype
    for field in field_segments:
        if isinstance(current_type, Simple_DataType):
            return False, f"datatype {current_type.value} has no field {field!r}"

        if current_type is None:
            return False, f"unknown datatype for field {field!r}"

        field_def = type_graph.field(str(current_type), field)
        if field_def is None:
            return False, f"field {field!r} not found in datatype {current_type}"

        current_type = field_def.datatype

    if isinstance(current_type, Simple_DataType):
        return True, None
    return (
        False,
        f"non-simple datatype {current_type} referenced without field path",
    )


def _resolve_leaf_datatype(
    type_graph: TypeGraph,
    root_var: Variable,
    field_segments: list[str],
) -> Simple_DataType | str | None:
    current_type: Simple_DataType | str | None = root_var.datatype
    for field in field_segments:
        if isinstance(current_type, Simple_DataType):
            return None
        if current_type is None:
            return None
        field_def = type_graph.field(str(current_type), field)
        if field_def is None:
            return None
        current_type = field_def.datatype
    return current_type


def _resolve_record_datatype(
    type_graph: TypeGraph,
    root_datatype: Simple_DataType | str | None,
    field_segments: list[str],
) -> str | None:
    current_type: Simple_DataType | str | None = root_datatype
    for field in field_segments:
        if isinstance(current_type, Simple_DataType):
            return None
        if current_type is None:
            return None
        field_def = type_graph.field(str(current_type), field)
        if field_def is None:
            return None
        current_type = field_def.datatype

    if isinstance(current_type, Simple_DataType) or current_type is None:
        return None
    return str(current_type)


def _validate_entry_context(entry: ICFEntry, path: str) -> list[ICFValidationIssue]:
    issues: list[ICFValidationIssue] = []
    path_segments = _split_path(path)

    if entry.unit and not _path_has_token(path_segments, entry.unit):
        issues.append(
            ICFValidationIssue(
                entry=entry,
                reason="unit tag mismatch",
                detail=f"expected unit {entry.unit} in path",
            )
        )

    normalized_group = _normalize_group_name(entry.group)
    group_rules = _GROUP_SUFFIX_RULES.get(normalized_group or "", {})
    expected_suffixes = group_rules.get(_cf(entry.key), ())
    if expected_suffixes and not any(_path_endswith(path_segments, suffix) for suffix in expected_suffixes):
        expected = " or ".join(".".join(suffix) for suffix in expected_suffixes)
        issues.append(
            ICFValidationIssue(
                entry=entry,
                reason="group tag mismatch",
                detail=f"expected suffix {expected}",
            )
        )

    return issues


def _validate_parameter_record_completeness(
    type_graph: TypeGraph,
    resolved_entries: list[ICFResolvedEntry],
) -> list[ICFValidationIssue]:
    issues: list[ICFValidationIssue] = []
    grouped: dict[
        tuple[str | None, str | None, str | None, tuple[str, ...], str, tuple[str, ...], str], list[ICFResolvedEntry]
    ] = {}

    for resolved in resolved_entries:
        if _normalize_group_name(resolved.entry.group) != "journaldata_parameters":
            continue
        if isinstance(resolved.root_datatype, Simple_DataType):
            continue
        if resolved.root_datatype is not None and not isinstance(resolved.root_datatype, str):
            continue
        if not resolved.field_path:
            continue
        field_segments = [segment for segment in resolved.field_path.split(".") if segment]
        if not field_segments:
            continue
        record_path = tuple(field_segments[:-1])
        datatype_name = _resolve_record_datatype(type_graph, resolved.root_datatype, list(record_path))
        if datatype_name is None:
            continue
        record = type_graph.record(datatype_name)
        if record is None:
            continue
        key = (
            resolved.entry.unit,
            resolved.entry.journal,
            resolved.entry.group,
            tuple(resolved.module_path),
            resolved.variable_name,
            record_path,
            datatype_name,
        )
        grouped.setdefault(key, []).append(resolved)

    grouped_items = list(grouped.items())

    for (unit, journal, group, module_path, variable_name, record_path, datatype_name), entries in grouped_items:
        record = type_graph.record(datatype_name)
        if record is None:
            continue
        expected_fields = {field.name: _cf(field.name) for field in record.fields_by_key.values()}
        optional_fields = _OPTIONAL_PARAMETER_RECORD_FIELDS.get(_cf(datatype_name), set())
        present = {_cf(resolved.leaf_name) for resolved in entries}
        for (
            other_unit,
            other_journal,
            other_group,
            other_module_path,
            other_variable_name,
            other_record_path,
            _other_datatype,
        ), _other_entries in grouped_items:
            if other_unit != unit or other_journal != journal or other_group != group:
                continue
            if other_module_path != module_path or other_variable_name != variable_name:
                continue
            if len(other_record_path) <= len(record_path):
                continue
            if other_record_path[: len(record_path)] != record_path:
                continue
            present.add(_cf(other_record_path[len(record_path)]))
        missing = [name for name, key in expected_fields.items() if key not in present and key not in optional_fields]
        if missing:
            record_label = variable_name if not record_path else f"{variable_name}.{'.'.join(record_path)}"
            issues.append(
                ICFValidationIssue(
                    entry=entries[0].entry,
                    reason="missing journal parameter fields",
                    detail=f"record {record_label} missing {len(missing)} fields: {', '.join(sorted(missing))}",
                )
            )

    return issues


def _validate_unit_structure(
    base_picture: BasePicture,
    entries: list[ICFEntry],
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
) -> list[ICFValidationIssue]:
    issues: list[ICFValidationIssue] = []
    unit_entries: dict[str, list[ICFEntry]] = {}
    for entry in entries:
        if entry.unit:
            unit_entries.setdefault(entry.unit, []).append(entry)

    typed_units: dict[str, dict[str, Any]] = {}
    for unit_name, unit_specific_entries in unit_entries.items():
        type_key, type_label = _resolve_unit_type_label(
            base_picture,
            unit_name,
            unit_specific_entries,
            moduletype_index=moduletype_index,
        )
        bucket = typed_units.setdefault(type_key, {"label": type_label, "units": []})
        bucket["units"].append(unit_name)

    for bucket in typed_units.values():
        type_label = str(bucket["label"])
        units = sorted(bucket["units"])
        if len(units) < 2:
            continue
        reference_unit = units[0]
        signatures: dict[str, tuple[tuple[str, str, str, str], ...]] = {}

        for unit_name in units:
            signature: list[tuple[str, str, str, str]] = []
            for entry in unit_entries[unit_name]:
                program, path = _extract_icf_sattline_ref(entry.value)
                if path is None:
                    normalized_value = entry.value
                else:
                    normalized_segments = [
                        "<UNIT>" if entry.unit and _cf(segment) == _cf(entry.unit) else segment
                        for segment in _split_path(path)
                    ]
                    normalized_path = ".".join(normalized_segments)
                    normalized_value = f"{program}:{normalized_path}" if program else normalized_path
                signature.append((entry.journal or "", entry.group or "", _cf(entry.key), normalized_value))
            signatures[unit_name] = tuple(signature)

        reference_signature = signatures[reference_unit]
        for unit_name in units[1:]:
            current_signature = signatures[unit_name]
            if current_signature == reference_signature:
                continue
            issues.append(
                ICFValidationIssue(
                    entry=unit_entries[unit_name][0],
                    reason="unit structure drift",
                    detail=(
                        f"unit type {type_label} differs from {reference_unit}: "
                        f"{_summarize_signature_diff(reference_signature, current_signature)}"
                    ),
                )
            )

    return issues


def validate_icf_entries_against_program(
    base_picture: BasePicture,
    entries: list[ICFEntry],
    expected_program: str,
    debug: bool = False,
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
) -> ICFValidationReport:
    type_graph = TypeGraph.from_basepicture(base_picture)
    issues: list[ICFValidationIssue] = []
    resolved_entries: list[ICFResolvedEntry] = []
    validated = 0
    valid = 0
    skipped = 0

    for entry in entries:
        program, path = _extract_icf_sattline_ref(entry.value)
        if program is None or path is None:
            skipped += 1
            continue

        if program.casefold() != expected_program.casefold():
            issues.append(
                ICFValidationIssue(
                    entry=entry,
                    reason="program mismatch",
                    detail=f"expected {expected_program}",
                )
            )
            continue

        issues.extend(_validate_entry_context(entry, path))
        validated += 1

        resolved, var, field_segments = _resolve_icf_path(
            base_picture,
            path,
            moduletype_index=moduletype_index,
        )
        if resolved is None or var is None:
            issues.append(
                ICFValidationIssue(
                    entry=entry,
                    reason="unresolved path",
                    detail=_describe_unresolved_icf_path(
                        base_picture,
                        path,
                        moduletype_index=moduletype_index,
                    ),
                )
            )
            continue

        ok, detail = _validate_field_path(type_graph, var, field_segments)
        if not ok:
            issues.append(
                ICFValidationIssue(
                    entry=entry,
                    reason="invalid field path",
                    detail=detail,
                )
            )
            continue

        leaf_datatype = _resolve_leaf_datatype(type_graph, var, field_segments)
        if leaf_datatype is None:
            issues.append(
                ICFValidationIssue(
                    entry=entry,
                    reason="invalid field path",
                    detail=detail,
                )
            )
            continue

        valid += 1
        resolved_entries.append(
            ICFResolvedEntry(
                entry=entry,
                module_path=list(resolved.path),
                variable_name=var.name,
                root_datatype=var.datatype,
                field_path=".".join(field_segments) or None,
                leaf_name=field_segments[-1] if field_segments else var.name,
                datatype=leaf_datatype,
            )
        )

    issues.extend(_validate_parameter_record_completeness(type_graph, resolved_entries))
    issues.extend(_validate_unit_structure(base_picture, entries, moduletype_index=moduletype_index))

    return ICFValidationReport(
        icf_file=entries[0].file_path if entries else Path(""),
        program_name=expected_program,
        total_entries=len(entries),
        validated_entries=validated,
        valid_entries=valid,
        skipped_entries=skipped,
        issues=issues,
        resolved_entries=resolved_entries,
    )
