"""SattLint policy over parser diagnostics.

The parser owns the language rules and returns ``Diagnostic`` values. This
module decides what SattLint does with them: the first error on a strict path
becomes a ``StructuralValidationError`` with line, column, and length. Every
parser diagnostic is final, because a project load is all or nothing. Wording
and severity policy stay here, not in the parser.
"""

from __future__ import annotations

from sattlint.parser_api import BasePicture, Diagnostic, validate_basepicture

from .shared import StructuralValidationError, ValidationNotice


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


def validate_basepicture_strict(basepic: BasePicture) -> None:
    """Run the parser validator and keep SattLint's raise-on-first-error contract.

    The parser's standalone path owns the external-datatype allowance. SattLint
    strict validation has no such switch, and every diagnostic is final, so the
    first one becomes the structural error.
    """
    diagnostics = validate_basepicture(basepic)
    if diagnostics:
        raise error_for(diagnostics[0])


__all__ = ["error_for", "notice_for", "validate_basepicture_strict"]
