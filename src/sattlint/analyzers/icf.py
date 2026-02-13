from __future__ import annotations
import re
from pathlib import Path
from typing import Any

from ..models.ast_model import (
    BasePicture,
    ModuleTypeDef,
    SingleModule,
    ModuleTypeInstance,
    Variable,
    Simple_DataType,
)
from ..resolution.common import (
    resolve_moduletype_def_strict,
    resolve_module_by_strict_path,
    ResolvedModulePath,
)
from ..resolution.type_graph import TypeGraph
from ..reporting.icf_report import (
    ICFEntry,
    ICFValidationIssue,
    ICFValidationReport,
)


_ICF_REF_RE = re.compile(r"(?:^|.*?)(?:[A-Za-z]::)?(?P<program>[^:]+):(?P<path>.+)$")


def parse_icf_file(file_path: Path) -> list[ICFEntry]:
    """Parse a .icf file into key/value entries with section and line number info."""
    entries: list[ICFEntry] = []
    section: str | None = None

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

        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip() or None
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
                mt = resolve_moduletype_def_strict(base_picture, module_def.moduletype_name)
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
        try:
            resolved = resolve_module_by_strict_path(
                base_picture,
                module_path,
                moduletype_index=moduletype_index,
            )
        except Exception:
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
        )
        if var is not None:
            return resolved, var, field_segments

    return None, None, []


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


def validate_icf_entries_against_program(
    base_picture: BasePicture,
    entries: list[ICFEntry],
    expected_program: str,
    debug: bool = False,
    moduletype_index: dict[str, list[ModuleTypeDef]] | None = None,
) -> ICFValidationReport:
    type_graph = TypeGraph.from_basepicture(base_picture)
    issues: list[ICFValidationIssue] = []
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
                    detail=path,
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

        valid += 1

    return ICFValidationReport(
        icf_file=entries[0].file_path if entries else Path(""),
        program_name=expected_program,
        total_entries=len(entries),
        validated_entries=validated,
        valid_entries=valid,
        skipped_entries=skipped,
        issues=issues,
    )
