from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from sattline_parser.models.ast_model import (
    BasePicture,
    FloatLiteral,
    IntLiteral,
    SFCFork,
)
from sattline_parser.utils import formatter as formatter_module

from ..grammar import constants as const
from ..resolution.scope import ScopeContext
from ._dataflow_common import (
    INITIALIZED,
    OLD_PREFIX,
    PENDING_PREFIX,
    UNKNOWN,
    PendingWrite,
    ResolvedRef,
    ScalarValue,
    StateMap,
)
from ._dataflow_conditions import DataflowConditionMixin
from ._dataflow_state import DataflowStateMixin
from ._dataflow_traversal import DataflowTraversalMixin
from .framework import Issue, SimpleReport
from .sattline_builtins import get_function_signature

_FORMAT_EXPR_ATTR = "format_expr"
_format_expr = cast(Callable[[Any], object], getattr(formatter_module, _FORMAT_EXPR_ATTR))


class DataflowAnalyzer(DataflowTraversalMixin, DataflowConditionMixin, DataflowStateMixin):
    _analyzed_target_is_library: bool

    def __init__(
        self,
        base_picture: BasePicture,
        unavailable_libraries: set[str] | None = None,
        analyzed_target_is_library: bool = False,
    ) -> None:
        self.bp = base_picture
        self._unavailable_libraries = unavailable_libraries or set()
        self._analyzed_target_is_library = analyzed_target_is_library
        self._issues: list[Issue] = []
        self._final_root_state: StateMap = {}
        self._site_stack: list[str] = []
        self._active_typedefs: set[str] = set()
        self._reported_read_before_write: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_dead_overwrite: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_scan_cycle_stale_read: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_scan_cycle_implicit_new: set[tuple[tuple[str, ...], str, str]] = set()
        self._reported_scan_cycle_temporal_misuse: set[tuple[tuple[str, ...], str, str, str]] = set()

    @property
    def issues(self) -> list[Issue]:
        return self._issues

    def _apply_call_side_effects(
        self,
        function_name: str | None,
        args: list[Any],
        context: ScopeContext,
        state: StateMap,
    ) -> StateMap:
        if not function_name:
            return state

        signature = get_function_signature(function_name)
        if signature is None:
            return state

        next_state = state.copy()
        for index, argument in enumerate(args):
            direction = "in"
            if index < len(signature.parameters):
                direction = signature.parameters[index].direction
            if direction not in {"out", "inout"}:
                continue
            resolved = self._resolve_ref(argument, context)
            if resolved is None:
                continue
            if resolved.state_access == "old":
                self._report_invalid_old_write(
                    resolved,
                    context.module_path,
                    operation=f"{direction} parameter",
                )
                continue
            next_state = self._apply_write_target(
                resolved,
                UNKNOWN,
                next_state,
                module_path=context.module_path,
                treat_as_root_overwrite=True,
            )
        return next_state

    def _write_target(
        self,
        target: Any,
        value: ScalarValue | object,
        context: ScopeContext,
        state: StateMap,
    ) -> StateMap:
        resolved = self._resolve_ref(target, context)
        if resolved is None:
            return state

        return self._apply_write_target(
            resolved,
            value,
            state,
            module_path=context.module_path,
        )

    def _read_resolved_value(
        self,
        resolved: ResolvedRef,
        module_path: list[str],
        state: StateMap,
    ) -> ScalarValue | object:
        if resolved.state_access != "old":
            self._consume_pending_reads(state, resolved.symbol_root_key)
        value = state.get(resolved.key, UNKNOWN)
        if value is UNKNOWN and resolved.key != resolved.root_key:
            value = state.get(resolved.root_key, UNKNOWN)

        if value is UNKNOWN:
            self._report_read_before_write(resolved, module_path)
            return UNKNOWN

        if value is INITIALIZED:
            return UNKNOWN

        return value

    def _report_read_before_write(
        self,
        resolved: ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if dedupe_key in self._reported_read_before_write:
            return
        self._reported_read_before_write.add(dedupe_key)
        self._add_issue(
            kind="dataflow.read_before_write",
            message=(f"Variable reference {resolved.display_name!r} may be read before it is assigned on this path."),
            module_path=module_path,
            data={
                "symbol": resolved.display_name,
                "site": site,
            },
        )

    def _report_dead_overwrite(
        self,
        pending: PendingWrite,
        resolved: ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, pending.display_name.casefold())
        if dedupe_key in self._reported_dead_overwrite:
            return
        self._reported_dead_overwrite.add(dedupe_key)
        self._add_issue(
            kind="dataflow.dead_overwrite",
            message=(f"Variable reference {pending.display_name!r} is overwritten before its previous value is read."),
            module_path=module_path,
            data={
                "symbol": pending.display_name,
                "site": site,
                "previous_sites": list(pending.sites),
                "overwrite_symbol": resolved.display_name,
            },
        )

    def _report_scan_cycle_stale_read(
        self,
        resolved: ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if dedupe_key in self._reported_scan_cycle_stale_read:
            return
        self._reported_scan_cycle_stale_read.add(dedupe_key)
        self._add_issue(
            kind="dataflow.scan_cycle_stale_read",
            message=(
                f"State reference {resolved.display_name!r} is read after {resolved.base_display_name!r} "
                "was already written earlier in the same scan; :OLD still refers to the previous scan value."
            ),
            module_path=module_path,
            data={
                "symbol": resolved.display_name,
                "state_symbol": resolved.base_display_name,
                "site": site,
            },
        )

    def _report_scan_cycle_implicit_new(
        self,
        resolved: ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if dedupe_key in self._reported_scan_cycle_implicit_new:
            return
        self._reported_scan_cycle_implicit_new.add(dedupe_key)
        self._add_issue(
            kind="dataflow.scan_cycle_implicit_new",
            message=(
                f"State reference {resolved.display_name!r} is read after {resolved.base_display_name!r} "
                "was already written earlier in the same scan; use :NEW to make the immediate-update dependency explicit."
            ),
            module_path=module_path,
            data={
                "symbol": resolved.display_name,
                "state_symbol": resolved.base_display_name,
                "site": site,
            },
        )

    def _report_invalid_old_write(
        self,
        resolved: ResolvedRef,
        module_path: list[str],
        *,
        operation: str,
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold(), operation)
        if dedupe_key in self._reported_scan_cycle_temporal_misuse:
            return
        self._reported_scan_cycle_temporal_misuse.add(dedupe_key)
        self._add_issue(
            kind="dataflow.scan_cycle_temporal_misuse",
            message=(
                f"State reference {resolved.display_name!r} cannot be written via {operation}; "
                ":OLD is read-only and always refers to the previous scan."
            ),
            module_path=module_path,
            data={
                "symbol": resolved.display_name,
                "state_symbol": resolved.base_display_name,
                "operation": operation,
                "site": site,
            },
        )

    def _report_expression_temporal_hazards(
        self,
        expr: Any,
        context: ScopeContext,
        module_path: list[str],
        state: StateMap,
    ) -> None:
        accesses = self._collect_stateful_refs(expr, context)
        if not accesses:
            return

        grouped: dict[tuple[str, ...], dict[str, list[ResolvedRef]]] = {}
        for resolved in accesses:
            group = grouped.setdefault(
                resolved.symbol_key,
                {"old": [], "explicit_new": [], "implicit_current": []},
            )
            if resolved.state_access == "old":
                group["old"].append(resolved)
            elif resolved.state_access == "new":
                group["explicit_new"].append(resolved)
            else:
                group["implicit_current"].append(resolved)

        for group in grouped.values():
            sample = next(
                iter(group["old"] or group["explicit_new"] or group["implicit_current"]),
                None,
            )
            if sample is None:
                continue
            if not self._has_pending_write_for_symbol(state, sample):
                continue
            for resolved in group["implicit_current"]:
                self._report_scan_cycle_implicit_new(resolved, module_path)
            if group["old"] and not group["explicit_new"] and not group["implicit_current"]:
                for resolved in group["old"]:
                    self._report_scan_cycle_stale_read(resolved, module_path)

    def _resolve_ref(self, expr: Any, context: ScopeContext) -> ResolvedRef | None:
        if not (isinstance(expr, dict) and const.KEY_VAR_NAME in expr):
            return None
        expr_map = cast(dict[str, object], expr)
        full_name = expr_map.get(const.KEY_VAR_NAME)
        if not isinstance(full_name, str):
            return None
        variable, field_path, decl_path, _decl_display_path = context.resolve_variable(full_name)
        if variable is None:
            return None
        raw_state_access = expr_map.get("state")
        state_access = raw_state_access if isinstance(raw_state_access, str) else None
        symbol_key = self._state_key(decl_path, variable.name, field_path)
        symbol_root_key = self._state_key(decl_path, variable.name, "")
        key = symbol_key
        root_key = symbol_root_key
        if state_access == "old":
            key = self._old_state_key(symbol_key)
            root_key = self._old_state_key(symbol_root_key)
        display_name = full_name if not state_access else f"{full_name}:{state_access.title()}"
        return ResolvedRef(
            key=key,
            root_key=root_key,
            symbol_key=symbol_key,
            symbol_root_key=symbol_root_key,
            display_name=display_name,
            base_display_name=full_name,
            state_access=state_access,
            is_state_variable=bool(variable.state),
        )

    def _compare_values(self, left: ScalarValue, operator: str, right: ScalarValue) -> bool | None:
        try:
            if operator == "==":
                return left == right
            if operator == "<>":
                return left != right
            if operator == "<":
                return left < right  # type: ignore[operator]
            if operator == ">":
                return left > right  # type: ignore[operator]
            if operator == "<=":
                return left <= right  # type: ignore[operator]
            if operator == ">=":
                return left >= right  # type: ignore[operator]
        except TypeError:
            return None
        return None

    def _apply_arithmetic(
        self,
        operator: str,
        left: ScalarValue,
        right: ScalarValue,
    ) -> ScalarValue | object:
        if isinstance(left, bool) or isinstance(right, bool):
            return UNKNOWN
        if not isinstance(left, int | float) or not isinstance(right, int | float):
            return UNKNOWN
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        if operator == "/":
            if right == 0:
                return UNKNOWN
            return left / right
        return UNKNOWN

    def _static_literal(self, value: Any) -> ScalarValue | object:
        if isinstance(value, IntLiteral):
            return int(value)
        if isinstance(value, FloatLiteral):
            return float(value)
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value
        if isinstance(value, str):
            return value
        return UNKNOWN

    def _state_key(
        self,
        module_path: list[str],
        variable_name: str,
        field_path: str,
    ) -> tuple[str, ...]:
        segments = [segment.casefold() for segment in module_path]
        segments.append(variable_name.casefold())
        if field_path:
            segments.extend(segment.casefold() for segment in field_path.split(".") if segment)
        return tuple(segments)

    def _old_state_key(self, key: tuple[str, ...]) -> tuple[str, ...]:
        return OLD_PREFIX + key

    def _pending_state_key(self, key: tuple[str, ...]) -> tuple[str, ...]:
        return PENDING_PREFIX + key

    def _is_pending_state_key(self, key: tuple[str, ...]) -> bool:
        return key[: len(PENDING_PREFIX)] == PENDING_PREFIX

    def _expr_text(self, expr: Any) -> str:
        return str(_format_expr(expr)).replace("\n", " ").strip()

    def _sequence_node_label(self, node: object) -> str:
        node_name = getattr(node, "name", None)
        if node_name:
            return f"{type(node).__name__}:{node_name}"
        if isinstance(node, SFCFork):
            return f"SFCFork:{node.target}"
        return type(node).__name__

    def _is_from_root_origin(
        self,
        origin_file: str | None,
        origin_lib: str | None = None,
    ) -> bool:
        if self._analyzed_target_is_library:
            root_origin_lib = getattr(self.bp, "origin_lib", None)
            if root_origin_lib and origin_lib:
                return origin_lib.casefold() == root_origin_lib.casefold()

        if not origin_file:
            return True
        root_origin = getattr(self.bp, "origin_file", None)
        if not root_origin:
            return False
        return origin_file.rsplit(".", 1)[0].casefold() == root_origin.rsplit(".", 1)[0].casefold()

    def _site_str(self) -> str:
        return " > ".join(self._site_stack)

    def _push_site(self, label: str) -> None:
        if label:
            self._site_stack.append(label)

    def _pop_site(self) -> None:
        if self._site_stack:
            self._site_stack.pop()

    def _add_issue(
        self,
        *,
        kind: str,
        message: str,
        module_path: list[str],
        data: dict[str, Any] | None = None,
    ) -> None:
        self._issues.append(
            Issue(
                kind=kind,
                message=message,
                module_path=module_path.copy(),
                data=data or None,
            )
        )


def analyze_dataflow(
    base_picture: BasePicture,
    *,
    unavailable_libraries: set[str] | None = None,
    analyzed_target_is_library: bool = False,
) -> SimpleReport:
    analyzer = DataflowAnalyzer(
        base_picture,
        unavailable_libraries=unavailable_libraries,
        analyzed_target_is_library=analyzed_target_is_library,
    )
    return SimpleReport(name=base_picture.header.name, issues=analyzer.run())
