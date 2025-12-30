"""
docgen.py

Generate a Word‑document design description from a Sattline AST.

Typical usage
--------
    from docgen import generate_docx
    from transformer.sl_transformer import SLTransformer
    from lark import Lark

    parser = Lark.open("my_grammar.lark", start="start")
    tree   = parser.parse(source_text)
    ast    = SLTransformer().transform(tree)          # → BasePicture

    generate_docx(ast, "MyDesign.docx")
"""

from __future__ import annotations

import pathlib
from typing import Union

# --------------------------------------------------------------
# python‑docx imports
# ----------------------------------------------------------
# The top‑level ``Document`` symbol is a *factory function* that returns an
# instance of the real class defined in ``docx.document``.  We import both:
#   * ``DocumentFactory`` – used to *create* a new document.
#   * ``DocClass``       – the actual class, used for type hints.
# -------------------------------------------------------
from docx import Document as DocumentFactory  # factory function
from docx.document import Document as DocClass  # real class
from docx.shared import Inches

# -------------------------------------------------------
# Import the AST model classes you already have.
# Adjust the import path if the modules live elsewhere.
# ----------------------------------------------------------------------
from models.ast_model import (
    BasePicture,
    FrameModule,
    SingleModule,
    ModuleTypeInstance,
    ModuleTypeDef,
    Variable,
    DataType,
    ModuleDef,
    ModuleCode,
    Sequence,
    Equation,
    format_expr,  # pretty‑printer for statements
)

# --------------------------------------------------------------
# Helper utilities – formatting -----------------------------------------
# ----------------------------------------------------------------------


def _heading(doc: DocClass, text: str, level: int = 1) -> None:
    """Add a heading (Word style Heading 1‑4)."""
    doc.add_heading(text, level=level)


def _paragraph(doc: DocClass, text: str, bold: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold


def _table(
    doc: DocClass,
    headers: list[str],
    rows: list[list[Union[str, int, float]]],
    col_widths: tuple[int, ...] = (),
) -> None:
    """
    Insert a simple table.
    `col_widths` – optional column widths (in inches) as integers.
    """
    table = doc.add_table(rows=1, cols=len(headers))
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = str(h)

    # -----  ←  NEW: each statement on its own line  --------
    for row in rows:
        # add a new row and keep a reference to its cells
        cells = table.add_row().cells  # ← now definitely bound
        for i, cell in enumerate(row):
            cells[i].text = str(cell)
    # --------------------------------------------------------

    if col_widths:
        for i, width in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Inches(width)


# ----------------------------------------------------------------------
# Core traversal – turning AST objects into Word elements
# ----------------------------------------------------------------------
def _format_coord(coord: tuple[float, ...] | None) -> str:
    """
    Turn a coordinate tuple into a readable string.
    If ``coord`` is ``None`` we return a placeholder – this avoids
    type‑checking errors when a field is optional.
    """
    if coord is None:
        return "<none>"
    # Normal case – a tuple of floats (any length)
    return "(" + ", ".join(f"{c:.6g}" for c in coord) + ")"


def _render_basepicture(doc: DocClass, bp: BasePicture) -> None:
    _heading(doc, "BasePicture", level=1)

    _paragraph(doc, f"Name       : {bp.name}")
    _paragraph(doc, f"Position   : {_format_coord(bp.position)}")
    doc.add_paragraph("")  # blank line

    if bp.datatype_defs:
        _heading(doc, "Datatype definitions (records)", level=2)
        for dt in bp.datatype_defs:
            _render_datatype(doc, dt)

    if bp.moduletype_defs:
        _heading(doc, "Module type definitions", level=2)
        for mt in bp.moduletype_defs:
            _render_moduletype_def(doc, mt)

    if bp.localvariables:
        _heading(doc, "Local variables (BasePicture)", level=2)
        _render_variable_table(doc, bp.localvariables)

    if bp.submodules:
        _heading(doc, "Sub‑modules (instances)", level=2)
        for sm in bp.submodules:
            _render_module_instance(doc, sm, indent=0)

    if bp.moduledef:
        _heading(doc, "ModuleDef (graphical settings)", level=2)
        _render_moduledef(doc, bp.moduledef)

    if bp.modulecode:
        _heading(doc, "ModuleCode (logic)", level=2)
        _render_modulecode(doc, bp.modulecode)


def _render_datatype(doc: DocClass, dt: DataType) -> None:
    _heading(doc, f"Datatype – {dt.name}", level=3)
    _paragraph(doc, f"Description : {dt.description}")
    _paragraph(doc, f"Datecode    : {dt.datecode}")
    if dt.var_list:
        _render_variable_table(doc, dt.var_list)


def _render_moduletype_def(doc: DocClass, mt: ModuleTypeDef) -> None:
    _heading(doc, f"ModuleTypeDef – {mt.name}", level=3)
    _paragraph(doc, f"Datecode : {mt.datecode}")

    if mt.moduleparameters:
        _paragraph(doc, "Parameters:", bold=True)
        _render_variable_table(doc, mt.moduleparameters)

    if mt.localvariables:
        _paragraph(doc, "Local variables:", bold=True)
        _render_variable_table(doc, mt.localvariables)

    if mt.submodules:
        _paragraph(doc, "Sub‑modules:", bold=True)
        for sm in mt.submodules:
            _render_module_instance(doc, sm, indent=1)

    if mt.moduledef:
        _paragraph(doc, "ModuleDef:", bold=True)
        _render_moduledef(doc, mt.moduledef)

    if mt.modulecode:
        _paragraph(doc, "ModuleCode:", bold=True)
        _render_modulecode(doc, mt.modulecode)


def _render_variable_table(doc: DocClass, vars_: list[Variable]) -> None:
    headers = ["Name", "Datatype", "Global", "Const", "State", "Init", "Description"]
    rows = [
        [
            v.name,
            v.datatype,
            v.global_var,
            v.const,
            v.state,
            v.init_value,
            v.description or "",
        ]
        for v in vars_
    ]
    # Column widths are integer inches – 2 in for the long description column,
    # 1 in for the others (good enough for most designs).
    _table(doc, headers, rows, col_widths=(2, 1, 1, 1, 1, 1, 2))


def _render_module_instance(
    doc: DocClass,
    inst,
    indent: int = 0,
) -> None:
    """Dispatch based on concrete instance type."""
    prefix = "    " * indent

    if isinstance(inst, FrameModule):
        _heading(doc, f"{prefix}FrameModule – {inst.header.name}", level=3)
        _paragraph(doc, f"{prefix}Enable       : {inst.header.enable}")
        _paragraph(
            doc, f"{prefix}Invoke_coord : {_format_coord(inst.header.invoke_coord)}"
        )
        _paragraph(doc, f"{prefix}Datecode     : {inst.datecode}")

        if inst.submodules:
            _paragraph(doc, f"{prefix}Sub‑modules :", bold=True)
            for sm in inst.submodules:
                _render_module_instance(doc, sm, indent + 1)

        if inst.moduledef:
            _paragraph(doc, f"{prefix}ModuleDef :", bold=True)
            _render_moduledef(doc, inst.moduledef, prefix)

        if inst.modulecode:
            _paragraph(doc, f"{prefix}ModuleCode :", bold=True)
            _render_modulecode(doc, inst.modulecode, prefix)

    elif isinstance(inst, SingleModule):
        _heading(doc, f"{prefix}SingleModule – {inst.header.name}", level=3)
        _paragraph(doc, f"{prefix}Enable       : {inst.header.enable}")
        _paragraph(
            doc, f"{prefix}Invoke_coord : {_format_coord(inst.header.invoke_coord)}"
        )
        _paragraph(doc, f"{prefix}Datecode     : {inst.datecode}")

        if inst.moduleparameters:
            _paragraph(doc, f"{prefix}Parameters :", bold=True)
            _render_variable_table(doc, inst.moduleparameters)

        if inst.localvariables:
            _paragraph(doc, f"{prefix}Local variables :", bold=True)
            _render_variable_table(doc, inst.localvariables)

        if inst.submodules:
            _paragraph(doc, f"{prefix}Sub‑modules :", bold=True)
            for sm in inst.submodules:
                _render_module_instance(doc, sm, indent + 1)

        if inst.parametermappings:
            _paragraph(doc, f"{prefix}Parameter Mappings :", bold=True)
            _render_parameter_mapping_table(doc, inst.parametermappings, prefix)

        if inst.moduledef:
            _paragraph(doc, f"{prefix}ModuleDef :", bold=True)
            _render_moduledef(doc, inst.moduledef, prefix)

        if inst.modulecode:
            _paragraph(doc, f"{prefix}ModuleCode :", bold=True)
            _render_modulecode(doc, inst.modulecode, prefix)

    elif isinstance(inst, ModuleTypeInstance):
        _heading(doc, f"{prefix}ModuleTypeInstance – {inst.header.name}", level=3)
        _paragraph(doc, f"{prefix}Enable          : {inst.header.enable}")
        _paragraph(
            doc, f"{prefix}Invoke_coord    : {_format_coord(inst.header.invoke_coord)}"
        )
        _paragraph(doc, f"{prefix}ModuleTypeName  : {inst.moduletype_name}")

        if inst.parametermappings:
            _paragraph(doc, f"{prefix}Parameter Mappings :", bold=True)
            _render_parameter_mapping_table(doc, inst.parametermappings, prefix)

    else:
        _paragraph(doc, f"{prefix}<Unknown instance type: {type(inst)}>")


def _render_parameter_mapping_table(
    doc: DocClass,
    mappings: list,
    prefix: str = "",
) -> None:
    headers = ["Target", "Source Type", "Is Global", "Is Duration", "Source / Literal"]
    rows = []
    for pm in mappings:
        target = (
            pm.target.get("var_name") if isinstance(pm.target, dict) else str(pm.target)
        )
        source = (
            pm.source.get("var_name")
            if isinstance(pm.source, dict)
            else repr(pm.source_literal)
        )
        rows.append(
            [
                target,
                pm.source_type,
                pm.is_source_global,
                pm.is_duration,
                source,
            ]
        )
    _table(doc, headers, rows, col_widths=(2, 2, 1, 1, 2))


def _render_moduledef(doc: DocClass, md: ModuleDef, prefix: str = "") -> None:
    _paragraph(doc, f"{prefix}ClippingBounds : {md.clipping_bounds}")
    _paragraph(doc, f"{prefix}ZoomLimits     : {md.zoom_limits}")
    _paragraph(doc, f"{prefix}SeqLayers      : {md.seq_layers}")
    _paragraph(doc, f"{prefix}Grid           : {md.grid}")
    _paragraph(doc, f"{prefix}Zoomable       : {md.zoomable}")


def _render_modulecode(doc: DocClass, mc: ModuleCode, prefix: str = "") -> None:
    if mc.sequences:
        _heading(doc, f"{prefix}Sequences", level=4)
        for seq in mc.sequences:
            _render_sequence(doc, seq, prefix + "    ")

    if mc.equations:
        _heading(doc, f"{prefix}Equations", level=4)
        for eq in mc.equations:
            _render_equation(doc, eq, prefix + "    ")


def _render_sequence(doc: DocClass, seq: Sequence, prefix: str = "") -> None:
    title = f"{prefix}Sequence '{seq.name}' at {_format_coord(seq.position)}"
    if seq.size:
        title += f" size {seq.size}"
    title += f" (type={seq.type})"
    _heading(doc, title, level=5)

    def _block(label: str, stmts: list):
        if not stmts:
            return
        _paragraph(doc, f"{prefix}{label}:", bold=True)
        for stmt in stmts:
            txt = format_expr(stmt)  # pretty‑printed statement
            _paragraph(doc, f"{prefix}    {txt}")

    _block("Enter", seq.code)


def _render_equation(doc: DocClass, eq: Equation, prefix: str = "") -> None:
    title = f"{prefix}EquationBlock name='{eq.name}' at {_format_coord(eq.position)}"
    if eq.size:
        title += f" size {eq.size}"
    _heading(doc, title, level=5)

    for stmt in eq.code:
        txt = format_expr(stmt)
        _paragraph(doc, f"{prefix}    {txt}")


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def generate_docx(root: BasePicture, out_path: Union[str, pathlib.Path]) -> None:
    """
    Create a Word document from the given AST root (BasePicture).

    Parameters
    ----------
    root : BasePicture
        The fully‑populated AST object returned by your transformer.
    out_path : str or Path
        Destination filename – ``.docx`` extension is recommended.
    """
    # ``DocumentFactory()`` is the callable that creates a ``DocClass`` instance.
    doc: DocClass = DocumentFactory()

    # Optional title page
    _heading(doc, "Design Documentation", level=0)
    _paragraph(doc, f"Generated from Sattline AST – {root.name}")
    doc.add_page_break()

    # Main content
    _render_basepicture(doc, root)

    # Save – ``doc.save`` expects a plain string or a binary stream.
    out_file = pathlib.Path(out_path)
    doc.save(str(out_file))
    print(f"✅ Documentation written to {out_file.resolve()}")


# ----------------------------------------------------------------------
# Simple CLI entry‑point (run this file directly for a quick test)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from transformer.sl_transformer import SLTransformer
    from lark import Lark

    if len(sys.argv) != 3:
        print("Usage: python docgen.py <grammar.lark> <source.sl>")
        sys.exit(1)

    grammar_path, source_path = sys.argv[1], sys.argv[2]

    parser = Lark.open(grammar_path, start="start")
    with open(source_path, encoding="utf-8") as f:
        src = f.read()

    tree = parser.parse(src)
    ast_root = SLTransformer().transform(tree)  # should be a BasePicture

    out_docx = pathlib.Path(source_path).with_suffix(".docx")
    generate_docx(ast_root, out_docx)
