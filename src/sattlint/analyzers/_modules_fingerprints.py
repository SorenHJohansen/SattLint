"""Fingerprint construction and structural hashing for module comparisons."""

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any, Literal, cast

from sattline_parser.models.ast_model import (
    Equation,
    FrameModule,
    ModuleTypeInstance,
    ParameterMapping,
    Sequence,
    SingleModule,
    Variable,
)

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
MISSING_AST_VALUE = object()

type NormalizedScalar = None | bool | int | float | str
type NormalizedEnumValue = tuple[str, NormalizedScalar]
type NormalizedFields = tuple[tuple[str, NormalizedValue], ...]
type NormalizedListValue = tuple[Literal["list"], tuple[NormalizedValue, ...]]
type NormalizedTupleValue = tuple[Literal["tuple"], tuple[NormalizedValue, ...]]
type NormalizedDictValue = tuple[Literal["dict"], NormalizedFields]
type NormalizedObjectValue = tuple[str, NormalizedFields]
type NormalizedTreeValue = tuple[str, object | None, tuple[NormalizedValue, ...]]
type NormalizedEntryMap = dict[str, NormalizedValue]
type NormalizedValue = (
    NormalizedScalar
    | NormalizedEnumValue
    | NormalizedListValue
    | NormalizedTupleValue
    | NormalizedDictValue
    | NormalizedObjectValue
    | NormalizedTreeValue
)
type NamedNormalizedValue = tuple[str, NormalizedValue]
type CodeEntryMap = dict[str, NamedNormalizedValue]
type VariantFingerprintKey = tuple[int, int, int, int, int, int, int, int, int, int]


def empty_fingerprints() -> list["ModuleFingerprint"]:
    return []


def empty_instance_fingerprints() -> list[tuple[list[str], "ModuleFingerprint"]]:
    return []


def _empty_str_list() -> list[str]:
    return []


def _sorted_object_items(mapping: dict[object, object]) -> list[tuple[str, object]]:
    return [(str(key), item) for key, item in sorted(mapping.items(), key=lambda pair: str(pair[0]))]


def _sorted_normalized_items(mapping: Mapping[str, NormalizedValue]) -> tuple[tuple[str, NormalizedValue], ...]:
    items = list(mapping.items())
    items.sort(key=lambda entry: entry[0])
    return tuple(items)


def _mapping_var_name(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        raw_name = cast(dict[object, object], value).get("var_name")
        return "" if raw_name is None else str(raw_name)
    return str(value)


def normalize_name(name: str) -> str:
    """Normalize a name for case-insensitive comparison."""
    return name.lower().strip()


def normalize_ast_value(value: Any) -> NormalizedValue:
    """Normalize AST-like values into stable, hashable tuples."""
    if value is None or isinstance(value, bool | int | float | str):
        return value

    if isinstance(value, Enum):
        enum_value = value.value
        if isinstance(enum_value, str):
            enum_value = enum_value.casefold()
        if enum_value is None or isinstance(enum_value, bool | int | float | str):
            return (type(value).__name__, enum_value)
        return (type(value).__name__, repr(enum_value))

    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        items: list[NamedNormalizedValue] = []
        for key, item in _sorted_object_items(mapping):
            if key in _IGNORED_AST_FIELDS:
                continue
            normalized = normalize_ast_value(item)
            if key in {"state", "var_name"} and isinstance(normalized, str):
                normalized = normalized.casefold()
            items.append((key, normalized))
        return ("dict", tuple(items))

    if isinstance(value, tuple):
        tuple_items = cast(tuple[object, ...], value)
        return ("tuple", tuple(normalize_ast_value(item) for item in tuple_items))

    if isinstance(value, list):
        list_items = cast(list[object], value)
        return ("list", tuple(normalize_ast_value(item) for item in list_items))

    if is_dataclass(value):
        items: list[NamedNormalizedValue] = []
        for field_info in fields(value):
            if field_info.name in _IGNORED_AST_FIELDS:
                continue
            normalized = normalize_ast_value(getattr(value, field_info.name))
            if field_info.name in {"name", "target", "type"} and isinstance(normalized, str):
                normalized = normalized.casefold()
            items.append((field_info.name, normalized))
        return (type(value).__name__, tuple(items))

    if hasattr(value, "data") and hasattr(value, "children"):
        raw_children = cast(object, getattr(value, "children", []))
        children: tuple[NormalizedValue, ...] = ()
        if isinstance(raw_children, list | tuple):
            children = tuple(
                normalize_ast_value(child) for child in cast(list[object] | tuple[object, ...], raw_children)
            )
        return (
            type(value).__name__,
            cast(object | None, getattr(value, "data", None)),
            children,
        )

    if hasattr(value, "__dict__"):
        items: list[NamedNormalizedValue] = []
        attrs = cast(dict[str, object], vars(value))
        for key, item in sorted(attrs.items()):
            if key.startswith("_") or key in _IGNORED_AST_FIELDS:
                continue
            items.append((key, normalize_ast_value(item)))
        return (type(value).__name__, tuple(items))

    return repr(value)


def _code_entry_map(items: list[Sequence] | list[Equation]) -> NormalizedEntryMap:
    """Map case-insensitive names to normalized structural signatures."""
    entries: NormalizedEntryMap = {}
    for item in items:
        entries[normalize_name(item.name)] = normalize_ast_value(item)
    return entries


def get_submodule_tree_structure(
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance],
    depth: int = 0,
    max_depth: int = 10,
) -> set[tuple[int, str, str]]:
    """Recursively extract a normalized submodule tree structure."""
    if depth > max_depth:
        return set()

    structure: set[tuple[int, str, str]] = set()
    for submodule in submodules:
        name = normalize_name(submodule.header.name)

        if isinstance(submodule, SingleModule):
            structure.add((depth, name, "Single"))
            structure.update(get_submodule_tree_structure(submodule.submodules, depth + 1, max_depth))
            continue

        if isinstance(submodule, FrameModule):
            structure.add((depth, name, "Frame"))
            structure.update(get_submodule_tree_structure(submodule.submodules, depth + 1, max_depth))
            continue

        structure.add((depth, name, f"Instance:{normalize_name(submodule.moduletype_name)}"))

    return structure


def _hash_variable_list(variables: list[Variable]) -> int:
    """Create a hash representing the structure of a variable list."""
    parts: list[tuple[object, ...]] = []
    for variable in variables:
        parts.append(
            (
                normalize_name(variable.name),
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
    parts: list[tuple[object, ...]] = []
    for mapping in mappings:
        target = cast(object, mapping.target)
        source = cast(object, mapping.source)
        target_str = _mapping_var_name(target) or ""
        source_str = _mapping_var_name(source)
        parts.append(
            (
                normalize_name(target_str),
                mapping.source_type,
                mapping.is_duration,
                mapping.is_source_global,
                normalize_name(source_str) if source_str else None,
                repr(mapping.source_literal),
            )
        )
    return hash(tuple(sorted(parts)))


def _hash_submodules(submodules: list[SingleModule | FrameModule | ModuleTypeInstance]) -> int:
    """Create a hash representing the complete recursive submodule structure."""
    structure = get_submodule_tree_structure(submodules)
    return hash(frozenset(structure))


def _hash_code(sequences: list[Sequence], equations: list[Equation]) -> int:
    """Create a hash representing code structure."""
    seq_parts = _sorted_normalized_items(_code_entry_map(sequences))
    eq_parts = _sorted_normalized_items(_code_entry_map(equations))
    return hash((seq_parts, eq_parts))


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
    moduleparameters: list[Variable]
    localvariables: list[Variable]
    submodules: list[SingleModule | FrameModule | ModuleTypeInstance]
    sequences: list[Sequence]
    equations: list[Equation]
    moduleparameters_hash: int
    localvariables_hash: int
    submodules_hash: int
    parameter_mappings_hash: int
    module: SingleModule
    module_path: list[str] = field(default_factory=_empty_str_list)


def create_fingerprint(module: SingleModule, path: list[str]) -> ModuleFingerprint:
    """Create a fingerprint for a SingleModule."""
    sequences = module.modulecode.sequences if module.modulecode and module.modulecode.sequences else []
    equations = module.modulecode.equations if module.modulecode and module.modulecode.equations else []

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


def fingerprint_variant_key(fingerprint: ModuleFingerprint) -> VariantFingerprintKey:
    return (
        fingerprint.num_moduleparameters,
        fingerprint.num_localvariables,
        fingerprint.num_submodules,
        fingerprint.num_sequences,
        fingerprint.num_equations,
        fingerprint.moduleparameters_hash,
        fingerprint.localvariables_hash,
        fingerprint.submodules_hash,
        fingerprint.parameter_mappings_hash,
        _hash_code(fingerprint.sequences, fingerprint.equations),
    )


def fingerprints_match(left: ModuleFingerprint, right: ModuleFingerprint) -> bool:
    return fingerprint_variant_key(left) == fingerprint_variant_key(right)
