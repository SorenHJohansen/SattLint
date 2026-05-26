"""Tests for grammar coverage and parser-core behaviour.

Covers parse_source_text, source spans, flags, and identifier rules.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, LiteralString, cast

import pytest
from lark import Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken

from sattline_parser import (
    api as parser_api,
)
from sattline_parser import (
    fuzz_harness as parser_fuzz_harness,
)
from sattline_parser import (
    parse_source_text as parser_core_parse_source_text,
)
from sattline_parser import (
    strip_sl_comments,
)
from sattline_parser.grammar import constants as parser_const
from sattline_parser.grammar import parser_decode as grammar_parser_decode
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FloatLiteral,
    FrameModule,
    GraphObject,
    InteractObject,
    IntLiteral,
    ModuleCode,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    SingleModule,
    SourceSpan,
    Variable,
)
from sattline_parser.transformer._expressions_mixin import _ExpressionsMixin
from sattline_parser.transformer._graphics_interact_mixin import _GraphicsInteractMixin
from sattline_parser.transformer._modules_mixin import _flatten_items, _meta_span, _ModulesMixin
from sattline_parser.transformer._sfc_mixin import _SFCMixin
from sattline_parser.transformer._tokens_mixin import DEFAULT_INIT, _TokensMixin
from sattline_parser.transformer.sl_transformer import (
    SLTransformer,
    _extract_program_name_from_header_lines,
    _iter_tree_children,
    _strip_quoted,
)
from sattline_parser.transformer.sl_transformer import (
    _flatten_items as _sl_flatten_items,
)
from sattline_parser.transformer.sl_transformer import (
    _is_tree as _sl_is_tree,
)
from sattline_parser.transformer.sl_transformer import (
    _meta_span as _sl_meta_span,
)
from sattline_parser.utils.formatter import format_expr, format_list, format_optional, format_seq_nodes
from sattline_parser.utils.text_processing import strip_sl_comments_with_mapping
from sattlint import constants as const
from sattlint.engine import (
    create_sl_parser,
    parse_source_file,
)


def _parse_to_basepicture(text: str):
    parser = create_sl_parser()
    tree = parser.parse(strip_sl_comments(text))
    return SLTransformer().transform(tree)


def _repo_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[2].joinpath(*parts)


_is_tree = _sl_is_tree


class _ModulesHarness(_ModulesMixin):
    def __init__(self, tails: list[Any] | None = None) -> None:
        self._tails = list(tails or [])

    def _extract_coord_tails(self, _items: list[Any]) -> list[Any]:
        return list(self._tails)


class _GraphicsHarness(_GraphicsInteractMixin):
    def __init__(self, coord_tails: list[Any] | None = None, extra_tails: list[Any] | None = None) -> None:
        self._coord_tails = list(coord_tails or [])
        self._extra_tails = list(extra_tails or [])

    def _extract_coord_payloads(self, items: list[Any]) -> tuple[list[Any], list[Any]]:
        payloads: list[Any] = []
        tails = list(self._coord_tails)
        for item in items:
            if isinstance(item, tuple):
                payloads.append(item)
            elif isinstance(item, dict) and parser_const.KEY_COORDS in item:
                payloads.append(item[parser_const.KEY_COORDS])
                tails.extend(item.get(parser_const.KEY_TAILS, []))
        return payloads, tails

    def _merge_tails(self, *tail_groups: list[Any]) -> list[Any]:
        merged: list[Any] = []
        for group in tail_groups:
            merged.extend(group)
        return merged

    def _collect_invar_enable_tails(self, items: list[Any]) -> list[Any]:
        tails = list(self._extra_tails)

        def _visit(node: Any) -> None:
            if isinstance(node, dict) and parser_const.KEY_TAIL in node:
                tails.append(node[parser_const.KEY_TAIL])
            elif isinstance(node, (list, tuple)):
                for child in node:
                    _visit(child)

        for item in items:
            _visit(item)
        return tails


class _TokensHarness(_TokensMixin):
    pass


class _ExpressionsHarness(_ExpressionsMixin):
    pass


class _SFCHarness(_SFCMixin):
    pass


def _module_header(name: str = "Module") -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0))


__all__ = [
    "DEFAULT_INIT",
    "Any",
    "BasePicture",
    "DataType",
    "Equation",
    "FloatLiteral",
    "FrameModule",
    "GraphObject",
    "IntLiteral",
    "InteractObject",
    "LiteralString",
    "ModuleCode",
    "ModuleDef",
    "ModuleHeader",
    "ModuleTypeDef",
    "ModuleTypeInstance",
    "ParameterMapping",
    "Path",
    "SFCAlternative",
    "SFCBreak",
    "SFCCodeBlocks",
    "SFCFork",
    "SFCParallel",
    "SFCStep",
    "SFCSubsequence",
    "SFCTransition",
    "SFCTransitionSub",
    "SLTransformer",
    "Sequence",
    "SimpleNamespace",
    "Simple_DataType",
    "SingleModule",
    "SourceSpan",
    "Token",
    "Tree",
    "UnexpectedCharacters",
    "UnexpectedEOF",
    "UnexpectedToken",
    "Variable",
    "_ExpressionsHarness",
    "_ExpressionsMixin",
    "_GraphicsHarness",
    "_GraphicsInteractMixin",
    "_ModulesHarness",
    "_ModulesMixin",
    "_SFCHarness",
    "_SFCMixin",
    "_TokensHarness",
    "_TokensMixin",
    "_extract_program_name_from_header_lines",
    "_flatten_items",
    "_is_tree",
    "_iter_tree_children",
    "_meta_span",
    "_module_header",
    "_parse_to_basepicture",
    "_repo_path",
    "_sl_flatten_items",
    "_sl_is_tree",
    "_sl_meta_span",
    "_strip_quoted",
    "ast",
    "cast",
    "const",
    "create_sl_parser",
    "format_expr",
    "format_list",
    "format_optional",
    "format_seq_nodes",
    "grammar_parser_decode",
    "importlib",
    "parse_source_file",
    "parser_api",
    "parser_const",
    "parser_core_parse_source_text",
    "parser_fuzz_harness",
    "pytest",
    "strip_sl_comments",
    "strip_sl_comments_with_mapping",
    "sys",
]
