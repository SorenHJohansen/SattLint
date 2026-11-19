"""Project graph and indexing helpers for SattLine projects."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from ..parser_api import BasePicture, DataType, ModuleTypeDef

if TYPE_CHECKING:
    from ..graphics.picture_display_paths import PictureDisplayOccurrence, PictureDisplayPathDiagnostic
    from ..graphics.picture_display_runtime import CompositeRecordOccurrence
    from ..graphics.validation import GraphicsCompositeRecord, PictureDisplayRecord
    from ..parser_api import GraphicsBinding, GraphicsMessage


def _ast_by_name_factory() -> dict[str, BasePicture]:
    return {}


def _moduletype_defs_factory() -> dict[tuple[str, str, str], ModuleTypeDef]:
    return {}


def _datatype_defs_factory() -> dict[tuple[str, str, str], DataType]:
    return {}


def _library_dependencies_factory() -> dict[str, set[str]]:
    return {}


def _missing_factory() -> list[str]:
    return []


def _warnings_factory() -> list[str]:
    return []


def _root_origins_factory() -> dict[str, RootOrigin]:
    return {}


def _failures_factory() -> dict[str, ProjectFailure]:
    return {}


def _unavailable_libraries_factory() -> set[str]:
    return set()


def _source_files_factory() -> set[Path]:
    return set()


def _source_file_libraries_factory() -> dict[Path, str]:
    return {}


def _analysis_manifest_files_factory() -> frozenset[Path]:
    return frozenset()


def _timings_factory() -> dict[str, float]:
    return {}


@dataclass(frozen=True)
class GraphicsAttachments:
    """SattLint's graphics view of one program, kept off the parser's AST.

    The parser owns the companion scan; this value carries the correlated
    record shapes the analyzers read. It is keyed by program name on
    :attr:`ProjectGraph.graphics_attachments`.
    """

    file_name: str | None = None
    bindings: tuple[GraphicsBinding, ...] = ()
    messages: tuple[GraphicsMessage, ...] = ()
    composite_records: tuple[GraphicsCompositeRecord, ...] = ()
    composite_occurrences: tuple[CompositeRecordOccurrence, ...] = ()
    picture_display_records: tuple[PictureDisplayRecord, ...] = ()
    picture_display_occurrences: tuple[PictureDisplayOccurrence, ...] = ()
    #: Path diagnostics computed while the companion was attached. Reading them
    #: back keeps the analyzer from diagnosing the same occurrences twice.
    picture_display_diagnostics: tuple[PictureDisplayPathDiagnostic, ...] = ()
    picture_display_diagnostics_computed: bool = False


EMPTY_GRAPHICS_ATTACHMENTS = GraphicsAttachments()


def _graphics_attachments_factory() -> dict[str, GraphicsAttachments]:
    return {}


def _timings_by_program_factory() -> dict[str, dict[str, float]]:
    return {}


@dataclass(frozen=True)
class ProjectFailure:
    name: str
    message: str
    detail: str | None = None
    line: int | None = None
    column: int | None = None
    length: int | None = None


@dataclass(frozen=True)
class RootOrigin:
    source_path: Path | None = None
    library_name: str | None = None

    @property
    def origin_file(self) -> str | None:
        return self.source_path.name if self.source_path is not None else None


#: The grammar keyword the parser stores in ``header.name`` for a picture.
_BASEPICTURE_KEYWORD = "basepicture"


def program_identity(bp: BasePicture) -> str:
    """Return the program name a base picture stands for.

    A loaded program carries its name in ``program_name``. A single-file parse
    leaves it unset and keeps the keyword ``BasePicture`` in ``header.name``;
    hand-built pictures may instead name the header directly.
    """
    if bp.program_name:
        return bp.program_name
    header_name = bp.header.name
    if header_name and header_name.casefold() != _BASEPICTURE_KEYWORD:
        return header_name
    return bp.name or header_name


@dataclass
class ProjectGraph:
    ast_by_name: dict[str, BasePicture] = field(default_factory=_ast_by_name_factory)
    root_origins: dict[str, RootOrigin] = field(default_factory=_root_origins_factory)
    # Keyed by (origin_lib.casefold(), moduletype_name.casefold(), origin_file.casefold())
    # so same-name types from the same library but different files are preserved.
    moduletype_defs: dict[tuple[str, str, str], ModuleTypeDef] = field(default_factory=_moduletype_defs_factory)
    # Keyed like ``moduletype_defs``: (origin_lib, name, origin_file), all
    # casefolded, so same-named record types from different libraries coexist.
    datatype_defs: dict[tuple[str, str, str], DataType] = field(default_factory=_datatype_defs_factory)
    # library_name.casefold() -> set of dependency library names (casefolded)
    library_dependencies: dict[str, set[str]] = field(default_factory=_library_dependencies_factory)
    source_dependencies: dict[str, set[str]] = field(default_factory=_library_dependencies_factory)
    missing: list[str] = field(default_factory=_missing_factory)
    warnings: list[str] = field(default_factory=_warnings_factory)
    #: Typed view of every parse, transform, and load failure. Keyed by the
    #: casefolded program name and the authoritative source for failure detail;
    #: ``missing`` also carries entries that have no program, such as a missing
    #: dependency file.
    failures: dict[str, ProjectFailure] = field(default_factory=_failures_factory)
    # Track libraries that couldn't be loaded (e.g., proprietary ABB libraries)
    unavailable_libraries: set[str] = field(default_factory=_unavailable_libraries_factory)
    source_files: set[Path] = field(default_factory=_source_files_factory)
    #: Source path -> library that owns it, recorded when the program is indexed.
    source_file_libraries: dict[Path, str] = field(default_factory=_source_file_libraries_factory)
    analysis_cache_key: str | None = None
    analysis_manifest_files: frozenset[Path] = field(default_factory=_analysis_manifest_files_factory)
    load_stage_timings: dict[str, float] = field(default_factory=_timings_factory)
    load_stage_timings_by_program: dict[str, dict[str, float]] = field(default_factory=_timings_by_program_factory)
    graphics_load_timings: dict[str, float] = field(default_factory=_timings_factory)
    graphics_load_timings_by_program: dict[str, dict[str, float]] = field(default_factory=_timings_by_program_factory)
    # Program name -> SattLint's graphics view of that program.
    graphics_attachments: dict[str, GraphicsAttachments] = field(default_factory=_graphics_attachments_factory)
    # True only when this whole graph was replayed from the project-level analysis-result cache
    # (see _app_analysis_loading.py); all timing/count fields above are then stale/historical,
    # not measurements of the current call.
    loaded_from_cache: bool = False

    def add_library_dependencies(self, library_name: str | None, dep_libs: list[str]) -> None:
        if not library_name:
            return
        key = library_name.casefold()
        bucket = self.library_dependencies.setdefault(key, set())
        for dep in dep_libs:
            if dep:
                bucket.add(dep.casefold())

    @staticmethod
    def _root_origin_key(name: str) -> str:
        return name.casefold()

    def record_root_origin(
        self,
        name: str,
        *,
        source_path: Path | None = None,
        library_name: str | None = None,
    ) -> None:
        key = self._root_origin_key(name)
        existing = self.root_origins.get(key)
        self.root_origins[key] = RootOrigin(
            source_path=source_path
            if source_path is not None
            else existing.source_path
            if existing is not None
            else None,
            library_name=(
                library_name if library_name is not None else existing.library_name if existing is not None else None
            ),
        )

    def root_origin_for_name(self, name: str) -> RootOrigin | None:
        return self.root_origins.get(self._root_origin_key(name))

    def _identity_for_basepicture(self, bp: BasePicture) -> str | None:
        """The ``root_origins`` key that belongs to ``bp``.

        Programs are indexed under their program name, while ``header.name`` is
        the literal ``BasePicture`` keyword. Identity is therefore resolved from
        the indexed picture, then from the merge clone's preserved fields, and
        only then from the name fields the picture itself carries.
        """
        for name, picture in self.ast_by_name.items():
            if picture is bp:
                return name

        matches = [
            name
            for name, picture in self.ast_by_name.items()
            if picture.name == bp.name and picture.origin_file == bp.origin_file and picture.origin_lib == bp.origin_lib
        ]
        if len(matches) == 1:
            return matches[0]

        for candidate in (bp.program_name, bp.name, bp.header.name):
            if candidate and self.root_origins.get(self._root_origin_key(candidate)) is not None:
                return candidate
        return None

    def root_origin_for_basepicture(self, bp: BasePicture) -> RootOrigin | None:
        identity = self._identity_for_basepicture(bp)
        return None if identity is None else self.root_origin_for_name(identity)

    def root_source_path_for_name(self, name: str) -> Path | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.source_path

    def root_source_path_for_basepicture(self, bp: BasePicture) -> Path | None:
        identity = self._identity_for_basepicture(bp)
        return None if identity is None else self.root_source_path_for_name(identity)

    def root_library_name_for_name(self, name: str) -> str | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.library_name

    def root_library_name_for_basepicture(self, bp: BasePicture) -> str | None:
        identity = self._identity_for_basepicture(bp)
        return None if identity is None else self.root_library_name_for_name(identity)

    def root_origin_file_for_name(self, name: str) -> str | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.origin_file

    def root_origin_file_for_basepicture(self, bp: BasePicture) -> str | None:
        identity = self._identity_for_basepicture(bp)
        return None if identity is None else self.root_origin_file_for_name(identity)

    def graphics_attachments_for(self, bp: BasePicture) -> GraphicsAttachments:
        """The graphics view attached to ``bp``, or an empty value when none was attached."""
        for name, picture in self.ast_by_name.items():
            if picture is bp:
                return self.graphics_attachments.get(name, EMPTY_GRAPHICS_ATTACHMENTS)

        # ``merge_project_basepicture`` returns a ``replace`` clone, so identity
        # fails for the merged picture the analyzers receive. Match the clone to
        # its indexed original by the fields the merge preserves.
        matches = [
            name
            for name, picture in self.ast_by_name.items()
            if picture.header.name == bp.header.name
            and picture.origin_file == bp.origin_file
            and picture.origin_lib == bp.origin_lib
        ]
        if len(matches) == 1:
            return self.graphics_attachments.get(matches[0], EMPTY_GRAPHICS_ATTACHMENTS)

        return self.graphics_attachments.get(program_identity(bp), EMPTY_GRAPHICS_ATTACHMENTS)

    def index_from_basepic(
        self,
        bp: BasePicture,
        source_path: Path | None = None,
        library_name: str | None = None,
        *,
        program_name: str | None = None,
    ) -> None:
        # Collect module and record type defs for global analysis [2]

        identity = program_name or program_identity(bp)
        self.record_root_origin(identity, source_path=source_path, library_name=library_name)
        if source_path:
            self.source_files.add(source_path)
            if library_name:
                # Library names disambiguate same-named files in different
                # libraries, so consumers can address a source file exactly.
                self.source_file_libraries[source_path] = library_name

        for m in bp.moduletype_defs:
            if source_path and not m.origin_file:
                m.origin_file = source_path.name
            if library_name and not m.origin_lib:
                m.origin_lib = library_name
            lib_key = (m.origin_lib or "").casefold()
            name_key = m.name.casefold()
            file_key = (m.origin_file or "").casefold()
            self.moduletype_defs[(lib_key, name_key, file_key)] = m
        for d in bp.datatype_defs:
            if source_path and not d.origin_file:
                d.origin_file = source_path.name
            if library_name and not d.origin_lib:
                d.origin_lib = library_name
            lib_key = (d.origin_lib or "").casefold()
            name_key = d.name.casefold()
            file_key = (d.origin_file or "").casefold()
            self.datatype_defs[(lib_key, name_key, file_key)] = d


def merge_project_basepicture(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
    """Merge gathered moduletype/datatype/label-definitions into the root base picture."""
    merged_datatypes: list[DataType] = list(graph.datatype_defs.values())
    merged_modtypes: list[ModuleTypeDef] = list(graph.moduletype_defs.values())
    return replace(
        root_bp,
        datatype_defs=merged_datatypes,
        moduletype_defs=merged_modtypes,
    )
