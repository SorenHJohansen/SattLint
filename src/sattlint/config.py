"""Configuration management for SattLint."""
from __future__ import annotations

from copy import deepcopy
import os
import sys
import tomllib
import tomli_w
from pathlib import Path
from typing import Any, cast

_DOCUMENTATION_RULE_LIST_KEYS = (
    "name_contains",
    "label_equals",
    "desc_name_contains",
    "desc_label_equals",
)

_DOCUMENTATION_CATEGORY_KEYS = (
    "em",
    "ops",
    "rp",
    "ep",
    "up",
)

_DOCUMENTATION_LEGACY_RULE_KEYS = {
    "moduletype_name_contains": "name_contains",
    "moduletype_label_equals": "label_equals",
    "descendant_moduletype_name_contains": "desc_name_contains",
    "descendant_moduletype_label_equals": "desc_label_equals",
}

_DOCUMENTATION_LEGACY_CATEGORY_KEYS = {
    "equipment_modules": "em",
    "operations": "ops",
    "recipe_parameters": "rp",
    "engineering_parameters": "ep",
    "user_parameters": "up",
}

_NAMING_STYLE_KEYS = (
    "infer",
    "pascal",
    "camel",
    "snake",
    "upper_snake",
    "lower",
    "upper",
)

_NAMING_RULE_TARGETS = (
    "variables",
    "modules",
    "instances",
)

DEFAULT_CONFIG: dict[str, Any] = {
    "analyzed_programs_and_libraries": [],
    "mode": "official",
    "scan_root_only": False,
    "fast_cache_validation": True,
    "debug": False,
    "program_dir": "",
    "ABB_lib_dir": "",
    "icf_dir": "",
    "other_lib_dirs": [],
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
    },
    "documentation": {
        "classifications": {
            "em": {
                "name_contains": [],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": [
                    "nnestruct:EquipModCoordinate"
                ],
            },
            "ops": {
                "name_contains": [],
                "label_equals": [],
                "desc_name_contains": [],
                "desc_label_equals": [
                    "NNEMESIFLib:MES_StateControl"
                ],
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


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
            continue
        merged[key] = value
    return merged


def _normalize_documentation_rule_keys(config: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(config)
    documentation = normalized.get("documentation")
    if not isinstance(documentation, dict):
        return normalized

    classifications = documentation.get("classifications")
    if not isinstance(classifications, dict):
        return normalized

    for legacy_key, short_key in _DOCUMENTATION_LEGACY_CATEGORY_KEYS.items():
        if legacy_key not in classifications:
            continue
        legacy_rule = classifications.pop(legacy_key)
        if short_key in classifications:
            continue
        classifications[short_key] = legacy_rule

    for rule in classifications.values():
        if not isinstance(rule, dict):
            continue
        for legacy_key, short_key in _DOCUMENTATION_LEGACY_RULE_KEYS.items():
            if legacy_key not in rule:
                continue
            legacy_values = rule.pop(legacy_key)
            if short_key in rule:
                continue
            rule[short_key] = legacy_values

    return normalized


def get_documentation_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    documentation_defaults = cast(dict[str, Any], deepcopy(DEFAULT_CONFIG["documentation"]))
    if not cfg:
        return documentation_defaults

    cfg = _normalize_documentation_rule_keys(cfg)

    if "documentation" in cfg and isinstance(cfg.get("documentation"), dict):
        override = cfg.get("documentation", {})
    else:
        override = cfg
    if not isinstance(override, dict):
        return documentation_defaults
    return _deep_merge_dict(documentation_defaults, override)

def get_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    cfg_dir = base / "sattlint"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.toml"


def load_config(path: Path) -> tuple[dict, bool]:
    if not path.exists():
        print(f"⚠ No config found, creating default: {path}")
        cfg = deepcopy(DEFAULT_CONFIG)
        save_config(path, cfg)
        return cfg, True

    with path.open("rb") as f:
        cfg = tomllib.load(f)

    cfg = _normalize_documentation_rule_keys(cfg)

    merged = _deep_merge_dict(DEFAULT_CONFIG, cfg)
    merged.pop("ignore_ABB_lib", None)
    return merged, False


def save_config(path: Path, cfg: dict) -> None:
    def normalize(v):
        if isinstance(v, Path):
            return str(v)
        if isinstance(v, (list, tuple)):
            return [normalize(x) for x in v]
        if isinstance(v, dict):
            return {k: normalize(x) for k, x in v.items()}
        if v is None:
            raise ValueError(
                "Cannot serialize None to TOML. Provide a default value or omit the key."
            )
        return v

    with path.open("wb") as f:
        tomli_w.dump(normalize(cfg), f)


def target_exists(target: str, cfg: dict) -> bool:
    dirs = [
        Path(cfg["program_dir"]),
        Path(cfg["ABB_lib_dir"]),
        *[Path(p) for p in cfg["other_lib_dirs"]],
    ]

    if cfg["mode"] == "draft":
        extensions = [".s", ".x"]  # Try draft first, fallback to official
    else:
        extensions = [".x"]  # Official only

    for d in dirs:
        if not d.exists():
            continue
        for ext in extensions:
            if (d / f"{target}{ext}").exists():
                return True

    return False


def self_check(cfg: dict) -> bool:
    print("\n--- Self-check diagnostics ---")
    ok = True

    # Python version
    if sys.version_info < (3, 13):
        print("❌ Python 3.13+ required")
        ok = False
    else:
        print(f"✔ Python {sys.version.split()[0]}")

    # Required keys
    required_keys = [
        "analyzed_programs_and_libraries",
        "mode",
        "scan_root_only",
        "fast_cache_validation",
        "debug",
        "program_dir",
        "ABB_lib_dir",
        "icf_dir",
        "other_lib_dirs",
        "documentation",
    ]
    for k in required_keys:
        if k not in cfg:
            print(f"❌ Missing config key: {k}")
            ok = False

    # Directories
    for name in ("program_dir", "ABB_lib_dir", "icf_dir"):
        raw = cfg.get(name, "")
        if not raw:
            print(f"⚠ {name} not set")
            continue
        p = Path(raw)
        if not p.exists():
            print(f"❌ {name} does not exist: {p}")
            ok = False
        elif not os.access(p, os.R_OK):
            print(f"❌ {name} not readable: {p}")
            ok = False
        else:
            print(f"✔ {name}: {p}")

    # other_lib_dirs
    for p in cfg.get("other_lib_dirs", []):
        path = Path(p)
        if not path.exists():
            print(f"⚠ other_lib_dirs entry missing: {path}")
        else:
            print(f"✔ other_lib_dirs: {path}")

    targets = [
        str(target).strip()
        for target in cfg.get("analyzed_programs_and_libraries", [])
        if str(target).strip()
    ]
    if not targets:
        print("WARNING analyzed_programs_and_libraries is empty")
        print("Configure targets before running analyses, documentation, or AST cache refresh.")
    else:
        print("Analyzed programs/libraries:")
        for target in targets:
            if target_exists(target, cfg):
                print(f"✔ {target}")
            else:
                print(f"❌ {target} (not found)")
                ok = False

    documentation = cfg.get("documentation", {})
    if not isinstance(documentation, dict):
        print("❌ documentation must be a table/object")
        ok = False
    else:
        classifications = documentation.get("classifications", {})
        if not isinstance(classifications, dict) or not classifications:
            print("❌ documentation.classifications must be a non-empty table/object")
            ok = False
        else:
            for category, rule in classifications.items():
                if category not in _DOCUMENTATION_CATEGORY_KEYS:
                    print(
                        f"❌ documentation.classifications.{category} is not a supported category"
                    )
                    ok = False
                    continue
                if not isinstance(rule, dict):
                    print(f"❌ documentation.classifications.{category} must be a table/object")
                    ok = False
                    continue
                for key in _DOCUMENTATION_RULE_LIST_KEYS:
                    values = rule.get(key, [])
                    if not isinstance(values, list) or not all(
                        isinstance(item, str) for item in values
                    ):
                        print(
                            f"❌ documentation.classifications.{category}.{key} must be a list of strings"
                        )
                        ok = False
                for key in _DOCUMENTATION_RULE_LIST_KEYS:
                    values = [str(item) for item in rule.get(key, []) if str(item).strip()]
                    if values:
                        print(
                            f"✔ documentation.classifications.{category}.{key}: "
                            + ", ".join(values)
                        )

    analysis = cfg.get("analysis", {})
    if not isinstance(analysis, dict):
        print("❌ analysis must be a table/object")
        ok = False
    else:
        sfc = analysis.get("sfc", {})
        if not isinstance(sfc, dict):
            print("❌ analysis.sfc must be a table/object")
            ok = False
        else:
            step_groups = sfc.get("mutually_exclusive_steps", [])
            if not isinstance(step_groups, list):
                print("❌ analysis.sfc.mutually_exclusive_steps must be a list")
                ok = False
            else:
                for index, group in enumerate(step_groups, start=1):
                    if not isinstance(group, list) or not all(
                        isinstance(item, str) for item in group
                    ):
                        print(
                            "❌ analysis.sfc.mutually_exclusive_steps"
                            f"[{index}] must be a list of strings"
                        )
                        ok = False

            step_contracts = sfc.get("step_contracts", {})
            if not isinstance(step_contracts, dict):
                print("❌ analysis.sfc.step_contracts must be a table/object")
                ok = False
            else:
                for step_name, contract in step_contracts.items():
                    if not isinstance(step_name, str) or not step_name.strip():
                        print("❌ analysis.sfc.step_contracts keys must be non-empty strings")
                        ok = False
                        continue
                    if not isinstance(contract, dict):
                        print(
                            "❌ analysis.sfc.step_contracts."
                            f"{step_name} must be a table/object"
                        )
                        ok = False
                        continue
                    for key in ("required_enter_writes", "required_exit_writes"):
                        values = contract.get(key, [])
                        if not isinstance(values, list) or not all(
                            isinstance(item, str) for item in values
                        ):
                            print(
                                "❌ analysis.sfc.step_contracts."
                                f"{step_name}.{key} must be a list of strings"
                            )
                            ok = False

        naming = analysis.get("naming", {})
        if not isinstance(naming, dict):
            print("❌ analysis.naming must be a table/object")
            ok = False
        else:
            for target in _NAMING_RULE_TARGETS:
                rule = naming.get(target, {})
                if not isinstance(rule, dict):
                    print(f"❌ analysis.naming.{target} must be a table/object")
                    ok = False
                    continue
                style = str(rule.get("style", "infer")).strip().lower()
                if style not in _NAMING_STYLE_KEYS:
                    print(
                        f"❌ analysis.naming.{target}.style must be one of: "
                        + ", ".join(_NAMING_STYLE_KEYS)
                    )
                    ok = False
                allow = rule.get("allow", [])
                if not isinstance(allow, list) or not all(
                    isinstance(item, str) for item in allow
                ):
                    print(
                        f"❌ analysis.naming.{target}.allow must be a list of strings"
                    )
                    ok = False

    print("------------------------------\n")
    return ok
