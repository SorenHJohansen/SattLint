"""Reporting utilities for variable usage analysis."""
from __future__ import annotations
import logging
from typing import Any, cast

from ..models.ast_model import (
    BasePicture,
    SingleModule,
    FrameModule,
    ModuleTypeInstance,
    ModuleTypeDef,
    Variable,
)
from ..resolution.common import (
    resolve_module_by_strict_path,
    resolve_moduletype_def_strict,
    format_moduletype_label,
    path_startswith_casefold,
    find_all_aliases,
)
from .variables import VariablesAnalyzer

log = logging.getLogger("SattLint")

def debug_variable_usage(
    base_picture: BasePicture,
    var_name: str,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
) -> str:
    """
    Run the analyzer and return a human-readable report for all variables
    with the given name across the AST, listing read/write usage with full field paths.
    """
    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
        unavailable_libraries=unavailable_libraries,
    )
    _ = analyzer.run()

    matches = analyzer._any_var_index.get(var_name.lower(), [])
    if not matches:
        return f"No variables named {var_name!r} found."

    lines: list[str] = []
    lines.append(
        f"Usage report for variable name {var_name!r} ({len(matches)} declaration(s)):"
    )

    for idx, v in enumerate(matches, start=1):
        usage = analyzer._get_usage(v)
        dt = v.datatype_text
        lines.append(
            f"[{idx}] {dt} | R:{bool(usage.read)} W:{bool(usage.written)}"
        )

        # List field-level reads (deduplicated).
        if usage.field_reads:
            lines.append("  Field reads:")
            for field_path, locations in sorted(usage.field_reads.items()):
                # Count unique access paths.
                unique_paths = {}
                for loc in locations:
                    where = " -> ".join(loc)
                    unique_paths[where] = unique_paths.get(where, 0) + 1

                lines.append(f"    • {var_name}.{field_path}")
                for path, count in sorted(unique_paths.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      {path}{count_str}")

        # List field-level writes (deduplicated).
        if usage.field_writes:
            lines.append("  Field writes:")
            for field_path, locations in sorted(usage.field_writes.items()):
                unique_paths = {}
                for loc in locations:
                    where = " -> ".join(loc)
                    unique_paths[where] = unique_paths.get(where, 0) + 1

                lines.append(f"    • {var_name}.{field_path}")
                for path, count in sorted(unique_paths.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      {path}{count_str}")

        # List whole-variable accesses (deduplicated by path/kind).
        whole_var_locs = [
            (path, kind) for path, kind in usage.usage_locations
            if kind in ("read", "write")
        ]
        if whole_var_locs:
            lines.append("  Whole variable:")
            # Aggregate by path.
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


def analyze_datatype_usage(
    base_picture: BasePicture,
    var_name: str,
    debug: bool = False,
    unavailable_libraries: set[str] | None = None,
) -> str:
    """
    Analyze field-level usage for a specific variable across modules.
    """
    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=False,
        unavailable_libraries=unavailable_libraries,
    )
    _ = analyzer.run()

    matches = analyzer._any_var_index.get(var_name.lower(), [])
    if not matches:
        return f"Variable {var_name!r} not found."

    lines = [f"Field usage analysis for variable {var_name!r}:"]

    for idx, var in enumerate(matches, 1):
        usage = analyzer._get_usage(var)
        lines.append(f"\n[{idx}] Declaration: {var.datatype_text}")
        lines.append(
            f"    Location: {' -> '.join(usage.usage_locations[0][0]) if usage.usage_locations else 'Unknown'}"
        )

        if usage.field_reads or usage.field_writes:
            # Combine read/write field keys.
            all_fields = set(usage.field_reads.keys()) | set(usage.field_writes.keys())

            lines.append(f"    Fields accessed: {len(all_fields)}")
            for field in sorted(all_fields):
                read_count = len(usage.field_reads.get(field, []))
                write_count = len(usage.field_writes.get(field, []))

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
    unavailable_libraries: set[str] | None = None,
) -> str:
    """
    Analyze field-level usage of a local variable within a module and its submodules.
    ONLY follows actual parameter mapping aliases, not all variables with the same name.
    """
    # Resolve the target module by BasePicture-relative dotted path to avoid
    # ambiguity between module instances and type definitions.
    resolved = resolve_module_by_strict_path(base_picture, module_path)
    module_def = resolved.node

    # Run the analyzer without alias back-propagation to build alias links only.
    # IMPORTANT: limit traversal to the selected subtree (plus ancestors) so
    # unrelated modules are not analyzed.
    analyzer = VariablesAnalyzer(
        base_picture,
        debug=debug,
        fail_loudly=fail_loudly,
        unavailable_libraries=unavailable_libraries,
    )

    if debug:
        log.debug("Starting analysis without alias back-propagation")
    analyzer.run(
        apply_alias_back_propagation=False,
        limit_to_module_path=resolved.path,
    )

    if debug:
        log.debug("Analysis complete. Alias links=%d", len(analyzer._alias_links))
        if getattr(analyzer, "_mapping_warnings", None):
            log.debug(
                "Parameter-mapping warnings=%d (skipped alias creation)",
                len(analyzer._mapping_warnings),
            )

    # Find the specific local variable instance:
    # - SingleModule: variable is declared on the module node.
    # - ModuleTypeInstance: variable is declared on the referenced ModuleTypeDef.
    var_name_key = var_name.casefold()
    module_type_info: str | None = None

    if isinstance(module_def, SingleModule):
        local_var = next(
            (v for v in (module_def.localvariables or []) if v.name.casefold() == var_name_key),
            None,
        )
    elif isinstance(module_def, ModuleTypeInstance):
        mt = resolve_moduletype_def_strict(base_picture, module_def.moduletype_name)
        module_type_info = format_moduletype_label(mt)
        local_var = next(
            (v for v in (mt.localvariables or []) if v.name.casefold() == var_name_key),
            None,
        )
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
        log.debug("Target variable id=%d", id(local_var))

    # Find only the Variable objects connected through alias links with field paths.
    aliased_vars_with_paths = find_all_aliases(local_var, analyzer._alias_links, debug=debug)
    # Include the local variable itself (direct field/whole-variable accesses).
    aliased_vars_with_paths.insert(0, (local_var, ""))

    # Build the report header.
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
        "",
        "=" * 80,
        "",
    ]

    # Aggregate usage only from connected aliases.
    all_field_reads = {}
    all_field_writes = {}
    whole_var_reads = []
    whole_var_writes = []

    if debug:
        log.debug("Aggregating usages from connected aliases")
    for var, field_prefix in aliased_vars_with_paths:
        usage = analyzer._get_usage(var)
        # field_prefix may be empty for the root variable itself.

        # Merge field reads and reconstruct the full field path (case-insensitive).
        for field_path, locations in (usage.field_reads or {}).items():
            # Combine the mapping prefix with the accessed field path.
            if field_prefix and field_path:
                full_field_path = f"{field_prefix}.{field_path}"
            elif field_prefix:
                full_field_path = field_prefix
            else:
                full_field_path = field_path

            # Normalize to lowercase for case-insensitive comparison.
            full_field_path_lower = full_field_path.lower()
            all_field_reads.setdefault(full_field_path_lower, []).extend(locations)

        # Merge field writes and reconstruct the full field path (case-insensitive).
        for field_path, locations in (usage.field_writes or {}).items():
            # Combine the mapping prefix with the accessed field path.
            if field_prefix and field_path:
                full_field_path = f"{field_prefix}.{field_path}"
            elif field_prefix:
                full_field_path = field_prefix
            else:
                full_field_path = field_path

            # Normalize to lowercase for case-insensitive comparison.
            full_field_path_lower = full_field_path.lower()
            all_field_writes.setdefault(full_field_path_lower, []).extend(locations)

        # Merge whole-variable accesses.
        for loc, kind in (usage.usage_locations or []):
            if kind == "read":
                whole_var_reads.append(loc)
            elif kind == "write":
                whole_var_writes.append(loc)

    # Filter to accesses within the selected module tree only.
    def is_within_module(location: list[str]) -> bool:
        """Check if location is within the selected module path (or its submodules)."""
        return path_startswith_casefold(location, module_path_list)

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

    # Whole-variable accesses
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
