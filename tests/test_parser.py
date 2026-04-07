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


def test_validate_single_file_syntax_rejects_comment_outside_equation_or_sequence(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	TransferRequest: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	(*
		Keep output publishing separate from guard evaluation.
		The regression steps update latched request variables, and this block
		republishes them every scan so the TransferPanel one-shot signals are
		continuously reasserted while a step needs them.
	*)
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		TransferRequest = False;
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "CommentOutsideEquationOrSequence.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.line == 11
	assert result.column == 2
	assert result.message is not None
	assert "only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks" in result.message


def test_validate_single_file_syntax_allows_comment_inside_equation_block(tmp_path):
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
		(* This comment is allowed inside an equation block. *)
		Counter = Counter + 1;
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "CommentInsideEquation.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is True
	assert result.stage == "ok"


def test_validate_single_file_syntax_allows_comment_inside_sequence_block(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	OPENSEQUENCE MainSequence (SeqControl) COORD 0.0, 0.2 OBJSIZE 2.0, 1.68
		(* This comment is allowed inside a sequence block. *)
		SEQINITSTEP InitSim
		SEQTRANSITION Start WAIT_FOR True
		SEQSTEP Running
	ENDOPENSEQUENCE
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "CommentInsideSequence.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is True
	assert result.stage == "ok"


def test_validate_single_file_syntax_allows_top_level_comment_outside_modulecode(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
(*
	1998-11-20 08:11 FDH
	Library created
*)
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "TopLevelCommentAllowed.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is True
	assert result.stage == "ok"


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


def test_validate_single_file_syntax_rejects_builtin_function_datatype_mismatch(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	Name1: string;
	Flag: boolean := False;
	Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		Match = EqualStrings(Name1, Flag, True);
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "BuiltinFunctionDatatypeMismatch.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "call 'EqualStrings' argument 2 has datatype 'boolean'" in result.message
	assert "expects 'string'" in result.message


def test_validate_single_file_syntax_rejects_builtin_procedure_datatype_mismatch(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	SourceDuration: duration;
	DestinationTime: time;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		CopyTime(SourceDuration, DestinationTime);
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "BuiltinProcedureDatatypeMismatch.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "call 'CopyTime' argument 1 has datatype 'duration'" in result.message
	assert "expects 'time'" in result.message


def test_validate_single_file_syntax_allows_builtin_string_family_match(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	Name1: identstring;
	Name2: string;
	Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		Match = EqualStrings(Name1, Name2, True);
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "BuiltinStringFamilyMatch.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is True
	assert result.stage == "ok"


def test_validate_single_file_syntax_rejects_builtin_arity_mismatch(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	Name1: string;
	Name2: string;
	Match: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		Match = EqualStrings(Name1, Name2);
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "BuiltinArityMismatch.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "call 'EqualStrings' has 2 arguments but builtin expects 3" in result.message


def test_validate_single_file_syntax_rejects_builtin_in_var_expression(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	SourceTime: time;
	DestinationTime: time;
	UseSource: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		CopyTime(IF UseSource THEN SourceTime ELSE SourceTime ENDIF, DestinationTime);
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "BuiltinInVarExpression.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "call 'CopyTime' argument 1 must be a variable reference" in result.message
	assert "is 'in var'" in result.message


def test_validate_single_file_syntax_rejects_builtin_out_expression(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	SourceTime: time;
	DestinationTime: time;
	UseDestination: boolean := False;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		CopyTime(SourceTime, IF UseDestination THEN DestinationTime ELSE DestinationTime ENDIF);
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "BuiltinOutExpression.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "call 'CopyTime' argument 2 must be a variable reference" in result.message
	assert "is 'out'" in result.message
