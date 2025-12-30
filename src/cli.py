# cli.py
from __future__ import annotations
import argparse
from pathlib import Path
import sys
import tomllib

# import things from your main.py (we reuse the loader & CodeMode definitions)
import main as main_module

import logging

log = logging.getLogger("sattline")


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    if p.suffix.lower() != ".toml":
        raise ValueError("Config file must be a .toml file")
    return tomllib.loads(p.read_text())


def parse_comma_list(s: str) -> list[Path]:
    if not s:
        return []
    return [Path(p.strip()) for p in s.split(",")]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="SattLint", description="SattLine project analyzer / doc generator CLI"
    )
    p.add_argument(
        "root",
        nargs="?",
        default=main_module.DEFAULT_ROOT_PROGRAM,
        help=f"Root program name (default: {main_module.DEFAULT_ROOT_PROGRAM})",
    )
    p.add_argument(
        "--programs-dir",
        "-p",
        default=str(main_module.DEFAULT_PROGRAMS_DIR),
        help="Directory containing program files",
    )
    p.add_argument(
        "--libs-dirs",
        "-l",
        default=",".join(map(str, main_module.DEFAULT_LIBS_DIRS)),
        help="Comma-separated list of library dirs",
    )
    p.add_argument(
        "--mode",
        "-m",
        choices=["official", "draft"],
        default=main_module.DEFAULT_SELECTED_MODE.value,
        help="Code mode (official=draft)",
    )
    p.add_argument(
        "--scan-root-only",
        action="store_true",
        help="Only parse the root file (no deps)",
    )
    p.add_argument(
        "--strict", action="store_true", help="Fail hard on missing/parse errors"
    )
    p.add_argument(
        "--no-DEFAULT_DEBUG", dest="DEFAULT_DEBUG", action="store_false", help="Disable DEFAULT_DEBUG prints"
    )
    p.add_argument(
        "--docx",
        "-d",
        default=None,
        help="Path to output .docx file (triggers doc generation if supported)",
    )
    p.add_argument(
        "--vendor-ignore",
        action="store_true",
        help="Ignore vendor dir (same as DEFAULT_IGNORE_VENDOR_LIB)",
    )
    p.add_argument(
        "--show-missing", action="store_true", help="Print missing files / issues"
    )
    p.add_argument("--version", action="version", version="SattLint 0.1")
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose info output"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Run dependency resolution only"
    )
    p.add_argument("--dump-parse-tree", help="Write raw parse tree to file")
    p.add_argument("--dump-ast", help="Write AST to file")

    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    # set DEFAULT_DEBUG flag on the imported module
    main_module.DEFAULT_DEBUG = args.DEFAULT_DEBUG

    DEFAULT_PROGRAMS_DIR = Path(args.programs_dir)
    libs = parse_comma_list(args.libs_dirs)

    mode = (
        main_module.CodeMode.OFFICIAL
        if args.mode == "official"
        else main_module.CodeMode.DRAFT
    )

    loader = main_module.SattLineProjectLoader(
        DEFAULT_PROGRAMS_DIR, libs, mode, scan_root_only=args.scan_root_only
    )
    # Respect vendor ignore override
    if args.vendor_ignore:
        main_module.DEFAULT_IGNORE_VENDOR_LIB = True

    graph = loader.resolve(args.root, strict=args.strict)

    root_bp = graph.ast_by_name.get(args.root)
    if not root_bp:
        print("Root program not parsed.")
        if args.show_missing or graph.missing:
            print("Missing / parse errors:")
            for m in graph.missing:
                print("  -", m)
        raise SystemExit(2)

    project_bp = main_module.merge_project_basepicture(root_bp, graph)
    print(project_bp)

    # run your analyzer (reuses your functions)
    report = main_module.analyze_variables(project_bp)
    print(report.summary())

    # optional docx generation (if available in your package)
    if args.docx:
        try:
            main_module.generate_docx(project_bp, Path(args.docx))
            print("Wrote docx:", args.docx)
        except Exception as ex:
            print("Docx generation failed:", ex)
            raise SystemExit(3)

    level = logging.WARNING
    if args.verbose:
        level = logging.INFO
    if args.DEFAULT_DEBUG:
        level = logging.DEBUG

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    if args.dump_parse_tree:
        pt = getattr(root_bp, "parse_tree", None)
        if pt is not None:
            Path(args.dump_parse_tree).write_text(pt.pretty())
            log.info(f"Wrote parse tree → {args.dump_parse_tree}")
        else:
            log.warning("No parse tree available")

    if args.dump_ast:
        Path(args.dump_ast).write_text(str(root_bp))
        log.info(f"Wrote AST → {args.dump_ast}")


"""
Inside code, replace any DEFAULT_DEBUG-style print with
log.DEFAULT_DEBUG("Something detailed…")
log.info("Something normal…")
log.warning("Something important…")
        """

if __name__ == "__main__":
    main()
