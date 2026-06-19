# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false
from __future__ import annotations

import textwrap

from sattline_parser import strip_sl_comments
from sattline_parser.models.ast_model import BasePicture
from sattline_parser.transformer.sl_transformer import SLTransformer
from sattlint.analyzers.state_inference import analyze_state_inference
from sattlint.engine import create_sl_parser


def _parse_to_basepicture(localvariables: str, equation_code: str) -> BasePicture:
    source = textwrap.dedent(
        f"""
        \"SyntaxVersion\"
        \"OriginalFileDate\"
        \"ProgramDate\"
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
    parser = create_sl_parser()
    tree = parser.parse(strip_sl_comments(source))
    return SLTransformer().transform(tree)


def _issue_kinds(report) -> set[str]:
    return {issue.kind for issue in report.issues}


def test_state_inference_reports_impossible_numeric_branch():
    bp = _parse_to_basepicture(
        localvariables="""
            Count: integer := 5;
        """,
        equation_code="""
                IF Count < 0 THEN
                    Count = 0;
                ENDIF;
        """,
    )

    report = analyze_state_inference(bp)

    assert "state_inference.condition_always_false" in _issue_kinds(report)
    assert "state_inference.unreachable_branch" in _issue_kinds(report)
    assert report.summary_data["summary"]["numeric_range_count"] >= 1


def test_state_inference_reports_stable_boolean_state():
    bp = _parse_to_basepicture(
        localvariables="""
            Flag: boolean := True;
        """,
        equation_code="""
                IF Flag THEN
                    Flag = Flag;
                ENDIF;
        """,
    )

    report = analyze_state_inference(bp)

    assert "state_inference.condition_always_true" in _issue_kinds(report)
    assert report.summary_data["summary"]["boolean_state_count"] >= 1


def test_state_inference_summary_tracks_string_mode_as_stable_state_without_finding():
    bp = _parse_to_basepicture(
        localvariables="""
            Mode: string := \"RUN\";
        """,
        equation_code="""
                Mode = Mode;
        """,
    )

    report = analyze_state_inference(bp)

    assert report.issues == []
    assert report.summary().startswith("Report: State inference")
