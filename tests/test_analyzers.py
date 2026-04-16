"""Tests for analyzer behavior and reports."""

import logging

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattlint import constants as const
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.analyzers.shadowing import analyze_shadowing
from sattlint.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FloatLiteral,
    IntLiteral,
    ModuleTypeDef,
    ModuleTypeInstance,
    ModuleHeader,
    ModuleCode,
    ParameterMapping,
    Sequence,
    Simple_DataType,
    SingleModule,
    SFCTransition,
    SourceSpan,
    Variable,
)
from sattlint.reporting.variables_report import VariablesReport
from sattlint.resolution.scope import ScopeContext


def _hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def _varref(s: str) -> dict:
    return {const.KEY_VAR_NAME: s}


def test_min_max_mapping_mismatch_detected():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[
            Variable(name="MaxValue", datatype=Simple_DataType.INTEGER)
        ],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MaxValue"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("MinValue"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="MinValue", datatype=Simple_DataType.INTEGER),
            Variable(name="MaxValue", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(
        i.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH for i in analyzer.issues
    )


def test_min_max_mapping_mismatch_not_raised_for_aligned_names():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[
            Variable(name="MinValue", datatype=Simple_DataType.INTEGER)
        ],
        localvariables=[],
        submodules=[],
        modulecode=None,
        parametermappings=[
            ParameterMapping(
                target=_varref("MinValue"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("MinValue"),
                source_literal=None,
            )
        ],
    )

    parent = SingleModule(
        header=_hdr("Parent"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="MinValue", datatype=Simple_DataType.INTEGER)
        ],
        submodules=[child],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[parent],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        i.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH for i in analyzer.issues
    )


def test_magic_number_detection_in_equations_and_sfc():
    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.KEY_ASSIGN,
                _varref("Output"),
                IntLiteral(42, SourceSpan(12, 5)),
            )
        ],
    )

    transition = SFCTransition(
        name="ToNext",
        condition=(
            const.KEY_COMPARE,
            _varref("Output"),
            [(">", FloatLiteral(2.5, SourceSpan(20, 7)))],
        ),
    )

    seq = Sequence(
        name="SeqMain",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[transition],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        localvariables=[
            Variable(name="Output", datatype=Simple_DataType.INTEGER)
        ],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    magic = [i for i in analyzer.issues if i.kind is IssueKind.MAGIC_NUMBER]
    assert len(magic) == 2

    values = sorted(i.literal_value for i in magic if i.literal_value is not None)
    assert values == [2.5, 42]

    spans = {
        (i.literal_span.line, i.literal_span.column)
        for i in magic
        if i.literal_span is not None
    }
    assert (12, 5) in spans
    assert (20, 7) in spans


def test_shadowing_detected_for_nested_locals():
    child = SingleModule(
        header=_hdr("Child"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[Variable(name="value", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="Value", datatype=Simple_DataType.INTEGER)],
        submodules=[child],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_shadowing(bp)

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_shadowing_detected_for_moduletype_instance_locals():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[
            Variable(name="setting", datatype=Simple_DataType.INTEGER)
        ],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
    )

    report = analyze_shadowing(bp)

    assert any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_variable_analysis_marks_invar_reads_across_graphics_and_interact_paths():
    code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0 : InVar_ "PosX",0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    PosX: integer := 0;
    PanelResize: integer := 0;
    WidthSource: integer := 0;
    FormatSource: integer := 0;
    ColourSource: integer := 0;
    ButtonTypeSource: integer := 0;
ModuleDef
    ClippingBounds = ( -1.0 , -1.0 : InVar_ "PanelResize" ) ( 1.0 , 1.0 )
    GraphObjects :
        TextObject ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            "Value" VarName Width_ = 5 : InVar_ "WidthSource"
            Format_String_ = "" : InVar_ "FormatSource"
            OutlineColour : Colour0 = 5 : InVar_ "ColourSource"
    InteractObjects :
        ComBut_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
            ButtonType = 0 : InVar_ "ButtonTypeSource"
ENDDEF (*BasePicture*);
"""

    bp = parser_core_parse_source_text(code)
    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    usage_by_name = {
        variable.name: analyzer._get_usage(variable)
        for variable in bp.localvariables
    }

    assert usage_by_name["PosX"].read is True
    assert usage_by_name["PanelResize"].read is True
    assert usage_by_name["WidthSource"].read is True
    assert usage_by_name["FormatSource"].read is True
    assert usage_by_name["ColourSource"].read is True
    assert usage_by_name["ButtonTypeSource"].read is True


def test_graphics_format_tail_keywords_do_not_log_missing_variables(caplog):
    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[Variable(name="RealSource", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    analyzer = VariablesAnalyzer(bp, debug=True)
    context = ScopeContext(
        env={"realsource": bp.localvariables[0]},
        param_mappings={},
        module_path=[bp.header.name],
        display_module_path=[bp.header.name],
    )

    with caplog.at_level(logging.DEBUG, logger="SattLint"):
        for token in ("Real_Value", "Relative_", "Decimal_", "Int_Value", "Abs_"):
            analyzer._walk_tail(token, context, [bp.header.name])
        analyzer._walk_tail("RealSource", context, [bp.header.name])
        analyzer._walk_tail("MissingVar", context, [bp.header.name])

    messages = [record.message for record in caplog.records]

    assert not any("real_value" in message.lower() for message in messages)
    assert not any("relative_" in message.lower() for message in messages)
    assert not any("decimal_" in message.lower() for message in messages)
    assert not any("int_value" in message.lower() for message in messages)
    assert not any("abs_" in message.lower() for message in messages)
    assert any("missingvar" in message.lower() for message in messages)
    assert analyzer._get_usage(bp.localvariables[0]).read is True


def test_shadowing_ignores_external_moduletype_instance_locals_for_program_target():
    mt = ModuleTypeDef(
        name="TypeA",
        moduleparameters=[],
        localvariables=[Variable(name="Setting", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="TypeA.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("InstanceA"),
        moduletype_name="TypeA",
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[mt],
        localvariables=[Variable(name="setting", datatype=Simple_DataType.INTEGER)],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    report = analyze_shadowing(bp)

    assert not any(i.kind is IssueKind.SHADOWING for i in report.issues)


def test_variable_analysis_ignores_external_moduletype_usage_for_program_target():
    library_mt = ModuleTypeDef(
        name="LibType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("Input")],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibType.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("LibInst"),
        moduletype_name="LibType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("ProgramVar"),
                source_literal=None,
            )
        ],
    )

    program_var = Variable(name="ProgramVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[library_mt],
        localvariables=[program_var],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProgramLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert any(
        issue.kind is IssueKind.UNUSED and issue.variable is program_var
        for issue in analyzer.issues
    )


def test_variable_analysis_treats_external_moduletype_usage_as_used_for_library_target():
    library_mt = ModuleTypeDef(
        name="LibType",
        moduleparameters=[Variable(name="Input", datatype=Simple_DataType.INTEGER)],
        localvariables=[],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="E1",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[_varref("Input")],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibType.x",
        origin_lib="SomeLib",
    )

    instance = ModuleTypeInstance(
        header=_hdr("LibInst"),
        moduletype_name="LibType",
        parametermappings=[
            ParameterMapping(
                target=_varref("Input"),
                source_type=const.TREE_TAG_VARIABLE_NAME,
                is_duration=False,
                is_source_global=False,
                source=_varref("LibraryVar"),
                source_literal=None,
            )
        ],
    )

    library_var = Variable(name="LibraryVar", datatype=Simple_DataType.INTEGER)
    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[library_mt],
        localvariables=[library_var],
        submodules=[instance],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    analyzer.run()

    assert not any(issue.variable is library_var for issue in analyzer.issues)


def test_library_typedef_moduleparameter_unused_fields_are_suppressed():
    record_type = DataType(
        name="RecType",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="Used", datatype=Simple_DataType.INTEGER),
            Variable(name="Unused", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    exported = ModuleTypeDef(
        name="ExportedType",
        moduleparameters=[Variable(name="p", datatype="RecType")],
        localvariables=[Variable(name="sink", datatype=Simple_DataType.INTEGER)],
        submodules=[],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_ASSIGN,
                            _varref("sink"),
                            _varref("p.Used"),
                        )
                    ],
                )
            ]
        ),
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[exported],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    program_analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=False)
    program_analyzer.run()
    assert any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in program_analyzer.issues
    )

    library_analyzer = VariablesAnalyzer(bp, analyzed_target_is_library=True)
    library_analyzer.run()
    assert not any(
        issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "RecType"
        and issue.field_path == "Unused"
        for issue in library_analyzer.issues
    )


def test_unused_datatype_fields_are_aggregated_across_variables():
    record_type = DataType(
        name="SharedRecord",
        description=None,
        datecode=None,
        var_list=[
            Variable(name="A", datatype=Simple_DataType.INTEGER),
            Variable(name="B", datatype=Simple_DataType.INTEGER),
            Variable(name="C", datatype=Simple_DataType.INTEGER),
        ],
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    first = Variable(name="First", datatype="SharedRecord")
    second = Variable(name="Second", datatype="SharedRecord")

    module = SingleModule(
        header=_hdr("M1"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[first, second],
        submodules=[],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _varref("sinkA"), _varref("First.A")),
                        (const.KEY_ASSIGN, _varref("sinkB"), _varref("Second.B")),
                    ],
                )
            ]
        ),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[record_type],
        moduletype_defs=[],
        localvariables=[
            Variable(name="sinkA", datatype=Simple_DataType.INTEGER),
            Variable(name="sinkB", datatype=Simple_DataType.INTEGER),
        ],
        submodules=[module],
        modulecode=None,
        moduledef=None,
        origin_file="Root.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    unused_fields = {
        issue.field_path
        for issue in analyzer.issues
        if issue.kind is IssueKind.UNUSED_DATATYPE_FIELD
        and issue.datatype_name == "SharedRecord"
    }

    assert unused_fields == {"C"}


def test_datatype_duplication_is_scoped_per_module_and_excludes_anytype():
    fyld = ModuleTypeDef(
        name="Fyld",
        moduleparameters=[
            Variable(name="WildcardA", datatype="AnyType"),
            Variable(name="WildcardB", datatype="AnyType"),
        ],
        localvariables=[
            Variable(name="PhaseTimer", datatype="Timer"),
            Variable(name="PhaseTimerCopy", datatype="Timer"),
        ],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )
    applik = ModuleTypeDef(
        name="Applik",
        moduleparameters=[Variable(name="WildcardC", datatype="AnyType")],
        localvariables=[Variable(name="PhaseTimer", datatype="Timer")],
        submodules=[],
        moduledef=None,
        modulecode=None,
        parametermappings=[],
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    bp = BasePicture(
        header=_hdr("BasePicture"),
        datatype_defs=[],
        moduletype_defs=[fyld, applik],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
        origin_file="LibraryRoot.x",
        origin_lib="ProjectLib",
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    duplication_issues = [
        issue for issue in analyzer.issues if issue.kind is IssueKind.DATATYPE_DUPLICATION
    ]
    assert len(duplication_issues) == 1

    issue = duplication_issues[0]
    assert issue.module_path == ["BasePicture", "TypeDef:Fyld"]
    assert issue.variable is not None
    assert issue.variable.name == "PhaseTimer"
    assert issue.variable.datatype_text == "Timer"
    assert issue.duplicate_count == 2
    assert issue.duplicate_locations == [
        (["BasePicture", "TypeDef:Fyld"], "localvariable", "PhaseTimerCopy")
    ]

    summary = VariablesReport(basepicture_name=bp.header.name, issues=duplication_issues).summary()
    assert "Datatype 'Timer' declared 2 times in BasePicture.TypeDef:Fyld:" in summary
    assert "+ PhaseTimerCopy (localvariable)" in summary
    assert "AnyType" not in summary
    assert "TypeDef:Applik" not in summary


def test_reset_contamination_detected_for_missing_reset_write():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[],
    )

    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OperationSequence.Reset")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OprSeqResetOld")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Other"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                ],
                [],
            ),
            (
                const.KEY_ASSIGN,
                _varref("OprSeqResetOld"),
                _varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="Other", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="OprSeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    issues = [
        i
        for i in analyzer.issues
        if i.kind is IssueKind.RESET_CONTAMINATION
    ]
    assert any(i.variable and i.variable.name == "Counter" for i in issues)


def test_reset_contamination_cleared_when_reset_writes_present():
    seq = Sequence(
        name="OperationSequence",
        type="sequence",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[],
    )

    eq = Equation(
        name="Main",
        position=(0.0, 0.0),
        size=(1.0, 1.0),
        code=[
            (
                const.GRAMMAR_VALUE_IF,
                [
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OperationSequence.Reset")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                    (
                        (const.GRAMMAR_VALUE_NOT, _varref("OprSeqResetOld")),
                        [
                            (
                                const.KEY_ASSIGN,
                                _varref("Counter"),
                                _varref("ResetValue"),
                            )
                        ],
                    ),
                ],
                [],
            ),
            (
                const.KEY_ASSIGN,
                _varref("OprSeqResetOld"),
                _varref("OperationSequence.Reset"),
            ),
        ],
    )

    mod = SingleModule(
        header=_hdr("Unit"),
        moduledef=None,
        moduleparameters=[],
        localvariables=[
            Variable(name="Counter", datatype=Simple_DataType.INTEGER),
            Variable(name="ResetValue", datatype=Simple_DataType.INTEGER),
            Variable(name="OprSeqResetOld", datatype=Simple_DataType.BOOLEAN),
        ],
        submodules=[],
        modulecode=ModuleCode(sequences=[seq], equations=[eq]),
        parametermappings=[],
    )

    bp = BasePicture(
        header=_hdr("Root"),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[mod],
        modulecode=None,
        moduledef=None,
    )

    analyzer = VariablesAnalyzer(bp)
    analyzer.run()

    assert not any(
        i.kind is IssueKind.RESET_CONTAMINATION for i in analyzer.issues
    )
