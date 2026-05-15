"""Module comparison, version drift analysis, and debug helpers."""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)

from ._modules_diffing import (
    CodeDiff,
    SubmoduleDiff,
    VariableDiff,
    compare_code,
    compare_submodules,
    compare_variable_lists,
)
from ._modules_fingerprints import (
    ModuleFingerprint,
    VariantFingerprintKey,
    create_fingerprint,
    empty_fingerprints,
    empty_instance_fingerprints,
    fingerprint_variant_key,
    fingerprints_match,
    normalize_name,
)
from ._modules_reporting import build_upgrade_notes, compact_diff, material_difference_labels
from .framework import Issue, empty_issues, format_report_header
from .variable_utils import same_origin_file_stem

log = logging.getLogger("SattLint")

_DEFAULT_DEBUG_MAX_DEPTH = 10

type SubmoduleNode = SingleModule | FrameModule | ModuleTypeInstance


def debug_module_structure(base_picture: BasePicture, max_depth: int = _DEFAULT_DEBUG_MAX_DEPTH) -> None:
    """Detailed debugging: show EVERYTHING about the structure."""
    log.debug("=== DEBUGGING MODULE STRUCTURE ===")
    log.debug("BasePicture type: %s", type(base_picture))
    log.debug("BasePicture name: %r", base_picture.header.name)
    log.debug("BasePicture has %d submodules", len(base_picture.submodules))
    log.debug("BasePicture has %d moduletype_defs", len(base_picture.moduletype_defs))

    # Show moduletype_defs
    log.debug("--- ModuleTypeDefs ---")
    for mtd in base_picture.moduletype_defs:
        log.debug("  ModuleTypeDef: %r", mtd.name)
        log.debug("    - has %d submodules", len(mtd.submodules))
        for i, sub in enumerate(mtd.submodules):
            log.debug(
                "    - submodule[%d]: %s - %r",
                i,
                type(sub).__name__,
                sub.header.name,
            )

    def _walk(node: Any, depth: int = 0, parent_name: str = "") -> None:
        if depth > max_depth:
            log.debug("%s[MAX DEPTH REACHED]", "  " * depth)
            return

        indent = "  " * depth
        node_type = type(node).__name__

        if isinstance(node, SingleModule):
            name = node.header.name
            log.debug(
                "%sSingleModule: name=%r, datecode=%s, parent=%r",
                indent,
                name,
                node.datecode,
                parent_name,
            )
            log.debug("%s  - has %d submodules", indent, len(node.submodules))
            for i, sub in enumerate(node.submodules):
                log.debug(
                    "%s  - submodule[%d] type: %s",
                    indent,
                    i,
                    type(sub).__name__,
                )
                _walk(sub, depth + 1, name)

        elif isinstance(node, FrameModule):
            name = node.header.name
            log.debug(
                "%sFrameModule: name=%r, datecode=%s, parent=%r",
                indent,
                name,
                node.datecode,
                parent_name,
            )
            log.debug("%s  - has %d submodules", indent, len(node.submodules))
            for i, sub in enumerate(node.submodules):
                log.debug(
                    "%s  - submodule[%d] type: %s",
                    indent,
                    i,
                    type(sub).__name__,
                )
                _walk(sub, depth + 1, name)

        elif isinstance(node, ModuleTypeInstance):
            name = node.header.name
            log.debug(
                "%sModuleTypeInstance: name=%r, type=%r, parent=%r",
                indent,
                name,
                node.moduletype_name,
                parent_name,
            )

        elif isinstance(node, BasePicture):
            log.debug("%sBasePicture: name=%r", indent, node.name)
            log.debug("%s  - has %d submodules", indent, len(node.submodules))
            for i, sub in enumerate(node.submodules):
                log.debug(
                    "%s  - submodule[%d] type: %s",
                    indent,
                    i,
                    type(sub).__name__,
                )
                _walk(sub, depth + 1, node.name)
        else:
            log.debug("%sUnknown type: %s", indent, node_type)

    log.debug("--- Submodules Tree ---")
    _walk(base_picture)
    log.debug("=== END DEBUGGING ===")


@dataclass
class ComparisonResult:
    """Results of comparing multiple SingleModules with the same name."""

    module_name: str
    total_found: int
    unique_variants: int
    fingerprints: list[ModuleFingerprint] = field(default_factory=empty_fingerprints)
    all_instances: list[tuple[list[str], ModuleFingerprint]] = field(default_factory=empty_instance_fingerprints)

    # Detailed diffs
    parameter_diff: VariableDiff | None = None
    localvar_diff: VariableDiff | None = None
    submodule_diff: SubmoduleDiff | None = None
    code_diff: CodeDiff | None = None

    def summary(self) -> str:
        status = "ok" if self.unique_variants <= 1 else "issues"
        lines = format_report_header("Module comparison", self.module_name, status=status)
        lines.extend(
            [
                f"Total Instances Found: {self.total_found}",
                f"Unique Variants: {self.unique_variants}",
                "",
            ]
        )

        if self.total_found == 0:
            lines.append("⚠ No modules found with this name")
            return "\n".join(lines)

        if self.unique_variants == 1:
            lines.append("✓ All instances are structurally identical (datecodes may differ)")
            lines.append("")
            lines.append("Instance locations:")
            for path, fp in self.all_instances:
                lines.append(f"  DateCode: {fp.datecode} - {' → '.join(path)}")
        else:
            lines.append(f"⚠ Found {self.unique_variants} different structural variants")
            lines.append("")

            # Group instances by variant FINGERPRINT (not just by id)
            variant_map: dict[int, list[tuple[list[str], ModuleFingerprint]]] = {}
            for path, fp in self.all_instances:
                # Find which unique fingerprint this instance matches
                for i, unique_fp in enumerate(self.fingerprints, 1):
                    # Check if they have the same structural hash (excluding datecode)
                    if (
                        fp.num_moduleparameters == unique_fp.num_moduleparameters
                        and fp.num_localvariables == unique_fp.num_localvariables
                        and fp.num_submodules == unique_fp.num_submodules
                        and fp.num_sequences == unique_fp.num_sequences
                        and fp.num_equations == unique_fp.num_equations
                        and fp.moduleparameters_hash == unique_fp.moduleparameters_hash
                        and fp.localvariables_hash == unique_fp.localvariables_hash
                        and fp.submodules_hash == unique_fp.submodules_hash
                        and fp.parameter_mappings_hash == unique_fp.parameter_mappings_hash
                    ):
                        if i not in variant_map:
                            variant_map[i] = []
                        variant_map[i].append((path, fp))
                        break

            for i, unique_fp in enumerate(self.fingerprints, 1):
                instances = variant_map.get(i, [])

                lines.append(f"=== Variant {i} ({len(instances)} instance(s)) ===")
                lines.append(f"Parameters: {unique_fp.num_moduleparameters}")
                lines.append(f"Local Vars: {unique_fp.num_localvariables}")
                lines.append(f"Submodules: {unique_fp.num_submodules}")
                lines.append(f"Sequences: {unique_fp.num_sequences}")
                lines.append(f"Equations: {unique_fp.num_equations}")
                lines.append("Locations:")
                for path, fp in instances:
                    lines.append(f"  DateCode: {fp.datecode} - {' → '.join(path)}")
                lines.append("")

            # Show detailed differences
            if self.parameter_diff:
                lines.append("=== Module Parameters Differences ===")
                lines.append(f"Common ({len(self.parameter_diff.common)}): {sorted(self.parameter_diff.common)}")
                for var_id, names in sorted(self.parameter_diff.only_in_variant.items()):
                    if names:
                        lines.append(f"Only in Variant {var_id} ({len(names)}): {sorted(names)}")
                lines.append("")

            if self.localvar_diff:
                lines.append("=== Local Variables Differences ===")
                lines.append(f"Common ({len(self.localvar_diff.common)}): {sorted(self.localvar_diff.common)}")
                for var_id, names in sorted(self.localvar_diff.only_in_variant.items()):
                    if names:
                        lines.append(f"Only in Variant {var_id} ({len(names)}): {sorted(names)}")
                lines.append("")

            if self.submodule_diff:
                lines.append("=== Submodules Differences (Recursive Tree) ===")

                # Group common by depth for better readability
                common_by_depth: defaultdict[int, list[tuple[str, str]]] = defaultdict(list)
                for depth, name, typ in self.submodule_diff.common:
                    common_by_depth[depth].append((name, typ))

                lines.append(f"Common across all variants ({len(self.submodule_diff.common)} total):")
                for depth in sorted(common_by_depth.keys()):
                    indent = "  " + ("  " * depth)
                    items = common_by_depth[depth]
                    for name, typ in sorted(items):
                        lines.append(f"{indent}Depth {depth}: {name} ({typ})")

                # Show unique submodules per variant
                for var_id, unique_subs in sorted(self.submodule_diff.only_in_variant.items()):
                    if unique_subs:
                        lines.append(f"Only in Variant {var_id} ({len(unique_subs)} nodes):")
                        # Group by depth
                        by_depth: defaultdict[int, list[tuple[str, str]]] = defaultdict(list)
                        for depth, name, typ in unique_subs:
                            by_depth[depth].append((name, typ))

                        for depth in sorted(by_depth.keys()):
                            indent = "  " + ("  " * depth)
                            items = by_depth[depth]
                            for name, typ in sorted(items):
                                lines.append(f"{indent}Depth {depth}: {name} ({typ})")
                lines.append("")

            if self.code_diff:
                lines.append("=== Module Code Differences ===")
                if self.code_diff.sequences_common or any(self.code_diff.sequences_only_in_variant.values()):
                    lines.append(
                        f"Sequences Common ({len(self.code_diff.sequences_common)}): {sorted(self.code_diff.sequences_common)}"
                    )
                    for var_id, names in sorted(self.code_diff.sequences_only_in_variant.items()):
                        if names:
                            lines.append(f"Sequences Only in Variant {var_id} ({len(names)}): {sorted(names)}")
                if self.code_diff.equations_common or any(self.code_diff.equations_only_in_variant.values()):
                    lines.append(
                        f"Equations Common ({len(self.code_diff.equations_common)}): {sorted(self.code_diff.equations_common)}"
                    )
                    for var_id, names in sorted(self.code_diff.equations_only_in_variant.items()):
                        if names:
                            lines.append(f"Equations Only in Variant {var_id} ({len(names)}): {sorted(names)}")
                lines.append("")

        return "\n".join(lines)


@dataclass
class VersionDriftReport:
    """Analyzer-facing report for module version drift findings."""

    name: str
    issues: list[Issue] = field(default_factory=empty_issues)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Version drift", self.name, status="ok")
            lines.append("No module version drift found.")
            return "\n".join(lines)

        lines = format_report_header("Version drift", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        kind_counts = Counter(issue.kind for issue in self.issues)
        lines.append("Kinds:")
        lines.append(f"  - Module version drift: {kind_counts.get('module.version_drift', 0)}")
        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


def _walk_modules(
    node: Any,
    target_name: str,
    current_path: list[str],
    results: list[tuple[list[str], SingleModule]],
    debug: bool = False,
) -> None:
    """Recursively find all SingleModule instances with the target name (case-insensitive)."""
    target_name_lower = target_name.lower()

    if debug:
        log.debug(
            "_walk_modules: checking node type=%s, path=%s",
            type(node).__name__,
            current_path,
        )

    if isinstance(node, SingleModule):
        node_name = node.header.name
        node_name_lower = node_name.lower()

        if debug:
            log.debug(
                "  SingleModule found: %r, comparing with target=%r, match=%s",
                node_name,
                target_name,
                node_name_lower == target_name_lower,
            )

        path_with_current = [*current_path, node_name]

        if node_name_lower == target_name_lower:
            if debug:
                log.debug("  MATCH: adding to results")
            results.append((path_with_current, node))

        if debug:
            log.debug(
                "  Checking %d submodules of %r",
                len(node.submodules),
                node_name,
            )
        for i, sub in enumerate(node.submodules):
            if debug:
                log.debug("  Submodule[%d]: %s", i, type(sub).__name__)
            _walk_modules(sub, target_name, path_with_current, results, debug)

    elif isinstance(node, FrameModule):
        node_name = node.header.name
        if debug:
            log.debug("  FrameModule: %r", node_name)
        path_with_current = [*current_path, node_name]

        if debug:
            log.debug(
                "  Checking %d submodules of FrameModule %r",
                len(node.submodules),
                node_name,
            )
        for i, sub in enumerate(node.submodules):
            if debug:
                log.debug("  Submodule[%d]: %s", i, type(sub).__name__)
            _walk_modules(sub, target_name, path_with_current, results, debug)

    elif isinstance(node, ModuleTypeDef):
        node_name = node.name
        if debug:
            log.debug("  ModuleTypeDef: %r", node_name)
            log.debug("  Has %d submodules", len(node.submodules))
        path_with_current = [*current_path, f"TypeDef:{node_name}"]

        for i, sub in enumerate(node.submodules):
            if debug:
                log.debug("  Submodule[%d]: %s", i, type(sub).__name__)
            _walk_modules(sub, target_name, path_with_current, results, debug)

    elif isinstance(node, BasePicture):
        if debug:
            log.debug("  BasePicture: %r", node.name)
            log.debug("  Has %d direct submodules", len(node.submodules))
            log.debug("  Has %d moduletype_defs", len(node.moduletype_defs))

        for i, sub in enumerate(node.submodules):
            if debug:
                log.debug("  Submodule[%d]: %s", i, type(sub).__name__)
            _walk_modules(sub, target_name, current_path, results, debug)

        for i, mtd in enumerate(node.moduletype_defs):
            if debug:
                log.debug("  ModuleTypeDef[%d]: %r", i, mtd.name)
            _walk_modules(mtd, target_name, current_path, results, debug)

    elif isinstance(node, ModuleTypeInstance):
        if debug:
            log.debug("  ModuleTypeInstance: %r (no submodules)", node.header.name)
        pass
    else:
        if debug:
            log.debug("  Unknown node type: %s", type(node).__name__)


def find_modules_by_name(
    base_picture: BasePicture, target_name: str, debug: bool = False
) -> list[tuple[list[str], SingleModule]]:
    """Find all SingleModule instances with the given name, returning path and module."""
    if debug:
        log.debug("=== SEARCHING FOR %r ===", target_name)

    results: list[tuple[list[str], SingleModule]] = []
    _walk_modules(base_picture, target_name, [base_picture.header.name], results, debug)

    if debug:
        log.debug("=== SEARCH COMPLETE: Found %d matches ===", len(results))

    return results


def compare_modules(
    modules_with_paths: list[tuple[list[str], SingleModule]],
) -> ComparisonResult:
    """Compare a list of SingleModules and identify differences."""
    if not modules_with_paths:
        return ComparisonResult(
            module_name="<none>",
            total_found=0,
            unique_variants=0,
        )

    module_name = modules_with_paths[0][1].header.name

    # Create fingerprints with paths
    instances_with_fps = [(path, create_fingerprint(m, path)) for path, m in modules_with_paths]

    # Group by structural similarity (EXCLUDE datecode from key)
    variant_groups: defaultdict[VariantFingerprintKey, list[tuple[list[str], ModuleFingerprint]]] = defaultdict(list)
    for path, fp in instances_with_fps:
        key = fingerprint_variant_key(fp)
        variant_groups[key].append((path, fp))

    # Get one representative fingerprint per variant
    unique_fingerprints = [group[0][1] for group in variant_groups.values()]

    # Compute detailed diffs if there are multiple variants
    param_diff = None
    localvar_diff = None
    submodule_diff = None
    code_diff = None

    if len(unique_fingerprints) > 1:
        param_diff = compare_variable_lists(unique_fingerprints)
        localvar_diff = compare_variable_lists(unique_fingerprints, "localvariables")
        submodule_diff = compare_submodules(unique_fingerprints)
        code_diff = compare_code(unique_fingerprints)

    return ComparisonResult(
        module_name=module_name,
        total_found=len(modules_with_paths),
        unique_variants=len(unique_fingerprints),
        fingerprints=unique_fingerprints,
        all_instances=instances_with_fps,
        parameter_diff=param_diff,
        localvar_diff=localvar_diff,
        submodule_diff=submodule_diff,
        code_diff=code_diff,
    )


def analyze_module_duplicates(base_picture: BasePicture, module_name: str, debug: bool = False) -> ComparisonResult:
    """Main entry point: find and compare all SingleModules with the given name."""
    modules_with_paths = find_modules_by_name(base_picture, module_name, debug)
    return compare_modules(modules_with_paths)


def _group_modules_by_name(
    base_picture: BasePicture,
) -> dict[str, list[tuple[list[str], SingleModule]]]:
    grouped: dict[str, list[tuple[list[str], SingleModule]]] = defaultdict(list)
    root_origin = getattr(base_picture, "origin_file", None)

    def walk(
        node: Any,
        current_path: list[str],
    ) -> None:
        if isinstance(node, SingleModule):
            module_path = [*current_path, node.header.name]
            if same_origin_file_stem(getattr(node, "origin_file", None), root_origin):
                grouped[normalize_name(node.header.name)].append((module_path, node))
            for child in node.submodules or []:
                walk(child, module_path)
            return

        if isinstance(node, FrameModule):
            module_path = [*current_path, node.header.name]
            for child in node.submodules or []:
                walk(child, module_path)
            return

        if isinstance(node, ModuleTypeDef):
            if not same_origin_file_stem(getattr(node, "origin_file", None), root_origin):
                return
            typedef_path = [*current_path, f"TypeDef:{node.name}"]
            for child in node.submodules or []:
                walk(child, typedef_path)
            return

        if isinstance(node, BasePicture):
            for child in node.submodules or []:
                walk(child, [node.header.name])
            for moduletype in node.moduletype_defs or []:
                walk(moduletype, [node.header.name])

    walk(base_picture, [base_picture.header.name])
    return grouped


def _common_module_prefix(paths: list[list[str]]) -> list[str]:
    if not paths:
        return []
    prefix = list(paths[0])
    for path in paths[1:]:
        limit = min(len(prefix), len(path))
        match_len = 0
        for index in range(limit):
            if prefix[index].casefold() != path[index].casefold():
                break
            match_len += 1
        prefix = prefix[:match_len]
        if not prefix:
            break
    return prefix


def _group_instances_by_variant(
    comparison: ComparisonResult,
) -> dict[int, list[tuple[list[str], ModuleFingerprint]]]:
    variant_map: dict[int, list[tuple[list[str], ModuleFingerprint]]] = defaultdict(list)
    for path, fingerprint in comparison.all_instances:
        for index, unique_fingerprint in enumerate(comparison.fingerprints, 1):
            if fingerprints_match(fingerprint, unique_fingerprint):
                variant_map[index].append((path, fingerprint))
                break
    return dict(variant_map)


def _compact_diff(diff: VariableDiff | SubmoduleDiff | CodeDiff | None) -> dict[str, Any] | None:
    return compact_diff(diff)


def _material_differences(comparison: ComparisonResult) -> dict[str, Any]:
    differences: dict[str, Any] = {}
    parameter_diff = _compact_diff(comparison.parameter_diff)
    if parameter_diff is not None:
        differences["moduleparameters"] = parameter_diff
    localvar_diff = _compact_diff(comparison.localvar_diff)
    if localvar_diff is not None:
        differences["localvariables"] = localvar_diff
    submodule_diff = _compact_diff(comparison.submodule_diff)
    if submodule_diff is not None:
        differences["submodules"] = submodule_diff
    code_diff = _compact_diff(comparison.code_diff)
    if code_diff is not None:
        differences["code"] = code_diff
    return differences


def _material_difference_labels(differences: dict[str, Any]) -> list[str]:
    return material_difference_labels(differences)


def analyze_version_drift(
    base_picture: BasePicture,
    debug: bool = False,
) -> VersionDriftReport:
    """Detect repeated module names that have drifted structurally over time."""
    issues: list[Issue] = []
    grouped_modules = _group_modules_by_name(base_picture)

    if debug:
        log.debug(
            "version drift: checking %d repeated module-name groups",
            len(grouped_modules),
        )

    for modules_with_paths in sorted(
        grouped_modules.values(),
        key=lambda items: (normalize_name(items[0][1].header.name), len(items)),
    ):
        if len(modules_with_paths) < 2:
            continue

        comparison = compare_modules(modules_with_paths)
        if comparison.unique_variants <= 1:
            continue

        differences = _material_differences(comparison)
        labels = _material_difference_labels(differences)
        label_text = ", ".join(labels) if labels else "module structure"
        variant_map = _group_instances_by_variant(comparison)
        instance_paths = [path for path, _module in modules_with_paths]
        location_preview = [" -> ".join(path) for path in instance_paths[:6]]
        if len(instance_paths) > 6:
            location_preview.append(f"... (+{len(instance_paths) - 6} more)")

        issues.append(
            Issue(
                kind="module.version_drift",
                message=(
                    f"Module {comparison.module_name!r} has {comparison.unique_variants} structural variants across "
                    f"{comparison.total_found} instances; drift is present in {label_text}."
                ),
                module_path=_common_module_prefix(instance_paths) or [base_picture.header.name],
                data={
                    "module_name": comparison.module_name,
                    "total_found": comparison.total_found,
                    "unique_variants": comparison.unique_variants,
                    "variant_instance_paths": {
                        variant_id: [path for path, _fingerprint in entries]
                        for variant_id, entries in variant_map.items()
                    },
                    "material_differences": differences,
                    "upgrade_notes": build_upgrade_notes(differences),
                    "location_preview": location_preview,
                },
            )
        )

    return VersionDriftReport(name=base_picture.header.name, issues=issues)
