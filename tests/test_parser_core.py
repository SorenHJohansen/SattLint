"""Tests for grammar coverage and parser-core behaviour.

Covers parse_source_text, source spans, flags, and identifier rules.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, LiteralString, cast

import pytest
from lark import Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken

from sattline_parser import api as parser_api
from sattline_parser import fuzz_harness as parser_fuzz_harness
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser import strip_sl_comments
from sattline_parser.grammar import constants as parser_const
from sattline_parser.grammar import parser_decode as grammar_parser_decode
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FloatLiteral,
    FrameModule,
    GraphObject,
    InteractObject,
    IntLiteral,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattline_parser.transformer._expressions_mixin import _ExpressionsMixin
from sattline_parser.transformer._graphics_interact_mixin import _GraphicsInteractMixin
from sattline_parser.transformer._modules_mixin import _flatten_items, _is_tree, _meta_span, _ModulesMixin
from sattline_parser.transformer._sfc_mixin import _SFCMixin
from sattline_parser.transformer._tokens_mixin import DEFAULT_INIT, _TokensMixin
from sattline_parser.transformer.sl_transformer import (
    SLTransformer,
    _extract_program_name_from_header_lines,
    _iter_tree_children,
    _strip_quoted,
)
from sattline_parser.transformer.sl_transformer import (
    _flatten_items as _sl_flatten_items,
)
from sattline_parser.transformer.sl_transformer import (
    _is_tree as _sl_is_tree,
)
from sattline_parser.transformer.sl_transformer import (
    _meta_span as _sl_meta_span,
)
from sattline_parser.utils.formatter import format_expr, format_list, format_optional, format_seq_nodes
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


class _ModulesHarness(_ModulesMixin):
    def __init__(self, tails: list[Any] | None = None) -> None:
        self._tails = list(tails or [])

    def _extract_coord_tails(self, _items: list[Any]) -> list[Any]:
        return list(self._tails)


class _GraphicsHarness(_GraphicsInteractMixin):
    def __init__(self, coord_tails: list[Any] | None = None, extra_tails: list[Any] | None = None) -> None:
        self._coord_tails = list(coord_tails or [])
        self._extra_tails = list(extra_tails or [])

    def _extract_coord_payloads(self, items: list[Any]) -> tuple[list[Any], list[Any]]:
        payloads: list[Any] = []
        tails = list(self._coord_tails)
        for item in items:
            if isinstance(item, tuple):
                payloads.append(item)
            elif isinstance(item, dict) and parser_const.KEY_COORDS in item:
                payloads.append(item[parser_const.KEY_COORDS])
                tails.extend(item.get(parser_const.KEY_TAILS, []))
        return payloads, tails

    def _merge_tails(self, *tail_groups: list[Any]) -> list[Any]:
        merged: list[Any] = []
        for group in tail_groups:
            merged.extend(group)
        return merged

    def _collect_invar_enable_tails(self, items: list[Any]) -> list[Any]:
        tails = list(self._extra_tails)

        def _visit(node: Any) -> None:
            if isinstance(node, dict) and parser_const.KEY_TAIL in node:
                tails.append(node[parser_const.KEY_TAIL])
            elif isinstance(node, (list, tuple)):
                for child in node:
                    _visit(child)

        for item in items:
            _visit(item)
        return tails


class _TokensHarness(_TokensMixin):
    pass


class _ExpressionsHarness(_ExpressionsMixin):
    pass


class _SFCHarness(_SFCMixin):
    pass


def _module_header(name: str = "Module") -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


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
    assert _strip_quoted('"He said ""Hi""\n"') == 'He said "Hi"'
    assert _strip_quoted("plain-text") == "plain-text"
    assert _sl_is_tree(nested_tree) is True
    assert _sl_is_tree("not-a-tree") is False
    assert list(_sl_flatten_items(["alpha", ["delta"], nested_tree])) == ["alpha", "delta", "beta", "gamma"]
    assert list(_iter_tree_children(Tree("wrapper", ["alpha", "beta"]))) == ["alpha", "beta"]
    assert list(_iter_tree_children("not-a-tree")) == []


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
    assert modulecode.sequences == [sequence, nested_sequence]
    assert modulecode.equations == [equation, nested_equation]


def test_sfc_mixin_rejects_malformed_shapes_and_missing_required_fields():
    mixin = _SFCHarness()

    with pytest.raises(ValueError, match="seqinitstep expected"):
        mixin.seqinitstep([Token("SEQINITSTEP", "SEQINITSTEP"), "Init"])
    with pytest.raises(ValueError, match="seqstep expected"):
        mixin.seqstep([Token("SEQSTEP", "SEQSTEP"), "Step", "not-code-blocks"])
    with pytest.raises(ValueError, match="seqtransition expected WAIT_FOR"):
        mixin.seqtransition([Token("SEQTRANSITION", "SEQTRANSITION"), "Gate", Token("NAME", "NAME"), True])
    with pytest.raises(ValueError, match="seqtransition expected WAIT_FOR"):
        mixin.seqtransition([Token("SEQTRANSITION", "SEQTRANSITION"), Token("NAME", "NAME"), True])
    with pytest.raises(ValueError, match=r"seqtransition expected \(SEQTRANSITION"):
        mixin.seqtransition([Token("SEQTRANSITION", "SEQTRANSITION")])
    with pytest.raises(ValueError, match="seqtransitionsub expected"):
        mixin.seqtransitionsub(
            [Token("SUBSEQTRANSITION", "SUBSEQTRANSITION"), "Sub", Tree("wrong", []), Token("END", "END")]
        )
    with pytest.raises(ValueError, match="seqsub expected"):
        mixin.seqsub([Token("SUBSEQUENCE", "SUBSEQUENCE"), "Sub", Tree("wrong", []), Token("END", "END")])
    with pytest.raises(ValueError, match="seqfork expected"):
        mixin.seqfork([Token("SEQFORK", "SEQFORK")])
    with pytest.raises(ValueError, match="Name can't be None"):
        mixin.sequence([(1, 2), (3, 4), Tree(parser_const.KEY_SEQUENCE_BODY, [])])
    with pytest.raises(ValueError, match="Position can't be None"):
        mixin.sequence([Token(parser_const.GRAMMAR_VALUE_SEQUENCE, parser_const.GRAMMAR_VALUE_SEQUENCE), "Seq"])
    with pytest.raises(ValueError, match="Size can't be None"):
        mixin.sequence([Token(parser_const.GRAMMAR_VALUE_SEQUENCE, parser_const.GRAMMAR_VALUE_SEQUENCE), "Seq", (1, 2)])
    with pytest.raises(ValueError, match="Name can't be None"):
        mixin.equationblock([(1, 2), (3, 4), Tree(parser_const.KEY_STATEMENT, ["stmt"])])
    with pytest.raises(ValueError, match="Position can't be None"):
        mixin.equationblock(["EqA"])
    with pytest.raises(ValueError, match="Size can't be None"):
        mixin.equationblock(["EqA", (1, 2)])


def test_parser_api_import_raises_when_grammar_file_is_missing(monkeypatch: pytest.MonkeyPatch):
    module_path = Path(parser_api.__file__)
    module_name = "sattline_parser.api_missing_grammar_test"
    original_exists = Path.exists

    def fake_exists(path: Path) -> bool:
        if path == parser_api.GRAMMAR_PATH:
            return False
        return original_exists(path)

    monkeypatch.setattr(Path, "exists", fake_exists)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    temp_module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)

    try:
        with pytest.raises(RuntimeError, match="Grammar file missing"):
            spec.loader.exec_module(temp_module)
    finally:
        sys.modules.pop(module_name, None)


def test_modules_mixin_helpers_flatten_nested_module_trees_and_meta_spans():
    meta = SimpleNamespace(line=12, column=4)
    nested_tree = Tree(
        parser_const.TREE_TAG_MODULE_BODY,
        ["beta", Tree(parser_const.TREE_TAG_BASE_MODULE_BODY, ["gamma"])],
    )

    assert _meta_span(meta) == SourceSpan(line=12, column=4)
    assert _meta_span(SimpleNamespace(line=None, column=4)) is None
    assert _is_tree(nested_tree) is True
    assert _is_tree("not-a-tree") is False
    assert list(_flatten_items(["alpha", ["delta"], nested_tree])) == ["alpha", "delta", "beta", "gamma"]


def test_modules_mixin_module_header_collects_argument_metadata():
    mixin = _ModulesHarness()

    header = mixin.module_header(
        SimpleNamespace(line=5, column=2),
        [
            "Motor",
            {
                parser_const.TREE_TAG_INVOKE_COORD: (1, 2, 3, 4, 5),
                parser_const.KEY_TAILS: ["PosX"],
            },
            Tree(
                parser_const.TREE_TAG_ARGUMENTS,
                [
                    7,
                    {
                        parser_const.TREE_TAG_ENABLE: False,
                        parser_const.KEY_TAIL: "EnableVar",
                    },
                    {parser_const.GRAMMAR_VALUE_ZOOMLIMITS: (0.5, 2.0)},
                    {parser_const.GRAMMAR_VALUE_ZOOMABLE: True},
                    parser_const.GRAMMAR_VALUE_IGNOREMAXMODULE,
                ],
            ),
        ],
    )

    assert header.name == "Motor"
    assert header.declaration_span == SourceSpan(line=5, column=2)
    assert header.invoke_coord == (1.0, 2.0, 3.0, 4.0, 5.0)
    assert header.invoke_coord_tails == ["PosX"]
    assert header.layer_info == "7"
    assert header.enable is False
    assert header.enable_tail == "EnableVar"
    assert header.zoom_limits == (0.5, 2.0)
    assert header.zoomable is True
    assert header.invocation_arguments == (parser_const.GRAMMAR_VALUE_IGNOREMAXMODULE,)

    tuple_header = mixin.module_header(
        SimpleNamespace(line=6, column=4),
        [
            "Valve",
            (6, 7, 8, 9, 10),
            Tree(parser_const.TREE_TAG_ARGUMENTS, ["FreeArg"]),
        ],
    )

    assert tuple_header.invoke_coord == (6.0, 7.0, 8.0, 9.0, 10.0)
    assert tuple_header.invocation_arguments == ("FreeArg",)

    with pytest.raises(ValueError, match="module_header missing invoke_coord"):
        mixin.module_header(SimpleNamespace(line=1, column=1), ["BrokenHeader"])


def test_modules_mixin_coordinate_helpers_preserve_pairs_tails_and_clipping_tree():
    mixin = _ModulesHarness(["PanelResize"])

    coords = mixin.coordinates([1, 2, "ignored"])
    pair = mixin.origo_size_pair(
        [
            coords,
            {
                parser_const.KEY_COORDS: (3, 4),
                parser_const.KEY_TAILS: ["PanelScale"],
            },
        ]
    )
    invoke = mixin.invoke_coord([1, 2, 3, 4, 5, "ignored"])
    clipping = mixin.coord_clippingbounds([coords])

    assert coords == {parser_const.KEY_COORDS: (1.0, 2.0), parser_const.KEY_TAILS: ["PanelResize"]}
    assert pair == {
        parser_const.KEY_COORDS: ((1.0, 2.0), (3.0, 4.0)),
        parser_const.KEY_TAILS: ["PanelResize", "PanelScale"],
    }
    assert invoke == {
        parser_const.TREE_TAG_INVOKE_COORD: (1.0, 2.0, 3.0, 4.0, 5.0),
        parser_const.KEY_TAILS: ["PanelResize"],
    }
    assert mixin.origo_size_pair([(1.0, 2.0), Tree(parser_const.TREE_TAG_COORDINATES, [3.0, 4.0])]) == {
        parser_const.KEY_COORDS: ((1.0, 2.0), (3.0, 4.0)),
        parser_const.KEY_TAILS: None,
    }
    assert mixin.coord_invar_tail([Token("COMMA", ","), "WidthSource"]) == "WidthSource"
    assert isinstance(clipping, Tree)
    assert clipping.data == parser_const.GRAMMAR_VALUE_CLIPPINGBOUNDS

    with pytest.raises(ValueError, match="coordinates missing REAL values"):
        mixin.coordinates([1])
    with pytest.raises(ValueError, match="origo_size_pair expected 2 coordinate pairs"):
        mixin.origo_size_pair([(1.0, 2.0)])
    with pytest.raises(ValueError, match="invoke_coord expected 5 REALs"):
        mixin.invoke_coord([1.0, 2.0, 3.0, 4.0])


@pytest.mark.parametrize(
    ("frame_marker", "expected_type"),
    [(False, SingleModule), (True, FrameModule)],
)
def test_modules_mixin_invocation_new_module_collects_decls_and_frame_marker(frame_marker, expected_type):
    mixin = _ModulesHarness()
    header = _module_header("Child")
    module_param = Variable(name="Param", datatype="integer")
    local_var = Variable(name="Local", datatype="integer")
    child = ModuleTypeInstance(header=_module_header("Nested"), moduletype_name="NestedType")
    mapping = ParameterMapping(
        target="Target",
        source_type=parser_const.KEY_VALUE,
        is_duration=False,
        is_source_global=False,
        source_literal=1,
    )
    items: list[Any] = [
        header,
        101,
        Tree(parser_const.GRAMMAR_VALUE_MODULEPARAMETERS, [module_param]),
        Tree(parser_const.GRAMMAR_VALUE_LOCALVARIABLES, [local_var]),
        Tree(parser_const.TREE_TAG_SUBMODULES, [child]),
        Tree(parser_const.TREE_TAG_MODULETYPE_PAR_LIST, [mapping]),
        ModuleDef(),
        {"groupconn": {parser_const.KEY_VAR_NAME: "ScanGroup"}, "global": False},
    ]
    if frame_marker:
        items.append(True)

    result = mixin.invocation_new_module(items)

    assert isinstance(result, expected_type)
    assert result.header.groupconn == {parser_const.KEY_VAR_NAME: "ScanGroup"}
    assert result.header.groupconn_global is False
    assert result.datecode == 101
    assert result.submodules == [child]
    if isinstance(result, SingleModule):
        assert result.moduleparameters == [module_param]
        assert result.localvariables == [local_var]
        assert result.parametermappings == [mapping]

    nested_result = mixin.invocation_new_module(
        [
            header,
            101,
            Tree(parser_const.TREE_TAG_SUBMODULES, [[child]]),
            ModuleDef(),
            ModuleCode(),
        ]
    )

    assert [cast(ModuleTypeInstance, sub).moduletype_name for sub in nested_result.submodules] == ["NestedType"]


def test_modules_mixin_base_picture_module_collects_nested_children_and_scan_group():
    mixin = _ModulesHarness()
    header = _module_header("BasePicture")
    datatype = DataType(name="Payload", description=None, datecode=100)
    moduletype = ModuleTypeDef(name="PumpType", datecode=200)
    local_var = Variable(name="Counter", datatype="integer")
    child = ModuleTypeInstance(header=_module_header("Nested"), moduletype_name="NestedType")
    moduledef = ModuleDef()

    result = mixin.base_picture_module(
        [
            header,
            Tree(
                parser_const.TREE_TAG_BASE_MODULE_BODY,
                cast(
                    Any,
                    [
                        Tree(parser_const.TREE_TAG_DATATYPE_LIST, [datatype]),
                        Tree(parser_const.TREE_TAG_MODULETYPE_LIST, [moduletype]),
                        Tree(parser_const.GRAMMAR_VALUE_LOCALVARIABLES, [local_var]),
                        Tree(parser_const.TREE_TAG_SUBMODULES, [[child]]),
                        moduledef,
                        {"groupconn": {parser_const.KEY_VAR_NAME: "ScanRoot"}, "global": True},
                    ],
                ),
            ),
        ]
    )

    assert isinstance(result, BasePicture)
    assert result.datatype_defs == [datatype]
    assert result.moduletype_defs == [moduletype]
    assert result.localvariables == [local_var]
    assert result.submodules == [child]
    assert result.moduledef is moduledef
    assert header.groupconn == {parser_const.KEY_VAR_NAME: "ScanRoot"}
    assert header.groupconn_global is True

    direct_items_result = mixin.base_picture_module([_module_header("BaseDirect"), datatype, moduletype])

    assert direct_items_result.datatype_defs == [datatype]
    assert direct_items_result.moduletype_defs == [moduletype]

    with pytest.raises(ValueError, match="No items in base_picture_module"):
        mixin.base_picture_module([])


def test_modules_mixin_variable_group_and_mapping_helpers_preserve_modifiers_and_state_suffixes():
    mixin = _ModulesHarness()
    parsed_name = mixin.variable_name(
        SimpleNamespace(line=9, column=3),
        [
            Token(parser_const.KEY_NAME, "Pump"),
            Token(parser_const.KEY_DOT, "."),
            Token(parser_const.KEY_NAME, "State"),
            Token(parser_const.TOKEN_OLD, ":OLD"),
        ],
    )
    mapping = mixin.moduletype_par_transfer(
        [
            parsed_name,
            True,
            parser_const.GRAMMAR_VALUE_DURATION_VALUE,
            {parser_const.KEY_VAR_NAME: "SourceVar"},
        ]
    )
    variables = mixin.variable_group(
        [
            ("Alpha", "desc", SourceSpan(4, 1)),
            True,
            "integer",
            parser_const.GRAMMAR_VALUE_CONST_KW,
            parser_const.GRAMMAR_VALUE_STATE_KW,
            parser_const.GRAMMAR_VALUE_OPSAVE_KW,
            parser_const.GRAMMAR_VALUE_SECURE_KW,
            ({parser_const.GRAMMAR_VALUE_TIME_VALUE: "T#5S"}, True),
        ]
    )
    list_tree = mixin.variable_list([variables])
    params_tree = mixin.moduleparameters([list_tree])
    locals_tree = mixin.localvariables([list_tree])
    scan_group = mixin.scan_group([True, parsed_name])

    assert parsed_name == {
        parser_const.KEY_VAR_NAME: "Pump.State",
        "state": "old",
        "span": SourceSpan(line=9, column=3),
    }
    assert mapping.target == parsed_name
    assert mapping.source == {parser_const.KEY_VAR_NAME: "SourceVar"}
    assert mapping.source_type == parser_const.TREE_TAG_VARIABLE_NAME
    assert mapping.is_duration is True
    assert mapping.is_source_global is True
    assert len(variables) == 1
    assert variables[0].global_var is True
    assert variables[0].const is True
    assert variables[0].state is True
    assert variables[0].opsave is True
    assert variables[0].secure is True
    assert variables[0].init_value == {parser_const.GRAMMAR_VALUE_TIME_VALUE: "T#5S"}
    assert variables[0].init_is_duration is True
    assert params_tree.data == parser_const.GRAMMAR_VALUE_MODULEPARAMETERS
    assert locals_tree.data == parser_const.GRAMMAR_VALUE_LOCALVARIABLES
    assert scan_group == {"groupconn": parsed_name, "global": True}

    string_state_name = mixin.variable_name(
        SimpleNamespace(line=10, column=5),
        ["Pump", ".", "State", "new"],
    )

    assert string_state_name == {
        parser_const.KEY_VAR_NAME: "Pump.State",
        "state": "new",
        "span": SourceSpan(line=10, column=5),
    }


def test_modules_mixin_definition_trees_keep_only_supported_children():
    mixin = _ModulesHarness()
    record_field = Variable(name="Field", datatype="integer")
    record = mixin.record(
        SimpleNamespace(line=8, column=2),
        [
            "Payload",
            "desc",
            300,
            Tree(parser_const.TREE_TAG_VAR_LIST, [record_field]),
        ],
    )
    moduletype = mixin.moduletype_definition(
        SimpleNamespace(line=3, column=1),
        [
            "PumpType",
            400,
            Tree(parser_const.GRAMMAR_VALUE_MODULEPARAMETERS, [Variable(name="In", datatype="integer")]),
            Tree(parser_const.GRAMMAR_VALUE_LOCALVARIABLES, [Variable(name="Tmp", datatype="integer")]),
            Tree(
                parser_const.TREE_TAG_SUBMODULES,
                [ModuleTypeInstance(header=_module_header("Nested"), moduletype_name="NestedType")],
            ),
            ModuleDef(),
            {"groupconn": {parser_const.KEY_VAR_NAME: "ScanType"}, "global": True},
        ],
    )
    datatype_tree = mixin.datatype_typedefinitions([record, Tree("wrapper", [record])])
    moduletype_tree = mixin.moduletype_definitions(
        [moduletype, Tree(parser_const.TREE_TAG_MODULETYPE_DEFINITION, [moduletype])]
    )
    submodules = mixin.submodules(["ignored", [moduletype.submodules[0]], _module_header("not-a-module")])
    invocation_tail = mixin.invocation_tail([moduletype_tree, Tree(parser_const.TREE_TAG_MODULETYPE_PAR_LIST, [])])

    assert record.name == "Payload"
    assert record.declaration_span == SourceSpan(line=8, column=2)
    assert record.var_list == [record_field]
    assert moduletype.groupconn == {parser_const.KEY_VAR_NAME: "ScanType"}
    assert moduletype.groupconn_global is True
    assert datatype_tree.data == parser_const.TREE_TAG_DATATYPE_LIST
    assert datatype_tree.children == [record, record]
    assert moduletype_tree.data == parser_const.TREE_TAG_MODULETYPE_LIST
    assert moduletype_tree.children == [moduletype, moduletype]
    assert submodules.data == parser_const.TREE_TAG_SUBMODULES
    assert submodules.children == [moduletype.submodules[0]]
    assert invocation_tail is not None
    assert invocation_tail.data == parser_const.TREE_TAG_MODULETYPE_PAR_LIST

    direct_nested = mixin.moduletype_definition(
        SimpleNamespace(line=4, column=2),
        [
            "MixerType",
            401,
            Tree(
                parser_const.TREE_TAG_SUBMODULES,
                [[ModuleTypeInstance(header=_module_header("Leaf"), moduletype_name="LeafType")]],
            ),
        ],
    )

    assert [sub.moduletype_name for sub in direct_nested.submodules] == ["LeafType"]

    with pytest.raises(Exception, match="Name cannot be none"):
        mixin.moduletype_definition(SimpleNamespace(line=1, column=1), [100])


def test_modules_mixin_wrapper_rules_and_invocation_errors():
    mixin = _ModulesHarness()
    header = _module_header("Pump")
    parameter_tree = Tree(
        parser_const.TREE_TAG_MODULETYPE_PAR_LIST,
        [
            ParameterMapping(
                target={parser_const.KEY_VAR_NAME: "Target"},
                source_type=parser_const.TREE_TAG_VARIABLE_NAME,
                is_source_global=False,
                is_duration=False,
                source={parser_const.KEY_VAR_NAME: "Source"},
            )
        ],
    )

    assert mixin.module_body(["a"]).data == parser_const.TREE_TAG_MODULE_BODY
    assert mixin.base_module_body(["b"]).data == parser_const.TREE_TAG_BASE_MODULE_BODY
    assert mixin.IGNOREMAXMODULE(None) == parser_const.GRAMMAR_VALUE_IGNOREMAXMODULE
    assert mixin.LAYERMODULE(None) == parser_const.GRAMMAR_VALUE_LAYERMODULE
    assert mixin.argument([Token("COMMA", ","), "value"]) == "value"
    assert mixin.argument([Token("COMMA", ",")]) is None
    assert mixin.arguments([Token("COMMA", ","), 1, "two"]).children == [1, "two"]
    assert mixin.frame_module([]) is True
    assert mixin.invocation_module_type([header, "PumpType", parameter_tree]).moduletype_name == "PumpType"
    assert isinstance(mixin.invocation_new_module([True, header, 101, ModuleDef(), ModuleCode()]), FrameModule)
    assert isinstance(
        mixin.invocation_new_module(
            [
                header,
                101,
                Tree(parser_const.GRAMMAR_VALUE_MODULEPARAMETERS, [Variable(name="In", datatype="integer")]),
                Tree(parser_const.GRAMMAR_VALUE_LOCALVARIABLES, [Variable(name="Tmp", datatype="integer")]),
                parameter_tree,
                ModuleDef(),
                ModuleCode(),
            ]
        ),
        SingleModule,
    )

    with pytest.raises(ValueError, match="Missing module header"):
        mixin.invocation_new_module([101])
    with pytest.raises(ValueError, match="Missing module header"):
        mixin.invocation_module_type(["PumpType"])
    with pytest.raises(ValueError, match="Missing module type name"):
        mixin.invocation_module_type([header])


def test_modules_mixin_transfer_and_variable_helpers_cover_fallback_branches():
    mixin = _ModulesHarness()

    assert mixin.opt_var_init([]) is None
    assert mixin.opt_var_init([parser_const.GRAMMAR_VALUE_DURATION_VALUE, 5]) == (5, True)
    assert mixin.time_value(["T#10S"]) == {parser_const.GRAMMAR_VALUE_TIME_VALUE: "T#10S"}
    assert mixin.variable_list([[Variable(name="A", datatype="integer")], None]).data == parser_const.TREE_TAG_VAR_LIST
    assert (
        mixin.moduleparameters([Tree(parser_const.TREE_TAG_VAR_LIST, [Variable(name="A", datatype="integer")])]).data
        == parser_const.GRAMMAR_VALUE_MODULEPARAMETERS
    )
    assert (
        mixin.localvariables([Tree(parser_const.TREE_TAG_VAR_LIST, [Variable(name="B", datatype="integer")])]).data
        == parser_const.GRAMMAR_VALUE_LOCALVARIABLES
    )
    assert mixin.submodules(["ignored", [_module_header("Nope")]]).children == []

    duration_transfer = mixin.moduletype_par_transfer(
        [
            {parser_const.KEY_VAR_NAME: "Target"},
            True,
            parser_const.GRAMMAR_VALUE_DURATION_VALUE,
            {parser_const.GRAMMAR_VALUE_TIME_VALUE: "T#5S"},
        ]
    )
    object_transfer = mixin.moduletype_par_transfer([{parser_const.KEY_VAR_NAME: "Target"}, object()])

    assert duration_transfer.is_source_global is True
    assert duration_transfer.is_duration is True
    assert duration_transfer.source_literal == {parser_const.GRAMMAR_VALUE_TIME_VALUE: "T#5S"}
    assert object_transfer.source_literal is not None
    assert object_transfer.source_literal.startswith("<object object at")
    assert mixin.moduletype_par_transfer(["TargetLiteral", "SourceLiteral"]).target == "TargetLiteral"
    assert mixin.moduletype_par_transfer([123, "SourceLiteral"]).target == "123"
    assert mixin.moduletype_par_list([duration_transfer]).data == parser_const.TREE_TAG_MODULETYPE_PAR_LIST

    assert mixin.variable_group([]) == []
    literal_init_variables = mixin.variable_group([("Beta", None, SourceSpan(2, 2)), "integer", 7])
    assert literal_init_variables[0].init_value == 7
    assert literal_init_variables[0].init_is_duration is False

    with pytest.raises(ValueError, match="moduletype_par_transfer received empty items"):
        mixin.moduletype_par_transfer([])
    with pytest.raises(ValueError, match="moduletype_par_transfer missing target variable_name"):
        mixin.moduletype_par_transfer([None])
    with pytest.raises(ValueError, match="Expected datatype NAME in variable_group"):
        mixin.variable_group([("Alpha", None, SourceSpan(1, 1)), 123])
    with pytest.raises(ValueError, match="record is missing datatype name"):
        mixin.record(SimpleNamespace(line=1, column=1), [100])


def test_modules_mixin_layout_helpers_cover_moduledef_and_numeric_errors():
    mixin = _ModulesHarness(["CoordTail"])
    graph = GraphObject(type="TextObject", properties={})
    interact = InteractObject(type="Button_", properties={})

    assert mixin.origo_coord([1, 2, 3]) == [1, 2, 3]
    assert mixin.size([4, 5]) == [4, 5]
    assert mixin.clippingbounds(
        [{parser_const.KEY_COORDS: ((0.0, 0.0), (1.0, 1.0)), parser_const.KEY_TAILS: ["TailA"]}]
    ) == {
        parser_const.GRAMMAR_VALUE_CLIPPINGBOUNDS: ((0.0, 0.0), (1.0, 1.0)),
        parser_const.KEY_TAILS: ["TailA"],
    }
    assert mixin.clippingbounds([((0.0, 0.0), (1.0, 1.0))]) == {
        parser_const.GRAMMAR_VALUE_CLIPPINGBOUNDS: ((0.0, 0.0), (1.0, 1.0))
    }
    assert mixin.seq_layers(["LayerA"]) == {parser_const.KEY_SEQ_LAYERS: "LayerA"}
    assert mixin.zoomlimits([0.5, 2.0]) == {parser_const.GRAMMAR_VALUE_ZOOMLIMITS: (0.5, 2.0)}
    assert mixin.ZOOMABLE(None) == {parser_const.GRAMMAR_VALUE_ZOOMABLE: True}
    assert mixin.grid([Token("JUNK", ","), 0.5, 1.5]) == 1.5
    assert mixin.moduledef_opts_seq(
        [{parser_const.GRAMMAR_VALUE_GRID: 0.5}, {parser_const.KEY_SEQ_LAYERS: "LayerA"}]
    ).children == [{parser_const.GRAMMAR_VALUE_GRID: 0.5, parser_const.KEY_SEQ_LAYERS: "LayerA"}]

    moduledef = mixin.moduledef(
        [
            {parser_const.GRAMMAR_VALUE_CLIPPINGBOUNDS: ((0.0, 0.0), (1.0, 1.0)), parser_const.KEY_TAILS: ["TailA"]},
            [graph],
            [interact],
            {parser_const.GRAMMAR_VALUE_ZOOMLIMITS: (0.5, 2.0)},
            {parser_const.GRAMMAR_VALUE_ZOOMABLE: True},
            {parser_const.GRAMMAR_VALUE_GRID: 0.75},
            {parser_const.KEY_SEQ_LAYERS: {"top": 1.0}},
        ]
    )

    assert moduledef.clipping_bounds == ((0.0, 0.0), (1.0, 1.0))
    assert moduledef.properties[parser_const.KEY_TAILS] == ["TailA"]
    assert moduledef.graph_objects == [graph]
    assert moduledef.interact_objects == [interact]
    assert moduledef.zoom_limits == (0.5, 2.0)
    assert moduledef.zoomable is True
    assert moduledef.grid == 0.75
    assert moduledef.seq_layers == {"top": 1.0}

    tuple_moduledef = mixin.moduledef([((2.0, 2.0), (3.0, 3.0))])
    assert tuple_moduledef.clipping_bounds == ((2.0, 2.0), (3.0, 3.0))

    with pytest.raises(ValueError, match="coord_invar_tail expected"):
        mixin.coord_invar_tail([Token("JUNK", ",")])
    with pytest.raises(ValueError, match="grid expected a numeric value"):
        mixin.grid(["bad"])
    with pytest.raises(ValueError, match="grid expected at least one numeric value"):
        mixin.grid([Token("JUNK", ",")])


def test_ast_model_helpers_cover_reduce_usage_and_string_formats(monkeypatch: pytest.MonkeyPatch):
    span = SourceSpan(2, 3)
    int_lit = IntLiteral(7, span)
    float_lit = FloatLiteral(2.5, span)

    assert span.__reduce__() == (SourceSpan, (2, 3))
    assert int_lit.__reduce__() == (IntLiteral, (7, span))
    assert float_lit.__reduce__() == (FloatLiteral, (2.5, span))
    assert Simple_DataType.from_any(Simple_DataType.BOOLEAN) is Simple_DataType.BOOLEAN
    assert Variable(name="Flag", datatype="BOOLEAN").datatype_text == "boolean"
    assert Variable(name="RecordValue", datatype="CustomRecord").datatype_text == "CustomRecord"
    assert str(Variable(name="Count", datatype="integer", init_value=0)).startswith("Name: 'Count'")

    with pytest.raises(TypeError, match="Expected Simple_DataType or str"):
        Simple_DataType.from_any(cast(Any, 123))
    with pytest.raises(TypeError, match="Expected Simple_DataType or str"):
        Variable(name="Broken", datatype=cast(Any, 123))

    def _raise_value_error(cls, value):
        raise ValueError("bad datatype")

    monkeypatch.setattr(Simple_DataType, "from_any", classmethod(_raise_value_error))
    with pytest.raises(ValueError, match="bad datatype"):
        Variable(name="Exploded", datatype=cast(Any, object()))

    usage_path = ["BasePicture"]
    datatype = DataType(
        name="Payload",
        description="desc",
        datecode=100,
        var_list=[Variable(name="FieldA", datatype="integer")],
        origin_file="Program.s",
        origin_lib="LibHA",
    )
    datatype.mark_read(usage_path)
    datatype.mark_written(usage_path)
    usage_path.append("Mutated")

    assert datatype.read is True
    assert datatype.written is True
    assert datatype.usage_locations == [(["BasePicture"], "read"), (["BasePicture"], "write")]
    assert "Variables in datatype" in str(datatype)

    assert (
        str(
            ParameterMapping(
                target={parser_const.KEY_VAR_NAME: "Target"},
                source_type=parser_const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=True,
            )
        )
        == "Target => GLOBAL"
    )
    assert (
        str(
            ParameterMapping(
                target={parser_const.KEY_VAR_NAME: "Target"},
                source_type=parser_const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                source={parser_const.KEY_VAR_NAME: "Source"},
                is_source_global=False,
            )
        )
        == "Target => Source"
    )
    assert (
        str(
            ParameterMapping(
                target="Target",
                source_type=parser_const.KEY_VALUE,
                is_duration=False,
                source_literal=42,
                is_source_global=False,
            )
        )
        == "Target => 42"
    )
    assert (
        str(
            ParameterMapping(
                target="Target",
                source_type=parser_const.KEY_VALUE,
                is_duration=False,
                is_source_global=False,
            )
        )
        == "Target => <None>"
    )

    sequence = Sequence(name="SeqA", type="sequence", position=(0.0, 0.0), size=(1.0, 1.0), code=["step"])
    equation = Equation(name="EqA", position=(1.0, 2.0), size=(3.0, 4.0), code=["stmt"])
    module_code = ModuleCode()
    rendered_module_code = ModuleCode(
        sequences=[sequence],
        equations=[
            Equation(
                name="EqStmt",
                position=(1.0, 2.0),
                size=(3.0, 4.0),
                code=[
                    Tree(
                        parser_const.KEY_STATEMENT,
                        [(parser_const.KEY_ASSIGN, {parser_const.KEY_VAR_NAME: "Out"}, 1)],
                    )
                ],
            )
        ],
    )
    empty_statement_module_code = ModuleCode(
        equations=[
            Equation(
                name="EqEmpty",
                position=(5.0, 6.0),
                size=cast(Any, None),
                code=[Tree(parser_const.KEY_STATEMENT, [])],
            )
        ]
    )
    direct_statement_module_code = ModuleCode(
        equations=[
            Equation(
                name="EqDirect",
                position=(7.0, 8.0),
                size=cast(Any, None),
                code=[(parser_const.KEY_ASSIGN, {parser_const.KEY_VAR_NAME: "Direct"}, 2)],
            )
        ]
    )
    module_def = ModuleDef(clipping_bounds=((0.0, 0.0), (1.0, 1.0)), zoomable=True)
    header = _module_header("Parent")
    child = ModuleTypeInstance(header=_module_header("Child"), moduletype_name="ChildType")

    assert "Sequence(name=SeqA" in str(sequence)
    assert "Equation(name=EqA" in str(equation)
    assert "No sequences" in str(module_code)
    assert "Sequence 'SeqA'" in str(rendered_module_code)
    assert "EquationBlock name='EqStmt'" in str(rendered_module_code)
    assert "Out = 1" in str(rendered_module_code)
    assert "EquationBlock name='EqEmpty'" in str(empty_statement_module_code)
    assert "Direct = 2" in str(direct_statement_module_code)
    assert "ClippingBounds" in str(module_def)
    assert "SingleModule{" in str(SingleModule(header=header, moduledef=module_def, modulecode=module_code))
    assert "FrameModule{" in str(FrameModule(header=header, moduledef=module_def, modulecode=module_code))
    assert "ModuleTypeInstance{" in str(child)
    assert "ModulType{" in str(ModuleTypeDef(name="ChildType", modulecode=module_code, submodules=[child]))
    assert "BasePicture{" in str(BasePicture(header=header, moduledef=module_def, modulecode=module_code))


def test_graphics_interact_mixin_builds_graph_objects_and_lists():
    mixin = _GraphicsHarness(coord_tails=["CoordTail"], extra_tails=["ExtraTail"])
    coords = ((1.0, 2.0), (3.0, 4.0))

    text_object = mixin.text_object(
        [
            Tree(parser_const.TREE_TAG_TEXT_CONTENT, ["Caption"]),
            Token(parser_const.TOKEN_VARNAME, "TextVar"),
            {parser_const.KEY_COORDS: coords, parser_const.KEY_TAILS: ["PayloadTail"]},
        ]
    )

    assert text_object.type == parser_const.GRAMMAR_VALUE_TEXTOBJECT
    assert text_object.properties[parser_const.KEY_COORDS] == coords
    assert text_object.properties[parser_const.KEY_TAILS] == ["CoordTail", "PayloadTail", "ExtraTail"]
    assert text_object.properties["text_vars"] == ["Caption"]

    skipped_empty_text = mixin.text_object(
        [
            "Caption",
            "",
            Token(parser_const.TOKEN_VARNAME, "FallbackTextVar"),
            {parser_const.KEY_COORDS: coords},
        ]
    )

    assert skipped_empty_text.properties["text_vars"] == ["Caption"]
    assert mixin.text_content(["Visible text"]) == "Visible text"

    with pytest.raises(ValueError, match="_extract_text_from_node expected"):
        mixin.text_object([0, Token(parser_const.TOKEN_VARNAME, "Broken")])

    for method_name, expected_type, keeps_coords in (
        ("rectangle_object", parser_const.GRAMMAR_VALUE_RECTANGLEOBJECT, True),
        ("line_object", parser_const.GRAMMAR_VALUE_LINEOBJECT, True),
        ("oval_object", parser_const.GRAMMAR_VALUE_OVALOBJECT, True),
        ("polygon_object", parser_const.GRAMMAR_VALUE_POLYGONOBJECT, False),
        ("segment_object", parser_const.GRAMMAR_VALUE_SEGMENTOBJECT, True),
        ("composite_object", parser_const.GRAMMAR_VALUE_COMPOSITEOBJECT, False),
    ):
        graph_object = getattr(mixin, method_name)([{parser_const.KEY_COORDS: coords}])
        assert graph_object.type == expected_type
        if keeps_coords:
            assert graph_object.properties[parser_const.KEY_COORDS] == coords
        assert graph_object.properties[parser_const.KEY_TAILS] == ["CoordTail", "ExtraTail"]

    wrapped = mixin.graph_object([text_object, 7])
    interact_child = InteractObject(type="Button_", properties={})

    assert wrapped.properties["layer"] == 7
    assert mixin.graph_objects([text_object, "ignored", GraphObject(type="Rect", properties={})]) == [
        text_object,
        GraphObject(type="Rect", properties={}),
    ]
    assert mixin.interact_objects([interact_child, Tree("wrapper", [interact_child, "ignored"])]) == [
        interact_child,
        interact_child,
    ]

    with pytest.raises(ValueError, match="graph_object expected a GraphObject"):
        mixin.graph_object(["bad"])
    with pytest.raises(ValueError, match="text_content expected a str"):
        mixin.text_content([1, 2])


def test_graphics_interact_mixin_cover_interact_helpers_and_validation_errors():
    mixin = _GraphicsHarness(coord_tails=["CoordTail"], extra_tails=["TailVar"])
    coords = ((0.0, 0.0), (1.0, 1.0))
    proc_dict = mixin.procedure_call([Token(parser_const.KEY_NAME, "ToggleWindow"), "arg1", 2])
    combut = mixin.combutproc_item(
        [
            coords,
            proc_dict,
            [{parser_const.KEY_PROCEDURE_CALL: {parser_const.KEY_NAME: "OtherProc", parser_const.KEY_ARGS: []}}],
        ]
    )
    simple = mixin.interact_simple_item(
        [
            Token("INTERACT", "Button_"),
            coords,
            Tree(parser_const.TREE_TAG_INTERACT_BODY_SEQ, ["body-a"]),
            ["body-b"],
            {parser_const.KEY_TAIL: "EnableVar"},
        ]
    )

    assert proc_dict == {
        parser_const.KEY_PROCEDURE_CALL: {
            parser_const.KEY_NAME: "ToggleWindow",
            parser_const.KEY_ARGS: ["arg1", 2],
        }
    }
    assert combut.type == parser_const.GRAMMAR_VALUE_COMBUTPROC
    assert combut.properties[parser_const.KEY_COORDS] == [coords]
    assert combut.properties[parser_const.KEY_PROCEDURE] == {
        parser_const.KEY_NAME: "OtherProc",
        parser_const.KEY_ARGS: [],
    }
    assert combut.properties[parser_const.KEY_TAILS] == ["CoordTail", "TailVar"]
    assert simple.type == "Button_"
    assert simple.properties[parser_const.KEY_COORDS] == [coords]
    assert simple.properties[parser_const.KEY_BODY] == ["body-a", "body-b"]
    assert simple.properties[parser_const.KEY_TAILS] == ["TailVar", "EnableVar"]

    assert mixin.invar([Token("JUNK", "="), "VarRef"]) == "VarRef"
    assert mixin.enable([False, {parser_const.KEY_TAIL: "EnableExpr"}]) == {
        parser_const.TREE_TAG_ENABLE: False,
        parser_const.KEY_TAIL: {parser_const.KEY_TAIL: "EnableExpr"},
    }
    assert mixin.enable_expression([Token("JUNK", "="), "Expr"]) == "Expr"
    assert mixin.interact_assign_variable_tailed(["Setpoint", 5, {parser_const.KEY_TAIL: "OutVar"}]) == {
        parser_const.KEY_NAME: "Setpoint",
        parser_const.KEY_VALUE: 5,
        parser_const.KEY_TAIL: {parser_const.KEY_TAIL: "OutVar"},
    }
    assert mixin.interact_assign_variable_plain(["Setpoint", 5]) == {
        parser_const.KEY_NAME: "Setpoint",
        parser_const.KEY_VALUE: 5,
        parser_const.KEY_TAIL: None,
    }
    assert mixin.interact_assign_variable([{parser_const.KEY_NAME: "Setpoint", parser_const.KEY_VALUE: 5}]) == {
        parser_const.KEY_ASSIGN: {parser_const.KEY_NAME: "Setpoint", parser_const.KEY_VALUE: 5}
    }
    assert mixin.interact_flag(
        [
            Token(parser_const.KEY_NAME, "Abs_"),
            Token(parser_const.KEY_STRING, "label"),
            {parser_const.KEY_TAIL: "InVar"},
        ]
    ) == {
        parser_const.KEY_NAME: "Abs_",
        parser_const.KEY_EXTRA: "label",
        parser_const.KEY_TAIL: {parser_const.KEY_TAIL: "InVar"},
    }
    assert mixin.interact_value_line([1, 2, 3]) == [1, 2, 3]
    assert mixin.layer_info([Token("JUNK", ":"), 4]) == 4
    assert mixin.seq_control_opt(["SEQ_CONTROL", "SEQTIMER"]).data == parser_const.KEY_SEQ_CONTROL_OPS
    assert mixin.codeblock_coord([Token("LPAR", "("), 1, 2]) == (1.0, 2.0)
    assert mixin.objsizedef([Token("LPAR", "("), 3, 4]) == (3.0, 4.0)
    assert mixin.two_layers([{"top": 1.0}, {"bottom": 0.0}]) == {"top": 1.0, "bottom": 0.0}

    with pytest.raises(ValueError, match="invar expected"):
        mixin.invar([Token("JUNK", "=")])
    with pytest.raises(ValueError, match="enable_expression expected"):
        mixin.enable_expression([Token("JUNK", "=")])
    with pytest.raises(ValueError, match="interact_assign_variable expected"):
        mixin.interact_assign_variable(["bad"])
    with pytest.raises(ValueError, match="layer_info expected"):
        mixin.layer_info(["bad"])
    with pytest.raises(ValueError, match="codeblock_coord expected 2 coordinate values"):
        mixin.codeblock_coord([1])
    with pytest.raises(ValueError, match="objsizedef expected 2 size values"):
        mixin.objsizedef([1])


def test_formatter_helpers_cover_variable_lists_optionals_and_expression_shapes():
    variables = [
        Variable(name="Alpha", datatype="integer", global_var=True, const=False, state=False, init_value=1),
        Variable(name="Beta", datatype="real", global_var=False, const=True, state=True, init_value=None),
    ]
    statement_tree = Tree(
        parser_const.KEY_STATEMENT,
        [(parser_const.KEY_ASSIGN, {parser_const.KEY_VAR_NAME: "Counter"}, 1)],
    )
    if_expr = (
        parser_const.GRAMMAR_VALUE_IF,
        [
            ({parser_const.KEY_VAR_NAME: "A"}, [(parser_const.KEY_ASSIGN, {parser_const.KEY_VAR_NAME: "B"}, 1)]),
            ({parser_const.KEY_VAR_NAME: "C"}, [(parser_const.KEY_ASSIGN, {parser_const.KEY_VAR_NAME: "D"}, 2)]),
        ],
        [(parser_const.KEY_ASSIGN, {parser_const.KEY_VAR_NAME: "E"}, 3)],
    )
    ternary_expr = (
        parser_const.KEY_TERNARY,
        [({parser_const.KEY_VAR_NAME: "Cond"}, {parser_const.KEY_VAR_NAME: "Left"})],
        {parser_const.KEY_VAR_NAME: "Right"},
    )

    assert format_list([], inline_if_singleline=True) == "[]"
    assert "Name: 'Alpha'" in format_list(variables)
    assert format_list([1, "two"], inline_if_singleline=True) == "[1, two]"
    assert format_list(["one\ntwo"], inline_if_singleline=True).startswith("[\n")
    assert format_optional(None) == "None"
    assert format_optional(5) == "5"
    assert format_expr(statement_tree) == "Counter = 1"
    assert format_expr({parser_const.KEY_VAR_NAME: "Value"}) == "Value"
    assert format_expr("hello") == "'hello'"
    assert format_expr([1, 2]) == "1\n2"
    assert format_expr((parser_const.KEY_ASSIGN, {parser_const.KEY_VAR_NAME: "Value"}, 5)) == "Value = 5"
    assert "ELSIF C" in format_expr(if_expr)
    assert "ELSE" in format_expr(if_expr)
    assert "ENDIF" in format_expr(ternary_expr)
    assert format_expr((parser_const.GRAMMAR_VALUE_OR, [True, False])) == "True OR \nFalse"
    assert format_expr((parser_const.GRAMMAR_VALUE_AND, [True, False])) == "True AND \nFalse"
    assert format_expr((parser_const.GRAMMAR_VALUE_NOT, {parser_const.KEY_VAR_NAME: "Flag"})) == "NOT(Flag)"
    assert format_expr((parser_const.KEY_COMPARE, {parser_const.KEY_VAR_NAME: "A"}, [])) == "A"
    assert format_expr((parser_const.KEY_COMPARE, {parser_const.KEY_VAR_NAME: "A"}, [(">", 1)])) == "A > 1"
    assert format_expr((parser_const.KEY_ADD, 1, [("+", 2)])) == "(1 + 2)"
    assert format_expr((parser_const.KEY_MUL, 2, [("*", 3)])) == "(2 * 3)"
    assert (
        format_expr((parser_const.KEY_FUNCTION_CALL, "CopyVariable", [{parser_const.KEY_VAR_NAME: "A"}, 1]))
        == "CopyVariable(A, 1)"
    )
    assert "('mystery', 1, 2)" in format_expr(("mystery", 1, 2))
    assert format_expr(SimpleNamespace(__str__=lambda self: "fallback")) != ""


def test_format_seq_nodes_covers_sfc_rendering_variants():
    assign_stmt = (parser_const.KEY_ASSIGN, {parser_const.KEY_VAR_NAME: "Out"}, 1)
    nodes = [
        SFCStep(
            kind="init",
            name="InitA",
            code=SFCCodeBlocks(enter=[assign_stmt], active=[assign_stmt], exit=[assign_stmt]),
        ),
        SFCTransition(name="ToRun", condition={parser_const.KEY_VAR_NAME: "Ready"}),
        SFCAlternative(branches=[[SFCFork(target="BranchA")], [SFCBreak()]]),
        SFCParallel(branches=[[SFCFork(target="P1")], [SFCFork(target="P2")]]),
        SFCSubsequence(name="SubA", body=[SFCFork(target="SubTarget")]),
        SFCTransitionSub(name="TransA", body=[SFCBreak()]),
        SFCFork(target="NextStep"),
        SFCBreak(),
        "fallback-node",
    ]

    rendered = format_seq_nodes(nodes)

    assert "InitStep InitA" in rendered
    assert "Enter:" in rendered
    assert "Active:" in rendered
    assert "Exit:" in rendered
    assert "Transition ToRun WAIT_FOR Ready" in rendered
    assert "Alternative:" in rendered
    assert "EndAlternative" in rendered
    assert "Parallel:" in rendered
    assert "EndParallel" in rendered
    assert "Subsequence SubA:" in rendered
    assert "EndSubsequence" in rendered
    assert "TransitionSub TransA:" in rendered
    assert "EndTransitionSub" in rendered
    assert "Fork to NextStep" in rendered
    assert "Break" in rendered
    assert "fallback-node" in rendered


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


def test_preprocess_sl_text_injects_modulecode_before_equationblock_when_missing():
    decoded, mapping = grammar_parser_decode.preprocess_sl_text(
        "MODULEDEFINITION Demo EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :"
    )

    assert "MODULEDEFINITION Demo ModuleCode EQUATIONBLOCK Main" in decoded
    assert mapping["#84"] == "ModuleCode"


def test_fuzz_harness_timeout_and_default_input_description(monkeypatch: pytest.MonkeyPatch):
    class FakeFuture:
        def result(self, timeout: float):
            assert timeout == 0.25
            raise parser_fuzz_harness.concurrent.futures.TimeoutError()

    class FakeExecutor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, source: str):
            assert fn is parser_fuzz_harness.parse_source_text
            assert source == "ABC"
            return FakeFuture()

    monkeypatch.setattr(
        parser_fuzz_harness.concurrent.futures,
        "ThreadPoolExecutor",
        lambda max_workers=1: FakeExecutor(),
    )
    result = parser_fuzz_harness.fuzz_parse_text("ABC", timeout=0.25)

    assert result.input_desc == "text(3 chars)"
    assert result.success is False
    assert isinstance(result.error, parser_fuzz_harness.TimeoutError)
    assert str(result.error) == "Parse timed out after 0.25s"
    assert result.duration_ms >= 0.0


def test_fuzz_harness_collect_corpus_inputs_uses_default_dir_and_skips_missing_or_unreadable_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    semantic_dir = tmp_path / "semantic"
    semantic_dir.mkdir()
    good_file = semantic_dir / "good.s"
    bad_file = semantic_dir / "bad.s"
    good_file.write_text("good", encoding="utf-8")
    bad_file.write_text("bad", encoding="utf-8")
    original_read_text = Path.read_text

    def fake_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == bad_file:
            raise OSError("unreadable")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(parser_fuzz_harness, "CORPUS_DIR", tmp_path)
    monkeypatch.setattr(Path, "read_text", fake_read_text)

    inputs = parser_fuzz_harness.collect_corpus_inputs(
        None,
        include_valid=False,
        include_invalid=True,
        include_edge_cases=False,
        include_semantic=True,
    )

    assert inputs == [(str(good_file), "good")]


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
        parser_api.parse_source_text(
            "A = 1;",
            parser=cast(Any, FakeParser()),
            transformer=cast(Any, FakeTransformer()),
            debug=events.append,
        )

    assert events == [
        "Parse OK, transforming with SLTransformer",
        "BasePicture does not allow dynamic attributes; parse tree not attached",
        "Transform result type: str",
    ]


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
