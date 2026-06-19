# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownLambdaType=false, reportArgumentType=false
from types import SimpleNamespace

from sattline_parser.grammar import constants as const
from sattline_parser.models import ast_model
from sattline_parser.utils import formatter


class _StatementNode:
    def __init__(self, child) -> None:
        self.data = const.KEY_STATEMENT
        self.children = [child]


def test_format_list_handles_empty_and_inline_rendering():
    assert formatter.format_list([]) == "[]"

    rendered = formatter.format_list(["A", "B"], inline_if_singleline=True)
    assert rendered == "[A, B]"


def test_format_list_aligns_variable_like_rows():
    vars_like = [
        ast_model.Variable(name="A", datatype="integer", global_var=True),
        ast_model.Variable(name="Longer", datatype="string", const=True, state=True),
    ]

    rendered = formatter.format_list(vars_like)

    assert rendered.startswith("[\n")
    assert "Name:" in rendered
    assert "Datatype:" in rendered
    assert "Global:" in rendered


def test_format_optional_and_literal_expression_rendering():
    assert formatter.format_optional(None) == "None"
    assert formatter.format_optional(5) == "5"

    assert formatter.format_expr({const.KEY_VAR_NAME: "MyVar"}) == "MyVar"
    assert formatter.format_expr("Text") == "'Text'"
    assert formatter.format_expr(True) == "True"


def test_format_expr_handles_statements_and_operators():
    statement = _StatementNode((const.KEY_ASSIGN, {const.KEY_VAR_NAME: "A"}, 4))
    if_expr = (
        const.GRAMMAR_VALUE_IF,
        [
            (True, [statement]),
            (False, [(const.KEY_ASSIGN, {const.KEY_VAR_NAME: "B"}, 2)]),
        ],
        [(const.KEY_ASSIGN, {const.KEY_VAR_NAME: "C"}, 3)],
    )
    ternary_expr = ("Ternary", [(True, "X")], "Y")

    rendered_if = formatter.format_expr(if_expr)
    rendered_ternary = formatter.format_expr(ternary_expr)
    rendered_or = formatter.format_expr((const.GRAMMAR_VALUE_OR, ["A", "B"]))
    rendered_and = formatter.format_expr((const.GRAMMAR_VALUE_AND, ["A", "B"]))
    rendered_not = formatter.format_expr((const.GRAMMAR_VALUE_NOT, "A"))
    rendered_compare = formatter.format_expr((const.KEY_COMPARE, "A", [(">", 1)]))
    rendered_add = formatter.format_expr((const.KEY_ADD, 1, [("+", 2)]))
    rendered_mul = formatter.format_expr((const.KEY_MUL, 2, [("*", 3)]))
    rendered_call = formatter.format_expr((const.KEY_FUNCTION_CALL, "Fn", [1, "x"]))
    rendered_fallback = formatter.format_expr(("unknown-op", 1))

    assert "IF True" in rendered_if
    assert "ELSIF False" in rendered_if
    assert "ELSE" in rendered_if
    assert "ENDIF" in rendered_if
    assert "THEN" in rendered_ternary
    assert "'A' OR" in rendered_or
    assert "'A' AND" in rendered_and
    assert rendered_not == "NOT('A')"
    assert rendered_compare == "'A' > 1"
    assert rendered_add == "(1 + 2)"
    assert rendered_mul == "(2 * 3)"
    assert rendered_call == "Fn(1, 'x')"
    assert rendered_fallback.startswith("('unknown-op', 1)")


def test_format_seq_nodes_renders_all_node_types():
    step = ast_model.SFCStep(
        kind="init",
        name="Start",
        code=ast_model.SFCCodeBlocks(
            enter=[(const.KEY_ASSIGN, {const.KEY_VAR_NAME: "A"}, 1)],
            active=[(const.KEY_ASSIGN, {const.KEY_VAR_NAME: "B"}, 2)],
            exit=[(const.KEY_ASSIGN, {const.KEY_VAR_NAME: "C"}, 3)],
        ),
    )
    nodes = [
        step,
        ast_model.SFCTransition(name="T1", condition=True),
        ast_model.SFCAlternative(branches=[[ast_model.SFCFork(targets=("X",))]]),
        ast_model.SFCParallel(branches=[[ast_model.SFCBreak()]]),
        ast_model.SFCSubsequence(name="Sub", body=[ast_model.SFCFork(targets=("Y",))]),
        ast_model.SFCTransitionSub(name="TS", body=[ast_model.SFCBreak()]),
        ast_model.SFCFork(targets=("Z",)),
        ast_model.SFCBreak(),
        SimpleNamespace(__str__=lambda self: "FallbackNode"),
    ]

    rendered = formatter.format_seq_nodes(nodes)

    assert "InitStep Start" in rendered
    assert "Transition T1 WAIT_FOR True" in rendered
    assert "Alternative:" in rendered
    assert "EndAlternative" in rendered
    assert "Parallel:" in rendered
    assert "EndParallel" in rendered
    assert "Subsequence Sub:" in rendered
    assert "EndSubsequence" in rendered
    assert "TransitionSub TS:" in rendered
    assert "EndTransitionSub" in rendered
    assert "Fork to Z" in rendered
    assert "Break" in rendered
