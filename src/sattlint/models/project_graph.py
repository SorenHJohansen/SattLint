"""Project graph and indexing helpers for SattLine projects."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from ._validation_notice import ValidationNotice
from .ast_model import BasePicture, DataType, ModuleTypeDef


def _ast_by_name_factory() -> dict[str, BasePicture]:
    return {}


def _moduletype_defs_factory() -> dict[tuple[str, str, str], ModuleTypeDef]:
    return {}


def _datatype_defs_factory() -> dict[str, DataType]:
    return {}


def _library_dependencies_factory() -> dict[str, set[str]]:
    return {}


def _missing_factory() -> list[str]:
    return []


def _warnings_factory() -> list[str]:
    return []


def _root_origins_factory() -> dict[str, RootOrigin]:
    return {}


def _warning_notices_factory() -> list[tuple[str, ValidationNotice]]:
    return []


def _failures_factory() -> dict[str, ProjectFailure]:
    return {}


def _unavailable_libraries_factory() -> set[str]:
    return set()


def _source_files_factory() -> set[Path]:
    return set()


def _analysis_manifest_files_factory() -> frozenset[Path]:
    return frozenset()


def _timings_factory() -> dict[str, float]:
    return {}


def _timings_by_program_factory() -> dict[str, dict[str, float]]:
    return {}


def _ast_cache_counts_factory() -> dict[str, int]:
    return {}


@dataclass(frozen=True)
class ProjectFailure:
    name: str
    message: str
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


@dataclass
class ProjectGraph:
    ast_by_name: dict[str, BasePicture] = field(default_factory=_ast_by_name_factory)
    root_origins: dict[str, RootOrigin] = field(default_factory=_root_origins_factory)
    # Keyed by (origin_lib.casefold(), moduletype_name.casefold(), origin_file.casefold())
    # so same-name types from the same library but different files are preserved.
    moduletype_defs: dict[tuple[str, str, str], ModuleTypeDef] = field(default_factory=_moduletype_defs_factory)
    datatype_defs: dict[str, DataType] = field(default_factory=_datatype_defs_factory)
    # library_name.casefold() -> set of dependency library names (casefolded)
    library_dependencies: dict[str, set[str]] = field(default_factory=_library_dependencies_factory)
    missing: list[str] = field(default_factory=_missing_factory)
    warnings: list[str] = field(default_factory=_warnings_factory)
    warning_notices: list[tuple[str, ValidationNotice]] = field(default_factory=_warning_notices_factory)
    failures: dict[str, ProjectFailure] = field(default_factory=_failures_factory)
    # Track libraries that couldn't be loaded (e.g., proprietary ABB libraries)
    unavailable_libraries: set[str] = field(default_factory=_unavailable_libraries_factory)
    source_files: set[Path] = field(default_factory=_source_files_factory)
    analysis_cache_key: str | None = None
    analysis_manifest_files: frozenset[Path] = field(default_factory=_analysis_manifest_files_factory)
    load_stage_timings: dict[str, float] = field(default_factory=_timings_factory)
    load_stage_timings_by_program: dict[str, dict[str, float]] = field(default_factory=_timings_by_program_factory)
    graphics_load_timings: dict[str, float] = field(default_factory=_timings_factory)
    graphics_load_timings_by_program: dict[str, dict[str, float]] = field(default_factory=_timings_by_program_factory)
    # Counted once, at the single authoritative decision point in _load_or_parse, so a prefetch
    # hit and its later consumption are never counted as two separate cache events.
    ast_cache_counts: dict[str, int] = field(default_factory=_ast_cache_counts_factory)
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

    def root_origin_for_basepicture(self, bp: BasePicture) -> RootOrigin | None:
        return self.root_origin_for_name(bp.header.name)

    def root_source_path_for_name(self, name: str) -> Path | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.source_path

    def root_source_path_for_basepicture(self, bp: BasePicture) -> Path | None:
        return self.root_source_path_for_name(bp.header.name)

    def root_library_name_for_name(self, name: str) -> str | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.library_name

    def root_library_name_for_basepicture(self, bp: BasePicture) -> str | None:
        return self.root_library_name_for_name(bp.header.name)

    def root_origin_file_for_name(self, name: str) -> str | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.origin_file

    def root_origin_file_for_basepicture(self, bp: BasePicture) -> str | None:
        return self.root_origin_file_for_name(bp.header.name)

    def index_from_basepic(
        self,
        bp: BasePicture,
        source_path: Path | None = None,
        library_name: str | None = None,
    ) -> None:
        # Collect module and record type defs for global analysis [2]

        self.record_root_origin(bp.header.name, source_path=source_path, library_name=library_name)
        if source_path:
            self.source_files.add(source_path)

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
            self.datatype_defs[d.name] = d


def merge_project_basepicture(root_bp: BasePicture, graph: ProjectGraph) -> BasePicture:
    """Merge gathered moduletype/datatype/label-definitions into the root base picture."""
    merged_datatypes: list[DataType] = list(graph.datatype_defs.values())
    merged_modtypes: list[ModuleTypeDef] = list(graph.moduletype_defs.values())
    lib_deps = {lib: sorted(deps) for lib, deps in (graph.library_dependencies or {}).items()}
    return replace(
        root_bp,
        datatype_defs=merged_datatypes,
        moduletype_defs=merged_modtypes,
        library_dependencies=lib_deps,
    )
