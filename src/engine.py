# main.py
from pathlib import Path
from lark import Lark
import constants
import sys
from transformer.sl_transformer import SLTransformer
from models.ast_model import BasePicture, DataType, ModuleTypeDef
from analyzers.variables import analyze_variables, VariablesReport, debug_variable_usage
from analyzers.modules import analyze_module_duplicates, debug_module_structure
from docgenerator.docgen import generate_docx
from collections.abc import Iterable
from enum import Enum
from models.project_graph import ProjectGraph
import logging

# ---------------- Toggles ----------------
DEFAULT_STRICT_FAIL_ON_MISSING: bool = False  # toggle: True -> raise on missing/parse errors
DEFAULT_IGNORE_VENDOR_LIB: bool = True
DEFAULT_DEBUG: bool = True
DEFAULT_SCAN_ROOT_ONLY: bool = True  # set False to include dependencies

# Create a module-level logger consistent with cli.py
logging.basicConfig(
    level=logging.DEBUG,
    format='%(message)s',  # Just the message, no prefixes
    force=True
)
log = logging.getLogger("SattLint")

class CodeMode(Enum):
    OFFICIAL = "official"  # .x code, .z deps
    DRAFT = "draft"  # .s code, .l deps

def code_ext(mode: CodeMode) -> str:
    return ".x" if mode is CodeMode.OFFICIAL else ".s"


def deps_ext(mode: CodeMode) -> str:
    return ".z" if mode is CodeMode.OFFICIAL else ".l"

DEFAULT_SELECTED_MODE: CodeMode = CodeMode.OFFICIAL  # or CodeMode.DRAFT
DEFAULT_PROGRAMS_ROOT = Path(r"C:\Users\SQHJ\OneDrive - Novo Nordisk\Workspace\Libs\HC")
DEFAULT_PROGRAMS_DIR = DEFAULT_PROGRAMS_ROOT / "unitlib"
DEFAULT_LIBS_DIRS = [DEFAULT_PROGRAMS_ROOT / "nnelib", DEFAULT_PROGRAMS_ROOT / "projectlib", ]
DEFAULT_ROOT_PROGRAM = "KaHCBOpsamLib"
DEFAULT_CODE_MODE = CodeMode.OFFICIAL
DEFAULT_VENDOR_DIR: Path = DEFAULT_PROGRAMS_ROOT / "SL_Library"


BASE_DIR = Path(__file__).resolve().parent
GRAMMAR_PATH = BASE_DIR / "grammar" / "sattline.lark"

def dbg(msg: str) -> None:
    if DEFAULT_DEBUG:
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
class SattLineProjectLoader:
    def __init__(
        self,
        programs_dir: Path,
        libs_dirs: Iterable[Path],
        mode: CodeMode,
        scan_root_only: bool = False,
    ):
        self.programs_dir = programs_dir
        self.libs_dirs = list(libs_dirs)
        self.mode = mode
        self.scan_root_only = scan_root_only
        dbg(
            f"Selected mode={mode.value}, code_ext={code_ext(mode)}, deps_ext={deps_ext(mode)}"
        )
        dbg(f"Programs dir: {self.programs_dir}")
        for i, ld in enumerate(self.libs_dirs, start=1):
            dbg(f"Lib {i}: {ld}")
        self.parser = create_sl_parser()  # reuse your grammar setup
        self.transformer = SLTransformer()  # reuse your transformer
        self._visited: set[str] = set()
        self._stack: set[str] = set()  # cycle protection
        self._ignored_dirs: set[Path] = (
            {DEFAULT_VENDOR_DIR.resolve()} if DEFAULT_IGNORE_VENDOR_LIB else set()
        )

    def _is_ignored_base(self, base: Path) -> bool:
        try:
            base_r = base.resolve()
        except Exception:
            base_r = base
        return any(base_r == ign for ign in self._ignored_dirs)

    def _find_code(self, name: str) -> Path | None:
        ext = code_ext(self.mode)
        found: Path | None = None
        for base in [self.programs_dir, *self.libs_dirs]:
            if self._is_ignored_base(base):
                # Skip vendor dir entirely
                continue
            p = base / f"{name}{ext}"
            dbg(f"Checking code file: {p} (exists={p.exists()})")
            if p.exists():
                found = p
                break

        if not found:
            dbg(f"No code file found for '{name}' with ext={ext}")
            return None
        else:
            dbg(f"Using code file: {found}")
            return found

    def _find_deps(self, name: str) -> Path | None:
        ext = deps_ext(self.mode)
        found: Path | None = None
        for base in [self.programs_dir, *self.libs_dirs]:
            if self._is_ignored_base(base):
                # Skip vendor dir entirely
                continue
            p = base / f"{name}{ext}"
            dbg(f"Checking deps file: {p} (exists={p.exists()})")
            if p.exists():
                found = p
                break
        if not found:
            dbg(f"No deps file found for '{name}' with ext={ext}")
        else:
            dbg(f"Using deps file: {found}")
        return found

    def _find_vendor_code(self, name: str) -> Path | None:
        ext = code_ext(self.mode)
        for ign in self._ignored_dirs:
            p = ign / f"{name}{ext}"
            if p.exists():
                return p
        return None

    def _find_vendor_deps(self, name: str) -> Path | None:
        ext = deps_ext(self.mode)
        for ign in self._ignored_dirs:
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
        dbg(f"Deps from {deps_path.name}: {names}")
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
            pr = self.programs_dir.resolve()
        except Exception:
            pr = self.programs_dir
        if rp.is_relative_to(pr):
            return pr.name
        for ld in self.libs_dirs:
            try:
                lr = ld.resolve()
            except Exception:
                lr = ld
            if rp.is_relative_to(lr):
                return lr.name
        # Fallback: parent directory name
        return rp.parent.name

    def _parse_one(self, code_path: Path) -> BasePicture:
        dbg(f"Parsing file: {code_path}")
        src = self._read_text_simple(code_path)
        cleaned = strip_sl_comments(src)
        tree = self.parser.parse(cleaned)  # may raise LarkError
        dbg("Parse OK, transforming with SLTransformer")
        basepic = self.transformer.transform(tree)
        # Attach raw parse tree for later dumping in CLI
        try:
            setattr(basepic, "parse_tree", tree)  # <-- add this
        except Exception:
            # If BasePicture uses __slots__, skip attaching
            dbg("BasePicture does not allow dynamic attributes; parse tree not attached")
        dbg(f"Transform result type: {type(basepic).__name__}")
        if not isinstance(basepic, BasePicture):
            dbg(
                "Warning: transform result is not BasePicture; check transformer.start()"
            )
        return basepic

    def resolve(self, root_name: str, strict: bool = False) -> ProjectGraph:
        if self.scan_root_only:
            return self._resolve_root_only(root_name, strict)
        dbg(f"Resolving root: {root_name}")
        graph = ProjectGraph()
        self._visit(root_name, graph, strict)
        dbg(f"Resolved ASTs: {list(graph.ast_by_name.keys())}")
        if graph.missing:
            dbg(f"Missing/failed: {graph.missing}")
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


if __name__ == "__main__":
    loader = SattLineProjectLoader(
        DEFAULT_PROGRAMS_DIR, DEFAULT_LIBS_DIRS, DEFAULT_SELECTED_MODE, scan_root_only=DEFAULT_SCAN_ROOT_ONLY
    )
    graph = loader.resolve(DEFAULT_ROOT_PROGRAM, strict=DEFAULT_STRICT_FAIL_ON_MISSING)

    # Build a synthetic project-wide BasePicture with merged defs
    root_bp = graph.ast_by_name.get(DEFAULT_ROOT_PROGRAM)
    if not root_bp:
        # Helpful summary before raising
        print("\n--- Debug summary ---")
        print(f"Mode: {DEFAULT_SELECTED_MODE.value}")
        print(f"Programs dir: {DEFAULT_PROGRAMS_DIR}")
        print(f"Libs dirs: {DEFAULT_LIBS_DIRS}")
        print(f"Resolved ASTs: {list(graph.ast_by_name.keys())}")
        if graph.missing:
            print("Missing/failed:")
            for m in graph.missing:
                print(f"  - {m}")
        # The same RuntimeError as before, but now with context printed
        raise RuntimeError(
            f"Root program '{DEFAULT_ROOT_PROGRAM}' not parsed. Missing or error?"
        )

    project_bp = merge_project_basepicture(root_bp, graph)
    
    # result = debug_variable_usage(project_bp, "AgitVariAtribut")
    # print(result)
    print(project_bp)
    report: VariablesReport = analyze_variables(project_bp)
    print(report.summary())

    #debug_module_structure(root_bp)

    # # Analyze specific module
    # result = analyze_module_duplicates(root_bp, "UnitControl", debug=False)
    # print("\n" + result.summary())

    # # Access detailed information
    # if result.unique_variants > 1:
    #     print("\nDetailed variant analysis:")
    #     for i, fp in enumerate(result.fingerprints, 1):
    #         print(f"\n=== Variant {i} ===")
    #         print(f"DateCode: {fp.datecode}")
    #         print(f"Module Parameters: {[v.name for v in fp.module.moduleparameters]}")
    #         print(f"Local Variables: {[v.name for v in fp.module.localvariables]}")
