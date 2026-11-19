# pyright: reportPrivateUsage=false
"""Frame-module scope parity between the analyzer and the semantic snapshot."""

from __future__ import annotations

from dataclasses import replace

from sattline_parser import parse_source_text as parser_core_parse_source_text

from sattlint.analyzers.variables import VariablesAnalyzer
from sattlint.core._semantic_index import SemanticIndexBuilder
from sattlint.models.project_graph import program_identity
from sattlint.parser_api import BasePicture, FrameModule, Variable
from sattlint.resolution import CanonicalSymbolTable, ContextBuilder, TypeGraph
from sattlint.resolution.context_builder import build_frame_scope

FRAME_SCOPE_SOURCE = """
"Syntax version 2.23, date: 2026-06-19-12:00:00.000 N"
"Original file date: ---"
"Program date: 2026-06-19-12:00:00.000, name: FrameScope"

BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
   Scoped: integer := 0;
SUBMODULES
   Panel Invocation
      ( 0.0 , 0.0 , 0.0 , 0.4 , 0.4
       ) : MODULEDEFINITION DateCode_ 2 ( Frame_Module )
   LOCALVARIABLES
      Scoped: integer := 1;
   ModuleDef
   ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
   GraphObjects :
      TextObject ( -1.0 , -1.0 ) ( 1.0 , 0.3 )
         "Info" VarName Width_ = 5 : InVar_ "Scoped"
         OutlineColour : Colour0 = -3
   ENDDEF (*Panel*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""


def _parse_frame_scope() -> BasePicture:
    return replace(parser_core_parse_source_text(FRAME_SCOPE_SOURCE), origin_file="FrameScope.s")


def _scoped_variables(base_picture: BasePicture) -> tuple[Variable, Variable]:
    parent_variable = (base_picture.localvariables or [])[0]
    frame = (base_picture.submodules or [])[0]
    assert isinstance(frame, FrameModule)
    frame_variable = (frame.localvariables or [])[0]
    return parent_variable, frame_variable


def test_frame_code_reads_the_frame_declaration_not_the_parent_one() -> None:
    base_picture = _parse_frame_scope()
    parent_variable, frame_variable = _scoped_variables(base_picture)

    analyzer = VariablesAnalyzer(base_picture)
    analyzer.run()

    assert analyzer._get_usage(frame_variable).read is True
    assert analyzer._get_usage(parent_variable).read is False

    root_path = (base_picture.header.name,)
    frame_context = analyzer.contexts_by_module_path[(*root_path, "Panel")]
    assert frame_context.env["scoped"] is frame_variable
    assert frame_context.param_mappings == {}
    assert frame_context.parent_context is analyzer.contexts_by_module_path[root_path]


def test_semantic_snapshot_attributes_frame_references_to_the_frame_declaration() -> None:
    base_picture = _parse_frame_scope()
    index = SemanticIndexBuilder(base_picture).build()

    program = program_identity(base_picture).casefold()
    frame_key = (program, "panel", "scoped")
    parent_key = (program, "scoped")

    assert frame_key in index.references_by_definition_key
    assert parent_key not in index.references_by_definition_key


def test_frame_scope_builder_keeps_the_frame_declarations_and_parent_chain() -> None:
    base_picture = _parse_frame_scope()
    parent_variable, frame_variable = _scoped_variables(base_picture)
    frame = (base_picture.submodules or [])[0]
    assert isinstance(frame, FrameModule)
    parent_context = ContextBuilder(
        base_picture=base_picture,
        symbol_table=CanonicalSymbolTable(collect=False),
        type_graph=TypeGraph.from_basepicture(base_picture),
        issues=[],
        global_lookup_fn=lambda _name: None,
    ).build_for_basepicture()

    context = build_frame_scope(frame, parent_context, [base_picture.header.name, "Panel"], ["Panel"])

    assert context.env == {"scoped": frame_variable}
    assert context.env["scoped"] is not parent_variable
    assert context.param_mappings == {}
    assert context.moduleparameter_keys == frozenset()
    assert context.current_library is parent_context.current_library
    assert context.parent_context is parent_context
