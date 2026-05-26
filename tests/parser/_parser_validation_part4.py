# ruff: noqa: F403, F405
from sattline_parser.models.ast_model import ModuleTypeInstance, SingleModule

from ._parser_validation_test_support import *


def test_validate_single_file_syntax_rejects_consecutive_transitions_in_sequence_path(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR True
        SEQTRANSITION TrNext WAIT_FOR True
        SEQSTEP Running
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "ConsecutiveTransitions.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "only one transition may execute per cycle" in result.message


def test_validate_single_file_syntax_rejects_step_reset_without_seqcontrol(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Flag: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR Start.Reset
        SEQSTEP Running
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StepResetWithoutSeqControl.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "only exposes .Reset when its sequence enables SeqControl" in result.message


def test_validate_single_file_syntax_accepts_step_reset_with_seqcontrol(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSeq (SeqControl) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR Start.Reset
        SEQSTEP Running
    ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StepResetWithSeqControl.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_sequence_reset_without_seqcontrol(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR MainSeq.Reset
        SEQSTEP Running
    ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "SequenceResetWithoutSeqControl.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "sequence 'MainSeq' only exposes .Reset when it enables SeqControl" in result.message


def test_validate_single_file_syntax_accepts_sequence_reset_and_hold_with_seqcontrol(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    si: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    OPENSEQUENCE MainSeq (SeqControl) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR False
        SEQSTEP Running
    ENDOPENSEQUENCE
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF NOT MainSeq.Reset AND NOT MainSeq.Hold THEN
            si = 1;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "SequenceResetHoldWithSeqControl.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_step_timer_without_seqtimer(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    SEQUENCE MainSeq COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
        SEQINITSTEP Start
        SEQTRANSITION TrStart WAIT_FOR Start.T >= 1
        SEQSTEP Running
    ENDSEQUENCE
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StepTimerWithoutSeqTimer.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "only exposes .T when its sequence enables SeqTimer" in result.message


def test_validate_single_file_syntax_rejects_old_on_non_state_variable(tmp_path):
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
        IF Counter:Old THEN
            Counter = 1;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "OldOnNonState.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "uses OLD on non-STATE variable 'Counter'" in result.message


def test_validate_single_file_syntax_accepts_old_on_state_record_field(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    CmdType = RECORD DateCode_ 1
        WaterPipeFull: boolean State;
        Other: boolean;
    ENDDEF (*CmdType*);
LOCALVARIABLES
    CMD: CmdType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF CMD.WaterPipeFull:Old THEN
            CMD.Other = True;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "OldOnStateRecordField.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_assignment_to_old_state_access(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Counter: boolean State := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Counter:Old = True;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "AssignOldStateAccess.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "must not use OLD state access" in result.message


def test_validation_internal_reserved_keywords_skip_non_string_grammar_values(monkeypatch):
    monkeypatch.setattr(validation_module.const, "GRAMMAR_VALUE_FAKE_NUMBER", 123, raising=False)

    reserved = validation_module._build_reserved_identifier_keywords()

    assert "123" not in reserved


def test_validation_internal_declared_variable_returns_for_untyped_literal(monkeypatch):
    variable = Variable(name="Value", datatype=Simple_DataType.INTEGER, init_value=object())

    monkeypatch.setattr(validation_module, "_infer_literal_datatype", lambda *args, **kwargs: None)

    validation_module._validate_declared_variable(
        variable,
        "test",
        type_graph=TypeGraph.from_datatypes([]),
        known_datatypes=(),
    )


def test_validation_internal_declared_variable_returns_for_workspace_external_datatype():
    variable = Variable(name="Value", datatype="ExternalType", init_value=1)

    validation_module._validate_declared_variable(
        variable,
        "test",
        type_graph=TypeGraph.from_datatypes([]),
        known_datatypes=(),
        allow_unresolved_external_datatypes=True,
    )


def test_validation_internal_collect_sequence_labels_keeps_first_casefolded_label():
    nodes = [
        SFCStep(kind="init", name="Start", code=SFCCodeBlocks()),
        SFCTransition(name="Run", condition=True),
        SFCStep(kind="step", name="run", code=SFCCodeBlocks()),
    ]

    labels: dict[str, str] = {}

    validation_module._collect_sequence_labels(nodes, labels, "test sequence")

    assert labels == {"start": "Start", "run": "Run"}


def test_validation_internal_validate_sequence_nodes_warns_for_multiple_init_steps():
    warnings = []
    nodes = [
        SFCStep(kind="init", name="Start", code=SFCCodeBlocks()),
        SFCTransition(name="TrStart", condition=True),
        SFCStep(kind="init", name="Restart", code=SFCCodeBlocks()),
    ]

    validation_module._validate_sequence_nodes(
        nodes,
        "test sequence",
        labels={},
        label_counts={},
        env={},
        type_graph=TypeGraph.from_datatypes([]),
        require_init_step=True,
        warning_sink=warnings.append,
    )

    assert all(hasattr(warning, "message") for warning in warnings)
    assert any("outside the first position" in warning.message for warning in warnings)
    assert any("must contain exactly one SEQINITSTEP" in warning.message for warning in warnings)


def test_validation_internal_iter_sequence_node_refs_collects_step_and_transition_refs():
    refs = validation_module._iter_sequence_node_refs(
        [
            SFCStep(
                kind="step",
                name="Running",
                code=SFCCodeBlocks(
                    enter=[_var_ref("Start.Hold")],
                    active=[(_var_ref("Start.Reset"),)],
                    exit=[],
                ),
            ),
            SFCTransition(name="TrDone", condition=_var_ref("Running.T")),
        ]
    )

    assert refs == [_var_ref("Start.Hold"), _var_ref("Start.Reset"), _var_ref("Running.T")]


def test_validation_internal_step_auto_variable_refs_cover_skip_and_hold_paths():
    validation_module._validate_step_auto_variable_refs(None, {}, "test module")

    modulecode = ModuleCode(
        sequences=cast(
            Any,
            [
                object(),
                Sequence(
                    name="MainSeq",
                    type="sequence",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[SFCStep(kind="init", name="Start", code=SFCCodeBlocks())],
                ),
            ],
        ),
        equations=[
            cast(Any, object()),
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[
                    _var_ref(123),
                    _var_ref("Local.Reset"),
                    _var_ref("MainSeq.Hold"),
                ],
            ),
        ],
    )

    with pytest.raises(StructuralValidationError, match=r"sequence 'MainSeq' only exposes \.Hold"):
        validation_module._validate_step_auto_variable_refs(
            modulecode,
            {"local": Variable(name="Local", datatype=Simple_DataType.BOOLEAN)},
            "test module",
        )


def test_validation_internal_variable_refs_skip_missing_record_field():
    record_graph = TypeGraph.from_datatypes(
        [
            DataType(
                name="RecordType",
                description=None,
                datecode=1,
                var_list=[Variable(name="Present", datatype=Simple_DataType.BOOLEAN, state=True)],
            )
        ]
    )

    validation_module._validate_variable_refs(
        [_var_ref("Config.Missing", state="Old")],
        {"config": Variable(name="Config", datatype="RecordType", state=True)},
        record_graph,
        "test module",
    )


def test_validation_internal_module_code_skips_non_equation_and_sequence_entries():
    validation_module._validate_module_code(
        ModuleCode(
            sequences=cast(Any, [object()]),
            equations=cast(Any, [object()]),
        ),
        "test module",
        {},
        TypeGraph.from_datatypes([]),
    )


def test_validation_internal_module_recurses_into_unknown_moduletype_instance_targets():
    validation_module._validate_module(
        SingleModule(
            header=ModuleHeader(name="Parent", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
            moduledef=None,
            submodules=[
                ModuleTypeInstance(
                    header=ModuleHeader(name="Child", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
                    moduletype_name="MissingType",
                    parametermappings=[
                        ParameterMapping(
                            target=_var_ref("Value"),
                            source_type="value",
                            is_duration=False,
                            is_source_global=False,
                            source_literal=1,
                        )
                    ],
                )
            ],
        ),
        "BasePicture",
        {},
        TypeGraph.from_datatypes([]),
        (),
        {},
    )


def test_validate_transformed_basepicture_skips_non_moduletype_entries():
    validate_transformed_basepicture(
        BasePicture(
            header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
            moduletype_defs=cast(Any, [object()]),
        )
    )


@pytest.mark.parametrize(
    ("ref_name", "expected_message"),
    [
        ("Missing.Reset", "no sequence step named 'Missing' exists in this module"),
        ("Start.Hold", "step 'Start' only exposes .Hold when its sequence enables SeqControl"),
    ],
)
def test_validation_internal_step_auto_variable_refs_reports_missing_and_step_hold(ref_name, expected_message):
    modulecode = ModuleCode(
        sequences=[
            Sequence(
                name="MainSeq",
                type="sequence",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[SFCStep(kind="init", name="Start", code=SFCCodeBlocks())],
            )
        ],
        equations=[
            Equation(
                name="Main",
                position=(0.0, 0.0),
                size=(1.0, 1.0),
                code=[_var_ref(ref_name)],
            )
        ],
    )

    with pytest.raises(StructuralValidationError, match=expected_message):
        validation_module._validate_step_auto_variable_refs(modulecode, {}, "test module")


def test_validation_internal_parallel_branch_trailer_recognizes_all_branch_markers():
    assert validation_module._parallel_branch_trailer(SFCTransitionSub(name="Tr", body=[])) == "SUBSEQTRANSITION"
    assert validation_module._parallel_branch_trailer(SFCFork(target="Target")) == "SEQFORK"
    assert validation_module._parallel_branch_trailer(SFCBreak()) == "SEQBREAK"


def test_validation_internal_variable_refs_skip_unknown_roots_and_simple_field_access():
    validation_module._validate_variable_refs(
        [
            _var_ref("Missing", state="Old"),
            _var_ref("Counter.Child", state="Old"),
        ],
        {"counter": Variable(name="Counter", datatype=Simple_DataType.INTEGER, state=False)},
        TypeGraph.from_datatypes([]),
        "test module",
    )
