"""Reusable SattLine parser-core package."""

from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture, SourceSpan
from sattline_parser.transformer.sl_transformer import SLTransformer

from .api import create_parser, create_sl_parser, parse_source_file, parse_source_text
from .fuzz_harness import (
    FuzzResult,
    assert_no_crashes,
    assert_no_timeouts,
    collect_corpus_inputs,
    fuzz_parse_text,
    generate_random_text,
    run_corpus_regression,
    run_random_fuzz,
)
from .grammar import constants
from .utils.text_processing import strip_sl_comments

__all__ = [
    "BasePicture",
    "FuzzResult",
    "SLTransformer",
    "SourceSpan",
    "assert_no_crashes",
    "assert_no_timeouts",
    "collect_corpus_inputs",
    "constants",
    "create_parser",
    "create_sl_parser",
    "fuzz_parse_text",
    "generate_random_text",
    "is_compressed",
    "parse_source_file",
    "parse_source_text",
    "preprocess_sl_text",
    "run_corpus_regression",
    "run_random_fuzz",
    "strip_sl_comments",
]
