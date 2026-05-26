# ruff: noqa: F403, F405
from sattline_parser.utils.text_processing import CommentStrippedText

from ._parser_core_test_support import *


def test_sl_transformer_top_level_helpers_cover_header_quote_and_tree_iteration_edges():
    header_lines = Tree(
        "header_lines",
        [
            Tree("original_file_date_line", [Token("STRING", '"ignored"')]),
            Tree("program_date_line", [Token("STRING", '"2026-04-30, name: UnitProgram"')]),
        ],
    )
    nested_tree = Tree(
        parser_const.TREE_TAG_MODULE_BODY,
        ["beta", Tree(parser_const.TREE_TAG_BASE_MODULE_BODY, ["gamma"])],
    )

    assert _sl_meta_span(SimpleNamespace(line=9, column=3)) == SourceSpan(line=9, column=3)
    assert _sl_meta_span(SimpleNamespace(line=None, column=3)) is None
    assert _extract_program_name_from_header_lines(header_lines) == "UnitProgram"
    assert (
        _extract_program_name_from_header_lines(
            Tree("header_lines", [Tree("program_date_line", [Token("STRING", '"no name here"')])])
        )
        is None
    )
    spaced_header_lines = Tree(
        "header_lines",
        [Tree("program_date_line", [Token("STRING", '"2026-04-30, variant: demo, Name: Spaced Program"')])],
    )
    assert _extract_program_name_from_header_lines(spaced_header_lines) == "Spaced Program"
    assert _strip_quoted('"He said ""Hi""\n"') == 'He said "Hi"'
    assert _strip_quoted("plain-text") == "plain-text"
    assert _sl_is_tree(nested_tree) is True
    assert _sl_is_tree("not-a-tree") is False
    assert list(_sl_flatten_items(["alpha", ["delta"], nested_tree])) == ["alpha", "delta", "beta", "gamma"]
    assert list(_iter_tree_children(Tree("wrapper", ["alpha", "beta"]))) == ["alpha", "beta"]
    assert list(_iter_tree_children("not-a-tree")) == []


def test_strip_sl_comments_with_mapping_remaps_inline_comment_columns():
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

    stripped = strip_sl_comments_with_mapping(source)
    cleaned_line = stripped.text.splitlines()[8]
    cleaned_column = cleaned_line.index("?") + 1

    assert stripped.map_line_column(9, cleaned_column) == (9, source.splitlines()[8].index("?") + 1)


def test_strip_sl_comments_with_mapping_handles_crlf_nested_comments_and_string_edges():
    source = '"unterminated\rA\r\n"He said ""Hi""" "A\\B" (* outer\r\n(* inner *)\ncomment *)\r\n   ;\rNext = 1;\n'

    stripped = strip_sl_comments_with_mapping(source)

    assert strip_sl_comments(source) == stripped.text
    assert '"unterminated\rA\r\n' in stripped.text
    assert '"He said ""Hi""" "A\\B" ' in stripped.text
    assert "(*" not in stripped.text
    assert stripped.text.endswith("\r\n   \rNext = 1;\n")


def test_comment_stripped_text_map_line_column_covers_bounds_and_fallbacks():
    source = "Alpha\r\nBeta (* comment *) Gamma"
    stripped = strip_sl_comments_with_mapping(source)
    cleaned_line = stripped.text.splitlines()[1]
    gamma_column = cleaned_line.index("Gamma") + 1

    assert stripped.map_line_column(None, 2) == (None, 2)
    assert stripped.map_line_column(0, 0) == (0, 0)
    assert stripped.map_line_column(99, 1) == (99, 1)
    assert stripped.map_line_column(2, gamma_column) == (2, source.splitlines()[1].index("Gamma") + 1)
    assert stripped.map_line_column(2, 999) == (2, len(source.splitlines()[1]) + 1)

    fallback = CommentStrippedText(
        text="A",
        cleaned_offsets_to_original=(0, 1),
        original_line_starts=(),
        cleaned_line_starts=(0,),
    )
    assert fallback.map_line_column(1, 1) == (1, 1)


def test_sl_transformer_helper_methods_cover_nested_tail_and_payload_collection():
    transformer = SLTransformer()
    variable_tail = {parser_const.KEY_VAR_NAME: "ScanGroup"}
    tuple_tail = ("Group", 3)

    tails = transformer._extract_coord_tails(
        [
            None,
            Token("NAME", "IgnoredToken"),
            IntLiteral(1),
            FloatLiteral(2.5),
            True,
            "TailText",
            (1.0, 2.0),
            tuple_tail,
            variable_tail,
            {"nested": ["NestedTail", {"deep": "DeepTail"}]},
            [Tree("inner", ["TreeTail"])],
        ]
    )

    assert tails == ["TailText", tuple_tail, variable_tail, "NestedTail", "DeepTail", "TreeTail"]
    assert transformer._merge_tails(["Left"], [], ["Right"]) == ["Left", "Right"]
    assert transformer._extract_coord_payloads(
        [
            {parser_const.KEY_COORDS: (1.0, 2.0), parser_const.KEY_TAILS: ["CoordTail"]},
            (3.0, 4.0),
            "ignored",
        ]
    ) == ([(1.0, 2.0), (3.0, 4.0)], ["CoordTail"])


def test_sl_transformer_tailed_rule_and_start_paths_cover_enable_payloads_and_errors():
    transformer = SLTransformer()
    enable_expr = Tree(parser_const.KEY_ENABLE_EXPRESSION, ["Enabled"])
    dict_payload = {"payload": "Width"}

    assert transformer._extract_tailed_rule_payload("plain") is None
    assert (
        transformer._extract_tailed_rule_payload(Tree("format_string_tailed", [Token("COMMA", ","), enable_expr]))
        is enable_expr
    )
    assert (
        transformer._extract_tailed_rule_payload(Tree("width_tailed", [Token("COMMA", ","), dict_payload]))
        == dict_payload
    )
    assert transformer._extract_tailed_rule_payload(Tree("width_tailed", [Token("COMMA", ",")])) is None

    invar_tree = Tree(parser_const.GRAMMAR_VALUE_INVAR_PREFIX, [])
    tail_tree = Tree("invar_tail", [])
    tailed_rule = Tree("format_string_tailed", [Token("COMMA", ","), {"payload": "FormatTail"}])
    collected = transformer._collect_invar_enable_tails(
        [
            {parser_const.KEY_TAIL: "PlainTail", "nested": [invar_tree]},
            {parser_const.TREE_TAG_ENABLE: True, parser_const.KEY_TAIL: "EnabledTail"},
            Tree("outer", cast(list[Any], [enable_expr, tail_tree, tailed_rule])),
            [None],
        ]
    )

    assert "PlainTail" in collected
    assert "EnabledTail" in collected
    assert invar_tree in collected
    assert enable_expr in collected
    assert tail_tree in collected
    assert {"payload": "FormatTail"} in collected

    base_picture = BasePicture(header=_module_header("BasePicture"))
    started = transformer.start(
        [
            Tree("header_lines", [Tree("program_date_line", [Token("STRING", '"2026-04-30, name: Starter"')])]),
            base_picture,
        ]
    )

    assert started is base_picture
    assert started.program_name == "Starter"
    with pytest.raises(ValueError, match="start expected a BasePicture"):
        transformer.start([Tree("header_lines", []), "missing-base-picture"])


def test_tokens_mixin_coerces_supported_terminals_and_keywords():
    mixin = _TokensHarness()
    signed_int = Token("SIGNED_INT", "-7", line=4, column=2)
    real_value = Token("REAL", "3.25", line=8, column=6)

    assert mixin._unwrap_token(Token("NAME", "Motor")) == "Motor"
    assert mixin._unwrap_token("AlreadyString") == "AlreadyString"
    assert mixin.NAME(Token("NAME", "Valve")) == "Valve"
    assert mixin.STRING(Token("STRING", '"He said ""Hi""\n"')) == 'He said "Hi"'
    assert mixin.STRING(Token("STRING", "bare-text")) == "bare-text"
    assert mixin.STRING_CRLF(Token("STRING_CRLF", '"Line"\n')) == '"Line"'
    assert mixin.STRING_NOTAIL(Token("STRING_NOTAIL", '"Tail"')) == "Tail"

    assert mixin.SIGNED_INT(signed_int) == IntLiteral(-7, SourceSpan(line=4, column=2))
    assert mixin.SIGNED_INT_NOTAIL(signed_int) == IntLiteral(-7, SourceSpan(line=4, column=2))
    assert mixin.REAL(real_value) == FloatLiteral(3.25, SourceSpan(line=8, column=6))
    assert mixin.REAL_NOTAIL(real_value) == FloatLiteral(3.25, SourceSpan(line=8, column=6))
    assert mixin.BOOL(Token("BOOL", parser_const.GRAMMAR_VALUE_BOOL_TRUE)) is True
    assert mixin.BOOL_NOTAIL(Token("BOOL_NOTAIL", parser_const.GRAMMAR_VALUE_BOOL_FALSE)) is False

    assert mixin.GLOBAL_KW(None) is True
    assert mixin.CONST_KW(None) == "Const"
    assert mixin.STATE_KW(None) == "State"
    assert mixin.OPSAVE_KW(None) == "OpSave"
    assert mixin.SECURE_KW(None) == "Secure"
    assert mixin.DEFAULT(None) is DEFAULT_INIT
    assert mixin.COLON(None) is None
    assert mixin.COMMA(None) is None
    assert mixin.SEMI(None) is None
    assert mixin.ASSIGN_INIT_VALUE(None) is None
    assert mixin.DURATION_VALUE(None) == parser_const.GRAMMAR_VALUE_DURATION_VALUE


def test_tokens_mixin_rejects_invalid_bool_and_bad_datecode_tokens():
    mixin = _TokensHarness()

    with pytest.raises(ValueError, match="BOOL expected"):
        mixin.BOOL(Token("BOOL", "Maybe"))

    assert mixin.sl_datecode([12, Token(parser_const.KEY_SL_DATECODE, "99")]) == 12
    assert mixin.sl_datecode([Token(parser_const.KEY_SL_DATECODE, "20260430")]) == 20260430

    with pytest.raises(ValueError, match="Invalid SL_DATECODE value"):
        mixin.sl_datecode([Token(parser_const.KEY_SL_DATECODE, "invalid")])

    with pytest.raises(ValueError, match="sl_datecode expected"):
        mixin.sl_datecode([Token("NAME", "NoDateCode")])


def test_expressions_mixin_coerces_values_and_builds_expression_tuples():
    mixin = _ExpressionsHarness()

    assert mixin.value([True]) is True
    with pytest.raises(ValueError, match="got empty list"):
        mixin.value([])
    with pytest.raises(ValueError, match="expected exactly one item"):
        mixin.value([1, 2])
    with pytest.raises(ValueError, match="item is None"):
        mixin.value([None])

    assert mixin.connected_variable([Token("NAME", "ignored"), "Motor.Speed"]) == "Motor.Speed"
    assert mixin.invar_tail([Token("NAME", "ignored"), {"tail": "InVar_1"}]) == {"tail": "InVar_1"}
    with pytest.raises(ValueError, match="connected_variable expected"):
        mixin.connected_variable([Token("NAME", "OnlyToken")])
    with pytest.raises(ValueError, match="invar_tail expected"):
        mixin.invar_tail([Token("NAME", "OnlyToken")])

    assert mixin.or_expression(["lhs"]) == "lhs"
    assert mixin.or_expression(["lhs", Token("OR", "OR"), "rhs"]) == (
        parser_const.GRAMMAR_VALUE_OR,
        ["lhs", "rhs"],
    )
    assert mixin.and_expression(["lhs"]) == "lhs"
    assert mixin.and_expression(["lhs", Token("AND", "AND"), "rhs"]) == (
        parser_const.GRAMMAR_VALUE_AND,
        ["lhs", "rhs"],
    )
    assert mixin.not_expression(["expr"]) == "expr"
    assert mixin.not_expression([Token("NOT", "NOT"), "expr"]) == (parser_const.GRAMMAR_VALUE_NOT, "expr")
    assert mixin.not_expression([Token("NOT", "NOT")]) == Token("NOT", "NOT")

    assert mixin.compare(["lhs"]) == "lhs"
    assert mixin.compare([]) is None
    assert mixin.compare(["lhs", Token("EQ", "="), "rhs", Token("NE", "<>"), "other"]) == (
        parser_const.KEY_COMPARE,
        "lhs",
        [("=", "rhs"), ("<>", "other")],
    )
    assert mixin.additive_expression(["lhs", Token("PLUS", "+"), "rhs"]) == (
        parser_const.KEY_ADD,
        "lhs",
        [("+", "rhs")],
    )
    assert mixin.multiplicative_expression(["lhs", Token("STAR", "*"), "rhs"]) == (
        parser_const.KEY_MUL,
        "lhs",
        [("*", "rhs")],
    )
    assert mixin.compare(["lhs", Token("EQ", "=")]) == "lhs"


def test_expressions_mixin_builds_statements_calls_and_conditionals():
    mixin = _ExpressionsHarness()

    assert mixin.unary_expression(["expr"]) == "expr"
    assert mixin.unary_expression([Token(parser_const.KEY_MINUS, "-"), "expr"]) == (parser_const.KEY_MINUS, "expr")
    assert mixin.unary_expression([Token("PLUS", "+"), "expr"]) == ("+", "expr")
    assert mixin.not_expression([Token("NOT", "NOT"), Token("PLUS", "+")]) == Token("PLUS", "+")
    assert mixin.additive_expression([Token("PLUS", "+")]) is None
    assert mixin.additive_expression(["lhs", Token("PLUS", "+"), "rhs", Token("PLUS", "+")]) == (
        parser_const.KEY_ADD,
        "lhs",
        [("+", "rhs")],
    )
    assert mixin.multiplicative_expression([Token("STAR", "*")]) is None
    assert mixin.multiplicative_expression(["lhs", Token("STAR", "*"), "rhs", Token("STAR", "*")]) == (
        parser_const.KEY_MUL,
        "lhs",
        [("*", "rhs")],
    )
    assert mixin.compare(["lhs", Token("EQ", "="), "rhs", Token("NE", "<>")]) == (
        parser_const.KEY_COMPARE,
        "lhs",
        [("=", "rhs")],
    )
    with pytest.raises(ValueError, match="expected operator and expression"):
        mixin.unary_expression([Token("PLUS", "+"), Token("MINUS", "-")])

    assert mixin.argument_list(["a", Token("COMMA", ","), "b"]) == ["a", "b"]
    assert mixin.function_call(["Fn", ["arg"]]) == (parser_const.KEY_FUNCTION_CALL, "Fn", ["arg"])
    assert mixin.function_call(["Fn", Token("LPAREN", "("), ["arg1", "arg2"], Token("RPAREN", ")")]) == (
        parser_const.KEY_FUNCTION_CALL,
        "Fn",
        ["arg1", "arg2"],
    )
    assert mixin.assignment_statement(["Target", "Value"]) == (parser_const.KEY_ASSIGN, "Target", "Value")
    assert mixin.assignment_statement(["Target", Token("EQUAL", "="), "Value"]) == (
        parser_const.KEY_ASSIGN,
        "Target",
        "Value",
    )

    ternary_items = [
        Token(parser_const.GRAMMAR_VALUE_IF, "IF"),
        "cond1",
        Token("THEN", "THEN"),
        "value1",
        Token(parser_const.GRAMMAR_VALUE_ELSIF, "ELSIF"),
        "cond2",
        Token("THEN", "THEN"),
        "value2",
        Token(parser_const.GRAMMAR_VALUE_ELSE, "ELSE"),
        "fallback",
        Token(parser_const.GRAMMAR_VALUE_ENDIF, "ENDIF"),
    ]
    assert mixin.ternary_if(ternary_items) == (
        parser_const.KEY_TERNARY,
        [("cond1", "value1"), ("cond2", "value2")],
        "fallback",
    )

    if_items = [
        Token(parser_const.GRAMMAR_VALUE_IF, "IF"),
        "cond1",
        Token("THEN", "THEN"),
        "stmt1",
        Token(parser_const.GRAMMAR_VALUE_ELSIF, "ELSIF"),
        "cond2",
        Token("THEN", "THEN"),
        "stmt2",
        Token(parser_const.GRAMMAR_VALUE_ELSE, "ELSE"),
        "stmt3",
        Token(parser_const.GRAMMAR_VALUE_ENDIF, "ENDIF"),
    ]
    assert mixin.if_statement(if_items) == (
        parser_const.GRAMMAR_VALUE_IF,
        [("cond1", ["stmt1"]), ("cond2", ["stmt2"])],
        ["stmt3"],
    )
    assert mixin.if_statement([Token("IGNORED", "?"), *if_items]) == (
        parser_const.GRAMMAR_VALUE_IF,
        [("cond1", ["stmt1"]), ("cond2", ["stmt2"])],
        ["stmt3"],
    )
    assert mixin.statement([Token("IGNORED", "?"), "assignment"]) == Tree(parser_const.KEY_STATEMENT, ["assignment"])
    with pytest.raises(ValueError, match="statement expected a non-Token child"):
        mixin.statement([Token("ONLY", "token")])
    with pytest.raises(ValueError, match="statement expected a non-Token child"):
        mixin.statement([])


def test_sfc_mixin_builds_modulecode_sequences_and_equations():
    mixin = _SFCHarness()
    code_blocks = mixin.code_blocks([{"enter": ["enter1"]}, {"active": ["active1"]}, {"exit": ["exit1"]}])
    init_step = mixin.seqinitstep([Token("SEQINITSTEP", "SEQINITSTEP"), "Init", code_blocks])
    step = mixin.seqstep([Token("SEQSTEP", "SEQSTEP"), "Run", code_blocks])
    transition = mixin.seqtransition(
        [Token("SEQTRANSITION", "SEQTRANSITION"), "Gate", Token("WAIT_FOR", "WAIT_FOR"), True]
    )
    anonymous_transition = mixin.seqtransition(
        [Token("SEQTRANSITION", "SEQTRANSITION"), Token("WAIT_FOR", "WAIT_FOR"), False]
    )
    body_tree = mixin.sequence_body([init_step, transition])

    assert code_blocks == SFCCodeBlocks(enter=["enter1"], active=["active1"], exit=["exit1"])
    assert init_step == SFCStep(kind="init", name="Init", code=code_blocks)
    assert step == SFCStep(kind="step", name="Run", code=code_blocks)
    assert transition == SFCTransition(name="Gate", condition=True)
    assert anonymous_transition == SFCTransition(name=None, condition=False)
    assert mixin.seqtransitionsub(
        [Token("SUBSEQTRANSITION", "SUBSEQTRANSITION"), "SubGate", body_tree, Token("ENDSUBSEQTRANSITION", "END")]
    ) == SFCTransitionSub(name="SubGate", body=[init_step, transition])
    assert mixin.seqsub(
        [Token("SUBSEQUENCE", "SUBSEQUENCE"), "SubA", body_tree, Token("ENDSUBSEQUENCE", "END")]
    ) == SFCSubsequence(
        name="SubA",
        body=[init_step, transition],
    )
    assert mixin.seqalternative([Token("ALT", "ALT"), body_tree, mixin.sequence_body([SFCBreak()])]) == SFCAlternative(
        branches=[[init_step, transition], [SFCBreak()]]
    )
    assert mixin.seqparallel(
        [Token("PAR", "PAR"), body_tree, mixin.sequence_body([SFCFork(target="Other")])]
    ) == SFCParallel(branches=[[init_step, transition], [SFCFork(target="Other")]])
    assert mixin.seqfork([Token("SEQFORK", "SEQFORK"), "NextStep"]) == SFCFork(target="NextStep")
    assert isinstance(mixin.seqbreak([]), SFCBreak)
    assert mixin.seq_element([step]) is step
    assert mixin.seq_element([]) is None

    seqcontrol_tree = Tree(
        parser_const.KEY_SEQ_CONTROL_OPS,
        [
            Token("FLAG", parser_const.GRAMMAR_VALUE_SEQCONTROL),
            Token("FLAG", parser_const.GRAMMAR_VALUE_SEQTIMER),
        ],
    )
    sequence = mixin.sequence(
        [
            Token(parser_const.GRAMMAR_VALUE_OPENSEQUENCE, parser_const.GRAMMAR_VALUE_OPENSEQUENCE),
            "MainSeq",
            (1, 2),
            (3, 4),
            seqcontrol_tree,
            body_tree,
        ]
    )
    equation = mixin.equationblock(["EqA", (5, 6), (7, 8), Tree(parser_const.KEY_STATEMENT, ["stmt"])])
    tokenized_equation = mixin.equationblock(
        [
            Token(parser_const.GRAMMAR_VALUE_EQUATIONBLOCK, parser_const.GRAMMAR_VALUE_EQUATIONBLOCK),
            "EqToken",
            (6, 7),
            (8, 9),
            Tree(parser_const.KEY_STATEMENT, ["token_stmt"]),
        ]
    )
    nested_sequence = Sequence(name="Nested", type="SEQUENCE", position=(0, 0), size=(1, 1), code=[])
    nested_equation = Equation(name="EqNested", position=(9, 10), size=(11, 12), code=[])
    modulecode = mixin.modulecode([sequence, equation, [nested_sequence, nested_equation]])

    assert sequence == Sequence(
        name="MainSeq",
        type=parser_const.GRAMMAR_VALUE_OPENSEQUENCE,
        position=(1.0, 2.0),
        size=(3.0, 4.0),
        seqcontrol=True,
        seqtimer=True,
        code=[init_step, transition],
    )
    assert equation == Equation(name="EqA", position=(5.0, 6.0), size=(7.0, 8.0), code=["stmt"])
    assert tokenized_equation == Equation(name="EqToken", position=(6.0, 7.0), size=(8.0, 9.0), code=["token_stmt"])
    assert modulecode.sequences == [sequence, nested_sequence]
    assert modulecode.equations == [equation, nested_equation]


def test_sfc_mixin_normalizes_enter_active_exit_code_blocks():
    mixin = _SFCHarness()

    enter = mixin.entercode([Token("ENTERCODE", "ENTERCODE"), Tree(parser_const.KEY_STATEMENT, ["enter_stmt"])])
    active = mixin.activecode([Token("ACTIVECODE", "ACTIVECODE"), Tree(parser_const.KEY_STATEMENT, ["active_stmt"])])
    exit_ = mixin.exitcode([Token("EXITCODE", "EXITCODE"), Tree(parser_const.KEY_STATEMENT, ["exit_stmt"])])

    code_blocks = mixin.code_blocks([enter, active, exit_])

    assert enter == {"enter": [Tree(parser_const.KEY_STATEMENT, ["enter_stmt"])]}
    assert active == {"active": [Tree(parser_const.KEY_STATEMENT, ["active_stmt"])]}
    assert exit_ == {"exit": [Tree(parser_const.KEY_STATEMENT, ["exit_stmt"])]}
    assert code_blocks == SFCCodeBlocks(
        enter=[Tree(parser_const.KEY_STATEMENT, ["enter_stmt"])],
        active=[Tree(parser_const.KEY_STATEMENT, ["active_stmt"])],
        exit=[Tree(parser_const.KEY_STATEMENT, ["exit_stmt"])],
    )
