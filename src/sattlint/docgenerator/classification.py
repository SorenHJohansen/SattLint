from __future__ import annotations

import re
from dataclasses import dataclass

from .. import config as config_module
from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleCode,
    ModuleTypeDef,
    ModuleTypeInstance,
    ParameterMapping,
    SingleModule,
    Variable,
)
from ..resolution.common import format_moduletype_label, path_startswith_casefold, resolve_moduletype_def_strict

type DocumentableNode = SingleModule | FrameModule | ModuleTypeInstance
DOCUMENTATION_CATEGORY_ORDER = [
    "em",
    "ops",
    "rp",
    "ep",
    "up",
]
_DOCUMENTATION_WRAPPER_SEGMENTS = {
    "display",
    "equipmodpanel",
    "epdisp",
    "form",
    "l1",
    "l2",
    "logic",
    "mes_statecontrol",
    "operations",
    "oprframe",
    "oprmodule",
    "panel",
    "report",
    "rpdisp",
    "startupanel",
    "statecontrol",
    "transfersetups",
    "trend",
    "unitcontrol",
    "updisp",
}
_DOCUMENTATION_PARAMETER_PREFIXES = {
    "rp": ("rp_", "recpar"),
    "ep": ("ep_", "engpar"),
    "up": ("up_", "usrpar"),
}


@dataclass(frozen=True)
class DocumentedModule:
    node: DocumentableNode
    path: tuple[str, ...]
    kind: str
    current_library: str | None
    resolved_moduletype: ModuleTypeDef | None
    moduleparameters: tuple[Variable, ...]
    localvariables: tuple[Variable, ...]
    parametermappings: tuple[ParameterMapping, ...]
    modulecode: ModuleCode | None

    @property
    def name(self) -> str:
        return self.node.header.name

    @property
    def moduletype_name(self) -> str | None:
        if self.resolved_moduletype is not None:
            return self.resolved_moduletype.name
        if isinstance(self.node, ModuleTypeInstance):
            return self.node.moduletype_name
        return None

    @property
    def moduletype_label(self) -> str | None:
        if self.resolved_moduletype is not None:
            return format_moduletype_label(self.resolved_moduletype)
        return self.moduletype_name

    @property
    def short_path(self) -> str:
        if not self.path:
            return ""
        if len(self.path) <= 1:
            return ".".join(self.path)
        return ".".join(self.path[1:])


@dataclass
class DocumentationScope:
    mode: str = "all"
    roots: list[DocumentedModule] | None = None
    requested_values: list[str] | None = None
    unmatched_values: list[str] | None = None


@dataclass
class DocumentationClassification:
    section_order: list[str]
    categories: dict[str, list[DocumentedModule]]
    uncategorized: list[DocumentedModule]
    all_entries: list[DocumentedModule]
    scope: DocumentationScope | None = None

    def descendants(
        self,
        entry: DocumentedModule,
        *,
        category: str | None = None,
    ) -> list[DocumentedModule]:
        pool = self.categories.get(category, []) if category else self.all_entries
        return [
            candidate
            for candidate in pool
            if candidate.path != entry.path and path_startswith_casefold(list(candidate.path), list(entry.path))
        ]


def classify_documentation_structure(
    base_picture: BasePicture,
    documentation_config: dict | None = None,
    *,
    unavailable_libraries: set[str] | None = None,
) -> DocumentationClassification:
    doc_cfg = config_module.get_documentation_config(documentation_config)
    section_order = DOCUMENTATION_CATEGORY_ORDER.copy()
    rules = doc_cfg.get("classifications", {})

    entries = _collect_documented_modules(
        base_picture,
        unavailable_libraries=unavailable_libraries,
    )
    categories = {
        name: _collect_category_entries(
            name,
            rules.get(name, {}),
            entries,
        )
        for name in section_order
    }
    uncategorized: list[DocumentedModule] = []

    for entry in entries:
        if not any(entry.path == candidate.path for items in categories.values() for candidate in items):
            uncategorized.append(entry)

    classification = DocumentationClassification(
        section_order=section_order,
        categories=categories,
        uncategorized=uncategorized,
        all_entries=entries,
    )
    return _apply_documentation_scope(classification, doc_cfg)


def discover_documentation_unit_candidates(
    classification: DocumentationClassification,
) -> list[DocumentedModule]:
    categorized_paths = {
        entry.path
        for category in (
            "em",
            "ops",
            "rp",
            "ep",
            "up",
        )
        for entry in classification.categories.get(category, [])
    }

    candidates = [
        entry for entry in classification.all_entries if _looks_like_unit_root(entry, classification, categorized_paths)
    ]
    if candidates:
        return candidates

    fallback = [
        entry
        for entry in classification.all_entries
        if entry.path not in categorized_paths
        and not _looks_like_wrapper_entry(entry)
        and (classification.descendants(entry, category="em") or classification.descendants(entry, category="ops"))
        and entry.moduletype_name not in {"RecPar", "EngPar", "UsrPar"}
    ]
    if fallback:
        return fallback

    return [
        entry
        for entry in classification.all_entries
        if len(entry.path) == 2
        and entry.path not in categorized_paths
        and entry.moduletype_name not in {"RecPar", "EngPar", "UsrPar"}
    ]


def document_scope_summary(entry: DocumentedModule, classification: DocumentationClassification) -> dict[str, int]:
    return {
        "ops": len(classification.descendants(entry, category="ops")),
        "em": len(classification.descendants(entry, category="em")),
        "rp": len(classification.descendants(entry, category="rp")),
        "ep": len(classification.descendants(entry, category="ep")),
        "up": len(classification.descendants(entry, category="up")),
    }


def _apply_documentation_scope(
    classification: DocumentationClassification,
    documentation_config: dict,
) -> DocumentationClassification:
    scope = _resolve_documentation_scope(classification, documentation_config)
    if not scope.roots:
        classification.scope = scope
        return classification

    def in_scope(entry: DocumentedModule) -> bool:
        return any(path_startswith_casefold(list(entry.path), list(root.path)) for root in scope.roots or [])

    root_paths = {root.path for root in scope.roots or []}
    filtered_categories = {
        category: [entry for entry in entries if in_scope(entry)]
        for category, entries in classification.categories.items()
    }
    filtered_uncategorized = [
        entry for entry in classification.uncategorized if in_scope(entry) and entry.path not in root_paths
    ]
    filtered_all_entries = [entry for entry in classification.all_entries if in_scope(entry)]

    return DocumentationClassification(
        section_order=classification.section_order,
        categories=filtered_categories,
        uncategorized=filtered_uncategorized,
        all_entries=filtered_all_entries,
        scope=scope,
    )


def _resolve_documentation_scope(
    classification: DocumentationClassification,
    documentation_config: dict,
) -> DocumentationScope:
    units = documentation_config.get("units", {})
    if not isinstance(units, dict):
        return DocumentationScope(mode="all", roots=[])

    mode = str(units.get("mode", "all")).strip().lower() or "all"
    candidates = discover_documentation_unit_candidates(classification)

    if mode == "all":
        return DocumentationScope(mode=mode, roots=[], requested_values=[], unmatched_values=[])

    if mode == "instance_paths":
        requested_values = _normalize_requested_values(units.get("instance_paths", []))
        roots, unmatched = _resolve_scope_paths(candidates, requested_values)
        return DocumentationScope(
            mode=mode,
            roots=roots,
            requested_values=requested_values,
            unmatched_values=unmatched,
        )

    if mode == "moduletype_names":
        requested_values = _normalize_requested_values(units.get("moduletype_names", []))
        requested_cf = {value.casefold() for value in requested_values}
        roots = [candidate for candidate in candidates if (candidate.moduletype_name or "").casefold() in requested_cf]
        matched_types = {(candidate.moduletype_name or "").casefold() for candidate in roots}
        unmatched = [value for value in requested_values if value.casefold() not in matched_types]
        return DocumentationScope(
            mode=mode,
            roots=roots,
            requested_values=requested_values,
            unmatched_values=unmatched,
        )

    return DocumentationScope(mode="all", roots=[], requested_values=[], unmatched_values=[])


def _normalize_requested_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _resolve_scope_paths(
    candidates: list[DocumentedModule],
    requested_values: list[str],
) -> tuple[list[DocumentedModule], list[str]]:
    exact_path_map = {".".join(candidate.path).casefold(): candidate for candidate in candidates}
    short_path_map = {candidate.short_path.casefold(): candidate for candidate in candidates}
    by_name: dict[str, list[DocumentedModule]] = {}
    for documented in candidates:
        by_name.setdefault(documented.name.casefold(), []).append(documented)

    roots: list[DocumentedModule] = []
    unmatched: list[str] = []
    seen_paths: set[tuple[str, ...]] = set()

    for requested in requested_values:
        key = requested.casefold()
        requested_candidate: DocumentedModule | None = exact_path_map.get(key) or short_path_map.get(key)
        if requested_candidate is None:
            name_matches = by_name.get(key, [])
            if len(name_matches) == 1:
                requested_candidate = name_matches[0]
        if requested_candidate is None:
            unmatched.append(requested)
            continue
        if requested_candidate.path in seen_paths:
            continue
        roots.append(requested_candidate)
        seen_paths.add(requested_candidate.path)

    return roots, unmatched


def _collect_documented_modules(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
) -> list[DocumentedModule]:
    entries: list[DocumentedModule] = []

    def walk(
        children: list[DocumentableNode] | None,
        parent_path: list[str],
        current_library: str | None,
        typedef_stack: set[tuple[str, str]],
    ) -> None:
        for child in children or []:
            child_path = [*parent_path, child.header.name]
            if isinstance(child, SingleModule):
                entries.append(
                    DocumentedModule(
                        node=child,
                        path=tuple(child_path),
                        kind="single_module",
                        current_library=current_library,
                        resolved_moduletype=None,
                        moduleparameters=tuple(child.moduleparameters or []),
                        localvariables=tuple(child.localvariables or []),
                        parametermappings=tuple(child.parametermappings or []),
                        modulecode=child.modulecode,
                    )
                )
                walk(child.submodules or [], child_path, current_library, typedef_stack)
                continue

            if isinstance(child, FrameModule):
                entries.append(
                    DocumentedModule(
                        node=child,
                        path=tuple(child_path),
                        kind="frame_module",
                        current_library=current_library,
                        resolved_moduletype=None,
                        moduleparameters=(),
                        localvariables=(),
                        parametermappings=(),
                        modulecode=child.modulecode,
                    )
                )
                walk(child.submodules or [], child_path, current_library, typedef_stack)
                continue

            resolved = _resolve_instance_moduletype(
                base_picture,
                child,
                current_library=current_library,
                unavailable_libraries=unavailable_libraries,
            )
            entries.append(
                DocumentedModule(
                    node=child,
                    path=tuple(child_path),
                    kind="moduletype_instance",
                    current_library=current_library,
                    resolved_moduletype=resolved,
                    moduleparameters=tuple(resolved.moduleparameters or []) if resolved else (),
                    localvariables=tuple(resolved.localvariables or []) if resolved else (),
                    parametermappings=tuple(child.parametermappings or []),
                    modulecode=resolved.modulecode if resolved else None,
                )
            )
            if resolved is None:
                continue

            signature = (
                (resolved.origin_lib or current_library or "").casefold(),
                resolved.name.casefold(),
            )
            if signature in typedef_stack:
                continue
            walk(
                resolved.submodules or [],
                child_path,
                resolved.origin_lib or current_library,
                typedef_stack | {signature},
            )

    walk(
        base_picture.submodules or [],
        [base_picture.header.name],
        base_picture.origin_lib,
        set(),
    )
    return entries


def _resolve_instance_moduletype(
    base_picture: BasePicture,
    instance: ModuleTypeInstance,
    *,
    current_library: str | None,
    unavailable_libraries: set[str] | None,
) -> ModuleTypeDef | None:
    try:
        return resolve_moduletype_def_strict(
            base_picture,
            instance.moduletype_name,
            current_library=current_library,
            unavailable_libraries=unavailable_libraries,
        )
    except ValueError:
        return None


def _matches_rule(
    entry: DocumentedModule,
    rule: dict,
    entries: list[DocumentedModule],
) -> bool:
    direct_name_patterns = _rule_list(rule, "name_contains")
    direct_label_patterns = _rule_list(rule, "label_equals")
    descendant_name_patterns = _rule_list(rule, "desc_name_contains")
    descendant_label_patterns = _rule_list(rule, "desc_label_equals")

    if not any(
        (
            direct_name_patterns,
            direct_label_patterns,
            descendant_name_patterns,
            descendant_label_patterns,
        )
    ):
        return False

    return bool(_matches_direct(entry, name_contains=direct_name_patterns, label_equals=direct_label_patterns))


def _matches_direct(
    entry: DocumentedModule,
    *,
    name_contains: list[str],
    label_equals: list[str],
) -> bool:
    moduletype_name = entry.moduletype_name or ""
    moduletype_label = entry.moduletype_label or ""

    if name_contains and _contains_pattern(moduletype_name, name_contains):
        return True
    return bool(label_equals and _equals_pattern(moduletype_label, label_equals))


def _contains_pattern(text: str, patterns: list[str]) -> bool:
    text_cf = text.casefold()
    return any(pattern.casefold() in text_cf for pattern in patterns if pattern)


def _equals_pattern(text: str, patterns: list[str]) -> bool:
    text_variants = _label_variants(text)
    for pattern in patterns:
        if not pattern:
            continue
        if text_variants & _label_variants(pattern):
            return True
    return False


def _rule_list(rule: dict, key: str) -> list[str]:
    values = rule.get(key, []) if isinstance(rule, dict) else []
    return [str(value) for value in values if str(value).strip()]


def _descendants_of(
    entry: DocumentedModule,
    entries: list[DocumentedModule],
) -> list[DocumentedModule]:
    return [
        candidate
        for candidate in entries
        if candidate.path != entry.path and path_startswith_casefold(list(candidate.path), list(entry.path))
    ]


def _has_descendant_marker_match(
    entry: DocumentedModule,
    entries: list[DocumentedModule],
    *,
    name_contains: list[str],
    label_equals: list[str],
) -> bool:
    return any(
        _matches_direct(
            descendant,
            name_contains=name_contains,
            label_equals=label_equals,
        )
        for descendant in _descendants_of(entry, entries)
    )


def _collect_category_entries(
    category: str,
    rule: dict,
    entries: list[DocumentedModule],
) -> list[DocumentedModule]:
    direct_name_patterns = _rule_list(rule, "name_contains")
    direct_label_patterns = _rule_list(rule, "label_equals")
    descendant_name_patterns = _rule_list(rule, "desc_name_contains")
    descendant_label_patterns = _rule_list(rule, "desc_label_equals")
    entry_lookup = {entry.path: entry for entry in entries}

    collected: list[DocumentedModule] = [
        entry
        for entry in entries
        if _matches_direct(
            entry,
            name_contains=direct_name_patterns,
            label_equals=direct_label_patterns,
        )
    ]

    if descendant_name_patterns or descendant_label_patterns:
        for marker in entries:
            if not _matches_direct(
                marker,
                name_contains=descendant_name_patterns,
                label_equals=descendant_label_patterns,
            ):
                continue
            anchor = _marker_anchor(
                marker,
                entry_lookup,
            )
            if anchor is not None:
                collected.append(anchor)

    collected.extend(entry for entry in entries if _matches_category_heuristic(entry, category))
    return _unique_documented_modules(collected)


def _marker_anchor(
    marker: DocumentedModule,
    entry_lookup: dict[tuple[str, ...], DocumentedModule],
) -> DocumentedModule | None:
    for depth in range(len(marker.path) - 1, 1, -1):
        ancestor = entry_lookup.get(marker.path[:depth])
        if ancestor is None:
            continue
        if _looks_like_wrapper_entry(ancestor):
            continue
        return ancestor
    return entry_lookup.get(marker.path[:-1])


def _matches_category_heuristic(entry: DocumentedModule, category: str) -> bool:
    if category == "em":
        return _looks_like_equipment_module(entry)
    if category == "ops":
        return _looks_like_operation(entry)
    if category in _DOCUMENTATION_PARAMETER_PREFIXES:
        return _looks_like_parameter(entry, prefixes=_DOCUMENTATION_PARAMETER_PREFIXES[category])
    return False


def _looks_like_equipment_module(entry: DocumentedModule) -> bool:
    if _looks_like_wrapper_entry(entry):
        return False
    name_cf = entry.name.casefold()
    moduletype_name = (entry.moduletype_name or "").casefold()
    if "coordinate" in name_cf or "coordinate" in moduletype_name:
        return False
    if name_cf.startswith("em_"):
        return True
    return "equipmod" in moduletype_name


def _looks_like_operation(entry: DocumentedModule) -> bool:
    if _looks_like_wrapper_entry(entry):
        return False
    if len(entry.path) < 2:
        return False
    if entry.path[-2].casefold() != "oprframe":
        return False
    return not entry.name.casefold().startswith("mes_")


def _looks_like_parameter(entry: DocumentedModule, *, prefixes: tuple[str, ...]) -> bool:
    if _looks_like_wrapper_entry(entry):
        return False
    name_cf = entry.name.casefold()
    moduletype_name = (entry.moduletype_name or "").casefold()
    return any(name_cf.startswith(prefix) or prefix in moduletype_name for prefix in prefixes)


def _looks_like_unit_root(
    entry: DocumentedModule,
    classification: DocumentationClassification,
    categorized_paths: set[tuple[str, ...]],
) -> bool:
    if entry.path in categorized_paths:
        return False
    if _looks_like_wrapper_entry(entry):
        return False
    if not (classification.descendants(entry, category="em") or classification.descendants(entry, category="ops")):
        return False

    parameter_names = {variable.name.casefold() for variable in entry.moduleparameters}
    if {"name", "medianame", "headername"} & parameter_names:
        return True
    if "sectionname" in parameter_names:
        return True
    return bool(entry.moduletype_name and len(entry.path) <= 3)


def _looks_like_wrapper_entry(entry: DocumentedModule) -> bool:
    return any(
        _looks_like_wrapper_name(value)
        for value in (
            entry.name,
            entry.moduletype_name or "",
            entry.moduletype_label or "",
        )
        if value
    )


def _looks_like_wrapper_name(value: str) -> bool:
    value_cf = value.casefold()
    if value_cf in _DOCUMENTATION_WRAPPER_SEGMENTS:
        return True
    if ":" in value_cf and value_cf.split(":", 1)[-1] in _DOCUMENTATION_WRAPPER_SEGMENTS:
        return True
    return re.fullmatch(r"l\d+", value_cf) is not None


def _label_variants(text: str) -> set[str]:
    text_cf = text.casefold().strip()
    if not text_cf:
        return set()
    variants = {text_cf}
    if ":" in text_cf:
        variants.add(text_cf.split(":", 1)[-1])
    return variants


def _unique_documented_modules(entries: list[DocumentedModule]) -> list[DocumentedModule]:
    unique: list[DocumentedModule] = []
    seen_paths: set[tuple[str, ...]] = set()
    for entry in entries:
        if entry.path in seen_paths:
            continue
        unique.append(entry)
        seen_paths.add(entry.path)
    return unique
