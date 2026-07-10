"""Compatibility wrapper for the moved repo-audit entrypoints."""

from __future__ import annotations

from .audit import repo_audit_entrypoints as _owner


def _export_owner_names() -> list[str]:
    exported_names: list[str] = []
    for name in dir(_owner):
        if name.startswith("__"):
            continue
        globals()[name] = getattr(_owner, name)
        exported_names.append(name)
    return exported_names


__all__ = _export_owner_names()


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
