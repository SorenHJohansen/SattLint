# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportCallIssue=false
# ruff: noqa: F403, F405
from ._parser_core_test_support import *


def test_parse_source_text_preserves_sfc_step_code_blocks():
    bp = _parse_to_basepicture(
        '"SyntaxVersion"\n'
        '"OriginalFileDate"\n'
        '"ProgramDate"\n'
        "BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1\n"
        "LOCALVARIABLES\n"
        "   Flag: boolean := False;\n"
        "   Counter: integer := 0;\n"
        "ModuleDef\n"
        "ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )\n"
        "ModuleCode\n"
        "SEQUENCE Main (SeqControl) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0\n"
        "   SEQINITSTEP Init\n"
        "   SEQTRANSITION Tr1 WAIT_FOR True\n"
        "   SEQSTEP Run\n"
        "      ENTERCODE\n"
        "         Flag = True;\n"
        "      ACTIVECODE\n"
        "         Counter = 1;\n"
        "      EXITCODE\n"
        "         Counter = 0;\n"
        "   SEQTRANSITION Done WAIT_FOR False\n"
        "ENDSEQUENCE\n"
        "ENDDEF (*BasePicture*);\n"
    )

    sequence = bp.modulecode.sequences[0]
    run_step = next(node for node in sequence.code if isinstance(node, SFCStep) and node.name == "Run")

    assert len(run_step.code.enter) == 1
    assert len(run_step.code.active) == 1
    assert len(run_step.code.exit) == 1
    enter_stmt = run_step.code.enter[0]
    active_stmt = run_step.code.active[0]
    exit_stmt = run_step.code.exit[0]

    assert isinstance(enter_stmt, Tree)
    assert isinstance(active_stmt, Tree)
    assert isinstance(exit_stmt, Tree)
    assert enter_stmt.data == parser_const.KEY_STATEMENT
    assert active_stmt.data == parser_const.KEY_STATEMENT
    assert exit_stmt.data == parser_const.KEY_STATEMENT
    enter_assignment = cast(tuple[str, dict[str, Any], Any], enter_stmt.children[0])
    active_assignment = cast(tuple[str, dict[str, Any], Any], active_stmt.children[0])
    exit_assignment = cast(tuple[str, dict[str, Any], Any], exit_stmt.children[0])
    assert enter_stmt.children == [
        (parser_const.KEY_ASSIGN, {"var_name": "Flag", "state": None, "span": enter_assignment[1]["span"]}, True)
    ]
    assert active_assignment[0] == parser_const.KEY_ASSIGN
    assert active_assignment[1]["var_name"] == "Counter"
    assert active_assignment[2] == 1
    assert exit_assignment[0] == parser_const.KEY_ASSIGN
    assert exit_assignment[1]["var_name"] == "Counter"
    assert exit_assignment[2] == 0


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
                    {
                        parser_const.KEY_ASSIGN: {
                            parser_const.KEY_NAME: "Module_In_View",
                            parser_const.KEY_VALUE: True,
                            parser_const.KEY_TAIL: "Allow.RecpSupParameters",
                        },
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
    assert header.invoke_coord_tails == ["PosX", "Allow.RecpSupParameters"]
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
