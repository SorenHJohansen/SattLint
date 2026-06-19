# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false
# ruff: noqa: F403, F405
import logging

from ._parser_core_test_support import *


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

        def __str__(self) -> LiteralString:
            return "Unexpected end of input"

    class FakeUnexpectedToken(UnexpectedToken):
        def __init__(self) -> None:
            self._expected_reads = 0
            object.__setattr__(self, "token", "BADTOKEN")

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


def test_unexpected_input_summary_appends_expected_items_when_present_on_first_read():
    class FakeUnexpectedInput(UnexpectedEOF):
        def __init__(self) -> None:
            pass

        expected = cast(Any, {"BETA", "ALPHA"})

        def __str__(self) -> LiteralString:
            return "Unexpected parse issue"

    summary = parser_api._unexpected_input_summary(FakeUnexpectedInput())

    assert summary == "Unexpected parse issue. Expected one of: ALPHA, BETA"


def test_describe_parse_error_includes_context_for_unexpected_input():
    class FakeUnexpectedInput(UnexpectedEOF):
        def __init__(self) -> None:
            pass

        line = 4
        column = 9
        expected = cast(Any, {"ENDIF"})

        def __str__(self) -> LiteralString:
            return "Unexpected end of input"

        def get_context(self, text: str, span: int = 40) -> str:
            assert text == "IF X THEN"
            assert span == 40
            return "line context\n"

    details = parser_api.describe_parse_error(FakeUnexpectedInput(), "IF X THEN")

    assert details == parser_api.ParseErrorDetails(
        message="Unexpected end of input. Expected one of: ENDIF\nline context",
        line=4,
        column=9,
    )


def test_describe_parse_error_falls_back_to_plain_exception_message():
    class PlainFailureError(Exception):
        def __init__(self) -> None:
            super().__init__("plain failure")
            self.line = 7
            self.column = 11

    details = parser_api.describe_parse_error(PlainFailureError(), "ignored")

    assert details.message == "plain failure"
    assert details.line == 7
    assert details.column == 11


def test_describe_parse_error_remaps_locations_from_inline_comment_stripped_source():
    source = """\
\"SyntaxVersion\"
\"OriginalFileDate\"
\"ProgramDate\"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        DemoValue = 1; (* inline comment *) ???
ENDDEF (*BasePicture*);
"""
    stripped = parser_api.strip_sl_comments(source)
    cleaned_line = stripped.splitlines()[8]
    cleaned_column = cleaned_line.index("?") + 1
    original_column = source.splitlines()[8].index("?") + 1

    class FakeUnexpectedInput(UnexpectedEOF):
        def __init__(self) -> None:
            pass

        line = 9
        column = cleaned_column
        expected = cast(Any, {"NAME"})

        def __str__(self) -> LiteralString:
            return "Unexpected end of input"

        def get_context(self, text: str, span: int = 40) -> str:
            raise AssertionError("mapped parse errors should render context from the original source")

    details = parser_api.describe_parse_error(FakeUnexpectedInput(), source)

    assert details.line == 9
    assert details.column == original_column
    assert "DemoValue = 1; (* inline comment *) ???" in details.message
    assert "^" in details.message


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
        "A = 1;",
        parser=cast(Any, FakeParser()),
        transformer=cast(Any, FakeTransformer()),
        debug=events.append,
    )

    assert result is basepic
    assert events == [
        "Parse OK, transforming with SLTransformer",
        "BasePicture does not allow dynamic attributes; parse tree not attached",
        "Transform result type: BasePicture",
    ]


def test_parse_source_text_raises_when_transformer_returns_non_basepicture(caplog):
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

    with (
        caplog.at_level(logging.ERROR, logger="SattLint"),
        pytest.raises(
            RuntimeError,
            match="Transform result is not BasePicture",
        ),
    ):
        parser_api.parse_source_text(
            "A = 1;",
            parser=cast(Any, FakeParser()),
            transformer=cast(Any, FakeTransformer()),
            debug=events.append,
        )

    assert events == ["Parse OK, transforming with SLTransformer"]
    record = caplog.records[-1]
    assert record.parser_stage == "transform"
    assert record.parser_path is None
    assert record.parser_context == "Transform result is not BasePicture; check transformer.start()"


def test_parse_source_file_logs_parse_failures_with_path(caplog, tmp_path):
    source_file = tmp_path / "BrokenProgram.s"
    source_file.write_text("IF X THEN", encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="SattLint"), pytest.raises(UnexpectedToken):
        parser_api.parse_source_file(source_file)

    record = caplog.records[-1]
    assert record.parser_stage == "parse"
    assert record.parser_path == str(source_file)
    assert record.parser_line == 1
    assert record.parser_column is not None
    assert "Unexpected" in record.parser_context


def test_strip_sl_comments_preserves_trailing_backslash_at_end_of_string():
    assert strip_sl_comments('"abc\\') == '"abc\\'


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
