"""Pure model type for validation notices."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ValidationNotice", "ValidationWarning", "coerce_validation_notice"]

type ValidationWarning = ValidationNotice | str


@dataclass(frozen=True, slots=True)
class ValidationNotice:
    message: str
    line: int | None = None
    column: int | None = None
    length: int | None = None

    def __str__(self) -> str:
        return self.message


def coerce_validation_notice(value: ValidationWarning) -> ValidationNotice:
    if isinstance(value, ValidationNotice):
        return value
    return ValidationNotice(message=value)
