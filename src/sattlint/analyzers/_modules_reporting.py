"""Reporting helpers for module comparison and version drift output."""

from collections import Counter, defaultdict
from typing import Any, cast

from ._modules_diffing import AstDiffDetail, CodeDiff, SubmoduleDiff, VariableDiff
from .framework import format_report_header


def compact_diff(diff: VariableDiff | SubmoduleDiff | CodeDiff | None) -> dict[str, Any] | None:
    if diff is None:
        return None
    if isinstance(diff, VariableDiff):
        only = {variant_id: names for variant_id, names in diff.only_in_variant.items() if names}
        modified = {
            name: [detail.to_dict() for detail in details] for name, details in diff.modified.items() if details
        }
        if not only and not modified:
            return None
        return {
            "common": diff.common,
            "only_in_variant": only,
            "modified": modified,
        }
    if isinstance(diff, SubmoduleDiff):
        only_paths = {
            variant_id: [list(item) for item in items] for variant_id, items in diff.only_in_variant.items() if items
        }
        if not only_paths:
            return None
        return {
            "common": [list(item) for item in diff.common],
            "only_in_variant": only_paths,
        }
    sequences_only = {variant_id: names for variant_id, names in diff.sequences_only_in_variant.items() if names}
    equations_only = {variant_id: names for variant_id, names in diff.equations_only_in_variant.items() if names}
    modified_sequences = {
        name: [detail.to_dict() for detail in details] for name, details in diff.modified_sequences.items() if details
    }
    modified_equations = {
        name: [detail.to_dict() for detail in details] for name, details in diff.modified_equations.items() if details
    }
    if not sequences_only and not equations_only and not modified_sequences and not modified_equations:
        return None
    return {
        "sequences_common": diff.sequences_common,
        "sequences_only_in_variant": sequences_only,
        "modified_sequences": modified_sequences,
        "equations_common": diff.equations_common,
        "equations_only_in_variant": equations_only,
        "modified_equations": modified_equations,
    }


def _format_variant_list(variant_ids: set[int]) -> str:
    return ", ".join(str(variant_id) for variant_id in sorted(variant_ids))


def _summarize_modified_item(label: str, item_name: str, details: list[AstDiffDetail]) -> str:
    paths = ", ".join(detail.path for detail in details[:3])
    if len(details) > 3:
        paths = f"{paths}, ... (+{len(details) - 3} more)"
    variants = _format_variant_list({variant_id for detail in details for variant_id in detail.variants})
    return f"{label} {item_name!r} changed across variants {variants} at {paths}."


def build_upgrade_notes(differences: dict[str, Any]) -> list[str]:
    notes: list[str] = []

    for bucket_name, label in (
        ("moduleparameters", "Module parameter"),
        ("localvariables", "Local variable"),
    ):
        bucket = cast(dict[str, Any] | None, differences.get(bucket_name))
        if not bucket:
            continue
        for variant_id, names in sorted(bucket.get("only_in_variant", {}).items()):
            if names:
                notes.append(f"{label}s only in variant {variant_id}: {', '.join(names)}.")
        for item_name, details in sorted(bucket.get("modified", {}).items()):
            detail_items = [
                AstDiffDetail(
                    path=detail["path"],
                    variants=cast(dict[int, str], detail["variants"]),
                )
                for detail in details
            ]
            notes.append(_summarize_modified_item(label, item_name, detail_items))

    code_bucket = cast(dict[str, Any] | None, differences.get("code"))
    if code_bucket:
        for variant_id, names in sorted(code_bucket.get("sequences_only_in_variant", {}).items()):
            if names:
                notes.append(f"Sequences only in variant {variant_id}: {', '.join(names)}.")
        for item_name, details in sorted(code_bucket.get("modified_sequences", {}).items()):
            detail_items = [
                AstDiffDetail(
                    path=detail["path"],
                    variants=cast(dict[int, str], detail["variants"]),
                )
                for detail in details
            ]
            notes.append(_summarize_modified_item("Sequence", item_name, detail_items))
        for variant_id, names in sorted(code_bucket.get("equations_only_in_variant", {}).items()):
            if names:
                notes.append(f"Equations only in variant {variant_id}: {', '.join(names)}.")
        for item_name, details in sorted(code_bucket.get("modified_equations", {}).items()):
            detail_items = [
                AstDiffDetail(
                    path=detail["path"],
                    variants=cast(dict[int, str], detail["variants"]),
                )
                for detail in details
            ]
            notes.append(_summarize_modified_item("Equation", item_name, detail_items))

    submodules_bucket = cast(dict[str, Any] | None, differences.get("submodules"))
    if submodules_bucket:
        for variant_id, items in sorted(submodules_bucket.get("only_in_variant", {}).items()):
            if items:
                notes.append(f"Submodule structure differs in variant {variant_id}: {len(items)} unique node(s).")

    return notes


def material_difference_labels(differences: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    if "moduleparameters" in differences:
        labels.append("module parameters")
    if "localvariables" in differences:
        labels.append("local variables")
    if "submodules" in differences:
        labels.append("submodule structure")
    if "code" in differences:
        labels.append("module code")
    return labels


def render_comparison_summary(comparison: Any) -> str:
    status = "ok" if comparison.unique_variants <= 1 else "issues"
    lines = format_report_header("Module comparison", comparison.module_name, status=status)
    lines.extend(
        [
            f"Total Instances Found: {comparison.total_found}",
            f"Unique Variants: {comparison.unique_variants}",
            "",
        ]
    )

    if comparison.total_found == 0:
        lines.append("! No modules found with this name")
        return "\n".join(lines)

    if comparison.unique_variants == 1:
        lines.append("OK All instances are structurally identical (datecodes may differ)")
        lines.append("")
        lines.append("Instance locations:")
        for path, fingerprint in comparison.all_instances:
            lines.append(f"  DateCode: {fingerprint.datecode} - {' -> '.join(path)}")
        return "\n".join(lines)

    variant_map: dict[int, list[tuple[list[str], Any]]] = defaultdict(list)
    for path, fingerprint in comparison.all_instances:
        for index, unique_fingerprint in enumerate(comparison.fingerprints, 1):
            if (
                fingerprint.num_moduleparameters == unique_fingerprint.num_moduleparameters
                and fingerprint.num_localvariables == unique_fingerprint.num_localvariables
                and fingerprint.num_submodules == unique_fingerprint.num_submodules
                and fingerprint.num_sequences == unique_fingerprint.num_sequences
                and fingerprint.num_equations == unique_fingerprint.num_equations
                and fingerprint.moduleparameters_hash == unique_fingerprint.moduleparameters_hash
                and fingerprint.localvariables_hash == unique_fingerprint.localvariables_hash
                and fingerprint.submodules_hash == unique_fingerprint.submodules_hash
                and fingerprint.parameter_mappings_hash == unique_fingerprint.parameter_mappings_hash
            ):
                variant_map[index].append((path, fingerprint))
                break

    lines.append(f"! Found {comparison.unique_variants} different structural variants")
    lines.append("")

    for index, unique_fingerprint in enumerate(comparison.fingerprints, 1):
        instances = variant_map.get(index, [])
        lines.append(f"=== Variant {index} ({len(instances)} instance(s)) ===")
        lines.append(f"Parameters: {unique_fingerprint.num_moduleparameters}")
        lines.append(f"Local Vars: {unique_fingerprint.num_localvariables}")
        lines.append(f"Submodules: {unique_fingerprint.num_submodules}")
        lines.append(f"Sequences: {unique_fingerprint.num_sequences}")
        lines.append(f"Equations: {unique_fingerprint.num_equations}")
        lines.append("Locations:")
        for path, fingerprint in instances:
            lines.append(f"  DateCode: {fingerprint.datecode} - {' -> '.join(path)}")
        lines.append("")

    if comparison.parameter_diff:
        lines.append("=== Module Parameters Differences ===")
        lines.append(f"Common ({len(comparison.parameter_diff.common)}): {sorted(comparison.parameter_diff.common)}")
        for variant_id, names in sorted(comparison.parameter_diff.only_in_variant.items()):
            if names:
                lines.append(f"Only in Variant {variant_id} ({len(names)}): {sorted(names)}")
        lines.append("")

    if comparison.localvar_diff:
        lines.append("=== Local Variables Differences ===")
        lines.append(f"Common ({len(comparison.localvar_diff.common)}): {sorted(comparison.localvar_diff.common)}")
        for variant_id, names in sorted(comparison.localvar_diff.only_in_variant.items()):
            if names:
                lines.append(f"Only in Variant {variant_id} ({len(names)}): {sorted(names)}")
        lines.append("")

    if comparison.submodule_diff:
        lines.append("=== Submodules Differences (Recursive Tree) ===")
        common_by_depth: defaultdict[int, list[tuple[str, str]]] = defaultdict(list)
        for depth, name, subtype in comparison.submodule_diff.common:
            common_by_depth[depth].append((name, subtype))

        lines.append(f"Common across all variants ({len(comparison.submodule_diff.common)} total):")
        for depth in sorted(common_by_depth):
            indent = "  " + ("  " * depth)
            for name, subtype in sorted(common_by_depth[depth]):
                lines.append(f"{indent}Depth {depth}: {name} ({subtype})")

        for variant_id, unique_submodules in sorted(comparison.submodule_diff.only_in_variant.items()):
            if unique_submodules:
                lines.append(f"Only in Variant {variant_id} ({len(unique_submodules)} nodes):")
                by_depth: defaultdict[int, list[tuple[str, str]]] = defaultdict(list)
                for depth, name, subtype in unique_submodules:
                    by_depth[depth].append((name, subtype))
                for depth in sorted(by_depth):
                    indent = "  " + ("  " * depth)
                    for name, subtype in sorted(by_depth[depth]):
                        lines.append(f"{indent}Depth {depth}: {name} ({subtype})")
        lines.append("")

    if comparison.code_diff:
        lines.append("=== Module Code Differences ===")
        if comparison.code_diff.sequences_common or any(comparison.code_diff.sequences_only_in_variant.values()):
            lines.append(
                f"Sequences Common ({len(comparison.code_diff.sequences_common)}): {sorted(comparison.code_diff.sequences_common)}"
            )
            for variant_id, names in sorted(comparison.code_diff.sequences_only_in_variant.items()):
                if names:
                    lines.append(f"Sequences Only in Variant {variant_id} ({len(names)}): {sorted(names)}")
        if comparison.code_diff.equations_common or any(comparison.code_diff.equations_only_in_variant.values()):
            lines.append(
                f"Equations Common ({len(comparison.code_diff.equations_common)}): {sorted(comparison.code_diff.equations_common)}"
            )
            for variant_id, names in sorted(comparison.code_diff.equations_only_in_variant.items()):
                if names:
                    lines.append(f"Equations Only in Variant {variant_id} ({len(names)}): {sorted(names)}")
        lines.append("")

    return "\n".join(lines)


def render_version_drift_summary(report: Any) -> str:
    if not report.issues:
        lines = format_report_header("Version drift", report.name, status="ok")
        lines.append("No module version drift found.")
        return "\n".join(lines)

    lines = format_report_header("Version drift", report.name, status="issues")
    lines.append(f"Issues: {len(report.issues)}")
    lines.append("")
    kind_counts = Counter(issue.kind for issue in report.issues)
    lines.append("Kinds:")
    lines.append(f"  - Module version drift: {kind_counts.get('module.version_drift', 0)}")
    lines.append("")
    lines.append("Findings:")
    for issue in report.issues:
        location = ".".join(issue.module_path or [report.name])
        lines.append(f"  - [{location}] {issue.message}")
    return "\n".join(lines)
