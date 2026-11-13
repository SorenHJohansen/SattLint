# pyright: reportPrivateUsage=false
"""Root module parameters participate in variable analysis like locals."""

from __future__ import annotations

from sattline_parser import parse_source_text

from sattlint.analyzers.variables import VariablesAnalyzer, _build_variable_analysis_artifacts

SOURCE = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
MODULEPARAMETERS
    Param: integer;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        Param = Param;
ENDDEF (*BasePicture*);
"""


def test_root_parameter_self_assignment_is_a_write() -> None:
    base_picture = parse_source_text(SOURCE)
    analyzer = VariablesAnalyzer(base_picture, fail_loudly=False)
    analyzer.run()

    parameter = base_picture.moduleparameters[0]
    usage = analyzer.get_usage(parameter)

    assert usage.written is True


def test_root_parameters_are_in_the_variable_artifacts() -> None:
    base_picture = parse_source_text(SOURCE)

    artifacts = _build_variable_analysis_artifacts(base_picture)

    assert "param" in artifacts.root_env
    assert "param" in artifacts.any_var_index
