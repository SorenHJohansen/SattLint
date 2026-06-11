# pyright: reportUnusedImport=false

"""Tests for variable analysis workflows, advanced datatype analysis, and variable usage sub-menus in the app."""

# ruff: noqa: F401

import builtins
import os
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, cast

import pytest

from sattline_parser import parse_source_text as parser_core_parse_source_text
from sattline_parser.models.ast_model import FrameModule, ModuleTypeInstance, SingleModule
from sattlint import app, app_analysis
from sattlint.analyzers import variable_usage_reporting as variables_reporting_module
from sattlint.analyzers import variables as variables_module
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind,
    VariableIssue,
    VariablesReport,
)

from ._app_menus_support import (
    INVALID_SINGLE_FILE,
    VALID_SINGLE_FILE,
    DummyReport,
    make_input,
    make_shadowing_report,
    make_variable_report,
    real_context,
)


@pytest.fixture
def noop_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "clear_screen", lambda: None)
    monkeypatch.setattr(app, "pause", lambda: None)
