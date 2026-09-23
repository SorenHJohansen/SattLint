"""Runtime representation of a SattLint project."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from ..config.defaults import DEFAULT_CONFIG
from ..config.types import ConfigDict
from ..config.validation import deep_merge_dict
from .types import ProjectDict


@dataclass(frozen=True)
class SattLintProjectFile:
    path: Path
    data: ProjectDict = field(repr=False)

    @property
    def root(self) -> Path:
        return self.path.parent.resolve()

    def _resolve(self, raw: str) -> Path:
        if not raw:
            return Path()
        p = Path(raw)
        if p.is_absolute():
            return p
        return (self.root / p).resolve()

    def _maybe_resolve(self, raw: str) -> str | Path:
        if not raw:
            return ""
        return self._resolve(raw)

    def to_config_dict(self) -> ConfigDict:
        d = self.data
        cfg = cast(
            ConfigDict,
            {
                "analyzed_programs_and_libraries": list(d["analyzed_programs_and_libraries"]),
                "mode": d["mode"],
                "program_dir": self._maybe_resolve(d["program_dir"]),
                "ABB_lib_dir": self._maybe_resolve(d["ABB_lib_dir"]),
                "icf_dir": self._maybe_resolve(d["icf_dir"]),
                "other_lib_dirs": [self._resolve(p) for p in d["other_lib_dirs"] if p.strip()],
                "analysis": {},
            },
        )
        return cfg

    def to_default_merged_config_dict(self) -> ConfigDict:
        merged = deep_merge_dict(
            cast(dict[str, object], deepcopy(DEFAULT_CONFIG)),
            cast(dict[str, object], self.to_config_dict()),
        )
        return cast(ConfigDict, merged)


__all__ = ["SattLintProjectFile"]
