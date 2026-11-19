"""Variable usage bookkeeping copies caller-owned paths."""

from __future__ import annotations

from sattlint.models.usage import AccessKind, VariableUsage


def test_recorded_field_location_is_independent_of_the_caller_list() -> None:
    usage = VariableUsage()
    location = ["Root", "Unit"]

    usage.mark_field_read("Value", location)
    location.append("Changed")

    assert usage.field_reads["Value"] == [["Root", "Unit"]]


def test_recorded_field_write_is_independent_of_the_caller_list() -> None:
    usage = VariableUsage()
    location = ["Root", "Unit"]

    usage.mark_field_written("Value", location)
    location.append("Changed")

    assert usage.field_writes["Value"] == [["Root", "Unit"]]


def test_whole_variable_locations_carry_a_typed_access_kind() -> None:
    usage = VariableUsage()

    usage.mark_read(["Root"])
    usage.mark_written(["Root"])

    assert [kind for _path, kind in usage.usage_locations] == [AccessKind.READ, AccessKind.WRITE]
