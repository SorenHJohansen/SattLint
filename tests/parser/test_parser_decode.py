from __future__ import annotations

from sattline_parser.grammar import parser_decode as grammar_parser_decode


def test_decode_compressed_normalizes_marker_prefixes_and_common_quirks() -> None:
    decoded = grammar_parser_decode.decode_compressed(
        " ".join(
            [
                "#01Tail",
                "#0<",
                "#0<Remark",
                "ENDDEF;",
                "; :=",
                "ENDIF; ,",
                "ENDIF; )",
                ":= ;",
                "GraphObjects : InteractObjects",
                'duration := "5s"',
                'time OpSave := "6s"',
                '=> "2024-01-02-03:04:05.678"',
                "ExecuteLocalOld = ExecuteLocal:Old ENDDEF",
                "ExecuteState:Old IF",
                "integer ENDDEF",
                "Enable_ = Flag : OutVar_",
                "TrueVar",
            ]
        ),
        grammar_parser_decode.SEED_MAPPING,
    )

    assert "(Tail" in decoded
    assert "*" in decoded
    assert "* Remark" in decoded
    assert "ENDDEF" in decoded and "ENDDEF;" not in decoded
    assert " :=" in decoded
    assert "ENDIF," in decoded
    assert "ENDIF)" in decoded
    assert ":= Default;" in decoded
    assert "InteractObjects" in decoded
    assert 'Duration_Value "5s"' in decoded
    assert 'Time_Value "6s"' in decoded
    assert '=> Time_Value "2024-01-02-03:04:05.678"' in decoded
    assert "ExecuteLocalOld = ExecuteLocal:Old; ENDDEF" in decoded
    assert "ExecuteState:Old; IF" in decoded
    assert "integer ; ENDDEF" in decoded
    assert "Enable_ = Flag : InVar_" in decoded
    assert "TTrueVar" in decoded


def test_preprocess_sl_text_keeps_existing_modulecode_and_fills_empty_trailing_args() -> None:
    decoded, _mapping = grammar_parser_decode.preprocess_sl_text(
        "MODULEDEFINITION Demo ModuleCode EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 : Func(a, )"
    )

    assert decoded.count("ModuleCode EQUATIONBLOCK") == 1
    assert "Func(a, 0)" in decoded


def test_decode_compressed_covers_marker_and_cleanup_quirks() -> None:
    decoded = grammar_parser_decode.decode_compressed(
        "#01Tail #0< #0<Flag #99 ENDIF GraphObjects : ENDDEF boolean ENDDEF Enable_ = Demo: OutVar_",
        {"#99": "Token"},
    )

    assert "(Tail" in decoded
    assert "*" in decoded
    assert "* Flag" in decoded
    assert "Token" in decoded
    assert "ENDIF;" in decoded
    assert "boolean ; ENDDEF" in decoded
    assert "Enable_ = Demo: InVar_" in decoded
    assert "GraphObjects : ENDDEF" not in decoded


def test_is_compressed_covers_false_and_true_heuristics() -> None:
    assert grammar_parser_decode.is_compressed("MODULEDEFINITION Demo EQUATIONBLOCK Main") is False
    assert grammar_parser_decode.is_compressed(" ".join(["#01X"] * 10)) is True
