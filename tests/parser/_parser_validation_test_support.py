"""Tests for validate_single_file_syntax, validate_transformed_basepicture, workspace-mode rules, compressed library sources, and builtin type checks."""

from pathlib import Path
from typing import Any, cast

import pytest

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser import strip_sl_comments
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    ModuleCode,
    ModuleHeader,
    ParameterMapping,
    Sequence,
    SFCBreak,
    SFCCodeBlocks,
    SFCFork,
    SFCStep,
    SFCTransition,
    SFCTransitionSub,
    Simple_DataType,
    Variable,
)
from sattline_parser.transformer.sl_transformer import SLTransformer
from sattlint import validation as validation_module
from sattlint.engine import (
    StructuralValidationError,
    _load_source_text,
    create_sl_parser,
    validate_single_file_syntax,
    validate_transformed_basepicture,
)
from sattlint.resolution.type_graph import TypeGraph


def _parse_to_basepicture(text: str):
    parser = create_sl_parser()
    tree = parser.parse(strip_sl_comments(text))
    return SLTransformer().transform(tree)


def _repo_path(*parts: str) -> Path:
    return Path(__file__).resolve().parents[2].joinpath(*parts)


def _official_library_fixture_path(*parts: str) -> Path:
    return _repo_path("tests", "fixtures", "sample_sattline_files", "official_library_files", *parts)


def _var_ref(name: object, *, state: str | None = None) -> dict[str, object]:
    ref = {validation_module.const.KEY_VAR_NAME: name}
    if state is not None:
        ref["state"] = state
    return ref


__all__ = [
    "Any",
    "BasePicture",
    "DataType",
    "Equation",
    "ModuleCode",
    "ModuleHeader",
    "ParameterMapping",
    "Path",
    "SFCBreak",
    "SFCCodeBlocks",
    "SFCFork",
    "SFCStep",
    "SFCTransition",
    "SFCTransitionSub",
    "SLTransformer",
    "Sequence",
    "Simple_DataType",
    "StructuralValidationError",
    "TypeGraph",
    "Variable",
    "_load_source_text",
    "_official_library_fixture_path",
    "_parse_to_basepicture",
    "_repo_path",
    "_var_ref",
    "cast",
    "create_sl_parser",
    "parser_core_parse_source_text",
    "pytest",
    "strip_sl_comments",
    "validate_single_file_syntax",
    "validate_transformed_basepicture",
    "validation_module",
]
