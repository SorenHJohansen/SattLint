# pyright: reportUnknownVariableType=false
# ruff: noqa: F403, F405
from ._parser_core_test_support import *


def test_parser_core_accepts_clipping_bounds_and_interact_tail_sequences():
    code = (
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "ModuleDef\n"
        '    ClippingBounds = ( -1.0 , -3.12 : InVar_ "PanelResize" '
        "ClippingBounds = -2.33 -3.12 0.0 : InVar_ 0.0 100.0 : InVar_ "
        "1.0 ) ( 1.0 , 0.22 )\n"
        "    InteractObjects :\n"
        "        TextBox_ ( 0.02 , 1.165 ) ( 0.48 , 1.245 )\n"
        "            Real_Value\n"
        '            "" : InVar_ LitString "+L2" 0\n'
        '            Variable = 0.0 : OutVar_ "Plant.Real1"\n'
        "            OpMin = 0.0 : InVar_ -1.0E+10\n"
        "            OpMax = 100.0 : InVar_ 1.0E+10\n"
        '            Event_Text_ = "" : InVar_ LitString "Real1"\n'
        '            Event_Severity_ = 0 : InVar_ "Severity"\n'
        "            LeftAligned Abs_ Decimal_\n"
        "ENDDEF (*BasePicture*);\n"
    )

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.moduledef is not None
    assert bp.moduledef.interact_objects is not None
    assert len(bp.moduledef.interact_objects) == 1


def test_parser_core_preserves_interact_outvar_tails_for_output_bindings():
    code = (
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "LOCALVARIABLES\n"
        "    Changed: boolean := False;\n"
        "ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    InteractObjects :\n"
        "        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )\n"
        '            Value_Changed = True : OutVar_ "Changed"\n'
        "ENDDEF (*BasePicture*);\n"
    )

    bp = parser_core_parse_source_text(code)

    assert bp.moduledef is not None
    assert bp.moduledef.interact_objects is not None
    interact = bp.moduledef.interact_objects[0]
    body = interact.properties[const.KEY_BODY]
    tails: list[Any] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
            return
        if isinstance(value, list):
            for nested in value:
                visit(nested)
            return
        if getattr(value, "data", None) == parser_const.GRAMMAR_VALUE_OUTVAR_PREFIX:
            tails.append(value)
            return
        children = getattr(value, "children", None)
        if isinstance(children, list):
            for child in children:
                visit(child)

    visit(body)

    assert len(tails) == 1
    assert tails[0].children == ["Changed"]


def test_parser_core_accepts_interact_flag_plus_textobject_assignment():
    code = (
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    InteractObjects :\n"
        "        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )\n"
        '            Abs_ TextObject = "" : InVar_ LitString "Start Sim"\n'
        "ENDDEF (*BasePicture*);\n"
    )

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.moduledef is not None
    assert bp.moduledef.interact_objects is not None
    assert len(bp.moduledef.interact_objects) == 1


def test_parser_core_accepts_combutproc_mixed_plain_and_tailed_args():
    code = (
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "ModuleDef\n"
        "    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "    InteractObjects :\n"
        "        ComButProc_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )\n"
        "            ToggleWindow\n"
        '            "" : InVar_ LitString "-+GainPanel" '
        '"" : InVar_ LitString "Calibration"\n'
        "            False : InVar_ True 0.0 0.0 0.0 : InVar_ 0.23 0.0 "
        "False 0 0 False 0\n"
        "            Variable = 0.0\n"
        "ENDDEF (*BasePicture*);\n"
    )

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.moduledef is not None
    assert bp.moduledef.interact_objects is not None
    assert len(bp.moduledef.interact_objects) == 1


def test_parser_core_parse_source_text_accepts_valid_source():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        A = A + 1;
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.name == "BasePicture"


def test_parser_core_accepts_combining_mark_identifier():
    identifier = "Cafe\u0301"
    code = f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    {identifier}: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        {identifier} = {identifier} + 1;
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.localvariables[0].name == identifier


def test_parser_core_accepts_replacement_character_in_identifier():
    identifier = "UdluftDr\ufffdnTime"
    code = f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    {identifier}: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        {identifier} = {identifier} + 1;
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.localvariables[0].name == identifier


def test_parser_core_sets_sequence_control_and_timer_flags():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION Tr1 WAIT_FOR False
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.modulecode is not None
    assert bp.modulecode.sequences is not None
    seq = bp.modulecode.sequences[0]
    assert seq.seqcontrol is True
    assert seq.seqtimer is True


def test_parser_core_emits_declaration_and_reference_spans():
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
""".strip()

    bp = parser_core_parse_source_text(code)
    declared = bp.localvariables[0]
    assert bp.modulecode is not None
    assert bp.modulecode.equations is not None
    assignment = bp.modulecode.equations[0].code[0]
    target = assignment[1]
    value_ref = assignment[2][1]

    assert declared.declaration_span is not None
    assert declared.declaration_span.line == 6
    assert declared.declaration_span.column == 5
    assert bp.header.declaration_span is not None
    assert bp.header.declaration_span.line == 4
    assert target["span"].line == 11
    assert target["span"].column == 9
    assert value_ref["span"].line == 11
    assert value_ref["span"].column == 19


def test_parser_core_preserves_invar_tails_in_invoke_coords_and_clipping_bounds():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0 : InVar_ "PosX",0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    PosX: integer := 0;
    PanelResize: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 : InVar_ "PanelResize" ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.header.invoke_coord_tails == ["PosX"]
    assert bp.moduledef is not None
    assert bp.moduledef.properties[const.KEY_TAILS] == ["PanelResize"]


def test_parser_core_preserves_outvar_tails_in_module_invocation_arguments():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Allow: PrivilegeType := 0;
SUBMODULES
    Child Invocation (0.1,0.1,0.0,0.9,0.9 Module_In_View = True : OutVar_ "Allow.RecpSupParameters") : ChildType;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert len(bp.submodules) == 1
    child = bp.submodules[0]
    assert isinstance(child, ModuleTypeInstance)
    assert child.header.invoke_coord_tails == ["Allow.RecpSupParameters"]


def test_parser_core_parses_nested_submodule_fixture_through_split_module_mixins():
    fixture_path = _repo_path("tests", "fixtures", "corpus", "valid", "NestedSubmodules.s")

    bp = parser_core_parse_source_text(fixture_path.read_text(encoding="utf-8"))

    assert [moduletype.name for moduletype in bp.moduletype_defs] == ["MiddleType"]
    assert len(bp.submodules) == 1
    middle = bp.submodules[0]
    assert isinstance(middle, ModuleTypeInstance)
    assert middle.moduletype_name == "MiddleType"
    middle_type = bp.moduletype_defs[0]
    assert [sub.header.name for sub in middle_type.submodules] == ["Inner"]
    assert middle_type.moduledef is not None
    assert middle_type.modulecode is not None
