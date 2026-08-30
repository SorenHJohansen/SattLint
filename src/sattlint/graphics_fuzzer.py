"""Atheris-based fuzz harness for graphics validation."""

import sys
from pathlib import Path

import atheris  # type: ignore[import-untyped]

from sattlint.graphics_validation import validate_graphics_text


def test_one_input(data: bytes) -> None:
    source = data.decode("utf-8", errors="replace")
    validate_graphics_text(source, Path("/tmp"))  # nosec


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
