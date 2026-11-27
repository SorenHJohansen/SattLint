"""String mapping validation resolves capacities from the project configuration."""

from __future__ import annotations

from sattline_parser.models.ast_model import ScalarDatatype, Variable

from sattlint.analyzers.shared._validators import StringMappingValidator
from sattlint.config.string_capacities import STANDARD_STRING_CAPACITIES, StringCapacities


def _string_capacities(*, string_capacity: int) -> StringCapacities:
    return StringCapacities(
        identstring=STANDARD_STRING_CAPACITIES.identstring,
        tagstring=STANDARD_STRING_CAPACITIES.tagstring,
        string=string_capacity,
        linestring=STANDARD_STRING_CAPACITIES.linestring,
        maxstring=STANDARD_STRING_CAPACITIES.maxstring,
    )


def test_standard_capacity_allows_a_tagstring_to_string_mapping() -> None:
    validator = StringMappingValidator(STANDARD_STRING_CAPACITIES)

    issues = validator.check_string_mapping(
        Variable(name="Target", datatype=ScalarDatatype.STRING),
        Variable(name="Source", datatype=ScalarDatatype.TAGSTRING),
        ["Root"],
    )

    assert issues == []


def test_a_tighter_string_capacity_makes_the_same_mapping_narrow() -> None:
    validator = StringMappingValidator(_string_capacities(string_capacity=20))

    issues = validator.check_string_mapping(
        Variable(name="Target", datatype=ScalarDatatype.STRING),
        Variable(name="Source", datatype=ScalarDatatype.TAGSTRING),
        ["Root"],
    )

    assert len(issues) == 1
    assert issues[0].context is not None
    assert "Target (string, 20 characters)" in issues[0].context
    assert "Source (tagstring, 30 characters)" in issues[0].context


def test_standard_capacity_allows_a_25_character_literal_mapping() -> None:
    validator = StringMappingValidator(STANDARD_STRING_CAPACITIES)

    issues = validator.check_string_literal_mapping(
        Variable(name="Target", datatype=ScalarDatatype.STRING),
        "x" * 25,
        ["Root"],
    )

    assert issues == []


def test_a_20_character_string_rejects_the_same_literal() -> None:
    validator = StringMappingValidator(_string_capacities(string_capacity=20))

    issues = validator.check_string_literal_mapping(
        Variable(name="Target", datatype=ScalarDatatype.STRING),
        "x" * 25,
        ["Root"],
    )

    assert len(issues) == 1
    assert issues[0].context is not None
    assert "Target (string, 20 characters)" in issues[0].context
