"""Reusable SattLine parser-core package."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING, Any

from sattline_parser.grammar.parser_decode import is_compressed, preprocess_sl_text
from sattline_parser.models.ast_model import BasePicture, SourceSpan
from sattline_parser.transformer.sl_transformer import SLTransformer

from .api import create_parser, create_sl_parser, parse_source_file, parse_source_text
from .grammar import constants
from .utils.text_processing import strip_sl_comments

if TYPE_CHECKING:
    from . import fuzz_harness as fuzz_harness
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

_FUZZ_EXPORTS = (
    "FuzzResult",
    "assert_no_crashes",
    "assert_no_timeouts",
    "collect_corpus_inputs",
    "fuzz_harness",
    "fuzz_parse_text",
    "generate_random_text",
    "run_corpus_regression",
    "run_random_fuzz",
)
_FUZZ_EXPORT_SET = frozenset(_FUZZ_EXPORTS)


def _load_fuzz_harness() -> ModuleType:
    module = import_module(".fuzz_harness", __name__)
    globals()["fuzz_harness"] = module
    for export_name in _FUZZ_EXPORTS:
        if export_name == "fuzz_harness":
            continue
        globals()[export_name] = getattr(module, export_name)
    return module


def __getattr__(name: str) -> Any:
    if name not in _FUZZ_EXPORT_SET:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = _load_fuzz_harness()
    if name == "fuzz_harness":
        return module
    return getattr(module, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | _FUZZ_EXPORT_SET)


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
