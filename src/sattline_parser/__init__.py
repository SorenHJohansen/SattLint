"""Reusable SattLine parser-core package."""

from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture, SourceSpan
from sattline_parser.transformer.sl_transformer import SLTransformer

from .api import create_parser, create_sl_parser, parse_source_file, parse_source_text
from .grammar import constants
from .utils.text_processing import strip_sl_comments

__all__ = [
    "BasePicture",
    "SLTransformer",
    "SourceSpan",
    "constants",
    "create_parser",
    "create_sl_parser",
    "is_compressed",
    "parse_source_file",
    "parse_source_text",
    "preprocess_sl_text",
    "strip_sl_comments",
]
