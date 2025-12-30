from models.ast_model import BasePicture, DataType, ModuleTypeDef
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ProjectGraph:
    ast_by_name: dict[str, BasePicture] = field(default_factory=dict)
    moduletype_defs: dict[str, ModuleTypeDef] = field(default_factory=dict)
    datatype_defs: dict[str, DataType] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    ignored_vendor: list[str] = field(default_factory=list)

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
            self.moduletype_defs[m.name] = m
        for d in bp.datatype_defs:
            if source_path and not d.origin_file:
                d.origin_file = source_path.name
            if library_name and not d.origin_lib:
                d.origin_lib = library_name
            self.datatype_defs[d.name] = d