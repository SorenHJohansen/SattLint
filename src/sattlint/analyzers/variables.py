# variables.py
from __future__ import annotations
from dataclasses import dataclass
import difflib
import re
from typing import Any, Union, cast
from enum import Enum
from pathlib import Path
from .sattline_builtins import get_function_signature
import logging
from ..grammar import constants as const
from ..resolution import (
    AccessEvent,
    AccessGraph,
    AccessKind,
    CanonicalPath,
    CanonicalSymbolTable,
    SymbolKind,
    TypeGraph,
    decorate_segment,
)
from ..models.ast_model import (
    BasePicture,
    SingleModule,
    FrameModule,
    ModuleTypeInstance,
    ModuleTypeDef,
    ModuleCode,
    Sequence,
    ModuleDef,
    Variable,
    SFCStep,
    SFCTransition,
    SFCAlternative,
    SFCParallel,
    SFCSubsequence,
    SFCTransitionSub,
    SFCFork,
    SFCBreak,
    ParameterMapping,
    Simple_DataType,
)

log = logging.getLogger("SattLint")

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

@dataclass
class ScopeContext:
    """Tracks variable environment with field-aware parameter mappings."""
    # Union of directly declared variables in this scope.
    # If both a parameter and a localvariable share the same name, the localvariable
    # wins in this mapping.
    env: dict[str, Variable]
    # Direct declarations split by kind, used for correct shadowing/mapping behavior.
    params: dict[str, Variable]
    locals: dict[str, Variable]
    # param_name -> (source_var, field_prefix, source_decl_module_path, source_decl_display_path)
    param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]]
    module_path: list[str]
    display_module_path: list[str]
    # casefolded library name for resolution (may be None)
    library: str | None = None
    parent_context: ScopeContext | None = None

    @staticmethod
    def _lookup_name(mapping: dict[str, Variable], name: str) -> Variable | None:
        # Prefer exact match; fall back to case-insensitive match only when unique.
        direct = mapping.get(name)
        if direct is not None:
            return direct
        name_cf = name.casefold()
        matches = [v for k, v in mapping.items() if k.casefold() == name_cf]
        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    def _lookup_mapping(
        mapping: dict[str, tuple[Variable, str, list[str], list[str]]],
        name: str,
    ) -> tuple[Variable, str, list[str], list[str]] | None:
        direct = mapping.get(name)
        if direct is not None:
            return direct
        name_cf = name.casefold()
        matches = [v for k, v in mapping.items() if k.casefold() == name_cf]
        if len(matches) == 1:
            return matches[0]
        return None

    def resolve_variable(self, var_ref: str) -> tuple[Variable | None, str, list[str], list[str]]:
        """
        Resolve a variable reference, reconstructing the full field path.

        Examples:
        - "signal.Comp_signal.value" with mapping (signal -> Dv.I.WT001)
          returns (Dv_variable, "I.WT001.Comp_signal.value")
        - "Dv.I.WT001.Comp_signal.value" in parent scope
          returns (Dv_variable, "I.WT001.Comp_signal.value")
        """
        base = var_ref.split(".", 1)[0]
        field_path = var_ref.split(".", 1)[1] if "." in var_ref else ""

        # Locals shadow everything in the current scope (including parameters and
        # mapped parameters).
        local_var = self._lookup_name(self.locals, base)
        if local_var:
            return local_var, field_path, self.module_path, self.display_module_path

        # Apply parameter mappings only when the name is actually a parameter in
        # this scope.
        mapping = self._lookup_mapping(self.param_mappings, base)
        param_decl = self._lookup_name(self.params, base)
        if mapping is not None and param_decl is not None:
            source_var, prefix, source_decl_path, source_decl_display_path = mapping
            if prefix and field_path:
                full_field_path = f"{prefix}.{field_path}"
            elif prefix:
                full_field_path = prefix
            else:
                full_field_path = field_path
            return source_var, full_field_path, source_decl_path, source_decl_display_path

        # Fall back to direct declarations.
        var = self._lookup_name(self.env, base)
        if var:
            return var, field_path, self.module_path, self.display_module_path

        # Try parent context
        if self.parent_context:
            return self.parent_context.resolve_variable(var_ref)

        return None, field_path, self.module_path, self.display_module_path


class IssueKind(Enum):
    UNUSED = "unused"
    READ_ONLY_NON_CONST = "read_only_non_const"
    NEVER_READ = "never_read"
    STRING_MAPPING_MISMATCH = "string_mapping_mismatch"
    DATATYPE_DUPLICATION = "datatype_duplication"
    NAME_COLLISION = "name_collision"


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

    def summary(self) -> str:
        if not self.issues:
            return f"No variable issues in {self.basepicture_name}"
        lines = [f"Variable issues in {self.basepicture_name}:"]
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

            # Calculate column widths
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

            # Header
            header = (
                f"      {'Location':<{location_w}}  "
                f"{'Source Var':<{src_name_w}}  {'Type':<{src_type_w}}  =>  "
                f"{'Target Var':<{tgt_name_w}}  {'Type':<{tgt_type_w}}"
            )
            lines.append(header)
            lines.append("      " + "-" * len(header.strip()))

            # Data rows
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

            # Group by datatype name
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
        return "\n".join(lines)


def analyze_variables(base_picture: BasePicture, debug: bool = False) -> VariablesReport:
    """
    Analyze a BasePicture AST and return a comprehensive report:
      - UNUSED variables
      - READ_ONLY_NON_CONST variables

    Variable.read / Variable.written are populated during traversal [3], and
    Variable itself remains the core AST (no report concerns baked in) [1].
    """
    analyzer = VariablesAnalyzer(base_picture, debug=debug)
    issues = analyzer.run()
    return VariablesReport(basepicture_name=base_picture.header.name, issues=issues)


def filter_variable_report(
    report: VariablesReport,
    kinds: set[IssueKind],
) -> VariablesReport:
    if not kinds:
        return report

    filtered = [i for i in report.issues if i.kind in kinds]

    return VariablesReport(
        basepicture_name=report.basepicture_name,
        issues=filtered,
    )


def debug_variable_usage(base_picture: BasePicture, var_name: str, debug: bool = False) -> str:
    """
    Run the analyzer and return a human-readable report for all variables
    with the given name across the AST, listing read/write usage with full field paths.
    """
    analyzer = VariablesAnalyzer(base_picture)
    _ = analyzer.run()

    matches = analyzer._any_var_index.get(var_name.lower(), [])
    if not matches:
        return f"No variables named {var_name!r} found."

    lines: list[str] = []
    lines.append(
        f"Usage report for variable name {var_name!r} ({len(matches)} declaration(s)):"
    )

    for idx, v in enumerate(matches, start=1):
        dt = v.datatype_text
        lines.append(
            f"[{idx}] {dt} | R:{bool(v.read)} W:{bool(v.written)}"
        )

        # Show field-level reads (deduplicated)
        if v.field_reads:
            lines.append("  Field reads:")
            for field_path, locations in sorted(v.field_reads.items()):
                # Count unique paths
                unique_paths = {}
                for loc in locations:
                    where = " -> ".join(loc)
                    unique_paths[where] = unique_paths.get(where, 0) + 1

                lines.append(f"    • {var_name}.{field_path}")
                for path, count in sorted(unique_paths.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      {path}{count_str}")

        # Show field-level writes (deduplicated)
        if v.field_writes:
            lines.append("  Field writes:")
            for field_path, locations in sorted(v.field_writes.items()):
                unique_paths = {}
                for loc in locations:
                    where = " -> ".join(loc)
                    unique_paths[where] = unique_paths.get(where, 0) + 1

                lines.append(f"    • {var_name}.{field_path}")
                for path, count in sorted(unique_paths.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      {path}{count_str}")

        # Show whole-variable accesses (deduplicated by path and kind)
        whole_var_locs = [
            (path, kind) for path, kind in v.usage_locations
            if kind in ("read", "write")
        ]
        if whole_var_locs:
            lines.append("  Whole variable:")
            # Group by path
            path_kinds = {}
            for path, kind in whole_var_locs:
                where = " -> ".join(path)
                if where not in path_kinds:
                    path_kinds[where] = {"read": 0, "write": 0}
                path_kinds[where][kind] += 1

            for path, kinds in sorted(path_kinds.items()):
                r_count = kinds["read"]
                w_count = kinds["write"]
                access = []
                if r_count > 0:
                    access.append(f"R:{r_count}")
                if w_count > 0:
                    access.append(f"W:{w_count}")
                lines.append(f"    {' '.join(access)} | {path}")

    return "\n".join(lines)


def analyze_datatype_usage(base_picture: BasePicture, var_name: str, debug: bool = False) -> str:
    """
    Analyze field-level usage for a specific variable across modules.
    """
    analyzer = VariablesAnalyzer(base_picture)
    _ = analyzer.run()

    matches = analyzer._any_var_index.get(var_name.lower(), [])
    if not matches:
        return f"Variable {var_name!r} not found."

    lines = [f"Field usage analysis for variable {var_name!r}:"]

    for idx, var in enumerate(matches, 1):
        lines.append(f"\n[{idx}] Declaration: {var.datatype_text}")
        lines.append(
            f"    Location: {' -> '.join(var.usage_locations[0][0]) if var.usage_locations else 'Unknown'}"
        )

        if var.field_reads or var.field_writes:
            # Combine all fields
            all_fields = set(var.field_reads.keys()) | set(var.field_writes.keys())

            lines.append(f"    Fields accessed: {len(all_fields)}")
            for field in sorted(all_fields):
                read_count = len(var.field_reads.get(field, []))
                write_count = len(var.field_writes.get(field, []))

                if read_count and write_count:
                    access = "READ+WRITE"
                elif read_count:
                    access = "READ"
                else:
                    access = "WRITE"

                lines.append(
                    f"      • {field}: {access} (R:{read_count}, W:{write_count})"
                )
        else:
            lines.append("    No field-level accesses tracked")

    return "\n".join(lines)

def analyze_module_localvar_fields(
    base_picture: BasePicture,
    module_path: str,
    var_name: str,
    debug: bool = False,
    fail_loudly: bool = False,
) -> str:
    """
    Analyze field-level usage of a local variable within a module and its submodules.
    ONLY follows actual parameter mapping aliases, not all variables with the same name.
    """
    # Resolve the target module strictly by BasePicture-relative dotted path.
    # This avoids ambiguity between module instances and typedef names.
    resolved = _resolve_module_by_strict_path(base_picture, module_path)
    module_def = resolved.node

    # Run analyzer WITHOUT back-propagation to build alias links.
    # IMPORTANT: limit traversal to the selected module subtree (plus its ancestor chain)
    # so unrelated modules aren't analyzed.
    analyzer = VariablesAnalyzer(base_picture, debug=debug, fail_loudly=fail_loudly)

    if debug:
        log.debug("Starting analysis (without alias back-propagation)")
    analyzer.run(
        apply_alias_back_propagation=False,
        limit_to_module_path=resolved.path,
    )

    if debug:
        log.debug(f"Analysis complete. Found {len(analyzer._alias_links)} alias links")
        if getattr(analyzer, "_mapping_warnings", None):
            log.debug(
                f"Analysis saw {len(analyzer._mapping_warnings)} parameter-mapping warning(s) "
                "(skipped alias creation for those mappings)."
            )

    # Find the SPECIFIC local variable instance.
    # - SingleModule: variable lives on the module node.
    # - ModuleTypeInstance: variable lives on the referenced ModuleTypeDef.
    def _pick_local_var(vars_: list[Variable]) -> Variable | None:
        # Prefer exact-case match; then case-insensitive match only if unique.
        exact = next((v for v in vars_ if v.name == var_name), None)
        if exact is not None:
            return exact
        matches = [v for v in vars_ if v.name.casefold() == var_name.casefold()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            opts = ", ".join(sorted({v.name for v in matches}))
            raise ValueError(
                f"Local variable name {var_name!r} is ambiguous in selected module scope {resolved.display_path_str!r}. "
                f"Matches: {opts}. Use exact casing."
            )
        return None
    module_type_info: str | None = None

    if isinstance(module_def, SingleModule):
        local_var = _pick_local_var(list(module_def.localvariables or []))
    elif isinstance(module_def, ModuleTypeInstance):
        mt = _resolve_moduletype_def_strict(
            base_picture,
            module_def.moduletype_name,
            current_library=getattr(base_picture, "origin_lib", None),
        )
        module_type_info = _format_moduletype_label(mt)
        local_var = _pick_local_var(list(mt.localvariables or []))
    else:
        raise ValueError(
            "Selected module path does not point to a SingleModule or ModuleTypeInstance. "
            f"Got: {type(module_def).__name__}"
        )

    if local_var is None:
        raise ValueError(
            f"Local variable {var_name!r} not found in selected module scope {resolved.display_path_str!r}."
        )

    module_path_list = resolved.path
    module_path_str = " -> ".join(module_path_list)

    if debug:
        log.debug(f"Target variable object id: {id(local_var)}")
        log.debug(f"Target variable datatype: {local_var.datatype_text}")
        log.debug(f"Finding aliases using graph traversal")

    # Find ONLY the Variable objects that are connected through alias links with field paths
    aliased_vars_with_paths = _find_all_aliases(local_var, analyzer._alias_links, debug=debug)
    # Include the local variable itself (direct field/whole-variable accesses).
    aliased_vars_with_paths.insert(0, (local_var, ""))

    if debug:
        log.debug(f"DEBUG: Found {len(aliased_vars_with_paths)} aliased variable instance(s):")
        for var, prefix in aliased_vars_with_paths:
            log.debug(f"  - {var.name} (id={id(var)}), prefix='{prefix}'")

    # Print all MessageSetup instances found with their prefixes
    messagesetup_instances = [(var, prefix) for var, prefix in aliased_vars_with_paths if var.name.lower() == "messagesetup"]
    if debug and messagesetup_instances:
        log.debug(f"DEBUG: Found {len(messagesetup_instances)} MessageSetup instance(s):")
        for var, prefix in messagesetup_instances:
            log.debug(f"       id={id(var)}, prefix='{prefix}'")

    # Build report
    header = f"Field usage analysis for local variable {var_name!r}"
    header += f" in module path {resolved.display_path_str!r}"
    lines = [
        header,
        f"Variable location: {module_path_str}",
        f"Variable datatype: {local_var.datatype_text}",
        f"Variable object ID: {id(local_var)}",
    ]
    if module_type_info is not None:
        lines.append(f"Module type: {module_type_info}")
    lines += [
        f"Found {len(aliased_vars_with_paths)} aliased variable instance(s) through parameter mappings",
        (
            f"Warnings during analysis: {len(analyzer.analysis_warnings)} (continued despite errors)"
            if analyzer.analysis_warnings
            else "Warnings during analysis: 0"
        ),
        "",
        "=" * 80,
        "",
    ]

    if analyzer.analysis_warnings:
        lines.append("Warnings:")
        for w in analyzer.analysis_warnings[:50]:
            lines.append(f"  - {w}")
        if len(analyzer.analysis_warnings) > 50:
            lines.append(f"  - ... ({len(analyzer.analysis_warnings) - 50} more)")
        lines += ["", "=" * 80, ""]

    # Aggregate ONLY from the connected aliases
    all_field_reads = {}
    all_field_writes = {}
    whole_var_reads = []
    whole_var_writes = []

    if debug:
        log.debug("Aggregating usages from connected aliases only")
    for var, field_prefix in aliased_vars_with_paths:
        # field_prefix may be empty for the root variable itself.

        # Merge field reads - reconstruct full field path (case-insensitive)
        for field_path, locations in (var.field_reads or {}).items():
            # Combine the field prefix from mappings with the field accessed on the variable.
            if field_prefix and field_path:
                full_field_path = f"{field_prefix}.{field_path}"
            elif field_prefix:
                full_field_path = field_prefix
            else:
                full_field_path = field_path

            if debug and full_field_path.lower() == "acktext":
                log.debug(f"DEBUG: Found field read 'acktext' - field_prefix='{field_prefix}', field_path={field_path}, var={var.name}(id={id(var)})")

            # Normalize to lowercase for case-insensitive comparison
            full_field_path_lower = full_field_path.lower()
            all_field_reads.setdefault(full_field_path_lower, []).extend(locations)

        # Merge field writes - reconstruct full field path (case-insensitive)
        for field_path, locations in (var.field_writes or {}).items():
            # Combine the field prefix from mappings with the field accessed on the variable.
            if field_prefix and field_path:
                full_field_path = f"{field_prefix}.{field_path}"
            elif field_prefix:
                full_field_path = field_prefix
            else:
                full_field_path = field_path

            if debug and full_field_path.lower() == "acktext":
                log.debug(f"DEBUG: Found field write 'acktext' - field_prefix='{field_prefix}', field_path={field_path}, var={var.name}(id={id(var)})")

            # Normalize to lowercase for case-insensitive comparison
            full_field_path_lower = full_field_path.lower()
            all_field_writes.setdefault(full_field_path_lower, []).extend(locations)

        # Merge whole variable accesses
        for loc, kind in (var.usage_locations or []):
            if kind == "read":
                whole_var_reads.append(loc)
            elif kind == "write":
                whole_var_writes.append(loc)

    # Filter to only show accesses from within this module tree
    def is_within_module(location: list[str]) -> bool:
        """Check if location is within the selected module path (or its submodules)."""
        return _path_startswith_casefold(location, module_path_list)

    # Field-level accesses
    internal_field_reads = {}
    internal_field_writes = {}

    for field_path, locations in all_field_reads.items():
        filtered = [loc for loc in locations if is_within_module(loc)]
        if filtered:
            internal_field_reads[field_path] = filtered

    for field_path, locations in all_field_writes.items():
        filtered = [loc for loc in locations if is_within_module(loc)]
        if filtered:
            internal_field_writes[field_path] = filtered

    # Whole variable accesses
    internal_whole_reads = [loc for loc in whole_var_reads if is_within_module(loc)]
    internal_whole_writes = [loc for loc in whole_var_writes if is_within_module(loc)]

    # Report field accesses
    all_fields = set(internal_field_reads.keys()) | set(internal_field_writes.keys())

    if all_fields:
        lines.append("FIELD-LEVEL ACCESSES:")
        lines.append("-" * 80)

        for field in sorted(all_fields):
            reads = internal_field_reads.get(field, [])
            writes = internal_field_writes.get(field, [])

            # Deduplicate locations
            unique_read_locs = {}
            for loc in reads:
                loc_str = " -> ".join(loc)
                unique_read_locs[loc_str] = unique_read_locs.get(loc_str, 0) + 1

            unique_write_locs = {}
            for loc in writes:
                loc_str = " -> ".join(loc)
                unique_write_locs[loc_str] = unique_write_locs.get(loc_str, 0) + 1

            access_type = []
            if reads:
                access_type.append("READ")
            if writes:
                access_type.append("WRITE")

            lines.append(f"\n  • {var_name}.{field} [{'/'.join(access_type)}]")

            if unique_read_locs:
                lines.append(f"    Reads ({sum(unique_read_locs.values())} total, {len(unique_read_locs)} unique location(s)):")
                for loc_str, count in sorted(unique_read_locs.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      - {loc_str}{count_str}")

            if unique_write_locs:
                lines.append(f"    Writes ({sum(unique_write_locs.values())} total, {len(unique_write_locs)} unique location(s)):")
                for loc_str, count in sorted(unique_write_locs.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      - {loc_str}{count_str}")
    else:
        lines.append("No field-level accesses found within this module.")

    # Report whole variable accesses
    if internal_whole_reads or internal_whole_writes:
        lines.append("")
        lines.append("=" * 80)
        lines.append("")
        lines.append("WHOLE VARIABLE ACCESSES:")
        lines.append("-" * 80)

        if internal_whole_reads:
            unique_reads = {}
            for loc in internal_whole_reads:
                loc_str = " -> ".join(loc)
                unique_reads[loc_str] = unique_reads.get(loc_str, 0) + 1

            lines.append(f"\n  Reads ({sum(unique_reads.values())} total, {len(unique_reads)} unique location(s)):")
            for loc_str, count in sorted(unique_reads.items()):
                count_str = f" ({count}x)" if count > 1 else ""
                lines.append(f"    - {loc_str}{count_str}")

        if internal_whole_writes:
            unique_writes = {}
            for loc in internal_whole_writes:
                loc_str = " -> ".join(loc)
                unique_writes[loc_str] = unique_writes.get(loc_str, 0) + 1

            lines.append(f"\n  Writes ({sum(unique_writes.values())} total, {len(unique_writes)} unique location(s)):")
            for loc_str, count in sorted(unique_writes.items()):
                count_str = f" ({count}x)" if count > 1 else ""
                lines.append(f"    - {loc_str}{count_str}")

    # Summary
    lines.append("")
    lines.append("=" * 80)
    lines.append("SUMMARY:")
    lines.append(f"  Variable object ID: {id(local_var)}")
    lines.append(f"  Aliased parameters: {len(aliased_vars_with_paths)}")
    lines.append(f"  Fields accessed: {len(all_fields)}")
    lines.append(f"  Total field reads: {sum(len(v) for v in internal_field_reads.values())}")
    lines.append(f"  Total field writes: {sum(len(v) for v in internal_field_writes.values())}")
    lines.append(f"  Whole variable reads: {len(internal_whole_reads)}")
    lines.append(f"  Whole variable writes: {len(internal_whole_writes)}")

    return "\n".join(lines)


def _find_all_aliases(target_var: Variable, alias_links: list[tuple[Variable, Variable, str]], debug: bool = False) -> list[tuple[Variable, str]]:
    """
    Given a target variable and the analyzer's alias links, find all variables
    that are transitively connected to it through parameter mappings.
    Returns list of (Variable, field_prefix_to_prepend) tuples.
    The field_prefix is the accumulated path of all mappings from the target to this variable.
    Only follows FORWARD links (source -> target), not backward, to avoid picking up
    unrelated parameters.
    Uses identity comparison (is) since Variable objects are not hashable.
    """
    aliases = []
    to_visit = [(target_var, "")]  # (variable, field_prefix_to_prepend_to_fields)
    visited: list[tuple[Variable, str]] = []

    while to_visit:
        current, current_prefix = to_visit.pop()

        # Check if already visited using identity + prefix
        if any(current is v and current_prefix == p for v, p in visited):
            continue

        visited.append((current, current_prefix))
        aliases.append((current, current_prefix))

        # Find all variables linked FROM current (only parent->child direction)
        for parent, child, mapping_name in alias_links:
            if parent is current:
                # When following parent->child link, accumulate the prefix
                # e.g., if current_prefix is "OpMessage1" and mapping_name is "AckText"
                # then the new prefix is "OpMessage1.AckText"
                if current_prefix and mapping_name:
                    new_prefix = f"{current_prefix}.{mapping_name}"
                elif current_prefix:
                    new_prefix = current_prefix
                else:
                    new_prefix = mapping_name
                if any(child is v and new_prefix == p for v, p in visited):
                    continue
                if debug and child.name.lower() == "messagesetup" and not mapping_name:
                    log.debug(f"DEBUG: MessageSetup alias with EMPTY mapping_name from {parent.name}(id={id(parent)})")
                to_visit.append((child, new_prefix))

    # Remove the original (we'll add it back in the caller)
    aliases = [(v, p) for v, p in aliases if v is not target_var]
    return aliases


def _find_module_instances(bp: BasePicture, typedef_name: str):
    """
    Find all instances of a module (by name) in the project.
    This handles both direct ModuleTypeInstances and modules defined within typedefs.

    Returns list of (module, full_path) tuples.
    """
    typedef_name_lower = typedef_name.lower()
    results = []

    # Helper: find where a typedef is used within another typedef's structure
    def find_in_typedef_tree(typedef: ModuleTypeDef, path: list[str]):
        """Search within a typedef's submodules for our target."""
        def search_subs(modules, current_path):
            for mod in modules or []:
                mod_path = current_path + [mod.header.name]

                # Check if this matches our target
                if isinstance(mod, ModuleTypeInstance):
                    if mod.moduletype_name.lower() == typedef_name_lower:
                        results.append((mod, mod_path, typedef.name))  # Also track parent typedef
                elif isinstance(mod, (SingleModule, FrameModule)):
                    if mod.header.name.lower() == typedef_name_lower:
                        results.append((mod, mod_path, typedef.name))

                # Recurse
                if isinstance(mod, (SingleModule, FrameModule)):
                    search_subs(mod.submodules or [], mod_path)

        search_subs(typedef.submodules or [], path)

    # First pass: find the module in all typedef definitions
    typedef_occurrences = []  # (module, path_within_typedef, parent_typedef_name)
    for mt in bp.moduletype_defs or []:
        find_in_typedef_tree(mt, [f"TypeDef:{mt.name}"])

    # results now contains (module, path_within_typedef, parent_typedef_name)
    # We need to find instances of the parent typedef and build full paths

    # Second pass: find direct instances in the project tree
    direct_instances = []

    def search_project_tree(modules, path):
        for mod in modules or []:
            current_path = path + [mod.header.name]

            if isinstance(mod, ModuleTypeInstance):
                if mod.moduletype_name.lower() == typedef_name_lower:
                    direct_instances.append((mod, current_path))

            if isinstance(mod, (SingleModule, FrameModule)):
                search_project_tree(mod.submodules or [], current_path)

    search_project_tree(bp.submodules, [bp.header.name])

    # Third pass: for each occurrence in a typedef, find instances of that parent typedef
    final_results = []
    for mod, typedef_path, parent_typedef_name in results:
        # Find instances of the parent typedef
        parent_instances = []

        def find_parent_instances(modules, path):
            for m in modules or []:
                p = path + [m.header.name]
                if isinstance(m, ModuleTypeInstance):
                    if m.moduletype_name.lower() == parent_typedef_name.lower():
                        parent_instances.append(p)
                if isinstance(m, (SingleModule, FrameModule)):
                    find_parent_instances(m.submodules or [], p)

        find_parent_instances(bp.submodules, [bp.header.name])

        # Build full paths
        relative_path = typedef_path[1:]  # Remove "TypeDef:X" prefix
        for parent_path in parent_instances:
            full_path = parent_path + relative_path
            final_results.append((mod, full_path))

    # Combine direct instances and typedef-based instances
    return direct_instances + final_results


def _find_var_in_scope(bp: BasePicture, instance_path: list[str], var_name: str) -> Variable | None:
    """
    Find a variable by name that's in scope at the given instance path.
    Searches from the instance location upwards through parent modules.
    """
    var_name_lower = var_name.lower()

    # Start from the parent of the instance (exclude the instance itself)
    parent_path = instance_path[:-1]

    # Search from the parent path upwards
    for i in range(len(parent_path), 0, -1):
        search_path = parent_path[:i]

        # Navigate to the module at this path
        if len(search_path) == 1:
            # At BasePicture level
            for v in bp.localvariables or []:
                if v.name.lower() == var_name_lower:
                    return v
            continue

        # Navigate through the path
        current = None
        for j, segment in enumerate(search_path[1:], 1):  # Skip "BasePicture"
            if j == 1:
                # First level: check if it's a TypeDef or submodule
                if segment.startswith("TypeDef:"):
                    typedef_name = segment.split(":", 1)[1]
                    current = next(
                        (mt for mt in bp.moduletype_defs or []
                         if mt.name == typedef_name),
                        None
                    )
                else:
                    current = next(
                        (mod for mod in bp.submodules or []
                         if hasattr(mod, 'header') and mod.header.name == segment),
                        None
                    )
            else:
                # Navigate deeper
                if current is None:
                    break

                if segment.startswith("TypeDef:"):
                    # We're at a typedef in the path - this shouldn't happen in normal navigation
                    # but let's handle it
                    break
                else:
                    if isinstance(current, (SingleModule, FrameModule)):
                        current = next(
                            (mod for mod in current.submodules or []
                             if hasattr(mod, 'header') and mod.header.name == segment),
                            None
                        )
                    else:
                        break

        if current is None:
            continue

        # Check variables at this level
        if isinstance(current, (SingleModule, ModuleTypeDef)):
            # Check localvariables
            for v in current.localvariables or []:
                if v.name.lower() == var_name_lower:
                    return v
            # Check moduleparameters
            for v in current.moduleparameters or []:
                if v.name.lower() == var_name_lower:
                    return v

    # Not found anywhere in the hierarchy
    return None


def _varname_base(var_dict_or_str: Any) -> str | None:
    """Extract base variable name from a variable_name dict or string."""
    if isinstance(var_dict_or_str, dict) and const.KEY_VAR_NAME in var_dict_or_str:
        full = var_dict_or_str[const.KEY_VAR_NAME]
    elif isinstance(var_dict_or_str, str):
        full = var_dict_or_str
    else:
        return None
    base = full.split(".", 1)[0] if full else None
    return base.lower() if base else None


@dataclass(frozen=True)
class ResolvedModulePath:
    node: Any
    path: list[str]
    display_path_str: str


def _path_startswith_casefold(location: list[str], prefix: list[str]) -> bool:
    if len(location) < len(prefix):
        return False
    for i, seg in enumerate(prefix):
        if location[i].casefold() != seg.casefold():
            return False
    return True


def _lib_key(lib: str | None) -> str | None:
    return lib.casefold() if isinstance(lib, str) else None


def _format_moduletype_label(mt: ModuleTypeDef) -> str:
    if mt.origin_lib:
        return f"{mt.origin_lib}:{mt.name}"
    return mt.name


def _resolve_moduletype_def_strict(
    bp: BasePicture, moduletype_name: str, current_library: str | None = None
) -> ModuleTypeDef:
    key = moduletype_name.casefold()
    matches = [mt for mt in (bp.moduletype_defs or []) if mt.name.casefold() == key]
    if not matches:
        available = sorted({mt.name for mt in (bp.moduletype_defs or [])})
        raise ValueError(
            f"Unknown moduletype {moduletype_name!r}. Available moduletype defs: {available[:50]}"
        )

    deps_raw = getattr(bp, "library_dependencies", {}) or {}
    deps_map = {
        _lib_key(lib): [_lib_key(dep) for dep in deps or []]
        for lib, deps in deps_raw.items()
    }

    def _mt_lib(mt: ModuleTypeDef) -> str | None:
        return _lib_key(getattr(mt, "origin_lib", None))

    lib_cf = _lib_key(current_library)
    if lib_cf:
        same_lib = [mt for mt in matches if _mt_lib(mt) == lib_cf]
        if len(same_lib) == 1:
            return same_lib[0]
        if len(same_lib) > 1:
            labels = sorted(_format_moduletype_label(mt) for mt in same_lib)
            raise ValueError(
                f"Ambiguous moduletype {moduletype_name!r} in library {current_library!r}: {labels}"
            )

        dep_libs = deps_map.get(lib_cf, [])
        dep_matches = [mt for mt in matches if _mt_lib(mt) in dep_libs]
        if len(dep_matches) == 1:
            return dep_matches[0]
        if len(dep_matches) > 1:
            labels = sorted(_format_moduletype_label(mt) for mt in dep_matches)
            raise ValueError(
                f"Ambiguous moduletype {moduletype_name!r} found in dependency libraries of {current_library!r}: {labels}"
            )

    if len(matches) == 1:
        return matches[0]

    labels = sorted(_format_moduletype_label(mt) for mt in matches)
    raise ValueError(
        f"Ambiguous moduletype {moduletype_name!r} (multiple definitions): {labels}"
    )


def _resolve_module_by_strict_path(bp: BasePicture, module_path: str) -> ResolvedModulePath:
    """Resolve a strict dotted module path relative to the BasePicture.

    - Input is case-insensitive.
    - No fallback/heuristics.
    - Any missing segment fails with a loud error.
    - Any ambiguous segment fails with a loud error.

    ModuleTypeInstance nodes have no `submodules`; if the path continues past a
    ModuleTypeInstance, subsequent segments are resolved within its referenced
    ModuleTypeDef's `submodules`.
    """
    raw = (module_path or "").strip()
    if not raw:
        raise ValueError("Empty module path")

    # Accept optional leading "<BasePictureName>." for convenience.
    bp_prefix = f"{bp.header.name}."
    if raw.casefold().startswith(bp_prefix.casefold()):
        raw = raw[len(bp_prefix) :].strip()
    if not raw:
        raise ValueError("Module path cannot point to BasePicture itself")

    if raw.startswith(".") or raw.endswith(".") or ".." in raw:
        raise ValueError(f"Invalid module path syntax: {module_path!r}")

    segments = raw.split(".")
    if any(not s.strip() for s in segments):
        raise ValueError(f"Invalid module path syntax: {module_path!r}")

    current: Any = bp
    resolved_path: list[str] = [bp.header.name]

    def children_of(node: Any) -> list[Any]:
        if isinstance(node, BasePicture):
            return list(node.submodules or [])
        if isinstance(node, (SingleModule, FrameModule, ModuleTypeDef)):
            return list(node.submodules or [])
        if isinstance(node, ModuleTypeInstance):
            mt = _resolve_moduletype_def_strict(
                bp,
                node.moduletype_name,
                current_library=getattr(bp, "origin_lib", None),
            )
            return list(mt.submodules or [])
        return []

    for seg in segments:
        wanted = seg.strip()
        candidates = children_of(current)
        if not candidates:
            raise ValueError(
                f"Module path {module_path!r} cannot continue past {resolved_path[-1]!r} "
                f"(node type: {type(current).__name__})."
            )

        matches: list[Any] = [
            m for m in candidates if hasattr(m, "header") and m.header.name.casefold() == wanted.casefold()
        ]

        if not matches:
            names = [m.header.name for m in candidates if hasattr(m, "header")]
            close = difflib.get_close_matches(wanted, names, n=5, cutoff=0.6)

            details: list[str] = []
            for m in candidates:
                if not hasattr(m, "header"):
                    continue
                if isinstance(m, ModuleTypeInstance):
                    try:
                        mt = _resolve_moduletype_def_strict(
                            bp,
                            m.moduletype_name,
                            current_library=getattr(bp, "origin_lib", None),
                        )
                        details.append(f"{m.header.name} ({_format_moduletype_label(mt)})")
                    except Exception:
                        details.append(f"{m.header.name} ({m.moduletype_name})")
                else:
                    details.append(m.header.name)

            msg = (
                f"Unknown module path segment {wanted!r} under {'.'.join(resolved_path)!r}. "
                f"Valid next segments: {details[:50]}"
            )
            if close:
                msg += f". Close matches: {close}"
            raise ValueError(msg)

        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous module path segment {wanted!r} under {'.'.join(resolved_path)!r}. "
                f"Matches: {[m.header.name for m in matches]}"
            )

        current = matches[0]
        resolved_path.append(matches[0].header.name)

    display_path = ".".join(resolved_path)
    return ResolvedModulePath(node=current, path=resolved_path, display_path_str=display_path)

def _find_module_by_name(bp: BasePicture, name: str):
    """Recursively find a module by name in the AST."""
    name_lower = name.lower()

    # First check if it's a ModuleTypeDef
    for mt in bp.moduletype_defs or []:
        if mt.name.lower() == name_lower:
            return mt

    # Then search in submodules (instances)
    def search(modules):
        for mod in modules or []:
            if hasattr(mod, 'header') and mod.header.name.lower() == name_lower:
                return mod
            if hasattr(mod, 'submodules'):
                result = search(mod.submodules)
                if result:
                    return result
        return None

    return search(bp.submodules)


def _get_module_path(bp: BasePicture, target_module) -> list[str]:
    """Get the full path to a module."""

    # Check if it's a ModuleTypeDef
    if isinstance(target_module, ModuleTypeDef):
        return [bp.header.name, f"TypeDef:{target_module.name}"]

    # Otherwise search in submodules
    def search(modules, path):
        for mod in modules or []:
            current_path = path + [mod.header.name]
            if mod is target_module:
                return current_path
            if hasattr(mod, 'submodules'):
                result = search(mod.submodules, current_path)
                if result:
                    return result
        return None

    result = search(bp.submodules, [bp.header.name])
    return result or []


def _is_external_to_module(location_path: list[str], module_path: list[str]) -> bool:
    """
    Check if a location is external to the module.

    For ModuleTypeDef (e.g., "TypeDef:Applik"):
    - External: location does NOT contain "TypeDef:Applik" in its path
    - Internal: location contains "TypeDef:Applik" in its path

    For regular modules:
    - External: location path doesn't start with the module's path
    - Internal: location path starts with the module's path
    """
    # Check if this is a TypeDef path
    if len(module_path) >= 2 and module_path[-1].startswith("TypeDef:"):
        typedef_segment = module_path[-1]
        # Internal if the typedef segment appears anywhere in the location path
        return typedef_segment not in location_path

    # For regular module instances, check if location starts with module_path
    if len(location_path) < len(module_path):
        return True

    # Check if location_path starts with module_path
    for i, segment in enumerate(module_path):
        if i >= len(location_path) or location_path[i] != segment:
            return True

    return False


# -----------------------------------------------------------------------------
# Analyzer
# -----------------------------------------------------------------------------


class VariablesAnalyzer:
    """
    Walks the AST and marks Variable.read / Variable.written via Variable.mark_read/mark_written [1][3].
    Propagates usage through ParameterMappings into child modules.
    GLOBAL mapping always counts the mapped source variable as used.
    External ModuleTypeInstance mappings are considered used.
    """

    def __init__(
        self,
        base_picture: BasePicture,
        debug: bool = False,
        fail_loudly: bool = True,
    ):
        self.bp = base_picture
        self.debug = debug
        self.fail_loudly = fail_loudly

        # Traversal context for better error messages (equation/sequence/step/etc.)
        self._site_stack: list[str] = []

        # Resolution layers
        self.type_graph = TypeGraph.from_basepicture(self.bp)
        self.symbol_table = CanonicalSymbolTable()
        self.access_graph = AccessGraph()

        self._bp_library: str | None = _lib_key(getattr(self.bp, "origin_lib", None))
        raw_deps = getattr(self.bp, "library_dependencies", {}) or {}
        self._library_deps: dict[str, list[str]] = {
            _lib_key(lib): [dep for dep in (deps or [])]
            for lib, deps in raw_deps.items()
        }

        self.typedef_index: dict[str, list[ModuleTypeDef]] = {}
        for mt in (self.bp.moduletype_defs or []):
            self.typedef_index.setdefault(mt.name.lower(), []).append(mt)

        self.used_params_by_typedef: dict[tuple[str, str], set[str]] = {}
        self.param_reads_by_typedef: dict[tuple[str, str], set[str]] = {}
        self.param_writes_by_typedef: dict[tuple[str, str], set[str]] = {}
        self._alias_links: list[
            tuple[Variable, Variable, str]
        ] = []  # (parent_var, child_param_var, field_path_in_parent)

        # Index BasePicture/global variables (localvariables)
        self._root_env: dict[str, Variable] = {v.name: v for v in (self.bp.localvariables or [])}

        # Fallback index across the whole AST (by name) to be robust
        self._any_var_index: dict[str, list[Variable]] = {}
        self._index_all_variables()
        self._analyzing_typedefs: set[tuple[str, str]] = set()

        # Unified collection of issues
        self._issues: list[VariableIssue] = []

        # Non-fatal analysis warnings (used when fail_loudly=False)
        self._analysis_warnings: list[str] = []

        self._STRING_LIMITS: dict[Simple_DataType, int] = {
            Simple_DataType.IDENTSTRING: 15,
            Simple_DataType.TAGSTRING: 30,
            Simple_DataType.STRING: 40,
            Simple_DataType.LINESTRING: 80,
            Simple_DataType.MAXSTRING: 140,
        }
        self._STRING_TYPES: set[Simple_DataType] = set(self._STRING_LIMITS.keys())

    @property
    def issues(self) -> list[VariableIssue]:
        return self._issues

    @property
    def analysis_warnings(self) -> list[str]:
        return self._analysis_warnings

    def _warn(self, message: str) -> None:
        self._analysis_warnings.append(message)
        log.warning(message)

    def _is_string_simple_type(self, dt: Simple_DataType | str | None) -> bool:
        return isinstance(dt, Simple_DataType) and dt in self._STRING_TYPES

    def _string_limit_for_datatype(
        self, dt: Simple_DataType | str | None
    ) -> int | None:
        if isinstance(dt, Simple_DataType):
            return self._STRING_LIMITS.get(dt)
        return None

    def _string_typename(self, dt: Simple_DataType | str | None) -> str:
        if isinstance(dt, Simple_DataType):
            return dt.value
        return str(dt) if dt is not None else "None"

    def _typedef_key_of(self, mt: ModuleTypeDef) -> tuple[str, str]:
        return (mt.name.lower(), _lib_key(getattr(mt, "origin_lib", None)) or "")

    def _record_mapping_mismatch_issue(
        self, tgt: Variable, src: Variable, path: list[str]
    ) -> None:
        issue = VariableIssue(
            kind=IssueKind.STRING_MAPPING_MISMATCH,
            module_path=path.copy(),
            variable=tgt,
            role="parameter mapping type mismatch",
            source_variable=src,
        )
        self._issues.append(issue)

    def _check_param_mappings_for_single(
        self,
        mod: SingleModule,
        child_env: dict[str, Variable],
        parent_env: dict[str, Variable],
        parent_path: list[str],
    ) -> None:
        params_by_name = {v.name: v for v in (mod.moduleparameters or [])}

        for pm in mod.parametermappings or []:
            tgt_name = self._varname_base(pm.target)
            tgt_var = params_by_name.get(tgt_name) if tgt_name else None
            self._check_param_mapping(pm, tgt_var, parent_env, parent_path)

    def _check_param_mappings_for_type_instance(
        self,
        inst,  # ModuleTypeInstance
        parent_env: dict[str, Variable],
        parent_path: list[str],
        current_library: str | None,
    ) -> None:
        mt = self._resolve_moduletype_for_context(
            inst.moduletype_name, current_library=current_library
        )
        if not mt:
            return
        # Only parameters are valid mapping targets [2]
        params_by_name = {v.name: v for v in (mt.moduleparameters or [])}
        for pm in inst.parametermappings or []:
            tgt_name = self._varname_base(pm.target)
            tgt_var = params_by_name.get(tgt_name) if tgt_name else None
            self._check_param_mapping(pm, tgt_var, parent_env, parent_path)

    def _check_param_mapping(
        self,
        pm: ParameterMapping,
        tgt_var: Variable | None,
        parent_env: dict[str, Variable],
        path: list[str],
    ) -> None:
        # If we cannot resolve target variable, we cannot validate types
        if tgt_var is None:
            return

        # 1) GLOBAL: no source variable to compare
        if pm.is_source_global:
            return

        # 2) Variable-to-variable mapping: enforce identical string type [2][4]
        src_var = self._lookup_env_var_from_varname_dict(pm.source, parent_env)
        if src_var is None:
            # Try resolving from root/global scope if not in parent env
            src_var = self._lookup_global_variable(self._varname_base(pm.source))

        if src_var is None:
            return  # cannot validate

        # Only check when both are built-in string types
        if self._is_string_simple_type(
            tgt_var.datatype
        ) and self._is_string_simple_type(src_var.datatype):
            if self.debug:
                log.debug(
                    f"DEBUG: Checking mapping at {path}: {src_var.name}:{src_var.datatype} -> {tgt_var.name}:{tgt_var.datatype}"
                )
            if tgt_var.datatype is not src_var.datatype:
                self._record_mapping_mismatch_issue(tgt_var, src_var, path)

    def _index_all_variables(self) -> None:
        def _add(v: Variable):
            self._any_var_index.setdefault(v.name.lower(), []).append(v)

        # BasePicture locals
        for v in self.bp.localvariables or []:
            _add(v)

        # Descendants
        def _walk(mods):
            for m in mods or []:
                if isinstance(m, SingleModule):
                    for v in m.moduleparameters or []:
                        _add(v)
                    for v in m.localvariables or []:
                        _add(v)
                    _walk(m.submodules or [])
                elif isinstance(m, FrameModule):
                    _walk(m.submodules or [])
                # ModuleTypeInstance declares no variables

        _walk(self.bp.submodules or [])

        # TypeDefs declared in this file
        for mt in self.bp.moduletype_defs or []:
            for v in mt.moduleparameters or []:
                _add(v)
            for v in mt.localvariables or []:
                _add(v)

    def _is_const_candidate(self, v: Variable) -> bool:
        # Built-ins are normalized to Simple_DataType in Variable.__post_init__ [1]
        return isinstance(v.datatype, Simple_DataType)

    def _canonical_path(
        self,
        decl_module_path: list[str],
        var: Variable,
        field_path: str,
    ) -> CanonicalPath:
        segs: list[str] = list(decl_module_path) + [var.name]
        if field_path:
            segs.extend([p for p in field_path.split(".") if p])
        return CanonicalPath(tuple(segs))

    def _record_access(
        self,
        kind: AccessKind,
        canonical_path: CanonicalPath,
        context: ScopeContext,
        syntactic_ref: str,
    ) -> None:
        self.access_graph.add(
            AccessEvent(
                kind=kind,
                canonical_path=canonical_path,
                use_module_path=tuple(context.module_path),
                use_display_path=tuple(context.display_module_path),
                syntactic_ref=syntactic_ref,
            )
        )

    def _mark_ref_access(
        self,
        full_ref: str,
        context: ScopeContext,
        path: list[str],
        kind: AccessKind,
    ) -> None:
        var, field_path, decl_module_path, _decl_display = context.resolve_variable(full_ref)
        if var is None:
            return

        # Store the usage location (where the code is), not the declaration location.
        # This allows filtering by module subtree to work correctly, especially with
        # Frame Modules that use enclosing scope and deep module hierarchies.
        if kind is AccessKind.READ:
            if field_path:
                var.mark_field_read(field_path, path)
            else:
                var.mark_read(path)
        else:
            if field_path:
                var.mark_field_written(field_path, path)
            else:
                var.mark_written(path)

        self._record_access(
            kind=kind,
            canonical_path=self._canonical_path(decl_module_path, var, field_path),
            context=context,
            syntactic_ref=full_ref,
        )

    def _site_str(self) -> str:
        if not self._site_stack:
            return ""
        return " > ".join(self._site_stack)

    def _push_site(self, label: str) -> None:
        if label:
            self._site_stack.append(label)

    def _pop_site(self) -> None:
        if self._site_stack:
            self._site_stack.pop()

    def _strict_datatype_at_field_prefix(
        self,
        root_type: Simple_DataType | str,
        field_prefix: str,
        *,
        fn_name: str,
        syntactic_ref: str,
        resolved_var_name: str,
        use_path: list[str],
    ) -> Simple_DataType | str:
        """Resolve the datatype at a dotted field-prefix (strict).

        Used only for record-wide builtin semantics.

        Raises ValueError if:
        - a referenced record type is unknown
        - a referenced field segment doesn't exist
        - the prefix continues into a scalar type
        """
        segments = [s for s in (field_prefix or "").split(".") if s]
        current: Simple_DataType | str = root_type

        for seg in segments:
            if isinstance(current, str):
                try:
                    current = Simple_DataType.from_any(current)
                except (ValueError, TypeError):
                    pass

            if isinstance(current, Simple_DataType):
                site = self._site_str()
                raise ValueError(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"cannot access field {seg!r} on scalar datatype {current.value!r}."
                )

            rec = self.type_graph.record(str(current))
            if rec is None:
                site = self._site_str()
                raise ValueError(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {str(current)!r}."
                )

            f = rec.fields_by_key.get(seg.casefold())
            if f is None:
                available = sorted({fd.name for fd in rec.fields_by_key.values()})
                close = difflib.get_close_matches(seg, available, n=5, cutoff=0.6)
                site = self._site_str()
                raise ValueError(
                    f"{fn_name}: at {' -> '.join(use_path)}"
                    f"{(' [' + site + ']') if site else ''}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown field {seg!r} in record datatype {rec.name!r}. "
                    f"Available fields: {available[:50]}"
                    + (f". Close matches: {close}" if close else "")
                )

            current = f.datatype

        return current

    def _iter_leaf_field_paths_strict(
        self,
        root_type: Simple_DataType | str,
        *,
        fn_name: str,
        syntactic_ref: str,
        resolved_var_name: str,
    ) -> list[tuple[str, ...]]:
        """Expand all leaf field paths for a datatype (strict).

        Returns tuples relative to the datatype root.
        Raises ValueError on unknown record types or cycles.
        """
        if isinstance(root_type, Simple_DataType):
            return [()]

        if isinstance(root_type, str):
            try:
                if isinstance(Simple_DataType.from_any(root_type), Simple_DataType):
                    return [()]
            except (ValueError, TypeError):
                pass

        # Builtin pseudo-type: cannot be expanded, treat as leaf.
        if isinstance(root_type, str) and root_type.casefold() == "anytype":
            return [()]

        start = str(root_type)
        results: list[tuple[str, ...]] = []
        stack: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [(start, (), ())]

        while stack:
            type_name, prefix, chain = stack.pop()
            key = type_name.casefold()

            if key in {c.casefold() for c in chain}:
                raise ValueError(
                    f"{fn_name}: datatype cycle detected while expanding {resolved_var_name!r} "
                    f"(ref {syntactic_ref!r}) at record datatype {type_name!r}."
                )

            rec = self.type_graph.record(type_name)
            if rec is None:
                # Unknown external type: record-wide expansion can't proceed.
                # Fail loudly for real record types, but allow the builtin pseudo-type.
                if type_name.casefold() == "anytype":
                    results.append(prefix)
                    continue
                try:
                    if isinstance(Simple_DataType.from_any(type_name), Simple_DataType):
                        results.append(prefix)
                        continue
                except (ValueError, TypeError):
                    pass
                raise ValueError(
                    f"{fn_name}: reference {syntactic_ref!r} resolves to {resolved_var_name!r} and "
                    f"uses unknown record datatype {type_name!r}."
                )

            next_chain = chain + (type_name,)
            for field in rec.fields_by_key.values():
                new_prefix = prefix + (field.name,)
                if isinstance(field.datatype, Simple_DataType):
                    results.append(new_prefix)
                else:
                    stack.append((str(field.datatype), new_prefix, next_chain))

        return results

    def _mark_record_wide_builtin_access(
        self,
        syntactic_ref: str,
        *,
        kind: AccessKind,
        fn_name: str,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        """Mark read/write for every leaf field under the resolved datatype.

        The `syntactic_ref` is what appears in code (e.g. "Dv.Y_Søjle" or "control").
        Resolution (param mappings) is applied via ScopeContext.resolve_variable().
        """
        resolved_var, resolved_field_prefix, _decl_path, _decl_display = context.resolve_variable(
            syntactic_ref
        )
        if resolved_var is None:
            site = self._site_str()
            raise ValueError(
                f"{fn_name}: at {' -> '.join(path)}"
                f"{(' [' + site + ']') if site else ''}: cannot resolve variable reference {syntactic_ref!r} for record-wide access."
            )

        dtype_at_prefix = self._strict_datatype_at_field_prefix(
            resolved_var.datatype,
            resolved_field_prefix,
            fn_name=fn_name,
            syntactic_ref=syntactic_ref,
            resolved_var_name=resolved_var.name,
            use_path=path,
        )

        leaf_paths = self._iter_leaf_field_paths_strict(
            dtype_at_prefix,
            fn_name=fn_name,
            syntactic_ref=syntactic_ref,
            resolved_var_name=resolved_var.name,
        )

        for leaf in leaf_paths:
            if not leaf:
                self._mark_ref_access(syntactic_ref, context, path, kind)
            else:
                self._mark_ref_access(
                    f"{syntactic_ref}.{'.'.join(leaf)}",
                    context,
                    path,
                    kind,
                )

    def _repath_context(
        self,
        context: ScopeContext,
        module_path: list[str],
        display_module_path: list[str],
    ) -> ScopeContext:
        return ScopeContext(
            env=context.env,
            params=context.params,
            locals=context.locals,
            param_mappings=context.param_mappings,
            module_path=module_path,
            display_module_path=display_module_path,
            library=context.library,
            parent_context=context.parent_context,
        )

    def _handle_function_call(
        self,
        fn_name: str | None,
        args: list,
        context: ScopeContext,
        path: list[str]
    ) -> None:
        """Handle function calls with proper parameter direction tracking."""
        if not fn_name:
            for a in args or []:
                self._walk_stmt_or_expr(a, context, path)
            return

        fn_key = fn_name.casefold()
        if fn_key in ("copyvariable", "copyvarnosort"):
            # Semantics: reads every field of Source, writes every field of Destination.
            if len(args or []) < 2:
                raise ValueError(f"{fn_name}: expected at least 2 arguments (Source, Destination)")

            src = args[0]
            dst = args[1]
            if not (isinstance(src, dict) and const.KEY_VAR_NAME in src):
                raise ValueError(f"{fn_name}: Source must be a variable reference")
            if not (isinstance(dst, dict) and const.KEY_VAR_NAME in dst):
                raise ValueError(f"{fn_name}: Destination must be a variable reference")

            try:
                self._mark_record_wide_builtin_access(
                    src[const.KEY_VAR_NAME],
                    kind=AccessKind.READ,
                    fn_name=fn_name,
                    context=context,
                    path=path,
                )
                self._mark_record_wide_builtin_access(
                    dst[const.KEY_VAR_NAME],
                    kind=AccessKind.WRITE,
                    fn_name=fn_name,
                    context=context,
                    path=path,
                )
            except ValueError as e:
                if self.fail_loudly:
                    raise
                self._warn(str(e))

            # Status is the 3rd arg (out) if present.
            if len(args) >= 3:
                status = args[2]
                if isinstance(status, dict) and const.KEY_VAR_NAME in status:
                    self._mark_ref_access(status[const.KEY_VAR_NAME], context, path, AccessKind.WRITE)
                else:
                    self._walk_stmt_or_expr(status, context, path)

            # Walk any extra args conservatively
            for extra in (args[3:] if len(args) > 3 else []):
                self._walk_stmt_or_expr(extra, context, path)
            return

        if fn_key == "initvariable":
            # Semantics (per user): writes defaults into every field of Rec; reads NOTHING.
            if len(args or []) < 1:
                raise ValueError(f"{fn_name}: expected at least 1 argument (Rec)")

            rec = args[0]
            if not (isinstance(rec, dict) and const.KEY_VAR_NAME in rec):
                raise ValueError(f"{fn_name}: Rec must be a variable reference")

            try:
                self._mark_record_wide_builtin_access(
                    rec[const.KEY_VAR_NAME],
                    kind=AccessKind.WRITE,
                    fn_name=fn_name,
                    context=context,
                    path=path,
                )
            except ValueError as e:
                if self.fail_loudly:
                    raise
                self._warn(str(e))

            # Skip InitRec entirely (args[1]) to avoid counting reads.
            # Status is args[2] (out) if present.
            if len(args) >= 3:
                status = args[2]
                if isinstance(status, dict) and const.KEY_VAR_NAME in status:
                    self._mark_ref_access(status[const.KEY_VAR_NAME], context, path, AccessKind.WRITE)
                else:
                    self._walk_stmt_or_expr(status, context, path)

            for extra in (args[3:] if len(args) > 3 else []):
                self._walk_stmt_or_expr(extra, context, path)
            return

        sig = get_function_signature(fn_name)
        if sig is None:
            for a in args or []:
                self._walk_stmt_or_expr(a, context, path)
            return

        for idx, arg in enumerate(args or []):
            direction = "in"
            if idx < len(sig.parameters):
                direction = sig.parameters[idx].direction

            if isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
                full_name = arg[const.KEY_VAR_NAME]
                if direction == "out":
                    self._mark_ref_access(full_name, context, path, AccessKind.WRITE)
                elif direction == "inout":
                    self._mark_ref_access(full_name, context, path, AccessKind.READ)
                    self._mark_ref_access(full_name, context, path, AccessKind.WRITE)
                else:
                    self._mark_ref_access(full_name, context, path, AccessKind.READ)
                continue

            self._walk_stmt_or_expr(arg, context, path)

    def _lookup_global_variable(self, base_name: str | None) -> Variable | None:
        if not base_name:
            return None
        var = ScopeContext._lookup_name(self._root_env, base_name)
        if var:
            return var
        lst = self._any_var_index.get(base_name.lower())
        return lst[0] if lst else None

    def _is_from_root_origin(self, origin_file: str | None) -> bool:
        if not origin_file:
            # If origin wasn't stamped (e.g., SCAN_ROOT_ONLY), treat as root.
            return True
        root_origin = getattr(self.bp, "origin_file", None)
        if not root_origin:
            # Without a root origin, be conservative: treat as not-from-root
            # (or return True if you want to analyze everything when origin is missing)
            return False

        try:
            return Path(origin_file).stem.lower() == Path(root_origin).stem.lower()
        except Exception:
            return (
                origin_file.rsplit(".", 1)[0].lower()
                == root_origin.rsplit(".", 1)[0].lower()
            )

    def _extract_field_path(self, var_dict: dict) -> tuple[str | None, str | None]:
        """
        Extract base variable name and field path from variable reference.
        E.g., "Dv.BatchID" -> ("Dv", "BatchID")
            "Dv.Recipe.Name" -> ("Dv", "Recipe.Name")
        """
        if not isinstance(var_dict, dict) or const.KEY_VAR_NAME not in var_dict:
            return None, None

        full_name = var_dict[const.KEY_VAR_NAME]
        if not full_name or "." not in full_name:
            return full_name if full_name else None, None

        parts = full_name.split(".", 1)
        base = parts[0]
        field_path = parts[1] if len(parts) > 1 else None

        return base, field_path

    # ------------ Entry point ------------

    def run(
        self,
        apply_alias_back_propagation: bool = True,
        limit_to_module_path: list[str] | None = None,
    ) -> list[VariableIssue]:
        # NOTE: When `limit_to_module_path` is set (used by option 9), we must NOT
        # analyze every ModuleTypeDef in the project. That would pull in unrelated
        # code and can legitimately fail loudly (e.g., record-wide builtins) outside
        # the selected subtree.
        self._issues = []
        self._mapping_warnings: list[str] = []
        self._analysis_warnings = []
        self._limit_to_module_path: list[str] | None = limit_to_module_path

        # Always log this to verify the analyzer is running
        log.debug(f"DEBUG: VariablesAnalyzer.run() called with debug={self.debug}")

        if self.debug:
            log.debug(f"DEBUG: Starting analysis run for {self.bp.header.name}")
            log.debug(f"  BasePicture localvariables: {len(self.bp.localvariables or [])}")
            log.debug(f"  Submodules: {len(self.bp.submodules or [])}")
            log.debug(f"  ModuleTypeDefs: {len(self.bp.moduletype_defs or [])}")

        # Build root scope context for BasePicture
        root_context = self._build_scope_context_for_basepicture()

        # Analyze BasePicture body
        self._walk_module_code(self.bp.modulecode, root_context, path=[self.bp.header.name])
        self._walk_moduledef(self.bp.moduledef, root_context, path=[self.bp.header.name])
        self._walk_header_enable(self.bp.header, root_context, path=[self.bp.header.name])
        self._walk_header_groupconn(self.bp.header, root_context, path=[self.bp.header.name])

        # Walk submodules with scope propagation
        self._walk_submodules(
            self.bp.submodules or [],
            parent_context=root_context,
            parent_path=[self.bp.header.name]
        )

        if apply_alias_back_propagation:
            if self.debug:
                log.debug("DEBUG: Applying alias back-propagation")
            self._apply_alias_back_propagation()

        if self.debug:
            log.debug(f"DEBUG: Detecting datatype duplications")
        self._detect_datatype_duplications()

        # Collect issues across this file
        bp_path = [self.bp.header.name]

        for v in self.bp.localvariables or []:
            role = "localvariable"
            if not (v.read or v.written):
                self._add_issue(IssueKind.UNUSED, bp_path, v, role=role)
            elif (
                bool(v.read)
                and not bool(v.written)
                and not bool(v.const)
                and self._is_const_candidate(v)
            ):
                self._add_issue(IssueKind.READ_ONLY_NON_CONST, bp_path, v, role=role)
            elif v.written and not v.read:
                self._add_issue(IssueKind.NEVER_READ, bp_path, v, role=role)

        for mod in self.bp.submodules or []:
            self._collect_issues_from_module(mod, path=bp_path)

        if self._limit_to_module_path is None:
            for mt in self.bp.moduletype_defs or []:
                if not self._is_from_root_origin(getattr(mt, "origin_file", None)):
                    continue
                td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]

                self._analyze_typedef(mt, path=[self.bp.header.name, f"TypeDef:{mt.name}"])

                # moduleparameters: UNUSED only
                for v in mt.moduleparameters or []:
                    role = "moduleparameter"
                    if not (v.read or v.written):
                        self._add_issue(IssueKind.UNUSED, td_path, v, role=role)
                # localvariables: UNUSED / READ_ONLY_NON_CONST / NEVER_READ
                for v in mt.localvariables or []:
                    role = "localvariable"
                    if not (v.read or v.written):
                        self._add_issue(IssueKind.UNUSED, td_path, v, role=role)
                    elif (
                        bool(v.read)
                        and not bool(v.written)
                        and not bool(v.const)
                        and self._is_const_candidate(v)
                    ):
                        self._add_issue(
                            IssueKind.READ_ONLY_NON_CONST, td_path, v, role=role
                        )
                    elif v.written and not v.read:
                        self._add_issue(IssueKind.NEVER_READ, td_path, v, role=role)

        if self.debug:
            log.debug(f"DEBUG: Analysis complete. Found {len(self._issues)} issues")

        return self._issues

    # ------------ Traversal helpers ------------

    def _add_issue(
        self, kind: IssueKind, path: list[str], variable: Variable, role: str
    ) -> None:
        self._issues.append(
            VariableIssue(
                kind=kind, module_path=path.copy(), variable=variable, role=role
            )
        )

    def _collect_issues_from_module(
        self,
        mod: Union[SingleModule, FrameModule, ModuleTypeInstance],
        path: list[str],
    ) -> None:
        if isinstance(mod, SingleModule):
            my_path = path + [mod.header.name]
            # Moduleparameters: only classify UNUSED (const does not apply to params)
            for v in mod.moduleparameters or []:
                if not (v.read or v.written):
                    self._add_issue(
                        IssueKind.UNUSED, my_path, v, role="moduleparameter"
                    )
            # Localvariables: both UNUSED and READ_ONLY_NON_CONST apply
            for v in mod.localvariables or []:
                if not (v.read or v.written):
                    self._add_issue(IssueKind.UNUSED, my_path, v, role="localvariable")
                elif (
                    bool(v.read)
                    and not bool(v.written)
                    and not bool(v.const)
                    and self._is_const_candidate(v)
                ):
                    self._add_issue(
                        IssueKind.READ_ONLY_NON_CONST, my_path, v, role="localvariable"
                    )
            for ch in mod.submodules or []:
                self._collect_issues_from_module(ch, my_path)

        elif isinstance(mod, FrameModule):
            my_path = path + [mod.header.name]
            for ch in mod.submodules or []:
                self._collect_issues_from_module(ch, my_path)

        elif isinstance(mod, ModuleTypeInstance):
            return

    # ------------ Traversal helpers ------------

    def _collect_unused_from_module(
        self,
        mod: Union[SingleModule, FrameModule, ModuleTypeInstance],
        path: list[str],
        out: list[VariableIssue],
    ) -> None:
        if isinstance(mod, SingleModule):
            my_path = path + [mod.header.name]
            for v in mod.moduleparameters or []:
                if not (v.read or v.written):
                    out.append(
                        VariableIssue(
                            kind=IssueKind.UNUSED, module_path=my_path, variable=v
                        )
                    )
            for v in mod.localvariables or []:
                if not (v.read or v.written):
                    out.append(
                        VariableIssue(
                            kind=IssueKind.UNUSED, module_path=my_path, variable=v
                        )
                    )
            for ch in mod.submodules or []:
                self._collect_unused_from_module(ch, my_path, out)

        elif isinstance(mod, FrameModule):
            my_path = path + [mod.header.name]
            for ch in mod.submodules or []:
                self._collect_unused_from_module(ch, my_path, out)

        elif isinstance(mod, ModuleTypeInstance):
            return

    def _build_scope_context_for_basepicture(self) -> ScopeContext:
        """Build root scope context for BasePicture."""
        env: dict[str, Variable] = {}
        params: dict[str, Variable] = {}
        locals_: dict[str, Variable] = {}
        for v in self.bp.localvariables or []:
            key = v.name
            env[key] = v
            locals_[key] = v

        module_path = [self.bp.header.name]
        display_path = [decorate_segment(self.bp.header.name, "BP")]

        for v in self.bp.localvariables or []:
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        return ScopeContext(
            env=env,
            params=params,
            locals=locals_,
            param_mappings={},
            module_path=module_path,
            display_module_path=display_path,
            library=self._bp_library,
            parent_context=None
        )

    def _build_scope_context_for_single(
        self,
        mod: SingleModule,
        parent_context: ScopeContext,
        module_path: list[str],
        display_module_path: list[str],
    ) -> ScopeContext:
        """Build scope context with parameter mapping resolution."""
        env: dict[str, Variable] = {}
        params_env: dict[str, Variable] = {}
        locals_env: dict[str, Variable] = {}

        # Add module parameters and locals
        params = list(mod.moduleparameters or [])
        locals_ = list(mod.localvariables or [])

        # Detect collisions ignoring case (e.g., X vs x). We still keep variables
        # distinct by case in the environment to avoid mis-resolution when both
        # exist in real projects.
        param_keys = {v.name.casefold(): v for v in params}
        local_keys = {v.name.casefold(): v for v in locals_}
        for k in (set(param_keys.keys()) & set(local_keys.keys())):
            p = param_keys[k]
            lv = local_keys[k]
            self._issues.append(
                VariableIssue(
                    kind=IssueKind.NAME_COLLISION,
                    module_path=module_path.copy(),
                    variable=lv,
                    role=f"name collision with parameter {p.name!r}",
                    source_variable=p,
                )
            )

        for v in params:
            key = v.name
            env[key] = v
            params_env[key] = v
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.PARAMETER,
                type_graph=self.type_graph,
            )
        for v in locals_:
            key = v.name
            env[key] = v
            locals_env[key] = v
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        # Build parameter mappings with field prefixes
        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]] = {}

        for pm in mod.parametermappings or []:
            target_name = self._varname_base(pm.target)
            if not target_name or pm.is_source_global:
                continue

            # Extract full source reference (e.g., "Dv.I.WT001")
            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                full_source = pm.source[const.KEY_VAR_NAME]
            elif isinstance(pm.source, str):
                full_source = pm.source
            else:
                continue

            # Resolve source variable from parent context
            source_var, source_field_prefix, source_decl_path, source_decl_display_path = parent_context.resolve_variable(full_source)

            if source_var:
                # Store mapping: parameter name -> (actual variable, field prefix)
                param_mappings[target_name] = (
                    source_var,
                    source_field_prefix,
                    source_decl_path,
                    source_decl_display_path,
                )

        return ScopeContext(
            env=env,
            params=params_env,
            locals=locals_env,
            param_mappings=param_mappings,
            module_path=module_path,
            display_module_path=display_module_path,
            library=parent_context.library,
            parent_context=parent_context
        )

    def _build_scope_context_for_typedef(
        self,
        mt: ModuleTypeDef,
        instance: ModuleTypeInstance,
        parent_context: ScopeContext | None = None,
        module_path: list[str] | None = None,
        display_module_path: list[str] | None = None,
    ) -> ScopeContext:
        """Build scope context for a typedef instance with parameter mappings."""
        env: dict[str, Variable] = {}
        params_env: dict[str, Variable] = {}
        locals_env: dict[str, Variable] = {}

        module_path = module_path or []
        display_module_path = display_module_path or []

        # Add typedef's parameters and locals
        params = list(mt.moduleparameters or [])
        locals_ = list(mt.localvariables or [])

        param_keys = {v.name.casefold(): v for v in params}
        local_keys = {v.name.casefold(): v for v in locals_}
        for k in (set(param_keys.keys()) & set(local_keys.keys())):
            p = param_keys[k]
            lv = local_keys[k]
            self._issues.append(
                VariableIssue(
                    kind=IssueKind.NAME_COLLISION,
                    module_path=module_path.copy(),
                    variable=lv,
                    role=f"name collision with parameter {p.name!r}",
                    source_variable=p,
                )
            )

        for v in params:
            key = v.name
            env[key] = v
            params_env[key] = v
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.PARAMETER,
                type_graph=self.type_graph,
            )
        for v in locals_:
            key = v.name
            env[key] = v
            locals_env[key] = v
            self.symbol_table.add_variable_root(
                module_path=module_path,
                var=v,
                kind=SymbolKind.LOCAL,
                type_graph=self.type_graph,
            )

        # Map instance parameters to parent variables
        param_mappings: dict[str, tuple[Variable, str, list[str], list[str]]] = {}
        for pm in instance.parametermappings or []:
            target_name = self._varname_base(pm.target)
            if not target_name or pm.is_source_global:
                continue

            if parent_context:
                # Allow full dotted source mapping for partial transfers
                if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                    full_source = pm.source[const.KEY_VAR_NAME]
                elif isinstance(pm.source, str):
                    full_source = pm.source
                else:
                    full_source = None

                if full_source:
                    source_var, source_field_prefix, source_decl_path, source_decl_display_path = parent_context.resolve_variable(full_source)
                    if source_var:
                        param_mappings[target_name] = (
                            source_var,
                            source_field_prefix,
                            source_decl_path,
                            source_decl_display_path,
                        )

        return ScopeContext(
            env=env,
            params=params_env,
            locals=locals_env,
            param_mappings=param_mappings,
            module_path=module_path,
            display_module_path=display_module_path,
            library=_lib_key(mt.origin_lib) or (parent_context.library if parent_context else self._bp_library),
            parent_context=parent_context
        )

    def _is_external_typename(self, typename: str) -> bool:
        # Type is external to this file if not present in BasePicture.moduletype_defs [3]
        return typename.lower() not in self.typedef_index

    def _resolve_moduletype_for_context(
        self, name: str, current_library: str | None
    ) -> ModuleTypeDef | None:
        try:
            return _resolve_moduletype_def_strict(
                self.bp, name, current_library=current_library
            )
        except ValueError as exc:
            if self.fail_loudly:
                raise
            self._analysis_warnings.append(str(exc))
            return None

    def _collect_read_only_non_const_from_module(
        self,
        mod: Union[SingleModule, FrameModule, ModuleTypeInstance],
        path: list[str],
        out: list[VariableIssue],
    ) -> None:
        if isinstance(mod, SingleModule):
            my_path = path + [mod.header.name]
            for v in mod.moduleparameters or []:
                if bool(v.read) and not bool(v.written) and not bool(v.const):
                    out.append(
                        VariableIssue(
                            kind=IssueKind.READ_ONLY_NON_CONST,
                            module_path=my_path,
                            variable=v,
                        )
                    )
            for v in mod.localvariables or []:
                if bool(v.read) and not bool(v.written) and not bool(v.const):
                    out.append(
                        VariableIssue(
                            kind=IssueKind.READ_ONLY_NON_CONST,
                            module_path=my_path,
                            variable=v,
                        )
                    )
            for ch in mod.submodules or []:
                self._collect_read_only_non_const_from_module(ch, my_path, out)

        elif isinstance(mod, FrameModule):
            my_path = path + [mod.header.name]
            for ch in mod.submodules or []:
                self._collect_read_only_non_const_from_module(ch, my_path, out)

        elif isinstance(mod, ModuleTypeInstance):
            return

    # ------------ ModuleTypeDef analysis ------------

    def _analyze_typedef(self, mt: ModuleTypeDef, path: list[str]) -> None:
        # Prevent infinite recursion
        mt_key = self._typedef_key_of(mt)
        if mt_key in self._analyzing_typedefs:
            return

        self._analyzing_typedefs.add(mt_key)

        try:
            params = list(mt.moduleparameters or [])
            locals_ = list(mt.localvariables or [])

            # Enforce: cannot have both a parameter and local with same name
            param_keys = {v.name.casefold(): v for v in params}
            local_keys = {v.name.casefold(): v for v in locals_}
            for k in (set(param_keys.keys()) & set(local_keys.keys())):
                p = param_keys[k]
                lv = local_keys[k]
                self._issues.append(
                    VariableIssue(
                        kind=IssueKind.NAME_COLLISION,
                        module_path=path.copy(),
                        variable=lv,
                        role=f"name collision with parameter {p.name!r}",
                        source_variable=p,
                    )
                )

            # Build environment from typedef's parameters + locals
            env: dict[str, Variable] = {}
            for v in params:
                env[v.name.lower()] = v
            for v in locals_:
                env[v.name.lower()] = v

            display_path: list[str] = []
            if path:
                display_path.append(decorate_segment(path[0], "BP"))
                for seg in path[1:]:
                    if seg.startswith("TypeDef:"):
                        display_path.append(decorate_segment(seg, "TD"))
                    else:
                        display_path.append(seg)

            # Create scope context
            context = ScopeContext(
                env=env,
                params={v.name.lower(): v for v in (mt.moduleparameters or [])},
                locals={v.name.lower(): v for v in (mt.localvariables or [])},
                param_mappings={},
                module_path=path.copy(),
                display_module_path=display_path,
                library=_lib_key(mt.origin_lib) or self._bp_library,
                parent_context=None
            )

            if self.debug:
                log.debug(f"DEBUG: _analyze_typedef for {mt.name}")
                log.debug(f"  env contains: {list(env.keys())}")

            # Scan typedef ModuleDef first (graph/interact), then ModuleCode
            self._walk_moduledef(mt.moduledef, context, path)
            self._walk_module_code(mt.modulecode, context, path)
            self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
            self._walk_typedef_groupconn(mt, context, path)

            # Track per-parameter read/write usage
            used_reads: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if v.read
            )
            used_writes: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if v.written
            )

            # Preserve existing "used" union for any other consumers
            used_params: set[str] = used_reads | used_writes
            self.used_params_by_typedef[mt_key] = used_params

            # Store separate read/write sets
            self.param_reads_by_typedef[mt_key] = used_reads
            self.param_writes_by_typedef[mt_key] = used_writes

            for pm in mt.parametermappings or []:
                tgt_name = self._varname_base(pm.target)
                tgt_var = env.get(tgt_name) if tgt_name else None
                self._check_param_mapping(pm, tgt_var, env, path)
        finally:
            self._analyzing_typedefs.discard(mt_key)

    def _apply_alias_back_propagation(self) -> None:
        """
        For every alias (parent_var -> child_param_var, field_prefix), replicate usage
        from the child parameter back to the parent variable WITH the field prefix.

        Example:
        parent_var = Dv
        child_var = OpMessage (parameter in child module)
        field_prefix = "OpMessage1"

        If OpMessage.AckText is accessed in child:
            -> Mark Dv field "OpMessage1.AckText" as accessed
        """
        for parent_var, child_var, field_prefix in self._alias_links:
            # **CHANGED**: Replicate field-level accesses WITH prefix reconstruction
            for field_path, locations in (child_var.field_reads or {}).items():
                # Reconstruct full field path: prefix + field accessed on parameter
                if field_prefix and field_path:
                    full_field_path = f"{field_prefix}.{field_path}"
                elif field_prefix:
                    full_field_path = field_prefix
                else:
                    full_field_path = field_path

                for loc in locations:
                    parent_var.mark_field_read(full_field_path, loc)

            for field_path, locations in (child_var.field_writes or {}).items():
                # Reconstruct full field path
                if field_prefix and field_path:
                    full_field_path = f"{field_prefix}.{field_path}"
                elif field_prefix:
                    full_field_path = field_prefix
                else:
                    full_field_path = field_path

                for loc in locations:
                    parent_var.mark_field_written(full_field_path, loc)

            # **CHANGED**: Replicate whole-variable accesses as field accesses
            # (accessing the parameter as a whole = accessing that field of parent)
            for loc, kind in (child_var.usage_locations or []):
                if field_prefix:
                    # If there's a field prefix, mark that field as accessed
                    if kind == "read":
                        parent_var.mark_field_read(field_prefix, loc)
                    elif kind == "write":
                        parent_var.mark_field_written(field_prefix, loc)
                else:
                    # No field prefix means whole variable mapping (rare case)
                    if kind == "read":
                        parent_var.mark_read(loc)
                    elif kind == "write":
                        parent_var.mark_written(loc)

    def _walk_submodules(
        self,
        children: list[Union[SingleModule, FrameModule, ModuleTypeInstance]],
        parent_context: ScopeContext,
        parent_path: list[str],
    ) -> None:
        """Walk submodules with proper scope context propagation."""

        for child in children:
            child_name = child.header.name
            child_path = parent_path + [child_name]

            if self._limit_to_module_path is not None:
                # Only traverse:
                #  - nodes along the path to the selected module, and
                #  - nodes within the selected module subtree.
                should_traverse = (
                    _path_startswith_casefold(self._limit_to_module_path, child_path)
                    or _path_startswith_casefold(child_path, self._limit_to_module_path)
                )
                if not should_traverse:
                    if self.debug:
                        log.debug(f"DEBUG: Skipping module {' -> '.join(child_path)} (outside limit {' -> '.join(self._limit_to_module_path)})")
                    continue
                elif self.debug:
                    log.debug(f"DEBUG: Traversing module {' -> '.join(child_path)} (within limit {' -> '.join(self._limit_to_module_path)})")

            if isinstance(child, SingleModule):
                child_display_path = parent_context.display_module_path + [
                    decorate_segment(child_name, "SM")
                ]
            elif isinstance(child, FrameModule):
                child_display_path = parent_context.display_module_path + [
                    decorate_segment(child_name, "FM")
                ]
            elif isinstance(child, ModuleTypeInstance):
                child_display_path = parent_context.display_module_path + [
                    decorate_segment(child_name, "MT", moduletype_name=child.moduletype_name)
                ]
            else:
                child_display_path = parent_context.display_module_path + [child_name]

            inst_context = self._repath_context(
                parent_context,
                module_path=child_path,
                display_module_path=child_display_path,
            )

            # Handle header-level enable and groupconn
            self._walk_header_enable(
                child.header, inst_context, path=child_path
            )
            self._walk_header_groupconn(
                child.header, inst_context, path=child_path
            )

            if isinstance(child, SingleModule):
                # **CHANGED**: Build scope context with parameter mappings
                child_context = self._build_scope_context_for_single(
                    child,
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )

                # **CHANGED**: Use child_context instead of building env dict
                self._walk_moduledef(
                    child.moduledef, child_context, child_path
                )
                self._walk_module_code(
                    child.modulecode, child_context, child_path
                )

                # Recursively walk submodules with child context
                self._walk_submodules(
                    child.submodules or [],
                    child_context,  # **CHANGED**: Pass child context, not parent
                    child_path,
                )

                # Track parameter usage for propagation (unchanged logic)
                used_reads: set[str] = set(
                    v.name.lower() for v in (child.moduleparameters or []) if v.read
                )
                used_writes: set[str] = set(
                    v.name.lower() for v in (child.moduleparameters or []) if v.written
                )

                # **CHANGED**: Create alias links with field path information
                for pm in child.parametermappings or []:
                    source_name = self._varname_base(pm.source)
                    target_name = self._varname_base(pm.target)

                    if source_name and target_name and not pm.is_source_global:
                        # **CHANGED**: Extract field prefix from mapping
                        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                            full_source_name = pm.source[const.KEY_VAR_NAME]
                        elif isinstance(pm.source, str):
                            full_source_name = pm.source
                        else:
                            continue

                        # **CHANGED**: Resolve with field path
                        source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(full_source_name)
                        target_var = ScopeContext._lookup_name(child_context.params, target_name)

                        if source_var and not target_var:
                            # Don't crash the full run for unrelated/broken mappings.
                            # We avoid fallbacks/heuristics and simply skip alias creation.
                            self._mapping_warnings.append(
                                f"Parameter mapping refers to unknown target parameter {target_name!r} "
                                f"in module {child_name!r}: {pm}"
                            )

                        if source_var and target_var:
                            # Store only the source field prefix (relative to the source variable).
                            # This must NOT include the target parameter name.
                            # Examples:
                            #   control => Dv        => mapping_name == ""         (Dv.cmd)
                            #   control => Dv.empty  => mapping_name == "empty"    (Dv.empty.cmd)
                            mapping_name = source_field_prefix or ""

                            if self.debug:
                                # Only log MessageSetup mappings to reduce noise
                                if target_var.name.lower() == "messagesetup" or source_var.name.lower() == "messagesetup":
                                    log.debug(f"DEBUG: Creating alias link: {source_var.name} (mapping='{mapping_name}') -> {target_var.name} at module {child_name}")
                            self._alias_links.append((source_var, target_var, mapping_name))

                # Propagate usage (unchanged)
                for pm in child.parametermappings or []:
                    self._propagate_mapping_to_parent(
                        pm,
                        child_used_reads=used_reads,
                        child_used_writes=used_writes,
                        parent_env=parent_context.env,
                        parent_path=parent_path,
                        external_typename=None,
                    )

                # Check string type mismatches (unchanged)
                self._check_param_mappings_for_single(
                    child,
                    child_env=child_context.env,
                    parent_env=parent_context.env,
                    parent_path=child_path,
                )

            elif isinstance(child, FrameModule):
                # FrameModule: no new scope, but access locations should be attributed to the frame's instance path.
                frame_context = self._repath_context(
                    parent_context,
                    module_path=child_path,
                    display_module_path=child_display_path,
                )
                self._walk_moduledef(
                    child.moduledef, frame_context, child_path
                )
                self._walk_module_code(
                    child.modulecode, frame_context, child_path
                )

                self._walk_submodules(
                    child.submodules or [],
                    frame_context,
                    child_path,
                )

            elif isinstance(child, ModuleTypeInstance):
                current_lib = parent_context.library
                mt = self._resolve_moduletype_for_context(
                    child.moduletype_name, current_library=current_lib
                )
                external = mt is None

                reads, writes = None, None  # Initialize to None

                if not external and mt:
                    mt_key = self._typedef_key_of(mt)

                    # **CHANGED**: Build typedef scope context with mappings
                    typedef_context = self._build_scope_context_for_typedef(
                        mt,
                        child,
                        parent_context,
                        module_path=child_path,
                        display_module_path=child_display_path,
                    )

                    # Analyze typedef if not already done
                    if mt_key not in self.param_reads_by_typedef and mt_key not in self._analyzing_typedefs:
                        # **CHANGED**: Use context-aware analysis
                        self._analyze_typedef_with_context(
                            mt, typedef_context, path=child_path
                        )

                    # **CHANGED**: Create alias links with field path information
                    for pm in child.parametermappings or []:
                        source_name = self._varname_base(pm.source)
                        target_name = self._varname_base(pm.target)

                        if source_name and target_name and not pm.is_source_global:
                            if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
                                full_source_name = pm.source[const.KEY_VAR_NAME]
                            elif isinstance(pm.source, str):
                                full_source_name = pm.source
                            else:
                                continue

                            # **CHANGED**: Resolve with field path
                            source_var, source_field_prefix, _decl_path, _decl_disp = parent_context.resolve_variable(full_source_name)
                            target_key = target_name.casefold()
                            target_var = ScopeContext._lookup_name(typedef_context.params, target_name)

                            if source_var and not target_var:
                                # Don't crash the full run for unrelated/broken mappings.
                                # We avoid fallbacks/heuristics and simply skip alias creation.
                                self._mapping_warnings.append(
                                    f"Parameter mapping refers to unknown target parameter {target_name!r} "
                                    f"in typedef instance {child_name!r}: {pm}"
                                )

                            if source_var and target_var:
                                # Store only the source field prefix (relative to the source variable).
                                # Do not include the target parameter name.
                                mapping_name = source_field_prefix or ""

                                if self.debug:
                                    # Only log MessageSetup mappings to reduce noise
                                    if target_var.name.lower() == "messagesetup" or source_var.name.lower() == "messagesetup":
                                        log.debug(f"DEBUG: Creating typedef alias link: {source_var.name} (mapping='{mapping_name}') -> {target_var.name} at typedef instance {child_name}")
                                self._alias_links.append((source_var, target_var, mapping_name))

                    reads = self.param_reads_by_typedef.get(mt_key, set())
                    writes = self.param_writes_by_typedef.get(mt_key, set())

                # Propagate usage (unchanged)
                for pm in child.parametermappings or []:
                    self._propagate_mapping_to_parent(
                        pm,
                        child_used_reads=reads,
                        child_used_writes=writes,
                        parent_env=parent_context.env,
                        parent_path=parent_path,
                        external_typename=(child.moduletype_name if external else None),
                    )

                if not external:
                    self._check_param_mappings_for_type_instance(
                        child,
                        parent_env=parent_context.env,
                        parent_path=parent_path + [child_name],
                        current_library=current_lib,
                    )


    def _analyze_single_module_with_context(
        self, mod: SingleModule, context: ScopeContext, path: list[str]
    ) -> tuple[set[str], set[str]]:
        """Analyze a SingleModule with scope context."""
        self._walk_moduledef(mod.moduledef, context, path)
        self._walk_module_code(mod.modulecode, context, path)
        self._walk_submodules(mod.submodules or [], parent_context=context, parent_path=path)

        used_reads: set[str] = set(
            v.name.lower() for v in (mod.moduleparameters or []) if v.read
        )
        used_writes: set[str] = set(
            v.name.lower() for v in (mod.moduleparameters or []) if v.written
        )
        return used_reads, used_writes

    def _analyze_typedef_with_context(
        self, mt: ModuleTypeDef, context: ScopeContext, path: list[str]
    ) -> None:
        """Analyze a ModuleTypeDef with scope context."""
        mt_key = self._typedef_key_of(mt)
        if mt_key in self._analyzing_typedefs:
            return

        self._analyzing_typedefs.add(mt_key)

        try:
            self._walk_moduledef(mt.moduledef, context, path)
            self._walk_module_code(mt.modulecode, context, path)
            self._walk_submodules(mt.submodules or [], parent_context=context, parent_path=path)
            self._walk_typedef_groupconn(mt, context, path)

            used_reads: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if v.read
            )
            used_writes: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if v.written
            )

            self.used_params_by_typedef[mt_key] = used_reads | used_writes
            self.param_reads_by_typedef[mt_key] = used_reads
            self.param_writes_by_typedef[mt_key] = used_writes
        finally:
            self._analyzing_typedefs.discard(mt_key)

    # ---------------- ModuleDef walkers ----------------
    def _walk_header_enable(self, header, context: ScopeContext, path):
        # ModuleHeader.enable_tail is a Tree(KEY_ENABLE_EXPRESSION) or Tree('InVar_') [5]
        tail = getattr(header, "enable_tail", None)
        if tail is not None:
            self._walk_tail(tail, context, path)

    def _walk_header_groupconn(self, header, context: ScopeContext, path):
        # header.groupconn is the variable_name dict
        # header.groupconn_global is True iff GLOBAL_KW was present in scan_group
        var_dict = getattr(header, "groupconn", None)
        if not isinstance(var_dict, dict):
            return

        base = self._varname_base(var_dict)
        if not base:
            return

        is_global = bool(getattr(header, "groupconn_global", False))

        # Only consult the global index when GLOBAL_KW was used.
        # Otherwise, resolve strictly within the current module env.
        if is_global:
            var = self._lookup_global_variable(base)
        else:
            var = ScopeContext._lookup_name(context.env, base)

        if var is not None:
            var.mark_read(path)

    def _walk_typedef_groupconn(self, mt, context: ScopeContext, path):
        var_dict = getattr(mt, "groupconn", None)
        if not isinstance(var_dict, dict):
            return
        base = self._varname_base(var_dict)
        if not base:
            return
        is_global = bool(getattr(mt, "groupconn_global", False))
        var = self._lookup_global_variable(base) if is_global else ScopeContext._lookup_name(context.env, base)
        if var is not None:
            var.mark_read(path)

    def _walk_moduledef(
        self, mdef: ModuleDef | None, context: ScopeContext, path: list[str]
    ) -> None:
        """Walk ModuleDef with scope context."""
        if mdef is None:
            return

        for go in mdef.graph_objects or []:
            self._walk_graph_object(go, context, path)

        for io in mdef.interact_objects or []:
            self._walk_interact_object(io, context, path)

        props = getattr(mdef, "properties", {}) or {}
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, context, path)

    def _walk_graph_object(self, go, context: ScopeContext, path):
        props = getattr(go, "properties", {}) or {}
        # NEW: text_vars list -> mark each as used
        for s in props.get("text_vars", []) or []:
            base = s.split(".", 1)[0] if isinstance(s, str) else None
            self._mark_var_by_basename(base, context.env, path)
        # Existing tails handling
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, context, path)

    def _walk_interact_object(self, io, context: ScopeContext, path):
        props = getattr(io, "properties", {}) or {}
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, context, path)
        self._scan_for_varrefs(props.get(const.KEY_BODY), context, path)

        proc = props.get(const.KEY_PROCEDURE)
        if isinstance(proc, dict) and const.KEY_PROCEDURE_CALL in proc:
            call = proc[const.KEY_PROCEDURE_CALL]
            fn_name = call.get(const.KEY_NAME)
            args = call.get(const.KEY_ARGS) or []
            self._handle_function_call(fn_name, args, context, path)

    def _scan_for_varrefs(
        self, obj: Any, context: ScopeContext, path: list[str]
    ) -> None:
        # Generic recursive scan used for interact object bodies and nested dict/tree structures
        if obj is None:
            return
        if isinstance(obj, list):
            for it in obj:
                self._scan_for_varrefs(it, context, path)
            return
        if isinstance(obj, dict):
            # enable dict
            if const.TREE_TAG_ENABLE in obj and const.KEY_TAIL in obj:
                self._walk_tail(obj[const.KEY_TAIL], context, path)
            # explicit assignment dict from interact_assign_variable
            if const.KEY_ASSIGN in obj:
                tail = (obj[const.KEY_ASSIGN] or {}).get(const.KEY_TAIL)
                if tail is not None:
                    self._walk_tail(tail, context, path)
            # descend into any values
            for v in obj.values():
                self._scan_for_varrefs(v, context, path)
            return
        # Trees: enable_expression, InVar_, invar_tail
        if hasattr(obj, "data"):
            data = getattr(obj, "data")
            if data in (
                const.KEY_ENABLE_EXPRESSION,
                const.GRAMMAR_VALUE_INVAR_PREFIX,
                "invar_tail",
            ):
                self._walk_tail(obj, context, path)
                return
            # descend into children
            for ch in getattr(obj, "children", []):
                self._scan_for_varrefs(ch, context, path)

    # ---------------- Tail handlers ----------------

    def _walk_tail(self, tail, context: ScopeContext, path):
        if tail is None:
            return

        # Expression tuple (from enable_expression)
        if isinstance(tail, tuple):
            self._walk_stmt_or_expr(tail, context, path)
            return

        # InVar string result: "Allow.ProgramDebug"
        if isinstance(tail, str):
            base = tail.split(".", 1)[0].lower()
            self._mark_var_by_basename(base, context.env, path)
            return

        # InVar variable_name dict result
        if isinstance(tail, dict) and const.KEY_VAR_NAME in tail:
            base = self._varname_base(tail)
            self._mark_var_by_basename(base, context.env, path)
            return

        raise ValueError(
            f"_walk_tail: unexpected tail type {type(tail).__name__}: {tail}"
        )

    def _extract_var_basenames_from_tree(
        self, node, allow_single_ident: bool = False
    ) -> set[str]:
        names: set[str] = set()

        def looks_like_varpath(s: str) -> bool:
            # dotted var path: A.B or A.B.C …
            return "." in s and s.split(".", 1)[0].strip() != ""

        def looks_like_ident(s: str) -> bool:
            # accept a simple identifier (used when allow_single_ident is True)
            return bool(s) and s[0].isalpha()

        def visit(x):
            if x is None:
                return
            if isinstance(x, dict) and const.KEY_VAR_NAME in x:
                full = x[const.KEY_VAR_NAME]
                if isinstance(full, str) and full:
                    names.add(full.split(".", 1)[0])
                return
            if isinstance(x, str):
                s = x.strip()
                if looks_like_varpath(s):
                    names.add(s.split(".", 1)[0])
                elif allow_single_ident and looks_like_ident(s):
                    names.add(s)
                return
            if isinstance(x, list):
                for y in x:
                    visit(y)
                return
            if hasattr(x, "children"):
                for ch in getattr(x, "children", []):
                    visit(ch)

        visit(node)
        return names

    _VARPATH_RE = re.compile(
        r"^[A-Za-zÆØÅæøå][A-Za-zÆØÅæøå0-9_']*(\.[A-Za-zÆØÅæøå][A-Za-zÆØÅæøå0-9_']*)+$"
    )

    def _looks_like_varpath(self, s: str) -> bool:
        # connected_variable may be a STRING containing e.g. Colours.Text (from GraphObjects in SattLine) [4]
        return bool(self._VARPATH_RE.match(s))

    def _mark_var_by_basename(
        self, base_name: str | None, env: dict[str, Variable], path: list[str]
    ) -> None:
        if not base_name:
            return
        var = ScopeContext._lookup_name(env, base_name)
        if var is None:
            var = self._lookup_global_variable(base_name)
        if var is not None:
            var.mark_read(path)
        else:
            if self.debug:
                log.debug(f"DEBUG: Variable '{base_name}' not found in env: {list(env.keys())}")

    # ------------ Propagation of parameter mappings ------------

    def _propagate_mapping_to_parent(
        self,
        pm: ParameterMapping,
        child_used_reads: set[str] | None,
        child_used_writes: set[str] | None,
        parent_env: dict[str, Variable],
        parent_path: list[str],
        external_typename: str | None,
    ) -> None:
        src_base = self._varname_base(pm.source)
        target_name = self._varname_base(pm.target)

        # GLOBAL means "used" at the global scope
        if pm.is_source_global:
            var = self._lookup_global_variable(src_base)
            if var is not None:
                var.mark_read(parent_path)
            return

        # **CHANGED**: Extract full source path with fields
        if isinstance(pm.source, dict) and const.KEY_VAR_NAME in pm.source:
            full_source = pm.source[const.KEY_VAR_NAME]
        elif isinstance(pm.source, str):
            full_source = pm.source
        else:
            return

        # **CHANGED**: Parse the source to get base and field path
        source_parts = full_source.split(".", 1)
        source_base = source_parts[0]
        source_field_path = source_parts[1] if len(source_parts) > 1 else ""

        # Resolve the actual source variable
        src_var = ScopeContext._lookup_name(parent_env, source_base)
        if src_var is None:
            src_var = self._lookup_global_variable(source_base)

        if src_var is None:
            return

        # External types: conservatively treat mapping as read+written
        if external_typename is not None:
            display_path: list[str] = []
            if parent_path:
                display_path.append(decorate_segment(parent_path[0], "BP"))
                display_path.extend(parent_path[1:])
            use_context = ScopeContext(
                env=parent_env,
                params={},
                locals={},
                param_mappings={},
                module_path=parent_path.copy(),
                display_module_path=display_path,
                parent_context=None,
            )

            if source_field_path:
                src_var.mark_field_read(source_field_path, parent_path)
                src_var.mark_field_written(source_field_path, parent_path)

                cp = self._canonical_path(parent_path, src_var, source_field_path)
                self._record_access(AccessKind.READ, cp, use_context, full_source)
                self._record_access(AccessKind.WRITE, cp, use_context, full_source)
            else:
                src_var.mark_read(parent_path)
                src_var.mark_written(parent_path)

                cp = self._canonical_path(parent_path, src_var, "")
                self._record_access(AccessKind.READ, cp, use_context, full_source)
                self._record_access(AccessKind.WRITE, cp, use_context, full_source)
            return

        # **CHANGED**: Internal types with field-aware propagation
        if target_name is not None:
            # If the child used the parameter for reading
            if child_used_reads is not None and target_name in child_used_reads:
                if source_field_path:
                    src_var.mark_field_read(source_field_path, parent_path)
                else:
                    src_var.mark_read(parent_path)

            # If the child used the parameter for writing
            if child_used_writes is not None and target_name in child_used_writes:
                if source_field_path:
                    src_var.mark_field_written(source_field_path, parent_path)
                else:
                    src_var.mark_written(parent_path)

    # ------------ ModuleCode walkers ------------

    def _walk_module_code(
        self,
        mc: ModuleCode | None,
        context: ScopeContext,
        path: list[str],
    ) -> None:
        """Walk ModuleCode with scope context."""
        if mc is None:
            return

        for seq in mc.sequences or []:
            label = f"SEQ:{getattr(seq, 'name', '<unnamed>')}"
            self._push_site(label)
            try:
                self._walk_sequence(seq, context, path)
            finally:
                self._pop_site()

        for eq in mc.equations or []:
            label = f"EQ:{getattr(eq, 'name', '<unnamed>')}"
            self._push_site(label)
            try:
                for stmt in eq.code or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            finally:
                self._pop_site()

    def _walk_sequence(
        self, seq: Sequence, context: ScopeContext, path: list[str]
    ) -> None:
        """Walk Sequence with scope context."""
        for node in seq.code or []:
            if isinstance(node, SFCStep):
                base = f"STEP:{node.name}"
                self._push_site(f"{base}:ENTER")
                try:
                    for stmt in node.code.enter or []:
                        self._walk_stmt_or_expr(stmt, context, path)
                finally:
                    self._pop_site()

                self._push_site(f"{base}:ACTIVE")
                try:
                    for stmt in node.code.active or []:
                        self._walk_stmt_or_expr(stmt, context, path)
                finally:
                    self._pop_site()

                self._push_site(f"{base}:EXIT")
                try:
                    for stmt in node.code.exit or []:
                        self._walk_stmt_or_expr(stmt, context, path)
                finally:
                    self._pop_site()

            elif isinstance(node, SFCTransition):
                label = f"TRANS:{node.name or '<unnamed>'}"
                self._push_site(label)
                try:
                    self._walk_stmt_or_expr(node.condition, context, path)
                finally:
                    self._pop_site()

            elif isinstance(node, SFCAlternative):
                for i, branch in enumerate(node.branches or []):
                    self._push_site(f"ALT:BRANCH:{i}")
                    try:
                        self._walk_seq_nodes(branch, context.env, path)
                    finally:
                        self._pop_site()

            elif isinstance(node, SFCParallel):
                for i, branch in enumerate(node.branches or []):
                    self._push_site(f"PAR:BRANCH:{i}")
                    try:
                        self._walk_seq_nodes(branch, context.env, path)
                    finally:
                        self._pop_site()

            elif isinstance(node, SFCSubsequence):
                self._push_site(f"SUBSEQ:{getattr(node, 'name', '<unnamed>')}")
                try:
                    self._walk_seq_nodes(node.body, context.env, path)
                finally:
                    self._pop_site()

            elif isinstance(node, SFCTransitionSub):
                self._push_site(f"TRANS-SUB:{getattr(node, 'name', '<unnamed>')}")
                try:
                    self._walk_seq_nodes(node.body, context.env, path)
                finally:
                    self._pop_site()

            elif isinstance(node, (SFCFork, SFCBreak)):
                # no variable usage in headers
                continue

    def _walk_seq_nodes(
        self, nodes: list[Any], env: dict[str, Variable], path: list[str]
    ) -> None:
        # Create a scope context from the environment
        display_path: list[str] = []
        if path:
            display_path.append(decorate_segment(path[0], "BP"))
            display_path.extend(path[1:])
        context = ScopeContext(
            env=env,
            params={},
            locals={},
            param_mappings={},
            module_path=path.copy(),
            display_module_path=display_path,
            parent_context=None
        )
        for nd in nodes:
            if isinstance(nd, SFCStep):
                for stmt in nd.code.enter or []:
                    self._walk_stmt_or_expr(stmt, context, path)
                for stmt in nd.code.active or []:
                    self._walk_stmt_or_expr(stmt, context, path)
                for stmt in nd.code.exit or []:
                    self._walk_stmt_or_expr(stmt, context, path)
            elif isinstance(nd, SFCTransition):
                self._walk_stmt_or_expr(nd.condition, context, path)
            elif isinstance(nd, SFCAlternative):
                for branch in nd.branches:
                    self._walk_seq_nodes(branch, env, path)
            elif isinstance(nd, SFCParallel):
                for branch in nd.branches:
                    self._walk_seq_nodes(branch, env, path)
            elif isinstance(nd, SFCSubsequence):
                self._walk_seq_nodes(nd.body, env, path)
            elif isinstance(nd, SFCTransitionSub):
                self._walk_seq_nodes(nd.body, env, path)

    # ------------ Statement/expression walkers ------------

    def _walk_stmt_or_expr(
        self,
        obj: Any,
        context: ScopeContext,
        path: list[str]
    ) -> None:
        # Tree wrapping for statements is present in transformer [5]; unwrap
        if hasattr(obj, "data") and getattr(obj, "data") == const.KEY_STATEMENT:
            for ch in getattr(obj, "children", []):
                self._walk_stmt_or_expr(ch, context, path)
            return

        # IF Statement: (IF, branches, else_block) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = obj
            for cond, stmts in branches or []:
                self._walk_stmt_or_expr(cond, context, path)
                for st in stmts or []:
                    self._walk_stmt_or_expr(st, context, path)
            for st in else_block or []:
                self._walk_stmt_or_expr(st, context, path)
            return

        # Ternary: (Ternary, [(cond, then_expr), ...], else_expr) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
            _, branches, else_expr = obj
            for cond, then_expr in branches or []:
                self._walk_stmt_or_expr(cond, context, path)
                self._walk_stmt_or_expr(then_expr, context, path)
            if else_expr is not None:
                self._walk_stmt_or_expr(else_expr, context, path)
            return

        # Function call: (FunctionCall, name, [args...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
            _, fn_name, args = obj
            self._handle_function_call(fn_name, args or [], context, path)
            return

        # Boolean OR/AND [5]
        if (
            isinstance(obj, tuple)
            and obj
            and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND)
        ):
            for sub in obj[1] or []:
                self._walk_stmt_or_expr(sub, context, path)
            return

        # NOT [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
            self._walk_stmt_or_expr(obj[1], context, path)
            return

        # Compare: (compare, left, [(sym, right), ...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
            _, left, pairs = obj
            self._walk_stmt_or_expr(left, context, path)
            for _sym, rhs in pairs or []:
                self._walk_stmt_or_expr(rhs, context, path)
            return

        # Add/Mul [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
            _, left, parts = obj
            self._walk_stmt_or_expr(left, context, path)
            for _opval, r in parts or []:
                self._walk_stmt_or_expr(r, context, path)
            return

        # Unary [+/- term] [5]
        if (
            isinstance(obj, tuple)
            and obj
            and obj[0] in (const.KEY_PLUS, const.KEY_MINUS)
        ):
            _, inner = obj
            self._walk_stmt_or_expr(inner, context, path)
            return

        # Interact/enable/invar tails may embed expressions/variable refs [5]
        if isinstance(obj, dict) and const.KEY_ENABLE_EXPRESSION in obj:
            tail = obj[const.KEY_ENABLE_EXPRESSION]
            self._walk_stmt_or_expr(tail, context, path)
            return

        # Tree wrappers for enable_expression / invar tails [5]
        if hasattr(obj, "data"):
            if getattr(obj, "data") == const.KEY_ENABLE_EXPRESSION:
                for ch in getattr(obj, "children", []):
                    self._walk_stmt_or_expr(ch, context, path)
                return
            if getattr(obj, "data") == const.GRAMMAR_VALUE_INVAR_PREFIX:
                for ch in getattr(obj, "children", []):
                    self._walk_stmt_or_expr(ch, context, path)
                return

        # Lists of nested statements
        if isinstance(obj, list):
            for it in obj:
                self._walk_stmt_or_expr(it, context, path)
            return

        # **CHANGED**: Variable reference with scope-aware resolution
        if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
            full_name = obj[const.KEY_VAR_NAME]
            self._mark_ref_access(full_name, context, path, AccessKind.READ)
            return

        # **CHANGED**: Assignment with scope-aware resolution
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
            _, target, expr = obj

            if isinstance(target, dict) and const.KEY_VAR_NAME in target:
                full_name = target[const.KEY_VAR_NAME]
                self._mark_ref_access(full_name, context, path, AccessKind.WRITE)

            self._walk_stmt_or_expr(expr, context, path)
            return

        # Tree wrapping for statements is present in transformer [5]; unwrap
        if hasattr(obj, "data") and getattr(obj, "data") == const.KEY_STATEMENT:
            for ch in getattr(obj, "children", []):
                self._walk_stmt_or_expr(ch, context, path)
            return

        # IF Statement: (IF, branches, else_block) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = obj
            for cond, stmts in branches or []:
                self._walk_stmt_or_expr(cond, context, path)
                for st in stmts or []:
                    self._walk_stmt_or_expr(st, context, path)
            for st in else_block or []:
                self._walk_stmt_or_expr(st, context, path)
            return

        # Ternary: (Ternary, [(cond, then_expr), ...], else_expr) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
            _, branches, else_expr = obj
            for cond, then_expr in branches or []:
                self._walk_stmt_or_expr(cond, context, path)
                self._walk_stmt_or_expr(then_expr, context, path)
            if else_expr is not None:
                self._walk_stmt_or_expr(else_expr, context, path)
            return

        # Function call: (FunctionCall, name, [args...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
            _, fn_name, args = (
                obj  # transformer emits (FunctionCall, name, [args...]) [3]
            )
            self._handle_function_call(fn_name, args or [], context, path)
            return

        # Boolean OR/AND [5]
        if (
            isinstance(obj, tuple)
            and obj
            and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND)
        ):
            for sub in obj[1] or []:
                self._walk_stmt_or_expr(sub, context, path)
            return

        # NOT [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
            self._walk_stmt_or_expr(obj[1], context, path)
            return

        # Compare: (compare, left, [(sym, right), ...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
            _, left, pairs = obj
            self._walk_stmt_or_expr(left, context, path)
            for _sym, rhs in pairs or []:
                self._walk_stmt_or_expr(rhs, context, path)
            return

        # Add/Mul [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
            _, left, parts = obj
            self._walk_stmt_or_expr(left, context, path)
            for _opval, r in parts or []:
                self._walk_stmt_or_expr(r, context, path)
                return

            # Unary [+/- term] [5]
            if (
                isinstance(obj, tuple)
                and obj
                and obj[0] in (const.KEY_PLUS, const.KEY_MINUS)
            ):
                _, inner = obj
                self._walk_stmt_or_expr(inner, context, path)
                return
            # Interact/enable/invar tails may embed expressions/variable refs [5]
            if isinstance(obj, dict) and const.KEY_ENABLE_EXPRESSION in obj:
                obj_dict: dict[str, Any] = cast(dict[str, Any], obj)
                tail = obj_dict.get(const.KEY_ENABLE_EXPRESSION)
                if tail is not None:
                    self._walk_stmt_or_expr(tail, context, path)
                return

            # Tree wrappers for enable_expression / invar tails [5]
            if hasattr(obj, "data"):
                if getattr(obj, "data") == const.KEY_ENABLE_EXPRESSION:
                    for ch in getattr(obj, "children", []):
                        self._walk_stmt_or_expr(ch, context, path)
                    return
                if getattr(obj, "data") == const.GRAMMAR_VALUE_INVAR_PREFIX:
                    for ch in getattr(obj, "children", []):
                        self._walk_stmt_or_expr(ch, context, path)
                    return

            # Lists of nested statements
            if isinstance(obj, list):
                for it in obj:
                    self._walk_stmt_or_expr(it, context, path)

            if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
                obj_dict: dict[str, Any] = cast(dict[str, Any], obj)
                full_name = obj_dict.get(const.KEY_VAR_NAME)
                if full_name is not None:
                    self._mark_ref_access(full_name, context, path, AccessKind.READ)
                return

            if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
                _, target, expr = obj

                if isinstance(target, dict) and const.KEY_VAR_NAME in target:
                    full_name = target[const.KEY_VAR_NAME]
                    self._mark_ref_access(full_name, context, path, AccessKind.WRITE)

                self._walk_stmt_or_expr(expr, context, path)
                return

    # ------------ Var lookup helpers ------------

    def _lookup_env_var_from_varname_dict(
        self,
        var_dict_or_other: Any,
        env: dict[str, Variable],
    ) -> Variable | None:
        """
        var_dict_or_other is either a {var_name: "..."} dict (from transformer.variable_name) [5],
        or something else (literal, None, etc.).
        """
        if (
            isinstance(var_dict_or_other, dict)
            and const.KEY_VAR_NAME in var_dict_or_other
        ):
            base = self._varname_base(var_dict_or_other)
            if base is not None:
                return ScopeContext._lookup_name(env, base)
        return None

    def _varname_base(self, var_dict_or_str: Any) -> str | None:
        if isinstance(var_dict_or_str, dict) and const.KEY_VAR_NAME in var_dict_or_str:
            full = var_dict_or_str[const.KEY_VAR_NAME]
        elif isinstance(var_dict_or_str, str):
            full = var_dict_or_str
        else:
            return None
        base = full.split(".", 1)[0] if full else None
        return base if base else None

    def _detect_datatype_duplications(self) -> None:
        """
        Find complex (record) datatypes that are declared multiple times
        across localvariables and moduleparameters instead of being defined
        as a RECORD type once and reused.
        """
        # Collect all variables with their locations
        var_locations: list[tuple[Variable, list[str], str]] = []

        # BasePicture locals
        bp_path = [self.bp.header.name]
        for v in self.bp.localvariables or []:
            var_locations.append((v, bp_path.copy(), "localvariable"))

        # Recursively collect from modules
        def _collect_from_module(
            mod: Union[SingleModule, FrameModule, ModuleTypeInstance], path: list[str]
        ):
            if isinstance(mod, SingleModule):
                my_path = path + [mod.header.name]
                for v in mod.moduleparameters or []:
                    var_locations.append((v, my_path.copy(), "moduleparameter"))
                for v in mod.localvariables or []:
                    var_locations.append((v, my_path.copy(), "localvariable"))
                for ch in mod.submodules or []:
                    _collect_from_module(ch, my_path)
            elif isinstance(mod, FrameModule):
                my_path = path + [mod.header.name]
                for ch in mod.submodules or []:
                    _collect_from_module(ch, my_path)

        for mod in self.bp.submodules or []:
            _collect_from_module(mod, bp_path)

        # Include TypeDef variables (only from root origin)
        for mt in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(getattr(mt, "origin_file", None)):
                continue
            td_path = [self.bp.header.name, f"TypeDef:{mt.name}"]
            for v in mt.moduleparameters or []:
                var_locations.append((v, td_path.copy(), "moduleparameter"))
            for v in mt.localvariables or []:
                var_locations.append((v, td_path.copy(), "localvariable"))

        # Only check non-built-in types (complex/record types)
        complex_vars = [
            (v, path, role)
            for v, path, role in var_locations
            if not isinstance(v.datatype, Simple_DataType)
        ]

        # Group by datatype name (case-insensitive)
        by_datatype: dict[str, list[tuple[Variable, list[str], str]]] = {}
        for v, path, role in complex_vars:
            dt_key = v.datatype_text.lower()
            by_datatype.setdefault(dt_key, []).append((v, path, role))

        # Report duplicates (2+ occurrences)
        for dt_name, occurrences in by_datatype.items():
            if len(occurrences) < 2:
                continue

            # Check if this is actually a defined RECORD type
            if dt_name in (d.name.lower() for d in self.bp.datatype_defs or []):
                # It's a legitimate record type being used multiple times - not a duplication issue
                continue

            # Create an issue for the first occurrence, listing all others
            first_var, first_path, first_role = occurrences[0]
            duplicate_locs = [(path, role) for _, path, role in occurrences[1:]]

            self._issues.append(
                VariableIssue(
                    kind=IssueKind.DATATYPE_DUPLICATION,
                    module_path=first_path,
                    variable=first_var,
                    role=first_role,
                    duplicate_count=len(occurrences),
                    duplicate_locations=duplicate_locs,
                )
            )
