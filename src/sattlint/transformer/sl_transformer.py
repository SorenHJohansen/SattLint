"""Public compatibility wrapper for parser-core transformer.

This module is retained as an external boundary. Internal SattLint code should
import parser-core symbols from ``sattline_parser.transformer.sl_transformer`` directly.
"""

from sattline_parser.transformer.sl_transformer import SLTransformer

__all__ = ["SLTransformer"]
