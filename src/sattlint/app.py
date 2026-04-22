#!/usr/bin/env python3
"""CLI entry points and interactive helpers for SattLint."""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, cast

from . import config as config_module
from . import engine as engine_module
from . import graphics_rules as graphics_rules_module
from .analyzers import variable_usage_reporting as variables_reporting_module
from .analyzers.comment_code import analyze_comment_code_files
from .analyzers.framework import AnalysisContext
from .analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from .analyzers.mms import analyze_mms_interface_variables
from .analyzers.modules import (
    analyze_module_duplicates,
    compare_modules,
    debug_module_structure,
    find_modules_by_name,
)
from .analyzers.registry import get_default_cli_analyzers
from .analyzers.rule_profiles import apply_rule_profile_to_report
from .analyzers.shadowing import analyze_shadowing
from .analyzers.variable_usage_reporting import (
    debug_variable_usage,
)
from .analyzers.variables import (
    IssueKind,
    analyze_variables,
    filter_variable_report,
)
from .cache import ASTCache, compute_cache_key, get_cache_dir
from .docgenerator import generate_docx
from .docgenerator.classification import (
    classify_documentation_structure,
    discover_documentation_unit_candidates,
    document_scope_summary,
)
from .models.ast_model import BasePicture
from .models.project_graph import ProjectGraph
from .reporting.variables_report import (
    DEFAULT_VARIABLE_ANALYSIS_KINDS,
    VariablesReport,
)

VARIABLE_ANALYSES = {
    "1": ("All variable analyses (high confidence)", None),
    "2": ("Unused variables", {IssueKind.UNUSED}),
    "3": ("Unused fields in datatypes", {IssueKind.UNUSED_DATATYPE_FIELD}),
    "4": ("Read-only but not CONST", {IssueKind.READ_ONLY_NON_CONST}),
    "5": ("Written but never read", {IssueKind.NEVER_READ}),
    "6": ("Unknown parameter mapping targets", {IssueKind.UNKNOWN_PARAMETER_TARGET}),
    "7": ("String mapping type mismatches", {IssueKind.STRING_MAPPING_MISMATCH}),
    "8": ("Duplicated complex datatypes", {IssueKind.DATATYPE_DUPLICATION}),
    "9": ("Min/Max mapping name mismatches", {IssueKind.MIN_MAX_MAPPING_MISMATCH}),
    "10": ("Magic numbers", {IssueKind.MAGIC_NUMBER}),
    "11": ("Name collisions", {IssueKind.NAME_COLLISION}),
    "12": ("Reset contamination", {IssueKind.RESET_CONTAMINATION}),
    "13": ("Variable shadowing", {IssueKind.SHADOWING}),
    "14": ("UI/display-only variables", {IssueKind.UI_ONLY}),
    "15": ("Procedure status handling", {IssueKind.PROCEDURE_STATUS}),
    "16": ("Write-without-effect variables", {IssueKind.WRITE_WITHOUT_EFFECT}),
    "17": ("Cross-module contract mismatches", {IssueKind.CONTRACT_MISMATCH}),
    "18": ("Implicit latching", {IssueKind.IMPLICIT_LATCH}),
    "19": ("Global scope minimization", {IssueKind.GLOBAL_SCOPE_MINIMIZATION}),
    "20": ("Hidden global coupling", {IssueKind.HIDDEN_GLOBAL_COUPLING}),
    "21": ("High fan-in or fan-out variables", {IssueKind.HIGH_FAN_IN_OUT}),
}

HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS = (
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
)

LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS = (
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
)


CONFIG_PATH = config_module.get_config_path()
DEFAULT_CONFIG = config_module.DEFAULT_CONFIG
_DOCUMENTATION_SCOPE_STATE = {
    "mode": "all",
    "instance_paths": [],
    "moduletype_names": [],
}


@dataclass(frozen=True)
class MenuOption:
    key: str
    label: str
    description: str = ""


class TargetLoadError(RuntimeError):
    def __init__(
        self,
        target_name: str,
        *,
        resolved: list[str],
        missing: list[str],
        warnings: list[str] | None = None,
        direct_dependencies: list[str] | None = None,
    ):
        self.target_name = target_name
        self.resolved = list(resolved)
        self.missing = list(missing)
        self.warnings = list(warnings or [])
        self.direct_dependencies = list(direct_dependencies or [])
        super().__init__(self._build_message())

    @staticmethod
    def _extract_missing_name(item: str) -> str | None:
        marker = " parse/transform error: "
        if marker in item:
            return item.split(marker, 1)[0]
        match = re.match(r"Missing code file for '([^']+)'", item)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _extract_warning_name(item: str) -> str | None:
        if ": " not in item:
            return None
        return item.split(": ", 1)[0]

    @staticmethod
    def _format_missing_item(item: str) -> str:
        marker = " parse/transform error: "
        if marker in item:
            name, detail = item.split(marker, 1)
            return f"{name}: {detail}"
        return item

    def _build_message(self) -> str:
        direct_keys = {name.casefold() for name in self.direct_dependencies}
        root_failures: list[str] = []
        direct_failures: list[str] = []
        transitive_failures: list[str] = []
        other_failures: list[str] = []
        root_warnings: list[str] = []
        direct_warnings: list[str] = []
        transitive_warnings: list[str] = []
        other_warnings: list[str] = []

        for item in self.missing:
            failure_name = self._extract_missing_name(item)
            if failure_name is None:
                other_failures.append(item)
                continue
            if failure_name.casefold() == self.target_name.casefold():
                root_failures.append(item)
            elif failure_name.casefold() in direct_keys:
                direct_failures.append(item)
            else:
                transitive_failures.append(item)

        for item in self.warnings:
            warning_name = self._extract_warning_name(item)
            if warning_name is None:
                other_warnings.append(item)
            elif warning_name.casefold() == self.target_name.casefold():
                root_warnings.append(item)
            elif warning_name.casefold() in direct_keys:
                direct_warnings.append(item)
            else:
                transitive_warnings.append(item)

        lines = [f"Target {self.target_name!r} was not parsed."]
        if self.direct_dependencies:
            lines.append(f"Direct dependencies from the target file ({len(self.direct_dependencies)}):")
            lines.extend(f"  - {name}" for name in self.direct_dependencies)
        if self.resolved:
            lines.append(f"Resolved targets ({len(self.resolved)}):")
            lines.extend(f"  - {name}" for name in self.resolved)
        else:
            lines.append("Resolved targets: none")

        if root_failures:
            lines.append(f"Root target validation errors ({len(root_failures)}):")
            lines.extend(f"  - {self._format_missing_item(item)}" for item in root_failures)

        if root_warnings:
            lines.append(f"Root target warnings ({len(root_warnings)}):")
            lines.extend(f"  - {item}" for item in root_warnings)

        if direct_failures:
            lines.append(f"Failed direct dependencies ({len(direct_failures)}):")
            lines.extend(f"  - {self._format_missing_item(item)}" for item in direct_failures)

        if direct_warnings:
            lines.append(f"Direct dependency warnings ({len(direct_warnings)}):")
            lines.extend(f"  - {item}" for item in direct_warnings)

        if transitive_failures:
            lines.append(f"Transitive dependency failures ({len(transitive_failures)}):")
            lines.extend(f"  - {self._format_missing_item(item)}" for item in transitive_failures)

        if transitive_warnings:
            lines.append(f"Transitive dependency warnings ({len(transitive_warnings)}):")
            lines.extend(f"  - {item}" for item in transitive_warnings)

        if other_failures:
            lines.append(f"Other missing/failed entries ({len(other_failures)}):")
            lines.extend(f"  - {self._format_missing_item(item)}" for item in other_failures)

        if other_warnings:
            lines.append(f"Other warnings ({len(other_warnings)}):")
            lines.extend(f"  - {item}" for item in other_warnings)

        if not self.missing:
            lines.append("Missing/failed targets: none")

        return "\n".join(lines)


def _print_validation_warnings(warnings: list[str], *, limit: int = 12) -> None:
    if not warnings:
        return

    print(f"Validation warnings ({len(warnings)}):")
    for item in warnings[:limit]:
        print(f"  - {item}")
    if len(warnings) > limit:
        print(f"  - ... (+{len(warnings) - limit} more)")


def _extract_warning_name(item: str) -> str | None:
    if ": " not in item:
        return None
    return item.split(": ", 1)[0]


def _target_validation_warnings(target_name: str, warnings: list[str]) -> list[str]:
    return [
        item
        for item in warnings
        if (warning_name := _extract_warning_name(item)) is None or warning_name.casefold() == target_name.casefold()
    ]


def load_config(path: Path):
    return config_module.load_config(path)


def save_config(path: Path, cfg: dict) -> None:
    config_module.save_config(path, cfg)
    print("Config saved")


def get_graphics_rules_path() -> Path:
    return graphics_rules_module.get_graphics_rules_path(CONFIG_PATH)


def load_graphics_rules(path: Path | None = None):
    return graphics_rules_module.load_graphics_rules(path or get_graphics_rules_path())


def save_graphics_rules(path: Path, rules: dict[str, Any]) -> None:
    graphics_rules_module.save_graphics_rules(path, rules)
    print("Graphics rules saved")


def self_check(cfg: dict) -> bool:
    return config_module.self_check(cfg)


# Configure logging so normal runs stay quiet unless debug mode is enabled.
logging.basicConfig(format="%(message)s", level=logging.INFO)
logging.getLogger().setLevel(logging.INFO)

log = logging.getLogger("SattLint")


# ----------------------------
# Helpers
# ----------------------------
def _configure_windows_console_api(kernel32, coord_type, buffer_info_type):
    import ctypes
    from ctypes import wintypes

    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE

    kernel32.GetConsoleScreenBufferInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(buffer_info_type),
    ]
    kernel32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL

    kernel32.FillConsoleOutputCharacterW.argtypes = [
        wintypes.HANDLE,
        wintypes.WCHAR,
        wintypes.DWORD,
        coord_type,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.FillConsoleOutputCharacterW.restype = wintypes.BOOL

    kernel32.FillConsoleOutputAttribute.argtypes = [
        wintypes.HANDLE,
        wintypes.WORD,
        wintypes.DWORD,
        coord_type,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.FillConsoleOutputAttribute.restype = wintypes.BOOL

    kernel32.SetConsoleCursorPosition.argtypes = [wintypes.HANDLE, coord_type]
    kernel32.SetConsoleCursorPosition.restype = wintypes.BOOL


def _clear_windows_console() -> None:
    import ctypes
    from ctypes import wintypes

    class _Coord(ctypes.Structure):
        _fields_: ClassVar[Any] = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

    class _SmallRect(ctypes.Structure):
        _fields_: ClassVar[Any] = [
            ("Left", wintypes.SHORT),
            ("Top", wintypes.SHORT),
            ("Right", wintypes.SHORT),
            ("Bottom", wintypes.SHORT),
        ]

    class _ConsoleScreenBufferInfo(ctypes.Structure):
        _fields_: ClassVar[Any] = [
            ("dwSize", _Coord),
            ("dwCursorPosition", _Coord),
            ("wAttributes", wintypes.WORD),
            ("srWindow", _SmallRect),
            ("dwMaximumWindowSize", _Coord),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[reportAttributeAccessIssue]
    _configure_windows_console_api(kernel32, _Coord, _ConsoleScreenBufferInfo)

    std_output_handle = wintypes.DWORD(-11).value
    stdout_handle = kernel32.GetStdHandle(std_output_handle)
    invalid_handle = ctypes.c_void_p(-1).value
    if stdout_handle in (None, 0, invalid_handle):
        raise OSError("unable to access stdout console handle")

    buffer_info = _ConsoleScreenBufferInfo()
    if not kernel32.GetConsoleScreenBufferInfo(stdout_handle, ctypes.byref(buffer_info)):
        raise OSError(ctypes.get_last_error(), "GetConsoleScreenBufferInfo failed")  # type: ignore[reportAttributeAccessIssue]

    cell_count = int(buffer_info.dwSize.X) * int(buffer_info.dwSize.Y)
    written = wintypes.DWORD()
    origin = _Coord(0, 0)

    if not kernel32.FillConsoleOutputCharacterW(
        stdout_handle,
        " ",
        cell_count,
        origin,
        ctypes.byref(written),
    ):
        raise OSError(ctypes.get_last_error(), "FillConsoleOutputCharacterW failed")  # type: ignore[reportAttributeAccessIssue]
    if not kernel32.FillConsoleOutputAttribute(
        stdout_handle,
        buffer_info.wAttributes,
        cell_count,
        origin,
        ctypes.byref(written),
    ):
        raise OSError(ctypes.get_last_error(), "FillConsoleOutputAttribute failed")  # type: ignore[reportAttributeAccessIssue]
    if not kernel32.SetConsoleCursorPosition(stdout_handle, origin):
        raise OSError(ctypes.get_last_error(), "SetConsoleCursorPosition failed")  # type: ignore[reportAttributeAccessIssue]


def clear_screen():
    sys.stdout.flush()
    if os.name == "nt":
        try:
            _clear_windows_console()
            return
        except OSError:
            if os.system("cls") == 0:  # nosec B605 B607 - fixed built-in command used as Windows console fallback
                return

    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def pause():
    input("\nPress Enter to continue...")


class QuitAppError(Exception):
    pass


def quit_app() -> None:
    clear_screen()
    raise QuitAppError()


def confirm(msg: str) -> bool:
    return input(f"{msg} [y/N]: ").strip().lower() in ("y", "yes")


def prompt(msg: str, default: str | None = None) -> str:
    if default is not None:
        return input(f"{msg} [{default}]: ").strip() or default
    return input(f"{msg}: ").strip()


def target_exists(target: str, cfg: dict) -> bool:
    return config_module.target_exists(target, cfg)


def apply_debug(cfg: dict):
    level = logging.DEBUG if cfg.get("debug") else logging.INFO
    logging.getLogger().setLevel(level)
    log.setLevel(level)


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sattlint",
        description="Interactive SattLine analysis app with a non-interactive syntax-check command.",
    )
    subparsers = parser.add_subparsers(dest="command")

    syntax_parser = subparsers.add_parser(
        "syntax-check",
        help="Validate a single SattLine file with the parser and transformer",
        description="Validate one SattLine source file and report a compact syntax or validation error.",
    )
    syntax_parser.add_argument("file", help="Path to the SattLine source file")
    return parser


def _format_syntax_error(result: engine_module.SyntaxValidationResult) -> str:
    location = ""
    if result.line is not None and result.column is not None:
        location = f":{result.line}:{result.column}"
    elif result.line is not None:
        location = f":{result.line}"

    detail = result.message or "Unknown error"
    return f"ERROR [{result.stage}] {result.file_path}{location}: {detail}"


def _format_syntax_warning(file_path: Path, message: str) -> str:
    return f"WARNING [validation] {file_path}: {message}"


def run_syntax_check_command(file_path: str) -> int:
    target_path = Path(file_path)
    if not target_path.exists() or not target_path.is_file():
        print(f"ERROR [io] {target_path}: File not found", file=sys.stderr)
        return 1

    result = engine_module.validate_single_file_syntax(target_path)
    if result.ok:
        for warning in result.warnings:
            print(_format_syntax_warning(result.file_path, warning), file=sys.stderr)
        print("OK")
        return 0

    print(_format_syntax_error(result), file=sys.stderr)
    return 1


def run_cli(argv: list[str]) -> int:
    parser = build_cli_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        return code

    if args.command == "syntax-check":
        return run_syntax_check_command(args.file)

    parser.print_usage(sys.stderr)
    return 1


# ----------------------------
# Display
# ----------------------------


def _format_config_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value in (None, ""):
        return "(not set)"
    return str(value)


def _print_config_section(title: str, rows: list[tuple[str, object]]) -> None:
    print(title)
    if not rows:
        print("  (none)")
        return

    label_width = max(len(label) for label, _ in rows)
    for label, value in rows:
        print(f"  {label:<{label_width}}  {_format_config_scalar(value)}")


def _print_config_list(title: str, items: list[object]) -> None:
    print(title)
    if not items:
        print("  (none)")
        return

    for index, item in enumerate(items, 1):
        print(f"  [{index}] {_format_config_scalar(item)}")


def show_config(cfg: dict):
    documentation_cfg = config_module.get_documentation_config(cfg)
    graphics_rules_path = get_graphics_rules_path()
    graphics_rule_count: object = 0
    graphics_rules_payload: dict[str, Any] | None = None
    if graphics_rules_path.exists():
        try:
            graphics_rules, _created = load_graphics_rules(graphics_rules_path)
        except Exception as exc:
            graphics_rule_count = f"invalid ({exc})"
        else:
            graphics_rules_payload = graphics_rules
            graphics_rule_count = len(graphics_rules.get("rules", []))
    general_rows = [
        ("mode", cfg["mode"]),
        ("scan_root_only", cfg["scan_root_only"]),
        ("fast_cache_validation", cfg["fast_cache_validation"]),
        ("debug", cfg["debug"]),
    ]
    directory_rows = [
        ("program_dir", cfg["program_dir"]),
        ("ABB_lib_dir", cfg["ABB_lib_dir"]),
        ("icf_dir", cfg["icf_dir"]),
    ]

    print("\nCurrent Configuration")
    print("=" * 21)
    print()
    _print_config_list(
        "Analyzed Programs And Libraries",
        list(cfg["analyzed_programs_and_libraries"]),
    )
    print()
    _print_config_section("General", general_rows)
    print()
    _print_config_section("Directories", directory_rows)
    print()
    _print_config_list("Other Library Directories", list(cfg["other_lib_dirs"]))
    print()
    _print_config_section(
        "Graphics Rules",
        [
            ("graphics_rules_path", graphics_rules_path),
            ("graphics_rule_count", graphics_rule_count),
        ],
    )
    if graphics_rules_payload and graphics_rules_payload.get("rules"):
        print("Configured Graphics Rule Selectors")
        for index, rule in enumerate(graphics_rules_payload.get("rules", []), start=1):
            print(f"  [{index}] {_graphics_rule_config_line(rule)}")
    print()
    print("Documentation Classifications")
    for category, rule in documentation_cfg.get("classifications", {}).items():
        active_rules = [(key, ", ".join(str(value) for value in values)) for key, values in rule.items() if values]
        print(f"  {category}")
        if not active_rules:
            print("    (none)")
            continue
        label_width = max(len(key) for key, _ in active_rules)
        for key, value in active_rules:
            print(f"    {key:<{label_width}}  {value}")
    print()


def _print_menu(
    title: str,
    options: Sequence[MenuOption],
    *,
    intro: str | None = None,
    note: str | None = None,
) -> None:
    print(f"\n--- {title} ---")
    if intro:
        print(intro.strip())
        print()

    label_width = max((len(option.label) for option in options), default=0)
    for option in options:
        if option.description:
            print(f"{option.key}) {option.label:<{label_width}}  {option.description}")
        else:
            print(f"{option.key}) {option.label}")

    if note:
        print()
        print(note.strip())


def _summarize_targets(cfg: dict) -> str:
    targets = _get_analyzed_targets(cfg)
    if not targets:
        return "No analysis targets configured yet. Open Setup first."
    if len(targets) == 1:
        return f"1 target configured: {targets[0]}"
    preview = ", ".join(targets[:3])
    if len(targets) > 3:
        preview += ", ..."
    return f"{len(targets)} targets configured: {preview}"


def show_help(cfg: dict) -> None:
    clear_screen()
    targets = _get_analyzed_targets(cfg)
    print(
        """
--- Help ---
SattLint can validate a single file quickly or analyze configured programs and
libraries together with their dependencies.

Recommended first run:
1. Open Setup and configure program_dir, ABB_lib_dir, and any extra library folders.
2. Add one or more analysis targets without file extensions.
3. Save the configuration.
4. Open Tools and run Self-check diagnostics.
5. Open Analyze to run checks, or Documentation to build DOCX output.

Main areas:
- Analyze: run curated reports, the full analyzer suite, or registry-backed checks.
- Documentation: preview unit candidates, choose scope, and generate DOCX output.
- Setup: edit directories, targets, mode, caching, and debug settings.
- Tools: self-check, dumps, and AST cache refresh for troubleshooting.

Quick single-file validation:
  sattlint syntax-check /path/to/Program.s

That command is useful when you want a strict parser or transformer check for one file
without loading a whole workspace.
"""
    )
    if targets:
        print(f"Current target status: {_summarize_targets(cfg)}")
    else:
        print("Current target status: no configured targets yet.")
    pause()


# ----------------------------
# Analysis & dumps
# ----------------------------
def _get_analyzed_targets(cfg: dict) -> list[str]:
    seen: set[str] = set()
    targets: list[str] = []
    for raw in cfg.get("analyzed_programs_and_libraries", []):
        target = str(raw).strip()
        if not target:
            continue
        key = target.casefold()
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)
    return targets


def _require_analyzed_targets(cfg: dict) -> list[str]:
    targets = _get_analyzed_targets(cfg)
    if not targets:
        raise RuntimeError(
            "No analyzed programs/libraries configured. Add entries to 'analyzed_programs_and_libraries' first."
        )
    return targets


def _has_analyzed_targets(cfg: dict) -> bool:
    return bool(_get_analyzed_targets(cfg))


def _require_targets_for_menu_action(cfg: dict, action: str) -> bool:
    if _has_analyzed_targets(cfg):
        return True
    print(f"\nNo analyzed programs/libraries configured. Add entries in Setup before {action}.")
    pause()
    return False


def _cache_key_for_target(cfg: dict, target_name: str) -> str:
    cache_cfg = cfg.copy()
    cache_cfg["analysis_target"] = target_name
    return compute_cache_key(cache_cfg)


def _split_csv_values(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


def _flatten_graphics_expected_fields(
    payload: dict[str, Any],
    *,
    prefix: str = "",
) -> list[str]:
    fields: list[str] = []
    for key, value in payload.items():
        field_name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            fields.extend(_flatten_graphics_expected_fields(value, prefix=field_name))
        else:
            fields.append(field_name)
    return fields


def _truncate_table_cell(value: object, width: int) -> str:
    text = str(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _graphics_rule_selector_text(rule: dict[str, Any]) -> str:
    module_kind = str(rule.get("module_kind") or "")
    relative_module_path = str(rule.get("relative_module_path") or "").strip()
    unit_structure_path = str(rule.get("unit_structure_path") or "").strip()
    equipment_module_structure_path = str(rule.get("equipment_module_structure_path") or "").strip()
    if unit_structure_path:
        return f"unit:{unit_structure_path}"
    if equipment_module_structure_path:
        return f"equipment:{equipment_module_structure_path}"
    if module_kind == "moduletype":
        moduletype_name = str(rule.get("moduletype_name") or "").strip()
        if relative_module_path:
            return f"{moduletype_name} @ path:{relative_module_path}"
        return moduletype_name or "(missing moduletype name)"
    if relative_module_path:
        return f"path:{relative_module_path}"
    return str(rule.get("module_name") or "(missing module name)")


def _graphics_rule_label(rule: dict[str, Any]) -> str:
    return f"{rule['module_kind']}:{_graphics_rule_selector_text(rule)}"


def _graphics_rule_scope_text(rule: dict[str, Any]) -> str:
    if str(rule.get("unit_structure_path") or "").strip():
        return "unit"
    if str(rule.get("equipment_module_structure_path") or "").strip():
        return "equipment"
    if str(rule.get("relative_module_path") or "").strip():
        return "path"
    if str(rule.get("moduletype_name") or "").strip():
        return "moduletype"
    return "name"


def _graphics_rule_config_line(rule: dict[str, Any]) -> str:
    parts = [
        str(rule.get("module_kind") or ""),
        f"scope={_graphics_rule_scope_text(rule)}",
    ]
    unit_structure_path = str(rule.get("unit_structure_path") or "").strip()
    equipment_module_structure_path = str(rule.get("equipment_module_structure_path") or "").strip()
    relative_module_path = str(rule.get("relative_module_path") or "").strip()
    moduletype_name = str(rule.get("moduletype_name") or "").strip()
    description = str(rule.get("description") or "").strip()

    if unit_structure_path:
        parts.append(f"unit_structure_path={unit_structure_path}")
    if equipment_module_structure_path:
        parts.append(f"equipment_module_structure_path={equipment_module_structure_path}")
    if relative_module_path:
        parts.append(f"relative_module_path={relative_module_path}")
    if moduletype_name:
        parts.append(f"moduletype_name={moduletype_name}")
    if description:
        parts.append(f"description={description}")
    return " | ".join(part for part in parts if part)


def _print_graphics_rules_summary(path: Path, rules: dict[str, Any], *, dirty: bool) -> None:
    print(f"\nGraphics rules file: {path}")
    print(f"Configured rules: {len(rules.get('rules', []))}")
    if dirty:
        print("Unsaved graphics rule changes")

    if not rules.get("rules"):
        print("  (no graphics rules configured)")
        return

    columns = (
        ("#", 3),
        ("Kind", 10),
        ("Selector", 52),
        ("Fields", 36),
        ("Description", 24),
    )
    header = "  " + "  ".join(f"{label:<{width}}" for label, width in columns)
    print()
    print(header)
    print("  " + "  ".join("-" * width for _label, width in columns))

    for index, rule in enumerate(rules.get("rules", []), start=1):
        fields = ", ".join(_flatten_graphics_expected_fields(rule.get("expected", {}))) or "(none)"
        row = (
            _truncate_table_cell(index, 3),
            _truncate_table_cell(rule.get("module_kind", ""), 10),
            _truncate_table_cell(_graphics_rule_selector_text(rule), 52),
            _truncate_table_cell(fields, 36),
            _truncate_table_cell(rule.get("description", ""), 24),
        )
        print("  " + "  ".join(f"{value:<{width}}" for value, (_label, width) in zip(row, columns, strict=False)))


def _prompt_optional_float_list(label: str, expected_count: int) -> list[float] | None:
    while True:
        raw = input(f"{label} ({expected_count} comma-separated numbers, blank to skip): ").strip()
        if not raw:
            return None
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if len(parts) != expected_count:
            print(f"? Expected {expected_count} values")
            continue
        try:
            return [float(part) for part in parts]
        except ValueError:
            print("? Enter numeric values only")


def _prompt_optional_text_list(label: str) -> list[str] | None:
    raw = input(f"{label} (comma-separated, blank to skip): ").strip()
    if not raw:
        return None
    return _split_csv_values(raw)


def _prompt_optional_bool(label: str) -> bool | None:
    while True:
        raw = input(f"{label} [y/n, blank to skip]: ").strip().lower()
        if not raw:
            return None
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("? Enter y, n, or leave blank")


def _prompt_graphics_rule_kind() -> str:
    options = {
        "1": "single",
        "2": "frame",
        "3": "moduletype",
        "single": "single",
        "frame": "frame",
        "moduletype": "moduletype",
    }
    while True:
        print("\nSelect module kind:")
        print("  1) single")
        print("  2) frame")
        print("  3) moduletype")
        raw = input("> ").strip().lower()
        module_kind = options.get(raw)
        if module_kind is not None:
            return module_kind
        print("? Choose single, frame, or moduletype")


def _prompt_graphics_rule_selector(
    module_kind: str,
    cfg: dict | None = None,
) -> tuple[str, str]:
    allow_blank = module_kind == "moduletype"
    options = {
        "1": "unit_structure_path",
        "2": "equipment_module_structure_path",
        "3": "relative_module_path",
    }
    while True:
        print("\nSelect selector scope:")
        print("  1) unit structure path")
        print("  2) equipment module structure path")
        print("  3) exact relative module path")
        if allow_blank:
            print("  Enter blank to match all instances of the selected ModuleType")
        raw = input("> ").strip().lower()
        if not raw and allow_blank:
            return "", ""
        selector_field = options.get(raw)
        if selector_field is None:
            print("? Choose 1, 2, or 3")
            continue
        selector_value = _pick_or_prompt_graphics_rule_selector_value(
            selector_field,
            module_kind,
            cfg=cfg,
        )
        if not selector_value:
            if allow_blank and selector_field == "":
                return "", ""
            continue
        return selector_field, selector_value


def _graphics_rule_target_kind_matches(module_kind: str, entry: dict[str, Any]) -> bool:
    entry_kind = str(entry.get("module_kind") or "").strip().lower()
    if module_kind == "single":
        return entry_kind == "module"
    if module_kind == "frame":
        return entry_kind == "frame"
    if module_kind == "moduletype":
        return entry_kind == "moduletype-instance"
    return False


def _selector_prompt_text(selector_field: str) -> str:
    return {
        "unit_structure_path": "Unit structure path",
        "equipment_module_structure_path": "Equipment module structure path",
        "relative_module_path": "Exact relative module path",
    }[selector_field]


def _discover_graphics_rule_selector_options(
    cfg: dict | None,
    *,
    selector_field: str,
    module_kind: str,
) -> list[dict[str, Any]]:
    if cfg is None or not _has_analyzed_targets(cfg):
        return []

    discovered: dict[str, dict[str, Any]] = {}
    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        try:
            entries = _collect_graphics_layout_entries_for_target(
                target_name,
                project_bp,
                graph,
            )
        except Exception:
            continue

        for entry in entries:
            if not _graphics_rule_target_kind_matches(module_kind, entry):
                continue
            selector_value = str(entry.get(selector_field) or "").strip()
            if not selector_value:
                continue
            if not str(entry.get("unit_root_path") or "").strip():
                continue

            key = selector_value.casefold()
            bucket = discovered.setdefault(
                key,
                {
                    "selector_value": selector_value,
                    "count": 0,
                    "targets": set(),
                    "sample_module_path": str(entry.get("module_path") or ""),
                },
            )
            bucket["count"] += 1
            cast(set[str], bucket["targets"]).add(target_name)

    return sorted(
        [
            {
                "selector_value": item["selector_value"],
                "count": item["count"],
                "target_count": len(cast(set[str], item["targets"])),
                "sample_module_path": item["sample_module_path"],
            }
            for item in discovered.values()
        ],
        key=lambda item: (str(item["selector_value"]).casefold(), str(item["sample_module_path"]).casefold()),
    )


def _pick_or_prompt_graphics_rule_selector_value(
    selector_field: str,
    module_kind: str,
    *,
    cfg: dict | None = None,
) -> str:
    options = _discover_graphics_rule_selector_options(
        cfg,
        selector_field=selector_field,
        module_kind=module_kind,
    )
    prompt_text = _selector_prompt_text(selector_field)

    if options:
        print(f"\nAvailable {prompt_text.lower()} values:")
        for index, option in enumerate(options, start=1):
            print(
                f"  {index}) {option['selector_value']} "
                f"[{option['count']} matches across {option['target_count']} targets]"
            )
        print("  m) Enter manually")

        while True:
            raw = input("> ").strip().lower()
            if raw == "m":
                break
            try:
                selected_index = int(raw) - 1
            except ValueError:
                print("? Choose an index or 'm'")
                continue
            if 0 <= selected_index < len(options):
                return str(options[selected_index]["selector_value"])
            print("? Invalid index")

    selector_value = input(f"{prompt_text}: ").strip()
    if not selector_value:
        print("? Selector path is required")
    return selector_value


def _path_startswith_casefold(path: Sequence[str], prefix: Sequence[str]) -> bool:
    if len(prefix) > len(path):
        return False
    return all(part.casefold() == other.casefold() for part, other in zip(path, prefix, strict=False))


def _graphics_entry_canonical_segment(entry: dict[str, Any]) -> str:
    moduletype_name = str(
        entry.get("moduletype_name") or entry.get("resolved_moduletype", {}).get("name") or ""
    ).strip()
    if moduletype_name:
        return moduletype_name
    return str(entry.get("module_name") or "").strip()


def _looks_like_graphics_unit_root(
    candidate_path: Sequence[str],
    entries: Sequence[dict[str, Any]],
) -> bool:
    for entry in entries:
        module_path = tuple(
            segment.strip() for segment in str(entry.get("module_path") or "").split(".") if segment.strip()
        )
        if not module_path or not _path_startswith_casefold(module_path, candidate_path):
            continue
        relative_segments = module_path[len(candidate_path) :]
        if len(relative_segments) < 3:
            continue
        if (
            relative_segments[0].casefold() == "l1"
            and relative_segments[1].casefold() == "l2"
            and relative_segments[2].casefold() == "unitcontrol"
        ):
            return True
    return False


def _annotate_graphics_entries_with_structure_paths(
    entries: list[dict[str, Any]],
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> list[dict[str, Any]]:
    classification = classify_documentation_structure(
        project_bp,
        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
    )
    unit_candidates = sorted(
        discover_documentation_unit_candidates(classification),
        key=lambda entry: len(entry.path),
        reverse=True,
    )
    candidate_paths = [
        tuple(candidate.path)
        for candidate in unit_candidates
        if _looks_like_graphics_unit_root(tuple(candidate.path), entries)
    ]

    for entry in entries:
        module_path = tuple(
            segment.strip() for segment in str(entry.get("module_path") or "").split(".") if segment.strip()
        )
        if not module_path:
            continue

        unit_root_path = next(
            (
                candidate_path
                for candidate_path in candidate_paths
                if _path_startswith_casefold(module_path, candidate_path)
            ),
            None,
        )
        if unit_root_path is None:
            continue

        unit_segments = list(module_path[len(unit_root_path) :])
        if not unit_segments:
            continue

        canonical_segments = [*unit_segments[:-1], _graphics_entry_canonical_segment(entry)]
        entry["unit_root_path"] = ".".join(unit_root_path)
        entry["unit_structure_path"] = ".".join(canonical_segments)

        if (
            len(canonical_segments) >= 5
            and canonical_segments[0].casefold() == "l1"
            and canonical_segments[1].casefold() == "l2"
            and canonical_segments[3].casefold() == "l1"
            and canonical_segments[4].casefold() == "l2"
        ):
            entry["equipment_module_name"] = unit_segments[2]
            entry["equipment_module_structure_path"] = ".".join(canonical_segments[3:])

    return entries


def _prompt_graphics_rule_definition() -> dict[str, Any] | None:
    return _prompt_graphics_rule_definition_with_config(None)


def graphics_rules_menu(cfg: dict | None = None) -> None:
    rules_path = get_graphics_rules_path()
    rules, _created = load_graphics_rules(rules_path)
    dirty = False

    while True:
        clear_screen()
        _print_graphics_rules_summary(rules_path, rules, dirty=dirty)
        print()
        _print_menu(
            "Graphics rules",
            [
                MenuOption("1", "Add or replace rule", "Prompt for one module graphics rule"),
                MenuOption("2", "Remove rule", "Delete one configured graphics rule by index"),
                MenuOption("3", "Save rules", "Write graphics rules to the JSON file"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro=(
                "Graphics rules are user-defined expected invocation and ModuleDef settings. "
                "Use unit structure paths, equipment module structure paths, exact relative module paths, "
                "or ModuleType names depending on the rule scope."
            ),
        )
        c = input("> ").strip().lower()

        if c == "b":
            if dirty and confirm("Unsaved graphics rule changes. Save before leaving?"):
                save_graphics_rules(rules_path, rules)
            return
        if c == "q":
            if dirty and confirm("Unsaved graphics rule changes. Save before quitting?"):
                save_graphics_rules(rules_path, rules)
            quit_app()

        if c == "1":
            rule = _prompt_graphics_rule_definition_with_config(cfg)
            if rule is None:
                continue
            updated = graphics_rules_module.upsert_graphics_rule(rules, rule)
            print("Updated existing graphics rule" if updated else "Added graphics rule")
            dirty = True
            pause()
        elif c == "2":
            if not rules.get("rules"):
                print("? No graphics rules configured")
                pause()
                continue
            idx_text = prompt("Index to remove")
            try:
                idx = int(idx_text) - 1
                removed = graphics_rules_module.remove_graphics_rule(rules, idx)
            except (ValueError, IndexError):
                print("? Invalid index")
                pause()
                continue
            print(f"Removed {_graphics_rule_label(removed)}")
            dirty = True
            pause()
        elif c == "3":
            save_graphics_rules(rules_path, rules)
            dirty = False
            pause()
        else:
            print("Invalid choice.")
            pause()


def _prompt_graphics_rule_definition_with_config(cfg: dict | None) -> dict[str, Any] | None:
    print("\nEnter graphics rule values. Leave optional fields blank to skip them.")
    module_kind = _prompt_graphics_rule_kind()

    module_name = ""
    relative_module_path = ""
    unit_structure_path = ""
    equipment_module_structure_path = ""
    moduletype_name = ""

    if module_kind == "moduletype":
        moduletype_name = prompt("ModuleType name")
        if not moduletype_name:
            print("? ModuleType name is required")
            pause()
            return None
        selector_field, selector_value = _prompt_graphics_rule_selector(module_kind, cfg=cfg)
    else:
        selector_field, selector_value = _prompt_graphics_rule_selector(module_kind, cfg=cfg)

    if selector_field == "relative_module_path":
        relative_module_path = selector_value
    elif selector_field == "unit_structure_path":
        unit_structure_path = selector_value
    elif selector_field == "equipment_module_structure_path":
        equipment_module_structure_path = selector_value

    selector_name = relative_module_path or unit_structure_path or equipment_module_structure_path
    if selector_name:
        module_name = selector_name.split(".")[-1].strip()

    description = input("Description (optional): ").strip()
    invocation: dict[str, Any] = {}
    moduledef: dict[str, Any] = {}

    invocation_coords = _prompt_optional_float_list("Invocation coords", 5)
    if invocation_coords is not None:
        invocation["coords"] = invocation_coords

    invocation_arguments = _prompt_optional_text_list("Invocation arguments")
    if invocation_arguments is not None:
        invocation["arguments"] = invocation_arguments

    invocation_layer = input("Invocation layer (blank to skip): ").strip()
    if invocation_layer:
        invocation["layer"] = invocation_layer

    invocation_zoom_limits = _prompt_optional_float_list(
        "Invocation zoom limits",
        2,
    )
    if invocation_zoom_limits is not None:
        invocation["zoom_limits"] = invocation_zoom_limits

    invocation_zoomable = _prompt_optional_bool("Invocation zoomable")
    if invocation_zoomable is not None:
        invocation["zoomable"] = invocation_zoomable

    clipping_origin = _prompt_optional_float_list("Clipping origin", 2)
    if clipping_origin is not None:
        moduledef["clipping_origin"] = clipping_origin

    clipping_size = _prompt_optional_float_list("Clipping size", 2)
    if clipping_size is not None:
        moduledef["clipping_size"] = clipping_size

    moduledef_zoom_limits = _prompt_optional_float_list("ModuleDef zoom limits", 2)
    if moduledef_zoom_limits is not None:
        moduledef["zoom_limits"] = moduledef_zoom_limits

    moduledef_grid = input("ModuleDef grid (blank to skip): ").strip()
    if moduledef_grid:
        try:
            moduledef["grid"] = float(moduledef_grid)
        except ValueError:
            print("? ModuleDef grid must be numeric")
            pause()
            return None

    moduledef_zoomable = _prompt_optional_bool("ModuleDef zoomable")
    if moduledef_zoomable is not None:
        moduledef["zoomable"] = moduledef_zoomable

    expected: dict[str, Any] = {}
    if invocation:
        expected["invocation"] = invocation
    if moduledef:
        expected["moduledef"] = moduledef

    if not expected:
        print("? At least one expected graphics field is required")
        pause()
        return None

    return {
        "module_name": module_name,
        "module_kind": module_kind,
        "relative_module_path": relative_module_path,
        "unit_structure_path": unit_structure_path,
        "equipment_module_structure_path": equipment_module_structure_path,
        "moduletype_name": moduletype_name,
        "description": description,
        "expected": expected,
    }


def _collect_graphics_layout_entries_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
) -> list[dict[str, Any]]:
    from .devtools import structural_reports as structural_reports_module

    synthetic_entry_file = Path.cwd() / f"{target_name}.s"
    snapshot = SimpleNamespace(
        entry_file=synthetic_entry_file,
        base_picture=project_bp,
        project_graph=graph,
    )
    discovery = SimpleNamespace(
        program_files=(synthetic_entry_file,),
        dependency_files=(),
    )
    report = structural_reports_module.collect_graphics_layout_report(
        workspace_root=Path.cwd(),
        graph_inputs=(discovery, [snapshot], []),
    )
    return _annotate_graphics_entries_with_structure_paths(
        list(report.get("entries", [])),
        project_bp,
        graph,
    )


def run_graphics_rules_validation(cfg: dict) -> None:
    print("\n--- Validate Graphics Rules ---")
    rules_path = get_graphics_rules_path()
    rules, _created = load_graphics_rules(rules_path)
    if not rules.get("rules"):
        print("? No graphics rules configured. Open Setup -> Edit graphics rules to add rules first.")
        pause()
        return

    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        try:
            entries = _collect_graphics_layout_entries_for_target(
                target_name,
                project_bp,
                graph,
            )
            report = graphics_rules_module.validate_graphics_layout_entries(
                entries,
                rules,
                target_name=target_name,
                rules_path=rules_path,
            )
            print(f"\n=== Target: {target_name} ===")
            print(report.summary())
        except Exception as exc:
            print(f"? Error during graphics rules validation for {target_name}: {exc}")

    pause()


def _get_documentation_unit_selection() -> dict:
    return {
        "mode": _DOCUMENTATION_SCOPE_STATE["mode"],
        "instance_paths": list(_DOCUMENTATION_SCOPE_STATE["instance_paths"]),
        "moduletype_names": list(_DOCUMENTATION_SCOPE_STATE["moduletype_names"]),
    }


def _set_documentation_unit_selection(
    *,
    mode: str,
    instance_paths: list[str] | None = None,
    moduletype_names: list[str] | None = None,
) -> None:
    _DOCUMENTATION_SCOPE_STATE["mode"] = mode
    _DOCUMENTATION_SCOPE_STATE["instance_paths"] = list(instance_paths or [])
    _DOCUMENTATION_SCOPE_STATE["moduletype_names"] = list(moduletype_names or [])


def _documentation_config_without_scope(cfg: dict) -> dict:
    documentation_cfg = config_module.get_documentation_config(cfg)
    documentation_cfg["units"] = {
        "mode": "all",
        "instance_paths": [],
        "moduletype_names": [],
    }
    return documentation_cfg


def _preview_documentation_candidates_for_target(
    target_name: str,
    project_bp: BasePicture,
    graph: ProjectGraph,
    cfg: dict,
) -> None:
    classification = classify_documentation_structure(
        project_bp,
        documentation_config=_documentation_config_without_scope(cfg),
        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
    )
    candidates = discover_documentation_unit_candidates(classification)
    print(f"\n=== Target: {target_name} ===")
    if not candidates:
        print("⚠ No unit candidates detected.")
        return

    for index, entry in enumerate(candidates, 1):
        summary = document_scope_summary(entry, classification)
        print(
            f"  {index}. {entry.short_path} | type={entry.moduletype_label or entry.kind} | "
            f"ops={summary['ops']} em={summary['em']} "
            f"rp={summary['rp']} ep={summary['ep']} up={summary['up']}"
        )


def preview_documentation_unit_candidates(cfg: dict) -> None:
    print("\n--- Documentation Unit Candidates ---")
    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        _preview_documentation_candidates_for_target(target_name, project_bp, graph, cfg)
    pause()


def configure_documentation_scope_by_moduletype(cfg: dict) -> bool:
    print("\n--- Documentation Scope by Unit ModuleType ---")
    print("Enter one or more unit moduletype names (comma-separated).")
    print("Example: ApplTank, XDilute_221X251XY")
    raw = input("> ").strip()
    values = _split_csv_values(raw)
    if not values:
        print("❌ No moduletype names provided")
        pause()
        return False
    _set_documentation_unit_selection(
        mode="moduletype_names",
        moduletype_names=values,
    )
    print("✔ Documentation scope updated")
    pause()
    return True


def configure_documentation_scope_by_instance_path(cfg: dict) -> bool:
    print("\n--- Documentation Scope by Unit Instance Path ---")
    print("Enter one or more unit instance paths (comma-separated).")
    print("Use the candidate preview to find valid paths.")
    raw = input("> ").strip()
    values = _split_csv_values(raw)
    if not values:
        print("❌ No instance paths provided")
        pause()
        return False
    _set_documentation_unit_selection(
        mode="instance_paths",
        instance_paths=values,
    )
    print("✔ Documentation scope updated")
    pause()
    return True


def reset_documentation_scope(cfg: dict) -> bool:
    _set_documentation_unit_selection(mode="all")
    print("✔ Documentation scope reset to all units")
    pause()
    return True


def run_generate_documentation(cfg: dict) -> None:
    print("\n--- Generate Documentation ---")
    documentation_cfg = config_module.get_documentation_config(cfg)
    documentation_cfg["units"] = _get_documentation_unit_selection()

    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        classification = classify_documentation_structure(
            project_bp,
            documentation_config=documentation_cfg,
            unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
        )
        scope = classification.scope
        if scope and scope.mode != "all" and not (scope.roots or []):
            print(f"\n=== Target: {target_name} ===")
            print("⚠ No unit roots matched the configured documentation scope; skipping target.")
            if scope.unmatched_values:
                print("Unmatched scope filters: " + ", ".join(scope.unmatched_values))
            continue

        default_name = f"{target_name}_FS.docx"
        out_name = prompt(f"Output DOCX for {target_name}", default_name)
        if scope and scope.roots:
            print(f"Selected units for {target_name}: " + ", ".join(entry.short_path for entry in scope.roots))
        generate_docx(
            project_bp,
            out_name,
            documentation_config=documentation_cfg,
            unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
        )

    pause()


def documentation_menu(cfg: dict) -> bool:
    dirty = False
    while True:
        clear_screen()
        selection = _get_documentation_unit_selection()
        _print_menu(
            "Documentation",
            [
                MenuOption("1", "Generate documentation", "Create DOCX output for each configured target"),
                MenuOption("2", "Preview unit candidates", "List the detected unit roots before choosing scope"),
                MenuOption("3", "Use all detected units", "Reset scoping and include every detected unit"),
                MenuOption("4", "Scope by moduletype", "Filter units by moduletype name"),
                MenuOption("5", "Scope by instance path", "Filter units by instance path"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro=(
                "Generate FS-style DOCX documentation for the configured targets. "
                "Preview candidates first if you want to scope the output to specific units."
            ),
        )
        print(
            "\nCurrent scope: "
            + (
                "all units"
                if selection["mode"] == "all"
                else f"{selection['mode']} -> "
                + ", ".join(selection["instance_paths"] or selection["moduletype_names"])
            )
        )
        c = input("> ").strip().lower()
        if c == "b":
            return dirty
        if c == "q":
            quit_app()

        if c == "1":
            run_generate_documentation(cfg)
        elif c == "2":
            preview_documentation_unit_candidates(cfg)
        elif c == "3":
            dirty |= reset_documentation_scope(cfg)
        elif c == "4":
            dirty |= configure_documentation_scope_by_moduletype(cfg)
        elif c == "5":
            dirty |= configure_documentation_scope_by_instance_path(cfg)
        else:
            print("Invalid choice.")
            pause()


def _iter_loaded_projects(
    cfg: dict,
    *,
    use_cache: bool = True,
) -> Iterator[tuple[str, BasePicture, ProjectGraph]]:
    for target_name in _require_analyzed_targets(cfg):
        try:
            project_bp, graph = load_project(
                cfg,
                target_name=target_name,
                use_cache=use_cache,
            )
        except Exception as exc:
            print(f"\n=== Target: {target_name} ===")
            print("? Failed to load target:")
            print(exc)
            continue
        yield target_name, project_bp, graph


def _source_paths_for_current_target(project_bp, graph) -> set[Path]:
    source_files: set[Path] = getattr(graph, "source_files", set())
    origin_file = getattr(project_bp, "origin_file", None)
    if origin_file:
        matches = {path for path in source_files if path.name.casefold() == origin_file.casefold()}
        if matches:
            return matches

    target_name = project_bp.header.name.casefold()
    return {path for path in source_files if path.stem.casefold() == target_name}


def _target_is_library(cfg: dict, project_bp, graph) -> bool:
    program_dir = cfg.get("program_dir")
    if not program_dir:
        return False

    source_paths = _source_paths_for_current_target(project_bp, graph)
    if not source_paths:
        return False

    program_path = Path(program_dir)
    return all(not engine_module._is_within_directory(path, program_path) for path in source_paths)


def load_project(
    cfg: dict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
    use_file_ast_cache: bool = True,
) -> tuple[BasePicture, ProjectGraph]:
    targets = _require_analyzed_targets(cfg)
    selected_target = target_name or targets[0]
    cache_dir = get_cache_dir()
    cache = ASTCache(cache_dir)

    key = _cache_key_for_target(cfg, selected_target)
    cached = cache.load(key) if use_cache else None

    if cached:
        log.debug("✔ Using cached AST (not revalidated)")
        return cast(tuple[BasePicture, ProjectGraph], cached["project"])

    loader = engine_module.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(p) for p in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine_module.CodeMode(cfg["mode"]),
        scan_root_only=cfg["scan_root_only"],
        debug=cfg["debug"],
        use_file_ast_cache=use_file_ast_cache,
    )

    graph = loader.resolve(selected_target, strict=False)
    deps_path = loader._find_deps_with_context(
        selected_target,
        requester_dir=Path(cfg["program_dir"]),
    )
    direct_dependencies = loader._read_deps(deps_path) if deps_path else []

    root_bp = graph.ast_by_name.get(selected_target)
    if not root_bp:
        raise TargetLoadError(
            selected_target,
            resolved=list(graph.ast_by_name.keys()),
            missing=graph.missing,
            warnings=graph.warnings,
            direct_dependencies=direct_dependencies,
        )

    project_bp = engine_module.merge_project_basepicture(root_bp, graph)

    # Collect actual files used
    used_files = set(graph.source_files)  # see note below

    cache.save(
        key,
        project=(project_bp, graph),
        files=used_files,
    )

    log.debug("✔ AST cached")
    return project_bp, graph


def load_program_ast(cfg: dict, program_name: str):
    """Load a single program AST without merging across libraries."""
    loader = engine_module.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(p) for p in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine_module.CodeMode(cfg["mode"]),
        scan_root_only=cfg["scan_root_only"],
        debug=cfg["debug"],
    )

    graph = loader.resolve(program_name, strict=False)
    root_bp = graph.ast_by_name.get(program_name)
    if not root_bp:
        raise RuntimeError(f"Program '{program_name}' not parsed. Resolved: {list(graph.ast_by_name.keys())}")

    return root_bp, graph


def force_refresh_ast(cfg: dict):
    """Clear cached ASTs for configured targets and rebuild them."""
    targets = _get_analyzed_targets(cfg)
    if not targets:
        return None

    cache_dir = get_cache_dir()
    cache = ASTCache(cache_dir)
    result = None
    for target_name in targets:
        cache.clear(_cache_key_for_target(cfg, target_name))
        result = load_project(
            cfg,
            target_name=target_name,
            use_cache=False,
            use_file_ast_cache=False,
        )
    log.debug("✔ AST caches cleared")
    return result


def ensure_ast_cache(cfg: dict) -> bool:
    """Check AST caches for configured targets and rebuild if needed."""
    targets = _get_analyzed_targets(cfg)
    if not targets:
        return True

    cache_dir = get_cache_dir()
    cache = ASTCache(cache_dir)
    fast = cfg.get("fast_cache_validation", False)
    ok = True
    for target_name in targets:
        print(f"\nChecking AST cache for {target_name}...")
        cached = cache.load(_cache_key_for_target(cfg, target_name))
        if cached:
            has_manifest = bool(cached.get("files"))
            if fast and has_manifest:
                is_valid = cache.validate(cached, fast=False)
            else:
                is_valid = cache.validate(cached, fast=fast)
            if is_valid:
                print("✔ AST cache OK")
                continue

            if has_manifest:
                print("⚠ AST cache stale; rebuilding (this may take a while)...")
            else:
                print("⚠ AST cache missing file manifest; rebuilding (this may take a while)...")
        else:
            print("⚠ AST cache missing; building (this may take a while)...")

        try:
            load_project(cfg, target_name=target_name, use_cache=False)
            print("✔ AST cache updated")
        except Exception as exc:
            print(f"❌ Failed to build AST cache for {target_name}: {exc}")
            ok = False

    return ok


def run_variable_analysis(cfg: dict, kinds: set[IssueKind] | None):
    def _merge_reports(*reports):
        basepicture_name = reports[0].basepicture_name
        issues = []
        visible_kinds: set[IssueKind] = set()
        include_empty_sections = False

        for report in reports:
            issues.extend(report.issues)
            if report.visible_kinds is not None:
                visible_kinds.update(report.visible_kinds)
            include_empty_sections = include_empty_sections or report.include_empty_sections

        return VariablesReport(
            basepicture_name=basepicture_name,
            issues=issues,
            visible_kinds=frozenset(visible_kinds) if visible_kinds else None,
            include_empty_sections=include_empty_sections,
        )

    requested_kinds = set(DEFAULT_VARIABLE_ANALYSIS_KINDS) | {IssueKind.SHADOWING} if kinds is None else set(kinds)

    produced_output = False
    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        produced_output = True
        target_is_library = _target_is_library(cfg, project_bp, graph)
        report = analyze_variables(
            project_bp,
            debug=cfg.get("debug", False),
            unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
            analyzed_target_is_library=target_is_library,
            config=cfg,
        )

        include_shadowing = IssueKind.SHADOWING in requested_kinds
        standard_kinds = requested_kinds - {IssueKind.SHADOWING}

        if standard_kinds:
            report = filter_variable_report(report, standard_kinds)
        else:
            report = VariablesReport(
                basepicture_name=report.basepicture_name,
                issues=[],
                visible_kinds=frozenset(),
                include_empty_sections=False,
            )

        if include_shadowing:
            shadowing_report = analyze_shadowing(
                project_bp,
                debug=cfg.get("debug", False),
                unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
            )
            if requested_kinds == {IssueKind.SHADOWING}:
                report = shadowing_report
            elif standard_kinds:
                report = _merge_reports(report, shadowing_report)

        print(f"\n=== Target: {target_name} ===")
        _print_validation_warnings(_target_validation_warnings(target_name, getattr(graph, "warnings", [])))
        print(report.summary())
    if not produced_output:
        print("\nNo variable analysis output was produced because no target loaded successfully.")
    pause()


def run_datatype_usage_analysis(cfg: dict):
    """Interactive datatype usage analysis (field-level usage by variable name)."""

    print("\n--- Datatype Usage Analysis ---")
    print("Enter the variable name to analyze:")
    var_name = input("> ").strip()

    if not var_name:
        print("❌ No variable name provided")
        pause()
        return

    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        try:
            report = variables_reporting_module.analyze_datatype_usage(
                project_bp,
                var_name,
                debug=cfg.get("debug", False),
                unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
            )
            print(f"\n=== Target: {target_name} ===")
            print(report)
        except Exception as e:
            print(f"❌ Error during analysis for {target_name}: {e}")

    pause()


def variable_usage_submenu(cfg: dict):
    """Variable usage analysis submenu."""
    while True:
        clear_screen()
        print("\n--- Variable issues ---")
        print("Run focused variable reports or open the investigation tools for deeper tracing.")
        print()
        print("High confidence:")
        print("1) All variable analyses (high confidence)")
        for k in HIGH_CONFIDENCE_VARIABLE_ANALYSIS_KEYS:
            name, _ = VARIABLE_ANALYSES[k]
            print(f"{k}) {name}")
        print("\nLow confidence:")
        for k in LOW_CONFIDENCE_VARIABLE_ANALYSIS_KEYS:
            name, _ = VARIABLE_ANALYSES[k]
            print(f"{k}) {name}")
        print("\nInvestigation tools:")
        print("22) Datatype usage analysis           Trace field-level usage for one variable name")
        print("23) Variable usage trace              Show fields and locations for one variable name")
        print("24) Module local variable analysis    Inspect field usage inside one module path")
        print("b) Back")
        print("q) Quit")

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()
        if c == "22":
            run_datatype_usage_analysis(cfg)
        elif c == "23":
            run_debug_variable_usage(cfg)
        elif c == "24":
            run_module_localvar_analysis(cfg)
        elif c in VARIABLE_ANALYSES:
            name, kinds = VARIABLE_ANALYSES[c]
            # kinds is either a set[IssueKind] or None at this point
            run_variable_analysis(cfg, kinds if isinstance(kinds, set | type(None)) else None)
        else:
            print("Invalid choice.")
            pause()


def module_analysis_submenu(cfg: dict):
    """Module analysis submenu."""
    while True:
        clear_screen()
        _print_menu(
            "Structure & modules",
            [
                MenuOption("1", "Compare module variants", "Compare matching module names across instances"),
                MenuOption("2", "Find module instances", "List where a module name appears in the target"),
                MenuOption("3", "Inspect module tree", "Print the module tree for debugging structure"),
                MenuOption("4", "Validate graphics rules", "Check configured graphics rules against loaded modules"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro="Use these tools when you need to inspect module layout, duplication, or structural drift.",
        )

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1":
            run_module_duplicates_analysis(cfg)
        elif c == "2":
            run_module_find_by_name(cfg)
        elif c == "3":
            run_module_tree_debug(cfg)
        elif c == "4":
            run_graphics_rules_validation(cfg)
        else:
            print("Invalid choice.")
            pause()


def interface_communication_submenu(cfg: dict):
    """Interface and communication analysis submenu."""
    while True:
        clear_screen()
        _print_menu(
            "Interfaces & communication",
            [
                MenuOption(
                    "1", "MMS interface variables", "Inventory MMSWriteVar or MMSReadVar usage and related checks"
                ),
                MenuOption("2", "Validate ICF paths", "Validate ICF entries against each program AST"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro="Check external interfaces and communication-related wiring for the current targets.",
        )

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1":
            run_mms_interface_analysis(cfg)
        elif c == "2":
            run_icf_validation(cfg)
        else:
            print("Invalid choice.")
            pause()


def code_quality_submenu(cfg: dict):
    """Code quality analysis submenu."""
    while True:
        clear_screen()
        _print_menu(
            "Code quality",
            [
                MenuOption("1", "Commented-out code", "Scan raw source comments for code-like content"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro="Use these checks for readability and maintainability issues rather than runtime semantics.",
        )

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1":
            run_comment_code_analysis(cfg)
        else:
            print("Invalid choice.")
            pause()


def analyzer_catalog_menu(cfg: dict):
    while True:
        clear_screen()
        analyzers = _get_enabled_analyzers()
        options = [
            MenuOption("1", "Run full analyzer suite", "Run every default analyzer in sequence"),
        ]
        options.extend(
            MenuOption(str(index), spec.name, spec.description) for index, spec in enumerate(analyzers, start=2)
        )
        options.extend([MenuOption("b", "Back"), MenuOption("q", "Quit")])
        _print_menu(
            "Analyzer catalog",
            options,
            intro=(
                "This view exposes the registry-backed analyzers directly. "
                "Only the default analyzer set is exposed here so low-confidence analyzers never run from the CLI suite."
            ),
        )

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1":
            _run_checks(cfg, None)
        elif c.isdigit():
            index = int(c) - 2
            if 0 <= index < len(analyzers):
                _run_checks(cfg, [analyzers[index].key])
            else:
                print("Invalid choice.")
                pause()
        else:
            print("Invalid choice.")
            pause()


def advanced_analysis_menu(cfg: dict):
    while True:
        clear_screen()
        _print_menu(
            "Advanced analysis & debug",
            [
                MenuOption("1", "Datatype usage analysis", "Trace field-level usage for a selected variable name"),
                MenuOption("2", "Variable usage trace", "Show fields and locations for a selected variable name"),
                MenuOption("3", "Module local variable analysis", "Inspect field usage inside one module path"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro="Use these tools when the summary reports are not specific enough and you need targeted tracing.",
        )

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1":
            run_datatype_usage_analysis(cfg)
        elif c == "2":
            run_debug_variable_usage(cfg)
        elif c == "3":
            run_module_localvar_analysis(cfg)
        else:
            print("Invalid choice.")
            pause()


def analysis_menu(cfg: dict):
    while True:
        clear_screen()
        _print_menu(
            "Analyze",
            [
                MenuOption("1", "Full analyzer suite", "Run every enabled registry-backed analyzer"),
                MenuOption("2", "Variable issues", "Focused variable reports and investigation tools"),
                MenuOption("3", "Structure & modules", "Inspect module layout, duplication, and tree structure"),
                MenuOption("4", "Interfaces & communication", "Check MMS mappings and validate ICF paths"),
                MenuOption("5", "Code quality", "Readability and maintainability checks"),
                MenuOption("6", "Analyzer catalog", "Choose one registry-backed analyzer by name"),
                MenuOption("7", "Advanced analysis & debug", "Targeted tracing for variables and module locals"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro=(
                "Run checks against the configured programs or libraries. "
                "Use the full analyzer suite for a broad pass, then drill into the focused menus if you need detail."
            ),
            note=_summarize_targets(cfg),
        )

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1":
            _run_checks(cfg, None)
        elif c == "2":
            variable_usage_submenu(cfg)
        elif c == "3":
            module_analysis_submenu(cfg)
        elif c == "4":
            interface_communication_submenu(cfg)
        elif c == "5":
            code_quality_submenu(cfg)
        elif c == "6":
            analyzer_catalog_menu(cfg)
        elif c == "7":
            advanced_analysis_menu(cfg)
        else:
            print("Invalid choice.")
            pause()


def run_module_duplicates_analysis(cfg: dict):
    print("\n--- Compare Module Variants ---")
    print("Enter module name(s) to compare (comma-separated):")
    raw_names = input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        print("❌ No module name provided")
        pause()
        return

    for target_name, project_bp, _graph in _iter_loaded_projects(cfg):
        print(f"\n=== Target: {target_name} ===")
        for module_name in module_names:
            try:
                matches = find_modules_by_name(project_bp, module_name, debug=cfg.get("debug", False))
                if not matches:
                    print(f"\n⚠ No modules found with name {module_name!r}.")
                    continue

                print(f"\nFound {len(matches)} instance(s) for {module_name!r}:")
                for idx, (path, module) in enumerate(matches, 1):
                    datecode = getattr(module, "datecode", None)
                    datecode_txt = f" (DateCode: {datecode})" if datecode else ""
                    print(f"  {idx}) {' -> '.join(path)}{datecode_txt}")

                print("\nSelect instances to compare (e.g., 6,7).")
                print("Press Enter to compare all instances.")
                selection = input("> ").strip()

                if selection:
                    indices = _parse_index_selection(selection, len(matches))
                    if len(indices) < 2:
                        print("⚠ Need at least two instances to compare; skipping.")
                        continue
                    selected = [matches[i - 1] for i in indices]
                    result = compare_modules(selected)
                else:
                    result = analyze_module_duplicates(project_bp, module_name, debug=cfg.get("debug", False))

                print("\n" + result.summary())
            except Exception as e:
                print(f"❌ Error during analysis for {module_name!r}: {e}")

    pause()


def run_module_find_by_name(cfg: dict):
    print("\n--- Find Module Instances ---")
    print("Enter module name(s) to search for (comma-separated):")
    raw_names = input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        print("❌ No module name provided")
        pause()
        return

    try:
        for target_name, project_bp, _graph in _iter_loaded_projects(cfg):
            print(f"\n=== Target: {target_name} ===")
            for module_name in module_names:
                matches = find_modules_by_name(project_bp, module_name, debug=cfg.get("debug", False))
                if not matches:
                    print(f"\nNo modules found with name {module_name!r}.")
                    continue
                print(f"\nFound {len(matches)} module instance(s) for {module_name!r}:")
                for path, module in matches:
                    datecode = getattr(module, "datecode", None)
                    datecode_txt = f" (DateCode: {datecode})" if datecode else ""
                    print(f"  - {' -> '.join(path)}{datecode_txt}")
    except Exception as e:
        print(f"❌ Error during search: {e}")

    pause()


def _parse_index_selection(selection: str, max_index: int) -> list[int]:
    """Parse a comma/whitespace-separated selection of indices and ranges."""
    tokens = [t.strip() for t in selection.replace(" ", ",").split(",") if t.strip()]
    indices: set[int] = set()

    for token in tokens:
        if "-" in token:
            parts = [p.strip() for p in token.split("-", 1)]
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                continue
            start = int(parts[0])
            end = int(parts[1])
            if start > end:
                start, end = end, start
            for i in range(start, end + 1):
                if 1 <= i <= max_index:
                    indices.add(i)
        else:
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= max_index:
                    indices.add(idx)

    return sorted(indices)


def run_module_tree_debug(cfg: dict):
    print("\n--- Debug Module Tree Structure ---")
    max_depth_txt = prompt("Max depth", "10")
    try:
        max_depth = int(max_depth_txt)
    except ValueError:
        print("❌ Invalid depth; using default 10")
        max_depth = 10

    try:
        for target_name, project_bp, _graph in _iter_loaded_projects(cfg):
            print(f"\n=== Target: {target_name} ===")
            debug_module_structure(project_bp, max_depth=max_depth)
    except Exception as e:
        print(f"❌ Error during debug: {e}")

    pause()


def run_analysis_menu(cfg: dict):
    analysis_menu(cfg)


def variable_analysis_menu(cfg: dict):
    analysis_menu(cfg)


def run_module_localvar_analysis(cfg: dict):
    """Interactive module local variable analysis."""
    print("\n--- Module Local Variable Analysis ---")
    print("Enter the module path (strict) relative to BasePicture.")
    print("Example: StartMaster.KaHA251A")
    default_bp, _default_graph = load_project(cfg)
    module_path = input(f"{default_bp.header.name}.").strip()

    if not module_path:
        print("❌ No module path provided")
        pause()
        return

    print("Enter the local variable name (e.g., Dv):")
    var_name = input("> ").strip()

    if not var_name:
        print("❌ No variable name provided")
        pause()
        return

    from .analyzers.variable_usage_reporting import analyze_module_localvar_fields

    for target_name, project_bp, _graph in _iter_loaded_projects(cfg):
        try:
            report = analyze_module_localvar_fields(
                project_bp,
                module_path,
                var_name,
                debug=cfg.get("debug", False),
            )
            print(f"\n=== Target: {target_name} ===")
            print(report)
        except Exception as e:
            print(f"❌ Error during analysis for {target_name}: {e}")

    pause()


def _get_enabled_analyzers():
    return get_default_cli_analyzers()


def _run_checks(cfg: dict, selected_keys: list[str] | None) -> None:
    analyzers = _get_enabled_analyzers()
    if selected_keys:
        selected = {key.casefold() for key in selected_keys}
        analyzers = [spec for spec in analyzers if spec.key.casefold() in selected]

    if not analyzers:
        print("❌ No matching checks found")
        pause()
        return

    print("\n--- Running checks ---")
    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        context = AnalysisContext(
            base_picture=project_bp,
            graph=graph,
            debug=cfg.get("debug", False),
            target_is_library=_target_is_library(cfg, project_bp, graph),
            config=cfg,
        )
        print(f"\n=== Target: {target_name} ===")
        for spec in analyzers:
            print(f"\n=== {spec.name} ({spec.key}) ===")
            report = spec.run(context)
            report = apply_rule_profile_to_report(spec.key, report, cfg)
            print(report.summary())

    pause()


def run_checks_menu(cfg: dict):
    _run_checks(cfg, None)


def run_mms_interface_analysis(cfg: dict):
    """Summarize MMS interface mappings and related OPC or MES validation issues."""
    print("\n--- MMS Interface Variables ---")

    for target_name, project_bp, _graph in _iter_loaded_projects(cfg):
        try:
            report = analyze_mms_interface_variables(
                project_bp,
                debug=cfg.get("debug", False),
                config=cfg,
            )
            print(f"\n=== Target: {target_name} ===")
            print(report.summary())
        except Exception as e:
            print(f"❌ Error during analysis for {target_name}: {e}")

    pause()


def run_icf_validation(cfg: dict):
    """Validate ICF paths against per-program ASTs (non-recursive, report-only)."""
    icf_dir_raw = cfg.get("icf_dir", "")
    if not icf_dir_raw:
        print("❌ icf_dir is not set in the config. Set it before running ICF validation.")
        pause()
        return

    icf_dir = Path(icf_dir_raw)
    if not icf_dir.exists() or not icf_dir.is_dir():
        print(f"❌ icf_dir does not exist or is not a directory: {icf_dir}")
        pause()
        return

    icf_files = sorted(p for p in icf_dir.iterdir() if p.is_file() and p.suffix.lower() == ".icf")
    if not icf_files:
        print(f"⚠ No .icf files found in {icf_dir}")
        pause()
        return

    total_entries = 0
    total_valid = 0
    total_invalid = 0
    total_skipped = 0
    files_failed = 0

    print("\n--- ICF Validation (per program) ---")

    for icf_file in icf_files:
        program_name = icf_file.stem
        entries = parse_icf_file(icf_file)
        if not entries:
            print(f"⚠ {icf_file.name}: no entries found")
            continue

        try:
            program_bp, graph = load_program_ast(cfg, program_name)
            program_bp = engine_module.merge_project_basepicture(program_bp, graph)
        except Exception as e:
            print(f"❌ {icf_file.name}: failed to load program {program_name!r}: {e}")
            files_failed += 1
            continue

        moduletype_index: dict[str, list[engine_module.ModuleTypeDef]] = {}
        for bp in graph.ast_by_name.values():
            for mt in bp.moduletype_defs or []:
                key = mt.name.casefold()
                moduletype_index.setdefault(key, []).append(mt)

        report = validate_icf_entries_against_program(
            program_bp,
            entries,
            expected_program=program_name,
            debug=cfg.get("debug", False),
            moduletype_index=moduletype_index,
        )
        print(report.summary())
        print("")

        total_entries += report.total_entries
        total_valid += report.valid_entries
        total_invalid += len(report.issues)
        total_skipped += report.skipped_entries

    print("Summary:")
    print(f"  Files processed: {len(icf_files)}")
    print(f"  Files failed: {files_failed}")
    print(f"  Entries: {total_entries}")
    print(f"  Valid: {total_valid}")
    print(f"  Invalid: {total_invalid}")
    print(f"  Skipped: {total_skipped}")

    pause()


def run_debug_variable_usage(cfg: dict):
    """Interactive debug for specific variable usage."""
    print("\n--- Variable Usage (Fields + Locations) ---")
    print("Enter the variable name to analyze:")
    var_name = input("> ").strip()

    if not var_name:
        print("❌ No variable name provided")
        pause()
        return

    for target_name, project_bp, _graph in _iter_loaded_projects(cfg):
        try:
            report = debug_variable_usage(project_bp, var_name, debug=cfg.get("debug", False))
            print(f"\n=== Target: {target_name} ===")
            print(report)
        except Exception as e:
            print(f"❌ Error during debug for {target_name}: {e}")

    pause()


def run_comment_code_analysis(cfg: dict):
    """Scan raw source files for code-like content inside comments."""
    print("\n--- Commented-out Code ---")
    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        paths = _source_paths_for_current_target(project_bp, graph)
        report = analyze_comment_code_files(paths, project_bp.header.name)
        print(f"\n=== Target: {target_name} ===")
        print(report.summary())
    pause()


def run_advanced_datatype_analysis(cfg: dict):
    """Enhanced datatype analysis with filtering options."""
    print("\n--- Advanced Datatype Analysis ---")
    print("1) Analyze variable by name (field-level usage)")
    print("2) Compare module variants by name")
    print("3) Debug specific variable usage")
    print("b) Back")

    choice = input("> ").strip()

    if choice == "1":
        var_name = input("Enter variable name: ").strip()
        if var_name:
            for target_name, project_bp, graph in _iter_loaded_projects(cfg):
                report = variables_reporting_module.analyze_datatype_usage(
                    project_bp,
                    var_name,
                    debug=cfg.get("debug", False),
                    unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
                )
                print(f"\n=== Target: {target_name} ===")
                print(report)

    elif choice == "2":
        module_name = input("Enter module name to compare: ").strip()
        if module_name:
            print("⚠ Module comparison analysis not yet implemented")

    elif choice == "3":
        var_name = input("Enter variable name to debug: ").strip()
        if var_name:
            for target_name, project_bp, _graph in _iter_loaded_projects(cfg):
                report = variables_reporting_module.debug_variable_usage(
                    project_bp,
                    var_name,
                    debug=cfg.get("debug", False),
                )
                print(f"\n=== Target: {target_name} ===")
                print(report)

    pause()


def dump_menu(cfg: dict):
    while True:
        clear_screen()
        _print_menu(
            "Diagnostics & dumps",
            [
                MenuOption("1", "Dump parse tree", "Write the parser tree for each loaded target"),
                MenuOption("2", "Dump AST", "Write the merged AST for each loaded target"),
                MenuOption("3", "Dump dependency graph", "Write dependency graph output for each loaded target"),
                MenuOption(
                    "4", "Print variable report", "Print the full variable summary without entering the variable menu"
                ),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro="Use these tools when you need raw diagnostics or want to inspect parser and dependency artifacts.",
        )
        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1" and confirm("Dump parse tree?"):
            for _target_name, project_bp, graph in _iter_loaded_projects(cfg):
                engine_module.dump_parse_tree((project_bp, graph))
        elif c == "2" and confirm("Dump AST?"):
            for _target_name, project_bp, graph in _iter_loaded_projects(cfg):
                engine_module.dump_ast((project_bp, graph))
        elif c == "3" and confirm("Dump dependency graph?"):
            for _target_name, project_bp, graph in _iter_loaded_projects(cfg):
                engine_module.dump_dependency_graph((project_bp, graph))
        elif c == "4" and confirm("Dump variable report?"):
            for target_name, project_bp, graph in _iter_loaded_projects(cfg):
                print(f"\n=== Target: {target_name} ===")
                print(
                    analyze_variables(
                        project_bp,
                        debug=cfg.get("debug", False),
                        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
                        config=cfg,
                    ).summary()
                )
        else:
            print("Invalid choice.")


# ----------------------------
# Config submenu
# ----------------------------


def config_menu(cfg: dict) -> bool:
    dirty = False
    while True:
        clear_screen()
        show_config(cfg)
        _print_menu(
            "Setup",
            [
                MenuOption("1", "Add analysis target", "Add a program or library name without file extension"),
                MenuOption("2", "Remove analysis target", "Remove one configured analysis target"),
                MenuOption("3", "Toggle mode", "Switch between official and draft file mode"),
                MenuOption("4", "Toggle scan_root_only", "Restrict dependency scanning to the root directory"),
                MenuOption("5", "Toggle fast_cache_validation", "Use faster but lighter AST cache checks"),
                MenuOption("6", "Change program_dir", "Set the main SattLine program directory"),
                MenuOption("7", "Change ABB_lib_dir", "Set the ABB or shared library directory"),
                MenuOption("8", "Edit other_lib_dirs", "Add or remove additional library directories"),
                MenuOption("9", "Save configuration", "Write the current configuration to disk"),
                MenuOption("10", "Change icf_dir", "Set the directory used for ICF validation"),
                MenuOption("11", "Toggle debug", "Show extra debugging output while running"),
                MenuOption("12", "Edit graphics rules", "Manage the JSON graphics rules used by the graphics check"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro=(
                "Setup controls what SattLint loads and analyzes. "
                "Start here on first run, then save and use Tools -> Self-check diagnostics to confirm the paths."
            ),
        )
        c = input("> ").strip().lower()

        if c == "b":
            return dirty
        if c == "q":
            if dirty and confirm("Unsaved config changes. Save before quitting?"):
                save_config(CONFIG_PATH, cfg)
            quit_app()
            sys.exit(0)

        elif c == "1":
            new = prompt("Program/library name to add")
            if not target_exists(new, cfg):
                print("❌ Target not found in configured directories")
                pause()
            elif any(str(existing).casefold() == new.casefold() for existing in cfg["analyzed_programs_and_libraries"]):
                print("⚠ Target already listed")
                pause()
            elif confirm(f"Add '{new}' to analyzed_programs_and_libraries?"):
                cfg["analyzed_programs_and_libraries"].append(new)
                dirty = True

        elif c == "2":
            targets = cfg["analyzed_programs_and_libraries"]
            if not targets:
                print("⚠ No analyzed targets configured")
                pause()
                continue

            print("\nCurrent analyzed_programs_and_libraries:")
            for i, target in enumerate(targets, 1):
                print(f"{i}. {target}")

            idx_txt = prompt("Index to remove")
            try:
                idx = int(idx_txt) - 1
            except ValueError:
                print("❌ Invalid index")
                pause()
                continue

            if 0 <= idx < len(targets) and confirm(f"Remove '{targets[idx]}' from analyzed_programs_and_libraries?"):
                targets.pop(idx)
                dirty = True

        elif c == "3":
            new = "draft" if cfg["mode"] == "official" else "official"
            if confirm(f"Switch mode to '{new}'?"):
                cfg["mode"] = new
                dirty = True

        elif c == "4":
            if confirm("Toggle scan_root_only?"):
                cfg["scan_root_only"] = not cfg["scan_root_only"]
                dirty = True

        elif c == "5":
            if confirm("Toggle fast_cache_validation?"):
                cfg["fast_cache_validation"] = not cfg["fast_cache_validation"]
                dirty = True

        elif c == "6":
            new = prompt("New program_dir", cfg["program_dir"])
            if confirm("Change program_dir?"):
                cfg["program_dir"] = new
                dirty = True

        elif c == "7":
            new = prompt("New ABB_lib_dir", cfg["ABB_lib_dir"])
            if confirm("Change ABB_lib_dir?"):
                cfg["ABB_lib_dir"] = new
                dirty = True

        elif c == "8":
            libs = cfg["other_lib_dirs"]
            print("\nCurrent other_lib_dirs:")
            for i, p in enumerate(libs, 1):
                print(f"{i}. {p}")
            if confirm("Add new entry?"):
                libs.append(prompt("Path"))
                dirty = True
            elif confirm("Remove entry?"):
                idx = int(prompt("Index")) - 1
                if 0 <= idx < len(libs):
                    libs.pop(idx)
                    dirty = True
        elif c == "9":
            if confirm("Save config to disk?"):
                save_config(CONFIG_PATH, cfg)
                dirty = False
        elif c == "10":
            new = prompt("New ICF_dir", cfg["icf_dir"])
            if confirm("Change ICF_dir?"):
                cfg["icf_dir"] = new
                dirty = True
        elif c == "11":
            if confirm("Toggle debug?"):
                cfg["debug"] = not cfg["debug"]
                apply_debug(cfg)
                dirty = True
        elif c == "12":
            graphics_rules_menu(cfg)
        else:
            print("Invalid choice.", flush=True)
            pause()


def tools_menu(cfg: dict) -> None:
    while True:
        clear_screen()
        _print_menu(
            "Tools",
            [
                MenuOption("1", "Self-check diagnostics", "Verify configuration and path setup"),
                MenuOption("2", "Diagnostics & dumps", "Inspect parser, AST, and dependency output"),
                MenuOption("3", "Refresh cached ASTs", "Rebuild cached ASTs when results look stale"),
                MenuOption("b", "Back"),
                MenuOption("q", "Quit"),
            ],
            intro=(
                "These tools are mainly for setup validation and troubleshooting. "
                "Most users only need them when paths change or results look stale."
            ),
        )

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1":
            clear_screen()
            self_check(cfg)
            pause()
        elif c == "2":
            if _require_targets_for_menu_action(cfg, "using diagnostics and dumps"):
                dump_menu(cfg)
        elif c == "3":
            if _require_targets_for_menu_action(cfg, "refreshing cached ASTs") and confirm("Force refresh cached AST?"):
                force_refresh_ast(cfg)
                print("? AST cache refreshed")
                pause()
        else:
            print("Invalid choice.")
            pause()


# ----------------------------
# Main loop
# ----------------------------
def main(argv: list[str] | None = None) -> int:
    cli_args = [] if argv is None else argv
    if cli_args:
        return run_cli(cli_args)

    try:
        cfg, default_used = load_config(CONFIG_PATH)
        apply_debug(cfg)
        if default_used:
            print("⚠ Default config created. Open Setup before running analysis.")
            pause()
        else:
            if not self_check(cfg) and not confirm("Self-check failed. Continue?"):
                return 0
            if _has_analyzed_targets(cfg):
                ensure_ast_cache(cfg)
        dirty = False

        while True:
            clear_screen()
            _print_menu(
                "SattLint",
                [
                    MenuOption("1", "Analyze", "Run checks and reports for configured targets"),
                    MenuOption("2", "Documentation", "Preview unit scope and generate DOCX output"),
                    MenuOption("3", "Setup", "Configure directories, targets, mode, and cache settings"),
                    MenuOption("4", "Tools", "Diagnostics, dumps, and cache refresh"),
                    MenuOption("5", "Help", "First-time guidance and workflow explanations"),
                    MenuOption("q", "Quit"),
                ],
                intro=(
                    "Analyze SattLine targets, generate documentation, and troubleshoot parser state from one place. "
                    "Start with Setup on first run."
                ),
                note=(
                    _summarize_targets(cfg) + "\nChanges are not saved until you choose Save configuration in Setup."
                ),
            )
            c = input("> ").strip().lower()

            if c == "1":
                if _require_targets_for_menu_action(cfg, "running analyses"):
                    analysis_menu(cfg)

            elif c == "2":
                if _require_targets_for_menu_action(cfg, "using documentation tools"):
                    dirty |= documentation_menu(cfg)

            elif c == "3":
                dirty |= config_menu(cfg)

            elif c == "4":
                tools_menu(cfg)

            elif c == "5":
                show_help(cfg)

            elif c == "q":
                if dirty and confirm("Unsaved config changes. Save before quitting?"):
                    save_config(CONFIG_PATH, cfg)
                quit_app()

            else:
                print("Invalid choice.", flush=True)
    except QuitAppError:
        return 0


def cli() -> int:
    return main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(cli())
