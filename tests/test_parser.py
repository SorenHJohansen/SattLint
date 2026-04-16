"""Parser-level tests for SattLine grammar coverage."""

import pytest

from sattline_parser import api as parser_api
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser import strip_sl_comments
from sattlint import constants as const
from sattlint.engine import (
	StructuralValidationError,
	create_sl_parser,
	parse_source_file,
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


def test_parser_core_reuses_default_parser(monkeypatch):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	A: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		A = A + 1;
ENDDEF (*BasePicture*);
"""

	call_count = 0
	real_create_parser = parser_api.create_parser
	parser_api._default_parser.cache_clear()

	def counting_create_parser():
		nonlocal call_count
		call_count += 1
		return real_create_parser()

	monkeypatch.setattr(parser_api, "create_parser", counting_create_parser)

	parser_api.parse_source_text(code)
	parser_api.parse_source_text(code)

	assert call_count == 1
	parser_api._default_parser.cache_clear()


def test_parser_core_parse_source_text_accepts_valid_source():
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	A: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		A = A + 1;
ENDDEF (*BasePicture*);
"""

	bp = parser_core_parse_source_text(code)

	assert isinstance(bp, BasePicture)
	assert bp.name == "BasePicture"


def test_parser_core_sets_sequence_control_and_timer_flags():
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	SEQUENCE MainSeq (SeqControl, SeqTimer) COORD 0.0, 0.0 OBJSIZE 1.0, 1.0
		SEQINITSTEP Start
		SEQTRANSITION Tr1 WAIT_FOR False
	ENDSEQUENCE
ENDDEF (*BasePicture*);
"""

	bp = parser_core_parse_source_text(code)

	assert bp.modulecode is not None
	assert bp.modulecode.sequences is not None
	seq = bp.modulecode.sequences[0]
	assert seq.seqcontrol is True
	assert seq.seqtimer is True


def test_parser_core_emits_declaration_and_reference_spans():
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
""".strip()

	bp = parser_core_parse_source_text(code)
	declared = bp.localvariables[0]
	assert bp.modulecode is not None
	assert bp.modulecode.equations is not None
	assignment = bp.modulecode.equations[0].code[0]
	target = assignment[1]
	value_ref = assignment[2][1]

	assert declared.declaration_span is not None
	assert declared.declaration_span.line == 6
	assert declared.declaration_span.column == 2
	assert bp.header.declaration_span is not None
	assert bp.header.declaration_span.line == 4
	assert target["span"].line == 11
	assert target["span"].column == 3
	assert value_ref["span"].line == 11
	assert value_ref["span"].column == 13


def test_parser_core_preserves_invar_tails_in_invoke_coords_and_clipping_bounds():
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0 : InVar_ "PosX",0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	PosX: integer := 0;
	PanelResize: integer := 0;
ModuleDef
	ClippingBounds = ( -1.0 , -1.0 : InVar_ "PanelResize" ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""

	bp = parser_core_parse_source_text(code)

	assert bp.header.invoke_coord_tails == ["PosX"]
	assert bp.moduledef is not None
	assert bp.moduledef.properties[const.KEY_TAILS] == ["PanelResize"]


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


def test_validate_single_file_syntax_rejects_builtin_datatype_typo(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	si: intege;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "DatatypeTypo.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.line == 7
	assert result.message is not None
	assert "unknown datatype 'intege'" in result.message
	assert "did you mean 'integer'" in result.message


def test_validate_single_file_syntax_rejects_init_value_type_mismatch(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	Counter: integer := "bad";
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "InitTypeMismatch.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.line == 7
	assert result.message is not None
	assert "has init value 'bad'" in result.message
	assert "declared datatype is 'integer'" in result.message


def test_validate_single_file_syntax_rejects_const_write(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	Limit: integer Const := 1;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		Limit = 2;
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "ConstWrite.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.line == 12
	assert result.message is not None
	assert "writes to CONST variable 'Limit'" in result.message


def test_validate_single_file_syntax_rejects_duplicate_submodule_names(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*Child*);
	child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 3
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "DuplicateSubmodules.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "duplicate submodule names 'Child' and 'child'" in result.message


def test_validate_single_file_syntax_allows_moduletype_instance_reusing_inline_name(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	ChildType = MODULEDEFINITION DateCode_ 2
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*ChildType*);
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 3
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*Child*);
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "RepeatedModuleTypeInvocationName.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is True
	assert result.stage == "ok"


def test_validate_single_file_syntax_allows_distinct_moduletype_instances_with_same_type(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	ChildType = MODULEDEFINITION DateCode_ 2
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*ChildType*);
SUBMODULES
	ChildA Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType;
	ChildB Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "DistinctModuleTypeInvocations.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is True
	assert result.stage == "ok"


def test_validate_transformed_basepicture_workspace_mode_allows_external_style_datatypes():
	bp = BasePicture(
		header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
		localvariables=[
			Variable(name="Wildcard", datatype="AnyType"),
			Variable(name="ExternalRef", datatype="DI_IOType"),
		],
	)

	validate_transformed_basepicture(
		bp,
		allow_unresolved_external_datatypes=True,
	)


def test_validate_transformed_basepicture_workspace_mode_allows_duplicate_submodule_names():
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 2
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*Child*);
	child Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 3
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*child*);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	bp = _parse_to_basepicture(code)

	validate_transformed_basepicture(
		bp,
		enforce_unique_submodule_names=False,
	)


def test_validate_transformed_basepicture_workspace_mode_allows_mappings_to_parameterless_module():
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	ChildType = MODULEDEFINITION DateCode_ 2
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*ChildType*);
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
		Wrong => Missing
	);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	bp = _parse_to_basepicture(code)

	validate_transformed_basepicture(
		bp,
		allow_parameterless_module_mappings=True,
	)


def test_validate_transformed_basepicture_workspace_mode_still_rejects_builtin_typos():
	bp = BasePicture(
		header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
		localvariables=[Variable(name="Broken", datatype="intege")],
	)

	with pytest.raises(StructuralValidationError, match="did you mean 'integer'"):
		validate_transformed_basepicture(
			bp,
			allow_unresolved_external_datatypes=True,
		)


def test_validate_transformed_basepicture_workspace_mode_warns_unknown_parameter_target():
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	ChildType = MODULEDEFINITION DateCode_ 2
	MODULEPARAMETERS
		Value: integer;
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*ChildType*);
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
		Wrong => 1
	);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	bp = _parse_to_basepicture(code)
	warnings: list[str] = []

	validate_transformed_basepicture(
		bp,
		warn_unknown_parameter_targets=True,
		warning_sink=warnings.append,
	)

	assert warnings == [
		"BasePicture module instance 'Child' maps unknown parameter target 'Wrong'"
	]


def test_validate_single_file_syntax_rejects_duplicate_parameter_mapping_targets(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	ChildType = MODULEDEFINITION DateCode_ 2
	MODULEPARAMETERS
		Value: integer;
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*ChildType*);
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
		Value => 1,
		value => 2
	);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "DuplicateParameterTargets.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "duplicate parameter mapping targets 'Value' and 'value'" in result.message


def test_validate_single_file_syntax_rejects_unknown_parameter_mapping_target(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	ChildType = MODULEDEFINITION DateCode_ 2
	MODULEPARAMETERS
		Value: integer;
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*ChildType*);
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
		Wrong => 1
	);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "UnknownParameterTarget.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "maps unknown parameter target 'Wrong'" in result.message


def test_validate_single_file_syntax_rejects_parameter_mapping_type_mismatch(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	ChildType = MODULEDEFINITION DateCode_ 2
	MODULEPARAMETERS
		Value: integer;
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*ChildType*);
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
		Value => "bad"
	);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "ParameterTargetTypeMismatch.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is False
	assert result.stage == "validation"
	assert result.message is not None
	assert "with datatype 'string'" in result.message
	assert "with datatype 'integer'" in result.message


def test_validate_single_file_syntax_allows_setstringpos_on_const_string(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
	Delimiter: string Const := ";";
	Status: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
	EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
		SetStringPos(Delimiter, 1, Status);
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "ConstSetStringPos.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is True
	assert result.stage == "ok"


def test_validate_single_file_syntax_accepts_parameter_mapping_to_anytype(tmp_path):
	code = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
TYPEDEFINITIONS
	ChildType = MODULEDEFINITION DateCode_ 2
	MODULEPARAMETERS
		Value: AnyType;
	ModuleDef
	ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
	ENDDEF (*ChildType*);
SUBMODULES
	Child Invocation (0.0,0.0,0.0,1.0,1.0) : ChildType (
		Value => 1
	);
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ENDDEF (*BasePicture*);
"""
	source_file = tmp_path / "AnyTypeParameterTarget.s"
	source_file.write_text(code, encoding="utf-8")

	result = validate_single_file_syntax(source_file)

	assert result.ok is True
	assert result.stage == "ok"


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
