from lark.lexer import Token
from lark.tree import Tree
from typing import Any, cast

from sattlint import constants as const
from sattlint.models.ast_model import SFCCodeBlocks


def _tok(token_type: str, value: str) -> Token:
	# Pyright/Pylance has a known bad signature for lark's Token (it treats it like bytes).
	# Runtime construction is correct; we cast to Any to avoid false-positive type errors.
	return cast(Any, Token)(token_type, value)


def test_seqstep_uses_name_token(transformer):
	blocks = SFCCodeBlocks()
	step = transformer.seqstep([_tok("SEQSTEP", "SEQSTEP"), _tok("NAME", "Stopped"), blocks])
	assert step.name == "Stopped"


def test_seqinitstep_uses_name_token(transformer):
	blocks = SFCCodeBlocks()
	step = transformer.seqinitstep(
		[_tok("SEQINITSTEP", "SEQINITSTEP"), _tok("NAME", "Init"), blocks]
	)
	assert step.name == "Init"


def test_seqtransition_uses_optional_name_token(transformer):
	tr_named = transformer.seqtransition(
		[
			_tok("SEQTRANSITION", "SEQTRANSITION"),
			_tok("NAME", "T1"),
			_tok("WAIT_FOR", "WAIT_FOR"),
			123,
		]
	)
	assert tr_named.name == "T1"
	assert tr_named.condition == 123

	tr_unnamed = transformer.seqtransition(
		[_tok("SEQTRANSITION", "SEQTRANSITION"), _tok("WAIT_FOR", "WAIT_FOR"), 123]
	)
	assert tr_unnamed.name is None
	assert tr_unnamed.condition == 123


def test_seqsub_uses_name_token(transformer):
	body = Tree(const.KEY_SEQUENCE_BODY, [])
	sub = transformer.seqsub(
		[_tok("SUBSEQUENCE", "SUBSEQUENCE"), _tok("NAME", "MySub"), body]
	)
	assert sub.name == "MySub"


def test_seqfork_uses_name_token(transformer):
	fork = transformer.seqfork([_tok("SEQFORK", "SEQFORK"), _tok("NAME", "NextStep")])
	assert fork.target == "NextStep"
