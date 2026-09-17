"""SattLint package root exports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .__version__ import __version__

if TYPE_CHECKING:
    from .grammar import constants as constants


def __getattr__(name: str) -> Any:
    if name == "constants":
        from .grammar import constants as constants_module  # noqa: PLC0415

        globals()[name] = constants_module
        return constants_module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "__version__",
    "constants",
]
