#!/usr/bin/env python3
"""CLI entry points and interactive helpers for SattLint."""
from __future__ import annotations

import logging
from pathlib import Path
import os
import sys
from . import engine as engine_module
from . import config as config_module
from .analyzers.variables import (
    IssueKind,
    filter_variable_report,
    analyze_variables,
)
from .analyzers.variable_usage_reporting import (
    debug_variable_usage,
    analyze_datatype_usage,
)
from .analyzers.mms import analyze_mms_interface_variables
from .analyzers.icf import parse_icf_file, validate_icf_entries_against_program
from .analyzers.framework import AnalysisContext
from .analyzers.registry import get_default_analyzers
from .analyzers import variables as variables_module
from .analyzers import variable_usage_reporting as variables_reporting_module
from .analyzers.comment_code import analyze_comment_code_files
from .analyzers.modules import (
    debug_module_structure,
    analyze_module_duplicates,
    find_modules_by_name,
    compare_modules,
)
from .cache import ASTCache, compute_cache_key
from .engine import GRAMMAR_PATH

VARIABLE_ANALYSES = {
    "1": ("All variable analyses", None),
    "2": ("Unused variables", {IssueKind.UNUSED}),
    "3": ("Read-only but not CONST", {IssueKind.READ_ONLY_NON_CONST}),
    "4": ("Written but never read", {IssueKind.NEVER_READ}),
    "5": ("String mapping type mismatches", {IssueKind.STRING_MAPPING_MISMATCH}),
    "6": ("Duplicated complex datatypes", {IssueKind.DATATYPE_DUPLICATION}),
    "7": ("Min/Max mapping name mismatches", {IssueKind.MIN_MAX_MAPPING_MISMATCH}),
}


CONFIG_PATH = config_module.get_config_path()
DEFAULT_CONFIG = config_module.DEFAULT_CONFIG


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

log = logging.getLogger("sattlint")


# ----------------------------
# Helpers
# ----------------------------
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


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


def root_exists(root: str, cfg: dict) -> bool:
    return config_module.root_exists(root, cfg)


def apply_debug(cfg: dict):
    log.setLevel(logging.DEBUG if cfg.get("debug") else logging.INFO)


# ----------------------------
# Display
# ----------------------------


def show_config(cfg: dict):
    print("\n--- Current configuration ---")
    for k in (
        "root",
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
    print("-----------------------------\n")


# ----------------------------
# Analysis & dumps
# ----------------------------
def load_project(cfg: dict, *, use_cache: bool = True):
    cache_dir = CONFIG_PATH.parent / "cache"
    cache = ASTCache(cache_dir)

    key = compute_cache_key(cfg)  # now only hashes config, not files
    cached = cache.load(key) if use_cache else None

    if cached:
        log.debug("✔ Using cached AST (not revalidated)")
        return cached["project"]

    loader = engine_module.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(p) for p in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine_module.CodeMode(cfg["mode"]),
        scan_root_only=cfg["scan_root_only"],
        debug=cfg["debug"],
    )

    graph = loader.resolve(cfg["root"], strict=False)

    root_bp = graph.ast_by_name.get(cfg["root"])
    if not root_bp:
        raise RuntimeError(
            f"Root program '{cfg['root']}' not parsed.\n"
            f"Resolved: {list(graph.ast_by_name.keys())}\n"
            f"Missing: {graph.missing}"
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
    """Clear cached AST for current config and rebuild it."""
    cache_dir = CONFIG_PATH.parent / "cache"
    cache = ASTCache(cache_dir)
    key = compute_cache_key(cfg)
    cache.clear(key)
    log.debug("✔ AST cache cleared")
    return load_project(cfg, use_cache=False)


def ensure_ast_cache(cfg: dict) -> bool:
    """Check AST cache validity and rebuild if needed with user feedback."""
    print("\n⏳ Checking AST cache...")
    cache_dir = CONFIG_PATH.parent / "cache"
    cache = ASTCache(cache_dir)
    key = compute_cache_key(cfg)
    cached = cache.load(key)

    fast = cfg.get("fast_cache_validation", False)
    if cached:
        has_manifest = bool(cached.get("files"))
        if fast and has_manifest:
            is_valid = cache.validate(cached, fast=False)
        else:
            is_valid = cache.validate(cached, fast=fast)
        if is_valid:
            print("✔ AST cache OK")
            return True

        if has_manifest:
            print("⚠ AST cache stale; rebuilding (this may take a while)...")
        else:
            print("⚠ AST cache missing file manifest; rebuilding (this may take a while)...")
    else:
        print("⚠ AST cache missing; building (this may take a while)...")

    try:
        load_project(cfg, use_cache=False)
        print("✔ AST cache updated")
        return True
    except Exception as exc:
        print(f"❌ Failed to build AST cache: {exc}")
        return False


def run_variable_analysis(cfg: dict, kinds: set[IssueKind] | None):
    project_bp, graph = load_project(cfg)

    report = analyze_variables(
        project_bp,
        debug=cfg.get("debug", False),
        unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
    )

    if kinds is not None:
        report = filter_variable_report(report, kinds)

    print(report.summary())
    pause()


def run_datatype_usage_analysis(cfg: dict):
    """Interactive datatype usage analysis (field-level usage by variable name)."""
    project_bp, graph = load_project(cfg)

    print("\n--- Datatype Usage Analysis ---")
    print("Enter the variable name to analyze:")
    var_name = input("> ").strip()

    if not var_name:
        print("❌ No variable name provided")
        pause()
        return

    try:
        report = variables_reporting_module.analyze_datatype_usage(
            project_bp,
            var_name,
            debug=cfg.get("debug", False),
            unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
        )
        print("\n" + report)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")

    pause()


def analysis_menu(cfg: dict):
    while True:
        clear_screen()
        print("\n--- Analyses ---")
        print("Variable analyses:")
        for k, (name, _) in VARIABLE_ANALYSES.items():
            print(f"{k}) {name}")
        print("8) Datatype usage analysis (by variable name)")
        print("9) Variable usage (fields + locations)")
        print("10) Module local variable field analysis")
        print("11) MMS interface variables (WriteData/Outputvariable)")
        print("12) Validate ICF paths (per program)")
        print("Module analyses:")
        print("13) Compare module variants by name")
        print("14) List module instances by name")
        print("15) Debug module tree structure")
        print("16) Commented-out code in comments")
        print("f) Force refresh cached AST")
        print("b) Back")
        print("q) Quit")

        c = input("> ").strip().lower()
        if c == "b":
            return
        if c == "q":
            quit_app()

        if c == "8":
            run_datatype_usage_analysis(cfg)
        elif c == "9":
            run_debug_variable_usage(cfg)
        elif c == "10":
            run_module_localvar_analysis(cfg)
        elif c == "11":
            run_mms_interface_analysis(cfg)
        elif c == "12":
            run_icf_validation(cfg)
        elif c == "13":
            run_module_duplicates_analysis(cfg)
        elif c == "14":
            run_module_find_by_name(cfg)
        elif c == "15":
            run_module_tree_debug(cfg)
        elif c == "16":
            run_comment_code_analysis(cfg)
        elif c == "f":
            if confirm("Force refresh cached AST?"):
                force_refresh_ast(cfg)
        elif c in VARIABLE_ANALYSES:
            name, kinds = VARIABLE_ANALYSES[c]
            # kinds is either a set[IssueKind] or None at this point
            run_variable_analysis(cfg, kinds if isinstance(kinds, (set, type(None))) else None)
        else:
            print("Invalid choice.")
            pause()


def run_module_duplicates_analysis(cfg: dict):
    project_bp, _ = load_project(cfg)

    print("\n--- Compare Module Variants ---")
    print("Enter module name(s) to compare (comma-separated):")
    raw_names = input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        print("❌ No module name provided")
        pause()
        return

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
    project_bp, _ = load_project(cfg)

    print("\n--- Find Module Instances ---")
    print("Enter module name(s) to search for (comma-separated):")
    raw_names = input("> ").strip()
    module_names = [name.strip() for name in raw_names.split(",") if name.strip()]

    if not module_names:
        print("❌ No module name provided")
        pause()
        return

    try:
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
    project_bp, _ = load_project(cfg)

    print("\n--- Debug Module Tree Structure ---")
    max_depth_txt = prompt("Max depth", "10")
    try:
        max_depth = int(max_depth_txt)
    except ValueError:
        print("❌ Invalid depth; using default 10")
        max_depth = 10

    try:
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
    project_bp, _ = load_project(cfg)

    print("\n--- Module Local Variable Analysis ---")
    print("Enter the module path (strict) relative to BasePicture.")
    print("Example: StartMaster.KaHA251A")
    module_path = input(f"{project_bp.header.name}.").strip()

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

    try:
        from .analyzers.variable_usage_reporting import analyze_module_localvar_fields

        report = analyze_module_localvar_fields(
            project_bp,
            module_path,
            var_name,
            debug=cfg.get("debug", False),
        )
        print("\n" + report)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback

        traceback.print_exc()

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

    project_bp, graph = load_project(cfg)
    context = AnalysisContext(
        base_picture=project_bp,
        graph=graph,
        debug=cfg.get("debug", False),
    )

    print("\n--- Running checks ---")
    for spec in analyzers:
        print(f"\n=== {spec.name} ({spec.key}) ===")
        report = spec.run(context)
        print(report.summary())

    pause()


def run_checks_menu(cfg: dict):
    _run_checks(cfg, None)


def run_mms_interface_analysis(cfg: dict):
    """List variables mapped into MMSWriteVar/MMSReadVar interface modules."""
    project_bp, _ = load_project(cfg)

    print("\n--- MMS Interface Variables ---")

    try:
        report = analyze_mms_interface_variables(
            project_bp,
            debug=cfg.get("debug", False),
        )
        print("\n" + report.summary())
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback

        traceback.print_exc()

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
    project_bp, _ = load_project(cfg)

    print("\n--- Variable Usage (Fields + Locations) ---")
    print("Enter the variable name to analyze:")
    var_name = input("> ").strip()

    if not var_name:
        print("❌ No variable name provided")
        pause()
        return

    try:
        report = debug_variable_usage(project_bp, var_name, debug=cfg.get("debug", False))
        print("\n" + report)
    except Exception as e:
        print(f"❌ Error during debug: {e}")

    pause()


def run_comment_code_analysis(cfg: dict):
    """Scan raw source files for code-like content inside comments."""
    project_bp, graph = load_project(cfg)

    print("\n--- Commented-out Code ---")
    paths = getattr(graph, "source_files", set())
    report = analyze_comment_code_files(paths, project_bp.header.name)
    print("\n" + report.summary())
    pause()


def run_advanced_datatype_analysis(cfg: dict):
    """Enhanced datatype analysis with filtering options."""
    project_bp, graph = load_project(cfg)

    print("\n--- Advanced Datatype Analysis ---")
    print("1) Analyze variable by name (field-level usage)")
    print("2) Compare module variants by name")
    print("3) Debug specific variable usage")
    print("b) Back")

    choice = input("> ").strip()

    if choice == "1":
        var_name = input("Enter variable name: ").strip()
        if var_name:
            report = variables_reporting_module.analyze_datatype_usage(
                project_bp,
                var_name,
                debug=cfg.get("debug", False),
                unavailable_libraries=getattr(graph, "unavailable_libraries", set()),
            )
            print("\n" + report)

    elif choice == "2":
        module_name = input("Enter module name to compare: ").strip()
        if module_name:
            print("⚠ Module comparison analysis not yet implemented")

    elif choice == "3":
        var_name = input("Enter variable name to debug: ").strip()
        if var_name:
            report = variables_reporting_module.debug_variable_usage(
                project_bp,
                var_name,
                debug=cfg.get("debug", False),
            )
            print("\n" + report)

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

        project_bp, graph = load_project(cfg)
        project = (project_bp, graph)

        if c == "1" and confirm("Dump parse tree?"):
            engine_module.dump_parse_tree(project)
        elif c == "2" and confirm("Dump AST?"):
            engine_module.dump_ast(project)
        elif c == "3" and confirm("Dump dependency graph?"):
            engine_module.dump_dependency_graph(project)
        elif c == "4" and confirm("Dump variable report?"):
            print(analyze_variables(project_bp, debug=cfg.get("debug", False),
                                    unavailable_libraries=getattr(graph, 'unavailable_libraries', set())).summary())
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
1) Change Root program/library to analyze
2) Toggle Mode (official/draft)
3) Toggle scan_root_only
4) Toggle fast_cache_validation
5) Change Program_dir
6) Change ABB_lib_dir
7) Add/remove other_lib_dirs
8) Save config
9) Change ICF_dir
10) Toggle debug
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
            new = prompt("New root program/library", cfg["root"])
            if not root_exists(new, cfg):
                print("❌ Root not found in configured directories")
                pause()
            elif confirm(f"Change root to '{new}'?"):
                cfg["root"] = new
                dirty = True

        elif c == "2":
            new = "draft" if cfg["mode"] == "official" else "official"
            if confirm(f"Switch mode to '{new}'?"):
                cfg["mode"] = new
                dirty = True

        elif c == "3":
            if confirm("Toggle scan_root_only?"):
                cfg["scan_root_only"] = not cfg["scan_root_only"]
                dirty = True

        elif c == "4":
            if confirm("Toggle fast_cache_validation?"):
                cfg["fast_cache_validation"] = not cfg["fast_cache_validation"]
                dirty = True

        elif c == "5":
            new = prompt("New program_dir", cfg["program_dir"])
            if confirm("Change program_dir?"):
                cfg["program_dir"] = new
                dirty = True

        elif c == "6":
            new = prompt("New ABB_lib_dir", cfg["ABB_lib_dir"])
            if confirm("Change ABB_lib_dir?"):
                cfg["ABB_lib_dir"] = new
                dirty = True

        elif c == "7":
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
        elif c == "8":
            if confirm("Save config to disk?"):
                save_config(CONFIG_PATH, cfg)
                dirty = False
        elif c == "9":
            new = prompt("New ICF_dir", cfg["icf_dir"])
            if confirm("Change ICF_dir?"):
                cfg["icf_dir"] = new
                dirty = True
        elif c == "10":
            if confirm("Toggle debug?"):
                cfg["debug"] = not cfg["debug"]
                dirty = True
        else:
            print("Invalid choice.")


# ----------------------------
# Main loop
# ----------------------------
def main():
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
                    return
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
• Use "Analyses" to analyze the configured root program
• Use "Dump outputs" to inspect parse trees, ASTs, etc.
• Use "Edit config" to change settings
• Use "Self-check" to check if the config is OK
• Press 'q' at any time in the main menu to quit

=== SattLint ===
1) Analyses
2) Dump outputs
3) Edit config
4) Self-check diagnostics
5) Force refresh cached AST
q) Quit
""")
            c = input("> ").strip().lower()

            if c == "1":
                analysis_menu(cfg)

            elif c == "2":
                dump_menu(cfg)

            elif c == "3":
                dirty |= config_menu(cfg)

            elif c == "4":
                clear_screen()
                self_check(cfg)
                pause()

            elif c == "5":
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
        return


if __name__ == "__main__":
    main()
