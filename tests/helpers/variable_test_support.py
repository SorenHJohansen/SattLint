from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from sattline_parser.models.ast_model import (
    Equation,
    ModuleCode,
    ModuleHeader,
    ModuleTypeDef,
    Simple_DataType,
    Variable,
)
from sattlint import constants as const


def ns(**kwargs: Any) -> Any:
    return SimpleNamespace(**kwargs)


def hdr(name: str) -> ModuleHeader:
    return ModuleHeader(name=name, invoke_coord=(0.0, 0.0, 0.0, 0.0, 0.0))


def varref(name: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name}


def state_ref(name: str, state: str) -> dict[str, str]:
    return {const.KEY_VAR_NAME: name, "state": state}


def issue_kinds(report: Any) -> set[Any]:
    return {issue.kind for issue in report.issues}


def status_bridge_typedef() -> ModuleTypeDef:
    return ModuleTypeDef(
        name="StatusBridge",
        moduleparameters=[Variable(name="OperationStatus", datatype=Simple_DataType.INTEGER)],
        localvariables=[
            Variable(name="Source", datatype=Simple_DataType.INTEGER),
            Variable(name="Destination", datatype=Simple_DataType.INTEGER),
        ],
        moduledef=None,
        modulecode=ModuleCode(
            equations=[
                Equation(
                    name="BridgeEq",
                    position=(0.0, 0.0),
                    size=(1.0, 1.0),
                    code=[
                        (
                            const.KEY_FUNCTION_CALL,
                            "CopyVariable",
                            [varref("Source"), varref("Destination"), varref("OperationStatus")],
                        )
                    ],
                )
            ]
        ),
    )


def access_event(
    path_parts: tuple[str, ...],
    use_module_path: list[str],
    kind: object,
) -> SimpleNamespace:
    return SimpleNamespace(
        canonical_path=SimpleNamespace(key=lambda: path_parts),
        use_module_path=use_module_path,
        kind=kind,
    )


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
        ui_usage_locations: list[object] | None = None,
    ) -> None:
        effective_ui_read = ui_read or is_display_only
        effective_read = read or is_read_only or effective_ui_read
        effective_non_ui_read = non_ui_read or is_read_only or (effective_read and not effective_ui_read)

        self.read = effective_read
        self.written = written
        self.non_ui_read = effective_non_ui_read
        self.ui_read = effective_ui_read
        self.field_reads = field_reads or {}
        self.field_writes = field_writes or {}
        self.usage_locations = usage_locations or []
        self.ui_usage_locations = ui_usage_locations or []
        self.is_unused = is_unused if is_unused else not (self.read or self.written)
        self.is_read_only = is_read_only if is_read_only else self.read and not self.written
        self.is_display_only = is_display_only if is_display_only else self.ui_read and not self.non_ui_read

    def _sync_flags(self) -> None:
        self.is_unused = not (self.read or self.written)
        self.is_read_only = self.read and not self.written
        self.is_display_only = self.ui_read and not self.non_ui_read

    def mark_field_read(self, field_path: str, location: object, *, ui: bool = False) -> None:
        self.field_reads.setdefault(field_path, []).append(location)
        self.read = True
        if ui:
            self.ui_read = True
            self.ui_usage_locations.append(location)
        else:
            self.non_ui_read = True
        self._sync_flags()

    def mark_field_written(self, field_path: str, location: object) -> None:
        self.field_writes.setdefault(field_path, []).append(location)
        self.written = True
        self._sync_flags()

    def mark_read(self, location: object, *, ui: bool = False) -> None:
        self.read = True
        if ui:
            self.ui_read = True
            self.ui_usage_locations.append(location)
        else:
            self.non_ui_read = True
        self.usage_locations.append((location, "read"))
        self._sync_flags()

    def mark_ui_read(self, location: object) -> None:
        self.mark_read(location, ui=True)

    def mark_written(self, location: object) -> None:
        self.written = True
        self.usage_locations.append((location, "write"))
        self._sync_flags()
