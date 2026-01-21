# variables.py
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any, Union
from enum import Enum
from pathlib import Path
from .sattline_builtins import get_function_signature
import logging
from .. import constants as const
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


class IssueKind(Enum):
    UNUSED = "unused"
    READ_ONLY_NON_CONST = "read_only_non_const"
    NEVER_READ = "never_read"
    STRING_MAPPING_MISMATCH = "string_mapping_mismatch"
    DATATYPE_DUPLICATION = "datatype_duplication"


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


def analyze_variables(base_picture: BasePicture) -> VariablesReport:
    """
    Analyze a BasePicture AST and return a comprehensive report:
      - UNUSED variables
      - READ_ONLY_NON_CONST variables

    Variable.read / Variable.written are populated during traversal [3], and
    Variable itself remains the core AST (no report concerns baked in) [1].
    """
    analyzer = VariablesAnalyzer(base_picture)
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


def debug_variable_usage(base_picture: BasePicture, var_name: str) -> str:
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
        if hasattr(v.datatype, "value"):
            dt = v.datatype.value
        else:
            dt = str(v.datatype)
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


def analyze_datatype_usage(base_picture: BasePicture, var_name: str) -> str:
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
    module_name: str,
    var_name: str
) -> str:
    """
    Analyze field-level usage of a local variable within a module and its submodules.
    ONLY follows actual parameter mapping aliases, not all variables with the same name.
    """
    # Run analyzer WITHOUT back-propagation to build alias links
    analyzer = VariablesAnalyzer(base_picture)
    
    # Call internal methods directly, skipping the expensive back-propagation
    log.debug("Starting analysis (without back-propagation)")
    
    # Build root environment
    env = analyzer._build_env_for_basepicture(analyzer.bp)
    
    # Walk the AST to build alias links and track usage
    analyzer._walk_module_code(analyzer.bp.modulecode, env, path=[analyzer.bp.header.name])
    analyzer._walk_moduledef(analyzer.bp.moduledef, env, path=[analyzer.bp.header.name])
    analyzer._walk_header_enable(analyzer.bp.header, env, path=[analyzer.bp.header.name])
    analyzer._walk_header_groupconn(analyzer.bp.header, env, path=[analyzer.bp.header.name])
    analyzer._walk_submodules(
        analyzer.bp.submodules or [], parent_env=env, parent_path=[analyzer.bp.header.name]
    )
    
    log.debug(f"Analysis complete. Found {len(analyzer._alias_links)} alias links")
    
    # Find the module definition
    module_def = _find_module_by_name(base_picture, module_name)
    if module_def is None:
        return f"Module '{module_name}' not found."
    
    # Find the SPECIFIC local variable instance
    if isinstance(module_def, (SingleModule, ModuleTypeDef)):
        local_var = next(
            (v for v in (module_def.localvariables or [])
             if v.name.lower() == var_name.lower()),
            None
        )
    else:
        return f"Module '{module_name}' is not a SingleModule or TypeDef."
    
    if local_var is None:
        return f"Local variable '{var_name}' not found in module '{module_name}'."
    
    # Get the module's path in the tree
    module_path = _get_module_path(base_picture, module_def)
    module_path_str = " -> ".join(module_path)
    
    log.debug(f"Target variable object id: {id(local_var)}")
    log.debug(f"Finding aliases using graph traversal")
    
    # Find ONLY the Variable objects that are connected through alias links
    aliased_vars = _find_all_aliases(local_var, analyzer._alias_links)
    aliased_vars.append(local_var)  # Include the original
    
    log.debug(f"Found {len(aliased_vars)} aliased variables (connected through mappings)")
    for i, var in enumerate(aliased_vars[:10], 1):  # Log first 10
        log.debug(f"  [{i}] {var.name} (id={id(var)}, datatype={var.datatype_text})")
    
    # Build report
    lines = [
        f"Field usage analysis for local variable '{var_name}' in module '{module_name}'",
        f"Variable location: {module_path_str}",
        f"Variable datatype: {local_var.datatype_text}",
        f"Variable object ID: {id(local_var)}",
        f"Found {len(aliased_vars)} variable instance(s) connected through parameter mappings",
        "",
        "=" * 80,
        ""
    ]
    
    # Aggregate ONLY from the connected aliases
    all_field_reads = {}
    all_field_writes = {}
    whole_var_reads = []
    whole_var_writes = []
    
    log.debug("Aggregating usages from connected aliases only")
    for var in aliased_vars:
        # Merge field reads
        for field_path, locations in (var.field_reads or {}).items():
            all_field_reads.setdefault(field_path, []).extend(locations)
        
        # Merge field writes
        for field_path, locations in (var.field_writes or {}).items():
            all_field_writes.setdefault(field_path, []).extend(locations)
        
        # Merge whole variable accesses
        for loc, kind in (var.usage_locations or []):
            if kind == "read":
                whole_var_reads.append(loc)
            elif kind == "write":
                whole_var_writes.append(loc)
    
    log.debug(f"Total field reads: {sum(len(v) for v in all_field_reads.values())}")
    log.debug(f"Total field writes: {sum(len(v) for v in all_field_writes.values())}")
    
    # Filter to only show accesses from within this module tree
    def is_within_module(location: list[str]) -> bool:
        """Check if location is within the target module or its submodules."""
        # For TypeDef modules, check if TypeDef:ModuleName appears in path
        typedef_segment = f"TypeDef:{module_name}"
        return typedef_segment in location
    
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
    lines.append(f"  Connected aliases: {len(aliased_vars) - 1}")
    lines.append(f"  Fields accessed: {len(all_fields)}")
    lines.append(f"  Total field reads: {sum(len(v) for v in internal_field_reads.values())}")
    lines.append(f"  Total field writes: {sum(len(v) for v in internal_field_writes.values())}")
    lines.append(f"  Whole variable reads: {len(internal_whole_reads)}")
    lines.append(f"  Whole variable writes: {len(internal_whole_writes)}")
    
    return "\n".join(lines)


def _find_all_aliases(target_var: Variable, alias_links: list[tuple[Variable, Variable]]) -> list[Variable]:
    """
    Given a target variable and the analyzer's alias links, find all variables
    that are transitively connected to it through parameter mappings.
    Uses identity comparison (is) since Variable objects are not hashable.
    """
    aliases = []
    to_visit = [target_var]
    visited = []
    
    while to_visit:
        current = to_visit.pop()
        
        # Check if already visited using identity
        if any(current is v for v in visited):
            continue
        
        visited.append(current)
        aliases.append(current)
        
        # Find all variables linked to current
        for parent, child in alias_links:
            if parent is current and not any(child is v for v in visited):
                to_visit.append(child)
            elif child is current and not any(parent is v for v in visited):
                to_visit.append(parent)
    
    # Remove the original (we'll add it back in the caller)
    aliases = [v for v in aliases if v is not target_var]
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
                    if hasattr(current, 'submodules'):
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

    def __init__(self, base_picture: BasePicture):
        self.bp = base_picture
        self.typedef_index = {
            mt.name.lower(): mt for mt in (self.bp.moduletype_defs or [])
        }
        self.used_params_by_typedef: dict[str, set[str]] = {}
        self.param_reads_by_typedef: dict[str, set[str]] = {}
        self.param_writes_by_typedef: dict[str, set[str]] = {}
        self._alias_links: list[
            tuple[Variable, Variable]
        ] = []  # (parent_var, child_param_var)

        # Index BasePicture/global variables (localvariables)
        self._root_env: dict[str, Variable] = {
            v.name.lower(): v for v in (self.bp.localvariables or [])
        }

        # Fallback index across the whole AST (by name) to be robust
        self._any_var_index: dict[str, list[Variable]] = {}
        self._index_all_variables()
        self._analyzing_typedefs: set[str] = set()

        # Unified collection of issues
        self._issues: list[VariableIssue] = []

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
    ) -> None:
        mt = self.typedef_index.get(inst.moduletype_name.lower())
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

    def _handle_function_call(
        self, fn_name: str | None, args: list, env: dict[str, Variable], path: list[str]
    ) -> None:
        if not fn_name:
            # Defensive: walk arguments generically
            for a in args or []:
                self._walk_stmt_or_expr(a, env, path)
            return

        sig = get_function_signature(fn_name)  # lowercasing is handled inside [1]
        if sig is None:
            # Unknown function: fallback to generic traversal
            for a in args or []:
                self._walk_stmt_or_expr(a, env, path)
            return

        for idx, arg in enumerate(args or []):
            # Default to 'in' if more args are supplied than we have parameters
            direction = "in"
            if idx < len(sig.parameters):
                direction = sig.parameters[
                    idx
                ].direction  # "in", "in var", "out", "inout" [1]

            if isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
                base, field_path = self._extract_field_path(arg)
                var = env.get(base) or self._lookup_global_variable(base)

                if var is not None and field_path:
                    if direction == "out":
                        var.mark_field_written(field_path, path)
                    elif direction == "inout":
                        var.mark_field_read(field_path, path)
                        var.mark_field_written(field_path, path)
                    else:  # "in" or "in var"
                        var.mark_field_read(field_path, path)

            # If the argument is a plain variable reference dict, handle directly by direction
            if isinstance(arg, dict) and const.KEY_VAR_NAME in arg:
                base = self._varname_base(arg)  # e.g., "p" from "p.BatchID" [2]
                if base:
                    var = env.get(base) or self._lookup_global_variable(base)
                    if var is not None:
                        if direction == "out":
                            var.mark_written(path)
                        elif direction == "inout":
                            var.mark_read(path)
                            var.mark_written(path)
                        else:
                            # "in" or "in var"
                            var.mark_read(path)
                # Do not recurse: we already handled this var by direction
                continue

            # Non-variable argument (literal or nested expression): traverse it
            self._walk_stmt_or_expr(arg, env, path)

    def _lookup_global_variable(self, base_name: str | None) -> Variable | None:
        if not base_name:
            return None
        normalized = base_name.lower()
        var = self._root_env.get(normalized)
        if var:
            return var
        lst = self._any_var_index.get(normalized)
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
            return full_name.lower() if full_name else None, None

        parts = full_name.split(".", 1)
        base = parts[0].lower()
        field_path = parts[1] if len(parts) > 1 else None

        return base, field_path

    # ------------ Entry point ------------

    def run(self) -> list[VariableIssue]:
        # Pre-analyze ModuleTypeDefs to know which of their parameters are used internally
        self._issues = []

        # Analyze BasePicture module body
        env = self._build_env_for_basepicture(self.bp)
        self._walk_module_code(self.bp.modulecode, env, path=[self.bp.header.name])
        self._walk_moduledef(self.bp.moduledef, env, path=[self.bp.header.name])
        self._walk_header_enable(self.bp.header, env, path=[self.bp.header.name])
        self._walk_header_groupconn(self.bp.header, env, path=[self.bp.header.name])

        # Walk submodules; propagate usage
        self._walk_submodules(
            self.bp.submodules or [], parent_env=env, parent_path=[self.bp.header.name]
        )
        self._apply_alias_back_propagation()
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

    def _build_env_for_basepicture(self, bp: BasePicture) -> dict[str, Variable]:
        env: dict[str, Variable] = {}
        for v in bp.localvariables or []:
            env[v.name.lower()] = v  # normalize to lowercase
        return env

    def _build_env_for_single(self, mod: SingleModule) -> dict[str, Variable]:
        env: dict[str, Variable] = {}
        for v in mod.moduleparameters or []:
            env[v.name.lower()] = v
        for v in mod.localvariables or []:
            env[v.name.lower()] = v
        return env

    def _build_env_for_typedef(self, mt: ModuleTypeDef) -> dict[str, Variable]:
        env: dict[str, Variable] = {}
        for v in mt.moduleparameters or []:
            env[v.name.lower()] = v
        for v in mt.localvariables or []:
            env[v.name.lower()] = v
        return env

    def _is_external_typename(self, typename: str) -> bool:
        # Type is external to this file if not present in BasePicture.moduletype_defs [3]
        return typename.lower() not in self.typedef_index

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
        mt_key = mt.name.lower()
        if mt_key in self._analyzing_typedefs:
            return
        
        self._analyzing_typedefs.add(mt_key)
        
        try:
            env = self._build_env_for_typedef(mt)
            log.debug(f"DEBUG: _analyze_typedef for {mt.name}")
            log.debug(f"  env contains: {list(env.keys())}")
            
            # Scan typedef ModuleDef first (graph/interact), then ModuleCode
            self._walk_moduledef(mt.moduledef, env, path)
            self._walk_module_code(mt.modulecode, env, path)
            self._walk_submodules(mt.submodules or [], parent_env=env, parent_path=path)
            self._walk_typedef_groupconn(mt, env, path)

            # Track per-parameter read/write usage
            used_reads: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if v.read
            )
            used_writes: set[str] = set(
                v.name.lower() for v in (mt.moduleparameters or []) if v.written
            )

            # Preserve existing "used" union for any other consumers
            used_params: set[str] = used_reads | used_writes
            self.used_params_by_typedef[mt.name] = used_params

            # Store separate read/write sets
            self.param_reads_by_typedef[mt.name.lower()] = used_reads
            self.param_writes_by_typedef[mt.name.lower()] = used_writes

            for pm in mt.parametermappings or []:
                tgt_name = self._varname_base(pm.target)
                tgt_var = env.get(tgt_name) if tgt_name else None
                self._check_param_mapping(pm, tgt_var, env, path)
        finally:
            self._analyzing_typedefs.discard(mt_key)

    def _apply_alias_back_propagation(self) -> None:
        """
        For every alias (parent_var -> child_param_var), replicate read/write usage
        from the parent variable into the child parameter. This makes mapped
        parameters appear 'used' when their source variable is used elsewhere.
        """
        for parent_var, child_var in self._alias_links:
            # replicate reads
            for path, kind in parent_var.usage_locations or []:
                if kind == "read":
                    child_var.mark_read(path)
                elif kind == "write":
                    child_var.mark_written(path)

    def _walk_submodules(
        self,
        children: list[Union[SingleModule, FrameModule, ModuleTypeInstance]],
        parent_env: dict[str, Variable],
        parent_path: list[str],
    ) -> None:
        path_str = " -> ".join(parent_path)
        log.debug(f"=== _walk_submodules ENTER: {path_str}")
        log.debug(f"    Children count: {len(children)}")
        
        for idx, child in enumerate(children):
            child_name = child.header.name
            child_type = type(child).__name__
            log.debug(f"  [{idx+1}/{len(children)}] Processing {child_type}: {child_name}")
            
            self._walk_header_enable(
                child.header, parent_env, path=parent_path + [child.header.name]
            )
            self._walk_header_groupconn(
                child.header, parent_env, path=parent_path + [child.header.name]
            )

            if isinstance(child, SingleModule):
                log.debug(f"    → SingleModule: {child_name}")
                child_env = self._build_env_for_single(child)
                used_reads, used_writes = self._analyze_single_module(
                    child, parent_path + [child.header.name]
                )

                for pm in child.parametermappings or []:
                    src_var = self._lookup_env_var_from_varname_dict(
                        pm.source, parent_env
                    )
                    if src_var is None:
                        src_var = self._lookup_global_variable(
                            self._varname_base(pm.source)
                        )

                    tgt_name = self._varname_base(pm.target)
                    tgt_var = child_env.get(tgt_name) if tgt_name else None

                    if src_var is not None and tgt_var is not None:
                        self._alias_links.append((src_var, tgt_var))

                for pm in child.parametermappings or []:
                    self._propagate_mapping_to_parent(
                        pm,
                        child_used_reads=used_reads,
                        child_used_writes=used_writes,
                        parent_env=parent_env,
                        parent_path=parent_path,
                        external_typename=None,
                    )
                self._check_param_mappings_for_single(
                    child,
                    child_env=child_env,
                    parent_env=parent_env,
                    parent_path=parent_path + [child.header.name],
                )

            elif isinstance(child, FrameModule):
                log.debug(f"    → FrameModule: {child_name}")
                self._walk_moduledef(
                    child.moduledef, parent_env, parent_path + [child.header.name]
                )
                self._walk_module_code(
                    child.modulecode, parent_env, parent_path + [child.header.name]
                )
                self._walk_submodules(
                    child.submodules or [],
                    parent_env,
                    parent_path + [child.header.name],
                )

            elif isinstance(child, ModuleTypeInstance):
                log.debug(f"    → ModuleTypeInstance: {child_name} (type: {child.moduletype_name})")
                log.debug(f"        Currently analyzing: {self._analyzing_typedefs}")
                
                external = self._is_external_typename(child.moduletype_name)
                log.debug(f"        External: {external}")
                
                mt = self.typedef_index.get(child.moduletype_name.lower())
                log.debug(f"        Found typedef: {mt.name if mt else None}")
                
                if not external and mt:
                    mt_key = child.moduletype_name.lower()
                    log.debug(f"        Checking if needs analysis: {mt_key}")
                    log.debug(f"        In param_reads_by_typedef: {mt_key in self.param_reads_by_typedef}")
                    log.debug(f"        In _analyzing_typedefs: {mt_key in self._analyzing_typedefs}")
                    
                    # Build environment FIRST (doesn't recurse)
                    typedef_env = self._build_env_for_typedef(mt)
                    
                    # Only analyze if not already done AND not currently analyzing
                    if mt_key not in self.param_reads_by_typedef and mt_key not in self._analyzing_typedefs:
                        log.debug(f"        ★ WILL ANALYZE typedef: {mt_key}")
                        self._analyze_typedef(
                            mt, path=parent_path + [f"TypeDef:{mt.name}"]
                        )
                        log.debug(f"        ★ DONE ANALYZING typedef: {mt_key}")
                    else:
                        log.debug(f"        ✓ Skipping analysis (already done or in progress)")
                    
                    # Create alias links
                    log.debug(f"        Creating alias links for {len(child.parametermappings or [])} mappings")
                    for pm in child.parametermappings or []:
                        src_var = self._lookup_env_var_from_varname_dict(
                            pm.source, parent_env
                        )
                        if src_var is None:
                            src_var = self._lookup_global_variable(
                                self._varname_base(pm.source)
                            )
                        
                        tgt_name = self._varname_base(pm.target)
                        tgt_var = typedef_env.get(tgt_name) if tgt_name else None
                        
                        if src_var is not None and tgt_var is not None:
                            self._alias_links.append((src_var, tgt_var))
                            log.debug(f"          Created alias: {src_var.name} -> {tgt_var.name}")
                    
                    reads = self.param_reads_by_typedef.get(mt_key, set())
                    writes = self.param_writes_by_typedef.get(mt_key, set())
                else:
                    reads, writes = None, None

                for pm in child.parametermappings or []:
                    self._propagate_mapping_to_parent(
                        pm,
                        child_used_reads=reads,
                        child_used_writes=writes,
                        parent_env=parent_env,
                        parent_path=parent_path,
                        external_typename=(child.moduletype_name if external else None),
                    )
                
                if not external:
                    self._check_param_mappings_for_type_instance(
                        child,
                        parent_env=parent_env,
                        parent_path=parent_path + [child.header.name],
                    )
        
        log.debug(f"=== _walk_submodules EXIT: {path_str}")


    def _analyze_single_module(
        self, mod: SingleModule, path: list[str]
    ) -> tuple[set[str], set[str]]:
        env = self._build_env_for_single(mod)
        log.debug(f"DEBUG: _analyze_single_module for {mod.header.name}")
        log.debug(f"  env contains: {list(env.keys())}")
        # Scan ModuleDef (graph/interact) and ModuleCode
        self._walk_moduledef(mod.moduledef, env, path)
        self._walk_module_code(mod.modulecode, env, path)
        log.debug(f"  Recursing into submodules with env: {list(env.keys())}")
        self._walk_submodules(mod.submodules or [], parent_env=env, parent_path=path)
        used_reads: set[str] = set(
            v.name.lower() for v in (mod.moduleparameters or []) if v.read
        )
        used_writes: set[str] = set(
            v.name.lower() for v in (mod.moduleparameters or []) if v.written
        )
        return used_reads, used_writes

    # ---------------- ModuleDef walkers ----------------
    def _walk_header_enable(self, header, env, path):
        # ModuleHeader.enable_tail is a Tree(KEY_ENABLE_EXPRESSION) or Tree('InVar_') [5]
        tail = getattr(header, "enable_tail", None)
        if tail is not None:
            log.debug(f"DEBUG: Walking enable_tail at {' -> '.join(path)}")
            log.debug(f"  tail type: {type(tail).__name__}")
            log.debug(f"  tail value: {tail}")
            log.debug(f"  env keys: {list(env.keys())}")
            self._walk_tail(tail, env, path)

    def _walk_header_groupconn(self, header, env, path):
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
            var = env.get(base)

        if var is not None:
            var.mark_read(path)

    def _walk_typedef_groupconn(self, mt, env, path):
        var_dict = getattr(mt, "groupconn", None)
        if not isinstance(var_dict, dict):
            return
        base = self._varname_base(var_dict)
        if not base:
            return
        is_global = bool(getattr(mt, "groupconn_global", False))
        var = self._lookup_global_variable(base) if is_global else env.get(base)
        if var is not None:
            var.mark_read(path)

    def _walk_moduledef(
        self, mdef: ModuleDef | None, env: dict[str, Variable], path: list[str]
    ) -> None:
        if mdef is None:
            return
        # Graph objects (now carry tails in properties)
        for go in mdef.graph_objects or []:
            self._walk_graph_object(go, env, path)
        # Interact objects
        for io in mdef.interact_objects or []:
            self._walk_interact_object(io, env, path)
        props = getattr(mdef, "properties", {}) or {}
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, env, path)

    def _walk_graph_object(self, go, env, path):
        props = getattr(go, "properties", {}) or {}
        # NEW: text_vars list -> mark each as used
        for s in props.get("text_vars", []) or []:
            base = s.split(".", 1)[0] if isinstance(s, str) else None
            self._mark_var_by_basename(base, env, path)
        # Existing tails handling
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, env, path)

    def _walk_interact_object(self, io, env, path):
        props = getattr(io, "properties", {}) or {}
        for t in props.get(const.KEY_TAILS, []) or []:
            self._walk_tail(t, env, path)
        self._scan_for_varrefs(props.get(const.KEY_BODY), env, path)

        proc = props.get(const.KEY_PROCEDURE)
        if isinstance(proc, dict) and const.KEY_PROCEDURE_CALL in proc:
            call = proc[const.KEY_PROCEDURE_CALL]
            fn_name = call.get(const.KEY_NAME)
            args = call.get(const.KEY_ARGS) or []
            self._handle_function_call(fn_name, args, env, path)

    def _scan_for_varrefs(
        self, obj: Any, env: dict[str, Variable], path: list[str]
    ) -> None:
        # Generic recursive scan used for interact object bodies and nested dict/tree structures
        if obj is None:
            return
        if isinstance(obj, list):
            for it in obj:
                self._scan_for_varrefs(it, env, path)
            return
        if isinstance(obj, dict):
            # enable dict
            if const.TREE_TAG_ENABLE in obj and const.KEY_TAIL in obj:
                self._walk_tail(obj[const.KEY_TAIL], env, path)
            # explicit assignment dict from interact_assign_variable
            if const.KEY_ASSIGN in obj:
                tail = (obj[const.KEY_ASSIGN] or {}).get(const.KEY_TAIL)
                if tail is not None:
                    self._walk_tail(tail, env, path)
            # descend into any values
            for v in obj.values():
                self._scan_for_varrefs(v, env, path)
            return
        # Trees: enable_expression, InVar_, invar_tail
        if hasattr(obj, "data"):
            data = getattr(obj, "data")
            if data in (
                const.KEY_ENABLE_EXPRESSION,
                const.GRAMMAR_VALUE_INVAR_PREFIX,
                "invar_tail",
            ):
                self._walk_tail(obj, env, path)
                return
            # descend into children
            for ch in getattr(obj, "children", []):
                self._scan_for_varrefs(ch, env, path)

    # ---------------- Tail handlers ----------------

    def _walk_tail(self, tail, env, path):
        log.debug(f"DEBUG: _walk_tail called")
        log.debug(f"  tail: {tail}")
        log.debug(f"  type: {type(tail).__name__}")
        if tail is None:
            return

        # Expression tuple (from enable_expression)
        if isinstance(tail, tuple):
            self._walk_stmt_or_expr(tail, env, path)
            return

        # InVar string result: "Allow.ProgramDebug"
        if isinstance(tail, str):
            base = tail.split(".", 1)[0].lower()
            self._mark_var_by_basename(base, env, path)
            return

        # InVar variable_name dict result
        if isinstance(tail, dict) and const.KEY_VAR_NAME in tail:
            base = self._varname_base(tail)
            self._mark_var_by_basename(base, env, path)
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
        log.debug(f"DEBUG: _mark_var_by_basename called")
        log.debug(f"  base_name: {base_name}")
        log.debug(f"  looking in env: {list(env.keys())}")
        if not base_name:
            return
        var = env.get(base_name)
        if var is None:
            var = self._lookup_global_variable(base_name)
            log.debug(f"  var from global: {var}")
        if var is not None:
            var.mark_read(path)
            log.debug(f"  ✓ Marking {var.name} as READ at {' -> '.join(path)}")
        else:
            log.debug(f"  ✗ Variable '{base_name}' not found!")

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
        if src_base and src_base.lower() == "colours":
            log.debug(f"DEBUG: Looking for Colours in env: {list(parent_env.keys())}")
            log.debug(f"  path: {' -> '.join(parent_path)}")
            log.debug(f"  mapping: {src_base} => {target_name}")
            log.debug(f"  child_used_reads: {child_used_reads}")
            log.debug(f"  child_used_writes: {child_used_writes}")
            log.debug(
                f"  target in reads: {target_name in child_used_reads if child_used_reads else 'N/A'}"
            )
            log.debug(
                f"  target in writes: {target_name in child_used_writes if child_used_writes else 'N/A'}"
            )
            log.debug(f"  is_global: {pm.is_source_global}")
            log.debug(f"  external_typename: {external_typename}")

        # GLOBAL means "used" at the global scope (conservatively mark read)
        if pm.is_source_global:
            var = self._lookup_global_variable(src_base)
            if var is not None:
                var.mark_read(parent_path)
            return

        # Resolve the actual source variable in parent scope (or fallback to root/global)
        src_var = self._lookup_env_var_from_varname_dict(pm.source, parent_env)
        if src_var is None:
            src_var = self._lookup_global_variable(src_base)

        # External types: conservatively treat mapping as read+written
        if external_typename is not None:
            if src_var is not None:
                src_var.mark_read(parent_path)
                src_var.mark_written(parent_path)
            return

        # Internal types: propagate directionally based on child's param usage
        if src_var is not None and target_name is not None:
            if child_used_reads is not None and target_name in child_used_reads:
                src_var.mark_read(parent_path)
            if child_used_writes is not None and target_name in child_used_writes:
                src_var.mark_written(parent_path)

    # ------------ ModuleCode walkers ------------

    def _walk_module_code(
        self,
        mc: ModuleCode | None,
        env: dict[str, Variable],
        path: list[str],
    ) -> None:
        if mc is None:
            return
        # Sequences
        for seq in mc.sequences or []:
            self._walk_sequence(seq, env, path)
        # Equations
        for eq in mc.equations or []:
            for stmt in eq.code or []:
                self._walk_stmt_or_expr(stmt, env, path)

    def _walk_sequence(
        self, seq: Sequence, env: dict[str, Variable], path: list[str]
    ) -> None:
        for node in seq.code or []:
            if isinstance(node, SFCStep):
                # Enter/Active/Exit blocks contain statements
                for stmt in node.code.enter or []:
                    self._walk_stmt_or_expr(stmt, env, path)
                for stmt in node.code.active or []:
                    self._walk_stmt_or_expr(stmt, env, path)
                for stmt in node.code.exit or []:
                    self._walk_stmt_or_expr(stmt, env, path)

            elif isinstance(node, SFCTransition):
                self._walk_stmt_or_expr(node.condition, env, path)

            elif isinstance(node, SFCAlternative):
                for branch in node.branches:
                    # branch: list of SFC nodes
                    self._walk_seq_nodes(branch, env, path)

            elif isinstance(node, SFCParallel):
                for branch in node.branches:
                    self._walk_seq_nodes(branch, env, path)

            elif isinstance(node, SFCSubsequence):
                self._walk_seq_nodes(node.body, env, path)

            elif isinstance(node, SFCTransitionSub):
                self._walk_seq_nodes(node.body, env, path)

            elif isinstance(node, (SFCFork, SFCBreak)):
                # no variable usage in headers
                continue

    def _walk_seq_nodes(
        self, nodes: list[Any], env: dict[str, Variable], path: list[str]
    ) -> None:
        for nd in nodes:
            if isinstance(nd, SFCStep):
                for stmt in nd.code.enter or []:
                    self._walk_stmt_or_expr(stmt, env, path)
                for stmt in nd.code.active or []:
                    self._walk_stmt_or_expr(stmt, env, path)
                for stmt in nd.code.exit or []:
                    self._walk_stmt_or_expr(stmt, env, path)
            elif isinstance(nd, SFCTransition):
                self._walk_stmt_or_expr(nd.condition, env, path)
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
        self, obj: Any, env: dict[str, Variable], path: list[str]
    ) -> None:
        # Tree wrapping for statements is present in transformer [5]; unwrap
        if hasattr(obj, "data") and getattr(obj, "data") == const.KEY_STATEMENT:
            for ch in getattr(obj, "children", []):
                self._walk_stmt_or_expr(ch, env, path)
            return

        # IF Statement: (IF, branches, else_block) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_IF:
            _, branches, else_block = obj
            for cond, stmts in branches or []:
                self._walk_stmt_or_expr(cond, env, path)
                for st in stmts or []:
                    self._walk_stmt_or_expr(st, env, path)
            for st in else_block or []:
                self._walk_stmt_or_expr(st, env, path)
            return

        # Ternary: (Ternary, [(cond, then_expr), ...], else_expr) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_TERNARY, "Ternary"):
            _, branches, else_expr = obj
            for cond, then_expr in branches or []:
                self._walk_stmt_or_expr(cond, env, path)
                self._walk_stmt_or_expr(then_expr, env, path)
            if else_expr is not None:
                self._walk_stmt_or_expr(else_expr, env, path)
            return

        # Function call: (FunctionCall, name, [args...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_FUNCTION_CALL:
            _, fn_name, args = (
                obj  # transformer emits (FunctionCall, name, [args...]) [3]
            )
            self._handle_function_call(fn_name, args or [], env, path)
            return

        # Boolean OR/AND [5]
        if (
            isinstance(obj, tuple)
            and obj
            and obj[0] in (const.GRAMMAR_VALUE_OR, const.GRAMMAR_VALUE_AND)
        ):
            for sub in obj[1] or []:
                self._walk_stmt_or_expr(sub, env, path)
            return

        # NOT [5]
        if isinstance(obj, tuple) and obj and obj[0] == const.GRAMMAR_VALUE_NOT:
            self._walk_stmt_or_expr(obj[1], env, path)
            return

        # Compare: (compare, left, [(sym, right), ...]) [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_COMPARE, "compare"):
            _, left, pairs = obj
            self._walk_stmt_or_expr(left, env, path)
            for _sym, rhs in pairs or []:
                self._walk_stmt_or_expr(rhs, env, path)
            return

        # Add/Mul [5]
        if isinstance(obj, tuple) and obj and obj[0] in (const.KEY_ADD, const.KEY_MUL):
            _, left, parts = obj
            self._walk_stmt_or_expr(left, env, path)
            for _opval, r in parts or []:
                self._walk_stmt_or_expr(r, env, path)
            return

        # Unary [+/- term] [5]
        if (
            isinstance(obj, tuple)
            and obj
            and obj[0] in (const.KEY_PLUS, const.KEY_MINUS)
        ):
            _, inner = obj
            self._walk_stmt_or_expr(inner, env, path)
            return

        # Interact/enable/invar tails may embed expressions/variable refs [5]
        if isinstance(obj, dict) and const.KEY_ENABLE_EXPRESSION in obj:
            tail = obj[const.KEY_ENABLE_EXPRESSION]
            self._walk_stmt_or_expr(tail, env, path)
            return

        # Tree wrappers for enable_expression / invar tails [5]
        if hasattr(obj, "data"):
            if getattr(obj, "data") == const.KEY_ENABLE_EXPRESSION:
                for ch in getattr(obj, "children", []):
                    self._walk_stmt_or_expr(ch, env, path)
                return
            if getattr(obj, "data") == const.GRAMMAR_VALUE_INVAR_PREFIX:
                for ch in getattr(obj, "children", []):
                    self._walk_stmt_or_expr(ch, env, path)
                return

        # Lists of nested statements
        if isinstance(obj, list):
            for it in obj:
                self._walk_stmt_or_expr(it, env, path)

        if isinstance(obj, dict) and const.KEY_VAR_NAME in obj:
            base, field_path = self._extract_field_path(obj)
            var = env.get(base) if base else None

            if var is not None:
                if field_path:
                    # Track field-level read
                    var.mark_field_read(field_path, path)
                else:
                    # Whole variable read
                    var.mark_read(path)
            return

        if isinstance(obj, tuple) and obj and obj[0] == const.KEY_ASSIGN:
            _, target, expr = obj

            base, field_path = self._extract_field_path(target)
            tgt_var = env.get(base) if base else None

            if tgt_var is not None:
                if field_path:
                    tgt_var.mark_field_written(field_path, path)
                else:
                    tgt_var.mark_written(path)

            self._walk_stmt_or_expr(expr, env, path)
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
                return env.get(base)
        return None

    def _varname_base(self, var_dict_or_str: Any) -> str | None:
        if isinstance(var_dict_or_str, dict) and const.KEY_VAR_NAME in var_dict_or_str:
            full = var_dict_or_str[const.KEY_VAR_NAME]
        elif isinstance(var_dict_or_str, str):
            full = var_dict_or_str
        else:
            return None
        base = full.split(".", 1)[0] if full else None
        return base.lower() if base else None  # normalize to lowercase

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
