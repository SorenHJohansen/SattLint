"""Parser-level tests for SattLine grammar coverage."""

import pytest

from sattlint import constants as const
from sattlint.engine import create_sl_parser, strip_sl_comments
from sattlint.transformer.sl_transformer import SLTransformer


def _parse_to_basepicture(text: str):
	parser = create_sl_parser()
	tree = parser.parse(strip_sl_comments(text))
	return SLTransformer().transform(tree)


def test_ternary_if_has_lowest_precedence():
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	A: integer := 0;
	B: integer := 1;
	C: integer := 2;
	D: integer := 3;
	X: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		X = IF A > 0 THEN B ELSE C + D ENDIF;
ENDDEF (*BasePicture*);
"""
	bp = _parse_to_basepicture(code)
	stmt = bp.modulecode.equations[0].code[0]
	assert stmt[0] == const.KEY_ASSIGN

	expr = stmt[2]
	assert expr[0] == const.KEY_TERNARY

	else_expr = expr[2]
	assert else_expr[0] == const.KEY_ADD
	assert else_expr[1][const.KEY_VAR_NAME].casefold() == "c"
	assert else_expr[2][0][0] == "+"
	assert else_expr[2][0][1][const.KEY_VAR_NAME].casefold() == "d"


def test_quoted_identifier_length_is_limited_to_20_chars():
	long_name = "'QuotedIdentifierLength21'"  # 25 chars without quotes
	code = f"""
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	{long_name}: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		{long_name} = 1;
ENDDEF (*BasePicture*);
"""
	parser = create_sl_parser()
	with pytest.raises(Exception):
		parser.parse(strip_sl_comments(code))
