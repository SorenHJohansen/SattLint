"""Call signature views build their parameter tuple once."""

from __future__ import annotations

from dataclasses import replace

from sattlint.core.call_signatures import CallParameter, resolve_call_signature


def test_parameters_are_a_stable_tuple_per_signature() -> None:
    signature = resolve_call_signature("abs")

    assert signature is not None
    assert signature.parameters is signature.parameters
    assert signature.parameters[0].direction == "in"


def test_parameter_direction_predicates_cover_every_direction() -> None:
    signature = resolve_call_signature("abs")
    assert signature is not None
    base = signature.parameters[0].builtin

    expected = {
        "in": (True, False),
        "in var": (True, False),
        "out": (False, True),
        "inout": (True, True),
    }
    for direction, (reads, writes) in expected.items():
        parameter = CallParameter(replace(base, direction=direction))
        assert parameter.is_input is reads
        assert parameter.is_output is writes
