"""Atheris-based fuzz harness for the SattLine parser.

ClusterFuzzLite uses atheris-based fuzz targets.
This harness wraps the existing fuzz_harness for compatibility.
"""

import sys

import atheris  # type: ignore[import-untyped]

from sattline_parser.fuzz_harness import fuzz_parse_text


def test_one_input(data: bytes) -> None:
    source = data.decode("utf-8", errors="replace")
    fuzz_parse_text(source)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
