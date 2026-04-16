"""Parsing and project-loading engine for SattLine sources."""
from dataclasses import dataclass
from pathlib import Path
from lark import Lark
from lark.exceptions import VisitError
from sattline_parser import create_parser as parser_core_create_parser
from sattline_parser import parse_source_file as parser_core_parse_source_file
from sattline_parser import parse_source_text as parser_core_parse_source_text
from .transformer.sl_transformer import SLTransformer
from .grammar.parser_decode import is_compressed, preprocess_sl_text
from .models.ast_model import (
    BasePicture,
    DataType,
    ModuleTypeDef,
)
from .utils.text_processing import find_disallowed_comments
from collections.abc import Callable, Iterable
from enum import Enum
from .models.project_graph import ProjectFailure, ProjectGraph
from .cache import FileLookupCache, FileASTCache, get_cache_dir
from .validation import (
    StructuralValidationError,
    RawSourceValidationError,
    validate_transformed_basepicture,
)
import logging

# Create a module-level logger consistent with the CLI output.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",  # Just the message, no prefixes
    force=True,
)
log = logging.getLogger("SattLint")


ContextualFileLookup = Callable[[str, list[str], Path | None, str], Path | None]

_EXPECTED_UNAVAILABLE_LIBRARY_REASONS: dict[str, str] = {
    "controllib": "expected proprietary dependency",
}


def is_expected_unavailable_library(name: str) -> bool:
    return name.casefold() in _EXPECTED_UNAVAILABLE_LIBRARY_REASONS



def expected_unavailable_library_reason(name: str) -> str | None:
    return _EXPECTED_UNAVAILABLE_LIBRARY_REASONS.get(name.casefold())


@dataclass(frozen=True)
class SyntaxValidationResult:
    file_path: Path
    ok: bool
    stage: str
    message: str | None = None
    line: int | None = None
    column: int | None = None


class CodeMode(Enum):
    OFFICIAL = "official"  # .x code, .z deps
    DRAFT = "draft"  # .s code, .l deps


def code_ext(mode: CodeMode) -> str:
    return ".x" if mode is CodeMode.OFFICIAL else ".s"


def deps_ext(mode: CodeMode) -> str:
    return ".z" if mode is CodeMode.OFFICIAL else ".l"


def _record_project_failure(graph: ProjectGraph, name: str, exception: Exception) -> None:
    message = f"{name} parse/transform error: {exception}"
    line = getattr(exception, "line", None)
    column = getattr(exception, "column", None)
    length = getattr(exception, "length", None)
    if isinstance(exception, VisitError) and exception.orig_exc is not None:
        line = line if line is not None else getattr(exception.orig_exc, "line", None)
        column = column if column is not None else getattr(exception.orig_exc, "column", None)
        length = length if length is not None else getattr(exception.orig_exc, "length", None)
    graph.missing.append(message)
    graph.failures[name.casefold()] = ProjectFailure(
        name=name,
        message=message,
        line=line,
        column=column,
        length=length,
    )


def _record_project_warning(graph: ProjectGraph, name: str, message: str) -> None:
    graph.warnings.append(f"{name}: {message}")


BASE_DIR = Path(__file__).resolve().parent


class DebugMixin:
    debug: bool = False

    def dbg(self, msg: str) -> None:
        if self.debug:
            log.debug(f"[DEBUG] {msg}")


def _is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def create_sl_parser() -> Lark:
    """Compatibility wrapper that delegates parser creation to parser-core."""
    return parser_core_create_parser()


def _read_text_simple(path: Path) -> str:
    # If utf-8 fails, try cp1252 (covers characters like 'ø' / 0xF8)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp1252")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")


def _load_source_text(
    code_path: Path,
    *,
    debug: Callable[[str], None] | None = None,
) -> str:
    source_path = Path(code_path)
    if debug is not None:
        debug(f"Parsing file: {source_path}")

    src = _read_text_simple(source_path)
    if is_compressed(src):
        if debug is not None:
            debug("Compressed format detected; decoding before parsing")
        src, _ = preprocess_sl_text(src)
    return src


def parse_source_text(
    src: str,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    basepic = parser_core_parse_source_text(
        src,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture(basepic)

    return basepic


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    basepic = parser_core_parse_source_file(
        code_path,
        parser=parser,
        transformer=transformer,
        debug=debug,
    )
    validate_transformed_basepicture(basepic)
    return basepic


def _extract_error_position(exc: Exception) -> tuple[int | None, int | None]:
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if isinstance(exc, VisitError) and exc.orig_exc is not None:
        line = line if line is not None else getattr(exc.orig_exc, "line", None)
        column = column if column is not None else getattr(exc.orig_exc, "column", None)
    return line, column


def validate_single_file_syntax(code_path: Path) -> SyntaxValidationResult:
    target_path = Path(code_path)
    try:
        src = _load_source_text(target_path)
        violations = find_disallowed_comments(src)
        if violations:
            first = violations[0]
            raise RawSourceValidationError(
                "comment is only allowed inside EQUATIONBLOCK or SEQUENCE/OPENSEQUENCE blocks",
                line=first.start_line,
                column=first.start_col,
            )
        parse_source_text(src)
    except VisitError as exc:
        line, column = _extract_error_position(exc)
        message = str(exc.orig_exc) if exc.orig_exc is not None else str(exc)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="transform",
            message=message,
            line=line,
            column=column,
        )
    except StructuralValidationError as exc:
        line, column = _extract_error_position(exc)
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage="validation",
            message=str(exc),
            line=line,
            column=column,
        )
    except Exception as exc:
        line, column = _extract_error_position(exc)
        stage = "parse" if line is not None or column is not None else "validation"
        return SyntaxValidationResult(
            file_path=target_path,
            ok=False,
            stage=stage,
            message=str(exc),
            line=line,
            column=column,
        )

    return SyntaxValidationResult(file_path=target_path, ok=True, stage="ok")


# ---------- Loader with recursive resolution ----------
class SattLineProjectLoader(DebugMixin):
    def __init__(
        self,
        program_dir: Path,
        other_lib_dirs: Iterable[Path],
        abb_lib_dir: Path,
        mode: CodeMode,
        scan_root_only: bool,
        debug: bool,
        contextual_lookup: ContextualFileLookup | None = None,
    ):
        self.program_dir = program_dir
        self.other_lib_dirs = list(other_lib_dirs)
        self.abb_lib_dir = abb_lib_dir
        self.mode = mode
        self.scan_root_only = scan_root_only
        self.debug = debug
        self.contextual_lookup = contextual_lookup
        self.parser = create_sl_parser()  # reuse your grammar setup
        self.transformer = SLTransformer()  # reuse your transformer
        self._visited: set[str] = set()
        self._stack: set[str] = set()  # cycle protection
        self._ignored_dirs: set[Path] = set()
        self._lookup_cache = FileLookupCache(get_cache_dir())
        self._ast_cache = FileASTCache(get_cache_dir())
        self._base_indexes: dict[Path, dict[str, dict[str, Path]]] = {}
        self._lib_by_name: dict[str, str] = {}
        self.dbg(
            f"Selected mode={mode.value}, code_ext={code_ext(mode)}, deps_ext={deps_ext(mode)}"
        )
        self.dbg(f"Programs dir: {self.program_dir}")
        for i, ld in enumerate(self.other_lib_dirs, start=1):
            self.dbg(f"Lib {i}: {ld}")
        self.dbg(f"ABB lib dir: {self.abb_lib_dir}")

    def _is_ignored_base(self, base: Path) -> bool:
        try:
            base_r = base.resolve()
        except Exception:
            base_r = base
        return any(base_r == ign for ign in self._ignored_dirs)

    def _is_allowed_base(self, base: Path) -> bool:
        allowed = [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]
        try:
            base_r = base.resolve()
        except Exception:
            base_r = base
        for candidate in allowed:
            try:
                cand_r = candidate.resolve()
            except Exception:
                cand_r = candidate
            if base_r == cand_r:
                return True
        return False

    def _get_base_index(self, base: Path) -> dict[str, dict[str, Path]]:
        if base in self._base_indexes:
            return self._base_indexes[base]
        index: dict[str, dict[str, Path]] = {}
        if not base.exists() or not base.is_dir():
            self._base_indexes[base] = index
            return index

        for entry in base.iterdir():
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext not in {".s", ".x", ".l", ".z"}:
                continue
            stem = entry.stem.casefold()
            index.setdefault(stem, {})[ext] = entry

        self._base_indexes[base] = index
        return index

    def _find_in_index(
        self,
        *,
        base: Path,
        name: str,
        extensions: list[str],
    ) -> Path | None:
        index = self._get_base_index(base)
        entries = index.get(name.casefold())
        if not entries:
            return None
        for ext in extensions:
            p = entries.get(ext)
            if p is not None:
                return p
        return None

    def _add_to_index(self, base: Path, name: str, path: Path) -> None:
        index = self._get_base_index(base)
        index.setdefault(name.casefold(), {})[path.suffix.lower()] = path

    def _find_in_cached_base(
        self,
        *,
        kind: str,
        name: str,
        extensions: list[str],
    ) -> Path | None:
        cached = self._lookup_cache.get(kind, name, self.mode.value)
        if not cached:
            return None

        base = Path(cached.get("base_dir", ""))
        if not base or self._is_ignored_base(base):
            return None
        if not self._is_allowed_base(base):
            self._lookup_cache.forget(kind, name, self.mode.value)
            return None

        cached_ext = cached.get("ext")
        ordered_exts = [cached_ext] if cached_ext in extensions else []
        ordered_exts.extend(ext for ext in extensions if ext != cached_ext)

        for ext in ordered_exts:
            p = base / f"{name}{ext}"
            self.dbg(f"Checking cached {kind} file: {p} (exists={p.exists()})")
            if p.exists():
                self.dbg(f"Using cached {kind} file: {p}")
                return p

        self._lookup_cache.forget(kind, name, self.mode.value)
        return None

    def _find_code(self, name: str) -> Path | None:
        """
        Find code file with fallback support.
        In draft mode: try .s first, fallback to .x
        In official mode: only use .x
        """
        return self._find_code_with_context(name, requester_dir=None)

    def _find_code_with_context(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        extensions = [".s", ".x"] if self.mode == CodeMode.DRAFT else [".x"]

        if self.contextual_lookup is not None:
            resolved = self.contextual_lookup(name, extensions, requester_dir, "code")
            if resolved is not None:
                self.dbg(
                    f"Using contextual code file: {resolved} "
                    f"(requested by {requester_dir or self.program_dir})"
                )
                return resolved

        cached = self._find_in_cached_base(
            kind="code",
            name=name,
            extensions=extensions,
        )
        if cached is not None:
            return cached

        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            indexed = self._find_in_index(
                base=base,
                name=name,
                extensions=extensions,
            )
            if indexed is not None:
                self.dbg(f"Using code file: {indexed}")
                self._lookup_cache.set(
                    "code", name, self.mode.value, base, indexed.suffix.lower()
                )
                return indexed

            for ext in extensions:
                p = base / f"{name}{ext}"
                self.dbg(f"Checking code file: {p} (exists={p.exists()})")
                if p.exists():
                    self.dbg(f"Using code file: {p}")
                    self._lookup_cache.set("code", name, self.mode.value, base, ext)
                    self._add_to_index(base, name, p)
                    return p

        self.dbg(f"No code file found for '{name}' in mode={self.mode.value}")
        return None

    def _find_deps(self, name: str) -> Path | None:
        """
        Find deps file with fallback support.
        In draft mode: try .l first, fallback to .z
        In official mode: only use .z
        """
        return self._find_deps_with_context(name, requester_dir=None)

    def _find_deps_with_context(
        self,
        name: str,
        *,
        requester_dir: Path | None,
    ) -> Path | None:
        extensions = [".l", ".z"] if self.mode == CodeMode.DRAFT else [".z"]

        if self.contextual_lookup is not None:
            resolved = self.contextual_lookup(name, extensions, requester_dir, "deps")
            if resolved is not None:
                self.dbg(
                    f"Using contextual deps file: {resolved} "
                    f"(requested by {requester_dir or self.program_dir})"
                )
                return resolved

        cached = self._find_in_cached_base(
            kind="deps",
            name=name,
            extensions=extensions,
        )
        if cached is not None:
            return cached

        for base in [self.program_dir, *self.other_lib_dirs, self.abb_lib_dir]:
            if self._is_ignored_base(base):
                continue

            indexed = self._find_in_index(
                base=base,
                name=name,
                extensions=extensions,
            )
            if indexed is not None:
                self.dbg(f"Using deps file: {indexed}")
                self._lookup_cache.set(
                    "deps", name, self.mode.value, base, indexed.suffix.lower()
                )
                return indexed

            for ext in extensions:
                p = base / f"{name}{ext}"
                self.dbg(f"Checking deps file: {p} (exists={p.exists()})")
                if p.exists():
                    self.dbg(f"Using deps file: {p}")
                    self._lookup_cache.set("deps", name, self.mode.value, base, ext)
                    self._add_to_index(base, name, p)
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
        return _read_text_simple(path)

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
        try:
            ar = self.abb_lib_dir.resolve()
        except Exception:
            ar = self.abb_lib_dir
        if rp.is_relative_to(ar):
            return ar.name
        # Fallback: parent directory name
        return rp.parent.name

    def _record_library_name(self, name: str, code_path: Path) -> str:
        lib_name = self._library_name_for_path(code_path)
        self._lib_by_name[name.casefold()] = lib_name
        return lib_name

    def _parse_one(self, code_path: Path) -> BasePicture:
        return parser_core_parse_source_file(
            code_path,
            parser=self.parser,
            transformer=self.transformer,
            debug=self.dbg,
        )

    def _load_or_parse(self, code_path: Path) -> BasePicture:
        cached = self._ast_cache.load(code_path, self.mode.value)
        if cached is not None:
            self.dbg(f"Using cached AST for: {code_path}")
            return cached

        bp = self._parse_one(code_path)
        self._ast_cache.save(code_path, self.mode.value, bp)
        return bp

    def resolve(self, root_name: str, strict: bool = False) -> ProjectGraph:
        if self.scan_root_only:
            return self._resolve_root_only(root_name, strict)
        self.dbg(f"Resolving root: {root_name}")
        graph = ProjectGraph()
        self._visit(root_name, graph, strict, requester_dir=self.program_dir)
        self.dbg(f"Resolved ASTs: {list(graph.ast_by_name.keys())}")
        if graph.missing:
            self.dbg(f"Missing/failed: {graph.missing}")
        return graph

    def _resolve_root_only(self, root_name: str, strict: bool) -> ProjectGraph:
        graph = ProjectGraph()
        code_path = self._find_code(root_name)
        if not code_path:
            if is_expected_unavailable_library(root_name):
                graph.unavailable_libraries.add(root_name.casefold())
                return graph
            msg = f"Missing code file for '{root_name}' in mode={self.mode.value}"
            if strict:
                raise FileNotFoundError(msg)
            graph.missing.append(msg)
            return graph

        try:
            validation_warnings: list[str] = []
            bp = self._load_or_parse(code_path)
            if bp is None:
                msg = f"{root_name} transformed to no BasePicture (parse/transform issue?)"
                if strict:
                    raise RuntimeError(msg)
                graph.missing.append(msg)
                return graph
            validate_transformed_basepicture(
                bp,
                allow_unresolved_external_datatypes=True,
                enforce_unique_submodule_names=_is_within_directory(
                    code_path,
                    self.program_dir,
                ),
                allow_parameterless_module_mappings=True,
                warn_unknown_parameter_targets=True,
                warning_sink=validation_warnings.append,
            )
            for warning in validation_warnings:
                _record_project_warning(graph, root_name, warning)
            graph.ast_by_name[root_name] = bp
            lib_name = self._library_name_for_path(code_path)
            graph.index_from_basepic(
                bp, source_path=code_path, library_name=lib_name
            )  # collect any defs emitted in this files
            return graph
        except Exception as ex:
            for warning in locals().get("validation_warnings", []):
                _record_project_warning(graph, root_name, warning)
            if strict:
                raise
            _record_project_failure(graph, root_name, ex)
            return graph

    def _visit(
        self,
        name: str,
        graph: ProjectGraph,
        strict: bool,
        *,
        requester_dir: Path | None,
    ) -> None:
        key = name.lower()
        if key in self._visited or key in self._stack:
            return
        self._stack.add(key)

        # Resolve dependencies first (from non-vendor dirs only)
        deps_path = self._find_deps_with_context(name, requester_dir=requester_dir)
        dep_names = self._read_deps(deps_path) if deps_path else []
        dependency_requester = deps_path.parent if deps_path is not None else requester_dir

        # Visit each dep
        for dep in dep_names:
            self._visit(dep, graph, strict, requester_dir=dependency_requester)

        dep_libs: list[str] = []
        for dep in dep_names:
            dep_bp = graph.ast_by_name.get(dep)
            if dep_bp:
                origin_lib = getattr(dep_bp, "origin_lib", None)
                if origin_lib:
                    dep_libs.append(origin_lib)
                    continue
            cached_lib = self._lib_by_name.get(dep.casefold())
            if cached_lib:
                dep_libs.append(cached_lib)

        # Determine code path
        code_path = self._find_code_with_context(name, requester_dir=requester_dir)
        if code_path is not None:
            try:
                validation_warnings: list[str] = []
                bp = self._load_or_parse(code_path)
                if bp is not None:
                    validate_transformed_basepicture(
                        bp,
                        external_datatypes=tuple(graph.datatype_defs.values()),
                        external_moduletype_defs=tuple(graph.moduletype_defs.values()),
                        allow_unresolved_external_datatypes=True,
                        enforce_unique_submodule_names=_is_within_directory(
                            code_path,
                            self.program_dir,
                        ),
                        allow_parameterless_module_mappings=True,
                        warn_unknown_parameter_targets=True,
                        warning_sink=validation_warnings.append,
                    )
                    for warning in validation_warnings:
                        _record_project_warning(graph, name, warning)
                    graph.ast_by_name[name] = bp
                    lib_name = self._record_library_name(name, code_path)
                    graph.add_library_dependencies(lib_name, dep_libs)
                    graph.index_from_basepic(
                        bp, source_path=code_path, library_name=lib_name
                    )  # aggregate defs for global analysis [2]
                else:
                    msg = f"{name} transform produced no BasePicture (skipped)"
                    graph.missing.append(msg)
            except Exception as ex:
                for warning in locals().get("validation_warnings", []):
                    _record_project_warning(graph, name, warning)
                if strict:
                    raise
                _record_project_failure(graph, name, ex)
        else:
            # If we skipped vendor dir and the file exists there, mark as ignored vendor
            v_code = self._find_vendor_code(name)
            v_deps = self._find_vendor_deps(name)
            if v_code or v_deps:
                graph.ignored_vendor.append(f"{name} (vendor: {v_code or v_deps})")
                # Track as unavailable library for better error messages
                graph.unavailable_libraries.add(name.lower())
            elif is_expected_unavailable_library(name):
                graph.unavailable_libraries.add(name.lower())
            else:
                msg = f"Missing code file for '{name}' ({self.mode.value})"
                if strict:
                    raise FileNotFoundError(msg)
                graph.missing.append(msg)
                # Track as unavailable library
                graph.unavailable_libraries.add(name.lower())

        self._stack.remove(key)
        self._visited.add(key)


# ---------- Merge: build a synthetic “project” BasePicture ----------
def merge_project_basepicture(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
    """
    Create a single BasePicture that contains all DataType and ModuleTypeDef
    definitions from the root and its dependencies, so analyzers can resolve
    types across files without changing SLTransformer.
    """
    # Moduletype defs are keyed by (library, name) so same-name types from different
    # libraries are preserved in the merged BasePicture.
    merged_datatypes: list[DataType] = list(graph.datatype_defs.values())
    merged_modtypes: list[ModuleTypeDef] = list(graph.moduletype_defs.values())

    lib_deps = {
        lib: sorted(deps)
        for lib, deps in (graph.library_dependencies or {}).items()
    }

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
        library_dependencies=lib_deps,
    )


# ---------- Dump functions ----------
def _get_dump_dir() -> Path:
    """Get or create the dump directory."""
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
        for (_lib_key, _name_key, _file_key), mt in sorted(graph.moduletype_defs.items()):
            display = f"{mt.origin_lib}:{mt.name}" if mt.origin_lib else mt.name
            origin_info = f" (from {mt.origin_lib}/{mt.origin_file})" if mt.origin_lib or mt.origin_file else ""
            lines.append(f"  • {display}{origin_info}")

    if graph.library_dependencies:
        lines.append("\nLibrary dependencies:")
        for lib, deps in sorted(graph.library_dependencies.items()):
            dep_list = ", ".join(sorted(deps)) if deps else "<none>"
            lines.append(f"  • {lib} -> {dep_list}")

    if graph.missing:
        lines.append(f"\nMissing/Unresolved: {len(graph.missing)}")
        for msg in graph.missing:
            lines.append(f"  ⚠ {msg}")

    if graph.warnings:
        lines.append(f"\nWarnings: {len(graph.warnings)}")
        for msg in graph.warnings:
            lines.append(f"  ⚠ {msg}")

    if graph.ignored_vendor:
        lines.append(f"\nIgnored Vendor: {len(graph.ignored_vendor)}")
        for msg in graph.ignored_vendor:
            lines.append(f"  ⓘ {msg}")

    output = "\n".join(lines)
    filename.write_text(output, encoding="utf-8")

    print(f"\n✔ Dependency graph saved to: {filename}")
    print()
