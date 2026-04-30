"""Tests for grammar coverage and parser-core behaviour.

Covers parse_source_text, source spans, flags, and identifier rules.
"""

import ast
from pathlib import Path

import pytest
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken

from sattline_parser import api as parser_api
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser import strip_sl_comments
from sattline_parser.models.ast_model import (
    BasePicture,
    ModuleHeader,
    ModuleTypeInstance,
)
from sattline_parser.transformer.sl_transformer import SLTransformer
from sattlint import constants as const
from sattlint.engine import (
    create_sl_parser,
    parse_source_file,
)


def _parse_to_basepicture(text: str):
    parser = create_sl_parser()
    tree = parser.parse(strip_sl_comments(text))
    return SLTransformer().transform(tree)


def _repo_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[1].joinpath(*parts)


def test_internal_modules_do_not_import_parser_compat_wrappers():
    repo_root = _repo_path()
    src_roots = (
        repo_root / "src" / "sattlint",
        repo_root / "src" / "sattlint_lsp",
    )
    allowed_wrapper_files = {
        repo_root / "src" / "sattlint" / "models" / "ast_model.py",
        repo_root / "src" / "sattlint" / "grammar" / "parser_decode.py",
        repo_root / "src" / "sattlint" / "transformer" / "sl_transformer.py",
    }
    forbidden_absolute = {
        "sattlint.models.ast_model",
        "sattlint.grammar.parser_decode",
        "sattlint.transformer.sl_transformer",
    }
    forbidden_relative = {
        "models.ast_model",
        "grammar.parser_decode",
        "transformer.sl_transformer",
    }

    violations: list[str] = []
    source_files: list[Path] = []
    for root in src_roots:
        source_files.extend(sorted(root.rglob("*.py")))

    for source_file in source_files:
        if source_file in allowed_wrapper_files:
            continue

        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        relative_path = source_file.relative_to(repo_root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in forbidden_absolute or (node.level > 0 and module in forbidden_relative):
                    violations.append(f"{relative_path}:{node.lineno} imports {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_absolute:
                        violations.append(f"{relative_path}:{node.lineno} imports {alias.name}")

    assert not violations, "Internal modules must import parser-core directly:\n" + "\n".join(violations)


def test_internal_modules_do_not_import_editor_api_compat_facade():
    repo_root = _repo_path()
    src_roots = (
        repo_root / "src" / "sattlint",
        repo_root / "src" / "sattlint_lsp",
    )
    allowed_wrapper_files = {
        repo_root / "src" / "sattlint" / "editor_api.py",
    }

    violations: list[str] = []
    source_files: list[Path] = []
    for root in src_roots:
        source_files.extend(sorted(root.rglob("*.py")))

    for source_file in source_files:
        if source_file in allowed_wrapper_files:
            continue

        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        relative_path = source_file.relative_to(repo_root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "sattlint.editor_api" or (node.level > 0 and module == "editor_api"):
                    violations.append(f"{relative_path}:{node.lineno} imports {module}")
                    continue
                if module == "sattlint":
                    for alias in node.names:
                        if alias.name == "editor_api":
                            violations.append(f"{relative_path}:{node.lineno} imports sattlint.editor_api")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "sattlint.editor_api":
                        violations.append(f"{relative_path}:{node.lineno} imports sattlint.editor_api")

    assert not violations, "Internal modules must import semantic-core directly:\n" + "\n".join(violations)


def test_ternary_if_has_lowest_precedence():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
    B: integer := 1;
    C: integer := 2;
    D: integer := 3;
    X: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        X = IF A > 0 THEN B ELSE C + D ENDIF;
ENDDEF (*BasePicture*);
"""
    bp = _parse_to_basepicture(code)
    stmt = bp.modulecode.equations[0].code[0]
    assert stmt[0] == const.KEY_ASSIGN

    expr = stmt[2]
    assert expr[0] == const.KEY_TERNARY

    else_expr = expr[2]
    assert else_expr[0] == const.KEY_ADD
    assert else_expr[1][const.KEY_VAR_NAME].casefold() == "c"
    assert else_expr[2][0][0] == "+"
    assert else_expr[2][0][1][const.KEY_VAR_NAME].casefold() == "d"


def test_quoted_identifier_length_is_limited_to_20_chars():
    long_name = "'QuotedIdentifierLength21'"  # 25 chars without quotes
    code = f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    {long_name}: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        {long_name} = 1;
ENDDEF (*BasePicture*);
"""
    parser = create_sl_parser()
    with pytest.raises(UnexpectedCharacters):
        parser.parse(strip_sl_comments(code))


def test_parse_source_file_accepts_valid_file(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
    B: integer := 1;
    C: integer := 2;
    D: integer := 3;
    X: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        X = IF A > 0 THEN B ELSE C + D ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ValidProgram.s"
    source_file.write_text(code, encoding="utf-8")

    bp = parse_source_file(source_file)

    assert bp.name == "BasePicture"


def test_parser_core_preserves_invocation_argument_flags():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0 IgnoreMaxModule) : MODULEDEFINITION DateCode_ 1
SUBMODULES
    Child Invocation (0.0,0.0,0.0,1.0,1.0 LayerModule) : ChildType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert bp.header.invocation_arguments == ("IgnoreMaxModule",)
    assert len(bp.submodules) == 1
    child = bp.submodules[0]
    assert isinstance(child, ModuleTypeInstance)
    assert child.header.invocation_arguments == ("LayerModule",)


def test_parser_core_reuses_default_parser(monkeypatch):
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

    call_count = 0
    real_create_parser = parser_api.create_parser
    parser_api._default_parser.cache_clear()

    def counting_create_parser():
        nonlocal call_count
        call_count += 1
        return real_create_parser()

    monkeypatch.setattr(parser_api, "create_parser", counting_create_parser)

    parser_api.parse_source_text(code)
    parser_api.parse_source_text(code)

    assert call_count == 1
    parser_api._default_parser.cache_clear()


def test_create_parser_uses_regex_and_disk_cache(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    cache_dir = tmp_path / "lark-cache"

    class DummyLark:
        def __init__(self, grammar, **options):
            captured["grammar"] = grammar
            captured["options"] = options

    monkeypatch.setattr(parser_api, "Lark", DummyLark)
    monkeypatch.setattr(parser_api, "_PARSER_CACHE_DIR", cache_dir)
    parser = parser_api.create_parser()

    assert isinstance(parser, DummyLark)
    options = captured["options"]
    assert isinstance(options, dict)
    assert options["regex"] is True
    assert options["cache_grammar"] is True
    assert Path(options["cache"]).parent == cache_dir
    assert options["parser"] == "lalr"


def test_create_sl_parser_delegates_to_create_parser(monkeypatch):
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_create_parser(*, strict: bool = False):
        captured["strict"] = strict
        return sentinel

    monkeypatch.setattr(parser_api, "create_parser", fake_create_parser)

    parser = parser_api.create_sl_parser(strict=True)

    assert parser is sentinel
    assert captured == {"strict": True}


def test_unexpected_input_summary_formats_eof_token_and_character_variants():
    class FakeUnexpectedEOF(UnexpectedEOF):
        def __init__(self) -> None:
            self._expected_reads = 0

        def __getattribute__(self, name: str):
            if name == "expected":
                reads = object.__getattribute__(self, "_expected_reads")
                object.__setattr__(self, "_expected_reads", reads + 1)
                if reads == 0:
                    return []
                return {"ENDDEF", "LOCALVARIABLES"}
            return object.__getattribute__(self, name)

        def __str__(self) -> str:
            return "Unexpected end of input"

    class FakeUnexpectedToken(UnexpectedToken):
        def __init__(self) -> None:
            self._expected_reads = 0
            self.token = "BADTOKEN"

        def __getattribute__(self, name: str):
            if name == "expected":
                reads = object.__getattribute__(self, "_expected_reads")
                object.__setattr__(self, "_expected_reads", reads + 1)
                if reads == 0:
                    return []
                return {"ENDDEF", "LOCALVARIABLES"}
            return object.__getattribute__(self, name)

        def __str__(self) -> str:
            return "Unexpected token BADTOKEN"

    class FakeUnexpectedCharacters(UnexpectedCharacters):
        def __init__(self) -> None:
            pass

        def __str__(self) -> str:
            return "Invalid character."

    eof_summary = parser_api._unexpected_input_summary(FakeUnexpectedEOF())
    token_summary = parser_api._unexpected_input_summary(FakeUnexpectedToken())
    char_summary = parser_api._unexpected_input_summary(FakeUnexpectedCharacters())

    assert eof_summary == "Unexpected end of input. Expected one of: ENDDEF, LOCALVARIABLES"
    assert token_summary == "Unexpected token 'BADTOKEN'. Expected one of: ENDDEF, LOCALVARIABLES"
    assert char_summary == "Invalid character"


def test_describe_parse_error_falls_back_to_plain_exception_message():
    class PlainFailure(Exception):
        def __init__(self) -> None:
            super().__init__("plain failure")
            self.line = 7
            self.column = 11

    details = parser_api.describe_parse_error(PlainFailure(), "ignored")

    assert details.message == "plain failure"
    assert details.line == 7
    assert details.column == 11


def test_read_text_with_fallback_accepts_cp1252_bytes(tmp_path):
    source_file = tmp_path / "cp1252.k"
    source_file.write_bytes("Søren".encode("cp1252"))

    assert parser_api.read_text_with_fallback(source_file) == "Søren"


def test_read_text_with_fallback_falls_back_to_latin1(tmp_path):
    source_file = tmp_path / "latin1.bin"
    source_file.write_bytes(b"\x81A")

    assert parser_api.read_text_with_fallback(source_file) == "\x81A"


def test_load_source_text_decodes_compressed_sources_and_emits_debug(monkeypatch, tmp_path):
    events: list[str] = []

    monkeypatch.setattr(parser_api, "_read_text_simple", lambda path: "compressed-body")
    monkeypatch.setattr(parser_api, "is_compressed", lambda text: text == "compressed-body")
    monkeypatch.setattr(parser_api, "preprocess_sl_text", lambda text: ("decoded-source", {"kind": "compressed"}))

    loaded = parser_api.load_source_text(tmp_path / "Program.s", debug=events.append)

    assert loaded == "decoded-source"
    assert events == [
        f"Parsing file: {tmp_path / 'Program.s'}",
        "Compressed format detected; decoding before parsing",
    ]


def test_parse_source_text_reports_parse_tree_attach_failure(monkeypatch):
    events: list[str] = []
    tree = object()
    basepic = BasePicture(header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)))

    class FakeParser:
        def parse(self, text: str):
            assert text == "A = 1;"
            return tree

    class FakeTransformer:
        def transform(self, payload):
            assert payload is tree
            return basepic

    def guarded_setattr(self, name, value):
        if name == "parse_tree":
            raise AttributeError("read-only")
        object.__setattr__(self, name, value)

    monkeypatch.setattr(BasePicture, "__setattr__", guarded_setattr)
    result = parser_api.parse_source_text(
        "A = 1;", parser=FakeParser(), transformer=FakeTransformer(), debug=events.append
    )

    assert result is basepic
    assert events == [
        "Parse OK, transforming with SLTransformer",
        "BasePicture does not allow dynamic attributes; parse tree not attached",
        "Transform result type: BasePicture",
    ]


def test_parse_source_text_raises_when_transformer_returns_non_basepicture():
    events: list[str] = []
    tree = object()

    class FakeParser:
        def parse(self, text: str):
            assert text == "A = 1;"
            return tree

    class FakeTransformer:
        def transform(self, payload):
            assert payload is tree
            return "not-a-basepicture"

    with pytest.raises(RuntimeError, match="Transform result is not BasePicture"):
        parser_api.parse_source_text("A = 1;", parser=FakeParser(), transformer=FakeTransformer(), debug=events.append)

    assert events == [
        "Parse OK, transforming with SLTransformer",
        "BasePicture does not allow dynamic attributes; parse tree not attached",
        "Transform result type: str",
    ]


def test_parser_core_strict_mode_compiles_cleanly():
    parser = parser_api.create_parser(strict=True)

    assert parser is not None


def test_parser_core_accepts_outline_colour_assignment_invar_tail():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    WidthSource: integer := 0;
    FormatSource: integer := 0;
    ColourSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
            Format_String_ = "" : InVar_ "FormatSource"
            OutlineColour : Colour0 = 5 : InVar_ "ColourSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)

    assert isinstance(bp, BasePicture)
    assert bp.moduledef is not None


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
