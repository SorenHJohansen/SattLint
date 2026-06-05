"""Shared error classes and span helpers for SattLine validation."""

from __future__ import annotations

from collections.abc import Callable

from sattline_parser.models.ast_model import SourceSpan

from .models._validation_notice import ValidationNotice

__all__ = [
    "RawSourceValidationError",
    "StructuralValidationError",
    "ValidationNotice",
    "ValidationWarning",
    "ValidationWarningSink",
    "_ref_span",
    "_span_kwargs",
    "_warn_or_raise",
    "coerce_validation_notice",
]


type ValidationWarning = ValidationNotice | str
type ValidationWarningSink = Callable[[ValidationWarning], None]


class StructuralValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        length: int | None = None,
    ):
        super().__init__(message)
        self.line = line
        self.column = column
        self.length = length


class RawSourceValidationError(StructuralValidationError):
    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        length: int | None = None,
    ):
        super().__init__(message)
        self.line = line
        self.column = column
        self.length = length


def _span_kwargs(span: SourceSpan | None) -> dict[str, int]:
    if span is None:
        return {}
    return {"line": span.line, "column": span.column}


def coerce_validation_notice(value: ValidationWarning) -> ValidationNotice:
    if isinstance(value, ValidationNotice):
        return value
    return ValidationNotice(message=value)


def _warn_or_raise(
    message: str,
    *,
    warning_sink: ValidationWarningSink | None = None,
    line: int | None = None,
    column: int | None = None,
    length: int | None = None,
) -> None:
    if warning_sink is not None:
        warning_sink(
            ValidationNotice(
                message=message,
                line=line,
                column=column,
                length=length,
            )
        )
        return
    raise StructuralValidationError(
        message,
        line=line,
        column=column,
        length=length,
    )


def _ref_span(ref: dict[str, object] | str | None) -> SourceSpan | None:
    if not isinstance(ref, dict):
        return None
    span = ref.get("span")
    return span if isinstance(span, SourceSpan) else None
