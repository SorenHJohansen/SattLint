"""Focused tests for custom LSP health and status requests."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from sattlint_lsp.document_state import DocumentState
from sattlint_lsp.server import LspSettings, SattLineLanguageServer, on_health, on_status


@pytest.mark.parametrize("handler", [on_health, on_status])
def test_health_and_status_requests_report_server_state(handler, tmp_path: Path) -> None:
    document_path = (tmp_path / "Program" / "Main.s").resolve()
    document_uri = document_path.as_uri()
    ls = SattLineLanguageServer()
    ls.workspace_root = tmp_path.resolve()
    ls.document_states[document_uri] = DocumentState(
        uri=document_uri,
        path=document_path,
        version=3,
        text='"SyntaxVersion"\n',
        is_dirty=True,
    )
    ls.document_paths[document_path] = document_uri
    ls.settings = LspSettings(workspace_diagnostics_mode="background")
    ls.workspace_scan_thread = threading.Thread()

    with ls.workspace_scan_condition:
        ls.entry_diagnostics = {"entry": {document_path: ()}}
        ls.published_workspace_diagnostics = {document_path: ()}
        ls.workspace_scan_pending = {document_path}
        ls.workspace_scan_generation = 7

    result = handler(ls)

    assert result == {
        "healthy": True,
        "status": "ok",
        "serverName": "sattline-lsp",
        "serverVersion": "0.1.0",
        "workspaceRoot": str(tmp_path.resolve()),
        "workspaceDiagnosticsMode": "background",
        "openDocumentCount": 1,
        "trackedDocumentPathCount": 1,
        "entryDiagnosticCount": 1,
        "publishedWorkspaceDiagnosticCount": 1,
        "pendingWorkspaceScanCount": 1,
        "workspaceScanGeneration": 7,
        "workspaceScanThreadAlive": False,
    }
