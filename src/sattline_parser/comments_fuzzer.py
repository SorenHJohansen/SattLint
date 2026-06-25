"""Atheris-based fuzz harness for the SattLine comment stripper."""

import sys

import atheris  # type: ignore[import-untyped]

from sattline_parser.utils.text_processing import strip_sl_comments


def test_one_input(data: bytes) -> None:
    source = data.decode("utf-8", errors="replace")
    strip_sl_comments(source)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
