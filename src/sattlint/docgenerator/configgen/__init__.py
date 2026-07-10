from __future__ import annotations

import argparse
import logging
import sys
import tomllib
from pathlib import Path

from sattline_parser.api import read_text_with_fallback

from . import _extraction as extraction_impl
from ._excel_generator import ExcelGenerator
from ._excel_support import StyleManager, WorksheetHelper
from ._extraction import WorkstationMapper
from ._types import (
    ComponentInfo,
    ConfigurationContents,
    ConfigurationFileInfo,
    DependencyRow,
    ExcelConfig,
    LibraryConfigEntry,
    ProgramConfigEntry,
    StationConfiguration,
    _WorksheetCellTarget,
)

__all__ = [
    "ComponentInfo",
    "ConfigurationContents",
    "ConfigurationFileInfo",
    "ConfigurationFileParser",
    "DependencyRow",
    "ExcelConfig",
    "ExcelGenerator",
    "LibraryConfigEntry",
    "ProgramConfigEntry",
    "SattLineConfigExtractor",
    "StationConfiguration",
    "StyleManager",
    "WorksheetHelper",
    "WorkstationMapper",
    "_WorksheetCellTarget",
    "main",
]


class ConfigurationFileParser(extraction_impl.ConfigurationFileParser):
    def parse_configuration_file(self, config_file: Path) -> ConfigurationFileInfo | None:
        try:
            text = read_text_with_fallback(config_file)
            config_match = self.config_pattern.search(text)
            if not config_match:
                logging.getLogger("SattLint").warning("Could not parse configuration header in %s", config_file.name)
                return None

            version = config_match.group(1)
            date = config_match.group(2)
            config_name = config_file.stem

            programs: list[ProgramConfigEntry] = []
            for match in self.program_pattern.finditer(text):
                program_name_raw = match.group(1)
                program_name = program_name_raw[:-2] if program_name_raw.endswith(".z") else program_name_raw
                programs.append(
                    {
                        "name": program_name,
                        "directory": match.group(2),
                        "main_program": match.group(3) == "True",
                    }
                )

            libraries: list[LibraryConfigEntry] = []
            for match in self.library_pattern.finditer(text):
                library_name_raw = match.group(1)
                library_name = library_name_raw[:-2] if library_name_raw.endswith(".z") else library_name_raw
                libraries.append({"name": library_name, "directory": match.group(2)})

            main_program = next((program["name"] for program in programs if program["main_program"]), "None")
            logging.getLogger("SattLint").info(
                "Parsed %s: Config=%r, %d programs, %d libraries",
                config_file.name,
                config_name,
                len(programs),
                len(libraries),
            )
            return ConfigurationFileInfo(
                config_name=config_name,
                version=version,
                date=date,
                main_program=main_program,
                programs=programs,
                libraries=libraries,
            )
        except (OSError, UnicodeError, ValueError, tomllib.TOMLDecodeError) as error:
            logging.getLogger("SattLint").error("Error parsing configuration file %s: %s", config_file, error)
            return None


class SattLineConfigExtractor(extraction_impl.SattLineConfigExtractor):
    def parse_all_configuration_files(self) -> list[ConfigurationFileInfo]:
        parser = ConfigurationFileParser()
        configurations: list[ConfigurationFileInfo] = []
        if not self.kfiles_dir.exists():
            logging.getLogger("SattLint").warning("Configuration directory not found: %s", self.kfiles_dir)
            return configurations
        config_files = sorted(self.kfiles_dir.glob("*.k"))
        if not config_files:
            logging.getLogger("SattLint").warning("No .k files found in %s", self.kfiles_dir)
            return configurations
        logging.getLogger("SattLint").info("Found %d configuration files", len(config_files))
        for config_file in config_files:
            config_info = parser.parse_configuration_file(config_file)
            if config_info:
                configurations.append(config_info)
        logging.getLogger("SattLint").info("✓ Successfully parsed %d configuration files", len(configurations))
        return configurations

    def read_dependencies(self, z_file: Path) -> list[str]:
        try:
            text = read_text_with_fallback(z_file)
            return [line.strip().replace(".z", "") for line in text.splitlines() if line.strip()]
        except OSError as error:
            logging.getLogger("SattLint").error("Error reading %s: %s", z_file, error)
            return []

    def get_ip_address(self, z_file: Path) -> str:
        q_file = z_file.with_suffix(".q")
        if not q_file.exists():
            return "No Q-File"
        try:
            text = read_text_with_fallback(q_file)
            match = self.name_pattern.search(text)
            return match.group(1) if match else "No SLC assigned"
        except OSError as error:
            logging.getLogger("SattLint").error("Error reading %s: %s", q_file, error)
            return "Error reading Q-File"

    def get_units_in_program(self, z_file: Path) -> str:
        x_file = z_file.with_suffix(".x")
        if not x_file.exists():
            return "No X-File"
        try:
            text = read_text_with_fallback(x_file)
            units_set = {match.group(1) for match in self.unit_pattern.finditer(text)}
            if not units_set:
                return "No units assigned"
            units = sorted(units_set)
            return f"({len(units)}) " + ", ".join(units)
        except OSError as error:
            logging.getLogger("SattLint").error("Error reading %s: %s", x_file, error)
            return "Error reading X-File"


def main(argv: list[str] | None = None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(
        description="Generate an Excel workbook from a SattLine configuration root directory."
    )
    parser.add_argument("root_dir", help="Root directory containing SattLine configuration files")
    parser.add_argument("--output", default="SattLine_Configuration.xlsx", help="Output workbook path")
    args = parser.parse_args(argv)

    try:
        root_dir = Path(args.root_dir).expanduser().resolve()
        output_file = Path(args.output).expanduser().resolve()
        if not root_dir.exists() or not root_dir.is_dir():
            print(f"Invalid root directory: {root_dir}", file=sys.stderr)
            return 2
        extractor = SattLineConfigExtractor(root_dir)
        generator = ExcelGenerator(extractor)
        generator.generate(output_file)
        print(f"✅ Configuration Excel file generated successfully: {output_file}")
    except (OSError, RuntimeError, ValueError) as error:
        logging.getLogger("SattLint").error("Failed to generate Excel file: %s", error, exc_info=True)
        print(f"❌ Error: {error}")
        return 1

    return 0
