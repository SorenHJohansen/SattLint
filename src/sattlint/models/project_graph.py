"""Project graph and indexing helpers for SattLine projects."""

from .ast_model import BasePicture, DataType, ModuleTypeDef
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectGraph:
    ast_by_name: dict[str, BasePicture] = field(default_factory=dict)
    # Keyed by (origin_lib.casefold(), moduletype_name.casefold(), origin_file.casefold())
    # so same-name types from the same library but different files are preserved.
    moduletype_defs: dict[tuple[str, str, str], ModuleTypeDef] = field(default_factory=dict)
    datatype_defs: dict[str, DataType] = field(default_factory=dict)
    # library_name.casefold() -> set of dependency library names (casefolded)
    library_dependencies: dict[str, set[str]] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    ignored_vendor: list[str] = field(default_factory=list)
    # Track libraries that couldn't be loaded (e.g., proprietary ABB libraries)
    unavailable_libraries: set[str] = field(default_factory=set)
    source_files: set[Path] = field(default_factory=set)

    def add_library_dependencies(self, library_name: str | None, dep_libs: list[str]) -> None:
        if not library_name:
            return
        key = library_name.casefold()
        bucket = self.library_dependencies.setdefault(key, set())
        for dep in dep_libs:
            if dep:
                bucket.add(dep.casefold())

    def index_from_basepic(
        self,
        bp: BasePicture,
        source_path: Path | None = None,
        library_name: str | None = None,
    ) -> None:
        # Collect module and record type defs for global analysis [2]

        if source_path and not bp.origin_file:
            bp.origin_file = source_path.name
        if library_name and not bp.origin_lib:
            bp.origin_lib = library_name

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
