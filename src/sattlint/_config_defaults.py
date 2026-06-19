from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from .config_types import ConfigDict, ConfigOverrideDict

DOCUMENTATION_RULE_LIST_KEYS = (
    "name_contains",
    "label_equals",
    "desc_name_contains",
    "desc_label_equals",
)

DOCUMENTATION_CATEGORY_KEYS = (
    "em",
    "ops",
    "rp",
    "ep",
    "up",
)

DOCUMENTATION_LEGACY_RULE_KEYS = {
    "moduletype_name_contains": "name_contains",
    "moduletype_label_equals": "label_equals",
    "descendant_moduletype_name_contains": "desc_name_contains",
    "descendant_moduletype_label_equals": "desc_label_equals",
}

DOCUMENTATION_LEGACY_CATEGORY_KEYS = {
    "equipment_modules": "em",
    "operations": "ops",
    "recipe_parameters": "rp",
    "engineering_parameters": "ep",
    "user_parameters": "up",
}

NAMING_STYLE_KEYS = (
    "infer",
    "pascal",
    "camel",
    "snake",
    "upper_snake",
    "lower",
    "upper",
)

NAMING_RULE_TARGETS = (
    "variables",
    "modules",
    "instances",
)


@dataclass(frozen=True, slots=True)
class TopLevelConfigField:
    default: Any
    description: str
    affects_project_cache: bool = False


TOP_LEVEL_CONFIG_FIELDS: dict[str, TopLevelConfigField] = {
    "analyzed_programs_and_libraries": TopLevelConfigField(
        [],
        "Names of program or library units to analyze.",
        affects_project_cache=True,
    ),
    "include_reverse_library_consumers": TopLevelConfigField(
        False,
        (
            "Whether library analysis should also load configured libraries that depend on the selected library "
            "target. Enable this for checks that need reverse-consumer context, such as unused datatype-field "
            "analysis."
        ),
        affects_project_cache=True,
    ),
    "mode": TopLevelConfigField(
        "official", "Controls whether official or draft file extensions are resolved.", affects_project_cache=True
    ),
    "scan_root_only": TopLevelConfigField(
        False,
        "Limits discovery to the configured program root instead of scanning dependency roots recursively.",
        affects_project_cache=True,
    ),
    "debug": TopLevelConfigField(False, "Enables verbose CLI diagnostics and debugging behavior."),
    "program_dir": TopLevelConfigField("", "Primary directory for program source files.", affects_project_cache=True),
    "ABB_lib_dir": TopLevelConfigField(
        "", "Primary directory for ABB dependency libraries.", affects_project_cache=True
    ),
    "icf_dir": TopLevelConfigField(
        "", "Directory containing ICF files used by ICF tooling and validation.", affects_project_cache=True
    ),
    "other_lib_dirs": TopLevelConfigField(
        [],
        "Additional dependency library directories searched after the primary program and ABB roots.",
        affects_project_cache=True,
    ),
    "telemetry": TopLevelConfigField(
        {
            "enabled": False,
        },
        "Telemetry settings for optional local event capture.",
    ),
    "analysis": TopLevelConfigField(
        {
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
        "Analyzer-specific configuration for SFC contracts, naming policy, and rule profiles.",
    ),
    "documentation": TopLevelConfigField(
        {
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
        "Documentation classification rules used by doc generation and related workflows.",
    ),
}

REQUIRED_TOP_LEVEL_CONFIG_KEYS = tuple(TOP_LEVEL_CONFIG_FIELDS)
OPTIONAL_TOP_LEVEL_OVERRIDE_KEYS = ()
VALID_TOP_LEVEL_CONFIG_KEYS = frozenset((*REQUIRED_TOP_LEVEL_CONFIG_KEYS, *OPTIONAL_TOP_LEVEL_OVERRIDE_KEYS))
TOP_LEVEL_CONFIG_CONTRACT = {key: field.description for key, field in TOP_LEVEL_CONFIG_FIELDS.items()}

DEFAULT_CONFIG: dict[str, Any] = {key: field.default for key, field in TOP_LEVEL_CONFIG_FIELDS.items()}

PROJECT_CACHE_CONFIG_KEYS = tuple(key for key, field in TOP_LEVEL_CONFIG_FIELDS.items() if field.affects_project_cache)


def _typed_dict_keys(typed_dict_cls: type[object]) -> frozenset[str]:
    required = cast(frozenset[str], getattr(typed_dict_cls, "__required_keys__", frozenset[str]()))
    optional = cast(frozenset[str], getattr(typed_dict_cls, "__optional_keys__", frozenset[str]()))
    return required | optional


def _assert_top_level_config_contract() -> None:
    required_keys = frozenset(REQUIRED_TOP_LEVEL_CONFIG_KEYS)
    if required_keys != _typed_dict_keys(ConfigDict):
        raise RuntimeError("ConfigDict keys must stay in sync with TOP_LEVEL_CONFIG_FIELDS")
    if _typed_dict_keys(ConfigOverrideDict) != VALID_TOP_LEVEL_CONFIG_KEYS:
        raise RuntimeError("ConfigOverrideDict keys must stay in sync with top-level config validation")


_assert_top_level_config_contract()
