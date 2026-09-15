"""Unsafe boolean-default collection inside the variables analyzer."""

from __future__ import annotations

import re
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FrameModule,
    ModuleTypeInstance,
    SingleModule,
    Variable,
)

from ...config.analysis import unsafe_default_tokens
from ...reporting.variables_report import IssueKind, VariableIssue
from ...utils.casefolding import casefold_equal, casefold_key
from ..shared._walk_utils import iter_nested_modules

_IDENTIFIER_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")

_UNSAFE_DEFAULT_REASONS: dict[str, str] = {
    "bypass": "which can bypass safety checks from startup",
    "enable": "which can activate equipment or logic from startup",
}
_DEFAULT_UNSAFE_DEFAULT_REASON = "which starts enabled at startup"


def collect_unsafe_default_issues(self: Any) -> None:
    """Append ``IssueKind.UNSAFE_BOOLEAN_DEFAULT`` issues for unsafe True defaults."""
    if getattr(self, "_limit_to_module_path", None) is not None:
        return

    tokens = unsafe_default_tokens(getattr(self, "_config", None))
    bp = cast(BasePicture, self.bp)
    root_path = [bp.header.name]
    _check_unsafe_defaults(self, root_path, bp.localvariables, tokens)
    _walk_nested_modules(self, bp.submodules or [], root_path, tokens)

    for moduletype in bp.moduletype_defs or []:
        if not self._is_from_root_origin(
            getattr(moduletype, "origin_file", None),
            getattr(moduletype, "origin_lib", None),
        ):
            continue
        typedef_path = [*root_path, f"TypeDef:{moduletype.name}"]
        _check_unsafe_defaults(self, typedef_path, moduletype.moduleparameters, tokens)
        _check_unsafe_defaults(self, typedef_path, moduletype.localvariables, tokens)
        _walk_nested_modules(self, moduletype.submodules or [], typedef_path, tokens)


def _walk_nested_modules(
    self: Any,
    children: list[SingleModule | FrameModule | ModuleTypeInstance],
    parent_path: list[str],
    tokens: tuple[str, ...],
) -> None:
    for child, child_path in iter_nested_modules(children, parent_path=parent_path):
        if not isinstance(child, SingleModule):
            continue
        _check_unsafe_defaults(self, child_path, child.moduleparameters, tokens)
        _check_unsafe_defaults(self, child_path, child.localvariables, tokens)


def _check_unsafe_defaults(
    self: Any,
    module_path: list[str],
    variables: list[Variable] | None,
    tokens: tuple[str, ...],
) -> None:
    for variable in variables or []:
        reason = _unsafe_default_reason(variable, tokens)
        if reason is None:
            continue
        issue = VariableIssue(
            kind=IssueKind.UNSAFE_BOOLEAN_DEFAULT,
            module_path=module_path.copy(),
            variable=variable,
            role=f"defaults to True, {reason}",
            site=".".join(module_path),
            context=f"{variable.name} = TRUE",
        )
        self._append_issue(issue)


def _unsafe_default_reason(variable: Variable, tokens: tuple[str, ...]) -> str | None:
    if variable.init_value is not True:
        return None
    if not casefold_equal(variable.datatype_text, "boolean"):
        return None

    variable_tokens = _identifier_tokens(variable.name)
    for token in tokens:
        normalized_token = casefold_key(token)
        if normalized_token in variable_tokens:
            return _UNSAFE_DEFAULT_REASONS.get(normalized_token, _DEFAULT_UNSAFE_DEFAULT_REASON)
    return None


def _identifier_tokens(name: str) -> tuple[str, ...]:
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", name) if part]
    tokens: list[str] = []
    for part in parts:
        matches = _IDENTIFIER_TOKEN_RE.findall(part)
        if matches:
            tokens.extend(casefold_key(match) for match in matches)
        else:
            tokens.append(casefold_key(part))
    return tuple(tokens)


__all__ = ["_identifier_tokens", "collect_unsafe_default_issues"]
