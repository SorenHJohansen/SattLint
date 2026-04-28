"""Public compatibility wrapper for parser-core source decoding helpers.

This module is retained as an external boundary. Internal SattLint code should
import parser-core symbols from ``sattline_parser.grammar.parser_decode`` directly.
"""

from sattline_parser.grammar.parser_decode import SEED_MAPPING, decode_compressed, is_compressed, preprocess_sl_text

__all__ = ["SEED_MAPPING", "decode_compressed", "is_compressed", "preprocess_sl_text"]
