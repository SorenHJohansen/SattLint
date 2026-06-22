"""Repo-audit family package."""

from __future__ import annotations

from typing import Any

from . import repo_audit, repo_audit_cli, repo_audit_entrypoints, repo_audit_runs, repo_audit_shared


def __getattr__(name: str) -> Any:
    return getattr(repo_audit, name)


def __dir__() -> list[str]:
    return sorted(
        set(globals())
        | set(dir(repo_audit))
        | set(dir(repo_audit_cli))
        | set(dir(repo_audit_entrypoints))
        | set(dir(repo_audit_runs))
        | set(dir(repo_audit_shared))
    )


__all__ = [
    "repo_audit",
    "repo_audit_cli",
    "repo_audit_entrypoints",
    "repo_audit_runs",
    "repo_audit_shared",
]
