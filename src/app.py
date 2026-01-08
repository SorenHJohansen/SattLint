#!/usr/bin/env python3
from __future__ import annotations

import logging
from pathlib import Path
import tomllib
import os
import sys

import engine as engine_module

CONFIG_PATH = Path("config.toml")

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
        "ignore_vendor",
        "scan_root_only",
        "debug",
        "programs_dir",
        "vendor_libs_dir",
        "libs_dirs",
    ]
    for k in required_keys:
        if k not in cfg:
            print(f"❌ Missing config key: {k}")
            ok = False

    # Directories
    for name in ("programs_dir", "vendor_libs_dir"):
        p = Path(cfg.get(name, ""))
        if not p.exists():
            print(f"❌ {name} does not exist: {p}")
            ok = False
        elif not os.access(p, os.R_OK):
            print(f"❌ {name} not readable: {p}")
            ok = False
        else:
            print(f"✔ {name}: {p}")

    # libs_dirs
    for p in cfg.get("libs_dirs", []):
        path = Path(p)
        if not path.exists():
            print(f"⚠ libs_dirs entry missing: {path}")
        else:
            print(f"✔ libs_dirs: {path}")

    # Root existence
    if root_exists(cfg.get("root", ""), cfg):
        print(f"✔ Root program found: {cfg['root']}")
    else:
        print(f"❌ Root program not found: {cfg.get('root')}")
        ok = False

    print("------------------------------\n")
    return ok


def confirm(msg: str) -> bool:
    return input(f"{msg} [y/N]: ").strip().lower() in ("y", "yes")


def prompt(msg: str, default: str | None = None) -> str:
    if default is not None:
        return input(f"{msg} [{default}]: ").strip() or default
    return input(f"{msg}: ").strip()


def load_config(path: Path) -> dict:
    if not path.exists():
        return {
            "root": engine_module.DEFAULT_ROOT_PROGRAM,
            "mode": engine_module.DEFAULT_SELECTED_MODE.value,
            "ignore_vendor": False,
            "scan_root_only": False,
            "debug": False,
            "vendor_libs_dir": str(engine_module.DEFAULT_VENDOR_DIR),
            "programs_dir": str(engine_module.DEFAULT_PROGRAMS_DIR),
            "libs_dirs": [str(p) for p in engine_module.DEFAULT_LIBS_DIRS],
        }
    with path.open("rb") as f:
        return tomllib.load(f)


def save_config(path: Path, cfg: dict) -> None:
    def w(val):
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, list):
            return "[\n" + "\n".join(f'  "{v}",' for v in val) + "\n]"
        return f'"{val}"'

    text = f"""
# ----------------------------
# General project configuration
# ----------------------------
root = {w(cfg["root"])}
mode = {w(cfg["mode"])}
ignore_vendor = {w(cfg["ignore_vendor"])}
scan_root_only = {w(cfg["scan_root_only"])}
debug = {w(cfg["debug"])}

# ----------------------------
# Paths
# ----------------------------
vendor_libs_dir = {w(cfg["vendor_libs_dir"])}
programs_dir = {w(cfg["programs_dir"])}

libs_dirs = {w(cfg["libs_dirs"])}
""".lstrip()

    path.write_text(text, encoding="utf-8")
    print(f"✔ Config saved to {path}")


def root_exists(root: str, cfg: dict) -> bool:
    dirs = [Path(cfg["programs_dir"])] + [Path(p) for p in cfg["libs_dirs"]]
    for d in dirs:
        if not d.exists():
            continue
        for ext in ("", ".txt", ".st"):
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
        "ignore_vendor",
        "scan_root_only",
        "debug",
        "programs_dir",
        "vendor_libs_dir",
    ):
        print(f"{k:16}: {cfg[k]}")
    print("libs_dirs:")
    for i, p in enumerate(cfg["libs_dirs"], 1):
        print(f"  {i}. {p}")
    print("-----------------------------\n")


# ----------------------------
# Analysis & dumps
# ----------------------------


def load_project(cfg: dict):
    apply_debug(cfg)

    engine_module.DEFAULT_IGNORE_VENDOR_LIB = cfg["ignore_vendor"]

    mode = (
        engine_module.CodeMode.OFFICIAL
        if cfg["mode"] == "official"
        else engine_module.CodeMode.DRAFT
    )

    loader = engine_module.SattLineProjectLoader(
        Path(cfg["programs_dir"]),
        [Path(p) for p in cfg["libs_dirs"]],
        mode,
        scan_root_only=cfg["scan_root_only"],
    )

    graph = loader.resolve(cfg["root"], strict=False)
    root_bp = graph.ast_by_name.get(cfg["root"])
    if not root_bp:
        raise RuntimeError("Root program not parsed")
    return engine_module.merge_project_basepicture(root_bp, graph)


def run_analysis(cfg: dict):
    project = load_project(cfg)
    report = engine_module.analyze_variables(project)
    print(report.summary())


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
        print("""
--- Configuration ---
1) Root program
2) Mode
3) Toggle ignore_vendor
4) Toggle scan_root_only
5) Toggle debug
6) Programs dir
7) Vendor libs dir
8) Edit libs_dirs
b) Back
""")
        c = input("> ").strip().lower()

        if c == "b":
            return dirty

        elif c == "1":
            new = prompt("Root program", cfg["root"])
            if not root_exists(new, cfg):
                print("❌ Root not found in configured directories")
            elif confirm(f"Change root to '{new}'?"):
                cfg["root"] = new
                dirty = True

        elif c == "2":
            new = "draft" if cfg["mode"] == "official" else "official"
            if confirm(f"Switch mode to '{new}'?"):
                cfg["mode"] = new
                dirty = True

        elif c == "3":
            if confirm("Toggle ignore_vendor?"):
                cfg["ignore_vendor"] = not cfg["ignore_vendor"]
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
            new = prompt("Programs dir", cfg["programs_dir"])
            if confirm("Change programs_dir?"):
                cfg["programs_dir"] = new
                dirty = True

        elif c == "7":
            new = prompt("Vendor libs dir", cfg["vendor_libs_dir"])
            if confirm("Change vendor_libs_dir?"):
                cfg["vendor_libs_dir"] = new
                dirty = True

        elif c == "8":
            libs = cfg["libs_dirs"]
            print("\nCurrent libs_dirs:")
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

        else:
            print("Invalid choice.")


# ----------------------------
# Main loop
# ----------------------------


def main():
    cfg = load_config(CONFIG_PATH)

    if not self_check(cfg):
        if not confirm("Self-check failed. Continue anyway?"):
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
• Use "Configuration" to change settings
• Use "Run analysis" to analyze the configured root program
• Use "Dump outputs" to inspect parse trees, ASTs, etc.
• Press 'q' at any time in the main menu to quit

=== SattLint ===
1) Show config
2) Configuration
3) Run analysis
4) Dump outputs
5) Save config
6) Self-check diagnostics
q) Quit
""")
        c = input("> ").strip().lower()

        if c == "1":
            clear_screen()
            show_config(cfg)
            pause()

        elif c == "2":
            dirty |= config_menu(cfg)

        elif c == "3":
            if confirm("Run analysis?"):
                run_analysis(cfg)

        elif c == "4":
            dump_menu(cfg)

        elif c == "5":
            if confirm("Save config to disk?"):
                save_config(CONFIG_PATH, cfg)
                dirty = False
        elif c == "6":
            clear_screen()
            self_check(cfg)
            pause()

        elif c == "q":
            if dirty and confirm("Unsaved changes. Save before quitting?"):
                save_config(CONFIG_PATH, cfg)
            print("Bye.")
            return

        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
