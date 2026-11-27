# pyright: reportPrivateUsage=false
"""Symbol invalidation keeps the state map's copy-on-write contract cheap."""

from __future__ import annotations

from sattlint.analyzers.dataflow._dataflow_common import INITIALIZED
from sattlint.analyzers.dataflow._dataflow_state import _DataflowStateMixin

SymbolKey = tuple[str, ...]


def _state() -> dict[SymbolKey, object]:
    return {
        ("root", "counter"): INITIALIZED,
        ("root", "counter", "value"): 3,
        ("root", "started"): True,
    }


def test_invalidation_drops_the_symbol_and_its_fields() -> None:
    mixin = _DataflowStateMixin()
    state = _state()

    result = mixin._invalidate_symbol(state, ("root", "counter"))

    assert result == {("root", "started"): True}
    assert state == _state()


def test_invalidation_leaves_unrelated_symbols_alone() -> None:
    mixin = _DataflowStateMixin()
    state = _state()

    result = mixin._invalidate_symbol(state, ("root", "absent"))

    assert result == state


def test_invalidation_without_a_match_shares_the_state() -> None:
    """The common case: a write to a symbol this state never recorded.

    Copying hundreds of tracked symbols to remove nothing dominated the analyzer's
    run time, so an unchanged map is returned as-is.
    """
    mixin = _DataflowStateMixin()
    state = _state()

    assert mixin._invalidate_symbol(state, ("root", "absent")) is state


def test_write_invalidation_always_returns_a_private_map() -> None:
    mixin = _DataflowStateMixin()
    state = _state()

    result = mixin._invalidate_symbol_for_write(state, ("root", "absent"))

    assert result is not state
    assert result == state
    result[("root", "written")] = INITIALIZED
    assert ("root", "written") not in state


def test_write_invalidation_does_not_share_a_matched_state() -> None:
    mixin = _DataflowStateMixin()
    state = _state()

    result = mixin._invalidate_symbol_for_write(state, ("root", "counter"))

    assert result == {("root", "started"): True}
    result[("root", "counter")] = INITIALIZED
    assert ("root", "counter") in state


def test_batch_invalidation_drops_every_listed_symbol_and_its_fields() -> None:
    mixin = _DataflowStateMixin()
    state = _state() | {("root", "other"): INITIALIZED, ("root", "other", "flag"): False}

    result = mixin._invalidate_symbols(state, [("root", "counter"), ("root", "other")])

    assert result == {("root", "started"): True}
    assert state == _state() | {("root", "other"): INITIALIZED, ("root", "other", "flag"): False}


def test_batch_invalidation_matches_a_symbol_named_like_a_prefix_segment() -> None:
    """A key must not match through a shorter path that only shares a segment."""
    mixin = _DataflowStateMixin()
    state = {("root", "counter", "state"): INITIALIZED, ("root", "counter"): INITIALIZED}

    result = mixin._invalidate_symbols(state, [("root", "count")])

    assert result == state


def test_batch_invalidation_without_a_match_shares_the_state() -> None:
    mixin = _DataflowStateMixin()
    state = _state()

    assert mixin._invalidate_symbols(state, [("root", "absent"), ("root", "alsoAbsent")]) is state


def test_batch_invalidation_with_no_keys_shares_the_state() -> None:
    mixin = _DataflowStateMixin()
    state = _state()

    assert mixin._invalidate_symbols(state, []) is state


def test_an_empty_key_never_clears_the_state() -> None:
    """A symbol key always names a variable, so an empty key is not a wildcard."""
    mixin = _DataflowStateMixin()
    state = _state()

    assert mixin._invalidate_symbols(state, [()]) is state
