from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    affects_project_cache: bool = False


TOP_LEVEL_CONFIG_FIELDS: dict[str, TopLevelConfigField] = {
    "analyzed_programs_and_libraries": TopLevelConfigField([], affects_project_cache=True),
    "include_reverse_library_consumers": TopLevelConfigField(False, affects_project_cache=True),
    "mode": TopLevelConfigField("official", affects_project_cache=True),
    "scan_root_only": TopLevelConfigField(False, affects_project_cache=True),
    "fast_cache_validation": TopLevelConfigField(True, affects_project_cache=True),
    "debug": TopLevelConfigField(False),
    "program_dir": TopLevelConfigField("", affects_project_cache=True),
    "ABB_lib_dir": TopLevelConfigField("", affects_project_cache=True),
    "icf_dir": TopLevelConfigField("", affects_project_cache=True),
    "other_lib_dirs": TopLevelConfigField([], affects_project_cache=True),
    "telemetry": TopLevelConfigField(
        {
            "enabled": False,
        }
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
                    "strict-pharma": {
                        "description": "Promotes style and maintainability drift during regulated review.",
                        "disabled_rules": [],
                        "severity_overrides": {
                            "semantic.naming-inconsistent-style": "error",
                            "semantic.cyclomatic-complexity.module": "error",
                            "semantic.cyclomatic-complexity.step": "error",
                        },
                        "confidence_overrides": {},
                    },
                    "legacy-plant": {
                        "description": "Suppresses style-heavy advisories while preserving contract and correctness findings.",
                        "disabled_rules": [
                            "semantic.naming-role-mismatch",
                            "semantic.naming-inconsistent-style",
                            "semantic.cyclomatic-complexity.module",
                            "semantic.cyclomatic-complexity.step",
                            "semantic.loop-output-refactor",
                        ],
                        "severity_overrides": {},
                        "confidence_overrides": {},
                    },
                },
            },
        }
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
        }
    ),
}

DEFAULT_CONFIG: dict[str, Any] = {key: field.default for key, field in TOP_LEVEL_CONFIG_FIELDS.items()}

PROJECT_CACHE_CONFIG_KEYS = tuple(key for key, field in TOP_LEVEL_CONFIG_FIELDS.items() if field.affects_project_cache)
