"""Parser-level tests for SattLine grammar coverage."""

import pytest

from sattlint import constants as const
from sattlint.engine import (
	StructuralValidationError,
	create_sl_parser,
	parse_source_file,
	strip_sl_comments,
	validate_transformed_basepicture,
	validate_single_file_syntax,
)
from sattlint.models.ast_model import BasePicture, ModuleHeader, Simple_DataType, Variable
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


def test_parse_source_file_accepts_valid_file(tmp_path):
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
	source_file = tmp_path / "ValidProgram.s"
	source_file.write_text(code, encoding="utf-8")

	bp = parse_source_file(source_file)

	assert bp.name == "BasePicture"


def test_validate_single_file_syntax_reports_location(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	Counter: integer := 0
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		Counter = Counter + 1;
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "InvalidProgram.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "parse"
	assert result.line is not None
	assert result.message


def test_validate_single_file_syntax_rejects_missing_transition(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	OPENSEQUENCE MainSimulation (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
		SEQINITSTEP InitSim
		SEQTRANSITION StartSimulation WAIT_FOR Sim.Start
		SEQSTEP StopBatchIfActive
			ENTERCODE
				BatchControl.Sim.ActivateMES_Stop = True;
		SEQSTEP StartBatch
			ENTERCODE
				BatchControl.Sim.ActivateMES_Start = True;
	ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "MissingTransition.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "without an intervening transition" in result.message


def test_validate_transformed_basepicture_rejects_long_identifier():
	bp = BasePicture(
		header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
		localvariables=[
			Variable(name="IdentifierLengthOver20", datatype=Simple_DataType.INTEGER)
		],
	)

	with pytest.raises(StructuralValidationError, match="exceeds 20 characters"):
		validate_transformed_basepicture(bp)


def test_validate_single_file_syntax_rejects_duplicate_variable_names(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	PumpCmd: integer := 0;
	pumpcmd: integer := 1;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "DuplicateVars.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "duplicate variable names" in result.message


def test_validate_single_file_syntax_rejects_unknown_seqfork_target(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	OPENSEQUENCE MainSimulation (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
		SEQINITSTEP InitSim
		SEQTRANSITION StartSimulation WAIT_FOR True
		SEQSTEP Running
		ALTERNATIVESEQ
			SEQTRANSITION Jump WAIT_FOR True
			SEQFORK MissingTarget
			SEQBREAK
		ALTERNATIVEBRANCH
			SEQTRANSITION Stay WAIT_FOR False
		ENDALTERNATIVE
	ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "UnknownForkTarget.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "SEQFORK target 'MissingTarget'" in result.message


def test_validate_single_file_syntax_rejects_old_on_non_state_variable(tmp_path):
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
		IF Counter:Old THEN
			Counter = 1;
		ENDIF;
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "OldOnNonState.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "uses OLD on non-STATE variable 'Counter'" in result.message


def test_validate_single_file_syntax_rejects_string_literal_in_call_argument(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	DummyType = RECORD DateCode_ 1
		StepText: string;
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
