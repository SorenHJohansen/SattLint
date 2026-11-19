"""Call signature views build their parameter tuple once."""

from __future__ import annotations

from sattlint.core.call_signatures import resolve_call_signature


def test_parameters_are_a_stable_tuple_per_signature() -> None:
    signature = resolve_call_signature("abs")

    assert signature is not None
    assert signature.parameters is signature.parameters
    assert signature.parameters[0].direction == "in"
