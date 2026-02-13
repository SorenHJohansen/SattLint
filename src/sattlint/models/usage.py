from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class VariableUsage:
    """Mutable state for variable usage analysis."""
    read: bool = False
    written: bool = False
    usage_locations: list[tuple[list[str], str]] = field(default_factory=list)
    field_reads: dict[str, list[list[str]]] = field(default_factory=dict)
    field_writes: dict[str, list[list[str]]] = field(default_factory=dict)

    @property
    def is_unused(self) -> bool:
        return not (self.read or self.written)

    @property
    def is_read_only(self) -> bool:
        return self.read and not self.written

    def mark_read(self, module_path: list[str]) -> None:
        self.read = True
        self.usage_locations.append((list(module_path), "read"))

    def mark_field_read(self, field_path: str, location: list[str]) -> None:
        """Mark a specific field (or nested field) as read."""
        if field_path not in self.field_reads:
            self.field_reads[field_path] = []
        self.field_reads[field_path].append(location)
        self.read = True  # also mark the variable itself as used

    def mark_written(self, module_path: list[str]) -> None:
        self.written = True
        self.usage_locations.append((list(module_path), "write"))

    def mark_field_written(self, field_path: str, location: list[str]) -> None:
        """Mark a specific field (or nested field) as written."""
        if field_path not in self.field_writes:
            self.field_writes[field_path] = []
        self.field_writes[field_path].append(location)
        self.written = True
