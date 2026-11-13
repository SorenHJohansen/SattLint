"""Quoted symbols in tails must not be treated as variable access."""

from __future__ import annotations

from sattline_parser import parse_source_text

from sattlint.analyzers.variables import VariablesAnalyzer

SOURCE = """
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


def test_quoted_litstring_tail_does_not_mark_a_read() -> None:
    base_picture = parse_source_text(SOURCE)
    analyzer = VariablesAnalyzer(base_picture, fail_loudly=False)
    analyzer.run()

    info = next(variable for variable in base_picture.localvariables if variable.name == "Info")
    usage = analyzer.get_usage(info)

    assert usage.read is False
    assert usage.written is False
