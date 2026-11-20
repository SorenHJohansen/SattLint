"""Terminal-agnostic application layer for SattLint.

The modules in this package orchestrate the SattLint workflows — project
loading, analyses, checks, and the interactive menu composition — using
direct imports from the owning implementation modules.  They do not depend
on a concrete terminal: console-facing behaviour is injected through
explicit parameters whose defaults target the standard helpers in
:mod:`sattlint.console`.

Submodules are imported explicitly by their callers; this package deliberately
re-exports nothing, because eager imports here would make ``sattlint.runs``
import its own consumer while the package is still initializing.
"""
