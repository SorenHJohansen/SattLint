# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportIndexIssue=false
"""Parser compatibility tests (Phase 22).

Documents the supported ``sattline-parser`` version policy and verifies the
installed parser exposes the API surface SattLint relies on.  The declared
range is ``>=2026.8.1,<2027`` (see ``pyproject.toml``); representative fixtures
exercise parse/transform behavior across the features that depend on it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import sattline_parser
from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.api import describe_parse_error, read_text_with_fallback
from sattline_parser.models.ast_model import BasePicture
from sattline_parser.preprocessing import is_compressed, preprocess_sl_text
from sattline_parser.transformer.sl_transformer import SLTransformer

from tests.helpers.app_menus_support import VALID_SINGLE_FILE

REPO_ROOT = Path(__file__).resolve().parents[2]


def _declared_parser_requirement() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)
    dependencies = project["project"]["dependencies"]
    return next(dep for dep in dependencies if dep.startswith("sattline-parser"))


def test_installed_parser_matches_declared_policy() -> None:
    requirement = _declared_parser_requirement()
    installed = sattline_parser.__version__

    assert requirement.startswith("sattline-parser>="), requirement
    assert installed >= "2026.8.1", f"installed parser {installed} below declared minimum"
    assert installed < "2027", f"installed parser {installed} outside declared major range"


def test_declared_parser_requirement_is_pinned() -> None:
    requirement = _declared_parser_requirement()
    assert ">=" in requirement
    assert "<2027" in requirement or "<2028" in requirement


def test_parser_core_api_surface_is_available() -> None:
    assert callable(parser_core_parse_source_text)
    assert callable(read_text_with_fallback)
    assert callable(describe_parse_error)
    assert callable(is_compressed)
    assert callable(preprocess_sl_text)
    assert isinstance(SLTransformer(), SLTransformer)


def test_parser_core_parse_source_text_returns_basepicture() -> None:
    base_picture = parser_core_parse_source_text(VALID_SINGLE_FILE)

    assert isinstance(base_picture, BasePicture)
    assert base_picture.header.name


@pytest.mark.parametrize(
    "fixture_name",
    ["EnableExpr.s", "MiscIssues.s", "PowerUp.s", "TestOverFlow.s"],
)
def test_representative_fixtures_parse(fixture_name: str) -> None:
    fixture_path = REPO_ROOT / "tests" / "fixtures" / "sample_sattline_files" / fixture_name
    if not fixture_path.exists():
        pytest.skip(f"fixture not present: {fixture_name}")

    base_picture = parser_core_parse_source_text(fixture_path.read_text(encoding="utf-8"))

    assert isinstance(base_picture, BasePicture)
    assert base_picture.header.name
