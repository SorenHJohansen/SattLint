from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sattlint.parser_api import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    ScalarDatatype,
    SingleModule,
    Variable,
)

from ...reporting.icf_report import (
    ICFDriftCountMismatch,
    ICFDriftEntry,
    ICFDriftEntryChange,
    ICFDriftOrderingMismatch,
    ICFEntry,
    ICFResolvedEntry,
    ICFSkippedEntry,
    ICFUnitDrift,
    ICFValidationIssue,
    ICFValidationReport,
    summarize_icf_unit_drift,
)
from ...resolution.common import (
    ResolvedModulePath,
    resolve_module_by_strict_path,
    resolve_moduletype_def_strict,
)
from ...resolution.type_graph import AmbiguousRecordError, TypeGraph, resolve_record
from ._icf_datatype_resolution import resolve_leaf_datatype, resolve_record_datatype
from ._icf_file_io import (
    decode_icf_text as _decode_icf_text_impl,
)
from ._icf_file_io import (
    extract_icf_sattline_ref as _extract_icf_sattline_ref,
)
from ._icf_file_io import (
    extract_icf_value_prefix as _extract_icf_value_prefix,
)
from ._icf_file_io import (
    is_placeholder_icf_value as _is_placeholder_icf_value,
)
from ._icf_file_io import (
    parse_icf_file as _parse_icf_file,
)

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

_IDENTITY_GROUP_FIELDS: dict[str, tuple[str, ...]] = {
    "journaldata_dcstomes": ("OPR_ID", "CR_ID", "CYCLE", "SEQ", "TRY", "TIME"),
    "journaldata_mestodcs": ("RESULT_CODE", "RESULT_TEXT", "LMES_RET_VAL", "LMES_RET_TEXT"),
}


@dataclass
class _UnitTypeBucket:
    """The units that share one resolved unit type."""

    label: str
    units: list[str]


_decode_icf_text = _decode_icf_text_impl
parse_icf_file = _parse_icf_file


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


_DRIFT_PREVIEW_LIMIT = 3
type _SignatureEntry = tuple[str, str, str, str, str]
type _Signature = tuple[_SignatureEntry, ...]


def _drift_entry(entry: _SignatureEntry) -> ICFDriftEntry:
    operation, journal, group, key, value = entry
    return ICFDriftEntry(operation=operation, journal=journal, group=group, key=key, value=value)


def _signature_drift_parts(
    reference: _Signature,
    current: _Signature,
) -> tuple[tuple[ICFDriftEntryChange, ...], ICFDriftCountMismatch | None, ICFDriftOrderingMismatch | None]:
    reference_set = set(reference)
    current_set = set(current)
    missing = reference_set - current_set
    extra = current_set - reference_set

    changes: list[ICFDriftEntryChange] = []
    if missing:
        changes.append(
            ICFDriftEntryChange(
                kind="missing",
                count=len(missing),
                entries=tuple(_drift_entry(entry) for entry in sorted(missing)[:_DRIFT_PREVIEW_LIMIT]),
            )
        )
    if extra:
        changes.append(
            ICFDriftEntryChange(
                kind="extra",
                count=len(extra),
                entries=tuple(_drift_entry(entry) for entry in sorted(extra)[:_DRIFT_PREVIEW_LIMIT]),
            )
        )
    if changes:
        return tuple(changes), None, None
    if len(reference) != len(current):
        return (), ICFDriftCountMismatch(current=len(current), reference=len(reference)), None

    for index, (expected_entry, current_entry) in enumerate(zip(reference, current, strict=False), start=1):
        if expected_entry == current_entry:
            continue
        return (
            (),
            None,
            ICFDriftOrderingMismatch(
                position=index,
                expected=_drift_entry(expected_entry),
                found=_drift_entry(current_entry),
            ),
        )

    return (), None, None


def _build_unit_drift(
    current_unit: str,
    unit_type: str,
    reference_unit: str,
    reference: _Signature,
    current: _Signature,
) -> ICFUnitDrift:
    entry_changes, count_mismatch, ordering = _signature_drift_parts(reference, current)
    return ICFUnitDrift(
        current_unit=current_unit,
        unit_type=unit_type,
        reference_unit=reference_unit,
        entry_changes=entry_changes,
        count_mismatch=count_mismatch,
        ordering=ordering,
    )


def _find_variable_in_module_scope(
    module_def: BasePicture | SingleModule | FrameModule | ModuleTypeDef | ModuleTypeInstance,
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
    *,
    library: str | None = None,
) -> tuple[bool, str | None]:
    if not field_segments:
        if isinstance(root_var.datatype, ScalarDatatype):
            return True, None
        return (
            False,
            f"non-simple datatype {root_var.datatype} referenced without field path",
        )

    current_type: ScalarDatatype | str | None = root_var.datatype
    field_library = library
    for field in field_segments:
        if isinstance(current_type, ScalarDatatype):
            return False, f"datatype {current_type.value} has no field {field!r}"

        ambiguity: list[AmbiguousRecordError] = []
        record = resolve_record(
            type_graph,
            str(current_type),
            library=field_library,
            on_ambiguity=ambiguity.append,
        )
        if ambiguity:
            return False, str(ambiguity[0])
        field_def = record.fields_by_key.get(field.casefold()) if record is not None else None
        if record is None or field_def is None:
            return False, f"field {field!r} not found in datatype {current_type}"

        current_type = field_def.datatype
        field_library = record.library

    if isinstance(current_type, ScalarDatatype):
        return True, None
    return (
        False,
        f"non-simple datatype {current_type} referenced without field path",
    )


def _resolve_canonical_leaf_name(
    type_graph: TypeGraph,
    root_var: Variable,
    field_segments: list[str],
    *,
    library: str | None = None,
) -> str | None:
    if not field_segments:
        return root_var.name

    current_type: ScalarDatatype | str | None = root_var.datatype
    resolved_name: str | None = None
    field_library = library
    for field in field_segments:
        if isinstance(current_type, ScalarDatatype):
            return None

        record = resolve_record(type_graph, str(current_type), library=field_library)
        field_def = record.fields_by_key.get(field.casefold()) if record is not None else None
        if record is None or field_def is None:
            return None

        resolved_name = field_def.name
        current_type = field_def.datatype
        field_library = record.library

    return resolved_name


def _validate_entry_reference_case(
    entry: ICFEntry,
    *,
    type_graph: TypeGraph,
    root_var: Variable,
    variable_name: str,
    field_segments: list[str],
    library: str | None = None,
) -> ICFValidationIssue | None:
    reference_name = field_segments[-1] if field_segments else variable_name
    resolved_name = _resolve_canonical_leaf_name(type_graph, root_var, field_segments, library=library)
    if resolved_name is None or reference_name == resolved_name or _cf(reference_name) != _cf(resolved_name):
        return None
    return ICFValidationIssue(
        entry=entry,
        reason="reference case mismatch",
        detail=f"resolved SattLine name is {resolved_name!r}, but ICF reference uses {reference_name!r}",
    )


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


def _validate_value_prefix_consistency(entries: list[ICFEntry]) -> ICFValidationIssue | None:
    prefix_letters: set[str] = set()
    first_prefixed_entry: ICFEntry | None = None

    for entry in entries:
        prefix = _extract_icf_value_prefix(entry.value)
        if prefix is None:
            continue
        if first_prefixed_entry is None:
            first_prefixed_entry = entry
        prefix_letters.add(prefix)

    if len(prefix_letters) < 2 or first_prefixed_entry is None:
        return None

    prefix_list = ", ".join(f"{prefix}::" for prefix in sorted(prefix_letters))
    return ICFValidationIssue(
        entry=first_prefixed_entry,
        reason="mixed ICF value prefix letters",
        detail=f"found multiple ICF value prefix letters in file: {prefix_list}",
    )


def _validate_journal_identity_groups(entries: list[ICFEntry]) -> list[ICFValidationIssue]:
    """Report an incomplete MES identity group.

    ``JournalData_DCStoMES`` and ``JournalData_MEStoDCS`` are fixed-key
    identity groups: once a group maps any of its keys it must map all of
    them. ``JOURNAL_TYPE`` is not required because real configurations omit it.
    A group that is absent is never a finding, and ``JournalData_Parameters``
    is a deliberate per-journal subset, so it is never checked for
    completeness.
    """
    grouped: dict[tuple[str | None, str | None, str], list[ICFEntry]] = {}
    for entry in entries:
        group = _normalize_group_name(entry.group)
        if group is None or group not in _IDENTITY_GROUP_FIELDS:
            continue
        grouped.setdefault((entry.unit, entry.journal, group), []).append(entry)

    issues: list[ICFValidationIssue] = []
    for (unit, journal, group), group_entries in grouped.items():
        present = {_cf(entry.key) for entry in group_entries}
        missing = [name for name in _IDENTITY_GROUP_FIELDS[group] if _cf(name) not in present]
        if not missing:
            continue
        label = journal or unit or group_entries[0].group or group
        issues.append(
            ICFValidationIssue(
                entry=group_entries[0],
                reason="missing journal parameter fields",
                detail=(f"group {group_entries[0].group} for {label} is missing identity keys: " + ", ".join(missing)),
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

    typed_units: dict[str, _UnitTypeBucket] = {}
    for unit_name, unit_specific_entries in unit_entries.items():
        type_key, type_label = _resolve_unit_type_label(
            base_picture,
            unit_name,
            unit_specific_entries,
            moduletype_index=moduletype_index,
        )
        typed_units.setdefault(type_key, _UnitTypeBucket(label=type_label, units=[])).units.append(unit_name)

    for bucket in typed_units.values():
        type_label = bucket.label
        units = sorted(bucket.units)
        if len(units) < 2:
            continue
        reference_unit = units[0]
        signatures: dict[str, tuple[tuple[str, str, str, str, str], ...]] = {}

        for unit_name in units:
            signature: list[tuple[str, str, str, str, str]] = []
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
                signature.append(
                    (entry.operation or "", entry.journal or "", entry.group or "", _cf(entry.key), normalized_value)
                )
            signatures[unit_name] = tuple(signature)

        reference_signature = signatures[reference_unit]
        for unit_name in units[1:]:
            current_signature = signatures[unit_name]
            if current_signature == reference_signature:
                continue
            drift = _build_unit_drift(
                current_unit=unit_name,
                unit_type=type_label,
                reference_unit=reference_unit,
                reference=reference_signature,
                current=current_signature,
            )
            issues.append(
                ICFValidationIssue(
                    entry=unit_entries[unit_name][0],
                    reason="unit structure drift",
                    detail=summarize_icf_unit_drift(drift),
                    drift=drift,
                )
            )

    return issues


__all__ = [
    "parse_icf_file",
    "resolve_leaf_datatype",
    "resolve_record_datatype",
    "validate_icf_entries_against_program",
]


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
    skipped_details: list[ICFSkippedEntry] = []
    validated = 0
    valid = 0
    skipped = 0

    for entry in entries:
        if _is_placeholder_icf_value(entry.value):
            skipped_details.append(
                ICFSkippedEntry(
                    entry=entry,
                    reason="placeholder value",
                    detail="matches placeholder pattern X::.",
                )
            )
            skipped += 1
            continue

        program, path = _extract_icf_sattline_ref(entry.value)
        if program is None or path is None:
            skipped_details.append(
                ICFSkippedEntry(
                    entry=entry,
                    reason="unparseable SattLine reference",
                    detail="expected Program:Path value",
                )
            )
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

        ok, detail = _validate_field_path(type_graph, var, field_segments, library=resolved.current_library)
        if not ok:
            issues.append(
                ICFValidationIssue(
                    entry=entry,
                    reason="invalid field path",
                    detail=detail,
                )
            )
            continue

        leaf_datatype = resolve_leaf_datatype(
            type_graph,
            var,
            field_segments,
            library=resolved.current_library,
        )
        if leaf_datatype is None:
            issues.append(
                ICFValidationIssue(
                    entry=entry,
                    reason="invalid field path",
                    detail=detail,
                )
            )
            continue

        resolved_leaf_name = _resolve_canonical_leaf_name(
            type_graph,
            var,
            field_segments,
            library=resolved.current_library,
        )
        resolved_entries.append(
            ICFResolvedEntry(
                entry=entry,
                module_path=list(resolved.path),
                variable_name=var.name,
                root_datatype=var.datatype,
                field_path=".".join(field_segments) or None,
                leaf_name=resolved_leaf_name or (field_segments[-1] if field_segments else var.name),
                datatype=leaf_datatype,
                current_library=resolved.current_library,
            )
        )

        key_case_issue = _validate_entry_reference_case(
            entry,
            type_graph=type_graph,
            root_var=var,
            variable_name=var.name,
            field_segments=field_segments,
            library=resolved.current_library,
        )
        if key_case_issue is not None:
            issues.append(key_case_issue)
            continue

        valid += 1

    issues.extend(_validate_journal_identity_groups(entries))
    issues.extend(_validate_unit_structure(base_picture, entries, moduletype_index=moduletype_index))
    prefix_consistency_issue = _validate_value_prefix_consistency(entries)
    if prefix_consistency_issue is not None:
        issues.append(prefix_consistency_issue)

    return ICFValidationReport(
        icf_file=entries[0].file_path if entries else Path(""),
        program_name=expected_program,
        total_entries=len(entries),
        validated_entries=validated,
        valid_entries=valid,
        skipped_entries=skipped,
        issues=issues,
        resolved_entries=resolved_entries,
        skipped_details=skipped_details,
    )
