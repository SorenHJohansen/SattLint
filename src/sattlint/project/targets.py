"""Discover configured project targets and validate their identity.

A target is a bare unit name, not a file name. The association of a target with
a program or library is inferred from the configured root it was found under,
because the project file does not declare it. The scan is used by
``project targets`` and ``project check``; it never parses a source file.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from ..config.types import ConfigDict
from ..parser_api import LoadMode, UnitIdentity, code_ext_candidates
from ..utils.casefolding import unit_key

#: Rows above this count are summarized rather than listed one by one.
TARGET_LIST_LIMIT = 200


@dataclass(frozen=True, slots=True)
class ProjectTarget:
    """One target the configured roots can provide."""

    name: str
    kind: str
    path: Path


@dataclass(slots=True)
class TargetScan:
    """Discovered targets plus identity problems the user must resolve."""

    targets: list[ProjectTarget] = field(default_factory=list[ProjectTarget])
    warnings: list[str] = field(default_factory=list[str])
    errors: list[str] = field(default_factory=list[str])


def _load_mode(cfg: ConfigDict) -> LoadMode:
    mode = str(cfg.get("mode", "official")).strip().casefold()
    return LoadMode.DRAFT if mode == "draft" else LoadMode.OFFICIAL


def _configured_roots(cfg: ConfigDict) -> tuple[tuple[Path, str], ...]:
    roots: list[tuple[Path, str]] = []
    for key, kind in (("program_dir", "program"), ("ABB_lib_dir", "library")):
        raw = str(cfg.get(key, "") or "").strip()
        if raw:
            roots.append((Path(raw).expanduser(), kind))
    for raw in cfg.get("other_lib_dirs") or ():
        text = str(raw).strip()
        if text:
            roots.append((Path(text).expanduser(), "library"))
    return tuple(roots)


def _files_by_name(root: Path, suffixes: tuple[str, ...]) -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = {}
    if not root.is_dir():
        return found
    wanted = {suffix.lower() for suffix in suffixes}
    for path in sorted(root.iterdir(), key=lambda entry: entry.name):
        if not path.is_file() or path.suffix.lower() not in wanted:
            continue
        found.setdefault(unit_key(path.stem), []).append(path)
    return found


def scan_project_targets(cfg: ConfigDict) -> TargetScan:
    """List targets under the configured roots and report identity problems."""
    scan = TargetScan()
    mode = _load_mode(cfg)
    suffixes = code_ext_candidates(mode)
    seen: dict[str, ProjectTarget] = {}

    for root, kind in _configured_roots(cfg):
        for stem_key, paths in _files_by_name(root, suffixes).items():
            if len(paths) > 1:
                shown = ", ".join(path.name for path in paths)
                scan.warnings.append(
                    f"Duplicate target {paths[0].stem!r} in {root}: {shown}. The loader uses one of them."
                )
            path = paths[0]
            existing = seen.get(stem_key)
            if existing is not None:
                if existing.path != path:
                    scan.errors.append(
                        f"Target {path.stem!r} is provided by both {existing.path} and {path}. "
                        "Remove one file or correct program_dir, ABB_lib_dir, or other_lib_dirs."
                    )
                continue
            seen[stem_key] = ProjectTarget(name=path.stem, kind=kind, path=path)

    for index, raw_target in enumerate(_configured_targets(cfg)):
        name = str(raw_target)
        identity = UnitIdentity.of(name)
        suffix = Path(name).suffix.lower()
        if suffix in {extension.lower() for extension in suffixes}:
            scan.errors.append(
                f"analyzed_programs_and_libraries[{index}] {name!r} includes the file suffix {suffix}. "
                f"Use {Path(name).stem!r} instead."
            )
            continue
        if identity.key not in seen:
            scan.errors.append(
                f"analyzed_programs_and_libraries[{index}] {name!r} was not found under program_dir, "
                "ABB_lib_dir, or other_lib_dirs. Correct the directory or the unit name."
            )

    scan.targets = sorted(seen.values(), key=lambda target: (target.name.casefold(), str(target.path)))
    return scan


def _configured_targets(cfg: ConfigDict) -> tuple[str, ...]:
    raw = cast(object, cfg.get("analyzed_programs_and_libraries"))
    if not isinstance(raw, (list, tuple)):
        return ()
    items = cast(Sequence[object], raw)
    return tuple(str(value).strip() for value in items if str(value).strip())
