# pyright: reportPrivateUsage=false, reportUnusedImport=false, reportReturnType=false

"""Shared fixtures and helpers for app menu tests."""

import os
from collections.abc import Sequence
from typing import ClassVar

import pytest

from sattline_parser.models.ast_model import BasePicture, FrameModule, ModuleTypeInstance, SingleModule
from sattlint import app
from sattlint.analyzers import variables as variables_module
from sattlint.models.project_graph import ProjectGraph
from sattlint.reporting.variables_report import (
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    IssueKind,
    VariablesReport,
)

from .helpers import RealContext, make_input

__all__ = [
    "INVALID_SINGLE_FILE",
    "VALID_SINGLE_FILE",
    "DummyReport",
    "make_input",
    "make_shadowing_report",
    "make_variable_report",
    "real_context",
]

VALID_SINGLE_FILE = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    A: integer := 0;
    B: integer := 1;
    C: integer := 2;
    D: integer := 3;
    X: integer := 0;
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        X = IF A > 0 THEN B ELSE C + D ENDIF;
ENDDEF (*BasePicture*);
"""

INVALID_SINGLE_FILE = """
"SyntaxVersion"
"OriginalFileDate"
"ProgramDate"
BasePicture Invocation (0.0,0.0,0.0,1.0,1.0) : MODULEDEFINITION DateCode_ 1
LOCALVARIABLES
    TestVar: integer := 0
ModuleDef
ClippingBounds = ( -1.0 , -1.0 ) ( 1.0 , 1.0 )
ModuleCode
    EQUATIONBLOCK Main COORD 0.0, 0.0 OBJSIZE 1.0, 1.0 :
        TestVar = TestVar + 1;
ENDDEF (*BasePicture*);
"""


class DummyReport:
    basepicture_name: ClassVar[str] = "Dummy"
    issues: ClassVar[list[object]] = []
    visible_kinds: ClassVar[frozenset[IssueKind]] = frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS)
    include_empty_sections: ClassVar[bool] = True

    def summary(self) -> str:
        return "summary"


def make_shadowing_report(basepicture_name: str = "Dummy") -> VariablesReport:
    return VariablesReport(
        basepicture_name=basepicture_name,
        issues=[],
        visible_kinds=frozenset({app.IssueKind.SHADOWING}),
        include_empty_sections=True,
    )


def make_variable_report(basepicture_name: str = "Dummy") -> VariablesReport:
    return VariablesReport(
        basepicture_name=basepicture_name,
        issues=[],
        visible_kinds=frozenset(DEFAULT_VARIABLE_ANALYSIS_KINDS),
        include_empty_sections=True,
    )


type _NestedModule = SingleModule | FrameModule | ModuleTypeInstance


def _find_module_with_localvar(base_picture: BasePicture) -> tuple[list[str], str] | None:
    def walk(mods: Sequence[_NestedModule] | None, path: list[str]) -> tuple[list[str], str] | None:
        for mod in mods or []:
            mod_path = [*path, mod.header.name]

            if isinstance(mod, SingleModule):
                if mod.localvariables:
                    return mod_path, mod.localvariables[0].name
                found = walk(mod.submodules, mod_path)
                if found:
                    return found

            elif isinstance(mod, FrameModule):
                found = walk(mod.submodules, mod_path)
                if found:
                    return found

            else:
                mt = next(
                    (
                        m
                        for m in (base_picture.moduletype_defs or [])
                        if m.name.casefold() == mod.moduletype_name.casefold()
                    ),
                    None,
                )
                if mt and mt.localvariables:
                    return mod_path, mt.localvariables[0].name

        return None

    return walk(getattr(base_picture, "submodules", None), [base_picture.header.name])


def _pick_any_variable_name(base_picture: BasePicture, graph: ProjectGraph) -> str | None:
    analyzer = variables_module.VariablesAnalyzer(
        base_picture,
        debug=False,
        fail_loudly=False,
        unavailable_libraries=graph.unavailable_libraries,
    )
    for var_list in analyzer._any_var_index.values():
        if var_list:
            for var in var_list:
                if getattr(var, "name", None):
                    return var.name
    return None


@pytest.fixture(scope="session")
def real_context() -> RealContext | None:
    if os.getenv("SATTLINT_RUN_REAL_CONTEXT") != "1":
        return None
    cfg, _ = app.load_config(app.CONFIG_PATH)
    if not app.self_check(cfg):
        return None

    project_bp, graph = app.load_project(cfg)

    var_name = _pick_any_variable_name(project_bp, graph)
    module_info = _find_module_with_localvar(project_bp)

    if not var_name or not module_info:
        return None

    module_path, module_var = module_info
    module_path_str = ".".join(module_path[1:])
    if not module_path_str:
        return None

    return {
        "cfg": cfg,
        "var_name": var_name,
        "module_path": module_path_str,
        "module_var": module_var,
        "module_name": module_path[-1],
    }
