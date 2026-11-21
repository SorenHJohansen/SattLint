"""String datatype capacities as a required part of the project configuration.

The capacities are a language fact, not an analyzer knob: they feed string
inference, string validation, and the analysis cache key. Every `.slproj` states
them explicitly, so a project never inherits a hidden default at load time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypedDict, cast

STRING_CAPACITY_KEYS: tuple[str, ...] = (
    "identstring",
    "tagstring",
    "string",
    "linestring",
    "maxstring",
)
_STRING_CAPACITY_KEYS_TEXT = ", ".join(STRING_CAPACITY_KEYS)


class StringCapacitiesDict(TypedDict):
    identstring: int
    tagstring: int
    string: int
    linestring: int
    maxstring: int


@dataclass(frozen=True, slots=True)
class StringCapacities:
    """The fixed capacity of each SattLine string datatype."""

    identstring: int
    tagstring: int
    string: int
    linestring: int
    maxstring: int

    def as_dict(self) -> StringCapacitiesDict:
        return {
            "identstring": self.identstring,
            "tagstring": self.tagstring,
            "string": self.string,
            "linestring": self.linestring,
            "maxstring": self.maxstring,
        }


STANDARD_STRING_CAPACITIES = StringCapacities(
    identstring=15,
    tagstring=30,
    string=40,
    linestring=80,
    maxstring=140,
)


@dataclass(frozen=True, slots=True)
class StringCapacityProblem:
    """One reason a ``[string_capacities]`` table is unusable.

    ``key`` is the offending subkey, or an empty string when the table itself is
    wrong. Callers turn it into a key path and the message into user output.
    """

    key: str
    message: str


def standard_string_capacities_dict() -> StringCapacitiesDict:
    """A fresh standard table, safe to place in a shared defaults mapping."""
    return STANDARD_STRING_CAPACITIES.as_dict()


def string_capacity_problems(table: object, *, location: str) -> tuple[StringCapacityProblem, ...]:
    """Every problem with a ``[string_capacities]`` table, in declaration order."""
    if not isinstance(table, Mapping):
        return (
            StringCapacityProblem(
                key="",
                message=(
                    f"Invalid [string_capacities] table in {location}: expected {_STRING_CAPACITY_KEYS_TEXT} "
                    "as positive integers."
                ),
            ),
        )

    mapping = cast(Mapping[object, object], table)
    problems: list[StringCapacityProblem] = []
    for raw_key in mapping:
        if isinstance(raw_key, str) and raw_key in STRING_CAPACITY_KEYS:
            continue
        problems.append(
            StringCapacityProblem(
                key=str(raw_key),
                message=(
                    f"Unknown [string_capacities] key {raw_key!r} in {location}. "
                    f"Expected one of: {_STRING_CAPACITY_KEYS_TEXT}."
                ),
            )
        )

    for key in STRING_CAPACITY_KEYS:
        if key not in mapping:
            problems.append(
                StringCapacityProblem(
                    key=key,
                    message=(
                        f"Missing required [string_capacities] key {key!r} in {location}. "
                        f"Declare {_STRING_CAPACITY_KEYS_TEXT} as positive integers."
                    ),
                )
            )
            continue
        value = mapping[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            problems.append(
                StringCapacityProblem(
                    key=key,
                    message=(
                        f"Invalid [string_capacities] value for {key!r} in {location}: expected a positive integer."
                    ),
                )
            )

    return tuple(problems)


def validate_string_capacities(table: object, *, location: str) -> StringCapacities:
    """Return the typed table, or raise ``ValueError`` naming the first problem."""
    problems = string_capacity_problems(table, location=location)
    if problems:
        raise ValueError(problems[0].message)

    mapping = cast(Mapping[str, object], table)
    return StringCapacities(
        identstring=cast(int, mapping["identstring"]),
        tagstring=cast(int, mapping["tagstring"]),
        string=cast(int, mapping["string"]),
        linestring=cast(int, mapping["linestring"]),
        maxstring=cast(int, mapping["maxstring"]),
    )


def resolve_string_capacities(config: Mapping[str, object] | None) -> StringCapacities:
    """Resolve the capacities carried by a config mapping.

    A mapping without the table is a context that has no project behind it (a
    focused analyzer test), so it resolves to the standard values. A table that
    is present is validated strictly; project loading rejects a malformed table
    before a real analysis ever reaches this function.
    """
    if config is None:
        return STANDARD_STRING_CAPACITIES
    table = config.get("string_capacities")
    if table is None:
        return STANDARD_STRING_CAPACITIES
    return validate_string_capacities(table, location="the effective configuration")


__all__ = [
    "STANDARD_STRING_CAPACITIES",
    "STRING_CAPACITY_KEYS",
    "StringCapacities",
    "StringCapacitiesDict",
    "StringCapacityProblem",
    "resolve_string_capacities",
    "standard_string_capacities_dict",
    "string_capacity_problems",
    "validate_string_capacities",
]
