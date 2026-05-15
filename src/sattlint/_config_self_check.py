from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from . import config as config_module


def _self_check_directories(cfg: dict[str, Any]) -> bool:
    validation = config_module.validate_loaded_config(cfg)
    errors_by_key = config_module._validation_errors_by_key(validation)
    ok = True

    for name in ("program_dir", "ABB_lib_dir", "icf_dir"):
        raw = cfg.get(name, "")
        if not raw:
            print(f"WARNING {name} not set")
            continue
        path = Path(raw)
        messages = errors_by_key.get(name, ())
        if messages:
            for message in messages:
                print(message)
            ok = False
        else:
            print(f"{name}: {path}")

    for index, raw_path in enumerate(cfg.get("other_lib_dirs", [])):
        path = Path(raw_path)
        messages = errors_by_key.get(f"other_lib_dirs[{index}]", ())
        if messages:
            for message in messages:
                print(message)
        else:
            print(f"other_lib_dirs: {path}")

    return ok


def _self_check_targets(cfg: dict[str, Any]) -> bool:
    validation = config_module.validate_loaded_config(cfg)
    errors_by_key = config_module._validation_errors_by_key(validation)
    ok = True
    targets = list(config_module._configured_targets(cfg))
    if not targets:
        print("WARNING analyzed_programs_and_libraries is empty")
        print("Configure targets before running analyses, documentation, or AST cache refresh.")
        return ok

    print("Analyzed programs/libraries:")
    for index, target in enumerate(targets):
        messages = errors_by_key.get(f"analyzed_programs_and_libraries[{index}]", ())
        if messages:
            for message in messages:
                print(message)
            ok = False
        else:
            print(f"\u2714 {target}")
    return ok


def _report_validation_namespace(cfg: dict[str, Any], namespace: str) -> bool:
    validation = config_module.validate_config(cfg)
    ok = True
    for error in validation.errors:
        if not error.key_path.startswith(namespace):
            continue
        print(error.message)
        ok = False
    return ok


def _self_check_graphics_rules() -> bool:
    validation = config_module.validate_loaded_config(config_module.DEFAULT_CONFIG)
    del validation
    graphics_rules_path = config_module.get_graphics_rules_path()
    if graphics_rules_path.exists():
        from . import graphics_rules as graphics_rules_module

        try:
            graphics_rules, _created = graphics_rules_module.load_graphics_rules(graphics_rules_path)
        except Exception as exc:
            print(f"graphics_rules_path invalid: {graphics_rules_path} ({exc})")
            return False
        print(f"graphics_rules_path: {graphics_rules_path} ({len(graphics_rules.get('rules', []))} rules)")
        return True

    print(f"graphics_rules_path not created yet: {graphics_rules_path}")
    return True


def self_check(cfg: dict[str, Any]) -> bool:
    print("\n--- Self-check diagnostics ---")
    ok = True

    print(f"\u2714 Python {sys.version.split()[0]}")

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
    for key in required_keys:
        if key not in cfg:
            print(f"â�Œ Missing config key: {key}")
            ok = False

    ok = _self_check_directories(cfg) and ok
    ok = _self_check_targets(cfg) and ok
    ok = _report_validation_namespace(cfg, "documentation") and ok
    ok = _report_validation_namespace(cfg, "analysis") and ok
    ok = _self_check_graphics_rules() and ok

    print("------------------------------\n")
    return ok
