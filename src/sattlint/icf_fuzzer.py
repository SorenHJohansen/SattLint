"""Atheris-based fuzz harness for ICF file parser."""

import sys
import tempfile
from pathlib import Path

import atheris  # type: ignore[import-untyped]

from sattlint.analyzers.icf._icf_file_io import parse_icf_file


def test_one_input(data: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".icf", delete=False) as f:
        f.write(data)
        tmp_path = Path(f.name)
    try:
        parse_icf_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
