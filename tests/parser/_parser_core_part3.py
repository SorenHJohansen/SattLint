# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportCallIssue=false
# ruff: noqa: F403, F405
from ._parser_core_test_support import *


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
    assert mixin.moduletype_par_transfer(["TargetLiteral", "SourceLiteral"]).target == {
        parser_const.KEY_VAR_NAME: "TargetLiteral"
    }
    assert mixin.moduletype_par_transfer([123, "SourceLiteral"]).target == {parser_const.KEY_VAR_NAME: "123"}
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


def test_ast_model_helpers_cover_reduce_usage_and_string_formats(monkeypatch: pytest.MonkeyPatch):  # noqa: PLR0915
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
