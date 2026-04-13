"""SattLint package root exports."""

from importlib import import_module
from typing import Any

from .grammar import constants as constants


def discover_workspace_sources(*args: Any, **kwargs: Any):
	return import_module("sattlint.editor_api").discover_workspace_sources(*args, **kwargs)


def load_workspace_snapshot(*args: Any, **kwargs: Any):
	return import_module("sattlint.editor_api").load_workspace_snapshot(*args, **kwargs)

__all__ = [
	"constants",
	"discover_workspace_sources",
	"load_workspace_snapshot",
]
