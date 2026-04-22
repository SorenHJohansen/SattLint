from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)
from .framework import Issue, format_report_header

SUPPORTED_NAMING_STYLES: tuple[str, ...] = (
    "infer",
    "pascal",
    "camel",
    "snake",
    "upper_snake",
    "lower",
    "upper",
)

_SEPARATOR_RE = re.compile(r"[_\-]")
_LOWER_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*$")
_PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_CAMEL_RE = re.compile(r"^[a-z][A-Za-z0-9]*$")
_LOWER_RE = re.compile(r"^[a-z][a-z0-9]*$")
_UPPER_RE = re.compile(r"^[A-Z][A-Z0-9]*$")

_SYMBOL_KIND_LABELS = {
    "variable": "Variables",
    "module": "Modules",
    "instance": "Instances",
}
_RULE_KEYS = {
    "variable": "variables",
    "module": "modules",
    "instance": "instances",
}


@dataclass(frozen=True)
class NamingRule:
    style: str = "infer"
    allow: tuple[str, ...] = ()

    @property
    def allowed_names(self) -> set[str]:
        return {name.casefold() for name in self.allow}


@dataclass(frozen=True)
class NamingDeclaration:
    symbol_kind: str
    name: str
    module_path: tuple[str, ...]


@dataclass
class NamingConsistencyReport:
    name: str
    issues: list[Issue] = field(default_factory=list)

    def summary(self) -> str:
        if not self.issues:
            lines = format_report_header("Naming consistency", self.name, status="ok")
            lines.append("No naming consistency issues found.")
            return "\n".join(lines)

        lines = format_report_header("Naming consistency", self.name, status="issues")
        lines.append(f"Issues: {len(self.issues)}")
        lines.append("")
        lines.append("Kinds:")
        kind_counts = Counter(
            str((issue.data or {}).get("symbol_kind", "unknown"))
            for issue in self.issues
        )
        for symbol_kind in ("variable", "module", "instance"):
            count = kind_counts.get(symbol_kind, 0)
            if count:
                lines.append(f"  - {_SYMBOL_KIND_LABELS[symbol_kind]}: {count}")

        lines.append("")
        lines.append("Findings:")
        for issue in self.issues:
            location = ".".join(issue.module_path or [self.name])
            lines.append(f"  - [{location}] {issue.message}")
        return "\n".join(lines)


def _normalize_rule(raw: object) -> NamingRule:
    if not isinstance(raw, dict):
        return NamingRule()

    style = str(raw.get("style", "infer")).strip().lower() or "infer"
    if style not in SUPPORTED_NAMING_STYLES:
        style = "infer"

    allow_raw = raw.get("allow", [])
    allow: list[str] = []
    if isinstance(allow_raw, list):
        for item in allow_raw:
            if not isinstance(item, str):
                continue
            value = item.strip()
            if value and value.casefold() not in {entry.casefold() for entry in allow}:
                allow.append(value)

    return NamingRule(style=style, allow=tuple(allow))


def get_configured_naming_rules(config: dict[str, Any] | None) -> dict[str, NamingRule]:
    defaults = {
        "variables": NamingRule(),
        "modules": NamingRule(),
        "instances": NamingRule(),
    }
    if not isinstance(config, dict):
        return defaults

    analysis = config.get("analysis", {})
    if not isinstance(analysis, dict):
        return defaults

    naming = analysis.get("naming", {})
    if not isinstance(naming, dict):
        return defaults

    return {
        key: _normalize_rule(naming.get(key, {}))
        for key in defaults
    }


def _identifier_style(name: str) -> str:
    if not name:
        return "unknown"
    if _SEPARATOR_RE.search(name):
        if _LOWER_SNAKE_RE.fullmatch(name):
            return "snake"
        if _UPPER_SNAKE_RE.fullmatch(name):
            return "upper_snake"
        return "unknown"
    if _PASCAL_RE.fullmatch(name):
        if any(ch.islower() for ch in name[1:]) or len(name) == 1:
            return "pascal"
        if name[1:].isdigit():
            return "pascal"
    if _CAMEL_RE.fullmatch(name):
        if any(ch.isupper() for ch in name[1:]):
            return "camel"
        return "lower"
    if _LOWER_RE.fullmatch(name):
        return "lower"
    if _UPPER_RE.fullmatch(name):
        return "upper"
    return "unknown"


def _infer_expected_style(
    declarations: list[NamingDeclaration],
    rule: NamingRule,
) -> str | None:
    if rule.style != "infer":
        return rule.style

    style_counts: Counter[str] = Counter()
    seen_names: set[str] = set()
    for declaration in declarations:
        normalized_name = declaration.name.casefold()
        if normalized_name in rule.allowed_names or normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)

        style = _identifier_style(declaration.name)
        if style in {"infer", "unknown"}:
            continue
        style_counts[style] += 1

    if not style_counts:
        return None

    best_count = max(style_counts.values())
    winners = sorted(
        style
        for style, count in style_counts.items()
        if count == best_count
    )
    if len(winners) != 1:
        return None
    return winners[0]


class NamingConsistencyAnalyzer:
    def __init__(
        self,
        base_picture: BasePicture,
        *,
        rules: dict[str, NamingRule] | None = None,
    ) -> None:
        self.bp = base_picture
        self.rules = rules or {
            "variables": NamingRule(),
            "modules": NamingRule(),
            "instances": NamingRule(),
        }
        self._issues: list[Issue] = []
        self._declarations: list[NamingDeclaration] = []

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    def run(self) -> list[Issue]:
        root_path = [self.bp.header.name]
        self._collect_variables(self.bp.localvariables or [], root_path)
        self._walk_modules(self.bp.submodules or [], root_path)

        for moduletype in self.bp.moduletype_defs or []:
            if not self._is_from_root_origin(getattr(moduletype, "origin_file", None)):
                continue
            moduletype_path = [self.bp.header.name, f"TypeDef:{moduletype.name}"]
            self._collect_module_name(moduletype.name, moduletype_path)
            self._collect_variables(
                [*(moduletype.moduleparameters or []), *(moduletype.localvariables or [])],
                moduletype_path,
            )
            self._walk_modules(moduletype.submodules or [], moduletype_path)

        self._emit_inconsistencies()
        return self._issues

    def _walk_modules(
        self,
        modules: list[SingleModule | FrameModule | ModuleTypeInstance],
        parent_path: list[str],
    ) -> None:
        for module in modules:
            child_path = [*parent_path, module.header.name]
            if isinstance(module, SingleModule):
                self._collect_module_name(module.header.name, child_path)
                self._collect_variables(
                    [*(module.moduleparameters or []), *(module.localvariables or [])],
                    child_path,
                )
                self._walk_modules(module.submodules or [], child_path)
                continue

            if isinstance(module, FrameModule):
                self._collect_module_name(module.header.name, child_path)
                self._walk_modules(module.submodules or [], child_path)
                continue

            self._declarations.append(
                NamingDeclaration(
                    symbol_kind="instance",
                    name=module.header.name,
                    module_path=tuple(child_path),
                )
            )

    def _collect_module_name(self, name: str, module_path: list[str]) -> None:
        self._declarations.append(
            NamingDeclaration(
                symbol_kind="module",
                name=name,
                module_path=tuple(module_path),
            )
        )

    def _collect_variables(self, variables: list[Variable], module_path: list[str]) -> None:
        for variable in variables:
            self._declarations.append(
                NamingDeclaration(
                    symbol_kind="variable",
                    name=variable.name,
                    module_path=tuple(module_path),
                )
            )

    def _emit_inconsistencies(self) -> None:
        declarations_by_kind: dict[str, list[NamingDeclaration]] = defaultdict(list)
        for declaration in self._declarations:
            declarations_by_kind[declaration.symbol_kind].append(declaration)

        for symbol_kind, declarations in declarations_by_kind.items():
            rule = self.rules.get(_RULE_KEYS[symbol_kind], NamingRule())
            expected_style = _infer_expected_style(declarations, rule)
            if expected_style is None:
                continue

            allowed_names = rule.allowed_names
            for declaration in declarations:
                if declaration.name.casefold() in allowed_names:
                    continue
                actual_style = _identifier_style(declaration.name)
                if actual_style == expected_style:
                    continue
                self._issues.append(
                    Issue(
                        kind="naming.inconsistent_style",
                        message=(
                            f"{symbol_kind.title()} name {declaration.name!r} uses {actual_style} style, "
                            f"but {symbol_kind} names are expected to use {expected_style} style."
                        ),
                        module_path=list(declaration.module_path),
                        data={
                            "symbol_kind": symbol_kind,
                            "name": declaration.name,
                            "actual_style": actual_style,
                            "expected_style": expected_style,
                        },
                    )
                )

    def _is_from_root_origin(self, origin_file: str | None) -> bool:
        if not origin_file:
            return True
        root_origin = getattr(self.bp, "origin_file", None)
        if not root_origin:
            return False
        return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()


def analyze_naming_consistency(
    base_picture: BasePicture,
    *,
    rules: dict[str, NamingRule] | None = None,
) -> NamingConsistencyReport:
    analyzer = NamingConsistencyAnalyzer(base_picture, rules=rules)
    return NamingConsistencyReport(name=base_picture.header.name, issues=analyzer.run())
