# ruff: noqa: F403, F405
from ._parser_validation_test_support import *


def test_validation_internal_parameter_mappings_cover_skip_and_target_branches():
    policy = validation_module._ModuleValidationPolicy()

    validation_module._validate_parameter_mappings(
        cast(
            Any,
            [
                object(),
                ParameterMapping(
                    target=_var_ref("Value"),
                    source_type="value",
                    is_duration=False,
                    is_source_global=False,
                    source_literal=1,
                ),
            ],
        ),
        "test module",
        type_graph=TypeGraph.from_datatypes([]),
        expected_parameters={"value": Variable(name="Value", datatype=Simple_DataType.INTEGER)},
        policy=policy,
    )

    with pytest.raises(StructuralValidationError, match="uses field access on non-record parameter 'Value'"):
        validation_module._validate_parameter_mappings(
            [
                ParameterMapping(
                    target=_var_ref("Value.Child"),
                    source_type="value",
                    is_duration=False,
                    is_source_global=False,
                    source_literal=1,
                )
            ],
            "test module",
            type_graph=TypeGraph.from_datatypes([]),
            expected_parameters={"value": Variable(name="Value", datatype=Simple_DataType.INTEGER)},
            policy=policy,
        )

    record_graph = TypeGraph.from_datatypes(
        [
            DataType(
                name="RecordParam",
                description=None,
                datecode=1,
                var_list=[Variable(name="Present", datatype=Simple_DataType.INTEGER)],
            )
        ]
    )
    with pytest.raises(StructuralValidationError, match=r"parameter mapping target 'Config\.Missing' does not exist"):
        validation_module._validate_parameter_mappings(
            [
                ParameterMapping(
                    target=_var_ref("Config.Missing"),
                    source_type="value",
                    is_duration=False,
                    is_source_global=False,
                    source_literal=1,
                )
            ],
            "test module",
            type_graph=record_graph,
            expected_parameters={"config": Variable(name="Config", datatype="RecordParam")},
            policy=policy,
        )

    validation_module._validate_parameter_mappings(
        [
            ParameterMapping(
                target=_var_ref("External.Child"),
                source_type="value",
                is_duration=False,
                is_source_global=False,
                source_literal=1,
            )
        ],
        "test module",
        type_graph=TypeGraph.from_datatypes([]),
        expected_parameters={"external": Variable(name="External", datatype="UnresolvedExternalType")},
        policy=policy,
    )


def test_validation_internal_parameter_mappings_fallback_to_target_variable_datatype(monkeypatch):
    monkeypatch.setattr(validation_module, "_resolve_variable_field_datatype", lambda *args, **kwargs: None)

    validation_module._validate_parameter_mappings(
        [
            ParameterMapping(
                target=_var_ref("Value"),
                source_type="value",
                is_duration=False,
                is_source_global=False,
                source_literal=1,
            )
        ],
        "test module",
        type_graph=TypeGraph.from_datatypes([]),
        expected_parameters={"value": Variable(name="Value", datatype=Simple_DataType.INTEGER)},
        policy=validation_module._ModuleValidationPolicy(),
    )


@pytest.mark.parametrize(
    ("target_name", "datatype", "source_literal", "is_duration", "expected_message"),
    [
        (
            "Delay",
            Simple_DataType.DURATION,
            "bad",
            True,
            "maps invalid duration literal 'bad' to parameter target 'Delay'",
        ),
        (
            "Stamp",
            Simple_DataType.TIME,
            {validation_module.const.GRAMMAR_VALUE_TIME_VALUE: "bad"},
            False,
            "maps invalid time literal 'bad' to parameter target 'Stamp'",
        ),
    ],
)
def test_validation_internal_parameter_mappings_reject_invalid_literal_shapes(
    target_name,
    datatype,
    source_literal,
    is_duration,
    expected_message,
):
    with pytest.raises(StructuralValidationError, match=expected_message):
        validation_module._validate_parameter_mappings(
            [
                ParameterMapping(
                    target=_var_ref(target_name),
                    source_type="value",
                    is_duration=is_duration,
                    is_source_global=False,
                    source_literal=source_literal,
                )
            ],
            "test module",
            type_graph=TypeGraph.from_datatypes([]),
            expected_parameters={target_name.casefold(): Variable(name=target_name, datatype=datatype)},
            policy=validation_module._ModuleValidationPolicy(),
        )


def test_validation_internal_datatypes_reject_single_field_record():
    datatype = DataType(
        name="SingleFieldType",
        description=None,
        datecode=1,
        var_list=[Variable(name="OnlyField", datatype=Simple_DataType.INTEGER)],
    )

    with pytest.raises(StructuralValidationError, match=r"datatype 'SingleFieldType' must declare at least 2 fields"):
        validation_module._validate_datatypes(
            [datatype],
            "test module",
            type_graph=TypeGraph.from_datatypes([]),
            known_datatypes=(),
        )


def test_validation_internal_datatypes_allow_zero_field_record():
    datatype = DataType(
        name="ZeroFieldType",
        description=None,
        datecode=1,
        var_list=[],
    )

    validation_module._validate_datatypes(
        [datatype],
        "test module",
        type_graph=TypeGraph.from_datatypes([]),
        known_datatypes=(),
    )


def test_validate_single_file_syntax_rejects_old_on_non_state_record_field(tmp_path):
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
        IF CMD.Other:Old THEN
            CMD.Other = True;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "OldOnNonStateRecordField.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "uses OLD on non-STATE variable 'CMD.Other'" in result.message


def test_validate_single_file_syntax_rejects_old_on_non_state_nested_self_field(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    RegressionType = RECORD DateCode_ 1
        Running: boolean;
        Enabled: boolean;
    ENDDEF (*RegressionType*);
    SelfType = RECORD DateCode_ 1
        Regression: RegressionType;
        Mirror: RegressionType;
    ENDDEF (*SelfType*);
LOCALVARIABLES
    Self: SelfType;
    Output: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        IF Self.Regression.Running:Old THEN
            Output = True;
        ENDIF;
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "OldOnNonStateNestedSelfField.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "uses OLD on non-STATE variable 'Self.Regression.Running'" in result.message


def test_load_source_text_preserves_state_markers_in_compressed_libraries():
    cases = [
        ("StateMarkersLib.x", "GetRemoteFile", "ExecuteLocal"),
        ("StateMarkersLib.x", "zRestoreStringList", "ExecuteState"),
        ("StateMarkersLib.x", "EventLogger2", "CurrentEventFinished"),
        ("StateMarkersLib.x", "MMSWriteVar", "Rdy"),
        ("StateMarkersLib.x", "ReportGeneralTable", "Ready"),
    ]

    for file_name, moduletype_name, variable_name in cases:
        source_path = _official_library_fixture_path(file_name)
        src = _load_source_text(source_path)
        basepicture = parser_core_parse_source_text(src)
        moduletype = next(
            (
                item
                for item in (basepicture.moduletype_defs or [])
                if item.name.casefold() == moduletype_name.casefold()
            ),
            None,
        )

        assert moduletype is not None, f"missing moduletype {moduletype_name} in {file_name}"

        variable = next(
            (
                item
                for item in [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])]
                if item.name.casefold() == variable_name.casefold()
            ),
            None,
        )

        assert variable is not None, f"missing variable {variable_name} in {file_name}"
        assert variable.state is True, f"expected {file_name}:{moduletype_name}.{variable_name} to decode as State"


def test_load_source_text_preserves_duration_value_in_compressed_libraries():
    journal_path = _official_library_fixture_path("DurationTypesLib.x")
    journal_src = _load_source_text(journal_path)
    assert 'Duration_Value "1h"' in journal_src
    assert 'Time_Value "1984-01-01-00:00:00.000"' in journal_src

    journal_basepicture = parser_core_parse_source_text(journal_src)
    curve_type = next(
        (item for item in (journal_basepicture.datatype_defs or []) if item.name.casefold() == "Curve4Par".casefold()),
        None,
    )
    assert curve_type is not None

    field = next(
        (item for item in (curve_type.var_list or []) if item.name.casefold() == "TimeRange".casefold()),
        None,
    )
    assert field is not None
    assert field.init_value == "1h"
    assert field.init_is_duration is True

    jou_read_tag_type = next(
        (
            item
            for item in (journal_basepicture.datatype_defs or [])
            if item.name.casefold() == "JouReadTagType".casefold()
        ),
        None,
    )
    assert jou_read_tag_type is not None

    start_time = next(
        (item for item in (jou_read_tag_type.var_list or []) if item.name.casefold() == "StartTime".casefold()),
        None,
    )
    assert start_time is not None
    assert isinstance(start_time.init_value, dict)
    assert start_time.init_value.get("Time_Value") == "1984-01-01-00:00:00.000"

    assert 'Duration_Value "590ms"' in journal_src


def test_validate_single_file_syntax_accepts_reported_compressed_library_files():
    file_names = [
        "StateMarkersLib.x",
        "DurationTypesLib.x",
        "SLIoUnitFixture.x",
    ]

    for file_name in file_names:
        result = validate_single_file_syntax(_official_library_fixture_path(file_name))
        assert result.ok is True, f"{file_name}: {result.stage} {result.message}"


def test_validate_single_file_syntax_rejects_string_literal_in_call_argument(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    DummyType = RECORD DateCode_ 1
        StepText: string;
        StepIndex: integer;
    ENDDEF (*DummyType*);
LOCALVARIABLES
    Dummy: boolean := False;
    Self: DummyType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Dummy = EqualStrings(Self.StepText, "Log", True);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StringLiteralInCall.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'EqualStrings' argument 2 uses string literal 'Log'" in result.message


def test_validate_single_file_syntax_allows_string_literal_parameter_connection(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
    MessageModule = MODULEDEFINITION DateCode_ 1
    MODULEPARAMETERS
        StepName: string;
    ModuleDef
    ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
    ENDDEF (*MessageModule*);
SUBMODULES
    Msg Invocation (0.0,0.0,0.0,1.0,1.0) : MessageModule (
        StepName => "Log"
    );
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "StringLiteralParameterConnection.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_builtin_function_datatype_mismatch(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Name1: string;
    Flag: boolean := False;
    Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Match = EqualStrings(Name1, Flag, True);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinFunctionDatatypeMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'EqualStrings' argument 2 has datatype 'boolean'" in result.message
    assert "expects 'string'" in result.message


def test_validate_single_file_syntax_rejects_builtin_procedure_datatype_mismatch(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    SourceDuration: duration;
    DestinationTime: time;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        CopyTime(SourceDuration, DestinationTime);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinProcedureDatatypeMismatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is False
    assert result.stage == "validation"
    assert result.message is not None
    assert "call 'CopyTime' argument 1 has datatype 'duration'" in result.message
    assert "expects 'time'" in result.message


def test_validate_single_file_syntax_allows_builtin_string_family_match(tmp_path):
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    Name1: identstring;
    Name2: string;
    Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Match = EqualStrings(Name1, Name2, True);
ENDDEF (*BasePicture*);
"""
    source_file = tmp_path / "BuiltinStringFamilyMatch.s"
    source_file.write_text(code, encoding="utf-8")

    result = validate_single_file_syntax(source_file)

    assert result.ok is True
    assert result.stage == "ok"
