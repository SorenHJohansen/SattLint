#!/usr/bin/env python3
from __future__ import annotations

import logging
from pathlib import Path
import tomllib
import tomli_w
import os
import sys
from . import engine as engine_module
from .analyzers.variables import IssueKind, filter_variable_report, analyze_variables

DEFAULT_CONFIG = {
    "root": "",
    "mode": "official",
    "ignore_ABB_lib": False,
    "scan_root_only": False,
    "debug": False,
    "program_dir": "",
    "ABB_lib_dir": "",
    "other_lib_dirs": [],
}


VARIABLE_ANALYSES = {
    "1": ("All variable analyses", None),
    "2": ("Unused variables", {IssueKind.UNUSED}),
    "3": ("Read-only but not CONST", {IssueKind.READ_ONLY_NON_CONST}),
    "4": ("Written but never read", {IssueKind.NEVER_READ}),
    "5": ("String mapping type mismatches", {IssueKind.STRING_MAPPING_MISMATCH}),
    "6": ("Duplicated complex datatypes", {IssueKind.DATATYPE_DUPLICATION}),
}


def get_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    cfg_dir = base / "sattlint"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.toml"


CONFIG_PATH = get_config_path()

logging.basicConfig(format="%(message)s")
log = logging.getLogger("sattlint")


# ----------------------------
# Helpers
# ----------------------------
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nPress Enter to continue...")


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
        "root",
        "mode",
        "ignore_ABB_lib",
        "scan_root_only",
        "debug",
        "program_dir",
        "ABB_lib_dir",
        "other_lib_dirs",
    ]
    for k in required_keys:
        if k not in cfg:
            print(f"❌ Missing config key: {k}")
            ok = False

    # Directories
    for name in ("program_dir", "ABB_lib_dir"):
        p = Path(cfg.get(name, ""))
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

    # Root existence
    if root_exists(cfg.get("root", ""), cfg):
        print(f"✔ Root program/library found: {cfg['root']}")
    else:
        print(f"❌ Root program/library not found: {cfg.get('root')}")
        ok = False

    print("------------------------------\n")
    return ok


def confirm(msg: str) -> bool:
    return input(f"{msg} [y/N]: ").strip().lower() in ("y", "yes")


def prompt(msg: str, default: str | None = None) -> str:
    if default is not None:
        return input(f"{msg} [{default}]: ").strip() or default
    return input(f"{msg}: ").strip()


def load_config(path: Path) -> tuple[dict, bool]:
    if not path.exists():
        print(f"⚠ No config found, creating default: {path}")
        cfg = DEFAULT_CONFIG.copy()
        save_config(path, cfg)
        return cfg, True

    with path.open("rb") as f:
        return tomllib.load(f), False


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

    data = {k: normalize(v) for k, v in cfg.items()}
    path.write_text(tomli_w.dumps(data), encoding="utf-8")
    print(f"✔ Config saved to {path}")


def root_exists(root: str, cfg: dict) -> bool:
    dirs = [Path(cfg["program_dir"])] + [Path(p) for p in cfg["other_lib_dirs"]]
    ext = ""
    for d in dirs:
        if not d.exists():
            continue
        if cfg["mode"] == "official":
            ext = ".x"
        elif cfg["mode"] == "draft":
            ext = ".s"
        if (d / f"{root}{ext}").exists():
            return True
    return False


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
        "ignore_ABB_lib",
        "scan_root_only",
        "debug",
        "program_dir",
        "ABB_lib_dir",
    ):
        print(f"{k:16}: {cfg[k]}")
    print("other_lib_dirs:")
    for i, p in enumerate(cfg["other_lib_dirs"], 1):
        print(f"  {i}. {p}")
    print("-----------------------------\n")


# ----------------------------
# Analysis & dumps
# ----------------------------


def load_project(cfg: dict):
    loader = engine_module.SattLineProjectLoader(
        program_dir=Path(cfg["program_dir"]),
        other_lib_dirs=[Path(p) for p in cfg["other_lib_dirs"]],
        abb_lib_dir=Path(cfg["ABB_lib_dir"]),
        mode=engine_module.CodeMode(cfg["mode"]),
        scan_root_only=cfg["scan_root_only"],
        ignore_abb_lib=cfg["ignore_ABB_lib"],
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
    return project_bp, graph


def run_variable_analysis(cfg: dict, kinds: set[IssueKind] | None):
    project_bp, _ = load_project(cfg)

    report = analyze_variables(project_bp)

    if kinds is not None:
        report = filter_variable_report(report, kinds)

    print(report.summary())
    pause()


def variable_analysis_menu(cfg: dict):
    while True:
        clear_screen()
        print("\n--- Variable analyses ---")
        for k, (name, _) in VARIABLE_ANALYSES.items():
            print(f"{k}) {name}")
        print("b) Back")

        c = input("> ").strip().lower()
        if c == "b":
            return

        if c in VARIABLE_ANALYSES:
            name, kinds = VARIABLE_ANALYSES[c]
            if confirm(f"Run '{name}'?"):
                run_variable_analysis(cfg, kinds)
        else:
            print("Invalid choice.")
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
""")
        c = input("> ").strip().lower()
        if c == "b":
            return

        project = load_project(cfg)

        if c == "1" and confirm("Dump parse tree?"):
            engine_module.dump_parse_tree(project)
        elif c == "2" and confirm("Dump AST?"):
            engine_module.dump_ast(project)
        elif c == "3" and confirm("Dump dependency graph?"):
            engine_module.dump_dependency_graph(project)
        elif c == "4" and confirm("Dump variable report?"):
            print(engine_module.analyze_variables(project))
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
--- Edit Configuration ---
1) Change Root program/library to analyze
2) Toggle Mode (official/draft)
3) Toggle ignore_ABB_lib
4) Toggle scan_root_only
5) Toggle debug
6) Change Program_dir
7) Change ABB_lib_dir
8) Add/remove other_lib_dirs
9) Save config
b) Back
""")
        c = input("> ").strip().lower()

        if c == "b":
            return dirty

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
            if confirm("Toggle ignore_ABB_lib?"):
                cfg["ignore_ABB_lib"] = not cfg["ignore_ABB_lib"]
                dirty = True

        elif c == "4":
            if confirm("Toggle scan_root_only?"):
                cfg["scan_root_only"] = not cfg["scan_root_only"]
                dirty = True

        elif c == "5":
            if confirm("Toggle debug?"):
                cfg["debug"] = not cfg["debug"]
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
        else:
            print("Invalid choice.")


# ----------------------------
# Main loop
# ----------------------------
def main():
    cfg, default_used = load_config(CONFIG_PATH)
    if default_used:
        print(
            "⚠ Default config created. Please edit configuration before running analysis."
        )
        pause()
    elif not self_check(cfg):
        if not confirm("Self-check failed. Continue?"):
            return
    dirty = False

    while True:
        clear_screen()
        print("""
How to use SattLint
------------------
• Navigate using the number keys shown in each menu
• Press Enter to confirm a selection
• Changes are NOT saved until you choose "Save config"
• Use "Run analysis" to analyze the configured root program
• Use "Dump outputs" to inspect parse trees, ASTs, etc.
• Use "Edit config" to change settings
• Use "Self-check" to check if the config is OK
• Press 'q' at any time in the main menu to quit

=== SattLint ===
1) Run analysis
2) Dump outputs
3) Edit config
4) Self-check diagnostics
q) Quit
""")
        c = input("> ").strip().lower()

        if c == "1":
            variable_analysis_menu(cfg)

        elif c == "2":
            dump_menu(cfg)

        elif c == "3":
            dirty |= config_menu(cfg)

        elif c == "4":
            clear_screen()
            self_check(cfg)
            pause()

        elif c == "q":
            if dirty and confirm("Unsaved config changes. Save before quitting?"):
                save_config(CONFIG_PATH, cfg)
            print("Bye.")
            return

        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
