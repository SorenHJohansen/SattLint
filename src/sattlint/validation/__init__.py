"""Validation policy over parser diagnostics.

The parser owns the language rules. This package keeps SattLint's policy: which
finding is fatal, how it is rendered, and the strict error/notice shapes the
application already consumes.
"""

from __future__ import annotations

from .policy import WarningSink, error_for, notice_for, validate_basepicture_strict
from .shared import (
    RawSourceValidationError,
    StructuralValidationError,
    ValidationNotice,
    ValidationWarning,
    coerce_validation_notice,
)

__all__ = [
    "RawSourceValidationError",
    "StructuralValidationError",
    "ValidationNotice",
    "ValidationWarning",
    "WarningSink",
    "coerce_validation_notice",
    "error_for",
    "notice_for",
    "validate_basepicture_strict",
]
