"""Shared test helpers.

Pyright policy:
- Prefer typed helpers from this package for reusable fakes and input feeders.
- Use file-level ``reportPrivateUsage=false`` only in support modules that
  intentionally bundle private production seams for leaf tests.
- Use broader file-level suppressions only in genuinely dynamic UI or runtime
  tests where typed stubs would be more misleading than helpful.
"""

from .stubs import (
    AnalysisGraphStub,
    InputFeeder,
    NamedHeader,
    NamedObject,
    NoOpWriter,
    NullWriter,
    RealContext,
    RecordingWriter,
    make_input,
    named_object,
)

__all__ = [
    "AnalysisGraphStub",
    "InputFeeder",
    "NamedHeader",
    "NamedObject",
    "NoOpWriter",
    "NullWriter",
    "RealContext",
    "RecordingWriter",
    "make_input",
    "named_object",
]
