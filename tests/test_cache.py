"""Regression tests for AST cache serialization."""

import pickle

from sattlint.models.ast_model import FloatLiteral, IntLiteral, SourceSpan


def test_int_literal_pickle_round_trip_preserves_span():
	value = IntLiteral(42, SourceSpan(12, 5))
	restored = pickle.loads(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))

	assert isinstance(restored, IntLiteral)
	assert restored == 42
	assert restored.span == SourceSpan(12, 5)


def test_float_literal_pickle_round_trip_preserves_span():
	value = FloatLiteral(2.5, SourceSpan(20, 7))
	restored = pickle.loads(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))

	assert isinstance(restored, FloatLiteral)
	assert restored == 2.5
	assert restored.span == SourceSpan(20, 7)


def test_legacy_literal_unpickle_without_span_defaults_to_origin():
	legacy_int = IntLiteral.__new__(IntLiteral, 7)
	legacy_float = FloatLiteral.__new__(FloatLiteral, 3.5)

	assert legacy_int.span == SourceSpan(0, 0)
	assert legacy_float.span == SourceSpan(0, 0)
