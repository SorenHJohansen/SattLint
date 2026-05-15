"""Normalized diff helpers for module comparison variants."""

from collections.abc import Mapping
from collections.abc import Sequence as CollectionSequence
from dataclasses import dataclass, field
from typing import Any, TypeGuard, cast

from ._modules_fingerprints import (
    MISSING_AST_VALUE,
    CodeEntryMap,
    ModuleFingerprint,
    NamedNormalizedValue,
    NormalizedDictValue,
    NormalizedFields,
    NormalizedListValue,
    NormalizedObjectValue,
    NormalizedTupleValue,
    NormalizedValue,
    get_submodule_tree_structure,
    normalize_ast_value,
    normalize_name,
)


def _empty_ast_diff_map() -> dict[str, list["AstDiffDetail"]]:
    return {}


@dataclass
class VariableDiff:
    """Comparison of variable lists."""

    common: list[str]
    only_in_variant: dict[int, list[str]]
    modified: dict[str, list["AstDiffDetail"]] = field(default_factory=_empty_ast_diff_map)


@dataclass
class SubmoduleDiff:
    """Comparison of submodule tree structures."""

    common: list[tuple[int, str, str]]
    only_in_variant: dict[int, list[tuple[int, str, str]]]


@dataclass
class CodeDiff:
    """Comparison of module code."""

    sequences_common: list[str]
    sequences_only_in_variant: dict[int, list[str]]
    equations_common: list[str]
    equations_only_in_variant: dict[int, list[str]]
    modified_sequences: dict[str, list["AstDiffDetail"]] = field(default_factory=_empty_ast_diff_map)
    modified_equations: dict[str, list["AstDiffDetail"]] = field(default_factory=_empty_ast_diff_map)


@dataclass(frozen=True)
class AstDiffDetail:
    """A compact AST-level difference across analyzed variants."""

    path: str
    variants: dict[int, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "variants": dict(self.variants),
        }


def _is_named_field_collection(value: object) -> TypeGuard[NormalizedFields]:
    if not isinstance(value, tuple):
        return False
    items = cast(tuple[object, ...], value)
    for item in items:
        if not isinstance(item, tuple):
            return False
        parts = cast(tuple[object, ...], item)
        if len(parts) != 2 or not isinstance(parts[0], str):
            return False
    return True


def _normalized_value_kind(value: object) -> str:
    if value is MISSING_AST_VALUE:
        return "missing"
    if isinstance(value, tuple):
        parts = cast(tuple[object, ...], value)
        if len(parts) == 2 and parts[0] in {"dict", "list", "tuple"}:
            return cast(str, parts[0])
        if len(parts) == 2 and isinstance(parts[0], str) and _is_named_field_collection(parts[1]):
            return f"object:{parts[0]}"
    return "scalar"


def _stringify_normalized_value(value: object) -> str:
    if value is MISSING_AST_VALUE:
        return "<missing>"
    text = repr(value)
    if len(text) > 140:
        return text[:137] + "..."
    return text


def _join_diff_path(base: str, segment: str) -> str:
    if not base:
        return segment
    if segment.startswith("["):
        return f"{base}{segment}"
    return f"{base}.{segment}"


def _diff_normalized_variants(
    variants: Mapping[int, object],
    path: str = "",
) -> list[AstDiffDetail]:
    if len({_stringify_normalized_value(value) for value in variants.values()}) <= 1:
        return []

    kinds = {variant_id: _normalized_value_kind(value) for variant_id, value in variants.items()}
    if len(set(kinds.values())) != 1:
        return [
            AstDiffDetail(
                path=path or "<root>",
                variants={
                    variant_id: _stringify_normalized_value(value) for variant_id, value in sorted(variants.items())
                },
            )
        ]

    kind = next(iter(kinds.values()))
    if kind == "list":
        list_values: dict[int, tuple[NormalizedValue, ...]] = {
            variant_id: cast(NormalizedListValue, value)[1] for variant_id, value in variants.items()
        }
        max_len = max(len(items) for items in list_values.values())
        details: list[AstDiffDetail] = []
        for index in range(max_len):
            child_variants = {
                variant_id: items[index] if index < len(items) else MISSING_AST_VALUE
                for variant_id, items in list_values.items()
            }
            details.extend(_diff_normalized_variants(child_variants, _join_diff_path(path, f"[{index}]")))
        return details

    if kind == "tuple":
        tuple_values: dict[int, tuple[NormalizedValue, ...]] = {
            variant_id: cast(NormalizedTupleValue, value)[1] for variant_id, value in variants.items()
        }
        max_len = max(len(items) for items in tuple_values.values())
        details: list[AstDiffDetail] = []
        for index in range(max_len):
            child_variants = {
                variant_id: items[index] if index < len(items) else MISSING_AST_VALUE
                for variant_id, items in tuple_values.items()
            }
            details.extend(_diff_normalized_variants(child_variants, _join_diff_path(path, f"[{index}]")))
        return details

    if kind == "dict":
        dict_values: dict[int, dict[str, NormalizedValue]] = {
            variant_id: dict(cast(NormalizedDictValue, value)[1]) for variant_id, value in variants.items()
        }
        keys = sorted({key for mapping in dict_values.values() for key in mapping})
        details: list[AstDiffDetail] = []
        for key in keys:
            child_variants = {
                variant_id: mapping.get(key, MISSING_AST_VALUE) for variant_id, mapping in dict_values.items()
            }
            details.extend(_diff_normalized_variants(child_variants, _join_diff_path(path, key)))
        return details

    if kind.startswith("object:"):
        object_values: dict[int, dict[str, NormalizedValue]] = {
            variant_id: dict(cast(NormalizedObjectValue, value)[1]) for variant_id, value in variants.items()
        }
        keys = sorted({key for mapping in object_values.values() for key in mapping})
        details: list[AstDiffDetail] = []
        for key in keys:
            child_variants = {
                variant_id: mapping.get(key, MISSING_AST_VALUE) for variant_id, mapping in object_values.items()
            }
            details.extend(_diff_normalized_variants(child_variants, _join_diff_path(path, key)))
        return details

    return [
        AstDiffDetail(
            path=path or "<root>",
            variants={variant_id: _stringify_normalized_value(value) for variant_id, value in sorted(variants.items())},
        )
    ]


def _collect_named_item_diffs(
    variant_items: CollectionSequence[Mapping[str, NamedNormalizedValue]],
) -> tuple[list[str], dict[int, list[str]], dict[str, list[AstDiffDetail]]]:
    common_normalized: set[str] = set()
    if variant_items:
        common_normalized = set(variant_items[0].keys())
        for items in variant_items[1:]:
            common_normalized &= set(items.keys())

    common = [variant_items[0][name][0] for name in sorted(common_normalized)] if variant_items else []
    only_in_variant = {
        index: [items[name][0] for name in sorted(set(items.keys()) - common_normalized)]
        for index, items in enumerate(variant_items, 1)
    }

    modified: dict[str, list[AstDiffDetail]] = {}
    for name in sorted(common_normalized):
        signatures = {index: items[name][1] for index, items in enumerate(variant_items, 1)}
        details = _diff_normalized_variants(signatures)
        if details:
            modified[variant_items[0][name][0]] = details

    return common, only_in_variant, modified


def compare_variable_lists(fingerprints: list[ModuleFingerprint], attr: str = "moduleparameters") -> VariableDiff:
    """Compare a named variable list across variants."""
    variant_names: list[dict[str, NamedNormalizedValue]] = []
    for fingerprint in fingerprints:
        names = {
            normalize_name(variable.name): (
                variable.name,
                normalize_ast_value(variable),
            )
            for variable in getattr(fingerprint, attr)
        }
        variant_names.append(names)

    common, only_in_variant, modified = _collect_named_item_diffs(variant_names)
    return VariableDiff(common=common, only_in_variant=only_in_variant, modified=modified)


def compare_submodules(fingerprints: list[ModuleFingerprint]) -> SubmoduleDiff:
    """Compare complete submodule tree structures across variants."""
    variant_structures = [get_submodule_tree_structure(fingerprint.submodules) for fingerprint in fingerprints]

    common_set: set[tuple[int, str, str]] = set()
    if variant_structures:
        common_set = variant_structures[0].copy()
        for structure in variant_structures[1:]:
            common_set &= structure
        common = sorted(common_set)
    else:
        common = []

    only_in_variant = {index: sorted(structure - common_set) for index, structure in enumerate(variant_structures, 1)}
    return SubmoduleDiff(common=common, only_in_variant=only_in_variant)


def compare_code(fingerprints: list[ModuleFingerprint]) -> CodeDiff:
    """Compare module code across variants."""
    variant_seqs: list[CodeEntryMap] = []
    variant_eqs: list[CodeEntryMap] = []

    for fingerprint in fingerprints:
        sequences = {
            key: (item.name, signature)
            for key, (item, signature) in {
                normalize_name(sequence.name): (
                    sequence,
                    normalize_ast_value(sequence),
                )
                for sequence in fingerprint.sequences
            }.items()
        }
        equations = {
            key: (item.name, signature)
            for key, (item, signature) in {
                normalize_name(equation.name): (
                    equation,
                    normalize_ast_value(equation),
                )
                for equation in fingerprint.equations
            }.items()
        }
        variant_seqs.append(sequences)
        variant_eqs.append(equations)

    seq_presence: set[str] = set(variant_seqs[0].keys()) if variant_seqs else set()
    for sequences in variant_seqs[1:]:
        seq_presence &= set(sequences.keys())

    modified_sequences: dict[str, list[AstDiffDetail]] = {}
    common_sequences: list[str] = []
    for name in sorted(seq_presence):
        signatures: dict[int, NormalizedValue] = {
            index: sequences[name][1] for index, sequences in enumerate(variant_seqs, 1)
        }
        details = _diff_normalized_variants(signatures)
        if details:
            modified_sequences[variant_seqs[0][name][0]] = details
            continue
        common_sequences.append(variant_seqs[0][name][0])

    only_sequences = {
        index: [sequences[name][0] for name in sorted(set(sequences.keys()) - seq_presence)]
        for index, sequences in enumerate(variant_seqs, 1)
    }

    eq_presence: set[str] = set(variant_eqs[0].keys()) if variant_eqs else set()
    for equations in variant_eqs[1:]:
        eq_presence &= set(equations.keys())

    modified_equations: dict[str, list[AstDiffDetail]] = {}
    common_equations: list[str] = []
    for name in sorted(eq_presence):
        signatures: dict[int, NormalizedValue] = {
            index: equations[name][1] for index, equations in enumerate(variant_eqs, 1)
        }
        details = _diff_normalized_variants(signatures)
        if details:
            modified_equations[variant_eqs[0][name][0]] = details
            continue
        common_equations.append(variant_eqs[0][name][0])

    only_equations = {
        index: [equations[name][0] for name in sorted(set(equations.keys()) - eq_presence)]
        for index, equations in enumerate(variant_eqs, 1)
    }

    return CodeDiff(
        sequences_common=common_sequences,
        sequences_only_in_variant=only_sequences,
        equations_common=common_equations,
        equations_only_in_variant=only_equations,
        modified_sequences=modified_sequences,
        modified_equations=modified_equations,
    )
