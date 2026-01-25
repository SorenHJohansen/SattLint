# main.py
from pathlib import Path
from lark import Lark
from . import constants
from .transformer.sl_transformer import SLTransformer
from .models.ast_model import BasePicture, DataType, ModuleTypeDef
from collections.abc import Iterable
from enum import Enum
from .models.project_graph import ProjectGraph
import logging

# Create a module-level logger consistent with cli.py
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",  # Just the message, no prefixes
    force=True,
)
log = logging.getLogger("SattLint")


class CodeMode(Enum):
    OFFICIAL = "official"  # .x code, .z deps
    DRAFT = "draft"  # .s code, .l deps


def code_ext(mode: CodeMode) -> str:
    return ".x" if mode is CodeMode.OFFICIAL else ".s"


def deps_ext(mode: CodeMode) -> str:
    return ".z" if mode is CodeMode.OFFICIAL else ".l"


BASE_DIR = Path(__file__).resolve().parent
GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar" / "sattline.lark"

if not GRAMMAR_PATH.exists():
    raise RuntimeError(f"Grammar file missing: {GRAMMAR_PATH}")


class DebugMixin:
    debug: bool = False

    def dbg(self, msg: str) -> None:
        if self.debug:
            log.debug(f"[DEBUG] {msg}")


def strip_sl_comments(text: str) -> str:
    """
    Remove nested comments of the form (* ... *) from the input text.
    Preserves original line numbers by emitting newline characters
    encountered inside comments and in the whitespace after a comment.
    Also removes a single semicolon that immediately follows a comment
    (allowing intervening whitespace/newlines), while preserving those
    whitespace/newlines.

    Additionally:
    - Does NOT treat (* or *) as comment delimiters when they appear inside
      single- or double-quoted strings.
    - Inside strings, supports doubled quotes ("" and '') and backslash escapes.
    - A newline ends a string if it hasn't been closed yet. Both LF and CR will
      terminate the string; CRLF is preserved as-is.

    Assumptions:
    - Comments can be nested and may contain newlines.
    - Every comment is closed before EOF.
    """
    n = len(text)
    i = 0
    depth = 0
    in_string = False
    string_quote = ""  # either '"' or "'"
    out = []

    while i < n:
        ch = text[i]

        if depth == 0:
            if not in_string:
                # Enter string?
                if ch == '"' or ch == "'":
                    in_string = True
                    string_quote = ch
                    out.append(ch)
                    i += 1
                    continue
                # Enter comment?
                if ch == "(" and i + 1 < n and text[i + 1] == "*":
                    depth = 1
                    i += 2
                    continue
                # Normal code
                out.append(ch)
                i += 1
            else:
                # Inside string: copy literally, but end on newline
                if ch == "\n" or ch == "\r":
                    # Newline ends the (possibly unterminated) string
                    out.append(ch)
                    in_string = False
                    string_quote = ""
                    i += 1
                elif ch == string_quote:
                    # Support doubled quote within the same kind of string
                    if i + 1 < n and text[i + 1] == string_quote:
                        out.append(string_quote)
                        out.append(string_quote)
                        i += 2
                    else:
                        out.append(string_quote)
                        i += 1
                        in_string = False
                        string_quote = ""
                elif ch == "\\":
                    # Preserve backslash escape and following char (if any)
                    out.append("\\")
                    if i + 1 < n:
                        out.append(text[i + 1])
                        i += 2
                    else:
                        i += 1
                else:
                    out.append(ch)
                    i += 1
        else:
            # Inside comment: manage nesting and closing; preserve only CR/LF
            if ch == "(" and i + 1 < n and text[i + 1] == "*":
                depth += 1
                i += 2
            elif ch == "*" and i + 1 < n and text[i + 1] == ")":
                depth -= 1
                i += 2
                if depth == 0:
                    # Just closed the outermost comment: emit following whitespace/newlines,
                    # but remove one optional semicolon.
                    j = i
                    while j < n and text[j] in (" ", "\t", "\r", "\n"):
                        out.append(text[j])  # preserve whitespace/newlines
                        j += 1
                    if j < n and text[j] == ";":
                        j += 1  # skip a single semicolon
                    i = j
            else:
                if ch == "\n" or ch == "\r":
                    out.append(ch)
                i += 1

    return "".join(out)


def create_sl_parser() -> Lark:
    """
    Loads the Lark grammar from a file, injecting terminal constants,
    and returns a configured Lark parser.
    """
    with open(GRAMMAR_PATH, "r"):
        grammar_text = GRAMMAR_PATH.read_text(encoding="utf-8")
    # Prepare the dictionary of constants to inject into the grammar template
    # We only include constants that start with "GRAMMAR_VALUE_" or "GRAMMAR_REGEX_"
    # as these are specifically for the grammar file.
    grammar_substitutions = {
        name: getattr(constants, name)
        for name in dir(constants)
        if name.startswith("GRAMMAR_VALUE_") or name.startswith("GRAMMAR_REGEX_")
    }
    # Format the grammar string by replacing placeholders with constant values
    formatted_grammar = grammar_text.format(**grammar_substitutions)

    # Now, initialize the Lark parser with the formatted grammar
    return Lark(
        formatted_grammar, start="start", parser="lalr", propagate_positions=True
    )


# ---------- Loader with recursive resolution ----------
class SattLineProjectLoader(DebugMixin):
    def __init__(
        self,
        program_dir: Path,
        other_lib_dirs: Iterable[Path],
        abb_lib_dir: Path,
        mode: CodeMode,
        scan_root_only: bool,
        ignore_abb_lib: bool,
        debug: bool,
    ):
        self.program_dir = program_dir
        self.other_lib_dirs = list(other_lib_dirs)
        self.abb_lib_dir = abb_lib_dir
        self.mode = mode
        self.scan_root_only = scan_root_only
        self.ignore_abb_lib = ignore_abb_lib
        self.debug = debug
        self.parser = create_sl_parser()  # reuse your grammar setup
        self.transformer = SLTransformer()  # reuse your transformer
        self._visited: set[str] = set()
        self._stack: set[str] = set()  # cycle protection
        self._ignored_dirs: set[Path] = (
            {self.abb_lib_dir} if self.ignore_abb_lib else set()
        )
        self.dbg(
            f"Selected mode={mode.value}, code_ext={code_ext(mode)}, deps_ext={deps_ext(mode)}"
        )
        self.dbg(f"Programs dir: {self.program_dir}")
        for i, ld in enumerate(self.other_lib_dirs, start=1):
            self.dbg(f"Lib {i}: {ld}")

    def _is_ignored_base(self, base: Path) -> bool:
        try:
            base_r = base.resolve()
        except Exception:
            base_r = base
        return any(base_r == ign for ign in self._ignored_dirs)

    def _find_code(self, name: str) -> Path | None:
        """
        Find code file with fallback support.
        In draft mode: try .s first, fallback to .x
        In official mode: only use .x
        """
        extensions = [".s", ".x"] if self.mode == CodeMode.DRAFT else [".x"]

        for base in [self.program_dir, *self.other_lib_dirs]:
            if self._is_ignored_base(base):
                continue

            for ext in extensions:
                p = base / f"{name}{ext}"
                self.dbg(f"Checking code file: {p} (exists={p.exists()})")
                if p.exists():
                    self.dbg(f"Using code file: {p}")
                    return p

        self.dbg(f"No code file found for '{name}' in mode={self.mode.value}")
        return None

    def _find_deps(self, name: str) -> Path | None:
        """
        Find deps file with fallback support.
        In draft mode: try .l first, fallback to .z
        In official mode: only use .z
        """
        extensions = [".l", ".z"] if self.mode == CodeMode.DRAFT else [".z"]

        for base in [self.program_dir, *self.other_lib_dirs]:
            if self._is_ignored_base(base):
                continue

            for ext in extensions:
                p = base / f"{name}{ext}"
                self.dbg(f"Checking deps file: {p} (exists={p.exists()})")
                if p.exists():
                    self.dbg(f"Using deps file: {p}")
                    return p

        self.dbg(f"No deps file found for '{name}' in mode={self.mode.value}")
        return None

    def _find_vendor_code(self, name: str) -> Path | None:
        """Find code file in vendor directories with fallback."""
        extensions = [".s", ".x"] if self.mode == CodeMode.DRAFT else [".x"]

        for ign in self._ignored_dirs:
            for ext in extensions:
                p = ign / f"{name}{ext}"
                if p.exists():
                    return p
        return None

    def _find_vendor_deps(self, name: str) -> Path | None:
        """Find deps file in vendor directories with fallback."""
        extensions = [".l", ".z"] if self.mode == CodeMode.DRAFT else [".z"]

        for ign in self._ignored_dirs:
            for ext in extensions:
                p = ign / f"{name}{ext}"
                if p.exists():
                    return p
        return None

    def _read_deps(self, deps_path: Path) -> list[str]:
        # If utf-8 fails, try cp1252 (covers characters like 'ø' / 0xF8)
        try:
            text = deps_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = deps_path.read_text(encoding="cp1252")

        lines = text.splitlines()
        names = [ln.strip() for ln in lines if ln.strip()]
        self.dbg(f"Deps from {deps_path.name}: {names}")
        return names

    def _read_text_simple(self, path: Path) -> str:
        # If utf-8 fails, try cp1252 (covers characters like 'ø' / 0xF8)
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="cp1252")

    def _library_name_for_path(self, code_path: Path) -> str:
        """
        Return the top-level root directory name this file belongs to
        (e.g., 'unitlib', 'nnelib', 'projectlib', 'SL_Library').
        """
        rp = code_path.resolve()
        try:
            pr = self.program_dir.resolve()
        except Exception:
            pr = self.program_dir
        if rp.is_relative_to(pr):
            return pr.name
        for ld in self.other_lib_dirs:
            try:
                lr = ld.resolve()
            except Exception:
                lr = ld
            if rp.is_relative_to(lr):
                return lr.name
        # Fallback: parent directory name
        return rp.parent.name

    def _parse_one(self, code_path: Path) -> BasePicture:
        self.dbg(f"Parsing file: {code_path}")
        src = self._read_text_simple(code_path)
        cleaned = strip_sl_comments(src)
        tree = self.parser.parse(cleaned)  # may raise LarkError
        self.dbg("Parse OK, transforming with SLTransformer")
        basepic = self.transformer.transform(tree)
        # Attach raw parse tree for later dumping in CLI
        try:
            setattr(basepic, "parse_tree", tree)  # <-- add this
        except Exception:
            # If BasePicture uses __slots__, skip attaching
            self.dbg(
                "BasePicture does not allow dynamic attributes; parse tree not attached"
            )
        self.dbg(f"Transform result type: {type(basepic).__name__}")
        if not isinstance(basepic, BasePicture):
            self.dbg(
                "Warning: transform result is not BasePicture; check transformer.start()"
            )
        return basepic

    def resolve(self, root_name: str, strict: bool = False) -> ProjectGraph:
        if self.scan_root_only:
            return self._resolve_root_only(root_name, strict)
        self.dbg(f"Resolving root: {root_name}")
        graph = ProjectGraph()
        self._visit(root_name, graph, strict)
        self.dbg(f"Resolved ASTs: {list(graph.ast_by_name.keys())}")
        if graph.missing:
            self.dbg(f"Missing/failed: {graph.missing}")
        return graph

    def _resolve_root_only(self, root_name: str, strict: bool) -> ProjectGraph:
        graph = ProjectGraph()
        code_path = self._find_code(root_name)
        if not code_path:
            msg = f"Missing code file for '{root_name}' in mode={self.mode.value}"
            if strict:
                raise FileNotFoundError(msg)
            graph.missing.append(msg)
            return graph

        try:
            bp = self._parse_one(code_path)
            if bp is None:
                msg = f"{root_name} transformed to no BasePicture (parse/transform issue?)"
                if strict:
                    raise RuntimeError(msg)
                graph.missing.append(msg)
                return graph
            graph.ast_by_name[root_name] = bp
            lib_name = self._library_name_for_path(code_path)
            graph.index_from_basepic(
                bp, source_path=code_path, library_name=lib_name
            )  # collect any defs emitted in this files
            return graph
        except Exception as ex:
            if strict:
                raise
            graph.missing.append(f"{root_name} parse/transform error: {ex}")
            return graph

    def _visit(self, name: str, graph: ProjectGraph, strict: bool) -> None:
        key = name.lower()
        if key in self._visited or key in self._stack:
            return
        self._stack.add(key)

        # Resolve dependencies first (from non-vendor dirs only)
        deps_path = self._find_deps(name)
        dep_names = self._read_deps(deps_path) if deps_path else []

        # Visit each dep
        for dep in dep_names:
            self._visit(dep, graph, strict)

        # Determine code path
        code_path = self._find_code(name)
        if code_path is not None:
            try:
                bp = self._parse_one(code_path)
                if bp is not None:
                    graph.ast_by_name[name] = bp
                    lib_name = self._library_name_for_path(code_path)
                    graph.index_from_basepic(
                        bp, source_path=code_path, library_name=lib_name
                    )  # aggregate defs for global analysis [2]
                else:
                    msg = f"{name} transform produced no BasePicture (skipped)"
                    graph.missing.append(msg)
            except Exception as ex:
                if strict:
                    raise
                graph.missing.append(f"{name} parse/transform error: {ex}")
        else:
            # If we skipped vendor dir and the file exists there, mark as ignored vendor
            v_code = self._find_vendor_code(name)
            v_deps = self._find_vendor_deps(name)
            if v_code or v_deps:
                graph.ignored_vendor.append(f"{name} (vendor: {v_code or v_deps})")
            else:
                msg = f"Missing code file for '{name}' ({self.mode.value})"
                if strict:
                    raise FileNotFoundError(msg)
                graph.missing.append(msg)

        self._stack.remove(key)
        self._visited.add(key)


# ---------- Merge: build a synthetic “project” BasePicture ----------
def merge_project_basepicture(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
    """
    Create a single BasePicture that contains all DataType and ModuleTypeDef
    definitions from the root and its dependencies, so analyzers can resolve
    types across files without changing SLTransformer.
    """
    # Deduplicate by name and keep last definition seen (adjust strategy if needed)
    merged_datatypes: list[DataType] = list(graph.datatype_defs.values())
    merged_modtypes: list[ModuleTypeDef] = list(graph.moduletype_defs.values())

    return BasePicture(
        header=root_bp.header,
        name=root_bp.name,
        position=root_bp.position,
        datatype_defs=merged_datatypes,
        moduletype_defs=merged_modtypes,
        localvariables=root_bp.localvariables,
        submodules=root_bp.submodules,
        moduledef=root_bp.moduledef,
        modulecode=root_bp.modulecode,
        origin_file=root_bp.origin_file,
        origin_lib=root_bp.origin_lib,
    )


# ---------- Dump functions ----------
def _get_dump_dir() -> Path:
    """Get or create the dump directory."""
    from datetime import datetime
    dump_dir = Path.home() / ".sattlint" / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    return dump_dir


def dump_parse_tree(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the parse tree from the root BasePicture to a file."""
    from datetime import datetime
    project_bp, graph = project
    
    if project_bp.parse_tree is None:
        print("❌ No parse tree available for the root program.")
        return
    
    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"parse_tree_{project_bp.header.name}_{timestamp}.txt"
    
    output = project_bp.parse_tree.pretty()
    filename.write_text(output, encoding="utf-8")
    
    print(f"\n✔ Parse tree saved to: {filename}")
    print()


def dump_ast(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the AST (BasePicture) structure to a file."""
    from datetime import datetime
    project_bp, graph = project
    
    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"ast_{project_bp.header.name}_{timestamp}.txt"
    
    output = str(project_bp)
    filename.write_text(output, encoding="utf-8")
    
    print(f"\n✔ AST saved to: {filename}")
    print()


def dump_dependency_graph(project: tuple[BasePicture, ProjectGraph]) -> None:
    """Save the dependency graph to a file."""
    from datetime import datetime
    project_bp, graph = project
    
    dump_dir = _get_dump_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = dump_dir / f"dependency_graph_{project_bp.header.name}_{timestamp}.txt"
    
    lines = ["--- Dependency Graph ---"]
    lines.append(f"Programs/Libraries parsed: {len(graph.ast_by_name)}")
    for name in sorted(graph.ast_by_name.keys()):
        bp = graph.ast_by_name[name]
        origin_info = f" (from {bp.origin_lib}/{bp.origin_file})" if bp.origin_lib or bp.origin_file else ""
        lines.append(f"  • {name}{origin_info}")
    
    if graph.datatype_defs:
        lines.append(f"\nDataType Definitions: {len(graph.datatype_defs)}")
        for name in sorted(graph.datatype_defs.keys()):
            dt = graph.datatype_defs[name]
            origin_info = f" (from {dt.origin_lib}/{dt.origin_file})" if dt.origin_lib or dt.origin_file else ""
            lines.append(f"  • {name}{origin_info}")
    
    if graph.moduletype_defs:
        lines.append(f"\nModuleType Definitions: {len(graph.moduletype_defs)}")
        for name in sorted(graph.moduletype_defs.keys()):
            mt = graph.moduletype_defs[name]
            origin_info = f" (from {mt.origin_lib}/{mt.origin_file})" if mt.origin_lib or mt.origin_file else ""
            lines.append(f"  • {name}{origin_info}")
    
    if graph.missing:
        lines.append(f"\nMissing/Unresolved: {len(graph.missing)}")
        for msg in graph.missing:
            lines.append(f"  ⚠ {msg}")
    
    if graph.ignored_vendor:
        lines.append(f"\nIgnored Vendor: {len(graph.ignored_vendor)}")
        for msg in graph.ignored_vendor:
            lines.append(f"  ⓘ {msg}")
    
    output = "\n".join(lines)
    filename.write_text(output, encoding="utf-8")
    
    print(f"\n✔ Dependency graph saved to: {filename}")
    print()
