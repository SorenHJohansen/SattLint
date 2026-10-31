"""SattLint policy over parser diagnostics.

The parser owns the language rules and returns ``Diagnostic`` values. This
module decides what SattLint does with them: the first error on a strict path
becomes a ``StructuralValidationError`` with line, column, and length; warnings
go to a sink as ``ValidationNotice`` values. Wording and severity policy stay
here, not in the parser.
"""

from __future__ import annotations

from collections.abc import Callable

from sattline_parser.models.ast_model import BasePicture
from sattline_parser.validation import Diagnostic, DiagnosticSeverity, validate_basepicture

from .shared import StructuralValidationError, ValidationNotice

type WarningSink = Callable[[ValidationNotice], None]


def notice_for(diagnostic: Diagnostic) -> ValidationNotice:
    """Translate one parser diagnostic into SattLint's notice shape."""
    span = diagnostic.span
    return ValidationNotice(
        message=diagnostic.message,
        line=None if span is None else span.line,
        column=None if span is None else span.column,
        length=None if span is None else max(span.end - span.start, 0),
    )


def error_for(diagnostic: Diagnostic) -> StructuralValidationError:
    """Translate one parser diagnostic into SattLint's strict error shape."""
    notice = notice_for(diagnostic)
    return StructuralValidationError(
        notice.message,
        line=notice.line,
        column=notice.column,
        length=notice.length,
    )


def validate_basepicture_strict(
    basepic: BasePicture,
    *,
    warning_sink: WarningSink | None = None,
    allow_unresolved_external_datatypes: bool = False,
    **_ignored: object,
) -> None:
    """Run the parser validator and keep SattLint's raise-on-first-error contract.

    Extra keyword arguments are accepted so this stays a drop-in for the old
    ``validate_transformed_basepicture`` seam, whose callers passed policy flags
    that no longer belong to the validator.
    """
    for diagnostic in validate_basepicture(
        basepic,
        allow_unresolved_external_datatypes=allow_unresolved_external_datatypes,
    ):
        if diagnostic.severity is DiagnosticSeverity.ERROR:
            raise error_for(diagnostic)
        if warning_sink is not None:
            warning_sink(notice_for(diagnostic))


__all__ = ["WarningSink", "error_for", "notice_for", "validate_basepicture_strict"]
