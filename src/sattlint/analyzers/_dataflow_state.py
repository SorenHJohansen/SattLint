from __future__ import annotations

from typing import Any, cast

from lark import Tree

from sattline_parser.models.ast_model import Variable

from ..grammar import constants as const
from ..resolution.scope import ScopeContext
from ._dataflow_common import _INITIALIZED, _UNKNOWN, ScalarValue, StateMap, _PendingWrite, _ResolvedRef


class _DataflowStateMixin:
    def _collect_stateful_refs(
        self: Any,
        expr: Any,
        context: ScopeContext,
    ) -> list[_ResolvedRef]:
        collected: list[_ResolvedRef] = []

        def visit(node: Any) -> None:
            if isinstance(node, dict) and const.KEY_VAR_NAME in node:
                resolved = self._resolve_ref(node, context)
                if resolved is not None and resolved.is_state_variable:
                    collected.append(resolved)
                return

            if isinstance(node, Tree) and node.data == const.KEY_STATEMENT:
                for child in node.children:
                    visit(child)
                return

            if isinstance(node, tuple):
                for item in node:
                    visit(item)
                return

            if isinstance(node, list):
                for item in node:
                    visit(item)
                return

            if hasattr(node, "children"):
                for child in getattr(node, "children", []):
                    visit(child)

        visit(expr)
        return collected

    def _apply_write_target(
        self: Any,
        resolved: _ResolvedRef,
        value: ScalarValue | object,
        state: StateMap,
        *,
        module_path: list[str],
        treat_as_root_overwrite: bool = False,
    ) -> StateMap:
        if resolved.state_access == "old":
            self._report_invalid_old_write(resolved, module_path, operation="assignment target")
            return state

        next_state = state.copy()
        whole_symbol_write = treat_as_root_overwrite or resolved.symbol_key == resolved.symbol_root_key

        if whole_symbol_write:
            overwritten = self._pop_pending_writes_for_root(next_state, resolved.symbol_root_key)
            for pending in overwritten:
                self._report_dead_overwrite(pending, resolved, module_path)
        else:
            next_state.pop(self._pending_state_key(resolved.symbol_root_key), None)
            pending_key = self._pending_state_key(resolved.symbol_key)
            pending_write = next_state.pop(pending_key, None)
            if isinstance(pending_write, _PendingWrite):
                self._report_dead_overwrite(pending_write, resolved, module_path)

        next_state = self._invalidate_symbol(next_state, resolved.symbol_root_key)
        next_state[resolved.symbol_key] = _INITIALIZED if value is _UNKNOWN else value
        next_state[self._pending_state_key(resolved.symbol_key)] = _PendingWrite(
            key=resolved.symbol_key,
            root_key=resolved.symbol_root_key,
            display_name=resolved.base_display_name,
            sites=(self._site_str(),),
        )
        return next_state

    def _has_pending_write_for_symbol(
        self: Any,
        state: StateMap,
        resolved: _ResolvedRef,
    ) -> bool:
        for pending in state.values():
            if not isinstance(pending, _PendingWrite):
                continue
            if pending.root_key != resolved.symbol_root_key:
                continue
            if pending.key in {resolved.symbol_key, resolved.symbol_root_key}:
                return True
        return False

    def _consume_pending_reads(
        self: Any,
        state: StateMap,
        root_key: tuple[str, ...],
    ) -> None:
        for pending_key in [
            key
            for key, pending in state.items()
            if self._is_pending_state_key(key) and isinstance(pending, _PendingWrite) and pending.root_key == root_key
        ]:
            state.pop(pending_key, None)

    def _pop_pending_writes_for_root(
        self: Any,
        state: StateMap,
        root_key: tuple[str, ...],
    ) -> list[_PendingWrite]:
        popped: list[_PendingWrite] = []
        for pending_key in [
            key
            for key, pending in state.items()
            if self._is_pending_state_key(key) and isinstance(pending, _PendingWrite) and pending.root_key == root_key
        ]:
            pending = state.pop(pending_key, None)
            if isinstance(pending, _PendingWrite):
                popped.append(pending)
        return popped

    def _seed_state(
        self: Any,
        state: StateMap,
        module_path: list[str],
        variables: list[Variable],
    ) -> StateMap:
        next_state = state.copy()
        for variable in variables:
            current_key = self._state_key(module_path, variable.name, "")
            old_key = self._old_state_key(current_key)
            value = self._static_literal(variable.init_value)
            if value is _UNKNOWN:
                if variable.init_value is None:
                    continue
                next_state[current_key] = _INITIALIZED
                next_state[old_key] = _INITIALIZED
                continue
            next_state[current_key] = value
            next_state[old_key] = value
        return next_state

    def _invalidate_symbol(
        self: Any,
        state: StateMap,
        key: tuple[str, ...],
    ) -> StateMap:
        next_state = state.copy()
        prefixes = [existing for existing in next_state if existing[: len(key)] == key]
        for existing in prefixes:
            next_state.pop(existing, None)
        return next_state

    def _merge_states(self: Any, states: list[StateMap]) -> StateMap:
        if not states:
            return {}
        merged: StateMap = {}
        value_keys: set[tuple[str, ...]] = set().union(
            *({key for key in state if not self._is_pending_state_key(key)} for state in states)
        )
        pending_keys_per_state = [{key for key in state if self._is_pending_state_key(key)} for state in states]
        for key in value_keys:
            values = [state.get(key, _UNKNOWN) for state in states]
            first = values[0]
            if first is _UNKNOWN:
                continue
            if all(value == first for value in values[1:]):
                merged[key] = first
                continue
            if all(value is not _UNKNOWN for value in values):
                merged[key] = _INITIALIZED

        common_pending_keys = set.intersection(*pending_keys_per_state) if pending_keys_per_state else set()
        for pending_key in common_pending_keys:
            pending_values = [state.get(pending_key) for state in states]
            if not all(isinstance(value, _PendingWrite) for value in pending_values):
                continue
            first_pending = cast(_PendingWrite, pending_values[0])
            merged[pending_key] = _PendingWrite(
                key=first_pending.key,
                root_key=first_pending.root_key,
                display_name=first_pending.display_name,
                sites=tuple(
                    sorted(
                        {site for value in pending_values if isinstance(value, _PendingWrite) for site in value.sites}
                    )
                ),
            )
        return merged


DataflowStateMixin = _DataflowStateMixin
