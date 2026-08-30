"""Typed configuration schema shared across the SattLint app."""

from __future__ import annotations

from os import PathLike
from pathlib import Path
from typing import Literal, TypedDict

type ConfigMode = Literal["official", "draft"]
type NamingStyle = Literal["infer", "pascal", "camel", "snake", "upper_snake", "lower", "upper"]
type ConfigPathValue = str | PathLike[str] | Path
type ConfigObjectMap = dict[str, object]


class TelemetryConfig(TypedDict):
    enabled: bool


class TelemetryConfigOverride(TypedDict, total=False):
    enabled: bool
    path: str


class NamingRuleConfig(TypedDict):
    style: NamingStyle
    allow: list[str]


class NamingRuleConfigOverride(TypedDict, total=False):
    style: str
    allow: list[str]


class NamingConfig(TypedDict):
    variables: NamingRuleConfig
    modules: NamingRuleConfig
    instances: NamingRuleConfig


class NamingConfigOverride(TypedDict, total=False):
    variables: NamingRuleConfigOverride
    modules: NamingRuleConfigOverride
    instances: NamingRuleConfigOverride


class StepContractConfig(TypedDict):
    required_enter_writes: list[str]
    required_exit_writes: list[str]


class StepContractConfigOverride(TypedDict, total=False):
    required_enter_writes: list[str]
    required_exit_writes: list[str]


class SfcConfig(TypedDict):
    mutually_exclusive_steps: list[object]
    step_contracts: dict[str, StepContractConfig]


class SfcConfigOverride(TypedDict, total=False):
    mutually_exclusive_steps: list[object]
    step_contracts: dict[str, StepContractConfigOverride | ConfigObjectMap]


class RuleProfileConfig(TypedDict):
    description: str
    disabled_rules: list[str]
    severity_overrides: dict[str, str]
    confidence_overrides: dict[str, str]


class RuleProfileConfigOverride(TypedDict, total=False):
    description: str
    disabled_rules: list[str]
    severity_overrides: dict[str, str]
    confidence_overrides: dict[str, str]


class RuleProfilesConfig(TypedDict):
    active: str
    profiles: dict[str, RuleProfileConfig]


class RuleProfilesConfigOverride(TypedDict, total=False):
    active: str
    profiles: dict[str, RuleProfileConfigOverride | ConfigObjectMap]


class AnalysisConfig(TypedDict):
    sfc: SfcConfig
    naming: NamingConfig
    rule_profiles: RuleProfilesConfig


class AnalysisConfigOverride(TypedDict, total=False):
    sfc: SfcConfigOverride
    naming: NamingConfigOverride
    rule_profiles: RuleProfilesConfigOverride


class ConfigDict(TypedDict):
    analyzed_programs_and_libraries: list[str]
    include_reverse_library_consumers: bool
    mode: ConfigMode
    debug: bool
    program_dir: ConfigPathValue
    ABB_lib_dir: ConfigPathValue
    icf_dir: ConfigPathValue
    other_lib_dirs: list[ConfigPathValue]
    telemetry: TelemetryConfig
    analysis: AnalysisConfig


class ConfigOverrideDict(TypedDict, total=False):
    analyzed_programs_and_libraries: list[str]
    include_reverse_library_consumers: bool
    mode: str
    debug: bool
    program_dir: ConfigPathValue
    ABB_lib_dir: ConfigPathValue
    icf_dir: ConfigPathValue
    other_lib_dirs: list[ConfigPathValue]
    telemetry: TelemetryConfigOverride
    analysis: AnalysisConfigOverride


__all__ = [
    "AnalysisConfig",
    "AnalysisConfigOverride",
    "ConfigDict",
    "ConfigMode",
    "ConfigObjectMap",
    "ConfigOverrideDict",
    "ConfigPathValue",
    "NamingConfig",
    "NamingConfigOverride",
    "NamingRuleConfig",
    "NamingRuleConfigOverride",
    "NamingStyle",
    "RuleProfileConfig",
    "RuleProfileConfigOverride",
    "RuleProfilesConfig",
    "RuleProfilesConfigOverride",
    "SfcConfig",
    "SfcConfigOverride",
    "StepContractConfig",
    "StepContractConfigOverride",
    "TelemetryConfig",
    "TelemetryConfigOverride",
]
