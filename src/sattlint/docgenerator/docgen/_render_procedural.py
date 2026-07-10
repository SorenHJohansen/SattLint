from __future__ import annotations

import typing as t

from docx.document import Document as DocClass

from ...analyzers.framework import Issue
from ..classification import DocumentationClassification, DocumentedModule
from ._core import DocumentUnit, _heading, _paragraph, _sequence_table_rows, _table, _underlined
from ._data_helpers import (
    _event_rows,
    _generic_section_rows,
    _is_within_any,
    _message_rows,
    _module_description,
    _module_title,
    _parameter_catalog_rows,
    _sequence_rows,
    _special_logging_rows,
)
from ._render_physical import _render_named_table_section


def _render_procedural_model(
    doc: DocClass, units: list[DocumentUnit], classification: DocumentationClassification
) -> None:
    _heading(doc, "S88 Procedural model", level=1)
    for unit in units:
        if not unit.operations and not unit.engineering_parameters:
            continue
        _heading(doc, f"Operations Unit Class - {unit.title}", level=2)
        _render_named_table_section(
            doc,
            "Unit engineering parameters",
            _parameter_catalog_rows(unit.engineering_parameters),
            headers=["Parameter", "Module Type", "Location", "Description"],
            level=3,
            widths=(2, 2, 3, 2),
        )
        for operation in unit.operations:
            _render_operation_section(doc, operation, classification)


def _render_operation_section(
    doc: DocClass, entry: DocumentedModule, classification: DocumentationClassification
) -> None:
    _heading(doc, f"Operation {_module_title(entry)}", level=3)
    _underlined(doc, "Description")
    _paragraph(doc, _module_description(entry))
    recipe_parameters = classification.descendants(entry, category="rp")
    engineering_parameters = classification.descendants(entry, category="ep")
    user_parameters = classification.descendants(entry, category="up")
    _render_named_table_section(
        doc,
        "Recipe parameters",
        _parameter_catalog_rows(recipe_parameters),
        headers=["Parameter", "Module Type", "Location", "Description"],
        level=4,
        widths=(2, 2, 3, 2),
    )
    _render_named_table_section(
        doc,
        "Engineering parameters",
        _parameter_catalog_rows(engineering_parameters),
        headers=["Parameter", "Module Type", "Location", "Description"],
        level=4,
        widths=(2, 2, 3, 2),
    )
    if user_parameters:
        _render_named_table_section(
            doc,
            "User parameters",
            _parameter_catalog_rows(user_parameters),
            headers=["Parameter", "Module Type", "Location", "Description"],
            level=4,
            widths=(2, 2, 3, 2),
        )
    _render_named_table_section(
        doc,
        "Messages",
        _message_rows(entry, classification),
        headers=["Name", "Module Type", "Location", "Description"],
        level=4,
        widths=(2, 2, 3, 2),
    )
    _render_named_table_section(
        doc,
        "Operation events",
        _event_rows(entry, classification),
        headers=["Name", "Module Type", "Location", "Description"],
        level=4,
        widths=(2, 2, 3, 2),
    )
    _render_named_table_section(
        doc,
        "Special log parameters",
        _special_logging_rows(entry, classification),
        headers=["Name", "Module Type", "Location", "Description"],
        level=4,
        widths=(2, 2, 3, 2),
    )
    for sequence_name, sequence_rows in _sequence_rows(entry, classification):
        _heading(doc, f"Sub sequence - {sequence_name}", level=4)
        if sequence_rows:
            _table(
                doc,
                ["Type", "Name", "Condition / Detail", "Enter", "Active", "Exit"],
                _sequence_table_rows(sequence_rows),
                col_widths=(1, 1, 3, 2, 2, 2),
            )
        else:
            _paragraph(doc, "No explicit sequence statements detected.")


def _render_uncategorized_appendix(
    doc: DocClass, classification: DocumentationClassification, units: list[DocumentUnit]
) -> None:
    unit_roots = [unit.root for unit in units]
    appendix_entries = [entry for entry in classification.uncategorized if not _is_within_any(entry, unit_roots)]
    if not appendix_entries:
        return
    _heading(doc, "Appendix: Supporting modules", level=1)
    _render_named_table_section(
        doc,
        "Other module instances",
        _generic_section_rows(appendix_entries),
        headers=["Name", "Module Type", "Location", "Description"],
        level=2,
        widths=(2, 2, 3, 2),
    )


def _render_upgrade_insights(doc: DocClass, upgrade_issues: t.Sequence[Issue]) -> None:
    if not upgrade_issues:
        return
    _heading(doc, "Upgrade insights", level=1)
    _paragraph(
        doc,
        "Repeated module names with structural drift are summarized below to support upgrade planning and regression review.",
    )
    for issue in upgrade_issues:
        issue_data = t.cast(dict[str, object], issue.data or {})
        module_name = str(issue_data.get("module_name", issue.message))
        _heading(doc, f"Module {module_name}", level=2)
        _paragraph(doc, issue.message)
        upgrade_notes = issue_data.get("upgrade_notes", [])
        for note in t.cast(list[object], upgrade_notes if isinstance(upgrade_notes, list) else []):
            doc.add_paragraph(str(note), style="List Paragraph")


def _render_change_log(doc: DocClass) -> None:
    _heading(doc, "Change Log", level=1)
    _table(
        doc,
        ["Revision", "Description"],
        [["Generated", "Document generated from SattLine source structure by SattLint."]],
        col_widths=(1, 5),
    )
