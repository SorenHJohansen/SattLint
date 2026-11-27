"""Typed schema for .slproj project files."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict, cast

from ..config.defaults import DEFAULT_CONFIG
from ..config.string_capacities import StringCapacitiesDict, standard_string_capacities_dict
from ..config.types import AnalysisConfig, ConfigMode

# Version 2 requires the top-level [string_capacities] table that version 1 lacks.
SLPROJ_VERSION = 2


class ProjectDict(TypedDict):
    slproj_version: int
    analyzed_programs_and_libraries: list[str]
    analyzers: list[str]
    string_capacities: StringCapacitiesDict
    mode: ConfigMode
    program_dir: str
    ABB_lib_dir: str
    icf_dir: str
    other_lib_dirs: list[str]
    allow_external_roots: bool
    analysis: AnalysisConfig


DEFAULT_PROJECT_DICT: ProjectDict = {
    "slproj_version": SLPROJ_VERSION,
    "analyzed_programs_and_libraries": [],
    "analyzers": [],
    "string_capacities": standard_string_capacities_dict(),
    "mode": "official",
    "program_dir": "",
    "ABB_lib_dir": "",
    "icf_dir": "",
    "other_lib_dirs": [],
    "allow_external_roots": False,
    "analysis": deepcopy(cast(AnalysisConfig, cast(Any, DEFAULT_CONFIG)["analysis"])),
}


__all__ = [
    "DEFAULT_PROJECT_DICT",
    "SLPROJ_VERSION",
    "ProjectDict",
]
