"""Typed schema for .slproj project files."""

from __future__ import annotations

from typing import TypedDict

from ..config_types import AnalysisConfig, ConfigMode, DocumentationConfig, TelemetryConfig


class ProjectDict(TypedDict):
    slproj_version: int
    analyzed_programs_and_libraries: list[str]
    include_reverse_library_consumers: bool
    mode: ConfigMode
    debug: bool
    program_dir: str
    ABB_lib_dir: str
    icf_dir: str
    other_lib_dirs: list[str]
    output_dir: str
    cache_dir: str
    telemetry: TelemetryConfig
    analysis: AnalysisConfig
    documentation: DocumentationConfig


DEFAULT_PROJECT_DICT: ProjectDict = {
    "slproj_version": 1,
    "analyzed_programs_and_libraries": [],
    "include_reverse_library_consumers": False,
    "mode": "official",
    "debug": False,
    "program_dir": "",
    "ABB_lib_dir": "",
    "icf_dir": "",
    "other_lib_dirs": [],
    "output_dir": "output",
    "cache_dir": ".sattlint-cache",
    "telemetry": {"enabled": False},
    "analysis": {
        "sfc": {
            "mutually_exclusive_steps": [],
            "step_contracts": {},
        },
        "naming": {
            "variables": {"style": "infer", "allow": []},
            "modules": {"style": "infer", "allow": []},
            "instances": {"style": "infer", "allow": []},
        },
        "rule_profiles": {
            "active": "default",
            "profiles": {
                "default": {
                    "description": "Balanced default analyzer profile.",
                    "disabled_rules": [],
                    "severity_overrides": {},
                    "confidence_overrides": {},
                },
            },
        },
    },
    "documentation": {
        "classifications": {
            "em": {
                "name_contains": [],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": ["nnestruct:EquipModCoordinate"],
            },
            "ops": {
                "name_contains": [],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": ["NNEMESIFLib:MES_StateControl"],
            },
            "rp": {
                "name_contains": ["RecPar"],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": [],
            },
            "ep": {
                "name_contains": ["EngPar"],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": [],
            },
            "up": {
                "name_contains": ["UsrPar"],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": [],
            },
        },
    },
}


__all__ = [
    "DEFAULT_PROJECT_DICT",
    "ProjectDict",
]
