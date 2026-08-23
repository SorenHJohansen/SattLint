# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownLambdaType=false, reportPrivateUsage=false, reportArgumentType=false, reportUnusedImport=false, reportUnusedFunction=false
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pytest import CaptureFixture, MonkeyPatch
from sattline_parser.models.ast_model import (
    BasePicture,
    DataType,
    FrameModule,
    ModuleDef,
    ModuleHeader,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
    SourceSpan,
    Variable,
)

from sattlint.devtools import source_diff_report

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "source_diff"

__all__ = [
    "FIXTURE_ROOT",
    "Any",
    "BasePicture",
    "CaptureFixture",
    "DataType",
    "FrameModule",
    "ModuleDef",
    "ModuleHeader",
    "ModuleTypeDef",
    "ModuleTypeInstance",
    "MonkeyPatch",
    "Path",
    "SimpleNamespace",
    "SingleModule",
    "SourceSpan",
    "Variable",
    "_basepicture",
    "_empty_module_detail",
    "_sections_by_kind",
    "json",
    "pytest",
    "runpy",
    "source_diff_report",
    "sys",
]


def _sections_by_kind(pair: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {section["kind"]: section for section in pair["sections"]}


def _empty_module_detail(*, module_kind: str = "singlemodule") -> dict[str, Any]:
    return {
        "module_kind": module_kind,
        "parameters": [],
        "variables": [],
        "submodules": [],
        "moduledef": source_diff_report._moduledef_detail(None),
        "modulecode": source_diff_report._modulecode_detail(None),
        "inline_modules": {},
    }


def _basepicture(
    *,
    moduletype_defs: list[ModuleTypeDef] | None = None,
    datatype_defs: list[DataType] | None = None,
    submodules: list[Any] | None = None,
    moduledef: ModuleDef | None = None,
) -> BasePicture:
    return BasePicture(
        header=ModuleHeader(name="BasePicture", invoke_coord=(0.0, 0.0, 0.0, 1.0, 1.0)),
        moduletype_defs=moduletype_defs,
        datatype_defs=datatype_defs,
        submodules=submodules,
        moduledef=moduledef,
    )
