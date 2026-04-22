"""User-editable graphics rules persisted as JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config as config_module

_SCHEMA_VERSION = 1
_ALLOWED_MODULE_KINDS = {
    "any",
    "single",
    "frame",
    "moduletype",
}
_MODULE_KIND_ALIASES = {
    "any": "any",
    "single": "single",
    "module": "single",
    "frame": "frame",
    "moduletype": "moduletype",
    "moduletype-instance": "moduletype",
}
_PATH_SELECTOR_FIELDS = (
    "relative_module_path",
    "unit_structure_path",
    "equipment_module_structure_path",
)

DEFAULT_GRAPHICS_RULES: dict[str, Any] = {
    "schema_version": _SCHEMA_VERSION,
    "rules": [],
}


@dataclass(frozen=True, slots=True)
class GraphicsRuleMismatch:
    field_path: str
    expected: Any
    actual: Any


@dataclass(frozen=True, slots=True)
class GraphicsRuleFinding:
    target_name: str
    module_path: str
    module_kind: str
    rule_name: str
    mismatches: tuple[GraphicsRuleMismatch, ...]


@dataclass(frozen=True, slots=True)
class GraphicsRulesCheckReport:
    target_name: str
    rules_path: Path
    configured_rule_count: int
    matched_rule_count: int
    checked_entry_count: int
    findings: tuple[GraphicsRuleFinding, ...]
    unmatched_rule_names: tuple[str, ...] = ()

    def summary(self) -> str:
        lines = [
            f"Configured rules : {self.configured_rule_count}",
            f"Matched rules    : {self.matched_rule_count}",
            f"Checked modules  : {self.checked_entry_count}",
            f"Not to spec      : {len(self.findings)}",
            f"Rules file       : {self.rules_path}",
        ]
        if self.unmatched_rule_names:
            lines.append("Unmatched rules  : " + ", ".join(self.unmatched_rule_names))

        for finding in self.findings:
            mismatch_text = "; ".join(
                f"{mismatch.field_path}: expected {mismatch.expected!r}, got {mismatch.actual!r}"
                for mismatch in finding.mismatches
            )
            lines.append(
                f"- {finding.module_path} [{finding.module_kind}] failed {finding.rule_name}: {mismatch_text}"
            )

        return "\n".join(lines)


def _normalize_module_kind(value: Any) -> str:
    raw = str(value or "").strip().lower()
    normalized = _MODULE_KIND_ALIASES.get(raw)
    if normalized is None:
        raise ValueError(
            "Unsupported graphics rule module_kind "
            f"{raw!r}; expected one of {sorted(_ALLOWED_MODULE_KINDS)}"
        )
    return normalized


def _normalized_rule_name(rule: dict[str, Any]) -> str:
    selector_text = ""
    if rule.get("unit_structure_path"):
        selector_text = f"unit:{rule['unit_structure_path']}"
    elif rule.get("equipment_module_structure_path"):
        selector_text = f"equipment:{rule['equipment_module_structure_path']}"
    elif rule.get("relative_module_path"):
        selector_text = f"path:{rule['relative_module_path']}"
    else:
        selector_text = rule["module_name"]

    if rule["module_kind"] == "moduletype":
        return f"moduletype:{rule['moduletype_name']}@{selector_text}"
    return f"{rule['module_kind']}:{selector_text}"


def _entry_rule_kind(entry: dict[str, Any]) -> str:
    return {
        "module": "single",
        "frame": "frame",
        "moduletype-instance": "moduletype",
    }.get(str(entry.get("module_kind", "")).strip().lower(), "")


def get_graphics_rules_path(config_path: Path | None = None) -> Path:
    return config_module.get_graphics_rules_path(config_path)


def _populated_path_selectors(rule: dict[str, Any]) -> list[tuple[str, str]]:
    selectors: list[tuple[str, str]] = []
    for field_name in _PATH_SELECTOR_FIELDS:
        value = str(rule.get(field_name) or "").strip()
        if value:
            selectors.append((field_name, value))
    return selectors


def _rule_selector_key(rule: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    return (
        str(rule.get("module_kind") or "").casefold(),
        str(rule.get("moduletype_name") or "").casefold(),
        str(rule.get("relative_module_path") or "").casefold(),
        str(rule.get("unit_structure_path") or "").casefold(),
        str(rule.get("equipment_module_structure_path") or "").casefold(),
        str(rule.get("module_name") or "").casefold(),
    )


def _normalize_rule(rule: Any) -> dict[str, Any]:
    if not isinstance(rule, dict):
        raise ValueError("Each graphics rule must be an object")

    module_name = str(rule.get("module_name") or rule.get("name") or "").strip()
    relative_module_path = str(rule.get("relative_module_path") or "").strip()
    unit_structure_path = str(rule.get("unit_structure_path") or "").strip()
    equipment_module_structure_path = str(
        rule.get("equipment_module_structure_path") or ""
    ).strip()
    moduletype_name = str(rule.get("moduletype_name") or "").strip()
    module_kind = _normalize_module_kind(rule.get("module_kind") or "any")
    populated_selectors = _populated_path_selectors(
        {
            "relative_module_path": relative_module_path,
            "unit_structure_path": unit_structure_path,
            "equipment_module_structure_path": equipment_module_structure_path,
        }
    )
    if len(populated_selectors) > 1:
        selector_names = ", ".join(name for name, _value in populated_selectors)
        raise ValueError(
            "Graphics rule must use only one selector path field; got: "
            f"{selector_names}"
        )

    if module_kind == "moduletype":
        if not moduletype_name:
            raise ValueError("Graphics moduletype rule is missing moduletype_name")
    elif module_kind != "any" and not populated_selectors and not module_name:
        raise ValueError(
            "Graphics single/frame rule must declare a selector path or module_name"
        )

    if not module_name:
        selector_value = populated_selectors[0][1] if populated_selectors else ""
        if selector_value:
            module_name = selector_value.split(".")[-1].strip()

    expected = rule.get("expected") or {}
    if not isinstance(expected, dict) or not expected:
        raise ValueError(f"Graphics rule {module_name!r} must declare a non-empty expected object")

    description = str(rule.get("description") or "").strip()
    return {
        "module_name": module_name,
        "module_kind": module_kind,
        "relative_module_path": relative_module_path,
        "unit_structure_path": unit_structure_path,
        "equipment_module_structure_path": equipment_module_structure_path,
        "moduletype_name": moduletype_name,
        "description": description,
        "expected": expected,
    }


def normalize_graphics_rules(raw_rules: Any) -> dict[str, Any]:
    if raw_rules is None:
        return {
            "schema_version": _SCHEMA_VERSION,
            "rules": [],
        }
    if not isinstance(raw_rules, dict):
        raise ValueError("Graphics rules JSON must be an object")

    schema_version = int(raw_rules.get("schema_version", _SCHEMA_VERSION))
    raw_rule_list = raw_rules.get("rules", [])
    if not isinstance(raw_rule_list, list):
        raise ValueError("Graphics rules JSON must contain a 'rules' array")

    return {
        "schema_version": schema_version,
        "rules": [_normalize_rule(rule) for rule in raw_rule_list],
    }


def load_graphics_rules(path: Path) -> tuple[dict[str, Any], bool]:
    if not path.exists():
        rules = normalize_graphics_rules(DEFAULT_GRAPHICS_RULES)
        save_graphics_rules(path, rules)
        return rules, True

    payload = json.loads(path.read_text(encoding="utf-8"))
    return normalize_graphics_rules(payload), False


def save_graphics_rules(path: Path, rules: dict[str, Any]) -> None:
    normalized = normalize_graphics_rules(rules)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def upsert_graphics_rule(rules: dict[str, Any], rule: dict[str, Any]) -> bool:
    normalized_rules = normalize_graphics_rules(rules)
    normalized_rule = _normalize_rule(rule)
    updated = False
    rule_list = list(normalized_rules["rules"])

    for index, existing in enumerate(rule_list):
        if _rule_selector_key(existing) == _rule_selector_key(normalized_rule):
            rule_list[index] = normalized_rule
            updated = True
            break
    else:
        rule_list.append(normalized_rule)

    rules.clear()
    rules.update(
        {
            "schema_version": normalized_rules["schema_version"],
            "rules": rule_list,
        }
    )
    return updated


def remove_graphics_rule(rules: dict[str, Any], index: int) -> dict[str, Any]:
    normalized_rules = normalize_graphics_rules(rules)
    if index < 0 or index >= len(normalized_rules["rules"]):
        raise IndexError("Graphics rule index out of range")

    removed = normalized_rules["rules"].pop(index)
    rules.clear()
    rules.update(normalized_rules)
    return removed


def _rule_matches_entry(rule: dict[str, Any], entry: dict[str, Any]) -> bool:
    if entry.get("module_kind") == "basepicture":
        return False

    module_kind = rule["module_kind"]
    if module_kind != "any" and _entry_rule_kind(entry) != module_kind:
        return False

    relative_module_path = str(rule.get("relative_module_path") or "").strip()
    if relative_module_path and entry.get("relative_module_path", "").casefold() != relative_module_path.casefold():
        return False

    unit_structure_path = str(rule.get("unit_structure_path") or "").strip()
    if unit_structure_path and entry.get("unit_structure_path", "").casefold() != unit_structure_path.casefold():
        return False

    equipment_module_structure_path = str(
        rule.get("equipment_module_structure_path") or ""
    ).strip()
    if equipment_module_structure_path and (
        entry.get("equipment_module_structure_path", "").casefold()
        != equipment_module_structure_path.casefold()
    ):
        return False

    if module_kind == "moduletype":
        expected_moduletype = str(rule.get("moduletype_name") or "").strip()
        if not expected_moduletype:
            return False
        actual_moduletype = str(
            entry.get("moduletype_name")
            or entry.get("resolved_moduletype", {}).get("name")
            or ""
        ).strip()
        return actual_moduletype.casefold() == expected_moduletype.casefold()

    if _populated_path_selectors(rule):
        return True

    if not rule["module_name"]:
        return True
    return entry.get("module_name", "").casefold() == rule["module_name"].casefold()


def _collect_mismatches(
    actual: Any,
    expected: Any,
    *,
    field_path: str,
    mismatches: list[GraphicsRuleMismatch],
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            mismatches.append(
                GraphicsRuleMismatch(
                    field_path=field_path,
                    expected=expected,
                    actual=actual,
                )
            )
            return
        for key, expected_value in expected.items():
            next_path = f"{field_path}.{key}" if field_path else key
            _collect_mismatches(
                actual.get(key),
                expected_value,
                field_path=next_path,
                mismatches=mismatches,
            )
        return

    if actual != expected:
        mismatches.append(
            GraphicsRuleMismatch(
                field_path=field_path,
                expected=expected,
                actual=actual,
            )
        )


def validate_graphics_layout_entries(
    entries: list[dict[str, Any]],
    rules: dict[str, Any],
    *,
    target_name: str,
    rules_path: Path,
) -> GraphicsRulesCheckReport:
    normalized_rules = normalize_graphics_rules(rules)
    findings: list[GraphicsRuleFinding] = []
    matched_rule_names: set[str] = set()

    for entry in entries:
        for rule in normalized_rules["rules"]:
            if not _rule_matches_entry(rule, entry):
                continue

            rule_name = _normalized_rule_name(rule)
            matched_rule_names.add(rule_name)
            mismatches: list[GraphicsRuleMismatch] = []
            _collect_mismatches(
                entry,
                {
                    "invocation": rule["expected"].get("invocation", {}),
                    "moduledef": rule["expected"].get("moduledef", {}),
                },
                field_path="",
                mismatches=mismatches,
            )
            mismatches = [
                mismatch
                for mismatch in mismatches
                if mismatch.field_path
            ]
            if not mismatches:
                continue

            findings.append(
                GraphicsRuleFinding(
                    target_name=target_name,
                    module_path=str(entry.get("module_path", "")),
                    module_kind=str(entry.get("module_kind", "")),
                    rule_name=rule_name,
                    mismatches=tuple(mismatches),
                )
            )

    unmatched_rule_names = sorted(
        _normalized_rule_name(rule)
        for rule in normalized_rules["rules"]
        if _normalized_rule_name(rule) not in matched_rule_names
    )
    checked_entry_count = sum(1 for entry in entries if entry.get("module_kind") != "basepicture")

    return GraphicsRulesCheckReport(
        target_name=target_name,
        rules_path=rules_path,
        configured_rule_count=len(normalized_rules["rules"]),
        matched_rule_count=len(matched_rule_names),
        checked_entry_count=checked_entry_count,
        findings=tuple(findings),
        unmatched_rule_names=tuple(unmatched_rule_names),
    )


__all__ = [
    "DEFAULT_GRAPHICS_RULES",
    "GraphicsRuleFinding",
    "GraphicsRuleMismatch",
    "GraphicsRulesCheckReport",
    "get_graphics_rules_path",
    "load_graphics_rules",
    "normalize_graphics_rules",
    "remove_graphics_rule",
    "save_graphics_rules",
    "upsert_graphics_rule",
    "validate_graphics_layout_entries",
]
