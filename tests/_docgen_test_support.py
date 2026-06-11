# pyright: reportPrivateUsage=false

import runpy
from pathlib import Path
from typing import Any, cast

import pytest
from docx import Document
from docx.document import Document as DocClass
from openpyxl.worksheet.worksheet import Worksheet

from sattline_parser.grammar import constants as const
from sattline_parser.models.ast_model import (
    BasePicture,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    Variable,
)
from sattlint import config as config_module
from sattlint.docgenerator import configgen
from sattlint.docgenerator.classification import (
    DocumentationClassification,
    DocumentedModule,
    _collect_documented_modules,
    _descendants_of,
    _equals_pattern,
    _has_descendant_marker_match,
    _label_variants,
    _looks_like_equipment_module,
    _looks_like_operation,
    _looks_like_unit_root,
    _looks_like_wrapper_name,
    _marker_anchor,
    _matches_category_heuristic,
    _matches_rule,
    _normalize_requested_values,
    _resolve_instance_moduletype,
    _resolve_scope_paths,
    classify_documentation_structure,
    discover_documentation_unit_candidates,
    document_scope_summary,
)
from sattlint.docgenerator.docgen import (
    DocumentUnit,
    _calculation_rows,
    _communication_rows,
    _configurable_parameter_rows,
    _ensure_styles,
    _entry_variable,
    _entry_variable_text,
    _event_rows,
    _event_table_rows,
    _first_non_empty,
    _format_coord,
    _mapping_source_text,
    _mapping_target_name,
    _message_rows,
    _module_description,
    _pid_controller_rows,
    _prettify_name,
    _render_equipment_module_section,
    _sequence_render_rows,
    _sequence_rows,
    _simple_name_tag_rows,
    _special_logging_rows,
    _state_logic_summary,
    _state_rows,
    _value_text,
    _variable_rows,
    generate_docx,
)


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


def _literal_mapping(target: str, value: object) -> ParameterMapping:
    return ParameterMapping(
        target=target,
        source_type=const.KEY_VALUE,
        is_duration=False,
        is_source_global=False,
        source=None,
        source_literal=value,
    )


def _table_headers(document: DocClass) -> list[list[str]]:
    return [[cell.text.strip() for cell in table.rows[0].cells] for table in document.tables if table.rows]


def _table_text(document: DocClass) -> list[str]:
    return [
        cell.text.strip() for table in document.tables for row in table.rows for cell in row.cells if cell.text.strip()
    ]


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _active_worksheet(workbook: Any) -> Worksheet:
    worksheet = workbook.active
    assert worksheet is not None
    return cast(Worksheet, worksheet)


def _typed_extractor(extractor: Any) -> configgen.SattLineConfigExtractor:
    return cast(configgen.SattLineConfigExtractor, extractor)


def _documented_instance(
    name: str,
    path: tuple[str, ...],
    *,
    moduletype_name: str,
    moduleparameters: list[Variable] | None = None,
    localvariables: list[Variable] | None = None,
    parametermappings: list[ParameterMapping] | None = None,
    modulecode: ModuleCode | None = None,
    resolved_moduletype: ModuleTypeDef | None = None,
) -> DocumentedModule:
    instance = ModuleTypeInstance(
        header=_hdr(name),
        moduletype_name=moduletype_name,
        parametermappings=list(parametermappings or []),
    )
    return DocumentedModule(
        node=instance,
        path=path,
        kind="moduletype_instance",
        current_library="ProjectLib",
        resolved_moduletype=resolved_moduletype,
        moduleparameters=tuple(moduleparameters or []),
        localvariables=tuple(localvariables or []),
        parametermappings=tuple(parametermappings or []),
        modulecode=modulecode,
    )


__all__ = [
    "Any",
    "BasePicture",
    "DocClass",
    "Document",
    "DocumentUnit",
    "DocumentationClassification",
    "DocumentedModule",
    "Equation",
    "FrameModule",
    "ModuleCode",
    "ModuleHeader",
    "ModuleTypeDef",
    "ModuleTypeInstance",
    "ParameterMapping",
    "Path",
    "SFCAlternative",
    "SFCBreak",
    "SFCCodeBlocks",
    "SFCFork",
    "SFCParallel",
    "SFCStep",
    "SFCSubsequence",
    "SFCTransition",
    "SFCTransitionSub",
    "Sequence",
    "SingleModule",
    "Variable",
    "Worksheet",
    "_active_worksheet",
    "_calculation_rows",
    "_collect_documented_modules",
    "_communication_rows",
    "_configurable_parameter_rows",
    "_descendants_of",
    "_documented_instance",
    "_ensure_styles",
    "_entry_variable",
    "_entry_variable_text",
    "_equals_pattern",
    "_event_rows",
    "_event_table_rows",
    "_first_non_empty",
    "_format_coord",
    "_has_descendant_marker_match",
    "_hdr",
    "_label_variants",
    "_literal_mapping",
    "_looks_like_equipment_module",
    "_looks_like_operation",
    "_looks_like_unit_root",
    "_looks_like_wrapper_name",
    "_mapping_source_text",
    "_mapping_target_name",
    "_marker_anchor",
    "_matches_category_heuristic",
    "_matches_rule",
    "_message_rows",
    "_module_description",
    "_normalize_requested_values",
    "_pid_controller_rows",
    "_prettify_name",
    "_render_equipment_module_section",
    "_resolve_instance_moduletype",
    "_resolve_scope_paths",
    "_sequence_render_rows",
    "_sequence_rows",
    "_simple_name_tag_rows",
    "_special_logging_rows",
    "_state_logic_summary",
    "_state_rows",
    "_table_headers",
    "_table_text",
    "_typed_extractor",
    "_value_text",
    "_variable_rows",
    "_write_text",
    "cast",
    "classify_documentation_structure",
    "config_module",
    "configgen",
    "const",
    "discover_documentation_unit_candidates",
    "document_scope_summary",
    "generate_docx",
    "pytest",
    "runpy",
]
