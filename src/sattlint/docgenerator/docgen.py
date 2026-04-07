"""Generate a Functional-Specification-style Word document from a SattLine AST."""

from __future__ import annotations

import pathlib
import typing as t

from docx import Document as DocumentFactory
from docx.document import Document as DocClass
from docx.shared import Inches

from .. import config as config_module
from ..models.ast_model import BasePicture, Equation, ModuleCode, Sequence, Variable
from ..utils.formatter import format_expr
from .classification import DocumentationClassification, DocumentedModule, classify_documentation_structure


def _heading(doc: DocClass, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def _paragraph(doc: DocClass, text: str, *, bold: bool = False) -> None:
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = bold


def _underlined(doc: DocClass, text: str) -> None:
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    run.underline = True


def _table(
    doc: DocClass,
    headers: list[str],
    rows: t.Sequence[t.Sequence[object]],
    col_widths: tuple[int, ...] = (),
) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"

    for index, header in enumerate(headers):
        table.rows[0].cells[index].text = str(header)

    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            cells[index].text = str(value)

    if col_widths:
        for index, width in enumerate(col_widths):
            for row in table.rows:
                row.cells[index].width = Inches(width)


def _format_coord(coord: tuple[float, ...] | None) -> str:
    if coord is None:
        return "<none>"
    return "(" + ", ".join(f"{value:.6g}" for value in coord) + ")"


def _render_variable_table(doc: DocClass, variables: list[Variable]) -> None:
    rows = [
        [
            variable.name,
            variable.datatype_text,
            bool(variable.global_var),
            bool(variable.const),
            bool(variable.state),
            _value_text(variable.init_value),
            variable.description or "",
        ]
        for variable in variables
    ]
    _table(
        doc,
        ["Name", "Datatype", "Global", "Const", "State", "Init", "Description"],
        rows,
        col_widths=(2, 1, 1, 1, 1, 1, 3),
    )


def _render_parameter_mapping_table(doc: DocClass, mappings: list) -> None:
    rows = []
    for mapping in mappings:
        target = mapping.target.get("var_name") if isinstance(mapping.target, dict) else str(mapping.target)
        source = (
            mapping.source.get("var_name")
            if isinstance(mapping.source, dict)
            else _value_text(mapping.source_literal)
        )
        rows.append(
            [
                target,
                mapping.source_type,
                bool(mapping.is_source_global),
                bool(mapping.is_duration),
                source,
            ]
        )

    _table(
        doc,
        ["Target", "Source Type", "Is Global", "Is Duration", "Source / Literal"],
        rows,
        col_widths=(2, 2, 1, 1, 3),
    )


def _render_modulecode(doc: DocClass, modulecode: ModuleCode | None, *, level: int = 4) -> None:
    if modulecode is None:
        _paragraph(doc, "No explicit code blocks found.")
        return

    if modulecode.sequences:
        _heading(doc, "Sequences", level=level)
        for sequence in modulecode.sequences:
            _render_sequence(doc, sequence, level=level + 1)

    if modulecode.equations:
        _heading(doc, "Equations", level=level)
        for equation in modulecode.equations:
            _render_equation(doc, equation, level=level + 1)

    if not modulecode.sequences and not modulecode.equations:
        _paragraph(doc, "No explicit code blocks found.")


def _render_sequence(doc: DocClass, sequence: Sequence, *, level: int) -> None:
    title = f"Sequence {sequence.name} at {_format_coord(sequence.position)}"
    if sequence.size:
        title += f" size {sequence.size}"
    _heading(doc, title, level=level)
    for statement in sequence.code or []:
        _paragraph(doc, format_expr(statement))


def _render_equation(doc: DocClass, equation: Equation, *, level: int) -> None:
    title = f"EquationBlock {equation.name} at {_format_coord(equation.position)}"
    if equation.size:
        title += f" size {equation.size}"
    _heading(doc, title, level=level)
    for statement in equation.code or []:
        _paragraph(doc, format_expr(statement))


def _value_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _module_row(entry: DocumentedModule) -> list[str]:
    return [
        entry.name,
        entry.moduletype_label or entry.kind,
        entry.short_path,
    ]


def _render_summary_table(
    doc: DocClass,
    entries: list[DocumentedModule],
    *,
    first_header: str,
) -> None:
    if not entries:
        _paragraph(doc, "No matching modules detected.")
        return
    rows = [_module_row(entry) for entry in entries]
    _table(
        doc,
        [first_header, "Module Type", "Location"],
        rows,
        col_widths=(2, 2, 4),
    )


def _render_module_metadata(doc: DocClass, entry: DocumentedModule) -> None:
    _paragraph(doc, f"Instance name: {entry.name}")
    _paragraph(doc, f"Module type: {entry.moduletype_label or entry.kind}")
    _paragraph(doc, f"Location: {entry.short_path}")
    _paragraph(doc, f"Coordinates: {_format_coord(entry.node.header.invoke_coord)}")


def _render_parameter_catalog(
    doc: DocClass,
    title: str,
    entries: list[DocumentedModule],
) -> None:
    _heading(doc, title, level=4)
    if not entries:
        _paragraph(doc, "No matching parameters detected.")
        return
    _table(
        doc,
        ["Parameter", "Module Type", "Location"],
        [_module_row(entry) for entry in entries],
        col_widths=(2, 2, 4),
    )


def _render_parameter_details(doc: DocClass, entry: DocumentedModule) -> None:
    if entry.moduleparameters:
        _paragraph(doc, "Module parameters", bold=True)
        _render_variable_table(doc, list(entry.moduleparameters))
    if entry.localvariables:
        _paragraph(doc, "Local variables", bold=True)
        _render_variable_table(doc, list(entry.localvariables))
    if entry.parametermappings:
        _paragraph(doc, "Parameter mappings", bold=True)
        _render_parameter_mapping_table(doc, list(entry.parametermappings))
    if not entry.moduleparameters and not entry.localvariables and not entry.parametermappings:
        _paragraph(doc, "No parameter details detected.")


def _render_equipment_module_section(
    doc: DocClass,
    entry: DocumentedModule,
) -> None:
    _heading(doc, f"Equipment Module {entry.name}", level=3)
    _underlined(doc, "Description")
    _render_module_metadata(doc, entry)
    _heading(doc, "Parameters", level=4)
    _render_parameter_details(doc, entry)
    _heading(doc, "States and logic", level=4)
    _render_modulecode(doc, entry.modulecode, level=5)


def _render_operation_section(
    doc: DocClass,
    entry: DocumentedModule,
    classification: DocumentationClassification,
) -> None:
    _heading(doc, f"Operation {entry.name}", level=3)
    _underlined(doc, "Description")
    _render_module_metadata(doc, entry)

    recipe_parameters = classification.descendants(entry, category="recipe_parameters")
    engineering_parameters = classification.descendants(entry, category="engineering_parameters")
    user_parameters = classification.descendants(entry, category="user_parameters")

    _render_parameter_catalog(doc, "Recipe parameters", recipe_parameters)
    _render_parameter_catalog(doc, "Engineering parameters", engineering_parameters)
    _render_parameter_catalog(doc, "User parameters", user_parameters)
    _heading(doc, "Parameters and mappings", level=4)
    _render_parameter_details(doc, entry)
    _heading(doc, "Operation logic", level=4)
    _render_modulecode(doc, entry.modulecode, level=5)


def _render_introduction(
    doc: DocClass,
    root: BasePicture,
    classification: DocumentationClassification,
) -> None:
    _heading(doc, "Introduction", level=1)
    _heading(doc, "Scope", level=2)
    _paragraph(
        doc,
        f"This document is the generated Functional Specification for {root.header.name}. It summarizes the parsed SattLine structure using categorized module detection rules.",
    )
    if classification.scope and classification.scope.mode != "all":
        scope_roots = classification.scope.roots or []
        if scope_roots:
            _paragraph(
                doc,
                "Documentation scope is limited to the selected unit roots: "
                + ", ".join(entry.short_path for entry in scope_roots),
            )
        if classification.scope.unmatched_values:
            _paragraph(
                doc,
                "Unmatched scope filters: "
                + ", ".join(classification.scope.unmatched_values),
            )

    _heading(doc, "S88 Model", level=2)
    _underlined(doc, "S88 Physical Model")
    _paragraph(doc, "The physical model section groups equipment-module style content detected from module structure and descendant marker modules.")
    _underlined(doc, "S88 Procedural Model")
    _paragraph(doc, "The procedural model section groups operation modules and their detected recipe, engineering, and user parameters.")

    _heading(doc, "Definitions and abbreviations", level=2)
    _table(
        doc,
        ["Abbreviation", "Meaning"],
        [
            ["EM", "Equipment Module"],
            ["OP", "Operation"],
            ["RP", "Recipe Parameter"],
            ["EP", "Engineering Parameter"],
            ["UP", "User Parameter"],
        ],
        col_widths=(2, 4),
    )

    _heading(doc, "References", level=2)
    rows = [[category, len(classification.categories.get(category, []))] for category in classification.section_order]
    rows.append(["uncategorized", len(classification.uncategorized)])
    _table(doc, ["Detected section", "Count"], rows, col_widths=(3, 1))


def _render_physical_model(
    doc: DocClass,
    root: BasePicture,
    classification: DocumentationClassification,
) -> None:
    equipment_modules = classification.categories.get("equipment_modules", [])
    uncategorized = classification.uncategorized

    _heading(doc, "S88 Physical model", level=1)
    _heading(doc, f"Process Cell - {root.header.name}", level=2)
    _paragraph(doc, f"The detected process-cell content for {root.header.name} is listed below.")

    _heading(doc, "Instance-configurable parameters", level=3)
    root_engineering = classification.categories.get("engineering_parameters", [])
    _render_summary_table(doc, root_engineering, first_header="Engineering Parameter")

    if classification.scope and classification.scope.roots:
        _heading(doc, "Selected units", level=3)
        _render_summary_table(
            doc,
            classification.scope.roots,
            first_header="Unit",
        )

    _heading(doc, f"Unit Class definition: {root.header.name}", level=2)
    _paragraph(doc, "This section summarizes physical modules and other detected unit-level structure.")

    _heading(doc, "Equipment module instances", level=3)
    _render_summary_table(doc, equipment_modules, first_header="Equipment Module")

    if uncategorized:
        _heading(doc, "Other module instances", level=3)
        _render_summary_table(doc, uncategorized, first_header="Module")

    for entry in equipment_modules:
        _render_equipment_module_section(doc, entry)


def _render_procedural_model(
    doc: DocClass,
    root: BasePicture,
    classification: DocumentationClassification,
) -> None:
    operations = classification.categories.get("operations", [])
    engineering_parameters = classification.categories.get("engineering_parameters", [])
    user_parameters = classification.categories.get("user_parameters", [])
    recipe_parameters = classification.categories.get("recipe_parameters", [])

    _heading(doc, "S88 Procedural model", level=1)
    _heading(doc, f"Operations Unit Class - {root.header.name}", level=2)

    _heading(doc, "Unit engineering parameters", level=3)
    _render_summary_table(doc, engineering_parameters, first_header="Engineering Parameter")

    _heading(doc, "Unit user parameters", level=3)
    _render_summary_table(doc, user_parameters, first_header="User Parameter")

    _heading(doc, "Unit recipe parameters", level=3)
    _render_summary_table(doc, recipe_parameters, first_header="Recipe Parameter")

    for entry in operations:
        _render_operation_section(doc, entry, classification)


def _render_uncategorized_appendix(doc: DocClass, classification: DocumentationClassification) -> None:
    if not classification.uncategorized:
        return

    _heading(doc, "Appendix: Uncategorized modules", level=1)
    _render_summary_table(doc, classification.uncategorized, first_header="Module")
    for entry in classification.uncategorized:
        _heading(doc, entry.name, level=2)
        _render_module_metadata(doc, entry)
        _heading(doc, "Parameters and mappings", level=3)
        _render_parameter_details(doc, entry)
        _heading(doc, "Logic", level=3)
        _render_modulecode(doc, entry.modulecode, level=4)


def generate_docx(
    root: BasePicture,
    out_path: str | pathlib.Path,
    *,
    documentation_config: dict | None = None,
    unavailable_libraries: set[str] | None = None,
) -> None:
    doc: DocClass = DocumentFactory()
    classification = classify_documentation_structure(
        root,
        documentation_config or config_module.get_documentation_config(),
        unavailable_libraries=unavailable_libraries,
    )

    _heading(doc, "Functional Specification", level=0)
    _paragraph(doc, f"Generated from SattLine AST - {root.header.name}")
    doc.add_page_break()

    _render_introduction(doc, root, classification)
    _render_physical_model(doc, root, classification)
    _render_procedural_model(doc, root, classification)
    _render_uncategorized_appendix(doc, classification)

    out_file = pathlib.Path(out_path)
    doc.save(str(out_file))
    print(f"✅ Documentation written to {out_file.resolve()}")
