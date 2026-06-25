"""Atheris-based fuzz harness for engine-level parse + structural validation."""

import sys

import atheris  # type: ignore[import-untyped]

from sattlint.engine import parse_source_text


def test_one_input(data: bytes) -> None:
    source = data.decode("utf-8", errors="replace")
    parse_source_text(source)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
