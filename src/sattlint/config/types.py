"""Typed configuration schema shared across the SattLint app."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Literal, TypedDict

type ConfigMode = Literal["official", "draft"]
type ConfigPathValue = str | PathLike[str] | Path
type ConfigObjectMap = dict[str, object]


class RunHistoryConfig(TypedDict):
    enabled: bool
    limit: int


class RunHistoryConfigOverride(TypedDict, total=False):
    enabled: bool
    limit: int


class OutputConfig(TypedDict):
    retention_lines: int


class OutputConfigOverride(TypedDict, total=False):
    retention_lines: int


class ReviewConfig(TypedDict):
    output_dir: ConfigPathValue


class ReviewConfigOverride(TypedDict, total=False):
    output_dir: ConfigPathValue


class SpecComplianceConfig(TypedDict):
    step_prefix: str
    transition_prefix: str
    sequence_prefix: str
    equation_prefix: str


class SpecComplianceConfigOverride(TypedDict, total=False):
    step_prefix: str
    transition_prefix: str
    sequence_prefix: str
    equation_prefix: str


class AnalysisConfig(TypedDict):
    spec_compliance: SpecComplianceConfig
    unsafe_default_tokens: list[str]
    cyclomatic_module_threshold: int
    cyclomatic_step_threshold: int
    cyclomatic_equation_block_threshold: int
    fan_in_out_threshold: int


class AnalysisConfigOverride(TypedDict, total=False):
    spec_compliance: SpecComplianceConfigOverride
    unsafe_default_tokens: list[str]
    cyclomatic_module_threshold: int
    cyclomatic_step_threshold: int
    cyclomatic_equation_block_threshold: int
    fan_in_out_threshold: int


class ConfigDict(TypedDict):
    analyzed_programs_and_libraries: list[str]
    mode: ConfigMode
    debug: bool
    program_dir: ConfigPathValue
    ABB_lib_dir: ConfigPathValue
    icf_dir: ConfigPathValue
    other_lib_dirs: list[ConfigPathValue]
    run_history: RunHistoryConfig
    output: OutputConfig
    review: ReviewConfig
    analysis: AnalysisConfig


class ConfigOverrideDict(TypedDict, total=False):
    analyzed_programs_and_libraries: list[str]
    mode: str
    debug: bool
    program_dir: ConfigPathValue
    ABB_lib_dir: ConfigPathValue
    icf_dir: ConfigPathValue
    other_lib_dirs: list[ConfigPathValue]
    run_history: RunHistoryConfigOverride
    output: OutputConfigOverride
    review: ReviewConfigOverride
    analysis: AnalysisConfigOverride


__all__ = [
    "AnalysisConfig",
    "AnalysisConfigOverride",
    "ConfigDict",
    "ConfigMode",
    "ConfigObjectMap",
    "ConfigOverrideDict",
    "ConfigPathValue",
    "OutputConfig",
    "OutputConfigOverride",
    "ReviewConfig",
    "ReviewConfigOverride",
    "RunHistoryConfig",
    "RunHistoryConfigOverride",
    "SpecComplianceConfig",
    "SpecComplianceConfigOverride",
]
