"""Phase 3 reference-visibility tests over real parser output.

Every test parses ``ParserSurfaceAnalyzerShapes.s`` and asserts the analyzer
result. Hand-built ASTs are deliberately avoided: the Phase 3 regressions were
silent disappearances of references from shapes the parser produced.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sattline_parser import parse_source_file
from sattline_parser.ast import (
    AssignClause,
    BasePicture,
    ColourSpec,
    EnableClause,
    IntLiteral,
    MappingSource,
    ModuleDef,
    ModuleTypeInstance,
    PickButton,
    ProcedureCall,
    VarTail,
)

from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.analyzers.variables._variables_mapping_refs import mapping_source_ref
from sattlint.models.usage import VariableUsage

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "parser_surface" / "ParserSurfaceAnalyzerShapes.s"


@pytest.fixture(scope="module")
def analyzed() -> tuple[BasePicture, VariablesAnalyzer]:
    base_picture = parse_source_file(FIXTURE_PATH)
    analyzer = VariablesAnalyzer(base_picture, fail_loudly=False)
    analyzer.run()
    return base_picture, analyzer


def _usage(analyzer: VariablesAnalyzer, name: str) -> VariableUsage:
    variable = next(variable for variable in analyzer.bp.localvariables if variable.name == name)
    return analyzer.get_usage(variable)


def _module_def(base_picture: BasePicture) -> ModuleDef:
    module_def = base_picture.moduledef
    assert module_def is not None
    return module_def


def test_text_object_and_pick_button_names_are_ui_reads(analyzed: tuple[BasePicture, VariablesAnalyzer]) -> None:
    _base_picture, analyzer = analyzed

    text_usage = _usage(analyzer, "TextVar")
    pick_usage = _usage(analyzer, "PickVar")

    assert text_usage.ui_read is True
    assert pick_usage.ui_read is True


def test_header_argument_tails_are_read_and_written(analyzed: tuple[BasePicture, VariablesAnalyzer]) -> None:
    base_picture, analyzer = analyzed

    header = base_picture.submodules[0].header
    coordinate_tail = header.invoke_coord_tails[0]
    assert isinstance(coordinate_tail, VarTail)
    assert coordinate_tail.bound_name == "PosVar"

    enable = header.arguments.enable
    assert enable is not None
    assert isinstance(enable.tail, VarTail)
    assert enable.tail.bound_name == "HeaderFlag"

    in_view = header.arguments.module_in_view
    assert in_view is not None
    assert isinstance(in_view.tail, VarTail)
    assert in_view.tail.bound_name == "HeaderOut"

    assign = header.arguments.assigns[0]
    assert assign.name == "Param1"
    assert isinstance(assign.value, IntLiteral)
    assert int(assign.value) == 5

    assert _usage(analyzer, "PosVar").ui_read is True
    assert _usage(analyzer, "HeaderFlag").read is True
    assert _usage(analyzer, "HeaderOut").written is True
    assert _usage(analyzer, "HeaderOut").read is False


def test_clipping_tail_is_read(analyzed: tuple[BasePicture, VariablesAnalyzer]) -> None:
    base_picture, analyzer = analyzed

    module_def = _module_def(base_picture)
    clipping = module_def.clipping
    assert clipping is not None
    clipping_tail = clipping.tails[0]
    assert isinstance(clipping_tail, VarTail)
    assert clipping_tail.bound_name == "ClipVar"
    assert _usage(analyzer, "ClipVar").ui_read is True


def test_procedure_expression_argument_is_read(analyzed: tuple[BasePicture, VariablesAnalyzer]) -> None:
    base_picture, analyzer = analyzed

    module_def = _module_def(base_picture)
    button = next(obj for obj in module_def.interact_objects if obj.type == "ComButProc_")
    procedure = button.properties.get("procedure")
    assert isinstance(procedure, ProcedureCall)
    assert procedure.name == "ToggleWindow"
    assert len(procedure.args) == 1

    assert _usage(analyzer, "ProcArg").ui_read is True


def test_interactor_body_marks_enable_read_outvar_write_and_pick_read(
    analyzed: tuple[BasePicture, VariablesAnalyzer],
) -> None:
    base_picture, analyzer = analyzed

    module_def = _module_def(base_picture)
    text_box = next(obj for obj in module_def.interact_objects if obj.type == "TextBox_")
    body = text_box.properties.get("body")
    assert body is not None
    assert any(isinstance(entry, EnableClause) for entry in body)
    assert any(isinstance(entry, AssignClause) for entry in body)
    assert any(isinstance(entry, ColourSpec) for entry in body)
    assert any(isinstance(entry, PickButton) for entry in body)

    assert _usage(analyzer, "BodyFlag").ui_read is True
    assert _usage(analyzer, "BodyOut").written is True
    assert _usage(analyzer, "BodyOut").read is False
    assert _usage(analyzer, "PickVar").ui_read is True
    assert _usage(analyzer, "ColourVar").ui_read is True


def test_parameter_mapping_kinds_are_typed(analyzed: tuple[BasePicture, VariablesAnalyzer]) -> None:
    base_picture, analyzer = analyzed

    maker = next(module for module in base_picture.submodules if module.header.name == "Maker")
    assert isinstance(maker, ModuleTypeInstance)
    literal_mapping, variable_mapping, unused_mapping = maker.parametermappings

    assert literal_mapping.source_type is MappingSource.VALUE
    assert literal_mapping.source is None
    assert isinstance(literal_mapping.source_literal, int)
    assert not isinstance(literal_mapping.source_literal, bool)
    assert literal_mapping.source_literal == 5
    assert mapping_source_ref(literal_mapping) is None

    assert variable_mapping.source_type is MappingSource.VARIABLE
    assert variable_mapping.source is not None
    assert variable_mapping.source.name == "MappedVar"
    assert mapping_source_ref(variable_mapping) == "MappedVar"

    assert unused_mapping.source is not None
    assert unused_mapping.source.name == "UnusedMappedVar"

    assert _usage(analyzer, "MappedVar").read is True
    assert _usage(analyzer, "UnusedMappedVar").read is False


def test_ui_and_mapping_reads_suppress_unused_findings(analyzed: tuple[BasePicture, VariablesAnalyzer]) -> None:
    _base_picture, analyzer = analyzed

    unused_names = {
        issue.variable.name
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED and issue.variable is not None
    }
    assert unused_names.isdisjoint(
        {
            "TextVar",
            "PickVar",
            "HeaderFlag",
            "HeaderOut",
            "BodyFlag",
            "BodyOut",
            "ProcArg",
            "PosVar",
            "ClipVar",
            "ColourVar",
            "MappedVar",
        }
    )
    # The typedef never reads Param3, so its mapped source stays unused. The
    # conservative external-mapping fallback would mark it read and hide this.
    assert "UnusedMappedVar" in unused_names
