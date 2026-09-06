"""Typed schema for .slproj project files."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict, cast

from ..config.defaults import DEFAULT_CONFIG
from ..config.types import AnalysisConfig, ConfigMode


class ProjectDict(TypedDict):
    slproj_version: int
    analyzed_programs_and_libraries: list[str]
    include_reverse_library_consumers: bool
    mode: ConfigMode
    program_dir: str
    ABB_lib_dir: str
    icf_dir: str
    other_lib_dirs: list[str]
    analysis: AnalysisConfig


DEFAULT_PROJECT_DICT: ProjectDict = {
    "slproj_version": 1,
    "analyzed_programs_and_libraries": [],
    "include_reverse_library_consumers": False,
    "mode": "official",
    "program_dir": "",
    "ABB_lib_dir": "",
    "icf_dir": "",
    "other_lib_dirs": [],
    "analysis": deepcopy(cast(AnalysisConfig, cast(Any, DEFAULT_CONFIG)["analysis"])),
}


__all__ = [
    "DEFAULT_PROJECT_DICT",
    "ProjectDict",
]
