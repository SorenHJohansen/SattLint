"""Secure-candidate facts collected during the variable traversal.

A local written in a step and then read by a transition guard has to survive a
controller restart for the sequence to resume from the same point. The check is
a heuristic: it only reports declarations that are written in the module's own
sequence code, read in a transition guard, and not already secured.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sattlint.parser_api import ScalarDatatype, Variable

from ...models._variable_issues import DECLARATION_ROLE_LOCAL_VARIABLE, SecureCandidateIssue
from ...resolution.scope import ScopeContext

_SECURE_CANDIDATE_DATATYPES: frozenset[ScalarDatatype] = frozenset(
    {ScalarDatatype.REAL, ScalarDatatype.INTEGER, ScalarDatatype.BOOLEAN}
)


@dataclass(slots=True)
class _Candidate:
    module_path: list[str]
    decl_key: tuple[str, ...]
    variable: Variable
    write_sites: set[str] = field(default_factory=lambda: set[str]())
    transition_sites: set[str] = field(default_factory=lambda: set[str]())


@dataclass(slots=True)
class SecureCandidateFacts:
    """Reads, writes, and unconditional equation writes observed in traversal."""

    candidates: dict[int, _Candidate] = field(default_factory=lambda: dict[int, _Candidate]())
    unconditional_equation_writes: set[int] = field(default_factory=lambda: set[int]())

    def record_write(
        self,
        variable: Variable,
        decl_module_path: list[str],
        display_path: list[str],
        site: str,
    ) -> None:
        self._candidate_for(variable, decl_module_path, display_path).write_sites.add(site)

    def record_transition_read(
        self,
        variable: Variable,
        decl_module_path: list[str],
        display_path: list[str],
        site: str,
    ) -> None:
        self._candidate_for(variable, decl_module_path, display_path).transition_sites.add(site)

    def record_unconditional_equation_write(self, variable: Variable) -> None:
        self.unconditional_equation_writes.add(id(variable))

    def build_issues(
        self,
        contexts_by_module_path: dict[tuple[str, ...], ScopeContext],
        *,
        root_library: str | None = None,
    ) -> list[SecureCandidateIssue]:
        issues: list[SecureCandidateIssue] = []
        for variable_id, candidate in self.candidates.items():
            if variable_id in self.unconditional_equation_writes:
                continue
            if not candidate.write_sites or not candidate.transition_sites:
                continue
            if not _is_candidate_declaration(
                candidate.variable,
                candidate.decl_key,
                contexts_by_module_path,
                root_library=root_library,
            ):
                continue
            transition_sites = tuple(sorted(candidate.transition_sites))
            write_sites = tuple(sorted(candidate.write_sites))
            issues.append(
                SecureCandidateIssue(
                    module_path=candidate.module_path,
                    variable=candidate.variable,
                    declaration_role=DECLARATION_ROLE_LOCAL_VARIABLE,
                    role=f"Secure candidate at {transition_sites[0]}",
                    site=transition_sites[0],
                    write_sites=write_sites,
                    transition_sites=transition_sites,
                )
            )
        return sorted(
            issues,
            key=lambda issue: (
                issue.module_path,
                issue.variable.name.casefold(),
                issue.site,
            ),
        )

    def _candidate_for(
        self,
        variable: Variable,
        decl_module_path: list[str],
        display_path: list[str],
    ) -> _Candidate:
        variable_id = id(variable)
        candidate = self.candidates.get(variable_id)
        if candidate is None:
            candidate = _Candidate(
                module_path=list(display_path or decl_module_path),
                decl_key=tuple(decl_module_path),
                variable=variable,
            )
            self.candidates[variable_id] = candidate
        return candidate


def _is_candidate_declaration(
    variable: Variable,
    decl_key: tuple[str, ...],
    contexts_by_module_path: dict[tuple[str, ...], ScopeContext],
    *,
    root_library: str | None,
) -> bool:
    if variable.const or variable.opsave or variable.secure or variable.state:
        return False
    if not isinstance(variable.datatype, ScalarDatatype):
        return False
    if variable.datatype not in _SECURE_CANDIDATE_DATATYPES:
        return False
    if len(decl_key) <= 1:
        # Root-level declarations are globals; another unit may own the value.
        return False
    declaring_context = contexts_by_module_path.get(decl_key)
    if declaring_context is None:
        return False
    if variable.name.casefold() in declaring_context.moduleparameter_keys:
        return False
    library = declaring_context.current_library
    return not (root_library and library and library.casefold() != root_library.casefold())


__all__ = ["SecureCandidateFacts"]
