# pyright: reportAssignmentType=false
"""Typed test stubs for reusable dynamic helpers.

Prefer these helpers over ad hoc ``SimpleNamespace`` or inline lambda doubles
when a reusable fake can express the same behavior. Reserve file-level Pyright
pragmas for support modules that intentionally aggregate private seams or for
genuinely dynamic UI or runtime tests.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict


def _string_list() -> list[str]:
    return []


def _string_set() -> set[str]:
    return set()


def _path_set() -> set[Path]:
    return set()


def _path_frozenset() -> frozenset[Path]:
    return frozenset()


def _float_dict() -> dict[str, float]:
    return {}


def _object_dict() -> dict[str, object]:
    return {}


def _nested_float_dict() -> dict[str, dict[str, float]]:
    return {}


class RealContext(TypedDict):
    cfg: dict[str, Any]
    var_name: str
    module_path: str
    module_var: str
    module_name: str


@dataclass(slots=True)
class NamedHeader:
    name: str


@dataclass(slots=True)
class NamedObject:
    header: NamedHeader
    origin_file: str | None = None
    origin_lib: str | None = None


@dataclass(slots=True, frozen=True)
class RootOriginStub:
    source_path: Path | None = None
    library_name: str | None = None

    @property
    def origin_file(self) -> str | None:
        return None if self.source_path is None else self.source_path.name


@dataclass(slots=True)
class AnalysisGraphStub:
    ast_by_name: dict[str, object] = field(default_factory=_object_dict)
    root_origins: dict[str, RootOriginStub] = field(default_factory=_object_dict)
    missing: list[str] = field(default_factory=_string_list)
    unavailable_libraries: set[str] = field(default_factory=_string_set)
    warnings: list[str] = field(default_factory=_string_list)
    source_files: set[Path] = field(default_factory=_path_set)
    analysis_cache_key: str | None = None
    analysis_manifest_files: frozenset[Path] = field(default_factory=_path_frozenset)
    load_stage_timings: dict[str, float] = field(default_factory=_float_dict)
    load_stage_timings_by_program: dict[str, dict[str, float]] = field(default_factory=_nested_float_dict)
    graphics_load_timings: dict[str, float] = field(default_factory=_float_dict)
    graphics_load_timings_by_program: dict[str, dict[str, float]] = field(default_factory=_nested_float_dict)

    def record_root_origin(
        self,
        name: str,
        *,
        source_path: Path | None = None,
        library_name: str | None = None,
    ) -> None:
        self.root_origins[name.casefold()] = RootOriginStub(source_path=source_path, library_name=library_name)

    def root_origin_for_name(self, name: str) -> RootOriginStub | None:
        return self.root_origins.get(name.casefold())

    def root_origin_for_basepicture(self, bp: object) -> RootOriginStub | None:
        header = getattr(bp, "header", None)
        name = getattr(header, "name", None)
        return self.root_origin_for_name(name) if isinstance(name, str) else None

    def root_source_path_for_name(self, name: str) -> Path | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.source_path

    def root_source_path_for_basepicture(self, bp: object) -> Path | None:
        root_origin = self.root_origin_for_basepicture(bp)
        return None if root_origin is None else root_origin.source_path

    def root_library_name_for_name(self, name: str) -> str | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.library_name

    def root_library_name_for_basepicture(self, bp: object) -> str | None:
        root_origin = self.root_origin_for_basepicture(bp)
        return None if root_origin is None else root_origin.library_name

    def root_origin_file_for_name(self, name: str) -> str | None:
        root_origin = self.root_origin_for_name(name)
        return None if root_origin is None else root_origin.origin_file

    def root_origin_file_for_basepicture(self, bp: object) -> str | None:
        root_origin = self.root_origin_for_basepicture(bp)
        return None if root_origin is None else root_origin.origin_file


class InputFeeder:
    def __init__(self, responses: Iterable[str]) -> None:
        self._responses: Iterator[str] = iter(responses)

    def __call__(self, _prompt: str = "") -> str:
        try:
            return next(self._responses)
        except StopIteration as exc:
            raise AssertionError("No more input responses provided") from exc


def make_input(responses: Iterable[str]) -> InputFeeder:
    return InputFeeder(responses)


def named_object(name: str, *, origin_file: str | None = None, origin_lib: str | None = None) -> NamedObject:
    return NamedObject(header=NamedHeader(name), origin_file=origin_file, origin_lib=origin_lib)


@dataclass(slots=True)
class RecordingWriter:
    writes: list[str] = field(default_factory=_string_list)

    def write(self, text: str) -> None:
        self.writes.append(text)

    def flush(self) -> None:
        return None


class NoOpWriter:
    def write(self, _text: str) -> None:
        return None

    def flush(self) -> None:
        return None


NullWriter = NoOpWriter


__all__ = [
    "AnalysisGraphStub",
    "InputFeeder",
    "NamedHeader",
    "NamedObject",
    "NoOpWriter",
    "NullWriter",
    "RealContext",
    "RecordingWriter",
    "make_input",
    "named_object",
]
