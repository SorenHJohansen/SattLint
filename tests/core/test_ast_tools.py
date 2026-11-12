from __future__ import annotations

from pathlib import Path

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.ast import BasePicture, BinOp, VarRef

from sattlint.core.ast_tools import iter_call_sites, iter_variable_refs

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "parser_surface" / "ParserSurfaceShapes.s"


def _parse_fixture() -> BasePicture:
    return parser_core_parse_source_text(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_iter_variable_refs_walks_parser_produced_modulecode() -> None:
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Counter = Counter + 1;
ENDDEF (*BasePicture*);
"""

    base_picture = parser_core_parse_source_text(code)

    refs = [ref.name for ref in iter_variable_refs(base_picture.modulecode)]

    assert refs == ["Counter", "Counter"]


def test_iter_variable_refs_reports_bound_tail_names() -> None:
    refs = {ref.name for ref in iter_variable_refs(_parse_fixture())}

    assert {"TextVar", "PickVar", "ProcArg", "Flag"} <= refs
    assert {"PosVar", "ClipVar", "OutVal"} <= refs


def test_iter_variable_refs_ignores_quoted_litstring_tails() -> None:
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Info: integer := 0;
SUBMODULES
   Child Invocation
      ( 0.0 : InVar_ LitString "Info" , 0.0 , 0.0 , 0.5 , 0.5 ) : MODULEDEFINITION
   MODULEPARAMETERS
      P: integer ;
   ModuleDef
   ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
   ENDDEF (*Child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    base_picture = parser_core_parse_source_text(code)

    assert "Info" not in {ref.name for ref in iter_variable_refs(base_picture)}


def test_iter_call_sites_reports_function_and_procedure_calls() -> None:
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Counter = Abs_(-1);
        Abs_(Counter);
ENDDEF (*BasePicture*);
"""

    base_picture = parser_core_parse_source_text(code)

    sites = list(iter_call_sites(base_picture))

    assert sites == [
        ("function", "Abs_", (-1,)),
        ("function", "Abs_", (VarRef("Counter"),)),
    ]


def test_iter_call_sites_reports_a_procedure_call_with_an_expression_argument() -> None:
    sites = list(iter_call_sites(_parse_fixture()))

    procedure_sites = [site for site in sites if site[0] == "procedure"]

    assert len(procedure_sites) == 1
    _kind, name, args = procedure_sites[0]
    assert name == "ToggleWindow"
    assert len(args) == 1
    assert isinstance(args[0], BinOp)
    assert isinstance(args[0].left, VarRef)
    assert args[0].left.name == "ProcArg"
