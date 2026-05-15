"""Reporting helpers for module comparison and version drift output."""

from typing import Any, cast

from ._modules_diffing import AstDiffDetail, CodeDiff, SubmoduleDiff, VariableDiff


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
