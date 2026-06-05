"""Module comparison and version drift analysis helpers."""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeDef,
    ModuleTypeInstance,
    SingleModule,
)

from . import _modules_diffing as modules_diffing
from ._modules_debug import debug_module_structure
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
    normalize_ast_value,
    normalize_name,
)
from ._modules_reporting import (
    build_upgrade_notes,
    compact_diff,
    material_difference_labels,
    render_comparison_summary,
    render_version_drift_summary,
)
from .framework import Issue, empty_issues
from .variable_utils import same_origin_file_stem

log = logging.getLogger("SattLint")

AstDiffDetail = modules_diffing.AstDiffDetail

__all__ = [
    "AstDiffDetail",
    "CodeDiff",
    "ComparisonResult",
    "SubmoduleDiff",
    "VariableDiff",
    "_build_upgrade_notes",
    "_collect_named_item_diffs",
    "_common_module_prefix",
    "_compact_diff",
    "_diff_normalized_variants",
    "_group_instances_by_variant",
    "_material_difference_labels",
    "_material_differences",
    "_normalize_ast_value",
    "analyze_version_drift",
    "compare_modules",
    "create_fingerprint",
    "debug_module_structure",
]


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
        return render_comparison_summary(self)


@dataclass
class VersionDriftReport:
    """Analyzer-facing report for module version drift findings."""

    name: str
    issues: list[Issue] = field(default_factory=empty_issues)

    def summary(self) -> str:
        return render_version_drift_summary(self)


@dataclass
class _ModuleSearchStats:
    visited_nodes: int = 0
    single_modules: int = 0
    frame_modules: int = 0
    moduletype_defs: int = 0
    moduletype_instances: int = 0
    unknown_nodes: int = 0


def _walk_modules(
    node: Any,
    target_name: str,
    current_path: list[str],
    results: list[tuple[list[str], SingleModule]],
    *,
    stats: _ModuleSearchStats | None = None,
) -> None:
    """Recursively find all SingleModule instances with the target name (case-insensitive)."""
    target_name_lower = target_name.lower()
    if stats is not None:
        stats.visited_nodes += 1

    if isinstance(node, SingleModule):
        if stats is not None:
            stats.single_modules += 1
        node_name = node.header.name
        node_name_lower = node_name.lower()

        path_with_current = [*current_path, node_name]

        if node_name_lower == target_name_lower:
            results.append((path_with_current, node))

        for sub in node.submodules:
            _walk_modules(sub, target_name, path_with_current, results, stats=stats)

    elif isinstance(node, FrameModule):
        if stats is not None:
            stats.frame_modules += 1
        node_name = node.header.name
        path_with_current = [*current_path, node_name]

        for sub in node.submodules:
            _walk_modules(sub, target_name, path_with_current, results, stats=stats)

    elif isinstance(node, ModuleTypeDef):
        if stats is not None:
            stats.moduletype_defs += 1
        node_name = node.name
        path_with_current = [*current_path, f"TypeDef:{node_name}"]

        for sub in node.submodules:
            _walk_modules(sub, target_name, path_with_current, results, stats=stats)

    elif isinstance(node, BasePicture):
        for sub in node.submodules:
            _walk_modules(sub, target_name, current_path, results, stats=stats)

        for mtd in node.moduletype_defs:
            _walk_modules(mtd, target_name, current_path, results, stats=stats)

    elif isinstance(node, ModuleTypeInstance):
        if stats is not None:
            stats.moduletype_instances += 1
    else:
        if stats is not None:
            stats.unknown_nodes += 1


def find_modules_by_name(
    base_picture: BasePicture, target_name: str, debug: bool = False
) -> list[tuple[list[str], SingleModule]]:
    """Find all SingleModule instances with the given name, returning path and module."""
    stats = _ModuleSearchStats() if debug else None
    if debug:
        log.debug(
            "Module search start: target=%r root=%r",
            target_name,
            base_picture.header.name,
        )

    results: list[tuple[list[str], SingleModule]] = []
    _walk_modules(base_picture, target_name, [base_picture.header.name], results, stats=stats)

    if debug and stats is not None:
        log.debug(
            "Module search complete: target=%r visited=%d single_modules=%d frame_modules=%d moduletype_defs=%d moduletype_instances=%d unknown_nodes=%d matches=%d",
            target_name,
            stats.visited_nodes,
            stats.single_modules,
            stats.frame_modules,
            stats.moduletype_defs,
            stats.moduletype_instances,
            stats.unknown_nodes,
            len(results),
        )
        if results:
            preview = [" -> ".join(path) for path, _module in results[:5]]
            if len(results) > 5:
                preview.append(f"... (+{len(results) - 5} more)")
            log.debug("Module search matches: %s", "; ".join(preview))

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


def _build_upgrade_notes(differences: dict[str, Any]) -> list[str]:
    return build_upgrade_notes(differences)


def _normalize_ast_value(value: Any) -> Any:
    return normalize_ast_value(value)


def _collect_named_item_diffs(variant_items: Any) -> Any:
    return cast(Any, modules_diffing)._collect_named_item_diffs(variant_items)


def _diff_normalized_variants(variants: Any, path: str = "") -> Any:
    return cast(Any, modules_diffing)._diff_normalized_variants(variants, path)


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
