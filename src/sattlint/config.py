"""Configuration management for SattLint."""
from __future__ import annotations

from copy import deepcopy
import os
import sys
import tomllib
import tomli_w
from pathlib import Path

_DOCUMENTATION_RULE_LIST_KEYS = (
    "moduletype_name_contains",
    "moduletype_label_equals",
    "descendant_moduletype_name_contains",
    "descendant_moduletype_label_equals",
)
_DOCUMENTATION_UNIT_SELECTION_MODES = {"all", "instance_paths", "moduletype_names"}

DEFAULT_CONFIG = {
    "analyzed_programs_and_libraries": [],
    "mode": "official",
    "scan_root_only": False,
    "fast_cache_validation": True,
    "debug": False,
    "program_dir": "",
    "ABB_lib_dir": "",
    "icf_dir": "",
    "other_lib_dirs": [],
    "documentation": {
        "section_order": [
            "equipment_modules",
            "operations",
            "recipe_parameters",
            "engineering_parameters",
            "user_parameters",
        ],
        "units": {
            "mode": "all",
            "instance_paths": [],
            "moduletype_names": [],
        },
        "classifications": {
            "equipment_modules": {
                "moduletype_name_contains": [],
                "moduletype_label_equals": [],
                "descendant_moduletype_name_contains": [],
                "descendant_moduletype_label_equals": [
                    "nnestruct:EquipModCoordinate"
                ],
            },
            "operations": {
                "moduletype_name_contains": [],
                "moduletype_label_equals": [],
                "descendant_moduletype_name_contains": [],
                "descendant_moduletype_label_equals": [
                    "NNEMESIFLib:MES_StateControl"
                ],
            },
            "recipe_parameters": {
                "moduletype_name_contains": ["RecPar"],
                "moduletype_label_equals": [],
                "descendant_moduletype_name_contains": [],
                "descendant_moduletype_label_equals": [],
            },
            "engineering_parameters": {
                "moduletype_name_contains": ["EngPar"],
                "moduletype_label_equals": [],
                "descendant_moduletype_name_contains": [],
                "descendant_moduletype_label_equals": [],
            },
            "user_parameters": {
                "moduletype_name_contains": ["UsrPar"],
                "moduletype_label_equals": [],
                "descendant_moduletype_name_contains": [],
                "descendant_moduletype_label_equals": [],
            },
        },
    },
}


def _deep_merge_dict(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
            continue
        merged[key] = value
    return merged


def get_documentation_config(cfg: dict | None = None) -> dict:
    documentation_defaults = deepcopy(DEFAULT_CONFIG["documentation"])
    if not cfg:
        return documentation_defaults

    if "documentation" in cfg and isinstance(cfg.get("documentation"), dict):
        override = cfg.get("documentation", {})
    else:
        override = cfg
    if not isinstance(override, dict):
        return documentation_defaults
    return _deep_merge_dict(documentation_defaults, override)


def get_documentation_unit_selection(cfg: dict | None = None) -> dict:
    documentation_cfg = get_documentation_config(cfg)
    units = documentation_cfg.get("units", {})
    if not isinstance(units, dict):
        return deepcopy(DEFAULT_CONFIG["documentation"]["units"])
    return _deep_merge_dict(DEFAULT_CONFIG["documentation"]["units"], units)

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
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ required")
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
        print("❌ analyzed_programs_and_libraries must contain at least one entry")
        ok = False
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
        section_order = documentation.get("section_order", [])
        if not isinstance(section_order, list) or not all(
            isinstance(name, str) and name.strip() for name in section_order
        ):
            print("❌ documentation.section_order must be a non-empty list of strings")
            ok = False
        else:
            print(
                "✔ documentation.section_order: "
                + ", ".join(str(name) for name in section_order)
            )

        classifications = documentation.get("classifications", {})
        if not isinstance(classifications, dict) or not classifications:
            print("❌ documentation.classifications must be a non-empty table/object")
            ok = False
        else:
            for category, rule in classifications.items():
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
                if ok:
                    active = [
                        key for key in _DOCUMENTATION_RULE_LIST_KEYS if rule.get(key)
                    ]
                    summary = ", ".join(active) if active else "no active matchers"
                    print(f"✔ documentation.classifications.{category}: {summary}")

        units = documentation.get("units", {})
        if not isinstance(units, dict):
            print("❌ documentation.units must be a table/object")
            ok = False
        else:
            mode = str(units.get("mode", "all")).strip().lower()
            if mode not in _DOCUMENTATION_UNIT_SELECTION_MODES:
                print(
                    "❌ documentation.units.mode must be one of: "
                    + ", ".join(sorted(_DOCUMENTATION_UNIT_SELECTION_MODES))
                )
                ok = False
            else:
                print(f"✔ documentation.units.mode: {mode}")

            for key in ("instance_paths", "moduletype_names"):
                values = units.get(key, [])
                if not isinstance(values, list) or not all(
                    isinstance(item, str) for item in values
                ):
                    print(f"❌ documentation.units.{key} must be a list of strings")
                    ok = False
                else:
                    summary = ", ".join(values) if values else "<empty>"
                    print(f"✔ documentation.units.{key}: {summary}")

    print("------------------------------\n")
    return ok
