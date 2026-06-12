"""Reporting utilities for variable usage analysis."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)

from ..core._semantic_helpers import format_moduletype_label
from ..models.usage import VariableUsage
from ..resolution.common import (
    find_all_aliases,
    resolve_module_by_strict_path,
    resolve_moduletype_def_strict,
)
from ..resolution.paths import path_startswith_casefold
from .shared._walk_utils import iter_nested_modules
from .variables import VariablesAnalyzer

log = logging.getLogger("SattLint")

_ANY_VAR_INDEX_ATTR = "_any_var_index"
_ALIAS_LINKS_ATTR = "_alias_links"
_GET_USAGE_ATTR = "_get_usage"


def _analyzer_any_var_index(analyzer: VariablesAnalyzer) -> dict[str, list[Variable]]:
    return cast(dict[str, list[Variable]], getattr(analyzer, _ANY_VAR_INDEX_ATTR))


def _analyzer_alias_links(analyzer: VariablesAnalyzer) -> list[tuple[Variable, Variable, str]]:
    return cast(list[tuple[Variable, Variable, str]], getattr(analyzer, _ALIAS_LINKS_ATTR))


def _analyzer_usage(analyzer: VariablesAnalyzer, variable: Variable) -> VariableUsage:
    usage_fn = cast(Callable[[Variable], VariableUsage], getattr(analyzer, _GET_USAGE_ATTR))
    return usage_fn(variable)


def _find_module_instances(
    base_picture: BasePicture,
    moduletype_name: str,
) -> list[tuple[ModuleTypeInstance, list[str]]]:
    target_name = moduletype_name.casefold()
    matches: list[tuple[ModuleTypeInstance, list[str]]] = []

    def _resolve_instance_submodules(
        instance: ModuleTypeInstance,
    ) -> list[SingleModule | FrameModule | ModuleTypeInstance] | None:
        return resolve_moduletype_def_strict(base_picture, instance.moduletype_name).submodules

    for module, module_path in iter_nested_modules(
        base_picture.submodules,
        parent_path=[base_picture.header.name],
        resolve_instance_submodules=_resolve_instance_submodules,
    ):
        if isinstance(module, ModuleTypeInstance) and module.moduletype_name.casefold() == target_name:
            matches.append((module, module_path))

    return matches


find_module_instances = _find_module_instances


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

    matches = _analyzer_any_var_index(analyzer).get(var_name.lower(), [])
    if not matches:
        return f"No variables named {var_name!r} found."

    lines: list[str] = []
    lines.append(f"Usage report for variable name {var_name!r} ({len(matches)} declaration(s)):")

    for idx, v in enumerate(matches, start=1):
        usage = _analyzer_usage(analyzer, v)
        dt = v.datatype_text
        lines.append(f"[{idx}] {dt} | R:{bool(usage.read)} W:{bool(usage.written)}")

        # List field-level reads (deduplicated).
        if usage.field_reads:
            lines.append("  Field reads:")
            for field_path, locations in sorted(usage.field_reads.items()):
                # Count unique access paths.
                unique_paths: dict[str, int] = {}
                for loc in locations:
                    where = " -> ".join(loc)
                    unique_paths[where] = unique_paths.get(where, 0) + 1

                lines.append(f"    • {var_name}.{field_path}")
                for path_label, count in sorted(unique_paths.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      {path_label}{count_str}")

        # List field-level writes (deduplicated).
        if usage.field_writes:
            lines.append("  Field writes:")
            for field_path, locations in sorted(usage.field_writes.items()):
                unique_write_paths: dict[str, int] = {}
                for loc in locations:
                    where = " -> ".join(loc)
                    unique_write_paths[where] = unique_write_paths.get(where, 0) + 1

                lines.append(f"    • {var_name}.{field_path}")
                for path_label, count in sorted(unique_write_paths.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      {path_label}{count_str}")

        # List whole-variable accesses (deduplicated by path/kind).
        whole_var_locs = [(path, kind) for path, kind in usage.usage_locations if kind in ("read", "write")]
        if whole_var_locs:
            lines.append("  Whole variable:")
            # Aggregate by path.
            path_kinds: dict[str, dict[str, int]] = {}
            for location_path, kind in whole_var_locs:
                where = " -> ".join(location_path)
                if where not in path_kinds:
                    path_kinds[where] = {"read": 0, "write": 0}
                path_kinds[where][kind] += 1

            for path_label, kinds in sorted(path_kinds.items()):
                r_count = kinds["read"]
                w_count = kinds["write"]
                access: list[str] = []
                if r_count > 0:
                    access.append(f"R:{r_count}")
                if w_count > 0:
                    access.append(f"W:{w_count}")
                lines.append(f"    {' '.join(access)} | {path_label}")

    return "\n".join(lines)


def report_datatype_usage(
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

    matches = _analyzer_any_var_index(analyzer).get(var_name.lower(), [])
    if not matches:
        return f"Variable {var_name!r} not found."

    lines: list[str] = [f"Field usage analysis for variable {var_name!r}:"]

    for idx, var in enumerate(matches, 1):
        usage = _analyzer_usage(analyzer, var)
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

                lines.append(f"      • {field}: {access} (R:{read_count}, W:{write_count})")
        else:
            lines.append("    No field-level accesses tracked")

    return "\n".join(lines)


def report_module_localvar_fields(  # noqa: PLR0915
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
        log.debug("Analysis complete. Alias links=%d", len(_analyzer_alias_links(analyzer)))

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
    aliased_vars_with_paths = find_all_aliases(local_var, _analyzer_alias_links(analyzer), debug=debug)
    # Include the local variable itself (direct field/whole-variable accesses).
    aliased_vars_with_paths.insert(0, (local_var, ""))

    # Build the report header.
    header = f"Field usage analysis for local variable {var_name!r}"
    header += f" in module path {resolved.display_path_str!r}"
    lines: list[str] = [
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
    all_field_reads: dict[str, list[list[str]]] = {}
    all_field_writes: dict[str, list[list[str]]] = {}
    whole_var_reads: list[list[str]] = []
    whole_var_writes: list[list[str]] = []

    if debug:
        log.debug("Aggregating usages from connected aliases")
    for var, field_prefix in aliased_vars_with_paths:
        usage = _analyzer_usage(analyzer, var)
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
        for loc, kind in usage.usage_locations or []:
            if kind == "read":
                whole_var_reads.append(loc)
            elif kind == "write":
                whole_var_writes.append(loc)

    # Filter to accesses within the selected module tree only.
    def is_within_module(location: list[str]) -> bool:
        """Check if location is within the selected module path (or its submodules)."""
        return path_startswith_casefold(location, module_path_list)

    # Field-level accesses
    internal_field_reads: dict[str, list[list[str]]] = {}
    internal_field_writes: dict[str, list[list[str]]] = {}

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
            unique_read_locs: dict[str, int] = {}
            for loc in reads:
                loc_str = " -> ".join(loc)
                unique_read_locs[loc_str] = unique_read_locs.get(loc_str, 0) + 1

            unique_write_locs: dict[str, int] = {}
            for loc in writes:
                loc_str = " -> ".join(loc)
                unique_write_locs[loc_str] = unique_write_locs.get(loc_str, 0) + 1

            access_type: list[str] = []
            if reads:
                access_type.append("READ")
            if writes:
                access_type.append("WRITE")

            lines.append(f"\n  • {var_name}.{field} [{'/'.join(access_type)}]")

            if unique_read_locs:
                lines.append(
                    f"    Reads ({sum(unique_read_locs.values())} total, {len(unique_read_locs)} unique location(s)):"
                )
                for loc_str, count in sorted(unique_read_locs.items()):
                    count_str = f" ({count}x)" if count > 1 else ""
                    lines.append(f"      - {loc_str}{count_str}")

            if unique_write_locs:
                lines.append(
                    f"    Writes ({sum(unique_write_locs.values())} total, {len(unique_write_locs)} unique location(s)):"
                )
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
            unique_reads: dict[str, int] = {}
            for loc in internal_whole_reads:
                loc_str = " -> ".join(loc)
                unique_reads[loc_str] = unique_reads.get(loc_str, 0) + 1

            lines.append(f"\n  Reads ({sum(unique_reads.values())} total, {len(unique_reads)} unique location(s)):")
            for loc_str, count in sorted(unique_reads.items()):
                count_str = f" ({count}x)" if count > 1 else ""
                lines.append(f"    - {loc_str}{count_str}")

        if internal_whole_writes:
            unique_writes: dict[str, int] = {}
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
