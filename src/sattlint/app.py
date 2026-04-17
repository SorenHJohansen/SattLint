#!/usr/bin/env python3
"""CLI entry points and interactive helpers for SattLint."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess  # nosec B404 - clear_screen uses a fixed local command list
import sys
from typing import Iterator, cast
from . import engine as engine_module
from . import config as config_module
from .analyzers.variables import (
    IssueKind,
    filter_variable_report,
    analyze_variables,
)
from .analyzers.shadowing import analyze_shadowing
from .analyzers.variable_usage_reporting import (
    debug_variable_usage,
)
from .analyzers.mms import analyze_mms_interface_variables
from .analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from .analyzers.framework import AnalysisContext
from .analyzers.registry import get_default_analyzers
from .analyzers import variable_usage_reporting as variables_reporting_module
from .analyzers.comment_code import analyze_comment_code_files
from .reporting.variables_report import VariablesReport
from .analyzers.modules import (
    debug_module_structure,
    analyze_module_duplicates,
    find_modules_by_name,
    compare_modules,
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

VARIABLE_ANALYSES = {
    "1": ("All variable analyses", None),
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
}


CONFIG_PATH = config_module.get_config_path()
DEFAULT_CONFIG = config_module.DEFAULT_CONFIG
_DOCUMENTATION_SCOPE_STATE = {
    "mode": "all",
    "instance_paths": [],
    "moduletype_names": [],
}


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
            lines.append(
                f"Transitive dependency failures ({len(transitive_failures)}):"
            )
            lines.extend(
                f"  - {self._format_missing_item(item)}" for item in transitive_failures
            )

        if transitive_warnings:
            lines.append(
                f"Transitive dependency warnings ({len(transitive_warnings)}):"
            )
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
        if (warning_name := _extract_warning_name(item)) is None
        or warning_name.casefold() == target_name.casefold()
    ]


def load_config(path: Path):
    return config_module.load_config(path)


def save_config(path: Path, cfg: dict) -> None:
    config_module.save_config(path, cfg)
    print("Config saved")


def self_check(cfg: dict) -> bool:
    return config_module.self_check(cfg)


# Configure root logger so all debug messages are shown
logging.basicConfig(format="%(message)s", level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

log = logging.getLogger("SattLint")


# ----------------------------
# Helpers
# ----------------------------
def clear_screen():
    if not sys.stdout.isatty():
        return

    if os.name == "nt":
        try:
            if os.system("cls") == 0:  # nosec B605 - fixed local console clear command
                return
        except OSError:
            pass
        clear_command = None
    else:
        clear_executable = shutil.which("clear")
        clear_command = [clear_executable] if clear_executable else None

    if clear_command is not None:
        try:
            completed = subprocess.run(  # nosec B603 - clear_screen only executes fixed local commands
                clear_command,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if completed.returncode == 0:
                return
        except OSError:
            pass

    try:
        print("\033[2J\033[H", end="", flush=True)
    except OSError:
        pass


def pause():
    input("\nPress Enter to continue...")


class QuitApp(Exception):
    pass


def quit_app() -> None:
    clear_screen()
    raise QuitApp()


def confirm(msg: str) -> bool:
    return input(f"{msg} [y/N]: ").strip().lower() in ("y", "yes")


def prompt(msg: str, default: str | None = None) -> str:
    if default is not None:
        return input(f"{msg} [{default}]: ").strip() or default
    return input(f"{msg}: ").strip()


def target_exists(target: str, cfg: dict) -> bool:
    return config_module.target_exists(target, cfg)


def apply_debug(cfg: dict):
    log.setLevel(logging.DEBUG if cfg.get("debug") else logging.INFO)


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


def run_syntax_check_command(file_path: str) -> int:
    target_path = Path(file_path)
    if not target_path.exists() or not target_path.is_file():
        print(f"ERROR [io] {target_path}: File not found", file=sys.stderr)
        return 1

    result = engine_module.validate_single_file_syntax(target_path)
    if result.ok:
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


def show_config(cfg: dict):
    documentation_cfg = config_module.get_documentation_config(cfg)

    print("\n--- Current configuration ---")
    print("analyzed_programs_and_libraries:")
    for i, target in enumerate(cfg["analyzed_programs_and_libraries"], 1):
        print(f"  {i}. {target}")
    for k in (
        "mode",
        "scan_root_only",
        "fast_cache_validation",
        "debug",
        "program_dir",
        "ABB_lib_dir",
        "icf_dir",
    ):
        print(f"{k:16}: {cfg[k]}")
    print("other_lib_dirs:")
    for i, p in enumerate(cfg["other_lib_dirs"], 1):
        print(f"  {i}. {p}")
    print("documentation.classifications:")
    for category, rule in documentation_cfg.get("classifications", {}).items():
        print(f"  {category}:")
        for key, values in rule.items():
            if values:
                print(f"    {key}: {', '.join(str(value) for value in values)}")
    print("-----------------------------\n")


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
            "No analyzed programs/libraries configured. "
            "Add entries to 'analyzed_programs_and_libraries' first."
        )
    return targets


def _has_analyzed_targets(cfg: dict) -> bool:
    return bool(_get_analyzed_targets(cfg))


def _require_targets_for_menu_action(cfg: dict, action: str) -> bool:
    if _has_analyzed_targets(cfg):
        return True
    print(
        "\nNo analyzed programs/libraries configured. "
        f"Add entries in Edit config before {action}."
    )
    pause()
    return False


def _cache_key_for_target(cfg: dict, target_name: str) -> str:
    cache_cfg = cfg.copy()
    cache_cfg["analysis_target"] = target_name
    return compute_cache_key(cache_cfg)


def _split_csv_values(raw: str) -> list[str]:
    return [value.strip() for value in raw.split(",") if value.strip()]


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
            print(
                f"Selected units for {target_name}: "
                + ", ".join(entry.short_path for entry in scope.roots)
            )
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
        print("""
--- Documentation ---
1) Generate documentation
2) Preview detected unit candidates
3) Scope all units
4) Scope by unit moduletype name(s)
5) Scope by unit instance path(s)
b) Back
q) Quit
""")
        print(
            "Current scope: "
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
        matches = {
            path for path in source_files if path.name.casefold() == origin_file.casefold()
        }
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
    return all(
        not engine_module._is_within_directory(path, program_path)
        for path in source_paths
    )


def load_project(
    cfg: dict,
    target_name: str | None = None,
    *,
    use_cache: bool = True,
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
        raise RuntimeError(
            f"Program '{program_name}' not parsed. Resolved: {list(graph.ast_by_name.keys())}"
        )

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
        result = load_project(cfg, target_name=target_name, use_cache=False)
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
                print(
                    "⚠ AST cache missing file manifest; rebuilding (this may take a while)..."
                )
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
            include_empty_sections = (
                include_empty_sections or report.include_empty_sections
            )

        return VariablesReport(
            basepicture_name=basepicture_name,
            issues=issues,
            visible_kinds=frozenset(visible_kinds) if visible_kinds else None,
            include_empty_sections=include_empty_sections,
        )

    produced_output = False
    for target_name, project_bp, graph in _iter_loaded_projects(cfg):
        produced_output = True
        target_is_library = _target_is_library(cfg, project_bp, graph)
        report = analyze_variables(
            project_bp,
            debug=cfg.get("debug", False),
            unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
            analyzed_target_is_library=target_is_library,
        )

        include_shadowing = kinds is None or IssueKind.SHADOWING in kinds
        standard_kinds = None if kinds is None else kinds - {IssueKind.SHADOWING}

        if standard_kinds is not None:
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
            if kinds == {IssueKind.SHADOWING}:
                report = shadowing_report
            elif kinds is None or standard_kinds:
                report = _merge_reports(report, shadowing_report)

        print(f"\n=== Target: {target_name} ===")
        _print_validation_warnings(
            _target_validation_warnings(target_name, getattr(graph, "warnings", []))
        )
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
        print("\n--- Variable Usage Analysis ---")
        print("Quick reports:")
        for k, (name, _) in VARIABLE_ANALYSES.items():
            print(f"{k}) {name}")
        print("\nDetailed analysis:")
        print("14) Datatype usage analysis (by variable name)")
        print("15) Variable usage (fields + locations)")
        print("16) Module local variable field analysis")
        print("b) Back")
        print("q) Quit")

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "14":
            run_datatype_usage_analysis(cfg)
        elif c == "15":
            run_debug_variable_usage(cfg)
        elif c == "16":
            run_module_localvar_analysis(cfg)
        elif c in VARIABLE_ANALYSES:
            name, kinds = VARIABLE_ANALYSES[c]
            # kinds is either a set[IssueKind] or None at this point
            run_variable_analysis(
                cfg, kinds if isinstance(kinds, (set, type(None))) else None
            )
        else:
            print("Invalid choice.")
            pause()


def module_analysis_submenu(cfg: dict):
    """Module analysis submenu."""
    while True:
        clear_screen()
        print("\n--- Module Analysis ---")
        print("1) Compare module variants by name")
        print("2) List module instances by name")
        print("3) Debug module tree structure")
        print("b) Back")
        print("q) Quit")

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
        else:
            print("Invalid choice.")
            pause()


def interface_communication_submenu(cfg: dict):
    """Interface and communication analysis submenu."""
    while True:
        clear_screen()
        print("\n--- Interface & Communication ---")
        print("1) MMS interface variables (WriteData/Outputvariable)")
        print("2) Validate ICF paths (per program)")
        print("b) Back")
        print("q) Quit")

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
        print("\n--- Code Quality ---")
        print("1) Commented-out code in comments")
        print("b) Back")
        print("q) Quit")

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


def analysis_menu(cfg: dict):
    while True:
        clear_screen()
        print("\n--- Analyses ---")
        print("1) Variable Usage Analysis")
        print("2) Module Analysis")
        print("3) Interface & Communication")
        print("4) Code Quality")
        print("f) Force refresh cached AST")
        print("b) Back")
        print("q) Quit")

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "1":
            variable_usage_submenu(cfg)
        elif c == "2":
            module_analysis_submenu(cfg)
        elif c == "3":
            interface_communication_submenu(cfg)
        elif c == "4":
            code_quality_submenu(cfg)
        elif c == "f":
            if confirm("Force refresh cached AST?"):
                force_refresh_ast(cfg)
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
                matches = find_modules_by_name(
                    project_bp, module_name, debug=cfg.get("debug", False)
                )
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
                    result = analyze_module_duplicates(
                        project_bp, module_name, debug=cfg.get("debug", False)
                    )

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
                matches = find_modules_by_name(
                    project_bp, module_name, debug=cfg.get("debug", False)
                )
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
    return [spec for spec in get_default_analyzers() if spec.enabled]


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
        )
        print(f"\n=== Target: {target_name} ===")
        for spec in analyzers:
            print(f"\n=== {spec.name} ({spec.key}) ===")
            report = spec.run(context)
            print(report.summary())

    pause()


def run_checks_menu(cfg: dict):
    _run_checks(cfg, None)


def run_mms_interface_analysis(cfg: dict):
    """List variables mapped into MMSWriteVar/MMSReadVar interface modules."""
    print("\n--- MMS Interface Variables ---")

    for target_name, project_bp, _graph in _iter_loaded_projects(cfg):
        try:
            report = analyze_mms_interface_variables(
                project_bp,
                debug=cfg.get("debug", False),
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
        print(
            "❌ icf_dir is not set in the config. Set it before running ICF validation."
        )
        pause()
        return

    icf_dir = Path(icf_dir_raw)
    if not icf_dir.exists() or not icf_dir.is_dir():
        print(f"❌ icf_dir does not exist or is not a directory: {icf_dir}")
        pause()
        return

    icf_files = sorted(
        p for p in icf_dir.iterdir() if p.is_file() and p.suffix.lower() == ".icf"
    )
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
            report = debug_variable_usage(
                project_bp, var_name, debug=cfg.get("debug", False)
            )
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
        print("""
--- Dump outputs ---
1) Dump parse tree
2) Dump AST
3) Dump dependency graph
4) Dump variable report
b) Back
q) Quit
""")
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
                        unavailable_libraries=getattr(
                            graph, "unavailable_libraries", set()
                        ),
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
        print("""
1) Add analyzed program/library
2) Remove analyzed program/library
3) Toggle Mode (official/draft)
4) Toggle scan_root_only
5) Toggle fast_cache_validation
6) Change Program_dir
7) Change ABB_lib_dir
8) Add/remove other_lib_dirs
9) Save config
10) Change ICF_dir
11) Toggle debug
b) Back
q) Quit
""")
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
            elif any(
                str(existing).casefold() == new.casefold()
                for existing in cfg["analyzed_programs_and_libraries"]
            ):
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

            if 0 <= idx < len(targets) and confirm(
                f"Remove '{targets[idx]}' from analyzed_programs_and_libraries?"
            ):
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
                dirty = True
        else:
            print("Invalid choice.")


# ----------------------------
# Main loop
# ----------------------------
def main(argv: list[str] | None = None) -> int:
    cli_args = [] if argv is None else argv
    if cli_args:
        return run_cli(cli_args)

    try:
        cfg, default_used = load_config(CONFIG_PATH)
        if default_used:
            print(
                "⚠ Default config created. Please edit configuration before running analysis."
            )
            pause()
        else:
            if not self_check(cfg):
                if not confirm("Self-check failed. Continue?"):
                    return 0
            if _has_analyzed_targets(cfg):
                ensure_ast_cache(cfg)
        dirty = False

        while True:
            clear_screen()
            print("""
How to use SattLint
------------------
• Navigate using the number keys shown in each menu
• Press Enter to confirm a selection
• Changes are NOT saved until you choose "Save config"
• Use "Analyses" to analyze the configured programs/libraries
• Use "Dump outputs" to inspect parse trees, ASTs, etc.
• Use "Documentation" to generate FS-style DOCX output and control unit scope
• Use "Edit config" to change settings
• Use "Self-check" to check if the config is OK
• Press 'q' at any time in the main menu to quit

=== SattLint ===
1) Analyses
2) Dump outputs
3) Documentation
4) Edit config
5) Self-check diagnostics
6) Force refresh cached AST
q) Quit
""")
            c = input("> ").strip().lower()

            if c == "1":
                if _require_targets_for_menu_action(cfg, "running analyses"):
                    analysis_menu(cfg)

            elif c == "2":
                if _require_targets_for_menu_action(cfg, "dumping outputs"):
                    dump_menu(cfg)

            elif c == "3":
                if _require_targets_for_menu_action(cfg, "using documentation tools"):
                    dirty |= documentation_menu(cfg)

            elif c == "4":
                dirty |= config_menu(cfg)

            elif c == "5":
                clear_screen()
                self_check(cfg)
                pause()

            elif c == "6":
                if _require_targets_for_menu_action(cfg, "refreshing cached ASTs"):
                    if confirm("Force refresh cached AST?"):
                        force_refresh_ast(cfg)
                        print("✔ AST cache refreshed")
                        pause()

            elif c == "q":
                if dirty and confirm("Unsaved config changes. Save before quitting?"):
                    save_config(CONFIG_PATH, cfg)
                quit_app()

            else:
                print("Invalid choice.")
    except QuitApp:
        return 0


def cli() -> int:
    return main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(cli())
