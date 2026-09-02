"""Terminal-agnostic application layer for SattLint.

The modules in this package orchestrate the SattLint workflows — project
loading, analyses, checks, and the interactive menu composition — using
direct imports from the owning implementation modules.  They do not depend
on a concrete terminal: console-facing behaviour is injected through
explicit parameters whose defaults target the standard helpers in
:mod:`sattlint.app_base` and :mod:`sattlint.console`.
"""

from __future__ import annotations

from . import analyze as analyze
from . import project as project

__all__ = ["analyze", "project"]
