"""Generate a Functional-Specification-style Word document from a SattLine AST."""

from __future__ import annotations

import logging
import pathlib
import typing as t

from docx import Document as DocumentFactory
from docx.document import Document as DocClass

from sattline_parser.models.ast_model import BasePicture

from ... import config as config_module
from ...analyzers.framework import Issue
from ...config_types import DocumentationConfig, DocumentationConfigOverride
from ..classification import DocumentationClassification, DocumentedModule, classify_documentation_structure
from ._core import (
    DocumentUnit,
    SequenceRenderRow,
    _bullet,
    _centered_title,
    _ensure_styles,
    _format_coord,
    _heading,
    _paragraph,
    _prettify_name,
    _sequence_render_rows,
    _sequence_table_rows,
    _table,
    _underlined,
    _value_text,
)
from ._data_helpers import (
    _build_units,
    _calculation_rows,
    _communication_rows,
    _configurable_parameter_rows,
    _entry_variable,
    _entry_variable_text,
    _event_rows,
    _event_table_rows,
    _first_non_empty,
    _is_calculation_entry,
    _is_cip_valve_entry,
    _is_event_entry,
    _is_graphics_entry,
    _is_inlet_consumption_entry,
    _is_intervention_entry,
    _is_measurement_entry,
    _is_other_device_entry,
    _is_special_logging_entry,
    _is_supervision_entry,
    _is_timer_entry,
    _is_within_any,
    _mapping_source_text,
    _mapping_target_name,
    _message_rows,
    _module_description,
    _pid_controller_rows,
    _sequence_rows,
    _simple_name_tag_rows,
    _special_logging_rows,
    _state_logic_summary,
    _state_rows,
    _variable_rows,
)
from ._render_physical import (
    _render_document_cover,
    _render_equipment_module_section,
    _render_introduction,
    _render_named_table_section,
    _render_physical_model,
    _render_references,
    _render_unit_physical_section,
)
from ._render_procedural import (
    _render_change_log,
    _render_operation_section,
    _render_procedural_model,
    _render_uncategorized_appendix,
    _render_upgrade_insights,
)

log = logging.getLogger("SattLint")

__all__ = [
    "DocClass",
    "DocumentUnit",
    "DocumentationClassification",
    "DocumentedModule",
    "SequenceRenderRow",
    "_bullet",
    "_calculation_rows",
    "_centered_title",
    "_communication_rows",
    "_configurable_parameter_rows",
    "_ensure_styles",
    "_entry_variable",
    "_entry_variable_text",
    "_event_rows",
    "_event_table_rows",
    "_first_non_empty",
    "_format_coord",
    "_heading",
    "_is_within_any",
    "_mapping_source_text",
    "_mapping_target_name",
    "_message_rows",
    "_module_description",
    "_paragraph",
    "_pid_controller_rows",
    "_prettify_name",
    "_render_equipment_module_section",
    "_render_named_table_section",
    "_sequence_render_rows",
    "_sequence_rows",
    "_sequence_table_rows",
    "_simple_name_tag_rows",
    "_special_logging_rows",
    "_state_logic_summary",
    "_state_rows",
    "_table",
    "_underlined",
    "_value_text",
    "_variable_rows",
    "generate_docx",
]


def generate_docx(
    root: BasePicture,
    out_path: str | pathlib.Path,
    *,
    documentation_config: DocumentationConfig | DocumentationConfigOverride | dict[str, t.Any] | None = None,
    unavailable_libraries: set[str] | None = None,
    upgrade_issues: t.Sequence[Issue] | None = None,
) -> None:
    doc: DocClass = DocumentFactory()
    _ensure_styles(doc)
    classification = classify_documentation_structure(
        root,
        documentation_config or config_module.get_documentation_config(),
        unavailable_libraries=unavailable_libraries,
    )
    units = _build_units(classification)
    _render_document_cover(doc, classification, units)
    _render_introduction(doc, units)
    _render_references(doc, classification, units)
    _render_physical_model(doc, units, classification)
    doc.add_page_break()
    _render_procedural_model(doc, units, classification)
    _render_uncategorized_appendix(doc, classification, units)
    if upgrade_issues is None:
        from ...analyzers.modules import analyze_version_drift  # noqa: PLC0415

        upgrade_issues = analyze_version_drift(root).issues
    resolved_upgrade_issues: t.Sequence[Issue] = upgrade_issues or ()
    _render_upgrade_insights(doc, resolved_upgrade_issues)
    _render_change_log(doc)
    out_file = pathlib.Path(out_path)
    doc.save(str(out_file))
    log.info("Documentation written to %s", out_file.resolve())
