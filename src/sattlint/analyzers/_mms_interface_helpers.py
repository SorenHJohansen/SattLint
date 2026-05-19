"""Shared helpers for MMS interface inventory analysis."""

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Simple_DataType,
    Variable,
)

from ..grammar import constants as const
from ..reporting.icf_report import ICFEntry
from ..resolution.common import find_var_in_scope, varname_base, varname_full
from ..resolution.type_graph import TypeGraph
from .icf import parse_icf_file, validate_icf_entries_against_program

_TAG_PARAMETER_NAMES: tuple[str, ...] = (
    "remotevarname",
    "tag",
    "name",
)
_NUMERIC_TAG_RE = re.compile(r"^\d+$")
_TAG_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")


def _datatype_label(datatype: Simple_DataType | str | None) -> str | None:
    if datatype is None:
        return None
    if isinstance(datatype, Simple_DataType):
        return datatype.value
    return str(datatype)


def _normalize_external_tag(tag: str | None) -> str | None:
    if not isinstance(tag, str):
        return None
    cleaned = tag.strip()
    if not cleaned or _NUMERIC_TAG_RE.fullmatch(cleaned):
        return None
    return cleaned.casefold()


def _tag_family_key(tag: str | None) -> str | None:
    if not isinstance(tag, str):
        return None
    cleaned = tag.strip()
    if not cleaned or _NUMERIC_TAG_RE.fullmatch(cleaned):
        return None

    normalized = cleaned.replace(".", "_").replace("-", "_").replace(" ", "_")
    tokens: list[str] = []
    for chunk in normalized.split("_"):
        chunk = chunk.strip()
        if not chunk:
            continue
        matches = _TAG_TOKEN_RE.findall(chunk)
        if matches:
            tokens.extend(match.casefold() for match in matches)
            continue
        tokens.append(chunk.casefold())

    if not tokens:
        return None
    return "|".join(tokens)


def _build_moduletype_index(base_picture: BasePicture) -> dict[str, list[ModuleTypeDef]]:
    index: dict[str, list[ModuleTypeDef]] = {}
    for moduletype in base_picture.moduletype_defs or []:
        index.setdefault(moduletype.name.casefold(), []).append(moduletype)
    return index


def _program_name_candidates(base_picture: BasePicture) -> list[str]:
    candidates: list[str] = []
    origin_file = getattr(base_picture, "origin_file", None)
    if isinstance(origin_file, str) and origin_file.strip():
        stem = Path(origin_file).stem.strip()
        if stem:
            candidates.append(stem)

    header_name = base_picture.header.name.strip()
    if header_name and header_name.casefold() not in {name.casefold() for name in candidates}:
        candidates.append(header_name)

    return candidates or [base_picture.header.name]


def _load_icf_entries_from_config(
    base_picture: BasePicture,
    config: dict[str, Any] | None,
) -> list[ICFEntry]:
    if not isinstance(config, dict):
        return []

    icf_dir_raw = str(config.get("icf_dir", "") or "").strip()
    if not icf_dir_raw:
        return []

    icf_dir = Path(icf_dir_raw)
    if not icf_dir.exists() or not icf_dir.is_dir():
        return []

    for name in _program_name_candidates(base_picture):
        candidate = icf_dir / f"{name}.icf"
        if candidate.exists() and candidate.is_file():
            return parse_icf_file(candidate)

    return []


def _find_parameter_mapping(
    mappings: list[ParameterMapping] | None,
    parameter_name: str,
) -> ParameterMapping | None:
    wanted = parameter_name.casefold()
    for mapping in mappings or []:
        target_name = varname_base(mapping.target)
        if target_name == wanted:
            return mapping
    return None


def _find_variable(
    variables: list[Variable] | None,
    wanted_name: str,
) -> Variable | None:
    wanted = wanted_name.casefold()
    for variable in variables or []:
        if variable.name.casefold() == wanted:
            return variable
    return None


def _resolve_string_parameter(
    base_picture: BasePicture,
    module_path: list[str],
    inst: ModuleTypeInstance,
    mt_def: ModuleTypeDef | None,
    parameter_name: str,
) -> str | None:
    mapping = _find_parameter_mapping(inst.parametermappings, parameter_name)
    if mapping is not None:
        if mapping.source_type == const.KEY_VALUE and isinstance(mapping.source_literal, str):
            value = mapping.source_literal.strip()
            return value or None

        full_ref = varname_full(mapping.source)
        if full_ref and ":" not in full_ref:
            base_name = full_ref.split(".", 1)[0]
            variable = find_var_in_scope(base_picture, module_path, base_name)
            if variable is not None and isinstance(variable.init_value, str):
                value = variable.init_value.strip()
                return value or None
        return None

    if mt_def is None:
        return None

    parameter = _find_variable(mt_def.moduleparameters, parameter_name)
    if parameter is None or not isinstance(parameter.init_value, str):
        return None

    value = parameter.init_value.strip()
    return value or None


def _extract_external_tag(
    base_picture: BasePicture,
    module_path: list[str],
    inst: ModuleTypeInstance,
    mt_def: ModuleTypeDef | None,
) -> str | None:
    available_names: set[str] = (
        {variable.name.casefold() for variable in (mt_def.moduleparameters or [])} if mt_def is not None else set()
    )
    for mapping in inst.parametermappings or []:
        target_name = varname_base(mapping.target)
        if target_name:
            available_names.add(target_name)

    for parameter_name in _TAG_PARAMETER_NAMES:
        if parameter_name not in available_names:
            continue
        value = _resolve_string_parameter(
            base_picture,
            module_path,
            inst,
            mt_def,
            parameter_name,
        )
        if value:
            return value

    return None


def _resolve_source_details(
    base_picture: BasePicture,
    type_graph: TypeGraph,
    module_path: list[str],
    source_variable: str,
) -> tuple[str | None, str | None]:
    if not source_variable:
        return None, None

    base_name = source_variable.split(".", 1)[0]
    field_segments = source_variable.split(".")[1:]
    variable = find_var_in_scope(base_picture, module_path, base_name)
    if variable is None:
        return None, field_segments[-1] if field_segments else None

    current_type: Simple_DataType | str | None = variable.datatype
    leaf_name = variable.name
    for field in field_segments:
        leaf_name = field
        if not isinstance(current_type, str):
            return _datatype_label(current_type), leaf_name

        field_def = type_graph.field(str(current_type), field)
        if field_def is None:
            return None, leaf_name
        current_type = field_def.datatype

    return _datatype_label(current_type), leaf_name


def _best_icf_validation_report(
    base_picture: BasePicture,
    entries: list[ICFEntry],
    moduletype_index: dict[str, list[ModuleTypeDef]],
) -> Any | None:
    best_report = None
    for program_name in _program_name_candidates(base_picture):
        candidate = validate_icf_entries_against_program(
            base_picture,
            entries,
            expected_program=program_name,
            moduletype_index=moduletype_index,
        )
        if best_report is None:
            best_report = candidate
            continue
        if candidate.valid_entries > best_report.valid_entries:
            best_report = candidate
            continue
        if candidate.valid_entries == best_report.valid_entries and len(candidate.issues) < len(best_report.issues):
            best_report = candidate
    return best_report


extract_external_tag = _extract_external_tag
find_parameter_mapping = _find_parameter_mapping
find_variable = _find_variable
normalize_external_tag = _normalize_external_tag
tag_family_key = _tag_family_key


__all__ = [
    "extract_external_tag",
    "find_parameter_mapping",
    "find_variable",
    "normalize_external_tag",
    "tag_family_key",
]
