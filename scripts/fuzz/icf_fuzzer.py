"""Atheris fuzz target for SattLint's own ICF config reader.

Exercises ``decode_icf_text`` and ``parse_icf_file`` against arbitrary bytes.
These are SattLint-owned — the .icf format is not parsed by
``sattline-parser`` (which fuzzes its own grammar in its own repo), so any
crash found here is a bug in SattLint's ICF handling.

The readers are tolerant by design, so an exception escaping any of them is a
genuine crash and is left uncaught for atheris to record.

Run locally::

    python -m pip install "atheris>=3.1"
    python scripts/fuzz/icf_fuzzer.py -runs=100000 -max_len=4096

CI runs a short bounded session (see .github/workflows/ci.yml fuzz-smoke).
"""

from __future__ import annotations

import atexit
import os
import sys
import tempfile
from pathlib import Path

import atheris  # type: ignore[import-untyped]

from sattlint.analyzers.icf._icf_file_io import decode_icf_text, parse_icf_file

# One file per process: rewriting it per input is cheaper than creating and
# deleting a temporary file for every test case.
_SPOOL_FD, _SPOOL_NAME = tempfile.mkstemp(prefix="sattlint-fuzz-", suffix=".icf")
os.close(_SPOOL_FD)
_SPOOL = Path(_SPOOL_NAME)
atexit.register(_SPOOL.unlink, missing_ok=True)


def test_one_input(data: bytes) -> None:
    decode_icf_text(data)
    _SPOOL.write_bytes(data)
    parse_icf_file(_SPOOL)


def _is_bounded(argv: list[str]) -> bool:
    return any(argument.startswith(("-runs=", "-max_total_time=")) for argument in argv)


def main() -> None:
    argv = sys.argv if _is_bounded(sys.argv) else [*sys.argv, "-max_total_time=60"]
    atheris.Setup(argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
