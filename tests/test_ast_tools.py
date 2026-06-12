from __future__ import annotations

from types import SimpleNamespace

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.grammar import constants as const
from sattlint.core.ast_tools import iter_call_sites, iter_variable_refs


def test_iter_call_sites_reads_flat_procedure_payloads() -> None:
    node = {
        const.KEY_PROCEDURE: {
            const.KEY_NAME: "ToggleWindow",
            const.KEY_ARGS: [{const.KEY_VAR_NAME: "XSize"}],
        }
    }

    assert list(iter_call_sites(node)) == [
        ("procedure", "ToggleWindow", ({const.KEY_VAR_NAME: "XSize"},)),
    ]


def test_iter_call_sites_ignores_wrapped_procedure_payloads() -> None:
    node = {
        const.KEY_PROCEDURE_CALL: {
            const.KEY_NAME: "ToggleWindow",
            const.KEY_ARGS: [{const.KEY_VAR_NAME: "XSize"}],
        }
    }

    assert list(iter_call_sites(node)) == []


def test_iter_variable_refs_walks_nested_dicts_and_tuple_children() -> None:
    node = {
        "outer": [
            {"inner": {const.KEY_VAR_NAME: "Alpha"}},
            SimpleNamespace(children=({const.KEY_VAR_NAME: "Beta"},)),
        ]
    }

    assert list(iter_variable_refs(node)) == [
        {const.KEY_VAR_NAME: "Alpha"},
        {const.KEY_VAR_NAME: "Beta"},
    ]


def test_iter_variable_refs_walks_parser_produced_modulecode() -> None:
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
        Counter = Counter + 1;
ENDDEF (*BasePicture*);
"""

    base_picture = parser_core_parse_source_text(code)

    refs = [ref[const.KEY_VAR_NAME] for ref in iter_variable_refs(base_picture.modulecode)]

    assert refs == ["Counter", "Counter"]


def test_iter_call_sites_walks_nested_dicts_and_children_variants() -> None:
    function_call = (const.KEY_FUNCTION_CALL, "DoThing", [{const.KEY_VAR_NAME: "Arg"}])
    procedure_payload = {
        const.KEY_NAME: "ToggleWindow",
        const.KEY_ARGS: [{const.KEY_VAR_NAME: "XSize"}],
        "nested": function_call,
    }
    node = {
        "wrapper": function_call,
        "children": [
            SimpleNamespace(children=[procedure_payload]),
            SimpleNamespace(children=(function_call,)),
        ],
    }

    assert list(iter_call_sites(node)) == [
        ("function", "DoThing", ({const.KEY_VAR_NAME: "Arg"},)),
        ("procedure", "ToggleWindow", ({const.KEY_VAR_NAME: "XSize"},)),
        ("function", "DoThing", ({const.KEY_VAR_NAME: "Arg"},)),
        ("function", "DoThing", ({const.KEY_VAR_NAME: "Arg"},)),
    ]
