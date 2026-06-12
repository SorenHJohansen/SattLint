"""Shared semantic-diagnostics cache helpers for LSP bundles."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from lsprotocol.types import Diagnostic


def semantic_diagnostics_for_path(
    bundle: Any,
    document_path: Path,
    *,
    collect: Callable[[Any, Path], Iterable[Diagnostic]],
) -> tuple[Diagnostic, ...]:
    resolved_path = document_path.resolve()
    with bundle.semantic_diagnostics_lock:
        cached = bundle.semantic_diagnostics_by_path.get(resolved_path)
    if cached is not None:
        return cached

    diagnostics = tuple(collect(bundle, resolved_path))
    with bundle.semantic_diagnostics_lock:
        cached = bundle.semantic_diagnostics_by_path.get(resolved_path)
        if cached is not None:
            return cached
        bundle.semantic_diagnostics_by_path[resolved_path] = diagnostics
    return diagnostics
