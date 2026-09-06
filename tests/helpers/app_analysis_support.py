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

from sattlint import app
from sattlint import cache as cache_module
from sattlint import console as console_module
from sattlint.analyzers import catalog as analysis_catalog_module
from sattlint.analyzers import icf as icf_module
from sattlint.analyzers import variable_usage_reporting as variables_reporting_module
from sattlint.analyzers import variables as variables_module
from sattlint.analyzers.framework import SimpleReport
from sattlint.application import checks as checks_application
from sattlint.application import commands as commands_application
from sattlint.application import output as output_module
from sattlint.application import project as project_application
from sattlint.core import profiling as profiling_module
from sattlint.project import loading as analysis_loading_module
from sattlint.project import support as support_module
from sattlint.reporting.variables_report import (
    ALL_VARIABLE_ANALYSIS_KINDS,
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind,
    VariableIssue,
    VariablesReport,
)
from tests.helpers.app_menus_support import (
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
