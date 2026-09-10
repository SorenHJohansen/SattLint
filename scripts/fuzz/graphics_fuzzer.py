"""Atheris fuzz target for SattLint's own serialized-graphics validator.

Exercises ``graphics/validation.py:validate_graphics_text`` (the .g/.y record
parser) against arbitrary bytes. This is SattLint-owned — serialized graphics
files are not parsed by ``sattline-parser`` (which fuzzes its own grammar in
its own repo), so any crash found here is a bug in SattLint's graphics
validation.

The validator is tolerant by design, so an exception escaping it is a genuine
crash and is left uncaught for atheris to record.

Run locally::

    python -m pip install "atheris>=3.1"
    python scripts/fuzz/graphics_fuzzer.py -runs=100000 -max_len=4096

CI runs a short bounded session (see .github/workflows/ci.yml fuzz-smoke).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import atheris  # type: ignore[import-untyped]

from sattlint.graphics.validation import validate_graphics_text


def test_one_input(data: bytes) -> None:
    text = data.decode("utf-8", errors="replace")
    with tempfile.NamedTemporaryFile(suffix=".g", delete=False) as handle:
        handle.write(data)
        tmp_path = Path(handle.name)
    try:
        validate_graphics_text(text, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
