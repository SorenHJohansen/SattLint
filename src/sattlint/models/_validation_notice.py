"""Pure model type for validation notices."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ValidationNotice"]


@dataclass(frozen=True, slots=True)
class ValidationNotice:
    message: str
    line: int | None = None
    column: int | None = None
    length: int | None = None

    def __str__(self) -> str:
        return self.message
