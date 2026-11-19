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

import atexit
import os
import sys
import tempfile
from pathlib import Path

import atheris  # type: ignore[import-untyped]

from sattlint.graphics.validation import validate_graphics_text

# One file per process: rewriting it per input is cheaper than creating and
# deleting a temporary file for every test case.
_SPOOL_FD, _SPOOL_NAME = tempfile.mkstemp(prefix="sattlint-fuzz-", suffix=".g")
os.close(_SPOOL_FD)
_SPOOL = Path(_SPOOL_NAME)
atexit.register(_SPOOL.unlink, missing_ok=True)


def test_one_input(data: bytes) -> None:
    text = data.decode("utf-8", errors="replace")
    _SPOOL.write_bytes(data)
    validate_graphics_text(text, _SPOOL)


def _is_bounded(argv: list[str]) -> bool:
    return any(argument.startswith(("-runs=", "-max_total_time=")) for argument in argv)


def main() -> None:
    argv = sys.argv if _is_bounded(sys.argv) else [*sys.argv, "-max_total_time=60"]
    atheris.Setup(argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
