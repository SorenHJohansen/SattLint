"""Module comparison, version drift analysis, and debug helpers."""
import logging
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any, cast
from ..models.ast_model import (
    BasePicture,
    SingleModule,
    FrameModule,
    ModuleTypeInstance,
    ModuleTypeDef,
    Variable,
    ParameterMapping,
    Sequence,
    Equation,
)
from .framework import Issue, format_report_header

log = logging.getLogger("SattLint")

_IGNORED_AST_FIELDS = {
    "datecode",
    "description",
    "invoke_coord",
    "origin_file",
    "origin_lib",
    "position",
    "size",
    "source_span",
    "span",
}
_MISSING_AST_VALUE = object()


def debug_module_structure(base_picture: BasePicture, max_depth: int = 10) -> None:
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
class ModuleFingerprint:
    """Represents the structure of a SingleModule for comparison."""

    name: str
    datecode: int | None
    num_moduleparameters: int
    num_localvariables: int
    num_submodules: int
    has_moduledef: bool
    has_modulecode: bool
    num_sequences: int
    num_equations: int
    num_parameter_mappings: int

    # Store actual lists for detailed comparison
    moduleparameters: list[Variable]
    localvariables: list[Variable]
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance]
    sequences: list[Sequence]
    equations: list[Equation]

    # Hashes for grouping (exclude datecode)
    moduleparameters_hash: int
    localvariables_hash: int
    submodules_hash: int
    parameter_mappings_hash: int

    # Store the actual module for access
    module: SingleModule
    module_path: list[str] = field(default_factory=list)


@dataclass
class VariableDiff:
    """Comparison of variable lists."""

    common: list[str]  # case-insensitive common names
    only_in_variant: dict[int, list[str]]  # variant_id -> list of names
    modified: dict[str, list["AstDiffDetail"]] = field(default_factory=dict)


def _get_submodule_tree_structure(
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance],
    depth: int = 0,
    max_depth: int = 10,
) -> set[tuple]:
    """
    Recursively extract the complete tree structure of submodules.
    Returns a set of tuples representing the full hierarchy.
    """
    if depth > max_depth:
        return set()

    structure = set()

    for sm in submodules:
        name = _normalize_name(sm.header.name)

        if isinstance(sm, SingleModule):
            typ = "Single"
            # Add this node
            structure.add((depth, name, typ))
            # Recurse into its submodules
            child_structure = _get_submodule_tree_structure(
                sm.submodules, depth + 1, max_depth
            )
            structure.update(child_structure)

        elif isinstance(sm, FrameModule):
            typ = "Frame"
            # Add this node
            structure.add((depth, name, typ))
            # Recurse into its submodules
            child_structure = _get_submodule_tree_structure(
                sm.submodules, depth + 1, max_depth
            )
            structure.update(child_structure)

        elif isinstance(sm, ModuleTypeInstance):
            typ = f"Instance:{_normalize_name(sm.moduletype_name)}"
            # Add this node (instances have no submodules)
            structure.add((depth, name, typ))

    return structure


@dataclass
class SubmoduleDiff:
    """Comparison of submodule tree structures (full recursive)."""

    common: list[tuple[int, str, str]]  # (depth, name, type)
    only_in_variant: dict[int, list[tuple[int, str, str]]]


@dataclass
class CodeDiff:
    """Comparison of module code."""

    sequences_common: list[str]
    sequences_only_in_variant: dict[int, list[str]]
    equations_common: list[str]
    equations_only_in_variant: dict[int, list[str]]
    modified_sequences: dict[str, list["AstDiffDetail"]] = field(default_factory=dict)
    modified_equations: dict[str, list["AstDiffDetail"]] = field(default_factory=dict)


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


@dataclass
class ComparisonResult:
    """Results of comparing multiple SingleModules with the same name."""

    module_name: str
    total_found: int
    unique_variants: int
    fingerprints: list[ModuleFingerprint] = field(default_factory=list)
    all_instances: list[tuple[list[str], ModuleFingerprint]] = field(
        default_factory=list
    )

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
            lines.append(
                "✓ All instances are structurally identical (datecodes may differ)"
            )
            lines.append("")
            lines.append("Instance locations:")
            for path, fp in self.all_instances:
                lines.append(f"  DateCode: {fp.datecode} - {' → '.join(path)}")
        else:
            lines.append(
                f"⚠ Found {self.unique_variants} different structural variants"
            )
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
                        and fp.parameter_mappings_hash
                        == unique_fp.parameter_mappings_hash
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
                lines.append(
                    f"Common ({len(self.parameter_diff.common)}): {sorted(self.parameter_diff.common)}"
                )
                for var_id, names in sorted(
                    self.parameter_diff.only_in_variant.items()
                ):
                    if names:
                        lines.append(
                            f"Only in Variant {var_id} ({len(names)}): {sorted(names)}"
                        )
                lines.append("")

            if self.localvar_diff:
                lines.append("=== Local Variables Differences ===")
                lines.append(
                    f"Common ({len(self.localvar_diff.common)}): {sorted(self.localvar_diff.common)}"
                )
                for var_id, names in sorted(self.localvar_diff.only_in_variant.items()):
                    if names:
                        lines.append(
                            f"Only in Variant {var_id} ({len(names)}): {sorted(names)}"
                        )
                lines.append("")

            if self.submodule_diff:
                lines.append("=== Submodules Differences (Recursive Tree) ===")

                # Group common by depth for better readability
                common_by_depth = defaultdict(list)
                for depth, name, typ in self.submodule_diff.common:
                    common_by_depth[depth].append((name, typ))

                lines.append(
                    f"Common across all variants ({len(self.submodule_diff.common)} total):"
                )
                for depth in sorted(common_by_depth.keys()):
                    indent = "  " + ("  " * depth)
                    items = common_by_depth[depth]
                    for name, typ in sorted(items):
                        lines.append(f"{indent}Depth {depth}: {name} ({typ})")

                # Show unique submodules per variant
                for var_id, unique_subs in sorted(
                    self.submodule_diff.only_in_variant.items()
                ):
                    if unique_subs:
                        lines.append(
                            f"Only in Variant {var_id} ({len(unique_subs)} nodes):"
                        )
                        # Group by depth
                        by_depth = defaultdict(list)
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
                if self.code_diff.sequences_common or any(
                    self.code_diff.sequences_only_in_variant.values()
                ):
                    lines.append(
                        f"Sequences Common ({len(self.code_diff.sequences_common)}): {sorted(self.code_diff.sequences_common)}"
                    )
                    for var_id, names in sorted(
                        self.code_diff.sequences_only_in_variant.items()
                    ):
                        if names:
                            lines.append(
                                f"Sequences Only in Variant {var_id} ({len(names)}): {sorted(names)}"
                            )
                if self.code_diff.equations_common or any(
                    self.code_diff.equations_only_in_variant.values()
                ):
                    lines.append(
                        f"Equations Common ({len(self.code_diff.equations_common)}): {sorted(self.code_diff.equations_common)}"
                    )
                    for var_id, names in sorted(
                        self.code_diff.equations_only_in_variant.items()
                    ):
                        if names:
                            lines.append(
                                f"Equations Only in Variant {var_id} ({len(names)}): {sorted(names)}"
                            )
                lines.append("")

        return "\n".join(lines)


@dataclass
class VersionDriftReport:
    """Analyzer-facing report for module version drift findings."""

    name: str
    issues: list[Issue] = field(default_factory=list)

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
        lines.append(
            f"  - Module version drift: {kind_counts.get('module.version_drift', 0)}"
        )
        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


def _normalize_name(name: str) -> str:
    """Normalize a name for case-insensitive comparison."""
    return name.lower().strip()


def _normalize_ast_value(value: Any) -> object:
    """Normalize AST-like values into stable, hashable tuples."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, Enum):
        enum_value = value.value
        if isinstance(enum_value, str):
            enum_value = enum_value.casefold()
        return (type(value).__name__, enum_value)

    if isinstance(value, dict):
        items = []
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            if key in _IGNORED_AST_FIELDS:
                continue
            normalized = _normalize_ast_value(item)
            if key in {"state", "var_name"} and isinstance(normalized, str):
                normalized = normalized.casefold()
            items.append((str(key), normalized))
        return ("dict", tuple(items))

    if isinstance(value, tuple):
        return ("tuple", tuple(_normalize_ast_value(item) for item in value))

    if isinstance(value, list):
        return ("list", tuple(_normalize_ast_value(item) for item in value))

    if is_dataclass(value):
        items = []
        for field_info in fields(value):
            if field_info.name in _IGNORED_AST_FIELDS:
                continue
            normalized = _normalize_ast_value(getattr(value, field_info.name))
            if field_info.name in {"name", "target", "type"} and isinstance(
                normalized, str
            ):
                normalized = normalized.casefold()
            items.append((field_info.name, normalized))
        return (type(value).__name__, tuple(items))

    if hasattr(value, "data") and hasattr(value, "children"):
        return (
            type(value).__name__,
            getattr(value, "data", None),
            tuple(_normalize_ast_value(child) for child in getattr(value, "children", [])),
        )

    if hasattr(value, "__dict__"):
        items = []
        for key, item in sorted(vars(value).items()):
            if key.startswith("_") or key in _IGNORED_AST_FIELDS:
                continue
            items.append((key, _normalize_ast_value(item)))
        return (type(value).__name__, tuple(items))

    return repr(value)


def _is_named_field_collection(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and all(
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            for item in value
        )
    )


def _normalized_value_kind(value: object) -> str:
    if value is _MISSING_AST_VALUE:
        return "missing"
    if isinstance(value, tuple) and len(value) == 2 and value[0] in {"dict", "list", "tuple"}:
        return cast(str, value[0])
    if (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and _is_named_field_collection(value[1])
    ):
        return f"object:{value[0]}"
    return "scalar"


def _stringify_normalized_value(value: object) -> str:
    if value is _MISSING_AST_VALUE:
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
    variants: dict[int, object],
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
                    variant_id: _stringify_normalized_value(value)
                    for variant_id, value in sorted(variants.items())
                },
            )
        ]

    kind = next(iter(kinds.values()))
    if kind == "list":
        list_values = {
            variant_id: cast(tuple[Any, ...], cast(tuple[object, tuple[Any, ...]], value)[1])
            for variant_id, value in variants.items()
        }
        max_len = max(len(items) for items in list_values.values())
        details: list[AstDiffDetail] = []
        for index in range(max_len):
            child_variants = {
                variant_id: items[index] if index < len(items) else _MISSING_AST_VALUE
                for variant_id, items in list_values.items()
            }
            details.extend(
                _diff_normalized_variants(
                    child_variants,
                    _join_diff_path(path, f"[{index}]"),
                )
            )
        return details

    if kind == "tuple":
        tuple_values = {
            variant_id: cast(tuple[Any, ...], cast(tuple[object, tuple[Any, ...]], value)[1])
            for variant_id, value in variants.items()
        }
        max_len = max(len(items) for items in tuple_values.values())
        details = []
        for index in range(max_len):
            child_variants = {
                variant_id: items[index] if index < len(items) else _MISSING_AST_VALUE
                for variant_id, items in tuple_values.items()
            }
            details.extend(
                _diff_normalized_variants(
                    child_variants,
                    _join_diff_path(path, f"[{index}]"),
                )
            )
        return details

    if kind == "dict":
        dict_values: dict[int, dict[str, object]] = {
            variant_id: {
                key: item
                for key, item in cast(
                    tuple[tuple[str, object], ...],
                    cast(tuple[object, tuple[tuple[str, object], ...]], value)[1],
                )
            }
            for variant_id, value in variants.items()
        }
        keys = sorted({key for mapping in dict_values.values() for key in mapping})
        details = []
        for key in keys:
            child_variants = {
                variant_id: mapping.get(key, _MISSING_AST_VALUE)
                for variant_id, mapping in dict_values.items()
            }
            details.extend(
                _diff_normalized_variants(
                    child_variants,
                    _join_diff_path(path, key),
                )
            )
        return details

    if kind.startswith("object:"):
        object_values: dict[int, dict[str, object]] = {
            variant_id: {
                key: item
                for key, item in cast(
                    tuple[tuple[str, object], ...],
                    cast(tuple[object, tuple[tuple[str, object], ...]], value)[1],
                )
            }
            for variant_id, value in variants.items()
        }
        keys = sorted({key for mapping in object_values.values() for key in mapping})
        details = []
        for key in keys:
            child_variants = {
                variant_id: mapping.get(key, _MISSING_AST_VALUE)
                for variant_id, mapping in object_values.items()
            }
            details.extend(
                _diff_normalized_variants(
                    child_variants,
                    _join_diff_path(path, key),
                )
            )
        return details

    return [
        AstDiffDetail(
            path=path or "<root>",
            variants={
                variant_id: _stringify_normalized_value(value)
                for variant_id, value in sorted(variants.items())
            },
        )
    ]


def _collect_named_item_diffs(
    variant_items: list[dict[str, tuple[str, object]]],
) -> tuple[list[str], dict[int, list[str]], dict[str, list[AstDiffDetail]]]:
    common_normalized: set[str] = set()
    if variant_items:
        common_normalized = set(variant_items[0].keys())
        for items in variant_items[1:]:
            common_normalized &= set(items.keys())

    common = [variant_items[0][name][0] for name in sorted(common_normalized)] if variant_items else []
    only_in_variant = {
        index: [
            items[name][0]
            for name in sorted(set(items.keys()) - common_normalized)
        ]
        for index, items in enumerate(variant_items, 1)
    }

    modified: dict[str, list[AstDiffDetail]] = {}
    for name in sorted(common_normalized):
        signatures = {
            index: items[name][1]
            for index, items in enumerate(variant_items, 1)
        }
        details = _diff_normalized_variants(signatures)
        if details:
            modified[variant_items[0][name][0]] = details

    return common, only_in_variant, modified


def _code_entry_map(items: list[Sequence] | list[Equation]) -> dict[str, object]:
    """Map case-insensitive names to normalized structural signatures."""
    return {
        _normalize_name(item.name): _normalize_ast_value(item)
        for item in items
    }


def _compare_variable_lists(fingerprints: list[ModuleFingerprint], attr: str = "moduleparameters") -> VariableDiff:
    """Compare a named variable list (moduleparameters or localvariables) across variants."""
    variant_names = []
    for fp in fingerprints:
        names = {
            _normalize_name(variable.name): (
                variable.name,
                _normalize_ast_value(variable),
            )
            for variable in getattr(fp, attr)
        }
        variant_names.append(names)

    common, only_in_variant, modified = _collect_named_item_diffs(variant_names)
    return VariableDiff(
        common=common,
        only_in_variant=only_in_variant,
        modified=modified,
    )


def _compare_submodules(fingerprints: list[ModuleFingerprint]) -> SubmoduleDiff:
    """Compare complete submodule tree structures across variants (recursive)."""
    variant_structures = []

    for fp in fingerprints:
        # Get the full recursive tree structure
        structure = _get_submodule_tree_structure(fp.submodules)
        variant_structures.append(structure)

    # Find common elements (intersection of all variant structures)
    common_set: set[tuple[int, str, str]] = set()
    if variant_structures:
        common_set = variant_structures[0].copy()
        for structure in variant_structures[1:]:
            common_set &= structure
        common = sorted(common_set)  # Sort by depth, then name
    else:
        common = []

    # Find unique elements in each variant
    only_in_variant = {}
    for i, structure in enumerate(variant_structures, 1):
        unique = structure - common_set
        only_in_variant[i] = sorted(unique)

    return SubmoduleDiff(common=common, only_in_variant=only_in_variant)


def _compare_code(fingerprints: list[ModuleFingerprint]) -> CodeDiff:
    """Compare module code (sequences and equations) across variants."""
    variant_seqs = []
    variant_eqs = []

    for fp in fingerprints:
        seqs = {
            key: (item.name, signature)
            for key, (item, signature) in {
                _normalize_name(sequence.name): (
                    sequence,
                    _normalize_ast_value(sequence),
                )
                for sequence in fp.sequences
            }.items()
        }
        eqs = {
            key: (item.name, signature)
            for key, (item, signature) in {
                _normalize_name(equation.name): (
                    equation,
                    _normalize_ast_value(equation),
                )
                for equation in fp.equations
            }.items()
        }
        variant_seqs.append(seqs)
        variant_eqs.append(eqs)

    seq_presence = set(variant_seqs[0].keys()) if variant_seqs else set()
    for seqs in variant_seqs[1:]:
        seq_presence &= set(seqs.keys())

    modified_sequences: dict[str, list[AstDiffDetail]] = {}
    common_seqs: list[str] = []
    for name in sorted(seq_presence):
        signatures = {
            index: seqs[name][1]
            for index, seqs in enumerate(variant_seqs, 1)
        }
        details = _diff_normalized_variants(signatures)
        if details:
            modified_sequences[variant_seqs[0][name][0]] = details
            continue
        common_seqs.append(variant_seqs[0][name][0])

    only_seqs = {
        index: [
            seqs[name][0]
            for name in sorted(set(seqs.keys()) - seq_presence)
        ]
        for index, seqs in enumerate(variant_seqs, 1)
    }

    eq_presence = set(variant_eqs[0].keys()) if variant_eqs else set()
    for eqs in variant_eqs[1:]:
        eq_presence &= set(eqs.keys())

    modified_equations: dict[str, list[AstDiffDetail]] = {}
    common_eqs: list[str] = []
    for name in sorted(eq_presence):
        signatures = {
            index: eqs[name][1]
            for index, eqs in enumerate(variant_eqs, 1)
        }
        details = _diff_normalized_variants(signatures)
        if details:
            modified_equations[variant_eqs[0][name][0]] = details
            continue
        common_eqs.append(variant_eqs[0][name][0])

    only_eqs = {
        index: [
            eqs[name][0]
            for name in sorted(set(eqs.keys()) - eq_presence)
        ]
        for index, eqs in enumerate(variant_eqs, 1)
    }

    return CodeDiff(
        sequences_common=common_seqs,
        sequences_only_in_variant=only_seqs,
        equations_common=common_eqs,
        equations_only_in_variant=only_eqs,
        modified_sequences=modified_sequences,
        modified_equations=modified_equations,
    )


def _hash_variable_list(variables: list[Variable]) -> int:
    """Create a hash representing the structure of a variable list."""
    parts = []
    for variable in variables:
        parts.append(
            (
                _normalize_name(variable.name),
                variable.datatype_text,
                variable.global_var,
                variable.const,
                variable.state,
                variable.opsave,
                variable.secure,
                repr(variable.init_value),
            )
        )
    return hash(tuple(sorted(parts)))


def _hash_parameter_mappings(mappings: list[ParameterMapping]) -> int:
    """Create a hash representing parameter mappings."""
    parts = []
    for mapping in mappings:
        target_str = (
            cast(str, mapping.target.get("var_name", ""))
            if isinstance(mapping.target, dict)
            else str(mapping.target)
        )
        source_str = None
        if mapping.source:
            source_str = (
                cast(str, mapping.source.get("var_name", ""))
                if isinstance(mapping.source, dict)
                else str(mapping.source)
            )
        parts.append(
            (
                _normalize_name(target_str),
                mapping.source_type,
                mapping.is_duration,
                mapping.is_source_global,
                _normalize_name(source_str) if source_str else None,
                repr(mapping.source_literal),
            )
        )
    return hash(tuple(sorted(parts)))


def _hash_submodules(
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance],
) -> int:
    """Create a hash representing the complete recursive submodule structure."""
    structure = _get_submodule_tree_structure(submodules)
    return hash(frozenset(structure))

def _hash_code(sequences: list[Sequence], equations: list[Equation]) -> int:
    """Create a hash representing code structure."""
    seq_parts = tuple(
        sorted(
            _code_entry_map(sequences).items(),
            key=lambda item: item[0],
        )
    )
    eq_parts = tuple(
        sorted(
            _code_entry_map(equations).items(),
            key=lambda item: item[0],
        )
    )
    return hash((seq_parts, eq_parts))


def create_fingerprint(module: SingleModule, path: list[str]) -> ModuleFingerprint:
    """Create a fingerprint for a SingleModule."""
    sequences = (
        module.modulecode.sequences
        if module.modulecode and module.modulecode.sequences
        else []
    )
    equations = (
        module.modulecode.equations
        if module.modulecode and module.modulecode.equations
        else []
    )

    return ModuleFingerprint(
        name=module.header.name,
        datecode=module.datecode,
        num_moduleparameters=len(module.moduleparameters),
        num_localvariables=len(module.localvariables),
        num_submodules=len(module.submodules),
        has_moduledef=module.moduledef is not None,
        has_modulecode=module.modulecode is not None,
        num_sequences=len(sequences),
        num_equations=len(equations),
        num_parameter_mappings=len(module.parametermappings),
        moduleparameters=module.moduleparameters,
        localvariables=module.localvariables,
        submodules=module.submodules,
        sequences=sequences,
        equations=equations,
        moduleparameters_hash=_hash_variable_list(module.moduleparameters),
        localvariables_hash=_hash_variable_list(module.localvariables),
        submodules_hash=_hash_submodules(module.submodules),
        parameter_mappings_hash=_hash_parameter_mappings(module.parametermappings),
        module=module,
        module_path=path.copy(),
    )


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

        path_with_current = current_path + [node_name]

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
        path_with_current = current_path + [node_name]

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
        path_with_current = current_path + [f"TypeDef:{node_name}"]

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
    instances_with_fps = [
        (path, create_fingerprint(m, path)) for path, m in modules_with_paths
    ]

    # Group by structural similarity (EXCLUDE datecode from key)
    variant_groups: dict[tuple, list[tuple[list[str], ModuleFingerprint]]] = (
        defaultdict(list)
    )
    for path, fp in instances_with_fps:
        key = (
            # REMOVED: fp.datecode
            fp.num_moduleparameters,
            fp.num_localvariables,
            fp.num_submodules,
            fp.num_sequences,
            fp.num_equations,
            fp.moduleparameters_hash,
            fp.localvariables_hash,
            fp.submodules_hash,
            fp.parameter_mappings_hash,
            _hash_code(fp.sequences, fp.equations),
        )
        variant_groups[key].append((path, fp))

    # Get one representative fingerprint per variant
    unique_fingerprints = [group[0][1] for group in variant_groups.values()]

    # Compute detailed diffs if there are multiple variants
    param_diff = None
    localvar_diff = None
    submodule_diff = None
    code_diff = None

    if len(unique_fingerprints) > 1:
        param_diff = _compare_variable_lists(unique_fingerprints)
        localvar_diff = _compare_variable_lists(unique_fingerprints, "localvariables")
        submodule_diff = _compare_submodules(unique_fingerprints)
        code_diff = _compare_code(unique_fingerprints)

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


def analyze_module_duplicates(
    base_picture: BasePicture, module_name: str, debug: bool = False
) -> ComparisonResult:
    """Main entry point: find and compare all SingleModules with the given name."""
    modules_with_paths = find_modules_by_name(base_picture, module_name, debug)
    return compare_modules(modules_with_paths)


def _is_from_root_origin(origin_file: str | None, root_origin: str | None) -> bool:
    if not origin_file:
        return True
    if not root_origin:
        return False
    return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()


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
            module_path = current_path + [node.header.name]
            if _is_from_root_origin(getattr(node, "origin_file", None), root_origin):
                grouped[_normalize_name(node.header.name)].append((module_path, node))
            for child in node.submodules or []:
                walk(child, module_path)
            return

        if isinstance(node, FrameModule):
            module_path = current_path + [node.header.name]
            for child in node.submodules or []:
                walk(child, module_path)
            return

        if isinstance(node, ModuleTypeDef):
            if not _is_from_root_origin(getattr(node, "origin_file", None), root_origin):
                return
            typedef_path = current_path + [f"TypeDef:{node.name}"]
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
                and _hash_code(fingerprint.sequences, fingerprint.equations)
                == _hash_code(unique_fingerprint.sequences, unique_fingerprint.equations)
            ):
                variant_map[index].append((path, fingerprint))
                break
    return dict(variant_map)


def _compact_diff(diff: VariableDiff | SubmoduleDiff | CodeDiff | None) -> dict[str, Any] | None:
    if diff is None:
        return None
    if isinstance(diff, VariableDiff):
        only = {
            variant_id: names
            for variant_id, names in diff.only_in_variant.items()
            if names
        }
        modified = {
            name: [detail.to_dict() for detail in details]
            for name, details in diff.modified.items()
            if details
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
            variant_id: [list(item) for item in items]
            for variant_id, items in diff.only_in_variant.items()
            if items
        }
        if not only_paths:
            return None
        return {
            "common": [list(item) for item in diff.common],
            "only_in_variant": only_paths,
        }
    if isinstance(diff, CodeDiff):
        sequences_only = {
            variant_id: names
            for variant_id, names in diff.sequences_only_in_variant.items()
            if names
        }
        equations_only = {
            variant_id: names
            for variant_id, names in diff.equations_only_in_variant.items()
            if names
        }
        modified_sequences = {
            name: [detail.to_dict() for detail in details]
            for name, details in diff.modified_sequences.items()
            if details
        }
        modified_equations = {
            name: [detail.to_dict() for detail in details]
            for name, details in diff.modified_equations.items()
            if details
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
    return None


def _format_variant_list(variant_ids: set[int]) -> str:
    return ", ".join(str(variant_id) for variant_id in sorted(variant_ids))


def _summarize_modified_item(
    label: str,
    item_name: str,
    details: list[AstDiffDetail],
) -> str:
    paths = ", ".join(detail.path for detail in details[:3])
    if len(details) > 3:
        paths = f"{paths}, ... (+{len(details) - 3} more)"
    variants = _format_variant_list(
        {
            variant_id
            for detail in details
            for variant_id in detail.variants
        }
    )
    return f"{label} {item_name!r} changed across variants {variants} at {paths}."


def _build_upgrade_notes(differences: dict[str, Any]) -> list[str]:
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
                notes.append(
                    f"{label}s only in variant {variant_id}: {', '.join(names)}."
                )
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
                notes.append(
                    f"Submodule structure differs in variant {variant_id}: {len(items)} unique node(s)."
                )

    return notes


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
    labels = []
    if "moduleparameters" in differences:
        labels.append("module parameters")
    if "localvariables" in differences:
        labels.append("local variables")
    if "submodules" in differences:
        labels.append("submodule structure")
    if "code" in differences:
        labels.append("module code")
    return labels


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
        key=lambda items: (_normalize_name(items[0][1].header.name), len(items)),
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
                module_path=_common_module_prefix(instance_paths)
                or [base_picture.header.name],
                data={
                    "module_name": comparison.module_name,
                    "total_found": comparison.total_found,
                    "unique_variants": comparison.unique_variants,
                    "variant_instance_paths": {
                        variant_id: [path for path, _fingerprint in entries]
                        for variant_id, entries in variant_map.items()
                    },
                    "material_differences": differences,
                    "upgrade_notes": _build_upgrade_notes(differences),
                    "location_preview": location_preview,
                },
            )
        )

    return VersionDriftReport(name=base_picture.header.name, issues=issues)

