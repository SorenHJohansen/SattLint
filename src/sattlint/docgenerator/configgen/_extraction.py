from __future__ import annotations

import logging
import re
import tomllib
from pathlib import Path

from sattline_parser.api import read_text_with_fallback

from ._types import ComponentInfo, ConfigurationContents, ConfigurationFileInfo, LibraryConfigEntry, ProgramConfigEntry

log = logging.getLogger("SattLint")


class ConfigurationFileParser:
    def __init__(self):
        self.config_pattern = re.compile(
            r'Configuration\s*\(\s*Version\s+"([^"]+)"\s+Date\s+"([^"]+)"\s+Name\s+"([^"]+)"', re.DOTALL
        )
        self.program_pattern = re.compile(
            r'Program\s*\(\s*Name\s+"([^"]+)"\s+Directory\s+"([^"]+)"\s+MainProgram\s+(\w+)', re.DOTALL
        )
        self.library_pattern = re.compile(r'Library\s*\(\s*Name\s+"([^"]+)"\s+Directory\s+"([^"]+)"', re.DOTALL)

    def parse_configuration_file(self, config_file: Path) -> ConfigurationFileInfo | None:
        try:
            text = read_text_with_fallback(config_file)
            config_match = self.config_pattern.search(text)
            if not config_match:
                log.warning("Could not parse configuration header in %s", config_file.name)
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

            main_program = next((p["name"] for p in programs if p["main_program"]), "None")
            log.info(
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
            log.error("Error parsing configuration file %s: %s", config_file, error)
            return None


class WorkstationMapper:
    def __init__(self):
        self.workstation_map = {
            "KaGC_OP_Utilf": ["LOP01", "OP06", "OP07"],
            "KaGC_OP_Procesf": ["OP01", "OP02", "OP03", "OP04", "OP05", "OP10"],
            "KaGC_Allf": ["OP11", "OP12", "LOP14"],
            "KaGC_Autf": ["PRG01", "PRG02"],
            "KaGC_OP_FDf": ["LOP11", "LOP12", "LOP13"],
            "KaGC_LOP04": ["LOP04"],
            "KaGC_LOP05": ["LOP05"],
            "KaGC_LOP08": ["LOP08"],
            "KaGC_LOP09": ["LOP09"],
            "KaGC_LOP10": ["LOP10"],
            "KaGC_LOP17": ["LOP17"],
            "KaGC_LOP18": ["LOP18"],
            "KaGC_LOP19": ["LOP19"],
            "KaGC_OPC01f": ["OPC01"],
            "KaGC_OPC02f": ["OPC02"],
            "KaGC_OPC03f": ["OPC03"],
            "KaGC_OPC04f": ["OPC04"],
            "KaGC_OPC05f": ["OPC05"],
            "KaGC_OPC06f": ["OPC06"],
            "KaGC_OPC07f": ["OPC07"],
            "KaGC_OPC08f": ["OPC08"],
            "KaGC_OPC09f": ["OPC09"],
            "KaGC_OPC10f": ["OPC10"],
            "KaGC_OPC11f": ["OPC11"],
            "SGDKKAGC01f": ["Kurver"],
            "KaGC_JN01f": ["Journal Server 1 Primær"],
            "KaGC_JN02f": ["Journal Server 1 Sekundær"],
            "KaGC_JN0304f": ["Journal Server 2 Primær", "Journal Server 2 Sekundær"],
        }
        self.physical_locations = {
            "LOP01": "Control Room 1",
            "OP06": "Control Room 2",
            "OP07": "Control Room 2",
            "OP01": "Main Control Room",
            "OP02": "Main Control Room",
            "OP03": "Main Control Room",
            "OP04": "Main Control Room",
            "OP05": "Main Control Room",
            "OP10": "Main Control Room",
            "OP11": "Control Room 3",
            "OP12": "Control Room 3",
            "LOP14": "Local Panel Area",
            "PRG01": "Engineering Office",
            "PRG02": "Engineering Office",
            "LOP11": "Field Station Area 1",
            "LOP12": "Field Station Area 1",
            "LOP13": "Field Station Area 1",
            "LOP04": "Field Station Area 2",
            "LOP05": "Field Station Area 2",
            "LOP08": "Field Station Area 3",
            "LOP09": "Field Station Area 3",
            "LOP10": "Field Station Area 3",
            "LOP17": "Field Station Area 4",
            "LOP18": "Field Station Area 4",
            "LOP19": "Field Station Area 4",
            "OPC01": "Server Room",
            "OPC02": "Server Room",
            "OPC03": "Server Room",
            "OPC04": "Server Room",
            "OPC05": "Server Room",
            "OPC06": "Server Room",
            "OPC07": "Server Room",
            "OPC08": "Server Room",
            "OPC09": "Server Room",
            "OPC10": "Server Room",
            "OPC11": "Server Room",
            "Kurver": "Curve Management Room",
            "Journal Server 1 Primær": "Server Room",
            "Journal Server 1 Sekundær": "Server Room",
            "Journal Server 2 Primær": "Server Room",
            "Journal Server 2 Sekundær": "Server Room",
        }

    def get_workstations(self, component_name: str) -> list[str]:
        component_name = component_name.replace(".z", "")
        for key in self.workstation_map:
            if key.lower() == component_name.lower():
                return self.workstation_map[key]
        return []

    def get_physical_location(self, station_id: str) -> str:
        return self.physical_locations.get(station_id, "Unknown Location")


class SattLineConfigExtractor:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.unitlib_dir = root_dir / "unitlib"
        self.projectlib_dir = root_dir / "projectlib"
        self.nnelib_dir = root_dir / "nnelib"
        self.sglib_dir = root_dir / "SL_Library"
        self.kfiles_dir = root_dir / "Configuration"
        self.slc_pattern = re.compile(r"SLC(\d+)", re.IGNORECASE)
        self.pbslc_pattern = re.compile(r"PBSLC(\d+)", re.IGNORECASE)
        self.name_pattern = re.compile(r'\(\s*Name\s+"([^"]+)"')
        self.unit_pattern = re.compile(r'\bp(\w+)\s*(?:"[^"]*")?\s*:\s*pType\s*;')
        if not self.validate_directories():
            raise ValueError("Required directories not found")

    def validate_directories(self) -> bool:
        required_dirs = [self.unitlib_dir, self.projectlib_dir, self.nnelib_dir, self.sglib_dir]
        missing_dirs = [directory for directory in required_dirs if not directory.exists()]
        if missing_dirs:
            log.error("Missing directories: %s", [str(directory) for directory in missing_dirs])
            return False
        log.info("✓ All required directories found")
        return True

    def parse_all_configuration_files(self) -> list[ConfigurationFileInfo]:
        parser = ConfigurationFileParser()
        configurations: list[ConfigurationFileInfo] = []
        if not self.kfiles_dir.exists():
            log.warning("Configuration directory not found: %s", self.kfiles_dir)
            return configurations
        config_files = sorted(self.kfiles_dir.glob("*.k"))
        if not config_files:
            log.warning("No .k files found in %s", self.kfiles_dir)
            return configurations
        log.info("Found %d configuration files", len(config_files))
        for config_file in config_files:
            config_info = parser.parse_configuration_file(config_file)
            if config_info:
                configurations.append(config_info)
        log.info("✓ Successfully parsed %d configuration files", len(configurations))
        return configurations

    def get_z_files(self, directory: Path) -> list[Path]:
        if not directory.exists():
            log.warning("Directory not found: %s", directory)
            return []
        return sorted(directory.glob("*.z"))

    def read_dependencies(self, z_file: Path) -> list[str]:
        try:
            text = read_text_with_fallback(z_file)
            return [line.strip().replace(".z", "") for line in text.splitlines() if line.strip()]
        except OSError as error:
            log.error("Error reading %s: %s", z_file, error)
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
            log.error("Error reading %s: %s", q_file, error)
            return "Error reading Q-File"

    def get_slc_name(self, ip_address: str, slc_programs: dict[str, str]) -> str:
        if ip_address in ["No Q-File", "No SLC assigned", "Error reading Q-File"]:
            return "No SLC"
        for prog_name, prog_ip in slc_programs.items():
            if prog_ip == ip_address and "pbslc" in prog_name.lower():
                match = self.pbslc_pattern.search(prog_name)
                if match:
                    return f"SLC{match.group(1)}"
            elif (
                prog_ip == ip_address
                and ("wdslc" in prog_name.lower() or prog_name.lower().startswith("kagcwd"))
                and (match := self.slc_pattern.search(prog_name))
            ):
                return f"SLC{match.group(1)}"
        return "No SLC"

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
            log.error("Error reading %s: %s", x_file, error)
            return "Error reading X-File"

    def get_component_info(
        self, z_file: Path, component_type: str, has_ip: bool, slc_programs: dict[str, str]
    ) -> ComponentInfo:
        component_name = z_file.stem
        dependencies = self.read_dependencies(z_file)
        if has_ip:
            ip = self.get_ip_address(z_file)
            slc = self.get_slc_name(ip, slc_programs)
            units = self.get_units_in_program(z_file)
        else:
            ip = slc = units = "N/A"
        return ComponentInfo(
            name=component_name,
            type=component_type,
            ip_address=ip,
            slc=slc,
            units=units,
            dependencies=dependencies,
        )

    def build_station_configurations(
        self, component_data: list[ComponentInfo], mapper: WorkstationMapper
    ) -> dict[str, ConfigurationContents | dict[str, object]]:
        station_configs: dict[str, dict[str, object]] = {}
        for config_file, workstations in mapper.workstation_map.items():
            for station_id in workstations:
                if station_id not in station_configs:
                    station_configs[station_id] = {
                        "config_file": config_file,
                        "type": self._determine_station_type(station_id),
                        "programs": [],
                        "libraries": [],
                        "units": None,
                        "ip_address": None,
                        "slc": None,
                    }

        configurations = self.parse_all_configuration_files()
        config_contents: dict[str, ConfigurationContents] = {}
        for config in configurations:
            config_contents[config.config_name.lower()] = {
                "programs": [program["name"] for program in config.programs],
                "libraries": [library["name"] for library in config.libraries],
            }

        for station_config in station_configs.values():
            config_file_lower = str(station_config["config_file"]).lower()
            if config_file_lower in config_contents:
                station_config["programs"] = config_contents[config_file_lower]["programs"].copy()
                station_config["libraries"] = config_contents[config_file_lower]["libraries"].copy()
                additional_libraries: set[str] = set()
                for program_name in station_config["programs"]:
                    comp = next((c for c in component_data if c.name.lower() == str(program_name).lower()), None)
                    if comp:
                        for dep in comp.dependencies:
                            dep_comp = next((c for c in component_data if c.name.lower() == dep.lower()), None)
                            if dep_comp and dep_comp.type != "Program":
                                additional_libraries.add(dep)
                for library in additional_libraries:
                    if not any(str(existing).lower() == library.lower() for existing in station_config["libraries"]):
                        station_config["libraries"].append(library)
                station_config["libraries"].sort()
                station_config["programs"].sort()

        return station_configs

    @staticmethod
    def _determine_station_type(station_id: str) -> str:
        if station_id.startswith("LOP"):
            return "Local Operator Panel"
        if station_id.startswith("OPC"):
            return "OPC Server"
        if station_id.startswith("OP"):
            return "Operator Station"
        if station_id.startswith("PRG"):
            return "Programmer Station"
        if "Journal" in station_id:
            return "Journal Server"
        return "Special System"
