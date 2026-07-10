from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypedDict

from openpyxl.cell.cell import Cell


class _WorksheetCellTarget(Protocol):
    def add(self, cell: Cell) -> None: ...


class ProgramConfigEntry(TypedDict):
    name: str
    directory: str
    main_program: bool


class LibraryConfigEntry(TypedDict):
    name: str
    directory: str


class ConfigurationContents(TypedDict):
    programs: list[str]
    libraries: list[str]


class StationConfiguration(TypedDict):
    config_file: str
    type: str
    programs: list[str]
    libraries: list[str]
    units: str | None
    ip_address: str | None
    slc: str | None


type DependencyRow = tuple[str, str]


@dataclass
class ComponentInfo:
    name: str
    type: str
    ip_address: str
    slc: str
    units: str
    dependencies: list[str]


@dataclass
class ConfigurationFileInfo:
    config_name: str
    version: str
    date: str
    main_program: str
    programs: list[ProgramConfigEntry]
    libraries: list[LibraryConfigEntry]


class ExcelConfig:
    HEADER_COLOR = "4472C4"
    HEADER_TEXT_COLOR = "FFFFFF"
    KPI_TITLE_COLOR = "1F4E78"
    KPI_VALUE_COLOR = "2E75B6"
    KPI_BG_COLOR = "E7E6E6"
    SUCCESS_COLOR = "70AD47"
    WARNING_COLOR = "ED7D31"
