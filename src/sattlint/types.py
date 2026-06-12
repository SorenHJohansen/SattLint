"""Semantic string aliases for user-facing SattLint concepts."""

from __future__ import annotations

from typing import NewType

type VariableRef = dict[str, object]

ProjectPath = NewType("ProjectPath", str)
ProjectPath.__doc__ = "Normalized project-relative or workspace source path string."

TargetName = NewType("TargetName", str)
TargetName.__doc__ = "Configured program or library target name."

VariableId = NewType("VariableId", str)
VariableId.__doc__ = "Stable variable identifier used in diagnostics and reports."

__all__ = ["ProjectPath", "TargetName", "VariableId", "VariableRef"]
