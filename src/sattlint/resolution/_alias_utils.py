from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sattline_parser.models.ast_model import Variable

from ..grammar import constants as const


def _string_object_mapping(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return None


def varname_base(var_dict_or_str: object) -> str | None:
    """Extract base variable name from a variable_name dict or string."""
    full = varname_full(var_dict_or_str)
    if full is None:
        return None
    base, _separator, _tail = full.partition(".")
    return base.casefold()


def varname_full(var_dict_or_str: object) -> str | None:
    """Extract full variable name from a variable_name dict or string."""
    if isinstance(var_dict_or_str, str):
        return var_dict_or_str
    mapping = _string_object_mapping(var_dict_or_str)
    if mapping is not None:
        value = mapping.get(const.KEY_VAR_NAME)
        if isinstance(value, str):
            return value
    return None


def find_all_aliases(
    target_var: Variable,
    alias_links: list[tuple[Variable, Variable, str]],
    debug: bool = False,
) -> list[tuple[Variable, str]]:
    """
    Given a target variable and the analyzer's alias links, find all variables
    that are transitively connected to it through parameter mappings.
    Returns list of (Variable, field_prefix_to_prepend) tuples.
    """
    aliases: list[tuple[Variable, str]] = []
    to_visit: list[tuple[Variable, str]] = [(target_var, "")]
    visited: list[tuple[Variable, str]] = []

    while to_visit:
        current, current_prefix = to_visit.pop()

        if any(current is variable for variable, _ in visited):
            continue

        visited.append((current, current_prefix))
        aliases.append((current, current_prefix))

        for parent, child, mapping_name in alias_links:
            if parent is current and not any(child is variable for variable, _ in visited):
                if current_prefix and mapping_name:
                    new_prefix = f"{current_prefix}.{mapping_name}"
                elif current_prefix:
                    new_prefix = current_prefix
                else:
                    new_prefix = mapping_name
                to_visit.append((child, new_prefix))

    return [(variable, prefix) for variable, prefix in aliases if variable is not target_var]


def find_all_aliases_upstream(
    target_var: Variable,
    alias_links: list[tuple[Variable, Variable, str]],
) -> list[tuple[Variable, str]]:
    """
    Find alias sources by walking parent links (child -> parent).
    Returns (parent_var, field_prefix_to_strip) tuples.
    """
    to_visit: list[tuple[Variable, str]] = [(target_var, "")]
    visited: list[tuple[Variable, str]] = []

    while to_visit:
        current, current_prefix = to_visit.pop()

        if any(current is variable and current_prefix == prefix for variable, prefix in visited):
            continue

        visited.append((current, current_prefix))

        for parent, child, mapping_name in alias_links:
            if child is current:
                if current_prefix and mapping_name:
                    new_prefix = f"{mapping_name}.{current_prefix}"
                elif mapping_name:
                    new_prefix = mapping_name
                else:
                    new_prefix = current_prefix
                to_visit.append((parent, new_prefix))

    return [(variable, prefix) for variable, prefix in visited if variable is not target_var]
