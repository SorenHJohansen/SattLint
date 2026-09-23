# pyright: reportPrivateUsage=false
"""Parser-backed project loading adapter (Phase 5).

This module is the thin bridge between ``sattline-parser`` and the SattLint
``ProjectGraph`` structures the application layer expects. It holds no SattLine
resolution logic of its own: file discovery, per-artifact draft/official
fallback, dependency recursion and program parsing are delegated to
``sattline_parser.project`` (``SattLineProject`` / ``ProjectLookup`` /
``read_dependency_names``), which mirrors the behaviour the old recursive
loader used to own.

What stays SattLint-side, per program, is the work that never belonged to the
parser: semantic validation, graphics companion attachment, library naming,
dependency-version conflict detection and definition indexing into the
``ProjectGraph``.

The ``SattLineProjectLoader`` shell is retired (final layer of the Phase 5/6
plan); the application seams built on it (``load_project``, reverse-library
consumers, ``load_program_ast``) call this adapter directly through
``build_parser_binding`` + ``load_parser_project`` + ``convert_project_into_graph``.

Known behaviour approximations (unchanged SattLint semantics in practice):

* Programs the parser silently drops under ``strict=False`` (missing code file
  or unparseable source) surface as *missing* SattLint-side; the old loader
  distinguished missing-vs-parse-failure. No corpus fixture exercises the
  parse-failure branch.
* The parser resolves a program's graph and ``.g``/``.y`` companion before
  SattLint re-attaches graphics via ``attach_graphics_companion``; SattLint
  keeps full graphics ownership.
* The parser load is hermetic (``cache_dir=None``); the parser runs its own
  program-level caches from a cache directory SattLint never passes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from sattline_parser.models.ast_model import BasePicture
from sattline_parser.project import (
    LoadMode,
    ProjectLookup,
    SattLineProgram,
    SattLineProject,
)
from sattline_parser.project import read_dependency_names as parser_read_dependency_names

from ..core.syntax import (
    CodeMode,
    mark_local_validation,
)
from ..core.syntax import (
    has_current_local_validation as _has_current_local_validation,
)
from ..graphics.graphics_helpers import attach_graphics_companion
from ..models.project_graph import ProjectGraph
from ..resolution.dependency_versions import collect_dependency_version_conflicts
from ..validation import (
    StructuralValidationError,
    validate_transformed_basepicture,
    validate_transformed_basepicture_dependency_context,
)
from ..validation.shared import ValidationWarning
from .loading_support import (
    record_project_failure as _record_project_failure,
)
from .loading_support import (
    record_project_warning as _record_project_warning,
)

LoadStageTimingSink = Callable[[str, str, float], None]


def _project_memo_factory() -> dict[tuple[str, bool], SattLineProject]:
    return {}


def _indexed_names_factory() -> set[str]:
    return set()


class CircularDependencyError(RuntimeError):
    """Exception raised when circular dependencies are detected."""

    def __init__(self, library: str, cycle_path: list[str]):
        self.library = library
        self.cycle_path = cycle_path
        super().__init__(f"Circular dependency detected: {' -> '.join([*cycle_path, cycle_path[0]])}")


class DependencyVersionCompatibilityError(RuntimeError):
    """Exception raised when conflicting dependency datecodes are detected."""

    def __init__(self, conflicts: list[str]):
        self.conflicts = conflicts
        super().__init__(f"Dependency version compatibility check failed: {'; '.join(conflicts)}")


def record_missing_library(
    graph: ProjectGraph,
    *,
    name: str,
    mode: str,
    strict: bool,
    requester: str | None = None,
) -> None:
    if requester and requester.casefold() != name.casefold():
        message = f"Missing code file for dependency '{name}' referenced by '{requester}' ({mode})"
    else:
        message = f"Missing code file for '{name}' ({mode})"
    if strict:
        raise FileNotFoundError(message)
    graph.missing.append(message)
    graph.unavailable_libraries.add(name.casefold())


@dataclass(frozen=True)
class ParserProjectBinding:
    """SattLint-side runtime configuration consumed by the adapter.

    Carries the loader config plus the runtime sinks the loader shell binds
    (status updates, stage/graphics timing), keeping the adapter free of loader
    internals.
    """

    program_dir: Path
    other_lib_dirs: tuple[Path, ...]
    abb_lib_dir: Path | None
    mode: CodeMode
    refresh_mode: str
    debug_fn: Callable[[str], None] | None = None
    status_update_fn: Callable[[str], None] | None = None
    stage_timing_sink: LoadStageTimingSink | None = None
    graphics_timing_sink: Callable[[str, str, float], None] | None = None
    # Session-scoped adapter state, shared across every load/visit in one
    # binding lifetime. These are the analogues of the old loader shell's
    # ``_visited`` / ``_lib_by_name`` / status dedupe, and are excluded from
    # equality/repr so the frozen binding stays a value-like configuration.
    _project_memo: dict[tuple[str, bool], SattLineProject] = field(
        default_factory=_project_memo_factory, compare=False, repr=False
    )
    _indexed_names: set[str] = field(default_factory=_indexed_names_factory, compare=False, repr=False)
    _lookup: ProjectLookup | None = field(default=None, compare=False, repr=False)
    _last_status_message: str | None = field(default=None, compare=False, repr=False)

    @property
    def roots(self) -> tuple[Path, ...]:
        return tuple(path for path in (self.program_dir, *self.other_lib_dirs, self.abb_lib_dir) if path is not None)

    def parser_mode(self) -> LoadMode:
        return LoadMode(self.mode.value)

    def new_lookup(self) -> ProjectLookup:
        # Reuse one lookup per binding: its per-root ``SourceIndex`` memo is
        # built lazily and would otherwise be re-created on every find call.
        lookup = self._lookup
        if lookup is None:
            lookup = ProjectLookup(self.roots, self.parser_mode(), debug=self.debug_fn)
            object.__setattr__(self, "_lookup", lookup)
        return lookup


def load_parser_project(
    binding: ParserProjectBinding,
    targets: Sequence[str],
    *,
    strict: bool,
) -> SattLineProject:
    """Load ``targets`` through the parser, hermetically (no parser-side cache).

    ``cache_dir=None`` keeps the load fully in-memory; the project-level
    analysis-result cache remains SattLint's replay/refresh layer.

    Single-target loads are memoized per binding (keyed by casefolded target
    and strictness), the analogue of the old loader shell's ``_visited`` set:
    the same target visited again within one load (e.g. a reverse-library
    consumer reachable through two different dependency files) is resolved and
    parsed only once.
    """
    if len(targets) == 1:
        memo_key = (targets[0].casefold(), strict)
        memoized = binding._project_memo.get(memo_key)
        if memoized is not None:
            return memoized
        project = _load_project(binding, targets, strict=strict)
        binding._project_memo[memo_key] = project
        return project
    return _load_project(binding, targets, strict=strict)


def _load_project(
    binding: ParserProjectBinding,
    targets: Sequence[str],
    *,
    strict: bool,
) -> SattLineProject:
    return SattLineProject.load(
        roots=binding.roots,
        mode=binding.parser_mode(),
        targets=targets,
        strict=strict,
        debug=binding.debug_fn,
        cache_dir=None,
    )


def find_code_path(binding: ParserProjectBinding, name: str, requester_dir: Path | None) -> Path | None:
    return binding.new_lookup().find_code(name, requester_dir=requester_dir)


def find_dependency_path(binding: ParserProjectBinding, name: str, requester_dir: Path | None) -> Path | None:
    return binding.new_lookup().find_deps(name, requester_dir=requester_dir)


def read_dependency_names(deps_path: Path) -> tuple[str, ...]:
    return parser_read_dependency_names(deps_path)


def convert_project_into_graph(
    project: SattLineProject,
    graph: ProjectGraph,
    *,
    binding: ParserProjectBinding,
    root_name: str,
    strict: bool,
    lib_names: dict[str, str] | None = None,
    extra_roots: Sequence[str] = (),
) -> None:
    """Translate a loaded parser project into a populated ``ProjectGraph``.

    Programs are processed in the parser's registry order, which is a valid
    post-order (dependencies are loaded before their consumers), so each
    program's ``external_datatypes``/``external_moduletype_defs`` and version
    checks see its dependencies already indexed. Programs already present in
    ``graph.ast_by_name`` (e.g. reverse-library consumers loaded earlier) are
    skipped rather than re-validated.

    ``extra_roots`` lets one batched parser load treat several reverse-library
    consumers as roots in a single pass: each is validated as a root (matching
    the per-target flow) while shared dependency programs are parsed and
    indexed exactly once.

    ``lib_names`` mirrors the old loader's ``_lib_by_name`` cache: a
    name-to-library mapping owned by the calling loader that carries across
    ``resolve``/``visit_target`` calls. Because ``BasePicture.header.name`` is
    always the literal ``"BasePicture"`` keyword (the real identity lives on
    ``program_name``), dependency-library resolution cannot rely on
    ``root_library_name_for_name`` and goes through this map — the same
    mechanism the recursive loader used.

    A target that the parser dropped (no code found) is recorded as missing so
    ``load_project``'s target-error report keeps its ``missing`` payload.
    """
    _raise_on_cycle(project)
    local_lib_names = {} if lib_names is None else lib_names
    indexed_names = binding._indexed_names
    root_names = [root_name, *extra_roots]
    root_keys = frozenset(name.casefold() for name in root_names)
    for program in project.programs().values():
        if _graph_has_name(graph, program.name, indexed_names):
            continue
        _index_program(
            program,
            graph,
            binding=binding,
            root_keys=root_keys,
            strict=strict,
            lib_names=local_lib_names,
            indexed_names=indexed_names,
        )
    _record_missing_dependencies(project, graph, binding=binding, strict=strict)
    for name in root_names:
        if _graph_has_name(graph, name, indexed_names) or name.casefold() in graph.unavailable_libraries:
            continue
        record_missing_library(
            graph,
            name=name,
            mode=binding.mode.value,
            strict=strict,
            requester=None,
        )


def _index_program(
    program: SattLineProgram,
    graph: ProjectGraph,
    *,
    binding: ParserProjectBinding,
    root_keys: frozenset[str],
    strict: bool,
    lib_names: dict[str, str],
    indexed_names: set[str],
) -> None:
    name = program.name
    code_path = program.source_path
    if code_path is None:
        return
    is_root = name.casefold() in root_keys
    validation_warnings: list[ValidationWarning] = []
    try:
        try:
            _emit_status(binding, f"Loading {name}: validating {code_path.name}")
            validation_started_at = perf_counter()
            mark_local_validation(program.code)
            _validate_program(
                program.code,
                graph,
                is_root=is_root,
                strict=strict,
                refresh_mode=binding.refresh_mode,
                warning_sink=validation_warnings.append,
            )
            if binding.stage_timing_sink is not None:
                binding.stage_timing_sink(name, "validate", perf_counter() - validation_started_at)
        except StructuralValidationError as ex:
            if is_root:
                raise
            _record_project_warning(graph, name, f"validation warning: {ex}")
        for warning in validation_warnings:
            _record_project_warning(graph, name, warning)
        _emit_status(binding, f"Loading {name}: validation complete")
        graph.ast_by_name[name] = program.code
        indexed_names.add(name.casefold())
        if binding.refresh_mode == "ast-only":
            return

        _emit_status(binding, f"Loading {name}: checking graphics companion")
        _emit_status(binding, f"Loading {name}: processing graphics companion")

        def _status_cb(msg: str) -> None:
            _emit_status(binding, f"Loading {name}: {msg}")

        attach_graphics_companion(
            program.code,
            code_path=code_path,
            mode=binding.mode,
            graph=graph,
            owner_name=name,
            timing_sink=binding.graphics_timing_sink,
            status_callback=_status_cb,
        )
        _emit_status(binding, f"Loading {name}: recording library")
        library_name = _library_name_for_path(code_path, binding)
        lib_names[name.casefold()] = library_name
        _emit_status(binding, f"Loading {name}: checking version conflicts")
        version_conflicts = collect_dependency_version_conflicts(
            graph,
            program.code,
            library_name=library_name,
            source_path=code_path,
        )
        if version_conflicts:
            if strict:
                raise DependencyVersionCompatibilityError(version_conflicts)
            for conflict in version_conflicts:
                _record_project_warning(graph, name, f"version compatibility warning: {conflict}")
        _emit_status(binding, f"Loading {name}: adding deps")
        dep_libs = [
            lib
            for dep in program.dependencies
            if (lib := graph.root_library_name_for_name(dep) or lib_names.get(dep.casefold()))
        ]
        graph.add_library_dependencies(library_name, dep_libs)
        _emit_status(binding, f"Loading {name}: indexing definitions")
        index_started_at = perf_counter()
        graph.index_from_basepic(program.code, source_path=code_path, library_name=library_name)
        if binding.stage_timing_sink is not None:
            binding.stage_timing_sink(name, "index", perf_counter() - index_started_at)
    except Exception as ex:
        for warning in validation_warnings:
            _record_project_warning(graph, name, warning)
        if strict:
            raise
        _record_project_failure(graph, name, ex)


def _validate_program(
    bp: BasePicture,
    graph: ProjectGraph,
    *,
    is_root: bool,
    strict: bool,
    refresh_mode: str,
    warning_sink: Callable[[ValidationWarning], None],
) -> None:
    external_datatypes = () if refresh_mode == "ast-only" else tuple(graph.datatype_defs.values())
    external_moduletype_defs = () if refresh_mode == "ast-only" else tuple(graph.moduletype_defs.values())
    if not is_root and _has_current_local_validation(bp):
        validate_transformed_basepicture_dependency_context(
            bp,
            external_datatypes=external_datatypes,
            external_moduletype_defs=external_moduletype_defs,
            allow_parameterless_module_mappings=True,
            warn_unknown_parameter_targets=refresh_mode != "ast-only",
            warn_incompatible_parameter_mappings=refresh_mode != "ast-only",
            warning_sink=warning_sink,
        )
    else:
        validate_transformed_basepicture(
            bp,
            external_datatypes=external_datatypes,
            external_moduletype_defs=external_moduletype_defs,
            allow_unresolved_external_datatypes=True if refresh_mode == "ast-only" else not strict,
            enforce_unique_submodule_names=False,
            allow_parameterless_module_mappings=True,
            warn_unknown_parameter_targets=refresh_mode != "ast-only",
            warn_incompatible_parameter_mappings=refresh_mode != "ast-only",
            warning_sink=warning_sink,
        )


def _library_name_for_path(code_path: Path, binding: ParserProjectBinding) -> str:
    resolved_path = _resolved_path(code_path)
    program_root = _resolved_path(binding.program_dir)
    if _is_relative_to(resolved_path, program_root):
        return program_root.name
    for library_dir in binding.other_lib_dirs:
        resolved_library_dir = _resolved_path(library_dir)
        if _is_relative_to(resolved_path, resolved_library_dir):
            return resolved_library_dir.name
    if binding.abb_lib_dir is not None:
        resolved_abb_root = _resolved_path(binding.abb_lib_dir)
        if _is_relative_to(resolved_path, resolved_abb_root):
            return resolved_abb_root.name
    return resolved_path.parent.name


def _resolved_path(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _raise_on_cycle(project: SattLineProject) -> None:
    registry = project.programs()
    original_name = {key: program.name for key, program in registry.items()}
    adjacency = {
        key: [dependency for dependency in program.dependencies if dependency.casefold() in registry]
        for key, program in registry.items()
    }
    state = dict.fromkeys(registry, _WHITE)
    for start in registry:
        if state[start] != _WHITE:
            continue
        state[start] = _GRAY
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack:
            key, next_index = stack[-1]
            dependencies = adjacency[key]
            if next_index >= len(dependencies):
                state[key] = _BLACK
                stack.pop()
                continue
            stack[-1] = (key, next_index + 1)
            child = dependencies[next_index]
            child_key = child.casefold()
            if state[child_key] == _GRAY:
                cycle_path = [original_name[entry[0]] for entry in stack]
                cycle_keys = [entry[0] for entry in stack]
                cycle_start = cycle_keys.index(child_key)
                raise CircularDependencyError(child, cycle_path[cycle_start:])
            if state[child_key] == _WHITE:
                state[child_key] = _GRAY
                stack.append((child_key, 0))


_WHITE = 0
_GRAY = 1
_BLACK = 2


def _record_missing_dependencies(
    project: SattLineProject,
    graph: ProjectGraph,
    *,
    binding: ParserProjectBinding,
    strict: bool,
) -> None:
    for program in project.programs().values():
        for dependency in program.dependencies:
            if dependency.casefold() in project or dependency.casefold() in graph.unavailable_libraries:
                continue
            record_missing_library(
                graph,
                name=dependency,
                mode=binding.mode.value,
                strict=strict,
                requester=program.name,
            )


def _graph_has_name(graph: ProjectGraph, name: str, indexed_names: set[str]) -> bool:
    key = name.casefold()
    if key in indexed_names:
        return True
    # Fallback for graphs populated outside this binding (e.g. test doubles).
    return any(existing.casefold() == key for existing in graph.ast_by_name)


def _emit_status(binding: ParserProjectBinding, message: str) -> None:
    if binding.status_update_fn is None:
        return
    text = str(message).strip()
    if not text or text == binding._last_status_message:
        return
    object.__setattr__(binding, "_last_status_message", text)
    binding.status_update_fn(text)


__all__ = [
    "CircularDependencyError",
    "DependencyVersionCompatibilityError",
    "ParserProjectBinding",
    "convert_project_into_graph",
    "find_code_path",
    "find_dependency_path",
    "load_parser_project",
    "mark_local_validation",
    "read_dependency_names",
    "record_missing_library",
]
