# pyright: reportPrivateUsage=false
from __future__ import annotations

import textwrap
from typing import Any, cast

from sattline_parser import strip_sl_comments
from sattline_parser.models.ast_model import (
    AstNodeDict,
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    Simple_DataType,
    Variable,
)
from sattline_parser.transformer.sl_transformer import SLTransformer
from sattlint import constants as const
from sattlint.analyzers.dataflow import DataflowAnalyzer, analyze_dataflow
from sattlint.analyzers.framework import AnalysisSharedArtifacts, SimpleReport, VariableAnalysisArtifacts
from sattlint.analyzers.registry import get_default_analyzers
from sattlint.engine import create_sl_parser


def _parse_to_basepicture(localvariables: str, equation_code: str) -> BasePicture:
    source = textwrap.dedent(
        f"""
        "SyntaxVersion"
        "OriginalFileDate"
        "ProgramDate"
        BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
        LOCALVARIABLES
        {localvariables}
        ModuleDef
        ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
        ModuleCode
            EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        {equation_code}
        ENDDEF (*BasePicture*);
        """
    )
    parser = cast(Any, create_sl_parser())
    tree = parser.parse(strip_sl_comments(source))
    return SLTransformer().transform(tree)


def _issue_kinds(report: SimpleReport) -> set[str]:
    return {issue.kind for issue in report.issues}


def _varref(name: str) -> AstNodeDict:
    return {const.KEY_VAR_NAME: name}


def _state_ref(name: str, state: str) -> AstNodeDict:
    return {const.KEY_VAR_NAME: name, "state": state}


def test_branch_join_produces_constant_condition():
    bp = _parse_to_basepicture(
        localvariables="""
            Start: boolean;
            Flag: boolean := False;
        """,
        equation_code="""
                IF Start THEN
                    Flag = True;
                ELSE
                    Flag = True;
                ENDIF;
                IF Flag THEN
                    Flag = Flag;
                ENDIF;
        """,
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.condition_always_true"
        and issue.data is not None
        and issue.data.get("condition") == "Flag"
        for issue in report.issues
    )


def test_else_branch_assumption_makes_nested_condition_false():
    bp = _parse_to_basepicture(
        localvariables="""
            Start: boolean;
            Output: integer := 0;
        """,
        equation_code="""
                IF Start THEN
                    Output = 1;
                ELSE
                    IF Start THEN
                        Output = 2;
                    ENDIF;
                ENDIF;
        """,
    )

    report = analyze_dataflow(bp)

    assert "dataflow.condition_always_false" in _issue_kinds(report)
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_read_before_write_is_reported_for_uninitialized_reads():
    bp = _parse_to_basepicture(
        localvariables="""
            Input: boolean;
            Output: boolean;
        """,
        equation_code="""
                Output = Input;
        """,
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.read_before_write" and issue.data is not None and issue.data.get("symbol") == "Input"
        for issue in report.issues
    )


def test_dataflow_analyzer_reuses_shared_variable_type_graph(monkeypatch: Any) -> None:
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        datatype_defs=[],
        moduletype_defs=[],
        localvariables=[],
        submodules=[],
        modulecode=None,
        moduledef=None,
    )
    shared_graph = object()
    shared_artifacts = AnalysisSharedArtifacts(
        variable_analysis=VariableAnalysisArtifacts(
            type_graph=cast(Any, shared_graph),
            typedef_index={},
            dependency_library_display_names={},
            root_env={},
            any_var_index={},
        )
    )

    def _unexpected_build(_base_picture: BasePicture) -> Any:
        raise AssertionError("TypeGraph.from_basepicture should not run when shared artifacts are available")

    monkeypatch.setattr("sattlint.analyzers.dataflow.TypeGraph.from_basepicture", _unexpected_build)

    analyzer = DataflowAnalyzer(bp, shared_artifacts=shared_artifacts)

    assert analyzer._type_graph is shared_graph


def test_branch_merge_preserves_initialized_unknown_values():
    bp = _parse_to_basepicture(
        localvariables="""
            Start: boolean;
            Flag: boolean;
        """,
        equation_code="""
                IF Start THEN
                    Flag = True;
                ELSE
                    Flag = False;
                ENDIF;
                IF Flag THEN
                    Start = True;
                ENDIF;
        """,
    )

    report = analyze_dataflow(bp)

    assert not any(
        issue.kind == "dataflow.read_before_write" and issue.data is not None and issue.data.get("symbol") == "Flag"
        for issue in report.issues
    )


def test_dead_overwrite_is_reported_for_back_to_back_writes():
    bp = _parse_to_basepicture(
        localvariables="""
            Flag: boolean;
        """,
        equation_code="""
                Flag = True;
                Flag = False;
        """,
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.dead_overwrite" and issue.data is not None and issue.data.get("symbol") == "Flag"
        for issue in report.issues
    )


def test_dead_overwrite_is_not_reported_after_intervening_read():
    bp = _parse_to_basepicture(
        localvariables="""
            Flag: boolean;
            Output: boolean;
        """,
        equation_code="""
                Flag = True;
                Output = Flag;
                Flag = False;
        """,
    )

    report = analyze_dataflow(bp)

    assert not any(
        issue.kind == "dataflow.dead_overwrite" and issue.data is not None and issue.data.get("symbol") == "Flag"
        for issue in report.issues
    )


def test_putarray_marks_array_as_written_for_following_reads() -> None:
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[
            Variable(name="Arr", datatype="ArrayObject"),
            Variable(name="Source", datatype=Simple_DataType.INTEGER, init_value=1),
            Variable(name="Target", datatype=Simple_DataType.INTEGER),
            Variable(name="Status", datatype=Simple_DataType.INTEGER),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Write",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_FUNCTION_CALL, "PutArray", [_varref("Arr"), 1, _varref("Source"), _varref("Status")])
                    ],
                ),
                Equation(
                    name="Read",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_FUNCTION_CALL, "GetArray", [_varref("Arr"), 1, _varref("Target"), _varref("Status")])
                    ],
                ),
            ]
        ),
    )

    report = analyze_dataflow(bp)

    array_issues = [
        issue
        for issue in report.issues
        if issue.kind == "dataflow.read_before_write" and issue.data is not None and issue.data.get("symbol") == "Arr"
    ]

    assert len(array_issues) == 1
    assert array_issues[0].data is not None
    assert array_issues[0].data.get("site") == "EQ:Write"


def test_same_scan_old_read_is_reported_after_state_write():
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _state_ref("Flag", "new"), True),
                        (const.KEY_ASSIGN, _varref("Output"), _state_ref("Flag", "old")),
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.scan_cycle_stale_read"
        and issue.data is not None
        and issue.data.get("symbol") == "Flag:Old"
        for issue in report.issues
    )


def test_old_reads_used_for_edge_detection_are_not_reported_as_stale():
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[
            Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (const.KEY_ASSIGN, _state_ref("Flag", "new"), True),
                        (
                            const.KEY_ASSIGN,
                            _varref("Output"),
                            (
                                const.KEY_COMPARE,
                                _state_ref("Flag", "new"),
                                [("<>", _state_ref("Flag", "old"))],
                            ),
                        ),
                    ],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert not any(issue.kind == "dataflow.scan_cycle_stale_read" for issue in report.issues)


def test_assigning_to_old_is_reported_as_temporal_misuse():
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        localvariables=[Variable(name="Flag", datatype=Simple_DataType.BOOLEAN, state=True)],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _state_ref("Flag", "old"), True)],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.scan_cycle_temporal_misuse"
        and issue.data is not None
        and issue.data.get("symbol") == "Flag:Old"
        for issue in report.issues
    )


def test_old_on_non_state_nested_field_is_reported():
    bp = BasePicture(
        header=ModuleHeader(name="Root", invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0)),
        datatype_defs=[
            DataType(
                name="RegressionType",
                description=None,
                datecode=None,
                var_list=[Variable(name="Running", datatype=Simple_DataType.BOOLEAN)],
            ),
            DataType(
                name="SelfType",
                description=None,
                datecode=None,
                var_list=[Variable(name="Regression", datatype="RegressionType")],
            ),
        ],
        localvariables=[
            Variable(name="Self", datatype="SelfType"),
            Variable(name="Output", datatype=Simple_DataType.BOOLEAN),
        ],
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="Main",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[(const.KEY_ASSIGN, _varref("Output"), _state_ref("Self.Regression.Running", "old"))],
                )
            ]
        ),
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.invalid_state_access"
        and issue.data is not None
        and issue.data.get("symbol") == "Self.Regression.Running:Old"
        for issue in report.issues
    )


def test_contradictory_boolean_condition_is_inferred_false():
    bp = _parse_to_basepicture(
        localvariables="""
            Flag: boolean;
            Output: boolean;
        """,
        equation_code="""
                IF Flag AND NOT Flag THEN
                    Output = True;
                ENDIF;
        """,
    )

    report = analyze_dataflow(bp)

    assert "dataflow.condition_always_false" in _issue_kinds(report)
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_tautological_boolean_condition_is_inferred_true():
    bp = _parse_to_basepicture(
        localvariables="""
            Flag: boolean;
            Output: boolean;
        """,
        equation_code="""
                IF Flag OR NOT Flag THEN
                    Output = True;
                ELSE
                    Output = False;
                ENDIF;
        """,
    )

    report = analyze_dataflow(bp)

    assert "dataflow.condition_always_true" in _issue_kinds(report)
    assert "dataflow.unreachable_branch" in _issue_kinds(report)


def test_contradictory_compare_condition_is_inferred_false():
    bp = _parse_to_basepicture(
        localvariables="""
            Counter: integer;
            Output: boolean;
        """,
        equation_code="""
                IF Counter == 1 AND Counter == 2 THEN
                    Output = True;
                ENDIF;
        """,
    )

    report = analyze_dataflow(bp)

    assert any(
        issue.kind == "dataflow.condition_always_false"
        and issue.data is not None
        and "Counter == 1" in str(issue.data.get("condition"))
        and "Counter == 2" in str(issue.data.get("condition"))
        for issue in report.issues
    )


def test_dataflow_analyzer_is_enabled_by_default():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "dataflow" in specs
    assert specs["dataflow"].enabled is True


def test_state_inference_analyzer_is_registered():
    specs = {spec.key: spec for spec in get_default_analyzers()}

    assert "state-inference" in specs
    assert specs["state-inference"].enabled is True
