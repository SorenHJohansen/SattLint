from __future__ import annotations

from typing import Any

from ...resolution.scope import ScopeContext
from ..shared._dedupe import remember_once
from ._dataflow_common import PendingWrite, ResolvedRef, StateMap


class DataflowIssueReportingMixin:
    def _report_read_before_write(
        self: Any,
        resolved: ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if not remember_once(self._reported_read_before_write, dedupe_key):
            return
        self._add_issue(
            kind="dataflow.read_before_write",
            message=(f"Variable reference {resolved.display_name!r} may be read before it is assigned on this path."),
            module_path=module_path,
            data={"symbol": resolved.display_name, "site": site},
        )

    def _report_dead_overwrite(
        self: Any,
        pending: PendingWrite,
        resolved: ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, pending.display_name.casefold())
        if not remember_once(self._reported_dead_overwrite, dedupe_key):
            return
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
        self: Any,
        resolved: ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if not remember_once(self._reported_scan_cycle_stale_read, dedupe_key):
            return
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
        self: Any,
        resolved: ResolvedRef,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold())
        if not remember_once(self._reported_scan_cycle_implicit_new, dedupe_key):
            return
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
        self: Any,
        resolved: ResolvedRef,
        module_path: list[str],
        *,
        operation: str,
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, resolved.display_name.casefold(), operation)
        if not remember_once(self._reported_scan_cycle_temporal_misuse, dedupe_key):
            return
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

    def _report_invalid_state_access(
        self: Any,
        display_name: str,
        base_display_name: str,
        state_access: str,
        module_path: list[str],
    ) -> None:
        site = self._site_str()
        dedupe_key = (tuple(module_path), site, display_name.casefold())
        if not remember_once(self._reported_invalid_state_access, dedupe_key):
            return
        self._add_issue(
            kind="dataflow.invalid_state_access",
            message=(
                f"Variable reference {display_name!r} uses {state_access.upper()} on non-STATE variable "
                f"{base_display_name!r}."
            ),
            module_path=module_path,
            data={
                "symbol": display_name,
                "state_symbol": base_display_name,
                "site": site,
            },
        )

    def _report_expression_temporal_hazards(
        self: Any,
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
            sample = next(iter(group["old"] or group["explicit_new"] or group["implicit_current"]), None)
            if sample is None:
                continue
            if not self._has_pending_write_for_symbol(state, sample):
                continue
            for resolved in group["implicit_current"]:
                self._report_scan_cycle_implicit_new(resolved, module_path)
            if group["old"] and not group["explicit_new"] and not group["implicit_current"]:
                for resolved in group["old"]:
                    self._report_scan_cycle_stale_read(resolved, module_path)
