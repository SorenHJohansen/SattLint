"""Parsing and project-loading engine for SattLine sources."""
from dataclasses import dataclass
from pathlib import Path
from lark import Lark, Tree
from lark.exceptions import VisitError
from .grammar import constants as const
from .transformer.sl_transformer import SLTransformer
from .grammar.parser_decode import is_compressed, preprocess_sl_text
from .models.ast_model import (
    BasePicture,
    DataType,
    Equation,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    Sequence,
    SFCAlternative,
    SFCBreak,
    SFCFork,
    SFCParallel,
    SFCStep,
    SFCSubsequence,
    SFCTransition,
    SFCTransitionSub,
    SingleModule,
    Variable,
)
from .utils.text_processing import strip_sl_comments
from collections.abc import Callable, Iterable
from enum import Enum
from .models.project_graph import ProjectGraph
from .cache import FileLookupCache, FileASTCache, get_cache_dir
import logging

# Create a module-level logger consistent with the CLI output.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",  # Just the message, no prefixes
    force=True,
)
log = logging.getLogger("SattLint")


class StructuralValidationError(ValueError):
    pass


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


BASE_DIR = Path(__file__).resolve().parent
GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar" / "sattline.lark"

if not GRAMMAR_PATH.exists():
    raise RuntimeError(f"Grammar file missing: {GRAMMAR_PATH}")


class DebugMixin:
    debug: bool = False

    def dbg(self, msg: str) -> None:
        if self.debug:
            log.debug(f"[DEBUG] {msg}")


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
        name: getattr(const, name)
        for name in dir(const)
        if name.startswith("GRAMMAR_VALUE_") or name.startswith("GRAMMAR_REGEX_")
    }
    # Format the grammar string by replacing placeholders with constant values
    formatted_grammar = grammar_text.format(**grammar_substitutions)

    # Now, initialize the Lark parser with the formatted grammar
    return Lark(
        formatted_grammar, start="start", parser="lalr", propagate_positions=True
    )


def _read_text_simple(path: Path) -> str:
    # If utf-8 fails, try cp1252 (covers characters like 'ø' / 0xF8)
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp1252")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")


def _identifier_length(name: str) -> int:
    if len(name) >= 2 and name.startswith("'") and name.endswith("'"):
        return len(name[1:-1])
    return len(name)


def _validate_identifier(name: str | None, context: str) -> None:
    if not name:
        return
    if _identifier_length(name) > 20:
        raise StructuralValidationError(
            f"{context} name {name!r} exceeds 20 characters"
        )


def _ensure_unique_names(names: list[str], context: str, kind: str) -> None:
    seen: dict[str, str] = {}
    for name in names:
        folded = name.casefold()
        if folded in seen:
            raise StructuralValidationError(
                f"{context} has duplicate {kind} names {seen[folded]!r} and {name!r}"
            )
        seen[folded] = name


def _collect_sequence_labels(nodes: list[object], labels: dict[str, str], context: str) -> None:
    for node in nodes:
        label: str | None = None
        if isinstance(node, SFCStep):
            label = node.name
        elif isinstance(node, SFCTransition) and node.name:
            label = node.name
        elif isinstance(node, SFCSubsequence):
            label = node.name
        elif isinstance(node, SFCTransitionSub):
            label = node.name

        if label:
            folded = label.casefold()
            if folded in labels:
                raise StructuralValidationError(
                    f"{context} has duplicate sequence labels {labels[folded]!r} and {label!r}"
                )
            labels[folded] = label

        if isinstance(node, SFCAlternative):
            for branch in node.branches:
                _collect_sequence_labels(branch, labels, context)
        elif isinstance(node, SFCParallel):
            for branch in node.branches:
                _collect_sequence_labels(branch, labels, context)
        elif isinstance(node, SFCSubsequence):
            _collect_sequence_labels(node.body, labels, context)
        elif isinstance(node, SFCTransitionSub):
            _collect_sequence_labels(node.body, labels, context)


def _iter_variable_refs(node: object):
    if isinstance(node, dict) and const.KEY_VAR_NAME in node:
        yield node
        return

    if isinstance(node, Tree):
        for child in node.children:
            yield from _iter_variable_refs(child)
        return

    if isinstance(node, tuple):
        for item in node:
            yield from _iter_variable_refs(item)
        return

    if isinstance(node, list):
        for item in node:
            yield from _iter_variable_refs(item)


def _validate_variable_refs(
    node: object,
    env: dict[str, Variable],
    context: str,
) -> None:
    for ref in _iter_variable_refs(node):
        state = ref.get("state")
        if not state:
            continue

        full_name = ref[const.KEY_VAR_NAME]
        base_name = str(full_name).split(".", 1)[0]
        variable = env.get(base_name.casefold())
        if variable is not None and not variable.state:
            raise StructuralValidationError(
                f"{context} uses {state.upper()} on non-STATE variable {base_name!r}"
            )


def _validate_call_arg_node(node: object, context: str) -> None:
    if isinstance(node, str):
        raise StructuralValidationError(
            f"{context} uses string literal {node!r}; string literals are only allowed in parameter connections"
        )

    if isinstance(node, Tree):
        for child in node.children:
            _validate_call_arg_node(child, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_call_arg_node(item, context)
        return

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return

        for value in node.values():
            _validate_call_arg_node(value, context)
        return

    if isinstance(node, tuple):
        if len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
            fn_name = node[1]
            args = node[2] or []
            for index, arg in enumerate(args, start=1):
                _validate_call_arg_node(
                    arg,
                    f"{context} call {fn_name!r} argument {index}",
                )
            return

        for item in node:
            _validate_call_arg_node(item, context)


def _validate_no_string_literals_in_calls(node: object, context: str) -> None:
    if isinstance(node, Tree):
        for child in node.children:
            _validate_no_string_literals_in_calls(child, context)
        return

    if isinstance(node, list):
        for item in node:
            _validate_no_string_literals_in_calls(item, context)
        return

    if isinstance(node, dict):
        if const.KEY_VAR_NAME in node:
            return

        for value in node.values():
            _validate_no_string_literals_in_calls(value, context)
        return

    if isinstance(node, tuple):
        if len(node) == 3 and node[0] == const.KEY_FUNCTION_CALL:
            fn_name = node[1]
            args = node[2] or []
            for index, arg in enumerate(args, start=1):
                _validate_call_arg_node(
                    arg,
                    f"{context} call {fn_name!r} argument {index}",
                )
            return

        for item in node:
            _validate_no_string_literals_in_calls(item, context)


def _validate_statement_list(
    statements: list[object],
    env: dict[str, Variable],
    context: str,
) -> None:
    for statement in statements:
        _validate_variable_refs(statement, env, context)
        _validate_no_string_literals_in_calls(statement, context)


def _validate_code_blocks(code, env: dict[str, Variable], context: str) -> None:
    _validate_statement_list(code.enter, env, f"{context} ENTERCODE")
    _validate_statement_list(code.active, env, f"{context} ACTIVECODE")
    _validate_statement_list(code.exit, env, f"{context} EXITCODE")


def _validate_sequence_nodes(
    nodes: list[object],
    context: str,
    *,
    labels: dict[str, str],
    env: dict[str, Variable],
    require_init_step: bool,
) -> None:
    previous_step: str | None = None
    init_steps = 0

    if require_init_step:
        if not nodes or not isinstance(nodes[0], SFCStep) or nodes[0].kind != "init":
            raise StructuralValidationError(
                f"{context} must start with exactly one SEQINITSTEP"
            )

    for index, node in enumerate(nodes):
        if isinstance(node, SFCStep):
            _validate_identifier(node.name, f"{context} step")
            if node.kind == "init":
                init_steps += 1
                if index != 0:
                    raise StructuralValidationError(
                        f"{context} has SEQINITSTEP {node.name!r} outside the first position"
                    )
            if previous_step is not None:
                raise StructuralValidationError(
                    f"{context} has step {node.name!r} immediately after step "
                    f"{previous_step!r} without an intervening transition"
                )
            _validate_code_blocks(node.code, env, f"{context} step {node.name!r}")
            previous_step = node.name
            continue

        previous_step = None

        if isinstance(node, SFCTransition):
            _validate_identifier(node.name, f"{context} transition")
        elif isinstance(node, SFCTransitionSub):
            _validate_identifier(node.name, f"{context} transition-sub")
            _validate_sequence_nodes(
                node.body,
                f"{context} transition-sub {node.name!r}",
                labels=labels,
                env=env,
                require_init_step=False,
            )
        elif isinstance(node, SFCSubsequence):
            _validate_identifier(node.name, f"{context} subsequence")
            _validate_sequence_nodes(
                node.body,
                f"{context} subsequence {node.name!r}",
                labels=labels,
                env=env,
                require_init_step=False,
            )
        elif isinstance(node, SFCAlternative):
            for index, branch in enumerate(node.branches, start=1):
                _validate_sequence_nodes(
                    branch,
                    f"{context} alternative branch {index}",
                    labels=labels,
                    env=env,
                    require_init_step=False,
                )
        elif isinstance(node, SFCParallel):
            for index, branch in enumerate(node.branches, start=1):
                _validate_sequence_nodes(
                    branch,
                    f"{context} parallel branch {index}",
                    labels=labels,
                    env=env,
                    require_init_step=False,
                )
        elif isinstance(node, SFCFork):
            _validate_identifier(node.target, f"{context} fork target")
            if node.target.casefold() not in labels:
                raise StructuralValidationError(
                    f"{context} has SEQFORK target {node.target!r} that does not exist in the sequence"
                )
        elif isinstance(node, SFCBreak):
            continue

    if require_init_step and init_steps != 1:
        raise StructuralValidationError(
            f"{context} must contain exactly one SEQINITSTEP"
        )


def _validate_module_code(
    modulecode: ModuleCode | None,
    context: str,
    env: dict[str, Variable],
) -> None:
    if modulecode is None:
        return

    for equation in modulecode.equations or []:
        if isinstance(equation, Equation):
            _validate_identifier(equation.name, f"{context} equation")
            _validate_statement_list(
                equation.code or [],
                env,
                f"{context} equation {equation.name!r}",
            )

    for sequence in modulecode.sequences or []:
        if isinstance(sequence, Sequence):
            _validate_identifier(sequence.name, f"{context} sequence")
            labels: dict[str, str] = {}
            _collect_sequence_labels(sequence.code or [], labels, f"{context} sequence {sequence.name!r}")
            _validate_sequence_nodes(
                sequence.code or [],
                f"{context} sequence {sequence.name!r}",
                labels=labels,
                env=env,
                require_init_step=True,
            )


def _validate_variable_list(variables: list[Variable] | None, context: str) -> None:
    names = [variable.name for variable in variables or []]
    _ensure_unique_names(names, context, "variable")
    for variable in variables or []:
        _validate_identifier(variable.name, f"{context} variable")


def _validate_datatypes(datatypes: list[DataType] | None, context: str) -> None:
    _ensure_unique_names([datatype.name for datatype in datatypes or []], context, "datatype")
    for datatype in datatypes or []:
        _validate_identifier(datatype.name, f"{context} datatype")
        _validate_variable_list(datatype.var_list, f"{context} datatype {datatype.name!r}")


def _merge_env(parent_env: dict[str, Variable], variables: list[Variable] | None) -> dict[str, Variable]:
    merged = dict(parent_env)
    for variable in variables or []:
        merged[variable.name.casefold()] = variable
    return merged


def _validate_module(
    module: object,
    context: str,
    parent_env: dict[str, Variable],
) -> None:
    if isinstance(module, SingleModule):
        _validate_identifier(module.header.name, f"{context} module")
        module_context = f"{context} module {module.header.name!r}"
        _validate_variable_list(module.moduleparameters, module_context)
        _validate_variable_list(module.localvariables, module_context)
        env = _merge_env(parent_env, module.moduleparameters)
        env = _merge_env(env, module.localvariables)
        _validate_module_code(module.modulecode, module_context, env)
        for submodule in module.submodules or []:
            _validate_module(submodule, module_context, env)
        return

    if isinstance(module, FrameModule):
        _validate_identifier(module.header.name, f"{context} frame")
        module_context = f"{context} frame {module.header.name!r}"
        _validate_module_code(module.modulecode, module_context, parent_env)
        for submodule in module.submodules or []:
            _validate_module(submodule, module_context, parent_env)
        return

    if isinstance(module, ModuleTypeInstance):
        _validate_identifier(module.header.name, f"{context} module instance")
        _validate_identifier(module.moduletype_name, f"{context} module type reference")
        return


def validate_transformed_basepicture(basepic: BasePicture) -> None:
    _validate_identifier(basepic.header.name, "BasePicture")
    _validate_variable_list(basepic.localvariables, "BasePicture")
    _validate_datatypes(basepic.datatype_defs, "BasePicture")
    _ensure_unique_names(
        [moduletype.name for moduletype in basepic.moduletype_defs or []],
        "BasePicture",
        "moduletype",
    )

    base_env = _merge_env({}, basepic.localvariables)

    for moduletype in basepic.moduletype_defs or []:
        if isinstance(moduletype, ModuleTypeDef):
            _validate_identifier(moduletype.name, "BasePicture moduletype")
            moduletype_context = f"BasePicture moduletype {moduletype.name!r}"
            _validate_variable_list(moduletype.moduleparameters, moduletype_context)
            _validate_variable_list(moduletype.localvariables, moduletype_context)
            env = _merge_env(base_env, moduletype.moduleparameters)
            env = _merge_env(env, moduletype.localvariables)
            _validate_module_code(moduletype.modulecode, moduletype_context, env)
            for submodule in moduletype.submodules or []:
                _validate_module(submodule, moduletype_context, env)

    _validate_module_code(basepic.modulecode, "BasePicture", base_env)

    for submodule in basepic.submodules or []:
        _validate_module(submodule, "BasePicture", base_env)


def parse_source_file(
    code_path: Path,
    *,
    parser: Lark | None = None,
    transformer: SLTransformer | None = None,
    debug: Callable[[str], None] | None = None,
) -> BasePicture:
    source_path = Path(code_path)
    if debug is not None:
        debug(f"Parsing file: {source_path}")

    src = _read_text_simple(source_path)
    if is_compressed(src):
        if debug is not None:
            debug("Compressed format detected; decoding before parsing")
        src, _ = preprocess_sl_text(src)

    cleaned = strip_sl_comments(src)
    active_parser = parser if parser is not None else create_sl_parser()
    active_transformer = transformer if transformer is not None else SLTransformer()
    tree = active_parser.parse(cleaned)

    if debug is not None:
        debug("Parse OK, transforming with SLTransformer")

    basepic = active_transformer.transform(tree)
    try:
        setattr(basepic, "parse_tree", tree)
    except Exception:
        if debug is not None:
            debug("BasePicture does not allow dynamic attributes; parse tree not attached")

    if debug is not None:
        debug(f"Transform result type: {type(basepic).__name__}")

    if not isinstance(basepic, BasePicture):
        raise RuntimeError(
            "Transform result is not BasePicture; check transformer.start()"
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
        parse_source_file(target_path)
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
    ):
        self.program_dir = program_dir
        self.other_lib_dirs = list(other_lib_dirs)
        self.abb_lib_dir = abb_lib_dir
        self.mode = mode
        self.scan_root_only = scan_root_only
        self.debug = debug
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
        extensions = [".s", ".x"] if self.mode == CodeMode.DRAFT else [".x"]

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
        extensions = [".l", ".z"] if self.mode == CodeMode.DRAFT else [".z"]

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
        return parse_source_file(
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
            bp = self._load_or_parse(code_path)
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
        code_path = self._find_code(name)
        if code_path is not None:
            try:
                bp = self._load_or_parse(code_path)
                if bp is not None:
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
                if strict:
                    raise
                graph.missing.append(f"{name} parse/transform error: {ex}")
        else:
            # If we skipped vendor dir and the file exists there, mark as ignored vendor
            v_code = self._find_vendor_code(name)
            v_deps = self._find_vendor_deps(name)
            if v_code or v_deps:
                graph.ignored_vendor.append(f"{name} (vendor: {v_code or v_deps})")
                # Track as unavailable library for better error messages
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

    if graph.ignored_vendor:
        lines.append(f"\nIgnored Vendor: {len(graph.ignored_vendor)}")
        for msg in graph.ignored_vendor:
            lines.append(f"  ⓘ {msg}")

    output = "\n".join(lines)
    filename.write_text(output, encoding="utf-8")

    print(f"\n✔ Dependency graph saved to: {filename}")
    print()
