"""Isolated-session contract summary extraction for ModuleTypeDef.

Step-1 provider
---------------
The expensive legacy path (:func:`~sattlint.analyzers.variables._variables_contracts._get_required_parameter_names_for_typedef`)
rebuilds a full nested :class:`VariablesAnalyzer` per distinct typedef and re-walks its
entire transitive closure to learn which module parameters must be connected. That is
both expensive (analyzer construction per typedef) and redundant across identical
definitions.

This module replaces it with an :class:`ContractSummaryProvider`:

* Each requested typedef ("root") is analyzed in its own isolated session
  (:class:`ContractExtractionSession`) with fresh mutable analysis state, so usage
  accumulated while walking one root is never conflated with usage from any other
  root. This preserves the legacy per-typedef independent closure semantics.
* The projected :class:`ModuleTypeContract` is cached by ``id(owner)`` and published
  only after the root analysis completes, so a partial result is never observable;
  concurrent requests for the same owner wait on a completion lock.
* Sessions are issue-suppressed (``selected_issue_kinds=frozenset()``) and parameter-
  mapping validation is disabled for their whole lifetime: only the symbolic usage
  walk is performed, no diagnostics are produced or validated.

What is cached is only the projected, immutable per-root summary. A child typedef is
never harvested into the global index merely because it was visited while analyzing a
parent; its usage belongs to that parent-rooted session.

ANYTYPE field contracts are intentionally kept in the existing cumulative ANYTYPE
pass (which has different accumulation semantics); the two sources are composed into
one :class:`ContractIndex` by the caller.
"""

# pyright: reportPrivateUsage=false
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from types import MappingProxyType
from typing import TYPE_CHECKING

from sattline_parser.models.ast_model import BasePicture, ModuleTypeDef

from ...models.usage import VariableUsage
from ...utils.casefolding import casefold_key
from ..shared._contract_index import ModuleTypeContract, ParameterEffect

if TYPE_CHECKING:
    from collections.abc import Generator

    from . import VariablesAnalyzer


@dataclass(frozen=True, slots=True)
class _ProviderPolicy:
    """Immutable policy the provider passes to every session it creates."""

    collector_class: type
    unavailable_libraries: frozenset[str]
    analyzed_target_is_library: bool
    include_dependency_moduletype_usage: bool


class ContractExtractionSession:
    """One logically-fresh analysis session rooted at a single typedef.

    The session references the immutable base-picture AST plus shared foundation
    indexes, but owns fresh usage / symbol / context / effect state, so walking one
    root cannot leak usage into another root. It is discarded after the root summary
    is projected.
    """

    _analyzer: VariablesAnalyzer

    def __init__(
        self,
        base_picture: BasePicture,
        policy: _ProviderPolicy,
        shared_artifacts: object | None,
    ) -> None:
        self._analyzer = policy.collector_class(
            base_picture,
            debug=False,
            fail_loudly=False,
            unavailable_libraries=set(policy.unavailable_libraries),
            analyzed_target_is_library=policy.analyzed_target_is_library,
            include_dependency_moduletype_usage=policy.include_dependency_moduletype_usage,
            selected_issue_kinds=frozenset(),
            trace_recorder=None,
            build_anytype_contracts=False,
            shared_artifacts=shared_artifacts,
        )
        # Marker guarding the requesting analyzer against accidental provider recursion:
        # sessions must never lazily build their own summary provider (their walks are
        # issue-suppressed so they do not consult the provider, but the marker makes that
        # invariant explicit and future-proof).
        self._analyzer._is_contract_session = True

    @property
    def bp(self) -> BasePicture:
        return self._analyzer.bp

    @property
    def usage_tracker(self) -> object:
        return self._analyzer.usage_tracker

    @contextmanager
    def suppress_diagnostics(self) -> Generator[None]:
        """Context under which the session performs an issue-free symbol walk."""
        yield

    def analyze_typedef(self, owner: ModuleTypeDef, path: list[str]) -> None:
        self._analyzer.analyze_typedef(owner, path)


class ContractSummaryProvider:
    """Produces and caches the isolated per-typedef :class:`ModuleTypeContract`.

    One provider is created per collector flavor so SFC traversal semantics match the
    requesting analyzer.
    """

    def __init__(
        self,
        base_picture: BasePicture,
        *,
        collector_class: type,
        unavailable_libraries: frozenset[str] | None,
        analyzed_target_is_library: bool,
        include_dependency_moduletype_usage: bool,
        shared_artifacts: object | None = None,
    ) -> None:
        self._base_picture = base_picture
        self._policy = _ProviderPolicy(
            collector_class=collector_class,
            unavailable_libraries=frozenset(unavailable_libraries or frozenset()),
            analyzed_target_is_library=analyzed_target_is_library,
            include_dependency_moduletype_usage=include_dependency_moduletype_usage,
        )
        self._shared_artifacts = shared_artifacts
        self._completed: dict[int, ModuleTypeContract] = {}
        self._completion_locks: dict[int, Lock] = {}
        self._global_lock = Lock()

    def get(self, owner: ModuleTypeDef) -> ModuleTypeContract:
        owner_id = id(owner)
        cached = self._completed.get(owner_id)
        if cached is not None:
            return cached

        lock = self._completion_locks.setdefault(owner_id, Lock())
        with lock:
            cached = self._completed.get(owner_id)
            if cached is not None:
                return cached
            session = ContractExtractionSession(
                self._base_picture,
                self._policy,
                self._shared_artifacts,
            )
            with session.suppress_diagnostics():
                session.analyze_typedef(
                    owner,
                    path=[session.bp.header.name, f"TypeDef:{owner.name}"],
                )
            result = project_contract(owner, session.usage_tracker)
            with self._global_lock:
                self._completed[owner_id] = result
            return result


def project_contract(owner: ModuleTypeDef, usage_tracker: object) -> ModuleTypeContract:
    """Project a :class:`ModuleTypeContract` for ``owner`` from a walker's usage tracker."""
    effects: dict[str, ParameterEffect] = {}
    for variable in owner.moduleparameters or []:
        usage = _session_usage(usage_tracker, variable)
        effects[casefold_key(variable.name)] = ParameterEffect(
            read=bool(usage.read),
            ui_read=bool(usage.ui_read),
            non_ui_read=bool(usage.non_ui_read),
            written=bool(usage.written),
            field_reads=frozenset((usage.field_reads or {}).keys()),
            field_writes=frozenset((usage.field_writes or {}).keys()),
        )
    return ModuleTypeContract(effects_by_parameter=MappingProxyType(effects))


def _session_usage(usage_tracker: object, variable: object) -> VariableUsage:
    return usage_tracker.get_usage(variable)  # type: ignore[union-attr]


__all__ = ["ContractExtractionSession", "ContractSummaryProvider", "project_contract"]
