"""Stable reporting boundary for SattLint.

Analyzers emit structured results (model types such as ``IssueKind``,
``VariableIssue``, ``ICFEntry``, ``MMSInterfaceHit``) and ``reporting/`` owns
their public model types plus rendering.  The boundary rules:

- Analyzers import only the public reporting surface (``reporting.*``), never
  private modules (``reporting._*``) — enforced by
  ``tests/test_dependency_guard.py``.
- Rendering helpers (e.g. ``_variables_report_rendering``) stay private to the
  reporting package; analyzers never call them.
- ``reporting/`` is not a compatibility facade; public model modules are the
  surface.
"""

from __future__ import annotations

__all__: list[str] = []
