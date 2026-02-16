"""Tests for analyzer behavior and reports."""

from sattlint import constants as const
from sattlint.analyzers.variables import IssueKind, VariablesAnalyzer
from sattlint.analyzers.shadowing import analyze_shadowing
from sattlint.models.ast_model import (
    BasePicture,
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

    values = sorted(i.literal_value for i in magic)
    assert values == [2.5, 42]

    spans = {(i.literal_span.line, i.literal_span.column) for i in magic}
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
