from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any
from ..models.ast_model import Variable, Simple_DataType
from ..analyzers.framework import format_report_header


class IssueKind(Enum):
    UNUSED = "unused"
    READ_ONLY_NON_CONST = "read_only_non_const"
    NEVER_READ = "never_read"
    STRING_MAPPING_MISMATCH = "string_mapping_mismatch"
    DATATYPE_DUPLICATION = "datatype_duplication"
    NAME_COLLISION = "name_collision"
    MIN_MAX_MAPPING_MISMATCH = "min_max_mapping_mismatch"


@dataclass
class VariableIssue:
    kind: IssueKind
    module_path: list[str]
    variable: Variable
    role: str | None = None
    source_variable: Variable | None = None
    duplicate_count: int | None = None  #
    duplicate_locations: list[tuple[list[str], str]] | None = None

    def __str__(self) -> str:
        mp = ".".join(self.module_path)
        dt = (
            self.variable.datatype.value
            if isinstance(self.variable.datatype, Simple_DataType)
            else str(self.variable.datatype)
        )
        role_txt = f"{self.role} "
        return f"[{mp}] {role_txt} {self.variable.name!r} ({dt})"


@dataclass
class VariablesReport:
    basepicture_name: str
    issues: list[VariableIssue]

    @property
    def name(self) -> str:
        return self.basepicture_name

    @property
    def unused(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.UNUSED]

    @property
    def read_only_non_const(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.READ_ONLY_NON_CONST]

    @property
    def never_read(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.NEVER_READ]

    @property
    def string_mapping_mismatch(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.STRING_MAPPING_MISMATCH]

    @property
    def datatype_duplication(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.DATATYPE_DUPLICATION]

    @property
    def min_max_mapping_mismatch(self) -> list[VariableIssue]:
        return [i for i in self.issues if i.kind is IssueKind.MIN_MAX_MAPPING_MISMATCH]

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Variable issues", self.basepicture_name, status="ok")
            lines.append("No issues found.")
            return "\n".join(lines)

        lines = format_report_header("Variable issues", self.basepicture_name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        if self.unused:
            lines.append("  - Unused variables:")
            for uv in self.unused:
                lines.append(f"      * {uv}")
        if self.read_only_non_const:
            lines.append("  - Read-only but not Const variables:")
            for rn in self.read_only_non_const:
                lines.append(f"      * {rn}")
        if self.never_read:
            lines.append("  - written, but never read variables:")
            for rn in self.never_read:
                lines.append(f"      * {rn}")

        if self.string_mapping_mismatch:
            lines.append("  - String mapping type mismatches:")
            lines.append("")

            # Compute column widths for aligned output.
            location_w = max(
                len(".".join(m.module_path)) for m in self.string_mapping_mismatch
            )
            src_name_w = max(
                len(m.source_variable.name) if m.source_variable else 0
                for m in self.string_mapping_mismatch
            )
            src_type_w = max(
                len(m.source_variable.datatype_text) if m.source_variable else 0
                for m in self.string_mapping_mismatch
            )
            tgt_name_w = max(len(m.variable.name) for m in self.string_mapping_mismatch)
            tgt_type_w = max(
                len(m.variable.datatype_text) for m in self.string_mapping_mismatch
            )

            # Table header
            header = (
                f"      {'Location':<{location_w}}  "
                f"{'Source Var':<{src_name_w}}  {'Type':<{src_type_w}}  =>  "
                f"{'Target Var':<{tgt_name_w}}  {'Type':<{tgt_type_w}}"
            )
            lines.append(header)
            lines.append("      " + "-" * len(header.strip()))

            # Table rows
            for m in self.string_mapping_mismatch:
                location = ".".join(m.module_path)
                src_name = m.source_variable.name if m.source_variable else "?"
                src_type = m.source_variable.datatype_text if m.source_variable else "?"
                tgt_name = m.variable.name
                tgt_type = m.variable.datatype_text

                row = (
                    f"      {location:<{location_w}}  "
                    f"{src_name:<{src_name_w}}  {src_type:<{src_type_w}}  =>  "
                    f"{tgt_name:<{tgt_name_w}}  {tgt_type:<{tgt_type_w}}"
                )
                lines.append(row)

            lines.append("")

        if self.datatype_duplication:
            lines.append("  - Duplicated complex datatypes (should be RECORD):")
            lines.append("")

            # Group by datatype name for duplication summary.
            by_dtype: dict[str, list[VariableIssue]] = {}
            for issue in self.datatype_duplication:
                dt_name = issue.variable.datatype_text
                by_dtype.setdefault(dt_name, []).append(issue)

            for dt_name, issues in sorted(by_dtype.items()):
                total_count = sum(i.duplicate_count or 0 for i in issues)
                lines.append(
                    f"      Datatype '{dt_name}' declared {total_count} times:"
                )

                for issue in issues:
                    loc = ".".join(issue.module_path)
                    lines.append(
                        f"        - {loc}: {issue.variable.name} ({issue.role})"
                    )

                    if issue.duplicate_locations:
                        for dup_path, dup_role in issue.duplicate_locations:
                            dup_loc = ".".join(dup_path)
                            lines.append(f"          + {dup_loc} ({dup_role})")

            lines.append("")

        if self.min_max_mapping_mismatch:
            lines.append("  - Min/Max mapping name mismatches:")
            lines.append("")

            location_w = max(
                len(".".join(m.module_path)) for m in self.min_max_mapping_mismatch
            )
            src_name_w = max(
                len(m.source_variable.name) if m.source_variable else 0
                for m in self.min_max_mapping_mismatch
            )
            tgt_name_w = max(
                len(m.variable.name) for m in self.min_max_mapping_mismatch
            )

            header = (
                f"      {'Location':<{location_w}}  "
                f"{'Source Var':<{src_name_w}}  =>  "
                f"{'Target Var':<{tgt_name_w}}"
            )
            lines.append(header)
            lines.append("      " + "-" * len(header.strip()))

            for m in self.min_max_mapping_mismatch:
                location = ".".join(m.module_path)
                src_name = m.source_variable.name if m.source_variable else "?"
                tgt_name = m.variable.name

                row = (
                    f"      {location:<{location_w}}  "
                    f"{src_name:<{src_name_w}}  =>  "
                    f"{tgt_name:<{tgt_name_w}}"
                )
                lines.append(row)

        return "\n".join(lines)
