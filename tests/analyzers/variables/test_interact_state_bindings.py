# pyright: reportPrivateUsage=false
"""Value-widget state bindings are reads as well as writes.

A text box, check box, option button, and combo button all display the state
they write, so the bound variable is read back to render the widget. A
momentary combo button without a toggle action is no exception. This is what
keeps a variable written in code and shown only by a widget out of the
``never_read`` class.
"""

from __future__ import annotations

import pytest
from sattline_parser import parse_source_text
from sattline_parser.models.ast_model import BasePicture

from sattlint.analyzers.variables import (
    IssueKind,
    VariablesAnalyzer,
    analyze_variables,
)
from sattlint.reporting.variables_report import (
    NeverReadIssue,
    UnusedIssue,
    WriteWithoutEffectIssue,
)

_SOURCE = """
"Syntax version 2.23, date: 2026-11-12-00:00:00.000 N"
"Original file date: ---"
"Program date: 2026-11-12-00:00:00.000, name: ValueWidgetBinding"
BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
   DisplayType = MODULEDEFINITION DateCode_ 2
   MODULEPARAMETERS
      Shown: %(datatype)s ;
   ModuleDef
   ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
   InteractObjects :
      %(widget)s ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
         %(body)s
   ENDDEF (*DisplayType*);

LOCALVARIABLES
   Source: %(datatype)s := %(literal)s;

SUBMODULES
   Display Invocation
      ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
       ) : DisplayType (
       Shown => Source );

ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
   EQUATIONBLOCK Main COORD 0.0 , 0.0 OBJSIZE 1.0 , 1.0 :
      Source = %(literal)s;
ENDDEF (*BasePicture*);
"""


def _source(widget: str, body: str, datatype: str, literal: str) -> str:
    return _SOURCE % {"widget": widget, "body": body, "datatype": datatype, "literal": literal}


_WIDGET_CASES = [
    pytest.param(
        "TextBox_",
        'Int_Value\n         Variable = 0 : OutVar_ "Shown"',
        "integer",
        "0",
        id="textbox",
    ),
    pytest.param(
        "CheckBox_",
        'Bool_Value\n         Variable = False : OutVar_ "Shown"',
        "boolean",
        "False",
        id="checkbox",
    ),
    pytest.param(
        "OptBut_",
        'Bool_Value\n         Variable = False : OutVar_ "Shown"',
        "boolean",
        "False",
        id="optbut",
    ),
    pytest.param(
        "ComBut_",
        'Bool_Value\n         Variable = False : OutVar_ "Shown" ToggleAction',
        "boolean",
        "False",
        id="combut-toggle",
    ),
    pytest.param(
        "ComBut_",
        'Bool_Value\n         Variable = False : OutVar_ "Shown"',
        "boolean",
        "False",
        id="combut-momentary",
    ),
]


def _analyze(source: str) -> tuple[BasePicture, VariablesAnalyzer]:
    base_picture = parse_source_text(source)
    analyzer = VariablesAnalyzer(base_picture, fail_loudly=False)
    analyzer.run()
    return base_picture, analyzer


@pytest.mark.parametrize(("widget", "body", "datatype", "literal"), _WIDGET_CASES)
def test_value_widget_state_binding_is_read_and_written(
    widget: str,
    body: str,
    datatype: str,
    literal: str,
) -> None:
    base_picture, analyzer = _analyze(_source(widget, body, datatype, literal))

    parameter = base_picture.moduletype_defs[0].moduleparameters[0]
    parameter_usage = analyzer._get_usage(parameter)
    assert parameter_usage.written is True
    assert parameter_usage.read is True
    assert parameter_usage.ui_read is True

    # The mapping into the widget is an input mapping, so the parent variable
    # written in code is read through it.
    source_usage = analyzer._get_usage(base_picture.localvariables[0])
    assert source_usage.written is True
    assert source_usage.read is True
    assert source_usage.ui_read is True


def test_variable_written_in_code_and_shown_only_by_widget_is_not_never_read() -> None:
    source = _source(
        "TextBox_",
        'Real_Value\n         Enable_ = True : InVar_ False Variable = 0.0 : OutVar_ "Shown"',
        "real",
        "0.0",
    )

    report = analyze_variables(
        parse_source_text(source),
        selected_issue_kinds=frozenset({IssueKind.NEVER_READ, IssueKind.UNUSED, IssueKind.WRITE_WITHOUT_EFFECT}),
    )

    reported = {
        (issue.kind, getattr(issue.variable, "name", None))
        for issue in report.issues
        if isinstance(issue, NeverReadIssue | UnusedIssue | WriteWithoutEffectIssue)
    }
    assert reported == set()


def test_widget_bound_local_has_no_write_without_effect() -> None:
    source = """
"Syntax version 2.23, date: 2026-11-12-00:00:00.000 N"
"Original file date: ---"
"Program date: 2026-11-12-00:00:00.000, name: WidgetLocal"
BasePicture Invocation
   ( 0.0 , 0.0 , 0.0 , 1.0 , 1.0
    ) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
   LocalDisplayType = MODULEDEFINITION DateCode_ 2
   LOCALVARIABLES
      Shown: boolean := False;
   ModuleDef
   ClippingBounds = ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
   InteractObjects :
      CheckBox_ ( 0.0 , 0.0 ) ( 1.0 , 1.0 )
         Bool_Value
         Variable = False : OutVar_ "Shown"
   ModuleCode
      EQUATIONBLOCK Main COORD 0.0 , 0.0 OBJSIZE 1.0 , 1.0 :
         Shown = True;
   ENDDEF (*LocalDisplayType*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

    report = analyze_variables(
        parse_source_text(source),
        selected_issue_kinds=frozenset(
            {IssueKind.NEVER_READ, IssueKind.UNUSED, IssueKind.WRITE_WITHOUT_EFFECT, IssueKind.READ_ONLY_NON_CONST}
        ),
    )

    # The widget displays the value it writes, so the write reaches a UI sink
    # instead of becoming a write without effect.
    assert not [
        issue
        for issue in report.issues
        if isinstance(issue, NeverReadIssue | UnusedIssue | WriteWithoutEffectIssue)
        and getattr(issue.variable, "name", None) == "Shown"
    ]


def test_combutproc_state_binding_stays_write_only() -> None:
    source = _source(
        "ComButProc_",
        'ToggleWindow\n         Variable = False : OutVar_ "Shown"',
        "boolean",
        "False",
    )

    base_picture, analyzer = _analyze(source)

    parameter_usage = analyzer._get_usage(base_picture.moduletype_defs[0].moduleparameters[0])
    assert parameter_usage.written is True
    assert parameter_usage.read is False
