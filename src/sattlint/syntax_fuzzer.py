"""Atheris-based fuzz harness for end-to-end file syntax validation."""

import sys
import tempfile
from pathlib import Path

import atheris  # type: ignore[import-untyped]

from sattlint.engine import validate_single_file_syntax


def test_one_input(data: bytes) -> None:
    with tempfile.NamedTemporaryFile(suffix=".s", delete=False) as f:
        f.write(data)
        tmp_path = Path(f.name)
    try:
        validate_single_file_syntax(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
