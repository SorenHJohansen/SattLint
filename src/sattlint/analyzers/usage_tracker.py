"""Tracks variable usage and access events."""
from __future__ import annotations
from typing import TYPE_CHECKING
from ..models.usage import VariableUsage
from ..resolution import AccessGraph, AccessEvent, AccessKind, CanonicalPath

if TYPE_CHECKING:
    from ..models.ast_model import Variable
    from ..resolution.scope import ScopeContext

class UsageTracker:
    def __init__(self):
        self._variable_usages: dict[int, VariableUsage] = {}
        self.access_graph = AccessGraph()

    def get_usage(self, variable: Variable) -> VariableUsage:
        vid = id(variable)
        if vid not in self._variable_usages:
            self._variable_usages[vid] = VariableUsage()
        return self._variable_usages[vid]

    def record_access(
        self,
        kind: AccessKind,
        canonical_path: CanonicalPath,
        context: ScopeContext,
        syntactic_ref: str,
    ) -> None:
        self.access_graph.add(
            AccessEvent(
                kind=kind,
                canonical_path=canonical_path,
                use_module_path=tuple(context.module_path),
                use_display_path=tuple(context.display_module_path),
                syntactic_ref=syntactic_ref,
            )
        )

    def mark_ref_access(
        self,
        variable: Variable,
        field_path: str | None,
        decl_module_path: list[str],
        context: ScopeContext,
        path: list[str],
        kind: AccessKind,
        syntactic_ref: str,
    ) -> None:
        usage = self.get_usage(variable)

        if kind is AccessKind.READ:
            if field_path:
                usage.mark_field_read(field_path, path)
            else:
                usage.mark_read(path)
        else:
            if field_path:
                usage.mark_field_written(field_path, path)
            else:
                usage.mark_written(path)

        # Create canonical path locally since it's usage tracking concern
        segs: list[str] = list(decl_module_path) + [variable.name]
        if field_path:
            segs.extend([p for p in field_path.split(".") if p])
        canonical = CanonicalPath(tuple(segs))

        self.record_access(
            kind=kind,
            canonical_path=canonical,
            context=context,
            syntactic_ref=syntactic_ref,
        )
