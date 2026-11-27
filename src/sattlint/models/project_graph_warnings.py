"""Warning sink shared by the project loader and the graphics attachment seam.

Both ``project`` and ``graphics`` may record a warning against a loaded
``ProjectGraph``. The sink lives here, below both layers, instead of in the
project loader package so neither layer has to reach the other.
"""

from __future__ import annotations

from ._validation_notice import ValidationWarning, coerce_validation_notice
from .project_graph import ProjectGraph

__all__ = ["record_project_warning"]


def record_project_warning(graph: ProjectGraph, name: str, message: ValidationWarning) -> None:
    graph.warnings.append(f"{name}: {coerce_validation_notice(message).message}")
