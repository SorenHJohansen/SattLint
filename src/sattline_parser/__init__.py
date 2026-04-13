"""Reusable SattLine parser-core package."""

from .api import create_parser, create_sl_parser, parse_source_file, parse_source_text
from .grammar import constants
from .grammar.parser_decode import is_compressed, preprocess_sl_text
from .models.ast_model import BasePicture, SourceSpan
from .transformer.sl_transformer import SLTransformer
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
