from __future__ import annotations

from pathlib import Path

from ._server_helpers import LspSettings

_WORKSPACE_CONTROL_SUFFIXES = {".l", ".z"}


def workspace_settings_signature(settings: LspSettings) -> tuple[object, ...]:
    return (
        settings.entry_file,
        settings.mode,
        settings.scan_root_only,
        settings.enable_variable_diagnostics,
        settings.workspace_diagnostics_mode,
        settings.max_cached_entry_snapshots,
    )


def is_workspace_control_path(workspace_root: Path | None, document_path: Path) -> bool:
    if workspace_root is None or document_path.suffix.lower() not in _WORKSPACE_CONTROL_SUFFIXES:
        return False

    resolved_root = workspace_root.resolve()
    resolved_path = document_path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        return False
    return True
