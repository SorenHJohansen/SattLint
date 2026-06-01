# ruff: noqa: F403, F405
from ._parser_core_test_support import *


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
    assert simple.properties[parser_const.KEY_TAILS] == ["CoordTail", "TailVar", "EnableVar"]

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
        SFCAlternative(branches=[[SFCFork(targets=("BranchA",))], [SFCBreak()]]),
        SFCParallel(branches=[[SFCFork(targets=("P1",))], [SFCFork(targets=("P2",))]]),
        SFCSubsequence(name="SubA", body=[SFCFork(targets=("SubTarget",))]),
        SFCTransitionSub(name="TransA", body=[SFCBreak()]),
        SFCFork(targets=("NextStep",)),
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
