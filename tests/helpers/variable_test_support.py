from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sattline_parser.models.ast_model import ModuleHeader


def ns(**kwargs: Any) -> Any:
    return SimpleNamespace(**kwargs)


def hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


class UsageStub:
    def __init__(
        self,
        *,
        is_unused: bool = False,
        is_display_only: bool = False,
        is_read_only: bool = False,
        read: bool = False,
        written: bool = False,
        non_ui_read: bool = False,
        ui_read: bool = False,
        field_reads: dict[str, list[object]] | None = None,
        field_writes: dict[str, list[object]] | None = None,
        usage_locations: list[tuple[object, str]] | None = None,
    ) -> None:
        self.is_unused = is_unused
        self.is_display_only = is_display_only
        self.is_read_only = is_read_only
        self.read = read
        self.written = written
        self.non_ui_read = non_ui_read
        self.ui_read = ui_read
        self.field_reads = field_reads or {}
        self.field_writes = field_writes or {}
        self.usage_locations = usage_locations or []

    def mark_field_read(self, field_path: str, location: object) -> None:
        self.field_reads.setdefault(field_path, []).append(location)

    def mark_field_written(self, field_path: str, location: object) -> None:
        self.field_writes.setdefault(field_path, []).append(location)

    def mark_read(self, location: object) -> None:
        self.read = True
        self.usage_locations.append((location, "read"))

    def mark_written(self, location: object) -> None:
        self.written = True
        self.usage_locations.append((location, "write"))
