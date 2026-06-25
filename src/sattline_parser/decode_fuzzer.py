"""Atheris-based fuzz harness for the compressed text decoder."""

import sys

import atheris  # type: ignore[import-untyped]

from sattline_parser.grammar.parser_decode import preprocess_sl_text


def test_one_input(data: bytes) -> None:
    source = data.decode("utf-8", errors="replace")
    preprocess_sl_text(source)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
