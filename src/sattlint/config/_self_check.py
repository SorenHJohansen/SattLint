from __future__ import annotations

import sys
from pathlib import Path

from .. import console as console_module
from .defaults import REQUIRED_TOP_LEVEL_CONFIG_KEYS
from .types import ConfigDict
from .validation import (
    configured_targets,
    validate_config,
    validate_loaded_config,
    validation_errors_by_key,
)

emit_output = console_module.print_output


def _self_check_directories(cfg: ConfigDict, *, errors_by_key: dict[str, tuple[str, ...]]) -> bool:
    ok = True

    for name in ("program_dir", "ABB_lib_dir", "icf_dir"):
        raw = cfg.get(name, "")
        if not raw:
            emit_output(f"WARNING {name} not set")
            continue
        path = Path(raw)
        messages = errors_by_key.get(name, ())
        if messages:
            for message in messages:
                emit_output(message)
            ok = False
        else:
            emit_output(f"{name}: {path}")

    for index, raw_path in enumerate(cfg.get("other_lib_dirs", [])):
        path = Path(raw_path)
        messages = errors_by_key.get(f"other_lib_dirs[{index}]", ())
        if messages:
            for message in messages:
                emit_output(message)
        else:
            emit_output(f"other_lib_dirs: {path}")

    return ok


def _self_check_targets(cfg: ConfigDict, *, errors_by_key: dict[str, tuple[str, ...]]) -> bool:
    ok = True
    targets = list(configured_targets(cfg))
    if not targets:
        emit_output("WARNING analyzed_programs_and_libraries is empty")
        emit_output("Configure targets before running analyses, documentation, or AST cache refresh.")
        return ok

    emit_output("Analyzed programs/libraries:")
    for index, target in enumerate(targets):
        messages = errors_by_key.get(f"analyzed_programs_and_libraries[{index}]", ())
        if messages:
            for message in messages:
                emit_output(message)
            ok = False
        else:
            emit_output(f"\u2714 {target}")
    return ok


def _report_validation_namespace(cfg: ConfigDict, namespace: str) -> bool:
    validation = validate_config(cfg)
    ok = True
    for error in validation.errors:
        if not error.key_path.startswith(namespace):
            continue
        emit_output(error.message)
        ok = False
    return ok


def self_check(cfg: ConfigDict) -> bool:
    emit_output("\n--- Self-check diagnostics ---")
    ok = True

    emit_output(f"\u2714 Python {sys.version.split()[0]}")

    for key in REQUIRED_TOP_LEVEL_CONFIG_KEYS:
        if key not in cfg:
            emit_output(f"â�Œ Missing config key: {key}")
            ok = False

    validation = validate_loaded_config(cfg)
    errors_by_key = validation_errors_by_key(validation)

    ok = _self_check_directories(cfg, errors_by_key=errors_by_key) and ok
    ok = _self_check_targets(cfg, errors_by_key=errors_by_key) and ok
    ok = _report_validation_namespace(cfg, "analysis") and ok

    emit_output("------------------------------\n")
    return ok
